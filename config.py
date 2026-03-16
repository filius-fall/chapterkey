"""
Configuration management for EPUB RAG MCP Server.
Handles environment variables and application settings.
"""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Application configuration."""

    # OpenRouter API
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Model settings
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-small")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "google/gemini-2.5-flash-preview")

    # Chunking settings
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "750"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "100"))

    # Retrieval settings
    TOP_K: int = int(os.getenv("TOP_K", "5"))

    # Storage paths
    BASE_DIR: Path = Path(__file__).parent
    DATA_DIR: Path = BASE_DIR / "data"
    VECTOR_DB_PATH: Path = DATA_DIR / "chroma_db"

    # API settings
    EMBEDDING_BATCH_SIZE: int = 100
    API_TIMEOUT: int = 60
    MAX_RETRIES: int = 3

    @classmethod
    def validate(cls) -> tuple[bool, Optional[str]]:
        """
        Validate configuration.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not cls.OPENROUTER_API_KEY:
            return False, "OPENROUTER_API_KEY is required. Please set it in .env file"

        if cls.CHUNK_SIZE <= 0:
            return False, "CHUNK_SIZE must be greater than 0"

        if cls.CHUNK_OVERLAP < 0:
            return False, "CHUNK_OVERLAP must be >= 0"

        if cls.CHUNK_OVERLAP >= cls.CHUNK_SIZE:
            return False, "CHUNK_OVERLAP must be less than CHUNK_SIZE"

        if cls.TOP_K <= 0:
            return False, "TOP_K must be greater than 0"

        # Ensure data directory exists
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)

        return True, None

    @classmethod
    def get_openai_client_kwargs(cls) -> dict:
        """Get kwargs for OpenAI client configured for OpenRouter."""
        return {
            "api_key": cls.OPENROUTER_API_KEY,
            "base_url": cls.OPENROUTER_BASE_URL,
            "timeout": cls.API_TIMEOUT,
            "max_retries": cls.MAX_RETRIES,
        }
