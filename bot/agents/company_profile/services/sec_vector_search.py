"""In-Memory Vector Search for SEC Documents

Ephemeral vector search without persisting to Qdrant.
Embeddings and search happen entirely in memory.
"""

import logging
from typing import Any

import numpy as np
import tiktoken
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class SECInMemoryVectorSearch:
    """In-memory vector search for SEC documents."""

    def __init__(
        self, openai_api_key: str, embedding_model: str = "text-embedding-3-small"
    ):
        """
        Initialize in-memory vector search.

        Args:
            openai_api_key: OpenAI API key for embeddings
            embedding_model: Embedding model to use
        """
        self.client = AsyncOpenAI(api_key=openai_api_key)
        self.embedding_model = embedding_model
        self.embeddings: list[np.ndarray] = []
        self.chunks: list[str] = []
        self.metadata: list[dict[str, Any]] = []

        # Initialize tiktoken encoder for token counting
        try:
            self.encoder = tiktoken.encoding_for_model(embedding_model)
        except KeyError:
            # Fallback to cl100k_base (used by text-embedding-3-*)
            logger.warning(
                f"Could not find encoding for {embedding_model}, using cl100k_base"
            )
            self.encoder = tiktoken.get_encoding("cl100k_base")

        # OpenAI embedding API limits
        self.max_tokens_per_input = 8191  # Max tokens per input string
        self.max_inputs_per_request = 2048  # Max inputs per API call

    def _validate_and_truncate_chunk(self, chunk: str) -> str:
        """
        Validate chunk token count and truncate if needed.

        Args:
            chunk: Text chunk to validate

        Returns:
            Validated chunk (truncated if over token limit)
        """
        tokens = self.encoder.encode(chunk)
        token_count = len(tokens)

        if token_count > self.max_tokens_per_input:
            logger.warning(
                f"Chunk exceeds {self.max_tokens_per_input} tokens ({token_count} tokens). Truncating..."
            )
            # Truncate to max tokens
            truncated_tokens = tokens[: self.max_tokens_per_input]
            truncated_chunk = self.encoder.decode(truncated_tokens)
            logger.info(
                f"Truncated chunk from {token_count} to {len(truncated_tokens)} tokens"
            )
            return truncated_chunk

        return chunk

    async def add_filing_chunks(
        self, chunks: list[str], filing_metadata: dict[str, Any]
    ) -> None:
        """
        Add chunks from a filing to the in-memory index.

        Args:
            chunks: Text chunks from filing
            filing_metadata: Metadata about the filing (type, date, etc.)
        """
        logger.info(f"Validating and generating embeddings for {len(chunks)} chunks...")

        # Validate and truncate chunks if needed
        validated_chunks = [
            self._validate_and_truncate_chunk(chunk) for chunk in chunks
        ]

        # Count total tokens for logging
        total_tokens = sum(
            len(self.encoder.encode(chunk)) for chunk in validated_chunks
        )
        logger.info(
            f"Total tokens to embed: {total_tokens:,} (~${total_tokens * 0.02 / 1_000_000:.4f} cost)"
        )

        # Generate embeddings in batches
        batch_size = 100  # Conservative (API allows up to 2048)
        for i in range(0, len(validated_chunks), batch_size):
            batch = validated_chunks[i : i + batch_size]

            try:
                response = await self.client.embeddings.create(
                    model=self.embedding_model, input=batch
                )

                for j, embedding_obj in enumerate(response.data):
                    embedding = np.array(embedding_obj.embedding)
                    self.embeddings.append(embedding)
                    self.chunks.append(batch[j])
                    self.metadata.append(
                        {
                            **filing_metadata,
                            "chunk_index": i + j,
                        }
                    )

                logger.info(
                    f"Processed batch {i // batch_size + 1}/{(len(chunks) + batch_size - 1) // batch_size}"
                )

            except Exception as e:
                logger.error(f"Failed to generate embeddings for batch {i}: {e}")
                continue

        logger.info(
            f"✅ Added {len(self.chunks)} chunks to in-memory index (total: {len(self.chunks)})"
        )

    async def search(
        self, query: str, top_k: int = 5, min_score: float = 0.7
    ) -> list[dict[str, Any]]:
        """
        Search for relevant chunks using cosine similarity.

        Args:
            query: Search query
            top_k: Number of results to return
            min_score: Minimum similarity score (0-1)

        Returns:
            List of relevant chunks with metadata and scores
        """
        if not self.embeddings:
            logger.warning("No chunks in index")
            return []

        # Validate and truncate query if needed
        validated_query = self._validate_and_truncate_chunk(query)

        # Generate query embedding
        try:
            response = await self.client.embeddings.create(
                model=self.embedding_model, input=[validated_query]
            )
            query_embedding = np.array(response.data[0].embedding)
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            return []

        # Calculate cosine similarity with all chunks
        scores = []
        for embedding in self.embeddings:
            similarity = self._cosine_similarity(query_embedding, embedding)
            scores.append(similarity)

        # Get top-k results above threshold
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in indexed_scores[:top_k]:
            if score >= min_score:
                results.append(
                    {
                        "content": self.chunks[idx],
                        "score": float(score),
                        "metadata": self.metadata[idx],
                    }
                )

        logger.info(
            f"Found {len(results)} relevant chunks (min_score={min_score}, top_k={top_k})"
        )

        return results

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the in-memory index."""
        return {
            "total_chunks": len(self.chunks),
            "total_characters": sum(len(chunk) for chunk in self.chunks),
            "filings": list({m["type"] for m in self.metadata}),
        }

    def clear(self) -> None:
        """Clear all data from memory."""
        self.embeddings = []
        self.chunks = []
        self.metadata = []
        logger.info("Cleared in-memory index")
