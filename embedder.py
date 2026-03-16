"""
Embedder for generating text embeddings using OpenRouter API.
Handles batch processing and caching for efficiency.
"""
import logging
from typing import List, Dict, Any
from tqdm import tqdm

from openrouter_client import OpenRouterClient
from config import Config

logger = logging.getLogger(__name__)

class Embedder:
    """Generator for text embeddings."""

    def __init__(self):
        """Initialize embedder with OpenRouter client."""
        self.client = OpenRouterClient()

    def generate_embeddings(
        self,
        texts: List[str],
        show_progress: bool = True
    ) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings
            show_progress: Whether to show progress bar

        Returns:
            List of embedding vectors

        Raises:
            Exception: If embedding generation fails
        """
        if not texts:
            return []

        logger.info(f"Generating embeddings for {len(texts)} texts")

        try:
            if show_progress:
                # Process in batches with progress bar
                batch_size = Config.EMBEDDING_BATCH_SIZE
                all_embeddings = []

                for i in tqdm(range(0, len(texts), batch_size), desc="Generating embeddings"):
                    batch = texts[i:i + batch_size]
                    batch_embeddings = self.client.generate_embeddings_batch(batch, batch_size)
                    all_embeddings.extend(batch_embeddings)
            else:
                all_embeddings = self.client.generate_embeddings_batch(texts)

            logger.info(f"Generated {len(all_embeddings)} embeddings")
            return all_embeddings

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise

    def generate_query_embedding(self, query: str) -> List[float]:
        """
        Generate embedding for a query string.

        Args:
            query: Query text

        Returns:
            Query embedding vector

        Raises:
            Exception: If embedding generation fails
        """
        logger.info(f"Generating embedding for query: {query[:50]}...")
        return self.client.generate_embedding(query)

    def estimate_cost(self, token_count: int) -> Dict[str, float]:
        """
        Estimate embedding generation cost.

        Args:
            token_count: Number of tokens to embed

        Returns:
            Dictionary with cost estimates
        """
        # text-embedding-3-small: $0.02/1M tokens
        # This is via OpenRouter/OpenAI compatibility
        cost_per_million = 0.02
        cost_usd = (token_count / 1_000_000) * cost_per_million

        # Convert to INR (approximate rate: 1 USD = 83 INR)
        inr_rate = 83
        cost_inr = cost_usd * inr_rate

        return {
            "tokens": token_count,
            "cost_usd": round(cost_usd, 4),
            "cost_inr": round(cost_inr, 2)
        }
