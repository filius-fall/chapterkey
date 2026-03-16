"""
ChromaDB manager for vector storage and retrieval.
Handles persistent storage of EPUB embeddings.
"""
import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from config import Config

logger = logging.getLogger(__name__)

class ChromaManager:
    """Manager for ChromaDB vector storage."""

    def __init__(self):
        """Initialize ChromaDB client with persistent storage."""
        self.vector_db_path = Config.VECTOR_DB_PATH
        self.vector_db_path.mkdir(parents=True, exist_ok=True)

        # Initialize persistent client
        self.client = chromadb.PersistentClient(
            path=str(self.vector_db_path),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        self._load_existing_collections()

    def _load_existing_collections(self):
        """Load all existing collections from the database."""
        self.collections = {}
        for collection in self.client.list_collections():
            self.collections[collection.name] = collection
            logger.info(f"Loaded collection: {collection.name}")

    def get_or_create_collection(self, epub_name: str):
        """
        Get or create a collection for an EPUB.

        Args:
            epub_name: Name of the EPUB (used as collection name)

        Returns:
            ChromaDB collection object
        """
        # Sanitize collection name (ChromaDB has restrictions)
        collection_name = self._sanitize_collection_name(epub_name)

        if collection_name in self.collections:
            return self.collections[collection_name]

        # Create new collection
        collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"epub_name": epub_name}
        )
        self.collections[collection_name] = collection
        logger.info(f"Created collection: {collection_name}")
        return collection

    def _sanitize_collection_name(self, name: str) -> str:
        """
        Sanitize collection name for ChromaDB.

        Args:
            name: Original name

        Returns:
            Sanitized name (3-63 chars, alphanumeric + - and _)
        """
        # Replace invalid characters
        sanitized = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)

        # Ensure length constraints
        if len(sanitized) > 63:
            sanitized = sanitized[:60] + "_truncated"
        if len(sanitized) < 3:
            sanitized = "col_" + sanitized

        return sanitized

    def add_documents(
        self,
        epub_name: str,
        embeddings: List[List[float]],
        texts: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str]
    ) -> None:
        """
        Add documents to a collection.

        Args:
            epub_name: Name of the EPUB
            embeddings: List of embedding vectors
            texts: List of text chunks
            metadatas: List of metadata dictionaries
            ids: List of unique IDs

        Raises:
            Exception: If add operation fails
        """
        collection = self.get_or_create_collection(epub_name)

        try:
            collection.add(
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
                ids=ids
            )
            logger.info(f"Added {len(texts)} documents to collection: {epub_name}")
        except Exception as e:
            logger.error(f"Error adding documents to collection {epub_name}: {e}")
            raise

    def query(
        self,
        epub_name: str,
        query_embedding: List[float],
        n_results: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Query a collection for similar documents.

        Args:
            epub_name: Name of the EPUB
            query_embedding: Query embedding vector
            n_results: Number of results to return (defaults to config TOP_K)

        Returns:
            Dictionary with results (documents, metadatas, distances)
        """
        collection = self.get_or_create_collection(epub_name)
        n_results = n_results or Config.TOP_K

        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            return results
        except Exception as e:
            logger.error(f"Error querying collection {epub_name}: {e}")
            raise

    def delete_collection(self, epub_name: str) -> None:
        """
        Delete a collection.

        Args:
            epub_name: Name of the EPUB
        """
        collection_name = self._sanitize_collection_name(epub_name)

        if collection_name in self.collections:
            self.client.delete_collection(name=collection_name)
            del self.collections[collection_name]
            logger.info(f"Deleted collection: {collection_name}")

    def list_collections(self) -> List[Dict[str, Any]]:
        """
        List all collections with metadata.

        Returns:
            List of collection info dictionaries
        """
        collections_info = []

        for name, collection in self.collections.items():
            try:
                count = collection.count()
                metadata = collection.metadata or {}
                collections_info.append({
                    "name": metadata.get("epub_name", name),
                    "sanitized_name": name,
                    "document_count": count
                })
            except Exception as e:
                logger.warning(f"Error getting info for collection {name}: {e}")
                collections_info.append({
                    "name": metadata.get("epub_name", name),
                    "sanitized_name": name,
                    "document_count": 0,
                    "error": str(e)
                })

        return collections_info

    def get_collection_info(self, epub_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a collection.

        Args:
            epub_name: Name of the EPUB

        Returns:
            Collection info dictionary or None if not found
        """
        collection_name = self._sanitize_collection_name(epub_name)

        if collection_name not in self.collections:
            return None

        collection = self.collections[collection_name]
        metadata = collection.metadata or {}

        try:
            count = collection.count()

            # Get a sample to estimate unique chapters
            sample = collection.get(limit=100, include=["metadatas"])
            chapters = set()
            for m in sample.get("metadatas", []):
                if "chapter" in m:
                    chapters.add(m["chapter"])

            return {
                "name": metadata.get("epub_name", epub_name),
                "document_count": count,
                "unique_chapters": len(chapters),
                "sanitized_name": collection_name
            }
        except Exception as e:
            logger.error(f"Error getting collection info for {epub_name}: {e}")
            return None

    def reset_database(self) -> None:
        """Reset the entire database (use with caution)."""
        self.client.reset()
        self.collections.clear()
        logger.warning("Database reset")
