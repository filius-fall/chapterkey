"""Application settings and filesystem paths."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class AppSettings:
    """Settings for the BookRAG application."""

    app_name: str
    app_secret: str
    data_dir: Path
    uploads_dir: Path
    vector_db_dir: Path
    sqlite_path: Path
    api_host: str
    api_port: int
    default_top_k: int
    default_chunk_size: int
    default_chunk_overlap: int
    admin_username: str

    @classmethod
    def load(cls) -> "AppSettings":
        """Load settings from environment variables."""
        base_dir = Path(__file__).resolve().parent.parent
        data_dir = Path(os.getenv("BOOKRAG_DATA_DIR", str(base_dir / "data" / "app_data")))
        uploads_dir = Path(os.getenv("BOOKRAG_UPLOADS_DIR", str(data_dir / "uploads")))
        vector_db_dir = Path(os.getenv("BOOKRAG_VECTOR_DB_DIR", str(data_dir / "chroma_db")))
        sqlite_path = Path(os.getenv("BOOKRAG_SQLITE_PATH", str(data_dir / "bookrag.sqlite3")))

        settings = cls(
            app_name=os.getenv("BOOKRAG_APP_NAME", "BookRAG"),
            app_secret=os.getenv("BOOKRAG_APP_SECRET", "change-me-bookrag-secret"),
            data_dir=data_dir,
            uploads_dir=uploads_dir,
            vector_db_dir=vector_db_dir,
            sqlite_path=sqlite_path,
            api_host=os.getenv("BOOKRAG_API_HOST", "0.0.0.0"),
            api_port=int(os.getenv("BOOKRAG_API_PORT", "8000")),
            default_top_k=int(os.getenv("BOOKRAG_TOP_K", "5")),
            default_chunk_size=int(os.getenv("BOOKRAG_CHUNK_SIZE", "750")),
            default_chunk_overlap=int(os.getenv("BOOKRAG_CHUNK_OVERLAP", "100")),
            admin_username=os.getenv("BOOKRAG_ADMIN_USERNAME", "admin"),
        )
        settings.ensure_directories()
        return settings

    def ensure_directories(self) -> None:
        """Create required directories."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.vector_db_dir.mkdir(parents=True, exist_ok=True)
