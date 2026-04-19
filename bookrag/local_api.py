"""Direct local query helpers for scripts."""

from __future__ import annotations

from typing import Any

from bookrag.services import BookRAGService
from bookrag.settings import AppSettings


def _service(settings: AppSettings | None = None) -> BookRAGService:
    return BookRAGService(settings=settings)


def query_context(settings: AppSettings | None = None, **kwargs: Any) -> dict[str, Any]:
    """Query indexed books directly from the local output store."""
    return _service(settings).query_context(**kwargs)


def answer_question(settings: AppSettings | None = None, **kwargs: Any) -> dict[str, Any]:
    """Answer a question directly from the local output store."""
    return _service(settings).answer_question(**kwargs)
