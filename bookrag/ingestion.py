"""Document ingestion for EPUB and PDF files."""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz

from bookrag.providers import BaseProvider, ProviderConfig

# Import from legacy module in parent directory
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from epub_processor import EpubProcessor


logger = logging.getLogger(__name__)


@dataclass
class IngestedDocument:
    """Normalized document content for indexing."""

    title: str
    author: str | None
    source_type: str
    chunks: list[str]
    metadata: list[dict[str, Any]]
    stats: dict[str, Any]


class DocumentIngestor:
    """Convert uploaded documents into chunks and metadata."""

    def ingest_epub(self, file_path: Path, chunk_size: int, chunk_overlap: int) -> IngestedDocument:
        """Ingest an EPUB using the existing processor."""
        processor = EpubProcessor()
        processor.chunk_size = chunk_size
        processor.chunk_overlap = chunk_overlap
        book = processor.load_epub(str(file_path))
        title = processor.get_epub_title(book)
        author = None
        try:
            authors = book.get_metadata("DC", "creator")
            if authors:
                author = authors[0][0]
        except Exception:
            author = None
        chapters = processor.extract_text(book)
        chunks, metadata = processor.chunk_text(chapters, title)
        stats = {
            "title": title,
            "chapter_count": len(chapters),
            "chunk_count": len(chunks),
            "total_tokens": sum(item["token_count"] for item in metadata),
        }
        return IngestedDocument(
            title=title,
            author=author,
            source_type="epub",
            chunks=chunks,
            metadata=metadata,
            stats=stats,
        )

    def ingest_pdf(
        self,
        file_path: Path,
        chunk_size: int,
        chunk_overlap: int,
        ocr_provider: BaseProvider | None = None,
        ocr_config: ProviderConfig | None = None,
        ocr_model: str | None = None,
        force_ocr: bool = False,
    ) -> IngestedDocument:
        """Ingest a PDF through direct extraction and optional OCR."""
        document = fitz.open(file_path)
        processor = EpubProcessor()
        processor.chunk_size = chunk_size
        processor.chunk_overlap = chunk_overlap

        pages: list[tuple[str, str]] = []
        used_ocr = False
        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            text = page.get_text("text").strip()
            if force_ocr or not text:
                if not (ocr_provider and ocr_config and ocr_model):
                    raise ValueError("OCR provider and model are required for scanned or OCR-forced PDFs")
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                image_bytes = pixmap.tobytes("png")
                text = ocr_provider.ocr_images(ocr_config, ocr_model, [("image/png", image_bytes)]).strip()
                used_ocr = True
            if text:
                pages.append((f"Page {page_index + 1}", text))

        if not pages:
            raise ValueError("No readable text extracted from PDF")

        title = file_path.stem
        chunks, metadata = processor.chunk_text(pages, title)
        for item in metadata:
            item["page_number"] = item["chapter_index"] + 1
        stats = {
            "title": title,
            "chapter_count": len(pages),
            "chunk_count": len(chunks),
            "total_tokens": sum(item["token_count"] for item in metadata),
            "used_ocr": used_ocr,
            "page_count": document.page_count,
        }
        return IngestedDocument(
            title=title,
            author=None,
            source_type="pdf",
            chunks=chunks,
            metadata=metadata,
            stats=stats,
        )
