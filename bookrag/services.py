"""Shared application service layer for BookRAG."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any

from bookrag.db import Database, utc_now
from bookrag.ingestion import DocumentIngestor
from bookrag.providers import ProviderConfig, ProviderRegistry
from bookrag.security import (
    decrypt_secret,
    encrypt_secret,
    hash_password,
    hash_token,
    issue_token,
    verify_password,
)
from bookrag.settings import AppSettings
from bookrag.vector_store import VectorStore


logger = logging.getLogger(__name__)

SERIES_NUMBER_PATTERNS = (
    re.compile(r"(?:^|[\s._\-])vol(?:ume)?[\s._\-]*(\d+)(?:$|[\s._\-])", re.IGNORECASE),
    re.compile(r"(?:^|[\s._\-])book[\s._\-]*(\d+)(?:$|[\s._\-])", re.IGNORECASE),
    re.compile(r"(?:^|[\s._\-])part[\s._\-]*(\d+)(?:$|[\s._\-])", re.IGNORECASE),
    re.compile(r"#\s*(\d+)", re.IGNORECASE),
)


class BookRAGService:
    """Service layer shared by API, CLI, MCP, and web routes."""

    def __init__(self, settings: AppSettings | None = None):
        self.settings = settings or AppSettings.load()
        self.db = Database(self.settings.sqlite_path)
        self.vector_store = VectorStore(self.settings)
        self.providers = ProviderRegistry()
        self.ingestor = DocumentIngestor()
        self.sync_env_providers()

    def ensure_default_library(self) -> dict[str, Any]:
        """Create the default library if none exists."""
        library = self.db.fetch_one("SELECT * FROM libraries ORDER BY id LIMIT 1")
        if library:
            return library
        library_id = self.db.execute(
            "INSERT INTO libraries(name, description, created_at) VALUES (?, ?, ?)",
            (self.settings.default_library_name, "Default self-hosted BookRAG library", utc_now()),
        )
        return self.get_library(library_id)

    @staticmethod
    def _default_base_url(provider_type: str) -> str | None:
        if provider_type == "ollama":
            return "http://127.0.0.1:11434/v1"
        if provider_type == "openrouter":
            return "https://openrouter.ai/api/v1"
        if provider_type == "nvidia_nim":
            return "https://integrate.api.nvidia.com/v1"
        return None

    @staticmethod
    def _hash_bytes(raw: bytes) -> str:
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _hash_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def file_fingerprint(self, path: Path) -> str:
        """Return a SHA-256 fingerprint for a local file."""
        return self._hash_file(Path(path))

    def _normalize_spoiler_inputs(
        self,
        spoiler_mode: str = "full_context",
        context_mode: str | None = None,
        active_book_id: int | None = None,
        active_chapter_index: int | None = None,
    ) -> tuple[str, int | None, int | None]:
        if context_mode:
            if context_mode == "spoiler":
                spoiler_mode = "full_context"
            elif context_mode == "no_spoiler":
                spoiler_mode = "through_chapter"
                if active_book_id is None or active_chapter_index is None:
                    raise ValueError("no_spoiler mode requires active_book_id and active_chapter_index")
            else:
                raise ValueError("context_mode must be spoiler or no_spoiler")
        return spoiler_mode, active_book_id, active_chapter_index

    def _upsert_provider(
        self,
        *,
        name: str,
        provider_type: str,
        api_key: str,
        base_url: str | None = None,
        default_embedding_model: str | None = None,
        default_chat_model: str | None = None,
        default_ocr_model: str | None = None,
    ) -> dict[str, Any]:
        provider_id = self.db.execute(
            """
            INSERT INTO provider_credentials(
                name, provider_type, api_key_encrypted, base_url,
                default_embedding_model, default_chat_model, default_ocr_model, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                provider_type = excluded.provider_type,
                api_key_encrypted = excluded.api_key_encrypted,
                base_url = excluded.base_url,
                default_embedding_model = excluded.default_embedding_model,
                default_chat_model = excluded.default_chat_model,
                default_ocr_model = excluded.default_ocr_model
            """,
            (
                name,
                provider_type,
                encrypt_secret(api_key, self.settings.app_secret),
                base_url or self._default_base_url(provider_type),
                default_embedding_model,
                default_chat_model,
                default_ocr_model,
                utc_now(),
            ),
        )
        row = self.db.fetch_one("SELECT id FROM provider_credentials WHERE name = ?", (name,))
        if not row:
            raise ValueError("Provider could not be created")
        return self.public_provider(int(row["id"]))

    def sync_env_providers(self) -> None:
        """Seed provider configs from environment variables for local workflows."""
        provider_specs = [
            {
                "name": os.getenv("BOOKRAG_OLLAMA_PROVIDER_NAME", "Ollama Local"),
                "provider_type": "ollama",
                "api_key": os.getenv("BOOKRAG_OLLAMA_API_KEY", "ollama"),
                "base_url": os.getenv("BOOKRAG_OLLAMA_BASE_URL", self._default_base_url("ollama")),
                "default_embedding_model": os.getenv("BOOKRAG_OLLAMA_EMBEDDING_MODEL"),
                "default_chat_model": os.getenv("BOOKRAG_OLLAMA_CHAT_MODEL"),
                "default_ocr_model": os.getenv("BOOKRAG_OLLAMA_OCR_MODEL"),
            },
            {
                "name": os.getenv("BOOKRAG_OLLAMA_CLOUD_PROVIDER_NAME", "Ollama Cloud"),
                "provider_type": "openai_compatible",
                "api_key": os.getenv("BOOKRAG_OLLAMA_CLOUD_API_KEY", ""),
                "base_url": os.getenv("BOOKRAG_OLLAMA_CLOUD_BASE_URL"),
                "default_embedding_model": os.getenv("BOOKRAG_OLLAMA_CLOUD_EMBEDDING_MODEL"),
                "default_chat_model": os.getenv("BOOKRAG_OLLAMA_CLOUD_CHAT_MODEL"),
                "default_ocr_model": os.getenv("BOOKRAG_OLLAMA_CLOUD_OCR_MODEL"),
            },
            {
                "name": os.getenv("BOOKRAG_OPENROUTER_PROVIDER_NAME", "OpenRouter"),
                "provider_type": "openrouter",
                "api_key": os.getenv("BOOKRAG_OPENROUTER_API_KEY", ""),
                "base_url": os.getenv("BOOKRAG_OPENROUTER_BASE_URL", self._default_base_url("openrouter")),
                "default_embedding_model": os.getenv("BOOKRAG_OPENROUTER_EMBEDDING_MODEL"),
                "default_chat_model": os.getenv("BOOKRAG_OPENROUTER_CHAT_MODEL"),
                "default_ocr_model": os.getenv("BOOKRAG_OPENROUTER_OCR_MODEL"),
            },
            {
                "name": os.getenv("BOOKRAG_NVIDIA_PROVIDER_NAME", "NVIDIA"),
                "provider_type": "nvidia_nim",
                "api_key": os.getenv("BOOKRAG_NVIDIA_API_KEY", ""),
                "base_url": os.getenv("BOOKRAG_NVIDIA_BASE_URL", self._default_base_url("nvidia_nim")),
                "default_embedding_model": os.getenv("BOOKRAG_NVIDIA_EMBEDDING_MODEL", "nvidia/nv-embedqa-e5-v5"),
                "default_chat_model": os.getenv("BOOKRAG_NVIDIA_CHAT_MODEL"),
                "default_ocr_model": os.getenv("BOOKRAG_NVIDIA_OCR_MODEL"),
            },
        ]
        for spec in provider_specs:
            if spec["api_key"] or spec["provider_type"] == "ollama":
                self._upsert_provider(**spec)

    def admin_exists(self) -> bool:
        """Return whether an admin user is configured."""
        return self.db.fetch_one("SELECT id FROM admin_users LIMIT 1") is not None

    def setup_admin(self, username: str, password: str) -> dict[str, Any]:
        """Create the single admin user."""
        if self.admin_exists():
            raise ValueError("Admin user already exists")
        password_salt, password_hash = hash_password(password)
        admin_id = self.db.execute(
            """
            INSERT INTO admin_users(username, password_salt, password_hash, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (username, password_salt, password_hash, utc_now()),
        )
        self.ensure_default_library()
        return {"id": admin_id, "username": username}

    def login(self, username: str, password: str, token_name: str = "web-session") -> dict[str, Any]:
        """Authenticate and create a session token."""
        user = self.db.fetch_one("SELECT * FROM admin_users WHERE username = ?", (username,))
        if not user or not verify_password(password, user["password_salt"], user["password_hash"]):
            raise ValueError("Invalid username or password")
        raw_token = issue_token()
        self.db.execute(
            """
            INSERT INTO session_tokens(user_id, token_name, token_hash, created_at, last_used_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user["id"], token_name, hash_token(raw_token), utc_now(), utc_now()),
        )
        return {"token": raw_token, "user": {"id": user["id"], "username": user["username"]}}

    def authenticate_token(self, token: str) -> dict[str, Any]:
        """Validate a session or API token."""
        token_hash = hash_token(token)
        row = self.db.fetch_one(
            """
            SELECT admin_users.id, admin_users.username, session_tokens.id AS session_id
            FROM session_tokens
            JOIN admin_users ON admin_users.id = session_tokens.user_id
            WHERE session_tokens.token_hash = ?
            """,
            (token_hash,),
        )
        if not row:
            raise ValueError("Invalid authentication token")
        self.db.execute("UPDATE session_tokens SET last_used_at = ? WHERE id = ?", (utc_now(), row["session_id"]))
        return {"id": row["id"], "username": row["username"]}

    def list_providers(self) -> list[dict[str, Any]]:
        """List provider credentials without decrypted keys."""
        rows = self.db.fetch_all("SELECT * FROM provider_credentials ORDER BY name")
        return [self._sanitize_provider(row) for row in rows]

    def create_provider(
        self,
        name: str,
        provider_type: str,
        api_key: str,
        base_url: str | None = None,
        default_embedding_model: str | None = None,
        default_chat_model: str | None = None,
        default_ocr_model: str | None = None,
    ) -> dict[str, Any]:
        """Create a provider credential."""
        if provider_type not in self.providers.providers:
            raise ValueError(f"Unsupported provider type: {provider_type}")
        return self._upsert_provider(
            name=name,
            provider_type=provider_type,
            api_key=api_key,
            base_url=base_url,
            default_embedding_model=default_embedding_model,
            default_chat_model=default_chat_model,
            default_ocr_model=default_ocr_model,
        )

    def _get_provider_row(self, provider_id: int) -> dict[str, Any]:
        """Fetch one provider without the decrypted key."""
        provider = self.db.fetch_one("SELECT * FROM provider_credentials WHERE id = ?", (provider_id,))
        if not provider:
            raise ValueError("Provider not found")
        return provider

    @staticmethod
    def _sanitize_provider(provider: dict[str, Any]) -> dict[str, Any]:
        """Hide stored encrypted secrets from public responses."""
        public_provider = dict(provider)
        public_provider.pop("api_key_encrypted", None)
        return public_provider

    def public_provider(self, provider_id: int) -> dict[str, Any]:
        """Fetch a provider for API responses."""
        return self._sanitize_provider(self._get_provider_row(provider_id))

    def _provider_config(self, provider_id: int) -> ProviderConfig:
        """Load a decrypted provider config."""
        provider = self._get_provider_row(provider_id)
        return ProviderConfig(
            id=provider["id"],
            name=provider["name"],
            provider_type=provider["provider_type"],
            api_key=decrypt_secret(provider["api_key_encrypted"], self.settings.app_secret),
            base_url=provider["base_url"],
            default_embedding_model=provider["default_embedding_model"],
            default_chat_model=provider["default_chat_model"],
            default_ocr_model=provider["default_ocr_model"],
        )

    def list_libraries(self) -> list[dict[str, Any]]:
        """List all libraries."""
        return self.db.fetch_all("SELECT * FROM libraries ORDER BY id")

    def create_library(self, name: str, description: str | None = None) -> dict[str, Any]:
        """Create a library."""
        library_id = self.db.execute(
            "INSERT INTO libraries(name, description, created_at) VALUES (?, ?, ?)",
            (name, description, utc_now()),
        )
        return self.get_library(library_id)

    def get_library(self, library_id: int) -> dict[str, Any]:
        """Fetch a library."""
        library = self.db.fetch_one("SELECT * FROM libraries WHERE id = ?", (library_id,))
        if not library:
            raise ValueError("Library not found")
        return library

    def list_books(self, library_id: int) -> list[dict[str, Any]]:
        """List books within a library."""
        return self.db.fetch_all(
            """
            SELECT books.*, series.name AS series_name, series_books.sort_order AS series_order
            FROM books
            LEFT JOIN series_books ON series_books.book_id = books.id
            LEFT JOIN series ON series.id = series_books.series_id
            WHERE books.library_id = ?
            ORDER BY books.id
            """,
            (library_id,),
        )

    def get_book(self, book_id: int) -> dict[str, Any]:
        """Fetch a single book."""
        book = self.db.fetch_one("SELECT * FROM books WHERE id = ?", (book_id,))
        if not book:
            raise ValueError("Book not found")
        book["metadata"] = self.db.json_loads(book["metadata_json"])
        return book

    def upload_book(self, library_id: int, file_name: str, source_bytes: bytes) -> dict[str, Any]:
        """Save an uploaded book to disk and register it."""
        library = self.get_library(library_id)
        library_dir = self.settings.uploads_dir / f"library_{library['id']}"
        library_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(file_name).name
        source_type = Path(safe_name).suffix.lower().lstrip(".")
        if source_type not in {"epub", "pdf"}:
            raise ValueError("Only EPUB and PDF uploads are supported")
        source_path = library_dir / safe_name
        source_path.write_bytes(source_bytes)
        book_id = self.db.execute(
            """
            INSERT INTO books(
                library_id, title, author, file_name, source_path, source_type, ingest_status,
                source_fingerprint, managed_source_path, verification_status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                library_id,
                source_path.stem,
                None,
                safe_name,
                str(source_path),
                source_type,
                "uploaded",
                self._hash_bytes(source_bytes),
                str(source_path),
                "pending",
                utc_now(),
            ),
        )
        return self.get_book(book_id)

    def verify_book_vectors(self, library_id: int, book_id: int, expected_chunk_count: int) -> dict[str, Any]:
        """Verify that a book collection was written and is readable."""
        if not self.vector_store.collection_exists(library_id, book_id):
            raise ValueError("Book collection was not created")
        actual_count = self.vector_store.count_book_chunks(library_id, book_id)
        if actual_count != expected_chunk_count:
            raise ValueError(f"Expected {expected_chunk_count} chunks, found {actual_count}")
        sample = self.vector_store.sample_book_chunk(library_id, book_id)
        if not sample or not sample.get("document"):
            raise ValueError("No readable chunk found in vector store")
        metadata = sample.get("metadata") or {}
        for key in ("library_id", "book_id", "chunk_index"):
            if key not in metadata:
                raise ValueError(f"Missing required metadata field: {key}")
        return {"chunk_count": actual_count, "sample_metadata": metadata}

    def find_provider_by_name(self, name: str) -> dict[str, Any] | None:
        """Find a provider by its configured name."""
        provider = self.db.fetch_one("SELECT * FROM provider_credentials WHERE name = ?", (name,))
        return self._sanitize_provider(provider) if provider else None

    def default_provider_ids(self) -> dict[str, int | None]:
        """Resolve default provider ids from environment-backed provider names."""
        lookup = {
            "embedding_provider": os.getenv("BOOKRAG_DEFAULT_EMBEDDING_PROVIDER_NAME"),
            "chat_provider": os.getenv("BOOKRAG_DEFAULT_CHAT_PROVIDER_NAME"),
            "ocr_provider": os.getenv("BOOKRAG_DEFAULT_OCR_PROVIDER_NAME"),
        }
        resolved: dict[str, int | None] = {}
        for key, name in lookup.items():
            if not name:
                resolved[key] = None
                continue
            provider = self.find_provider_by_name(name)
            resolved[key] = int(provider["id"]) if provider else None
        return resolved

    def find_verified_book_by_fingerprint(self, library_id: int, fingerprint: str) -> dict[str, Any] | None:
        """Return a verified indexed book that matches the source fingerprint."""
        row = self.db.fetch_one(
            """
            SELECT books.*, series.name AS series_name, series_books.sort_order AS series_order
            FROM books
            LEFT JOIN series_books ON series_books.book_id = books.id
            LEFT JOIN series ON series.id = series_books.series_id
            WHERE books.library_id = ?
              AND books.source_fingerprint = ?
              AND books.ingest_status = 'ready'
              AND books.verification_status = 'verified'
            ORDER BY books.id DESC
            LIMIT 1
            """,
            (library_id, fingerprint),
        )
        return row

    def ingest_file_from_path(
        self,
        source_path: Path,
        *,
        library_id: int | None = None,
        embedding_provider_id: int,
        embedding_model: str,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        ocr_provider_id: int | None = None,
        ocr_model: str | None = None,
        ocr_mode: str = "disabled",
        confirm_ocr_cost: bool = False,
        delete_source: bool | None = None,
    ) -> dict[str, Any]:
        """Register and ingest a book from a filesystem path."""
        path = Path(source_path)
        if not path.exists():
            raise ValueError(f"File not found: {path}")
        source_type = path.suffix.lower().lstrip(".")
        if source_type not in {"epub", "pdf"}:
            raise ValueError("Only EPUB and PDF uploads are supported")

        library = self.get_library(library_id) if library_id else self.ensure_default_library()
        fingerprint = self._hash_file(path)
        existing = self.db.fetch_one(
            "SELECT * FROM books WHERE source_fingerprint = ? AND library_id = ? AND ingest_status = ?",
            (fingerprint, library["id"], "ready"),
        )
        if existing:
            if delete_source if delete_source is not None else self.settings.auto_delete_source:
                if path.resolve().parent == self.settings.input_dir.resolve():
                    path.unlink(missing_ok=True)
            return {"duplicate": True, "book": self.get_book(int(existing["id"]))}

        library_dir = self.settings.managed_books_dir / f"library_{library['id']}"
        library_dir.mkdir(parents=True, exist_ok=True)
        managed_path = library_dir / path.name
        if managed_path.exists():
            managed_path = library_dir / f"{path.stem}_{fingerprint[:8]}{path.suffix}"
        shutil.copy2(path, managed_path)
        book_id = self.db.execute(
            """
            INSERT INTO books(
                library_id, title, author, file_name, source_path, source_type, ingest_status,
                source_fingerprint, source_origin_path, managed_source_path, verification_status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                library["id"],
                path.stem,
                None,
                managed_path.name,
                str(managed_path),
                source_type,
                "uploaded",
                fingerprint,
                str(path),
                str(managed_path),
                "pending",
                utc_now(),
            ),
        )
        result = self.ingest_book(
            book_id=book_id,
            embedding_provider_id=embedding_provider_id,
            embedding_model=embedding_model,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            ocr_provider_id=ocr_provider_id,
            ocr_model=ocr_model,
            ocr_mode=ocr_mode,
            confirm_ocr_cost=confirm_ocr_cost,
            source_path=str(path),
        )
        should_delete = delete_source if delete_source is not None else self.settings.auto_delete_source
        if should_delete and path.resolve().parent == self.settings.input_dir.resolve():
            path.unlink(missing_ok=True)
            self.db.execute(
                "UPDATE ingest_jobs SET source_deleted = ?, updated_at = ? WHERE id = ?",
                (1, utc_now(), result["job_id"]),
            )
        return result

    def create_series(self, library_id: int, name: str) -> dict[str, Any]:
        """Create a series in a library."""
        series_id = self.db.execute(
            "INSERT INTO series(library_id, name, created_at) VALUES (?, ?, ?)",
            (library_id, name, utc_now()),
        )
        return self.get_series(series_id)

    def get_series(self, series_id: int) -> dict[str, Any]:
        """Fetch a series and its books."""
        series = self.db.fetch_one("SELECT * FROM series WHERE id = ?", (series_id,))
        if not series:
            raise ValueError("Series not found")
        books = self.db.fetch_all(
            """
            SELECT books.*, series_books.sort_order
            FROM series_books
            JOIN books ON books.id = series_books.book_id
            WHERE series_books.series_id = ?
            ORDER BY series_books.sort_order
            """,
            (series_id,),
        )
        series["books"] = books
        return series

    def list_series(self, library_id: int) -> list[dict[str, Any]]:
        """List all series in a library."""
        rows = self.db.fetch_all("SELECT * FROM series WHERE library_id = ? ORDER BY name", (library_id,))
        return [self.get_series(item["id"]) for item in rows]

    @staticmethod
    def _series_sort_key(value: str) -> tuple[int, str]:
        """Sort volume labels with numeric awareness."""
        match = re.search(r"\d+", value)
        if not match:
            return (10**9, value.lower())
        return (int(match.group(0)), value.lower())

    @staticmethod
    def _extract_series_position(text: str) -> tuple[int | None, str | None]:
        """Extract an ordered volume indicator from a title or filename."""
        for pattern in SERIES_NUMBER_PATTERNS:
            match = pattern.search(text)
            if match:
                number = int(match.group(1))
                return number, match.group(0).strip()
        standalone = re.search(r"(?:^|[\s._\-])(\d{1,3})(?:$|[\s._\-])", text)
        if standalone:
            return int(standalone.group(1)), standalone.group(1)
        return None, None

    @staticmethod
    def _normalize_series_label(text: str) -> str:
        """Remove volume markers so similar titles can be grouped."""
        normalized = Path(text).stem.lower()
        normalized = re.sub(r"[\[\(\{].*?[\]\)\}]", " ", normalized)
        normalized = re.sub(r"(?:^|[\s._\-])vol(?:ume)?[\s._\-]*\d+(?:$|[\s._\-])", " ", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"(?:^|[\s._\-])book[\s._\-]*\d+(?:$|[\s._\-])", " ", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"(?:^|[\s._\-])part[\s._\-]*\d+(?:$|[\s._\-])", " ", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"#\s*\d+", " ", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"[_\-.]+", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip(" -_:")
        return normalized

    def suggest_series_groups(self, library_id: int) -> dict[str, Any]:
        """Suggest series groupings and ordering from current book titles and filenames."""
        books = self.list_books(library_id)
        grouped: dict[str, list[dict[str, Any]]] = {}

        for book in books:
            title = str(book.get("title") or "")
            file_name = str(book.get("file_name") or "")
            source_text = title if title else file_name
            normalized = self._normalize_series_label(source_text or file_name)
            if not normalized:
                continue
            guessed_position, matched_from = self._extract_series_position(f"{title} {file_name}")
            grouped.setdefault(normalized, []).append(
                {
                    "book_id": int(book["id"]),
                    "title": title,
                    "file_name": file_name,
                    "ingest_status": book.get("ingest_status"),
                    "existing_series_name": book.get("series_name"),
                    "existing_series_order": book.get("series_order"),
                    "guessed_position": guessed_position,
                    "matched_from": matched_from,
                }
            )

        suggestions: list[dict[str, Any]] = []
        for normalized_name, items in grouped.items():
            if len(items) < 2:
                continue
            ordered = sorted(
                items,
                key=lambda item: (
                    item["guessed_position"] is None,
                    item["guessed_position"] if item["guessed_position"] is not None else 10**9,
                    self._series_sort_key(item["title"] or item["file_name"]),
                ),
            )
            positions = [item["guessed_position"] for item in ordered if item["guessed_position"] is not None]
            confidence = "high" if len(positions) == len(ordered) else "medium"
            suggestions.append(
                {
                    "series_name_guess": normalized_name.title(),
                    "normalized_key": normalized_name,
                    "confidence": confidence,
                    "books": ordered,
                    "reason": "Grouped by matching title/file stem with detected volume markers.",
                }
            )

        suggestions.sort(key=lambda item: (item["confidence"] != "high", item["series_name_guess"].lower()))
        return {"library_id": library_id, "suggestions": suggestions, "total_books": len(books)}

    def reorder_series_books(self, series_id: int, items: list[dict[str, int]]) -> dict[str, Any]:
        """Assign books to a series with an explicit order."""
        self.db.execute("DELETE FROM series_books WHERE series_id = ?", (series_id,))
        params = [(series_id, item["book_id"], item["sort_order"]) for item in items]
        self.db.execute_many(
            "INSERT INTO series_books(series_id, book_id, sort_order) VALUES (?, ?, ?)",
            params,
        )
        return self.get_series(series_id)

    def set_boundary(
        self,
        library_id: int,
        scope_type: str,
        scope_id: int,
        boundary_type: str,
        active_book_id: int | None = None,
        active_chapter_index: int | None = None,
    ) -> dict[str, Any]:
        """Store a reading boundary for a book or series."""
        self.db.execute(
            """
            INSERT INTO reading_boundaries(
                library_id, scope_type, scope_id, boundary_type, active_book_id, active_chapter_index, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(library_id, scope_type, scope_id)
            DO UPDATE SET
                boundary_type = excluded.boundary_type,
                active_book_id = excluded.active_book_id,
                active_chapter_index = excluded.active_chapter_index,
                updated_at = excluded.updated_at
            """,
            (library_id, scope_type, scope_id, boundary_type, active_book_id, active_chapter_index, utc_now()),
        )
        return self.db.fetch_one(
            "SELECT * FROM reading_boundaries WHERE library_id = ? AND scope_type = ? AND scope_id = ?",
            (library_id, scope_type, scope_id),
        ) or {}

    def get_boundary(self, library_id: int, scope_type: str, scope_id: int) -> dict[str, Any] | None:
        """Fetch a stored reading boundary."""
        return self.db.fetch_one(
            "SELECT * FROM reading_boundaries WHERE library_id = ? AND scope_type = ? AND scope_id = ?",
            (library_id, scope_type, scope_id),
        )

    def ingest_book(
        self,
        book_id: int,
        embedding_provider_id: int,
        embedding_model: str,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        ocr_provider_id: int | None = None,
        ocr_model: str | None = None,
        ocr_mode: str = "disabled",
        confirm_ocr_cost: bool = False,
        source_path: str | None = None,
    ) -> dict[str, Any]:
        """Ingest a book synchronously and store its vectors."""
        book = self.get_book(book_id)
        chunk_size = chunk_size or self.settings.default_chunk_size
        chunk_overlap = chunk_overlap or self.settings.default_chunk_overlap
        job_id = self.db.execute(
            """
            INSERT INTO ingest_jobs(
                library_id, book_id, status, mode, message, source_path, verification_status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                book["library_id"],
                book_id,
                "running",
                ocr_mode,
                "Ingest started",
                source_path,
                "pending",
                utc_now(),
                utc_now(),
            ),
        )
        self.db.execute(
            "UPDATE books SET ingest_status = ?, verification_status = ? WHERE id = ?",
            ("processing", "pending", book_id),
        )

        try:
            embed_config = self._provider_config(embedding_provider_id)
            embed_adapter = self.providers.get(embed_config.provider_type)
            ocr_adapter = None
            ocr_config = None
            if ocr_mode != "disabled":
                if not confirm_ocr_cost:
                    raise ValueError("OCR requires confirm_ocr_cost=true because it may consume vision model credits")
                if not ocr_provider_id or not ocr_model:
                    raise ValueError("OCR provider and OCR model are required when OCR is enabled")
                ocr_config = self._provider_config(ocr_provider_id)
                ocr_adapter = self.providers.get(ocr_config.provider_type)

            path = Path(book["source_path"])
            if book["source_type"] == "epub":
                document = self.ingestor.ingest_epub(path, chunk_size, chunk_overlap)
            elif book["source_type"] == "pdf":
                document = self.ingestor.ingest_pdf(
                    path,
                    chunk_size,
                    chunk_overlap,
                    ocr_provider=ocr_adapter,
                    ocr_config=ocr_config,
                    ocr_model=ocr_model,
                    force_ocr=ocr_mode == "force",
                )
            else:
                raise ValueError(f"Unsupported source type: {book['source_type']}")

            embeddings = embed_adapter.embed_texts(embed_config, embedding_model, document.chunks, purpose="document")
            enriched_metadata: list[dict[str, Any]] = []
            for index, metadata in enumerate(document.metadata):
                page_num = metadata.get("page_number")
                # Ensure page_number is int or None (ChromaDB requirement)
                if page_num is not None:
                    try:
                        page_num = int(page_num)
                    except (ValueError, TypeError):
                        page_num = None
                
                meta = {
                    "library_id": int(book["library_id"]),
                    "book_id": int(book_id),
                    "book_title": str(document.title),
                    "source_type": str(document.source_type),
                    "chapter_index": int(metadata.get("chapter_index", 0)),
                    "chapter_title": str(metadata.get("chapter", f"Section {index + 1}")),
                    "chunk_index": int(metadata.get("chunk_index", index)),
                }
                # Only include page_number if it's a valid int (ChromaDB doesn't accept None)
                if page_num is not None:
                    meta["page_number"] = page_num
                
                enriched_metadata.append(meta)
            self.vector_store.upsert_book_chunks(book["library_id"], book_id, embeddings, document.chunks, enriched_metadata)
            verification = self.verify_book_vectors(book["library_id"], book_id, len(document.chunks))
            self.db.execute(
                """
                UPDATE books
                SET title = ?, author = ?, ingest_status = ?, chapter_count = ?, chunk_count = ?, total_tokens = ?,
                    embedding_provider_id = ?, embedding_model = ?, ocr_provider_id = ?, ocr_model = ?,
                    metadata_json = ?, verification_status = ?, last_verified_at = ?
                WHERE id = ?
                """,
                (
                    document.title,
                    document.author,
                    "ready",
                    document.stats.get("chapter_count", 0),
                    document.stats.get("chunk_count", 0),
                    document.stats.get("total_tokens", 0),
                    embedding_provider_id,
                    embedding_model,
                    ocr_provider_id,
                    ocr_model,
                    self.db.json_dumps(
                        {
                            "ocr_mode": ocr_mode,
                            "stats": document.stats,
                            "chunk_size": chunk_size,
                            "chunk_overlap": chunk_overlap,
                            "verification": verification,
                        }
                    ),
                    "verified",
                    utc_now(),
                    book_id,
                ),
            )
            self.db.execute(
                """
                UPDATE ingest_jobs
                SET status = ?, message = ?, verification_status = ?, verification_message = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    "completed",
                    f"Indexed {document.stats.get('chunk_count', 0)} chunks",
                    "verified",
                    f"Verified {verification['chunk_count']} chunks",
                    utc_now(),
                    job_id,
                ),
            )
            return {"job_id": job_id, "book": self.get_book(book_id)}
        except Exception as exc:
            self.db.execute(
                "UPDATE books SET ingest_status = ?, verification_status = ? WHERE id = ?",
                ("failed", "failed", book_id),
            )
            self.db.execute(
                """
                UPDATE ingest_jobs
                SET status = ?, message = ?, verification_status = ?, verification_message = ?, updated_at = ?
                WHERE id = ?
                """,
                ("failed", str(exc), "failed", str(exc), utc_now(), job_id),
            )
            raise

    def list_jobs(self) -> list[dict[str, Any]]:
        """List ingest jobs."""
        return self.db.fetch_all("SELECT * FROM ingest_jobs ORDER BY id DESC")

    def get_job(self, job_id: int) -> dict[str, Any]:
        """Fetch one ingest job."""
        job = self.db.fetch_one("SELECT * FROM ingest_jobs WHERE id = ?", (job_id,))
        if not job:
            raise ValueError("Job not found")
        return job

    def _series_position(self, book_id: int) -> tuple[int, int] | None:
        """Return series_id and sort_order if the book belongs to a series."""
        row = self.db.fetch_one("SELECT series_id, sort_order FROM series_books WHERE book_id = ?", (book_id,))
        if not row:
            return None
        return int(row["series_id"]), int(row["sort_order"])

    def _result_allowed(
        self,
        result: dict[str, Any],
        spoiler_mode: str,
        active_book_id: int | None,
        active_chapter_index: int | None,
    ) -> bool:
        """Evaluate whether a retrieval hit is allowed under the spoiler mode."""
        meta = result["metadata"]
        result_book_id = int(meta["book_id"])
        result_chapter = int(meta.get("chapter_index", 0))

        if spoiler_mode == "full_context":
            return True
        if not active_book_id:
            return False
        if spoiler_mode == "book_only":
            return result_book_id == active_book_id
        if spoiler_mode in {"through_chapter", "through_series_boundary"}:
            active_series = self._series_position(active_book_id)
            result_series = self._series_position(result_book_id)
            if active_series and result_series and active_series[0] == result_series[0]:
                if result_series[1] < active_series[1]:
                    return True
                if result_book_id == active_book_id:
                    return active_chapter_index is None or result_chapter <= active_chapter_index
                return False
            if result_book_id != active_book_id:
                return False
            return active_chapter_index is None or result_chapter <= active_chapter_index
        return True

    def query_context(
        self,
        library_id: int,
        question: str,
        top_k: int | None = None,
        spoiler_mode: str = "full_context",
        context_mode: str | None = None,
        active_book_id: int | None = None,
        active_chapter_index: int | None = None,
    ) -> dict[str, Any]:
        """Retrieve context passages for a question."""
        spoiler_mode, active_book_id, active_chapter_index = self._normalize_spoiler_inputs(
            spoiler_mode=spoiler_mode,
            context_mode=context_mode,
            active_book_id=active_book_id,
            active_chapter_index=active_chapter_index,
        )
        library = self.get_library(library_id)
        books = [book for book in self.list_books(library_id) if book["ingest_status"] == "ready"]
        if not books:
            raise ValueError("No indexed books are available in this library")

        grouped_books: dict[tuple[int, str], list[dict[str, Any]]] = {}
        for book in books:
            if not book["embedding_provider_id"] or not book["embedding_model"]:
                continue
            grouped_books.setdefault((book["embedding_provider_id"], book["embedding_model"]), []).append(book)

        top_k = top_k or self.settings.default_top_k
        merged_results: list[dict[str, Any]] = []
        for (provider_id, embedding_model), group_books in grouped_books.items():
            provider_config = self._provider_config(int(provider_id))
            provider = self.providers.get(provider_config.provider_type)
            query_embedding = provider.embed_texts(provider_config, embedding_model, [question], purpose="query")[0]
            for book in group_books:
                merged_results.extend(
                    self.vector_store.query_book(library_id, book["id"], query_embedding, max(top_k * 3, 10))
                )

        filtered = [
            item
            for item in sorted(merged_results, key=lambda value: value["similarity_score"], reverse=True)
            if self._result_allowed(item, spoiler_mode, active_book_id, active_chapter_index)
        ][:top_k]
        citations = [
            {
                "book_title": item["metadata"]["book_title"],
                "chapter_title": item["metadata"].get("chapter_title"),
                "chapter_index": item["metadata"].get("chapter_index"),
                "page_number": item["metadata"].get("page_number"),
                "similarity_score": round(item["similarity_score"], 3),
            }
            for item in filtered
        ]
        return {
            "library": library,
            "question": question,
            "spoiler_mode": spoiler_mode,
            "context_mode": context_mode,
            "active_book_id": active_book_id,
            "active_chapter_index": active_chapter_index,
            "results": filtered,
            "citations": citations,
        }

    def answer_question(
        self,
        library_id: int,
        question: str,
        chat_provider_id: int,
        chat_model: str,
        top_k: int | None = None,
        spoiler_mode: str = "full_context",
        context_mode: str | None = None,
        active_book_id: int | None = None,
        active_chapter_index: int | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> dict[str, Any]:
        """Answer a question using retrieved context and a selected chat provider."""
        context = self.query_context(
            library_id=library_id,
            question=question,
            top_k=top_k,
            spoiler_mode=spoiler_mode,
            context_mode=context_mode,
            active_book_id=active_book_id,
            active_chapter_index=active_chapter_index,
        )
        prompt_blocks = []
        for index, item in enumerate(context["results"], start=1):
            meta = item["metadata"]
            prompt_blocks.append(
                f"[Passage {index}] {meta['book_title']} / {meta.get('chapter_title', 'Unknown')} "
                f"(chapter_index={meta.get('chapter_index')}, page={meta.get('page_number')})\n"
                f"{item['content']}"
            )
        provider_config = self._provider_config(chat_provider_id)
        provider = self.providers.get(provider_config.provider_type)
        system_prompt = (
            "You answer questions using only the supplied passages from the user's indexed books. "
            "Cite book title and chapter or page. If the passages are insufficient, say so. "
            f"Spoiler mode is {spoiler_mode}; do not infer content beyond the available context."
        )
        user_prompt = (
            f"Question: {question}\n\n"
            f"Context passages:\n\n{chr(10).join(prompt_blocks)}\n\n"
            "Answer with short citations."
        )
        answer = provider.chat(
            provider_config,
            chat_model,
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return {"answer": answer, "context": context}
