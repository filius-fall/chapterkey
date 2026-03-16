"""
EPUB processor for text extraction and chunking.
Handles EPUB file parsing and intelligent text segmentation.
"""
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple
from ebooklib import epub
from bs4 import BeautifulSoup
import tiktoken
from tqdm import tqdm

from config import Config

logger = logging.getLogger(__name__)

class EpubProcessor:
    """Processor for EPUB files."""

    def __init__(self):
        """Initialize EPUB processor."""
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        self.chunk_size = Config.CHUNK_SIZE
        self.chunk_overlap = Config.CHUNK_OVERLAP

    def load_epub(self, epub_path: str) -> epub.EpubBook:
        """
        Load an EPUB file.

        Args:
            epub_path: Path to EPUB file

        Returns:
            EpubBook object

        Raises:
            FileNotFoundError: If file doesn't exist
            Exception: If EPUB parsing fails
        """
        path = Path(epub_path)

        if not path.exists():
            raise FileNotFoundError(f"EPUB file not found: {epub_path}")

        try:
            book = epub.read_epub(str(path))
            logger.info(f"Loaded EPUB: {path.name}")
            return book
        except Exception as e:
            logger.error(f"Error loading EPUB: {e}")
            raise

    def get_epub_title(self, book: epub.EpubBook) -> str:
        """
        Get the title of an EPUB.

        Args:
            book: EpubBook object

        Returns:
            Title string or "Unknown" if not found
        """
        try:
            title = book.get_metadata('DC', 'title')
            if title:
                return title[0][0]
        except Exception:
            pass
        return "Unknown"

    def extract_text(self, book: epub.EpubBook) -> List[Tuple[str, str]]:
        """
        Extract text from all chapters in the EPUB.

        Args:
            book: EpubBook object

        Returns:
            List of (chapter_title, chapter_text) tuples
        """
        chapters = []

        # Get all items from the book
        try:
            items = list(book.get_items())
            logger.info(f"Found {len(items)} items in EPUB")

            for item in items:
                try:
                    item_name = item.get_name()
                    logger.debug(f"Item: {item_name}")

                    # Check if it's an HTML document (has .xhtml extension)
                    if item_name.endswith('.xhtml') and not any(x in item_name for x in ['nav', 'toc', 'ncx']):
                        content = item.get_content()
                        soup = BeautifulSoup(content, 'lxml')
                        text = soup.get_text(separator=' ', strip=True)

                        # Get chapter title from h1-h6 tags
                        title = None
                        for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                            if tag.get_text(strip=True):
                                title = tag.get_text(strip=True)
                                break

                        if text.strip():
                            chapters.append((title or "Untitled Chapter", text))

                except Exception as item_error:
                    logger.warning(f"Error processing item {item.get_name()}: {item_error}")
                    continue

        except Exception as e:
            logger.error(f"Error extracting text: {e}")
            raise

        logger.info(f"Extracted {len(chapters)} chapters")
        return chapters

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text using tiktoken.

        Args:
            text: Text to count

        Returns:
            Number of tokens
        """
        return len(self.tokenizer.encode(text))

    def chunk_text(
        self,
        chapters: List[Tuple[str, str]],
        epub_name: str
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Chunk text into manageable pieces.

        Args:
            chapters: List of (chapter_title, chapter_text) tuples
            epub_name: Name of the EPUB

        Returns:
            Tuple of (chunks, metadata_list)
        """
        chunks = []
        metadata_list = []

        chunk_id = 0

        for chapter_idx, (chapter_title, chapter_text) in enumerate(tqdm(chapters, desc="Chunking text")):
            # Clean and normalize text
            chapter_text = self._clean_text(chapter_text)

            if not chapter_text.strip():
                continue

            # Tokenize
            tokens = self.tokenizer.encode(chapter_text)
            token_count = len(tokens)

            # If chapter is small enough, use as single chunk
            if token_count <= self.chunk_size:
                chunks.append(chapter_text)
                metadata_list.append({
                    "epub": epub_name,
                    "chapter": chapter_title,
                    "chapter_index": chapter_idx,
                    "chunk_index": 0,
                    "token_count": token_count,
                    "total_chunks_in_chapter": 1
                })
                chunk_id += 1
                continue

            # Split chapter into chunks
            chunk_tokens = []
            chunk_texts = []

            for i, token in enumerate(tokens):
                chunk_tokens.append(token)

                if len(chunk_tokens) >= self.chunk_size:
                    # Decode chunk to text
                    chunk_text = self.tokenizer.decode(chunk_tokens)
                    chunk_texts.append(chunk_text)

                    # Create overlap
                    if len(chunk_tokens) > self.chunk_overlap:
                        chunk_tokens = chunk_tokens[-self.chunk_overlap:]
                    else:
                        chunk_tokens = []

            # Add remaining tokens
            if chunk_tokens:
                chunk_text = self.tokenizer.decode(chunk_tokens)
                chunk_texts.append(chunk_text)

            # Create metadata for each chunk
            for chunk_idx, chunk_text in enumerate(chunk_texts):
                chunks.append(chunk_text)
                metadata_list.append({
                    "epub": epub_name,
                    "chapter": chapter_title,
                    "chapter_index": chapter_idx,
                    "chunk_index": chunk_idx,
                    "token_count": self.count_tokens(chunk_text),
                    "total_chunks_in_chapter": len(chunk_texts)
                })
                chunk_id += 1

        logger.info(f"Created {len(chunks)} chunks from {len(chapters)} chapters")
        return chunks, metadata_list

    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize text.

        Args:
            text: Text to clean

        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        text = ' '.join(text.split())

        # Remove common artifacts
        text = text.replace('\u200b', '')  # Zero-width space
        text = text.replace('\ufeff', '')  # Zero-width no-break space

        return text.strip()

    def process_epub(self, epub_path: str) -> Dict[str, Any]:
        """
        Process an EPUB file completely.

        Args:
            epub_path: Path to EPUB file

        Returns:
            Dictionary with chunks, metadata, and stats
        """
        book = self.load_epub(epub_path)
        title = self.get_epub_title(book)

        # Extract text from chapters
        chapters = self.extract_text(book)

        # Chunk the text
        chunks, metadata_list = self.chunk_text(chapters, title)

        # Calculate stats
        total_tokens = sum(m["token_count"] for m in metadata_list)
        unique_chapters = len(set(m["chapter"] for m in metadata_list))

        stats = {
            "title": title,
            "path": epub_path,
            "chapter_count": len(chapters),
            "chunk_count": len(chunks),
            "total_tokens": total_tokens,
            "unique_chapters": unique_chapters,
            "avg_chunk_tokens": total_tokens / len(chunks) if chunks else 0
        }

        return {
            "chunks": chunks,
            "metadata": metadata_list,
            "stats": stats
        }
