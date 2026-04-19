"""Application settings and filesystem paths."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AppSettings:
    """Settings for the ChapterKey application."""

    app_name: str
    app_secret: str
    data_dir: Path
    input_dir: Path
    output_dir: Path
    uploads_dir: Path
    managed_books_dir: Path
    vector_db_dir: Path
    sqlite_path: Path
    api_host: str
    api_port: int
    default_top_k: int
    default_chunk_size: int
    default_chunk_overlap: int
    admin_username: str
    watch_interval_sec: int
    min_file_age_sec: int
    auto_delete_source: bool
    default_library_name: str

    @classmethod
    def load(cls) -> "AppSettings":
        """Load settings from environment variables."""
        base_dir = Path(__file__).resolve().parent.parent
        output_dir_raw = os.getenv("BOOKRAG_OUTPUT_DIR", str(base_dir / "data" / "bookrag_output"))
        input_dir_raw = os.getenv("BOOKRAG_INPUT_DIR", str(base_dir / "data" / "input_books"))
        data_dir_default = Path(output_dir_raw).expanduser()
        data_dir = Path(os.getenv("BOOKRAG_DATA_DIR", str(data_dir_default)))
        output_dir = Path(output_dir_raw).expanduser().resolve()
        data_dir = output_dir
        uploads_dir = Path(
            os.getenv(
                "BOOKRAG_UPLOADS_DIR",
                str((output_dir or data_dir) / "uploads"),
            )
        ).expanduser()
        managed_books_dir = Path(
            os.getenv(
                "BOOKRAG_MANAGED_BOOKS_DIR",
                str((output_dir or data_dir) / "managed_books"),
            )
        ).expanduser()
        vector_db_dir = Path(
            os.getenv(
                "BOOKRAG_VECTOR_DB_DIR",
                str((output_dir or data_dir) / "chroma_db"),
            )
        ).expanduser()
        sqlite_path = Path(
            os.getenv(
                "BOOKRAG_SQLITE_PATH",
                str((output_dir or data_dir) / "bookrag.sqlite3"),
            )
        ).expanduser()
        input_dir = Path(input_dir_raw).expanduser().resolve()

        settings = cls(
            app_name=os.getenv("BOOKRAG_APP_NAME", "ChapterKey"),
            app_secret=os.getenv("BOOKRAG_APP_SECRET", "change-me-bookrag-secret"),
            data_dir=data_dir,
            input_dir=input_dir,
            output_dir=output_dir,
            uploads_dir=uploads_dir,
            managed_books_dir=managed_books_dir,
            vector_db_dir=vector_db_dir,
            sqlite_path=sqlite_path,
            api_host=os.getenv("BOOKRAG_API_HOST", "0.0.0.0"),
            api_port=int(os.getenv("BOOKRAG_API_PORT", "8000")),
            default_top_k=int(os.getenv("BOOKRAG_TOP_K", "5")),
            default_chunk_size=int(os.getenv("BOOKRAG_CHUNK_SIZE", "750")),
            default_chunk_overlap=int(os.getenv("BOOKRAG_CHUNK_OVERLAP", "100")),
            admin_username=os.getenv("BOOKRAG_ADMIN_USERNAME", "admin"),
            watch_interval_sec=int(os.getenv("BOOKRAG_WATCH_INTERVAL_SEC", "10")),
            min_file_age_sec=int(os.getenv("BOOKRAG_MIN_FILE_AGE_SEC", "30")),
            auto_delete_source=_env_bool("BOOKRAG_AUTO_DELETE_SOURCE", True),
            default_library_name=os.getenv("BOOKRAG_DEFAULT_LIBRARY_NAME", "Default Library"),
        )
        settings.ensure_directories()
        return settings

    def ensure_directories(self) -> None:
        """Create required directories."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.managed_books_dir.mkdir(parents=True, exist_ok=True)
        self.vector_db_dir.mkdir(parents=True, exist_ok=True)
