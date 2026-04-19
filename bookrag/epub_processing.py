"""Internal EPUB processing helpers for installed BookRAG packages."""

from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from ebooklib import epub
import tiktoken
from tqdm import tqdm
import warnings


logger = logging.getLogger(__name__)


class EpubProcessor:
    """Processor for EPUB files."""

    def __init__(self, chunk_size: int = 750, chunk_overlap: int = 100):
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def load_epub(self, epub_path: str) -> epub.EpubBook:
        return epub.read_epub(epub_path)

    def get_epub_title(self, book: epub.EpubBook) -> str:
        try:
            title = book.get_metadata("DC", "title")
            if title:
                return str(title[0][0])
        except Exception:
            pass
        return "Unknown"

    def extract_text(self, book: epub.EpubBook) -> list[tuple[str, str]]:
        chapters: list[tuple[str, str]] = []
        items = list(book.get_items())
        for item in items:
            item_name = item.get_name()
            if not item_name.endswith(".xhtml") or any(token in item_name for token in ("nav", "toc", "ncx")):
                continue
            try:
                content = item.get_content()
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
                    soup = BeautifulSoup(content, "lxml")
                text = soup.get_text(separator=" ", strip=True)
                title = None
                for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
                    tag_text = tag.get_text(strip=True)
                    if tag_text:
                        title = tag_text
                        break
                if text.strip():
                    chapters.append((title or "Untitled Chapter", text))
            except Exception as exc:
                logger.warning("Error processing EPUB item %s: %s", item_name, exc)
        return chapters

    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text))

    def chunk_text(self, chapters: list[tuple[str, str]], epub_name: str) -> tuple[list[str], list[dict[str, Any]]]:
        chunks: list[str] = []
        metadata_list: list[dict[str, Any]] = []

        for chapter_idx, (chapter_title, chapter_text) in enumerate(tqdm(chapters, desc="Chunking text")):
            chapter_text = self._clean_text(chapter_text)
            if not chapter_text.strip():
                continue
            tokens = self.tokenizer.encode(chapter_text)
            token_count = len(tokens)
            if token_count <= self.chunk_size:
                chunks.append(chapter_text)
                metadata_list.append(
                    {
                        "epub": epub_name,
                        "chapter": chapter_title,
                        "chapter_index": chapter_idx,
                        "chunk_index": 0,
                        "token_count": token_count,
                        "total_chunks_in_chapter": 1,
                    }
                )
                continue

            chunk_tokens: list[int] = []
            chunk_texts: list[str] = []
            for token in tokens:
                chunk_tokens.append(token)
                if len(chunk_tokens) >= self.chunk_size:
                    chunk_texts.append(self.tokenizer.decode(chunk_tokens))
                    chunk_tokens = chunk_tokens[-self.chunk_overlap :] if len(chunk_tokens) > self.chunk_overlap else []
            if chunk_tokens:
                chunk_texts.append(self.tokenizer.decode(chunk_tokens))

            for chunk_idx, chunk_text in enumerate(chunk_texts):
                chunks.append(chunk_text)
                metadata_list.append(
                    {
                        "epub": epub_name,
                        "chapter": chapter_title,
                        "chapter_index": chapter_idx,
                        "chunk_index": chunk_idx,
                        "token_count": self.count_tokens(chunk_text),
                        "total_chunks_in_chapter": len(chunk_texts),
                    }
                )
        return chunks, metadata_list

    @staticmethod
    def _clean_text(text: str) -> str:
        text = " ".join(text.split())
        text = text.replace("\u200b", "")
        text = text.replace("\ufeff", "")
        return text.strip()
