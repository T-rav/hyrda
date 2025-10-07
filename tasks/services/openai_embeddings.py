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
            raise ValueError(
                "EMBEDDING_API_KEY or LLM_API_KEY not found in environment"
            )

        self.model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
        self.client = None

    def _get_client(self):
        """Lazy load OpenAI client."""
        if not self.client:
            try:
                from openai import OpenAI

                self.client = OpenAI(api_key=self.api_key)
            except ImportError as e:
                raise ImportError(
                    "openai package not installed. Run: pip install openai"
                ) from e
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

        # Filter out empty strings (OpenAI API rejects them)
        filtered_texts = [t for t in texts if t and t.strip()]
        if not filtered_texts:
            logger.warning("All texts were empty after filtering")
            return []

        if len(filtered_texts) != len(texts):
            logger.warning(
                f"Filtered out {len(texts) - len(filtered_texts)} empty texts from batch"
            )

        client = self._get_client()

        # OpenAI has a limit of 2048 texts per batch
        batch_size = 2048
        all_embeddings = []

        try:
            for i in range(0, len(filtered_texts), batch_size):
                batch = filtered_texts[i : i + batch_size]
                logger.info(
                    f"Generating embeddings for batch {i // batch_size + 1} "
                    f"({len(batch)} texts)"
                )
                response = client.embeddings.create(input=batch, model=self.model)
                batch_embeddings = [data.embedding for data in response.data]
                all_embeddings.extend(batch_embeddings)

            logger.info(
                f"Generated {len(all_embeddings)} embeddings using {self.model}"
            )
            return all_embeddings
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise
