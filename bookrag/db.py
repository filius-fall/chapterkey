"""SQLite persistence layer for the BookRAG app."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def utc_now() -> str:
    """Return an ISO timestamp in UTC."""
    return datetime.now(timezone.utc).isoformat()


class Database:
    """Small SQLite wrapper with row dict support."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connect(self) -> Iterable[sqlite3.Connection]:
        """Yield a configured SQLite connection."""
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS admin_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS session_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token_name TEXT NOT NULL,
                    token_hash TEXT UNIQUE NOT NULL,
                    created_at TEXT NOT NULL,
                    last_used_at TEXT,
                    FOREIGN KEY(user_id) REFERENCES admin_users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS provider_credentials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    provider_type TEXT NOT NULL,
                    api_key_encrypted TEXT NOT NULL,
                    base_url TEXT,
                    default_embedding_model TEXT,
                    default_chat_model TEXT,
                    default_ocr_model TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS libraries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    library_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    author TEXT,
                    file_name TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    ingest_status TEXT NOT NULL,
                    chapter_count INTEGER DEFAULT 0,
                    chunk_count INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    embedding_provider_id INTEGER,
                    embedding_model TEXT,
                    ocr_provider_id INTEGER,
                    ocr_model TEXT,
                    metadata_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE CASCADE,
                    FOREIGN KEY(embedding_provider_id) REFERENCES provider_credentials(id),
                    FOREIGN KEY(ocr_provider_id) REFERENCES provider_credentials(id)
                );

                CREATE TABLE IF NOT EXISTS ingest_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    library_id INTEGER NOT NULL,
                    book_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE CASCADE,
                    FOREIGN KEY(book_id) REFERENCES books(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS series (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    library_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(library_id, name),
                    FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS series_books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    series_id INTEGER NOT NULL,
                    book_id INTEGER NOT NULL,
                    sort_order INTEGER NOT NULL,
                    UNIQUE(series_id, book_id),
                    UNIQUE(series_id, sort_order),
                    FOREIGN KEY(series_id) REFERENCES series(id) ON DELETE CASCADE,
                    FOREIGN KEY(book_id) REFERENCES books(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS reading_boundaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    library_id INTEGER NOT NULL,
                    scope_type TEXT NOT NULL,
                    scope_id INTEGER NOT NULL,
                    boundary_type TEXT NOT NULL,
                    chapter_index INTEGER,
                    series_order INTEGER,
                    active_book_id INTEGER,
                    active_chapter_index INTEGER,
                    updated_at TEXT NOT NULL,
                    UNIQUE(library_id, scope_type, scope_id),
                    FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE CASCADE,
                    FOREIGN KEY(active_book_id) REFERENCES books(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    library_id INTEGER NOT NULL,
                    title TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE CASCADE
                );
                """
            )

    def fetch_one(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        """Fetch one row and return a dict."""
        with self.connect() as conn:
            row = conn.execute(query, params).fetchone()
            return dict(row) if row else None

    def fetch_all(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        """Fetch all rows and return dicts."""
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> int:
        """Execute a statement and return the last inserted row id."""
        with self.connect() as conn:
            cursor = conn.execute(query, params)
            return int(cursor.lastrowid)

    def execute_many(self, query: str, params: list[tuple[Any, ...]]) -> None:
        """Execute many statements."""
        with self.connect() as conn:
            conn.executemany(query, params)

    @staticmethod
    def json_loads(raw: str | None) -> dict[str, Any]:
        """Decode JSON metadata."""
        return json.loads(raw or "{}")

    @staticmethod
    def json_dumps(value: dict[str, Any]) -> str:
        """Encode JSON metadata."""
        return json.dumps(value, sort_keys=True)
