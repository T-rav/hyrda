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

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Uses rough approximation: ~4 characters per token for English text.
        This is conservative to avoid hitting token limits.
        """
        return len(text) // 4

    def _create_token_aware_batches(
        self, texts: list[str], max_texts: int = 2048, max_tokens: int = 280000
    ) -> list[list[str]]:
        """
        Create batches that respect both text count and token count limits.

        Args:
            texts: List of texts to batch
            max_texts: Maximum texts per batch (OpenAI limit: 2048)
            max_tokens: Maximum tokens per batch (OpenAI limit: 300k, use 280k for safety)

        Returns:
            List of batches, where each batch is a list of texts
        """
        batches = []
        current_batch = []
        current_tokens = 0

        for text in texts:
            text_tokens = self._estimate_tokens(text)

            # If single text exceeds token limit, truncate it
            if text_tokens > max_tokens:
                logger.warning(
                    f"Single text has ~{text_tokens} tokens, truncating to {max_tokens}"
                )
                # Rough truncation: keep first max_tokens * 4 characters
                text = text[: max_tokens * 4]
                text_tokens = max_tokens

            # Start new batch if adding this text would exceed limits
            if (
                current_batch
                and (
                    len(current_batch) >= max_texts
                    or current_tokens + text_tokens > max_tokens
                )
            ):
                batches.append(current_batch)
                current_batch = []
                current_tokens = 0

            current_batch.append(text)
            current_tokens += text_tokens

        # Add final batch
        if current_batch:
            batches.append(current_batch)

        return batches

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

        # Create token-aware batches (respects both text and token limits)
        batches = self._create_token_aware_batches(filtered_texts)
        logger.info(
            f"Split {len(filtered_texts)} texts into {len(batches)} batches "
            f"(token-aware batching)"
        )

        all_embeddings = []

        try:
            for batch_idx, batch in enumerate(batches, 1):
                estimated_tokens = sum(self._estimate_tokens(t) for t in batch)
                logger.info(
                    f"Generating embeddings for batch {batch_idx}/{len(batches)} "
                    f"({len(batch)} texts, ~{estimated_tokens:,} tokens)"
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
