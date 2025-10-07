"""Standalone OpenAI embeddings client for tasks service."""

import logging
import os

logger = logging.getLogger(__name__)


class OpenAIEmbeddings:
    """Standalone OpenAI embeddings client."""

    def __init__(self):
        """Initialize OpenAI client."""
        self.api_key = os.getenv("EMBEDDING_API_KEY") or os.getenv("LLM_API_KEY")
        if not self.api_key:
            raise ValueError("EMBEDDING_API_KEY or LLM_API_KEY not found in environment")

        self.model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
        self.client = None

    def _get_client(self):
        """Lazy load OpenAI client."""
        if not self.client:
            try:
                from openai import OpenAI

                self.client = OpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("openai package not installed. Run: pip install openai")
        return self.client

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a batch of texts.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        client = self._get_client()

        try:
            response = client.embeddings.create(input=texts, model=self.model)
            embeddings = [data.embedding for data in response.data]
            logger.debug(f"Generated {len(embeddings)} embeddings using {self.model}")
            return embeddings
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise
