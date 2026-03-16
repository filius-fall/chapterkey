"""
OpenRouter API client for embeddings and LLM calls.
Provides OpenAI-compatible interface through OpenRouter.
"""
import logging
from typing import List, Optional
import openai
from config import Config

logger = logging.getLogger(__name__)

class OpenRouterClient:
    """Client for OpenRouter API operations."""

    def __init__(self):
        """Initialize OpenRouter client."""
        is_valid, error = Config.validate()
        if not is_valid:
            raise ValueError(f"Configuration error: {error}")

        self.client = openai.OpenAI(**Config.get_openai_client_kwargs())
        self.embedding_model = Config.EMBEDDING_MODEL
        self.llm_model = Config.LLM_MODEL

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text string.

        Args:
            text: Text to embed

        Returns:
            List of float values representing the embedding

        Raises:
            Exception: If API call fails
        """
        try:
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=text,
                encoding_format="float"
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    def generate_embeddings_batch(self, texts: List[str], batch_size: Optional[int] = None) -> List[List[float]]:
        """
        Generate embeddings for multiple text strings in batches.

        Args:
            texts: List of texts to embed
            batch_size: Batch size (defaults to config value)

        Returns:
            List of embeddings

        Raises:
            Exception: If API call fails
        """
        if not texts:
            return []

        batch_size = batch_size or Config.EMBEDDING_BATCH_SIZE
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                response = self.client.embeddings.create(
                    model=self.embedding_model,
                    input=batch,
                    encoding_format="float"
                )
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                logger.info(f"Generated embeddings for batch {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size}")
            except Exception as e:
                logger.error(f"Error generating embeddings for batch {i//batch_size + 1}: {e}")
                raise

        return all_embeddings

    def chat_completion(self, messages: List[dict], temperature: float = 0.7, max_tokens: Optional[int] = None) -> str:
        """
        Generate chat completion using LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate

        Returns:
            Generated response text

        Raises:
            Exception: If API call fails
        """
        try:
            kwargs = {
                "model": self.llm_model,
                "messages": messages,
                "temperature": temperature,
            }
            if max_tokens:
                kwargs["max_tokens"] = max_tokens

            response = self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating chat completion: {e}")
            raise
