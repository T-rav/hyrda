"""
Minimal Embedding Provider for Ingestion

Stripped-down version with only OpenAI embeddings support.
"""

from typing import Any

from openai import AsyncOpenAI


def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> list[str]:
    """
    Split text into overlapping chunks.

    Args:
        text: Text to chunk
        chunk_size: Maximum size of each chunk
        chunk_overlap: Number of characters to overlap between chunks

    Returns:
        List of text chunks
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)

        # Move start forward by (chunk_size - overlap)
        start += chunk_size - chunk_overlap

    return chunks


class OpenAIEmbeddingProvider:
    """Minimal OpenAI embedding provider for document ingestion."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        """
        Initialize OpenAI client.

        Args:
            api_key: OpenAI API key
            model: Embedding model to use
        """
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        response = await self.client.embeddings.create(input=texts, model=self.model)
        return [item.embedding for item in response.data]

    async def embed_query(self, text: str) -> list[float]:
        """
        Generate embedding for a single query.

        Args:
            text: Query text

        Returns:
            Embedding vector
        """
        embeddings = await self.embed_texts([text])
        return embeddings[0]

    def chunk_text(
        self, text: str, chunk_size: int = 1000, chunk_overlap: int = 200
    ) -> list[str]:
        """
        Split text into chunks.

        Args:
            text: Text to chunk
            chunk_size: Maximum size of each chunk
            chunk_overlap: Number of characters to overlap

        Returns:
            List of text chunks
        """
        return chunk_text(text, chunk_size, chunk_overlap)
