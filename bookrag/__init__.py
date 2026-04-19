"""ChapterKey application package."""

__version__ = "2.0.0"
__update_repo__ = "filius-fall/chapterkey"
__default_branch__ = "master"


def create_app():
    """Lazy import FastAPI app factory for CLI-friendly package import."""
    from bookrag.api import create_app as factory

    return factory()


__all__ = ["create_app", "__version__", "__update_repo__", "__default_branch__"]
