"""
Minimal Embedding Provider for Ingestion

Stripped-down version with only OpenAI embeddings support.
"""

from openai import AsyncOpenAI


def chunk_text(
    text: str, chunk_size: int = 1000, chunk_overlap: int = 200
) -> list[str]:
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

    # Embedding dimensions for different models
    MODEL_DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        """
        Initialize OpenAI client.

        Args:
            api_key: OpenAI API key
            model: Embedding model to use
        """
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.dimension = self.MODEL_DIMENSIONS.get(model, 1536)

    def get_dimension(self) -> int:
        """
        Get the embedding dimension for the current model.

        Returns:
            Embedding dimension
        """
        return self.dimension

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        response = await self.client.embeddings.create(
            input=texts,
            model=self.model,
            dimensions=3072  # Use full 3072 dimensions for text-embedding-3-large
        )
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
