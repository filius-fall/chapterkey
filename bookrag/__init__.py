"""BookRAG application package."""

from bookrag.services import BookRAGService


def create_app():
    """Lazy import FastAPI app factory for CLI-friendly package import."""
    from bookrag.api import create_app as factory

    return factory()


__all__ = ["BookRAGService", "create_app"]
