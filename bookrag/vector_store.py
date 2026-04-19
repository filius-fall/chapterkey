"""Chroma-backed vector storage for BookRAG books."""

from __future__ import annotations

import logging
from typing import Any

import chromadb
from chromadb.config import Settings

from bookrag.settings import AppSettings


logger = logging.getLogger(__name__)


class VectorStore:
    """Manage one Chroma collection per book."""

    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.client = chromadb.PersistentClient(
            path=str(settings.vector_db_dir),
            settings=Settings(anonymized_telemetry=False, allow_reset=True),
        )

    @staticmethod
    def collection_name(library_id: int, book_id: int) -> str:
        """Build a stable collection name."""
        return f"library_{library_id}_book_{book_id}"

    def _collection(self, library_id: int, book_id: int):
        return self.client.get_or_create_collection(name=self.collection_name(library_id, book_id))

    def collection_exists(self, library_id: int, book_id: int) -> bool:
        """Return whether a collection already exists for the book."""
        target = self.collection_name(library_id, book_id)
        return any(collection.name == target for collection in self.client.list_collections())

    def upsert_book_chunks(
        self,
        library_id: int,
        book_id: int,
        embeddings: list[list[float]],
        chunks: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """Replace all chunks for a book."""
        collection = self._collection(library_id, book_id)
        existing = collection.get()
        existing_ids = existing.get("ids", [])
        if existing_ids:
            collection.delete(ids=existing_ids)

        ids = [f"{library_id}_{book_id}_{index}" for index in range(len(chunks))]
        collection.add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
        logger.info("Indexed %s chunks for library=%s book=%s", len(chunks), library_id, book_id)

    def count_book_chunks(self, library_id: int, book_id: int) -> int:
        """Count the stored chunks for a book."""
        collection = self._collection(library_id, book_id)
        return len(collection.get().get("ids", []))

    def sample_book_chunk(self, library_id: int, book_id: int) -> dict[str, Any] | None:
        """Fetch one stored chunk for verification."""
        collection = self._collection(library_id, book_id)
        sample = collection.get(limit=1)
        ids = sample.get("ids", [])
        if not ids:
            return None
        documents = sample.get("documents", [])
        metadatas = sample.get("metadatas", [])
        return {
            "id": ids[0],
            "document": documents[0] if documents else None,
            "metadata": metadatas[0] if metadatas else None,
        }

    def query_book(
        self,
        library_id: int,
        book_id: int,
        query_embedding: list[float],
        n_results: int,
    ) -> list[dict[str, Any]]:
        """Query a book collection and return formatted rows."""
        collection = self._collection(library_id, book_id)
        results = collection.query(query_embeddings=[query_embedding], n_results=n_results)
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        formatted: list[dict[str, Any]] = []
        for index, (document, metadata, distance) in enumerate(zip(documents, metadatas, distances)):
            formatted.append(
                {
                    "index": index,
                    "content": document,
                    "metadata": metadata,
                    "distance": distance,
                    "similarity_score": 1 - distance,
                }
            )
        return sorted(formatted, key=lambda item: item["similarity_score"], reverse=True)
