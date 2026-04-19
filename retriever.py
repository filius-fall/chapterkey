"""
Retriever for querying EPUB content using vector similarity search.
Handles question processing and result formatting.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple

from config import Config
from embedder import Embedder
from chroma_manager import ChromaManager

logger = logging.getLogger(__name__)

class Retriever:
    """Retriever for EPUB content queries."""

    def __init__(self):
        """Initialize retriever."""
        self.embedder = Embedder()
        self.chroma_manager = ChromaManager()

    def query(
        self,
        question: str,
        epub_name: str,
        n_results: Optional[int] = None,
        progress_percent: Optional[int] = None,
        chapter_limit: Optional[str] = None,
        chunk_count: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Query EPUB content with a question.

        Args:
            question: User's question
            epub_name: Name of the EPUB to query
            n_results: Number of results to return (defaults to config TOP_K)
            progress_percent: Limit search to first X% of book (0-100)
            chapter_limit: Limit search to chapters before specified chapter name
            chunk_count: Limit search to first N chunks from start of book

        Returns:
            Dictionary with relevant chunks and metadata
        """
        logger.info(f"Querying EPUB '{epub_name}' with: {question}")

        # Determine search limit
        search_limit = self._determine_search_limit(
            epub_name, progress_percent, chapter_limit, chunk_count
        )

        # Generate query embedding
        query_embedding = self.embedder.generate_query_embedding(question)

        # Query ChromaDB - get more results to account for filtering
        try:
            # Use config TOP_K as default if n_results not specified
            effective_n = n_results or Config.TOP_K
            # Query with more results if we're limiting
            query_n = effective_n * 3 if search_limit else effective_n
            results = self.chroma_manager.query(
                epub_name=epub_name,
                query_embedding=query_embedding,
                n_results=query_n
            )

            # Format results
            formatted_results = self._format_results(results)

            # Apply search limit if specified
            if search_limit:
                formatted_results = self._apply_search_limit(formatted_results, search_limit)
                logger.info(f"Applied search limit: {search_limit}")

            # Limit to requested n_results after filtering
            if n_results:
                formatted_results = formatted_results[:n_results]

            return {
                "question": question,
                "epub": epub_name,
                "results": formatted_results,
                "total_results": len(formatted_results),
                "search_limit": search_limit
            }

        except Exception as e:
            logger.error(f"Error querying EPUB: {e}")
            raise

    def _determine_search_limit(
        self,
        epub_name: str,
        progress_percent: Optional[int],
        chapter_limit: Optional[str],
        chunk_count: Optional[int]
    ) -> Optional[Dict[str, Any]]:
        """
        Determine the search limit based on provided parameters.

        Args:
            epub_name: Name of the EPUB
            progress_percent: Percentage of book to search (0-100)
            chapter_limit: Chapter name to limit before
            chunk_count: Number of chunks to include

        Returns:
            Dictionary with limit info or None
        """
        if progress_percent is not None:
            if not (0 <= progress_percent <= 100):
                logger.warning(f"Invalid progress_percent: {progress_percent}, must be 0-100")
                return None

            # Get total chapter count
            info = self.chroma_manager.get_collection_info(epub_name)
            if not info:
                return None

            total_chapters = info.get('unique_chapters', 0)
            if total_chapters == 0:
                return None

            # Calculate chapter limit based on percentage
            max_chapter_index = int((progress_percent / 100) * total_chapters)
            return {
                "type": "progress_percent",
                "value": progress_percent,
                "max_chapter_index": max_chapter_index,
                "max_chapters": total_chapters
            }

        if chapter_limit is not None:
            return {
                "type": "chapter_limit",
                "value": chapter_limit
            }

        if chunk_count is not None:
            if chunk_count <= 0:
                logger.warning(f"Invalid chunk_count: {chunk_count}, must be > 0")
                return None

            return {
                "type": "chunk_count",
                "value": chunk_count
            }

        return None

    def _apply_search_limit(
        self,
        results: List[Dict[str, Any]],
        limit: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Filter results based on search limit.

        Args:
            results: List of formatted results
            limit: Search limit dictionary

        Returns:
            Filtered results
        """
        limit_type = limit.get("type")

        if limit_type == "progress_percent":
            max_chapter_index = limit.get("max_chapter_index")
            # Filter results by chapter index
            filtered = [
                r for r in results
                if r.get("metadata", {}).get("chapter_index", 999) < max_chapter_index
            ]
            return filtered

        elif limit_type == "chapter_limit":
            chapter_name = limit.get("value")
            # Filter results by chapter name (exclude the specified chapter and after)
            # This is tricky because chapter names are strings, so we need to get chapter indices first
            chapter_indices = set(
                r.get("metadata", {}).get("chapter_index", -1)
                for r in results
            )
            max_index = max(chapter_indices) if chapter_indices else -1

            # Filter results that come before chapters with the limit name
            filtered = []
            for r in results:
                meta = r.get("metadata", {})
                chapter = meta.get("chapter", "")
                if chapter == chapter_name:
                    # Stop at this chapter, don't include it
                    break
                filtered.append(r)
            return filtered

        elif limit_type == "chunk_count":
            max_chunk = limit.get("value")
            # Simply return first N chunks
            return results[:max_chunk]

        return results

    def _format_results(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Format ChromaDB query results.

        Args:
            results: Raw ChromaDB results

        Returns:
            List of formatted result dictionaries
        """
        formatted = []

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
            formatted.append({
                "index": i,
                "content": doc,
                "metadata": meta,
                "similarity_score": 1 - dist,  # Convert distance to similarity
                "distance": dist
            })

        # Sort by similarity (highest first)
        formatted.sort(key=lambda x: x["similarity_score"], reverse=True)

        return formatted

    def format_for_claude(self, query_results: Dict[str, Any]) -> str:
        """
        Format query results for Claude Code consumption.

        Args:
            query_results: Results from query method

        Returns:
            Formatted string with context for Claude
        """
        output = [f"## Relevant Content from '{query_results['epub']}'"]
        output.append(f"**Question:** {query_results['question']}")

        # Add search limit info if present
        if query_results.get('search_limit'):
            limit = query_results['search_limit']
            limit_type = limit.get('type')

            if limit_type == 'progress_percent':
                output.append(f"**Search Limit:** First {limit['value']}% of book (up to chapter {limit['max_chapter_index']} of {limit['max_chapters']})")
            elif limit_type == 'chapter_limit':
                output.append(f"**Search Limit:** Before chapter '{limit['value']}'")
            elif limit_type == 'chunk_count':
                output.append(f"**Search Limit:** First {limit['value']} chunks from start")

            output.append("**Note:** Answers are based ONLY on content within this limit (no spoilers!)\n")

        output.append(f"**Found {query_results['total_results']} relevant passages**\n")
        """
        Format query results for Claude Code consumption.

        Args:
            query_results: Results from query method

        Returns:
            Formatted string with context for Claude
        """
        output = [f"## Relevant Content from '{query_results['epub']}'"]
        output.append(f"**Question:** {query_results['question']}")
        output.append(f"**Found {query_results['total_results']} relevant passages**\n")

        for i, result in enumerate(query_results['results'], 1):
            meta = result['metadata']
            output.append(f"### Passage {i}")
            output.append(f"**Source:** {meta.get('chapter', 'Unknown')}")
            output.append(f"**Similarity:** {result['similarity_score']:.3f}")
            output.append(f"**Content:**")
            output.append(f"{result['content']}\n")

        return "\n".join(output)

    def summarize_results(self, query_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a summary of query results.

        Args:
            query_results: Results from query method

        Returns:
            Summary dictionary
        """
        results = query_results['results']

        if not results:
            return {
                "found": False,
                "message": "No relevant content found"
            }

        # Get unique chapters
        chapters = set(r['metadata'].get('chapter', 'Unknown') for r in results)

        # Get average similarity
        avg_similarity = sum(r['similarity_score'] for r in results) / len(results)

        return {
            "found": True,
            "total_passages": len(results),
            "unique_chapters": len(chapters),
            "chapters": sorted(chapters),
            "average_similarity": round(avg_similarity, 3),
            "best_match": results[0]['similarity_score'] if results else 0
        }
