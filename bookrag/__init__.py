"""BookRAG application package."""

__version__ = "2.0.0"


def create_app():
    """Lazy import FastAPI app factory for CLI-friendly package import."""
    from bookrag.api import create_app as factory

    return factory()


__all__ = ["create_app", "__version__"]
