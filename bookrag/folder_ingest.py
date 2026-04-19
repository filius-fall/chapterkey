"""Folder-based book ingestion helpers."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bookrag.services import BookRAGService


SUPPORTED_EXTENSIONS = {".epub", ".pdf"}
SKIP_SUFFIXES = {".part", ".tmp", ".crdownload"}


@dataclass
class LocalIngestConfig:
    """Resolved local ingestion options."""

    library_id: int | None
    embedding_provider_id: int
    embedding_model: str
    chat_provider_id: int | None = None
    chat_model: str | None = None
    ocr_provider_id: int | None = None
    ocr_model: str | None = None
    ocr_mode: str = "disabled"
    confirm_ocr_cost: bool = False
    delete_source: bool | None = None
    chunk_size: int | None = None
    chunk_overlap: int | None = None


class FolderIngestor:
    """Watch or scan the configured input directory."""

    def __init__(self, service: BookRAGService):
        self.service = service

    @staticmethod
    def _should_skip(path: Path) -> bool:
        return (
            not path.is_file()
            or path.name.startswith(".")
            or path.suffix.lower() in SKIP_SUFFIXES
            or path.suffix.lower() not in SUPPORTED_EXTENSIONS
        )

    def stable_files(self, input_dir: Path | None = None, min_file_age_sec: int | None = None) -> list[Path]:
        """Return stable candidate files from the input directory."""
        folder = input_dir or self.service.settings.input_dir
        min_age = min_file_age_sec or self.service.settings.min_file_age_sec
        now = time.time()
        candidates: list[Path] = []
        for path in sorted(folder.iterdir()):
            if self._should_skip(path):
                continue
            stat = path.stat()
            if now - stat.st_mtime < min_age:
                continue
            candidates.append(path)
        return candidates

    def scan_once(
        self,
        config: LocalIngestConfig,
        input_dir: Path | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Process all stable files in the input directory once."""
        results: list[dict[str, Any]] = []
        for index, path in enumerate(self.stable_files(input_dir=input_dir), start=1):
            if limit is not None and index > limit:
                break
            try:
                results.append(
                    self.service.ingest_file_from_path(
                        path,
                        library_id=config.library_id,
                        embedding_provider_id=config.embedding_provider_id,
                        embedding_model=config.embedding_model,
                        chunk_size=config.chunk_size,
                        chunk_overlap=config.chunk_overlap,
                        ocr_provider_id=config.ocr_provider_id,
                        ocr_model=config.ocr_model,
                        ocr_mode=config.ocr_mode,
                        confirm_ocr_cost=config.confirm_ocr_cost,
                        delete_source=config.delete_source,
                    )
                )
            except Exception as exc:
                results.append({"error": str(exc), "file": str(path)})
        return results

    def watch_forever(
        self,
        config: LocalIngestConfig,
        input_dir: Path | None = None,
        interval_sec: int | None = None,
        limit_per_scan: int | None = None,
    ) -> None:
        """Continuously process new stable files."""
        sleep_for = interval_sec or self.service.settings.watch_interval_sec
        while True:
            self.scan_once(config=config, input_dir=input_dir, limit=limit_per_scan)
            time.sleep(sleep_for)
