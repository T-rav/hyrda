"""
Sentence Transformers embedding provider implementation (local)
"""

import asyncio
import logging

from config.settings import EmbeddingSettings
from services.embedding.base import EmbeddingProvider

logger = logging.getLogger(__name__)


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """Sentence Transformers embedding provider (local)"""

    def __init__(self, settings: EmbeddingSettings):
        super().__init__(settings)
        self.model_instance = None
        self._initialized = False

    async def _initialize(self) -> None:
        """Initialize the sentence transformer model"""
        if self._initialized:
            return

        try:
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415

            # Load model in executor to avoid blocking
            self.model_instance = await asyncio.get_event_loop().run_in_executor(
                None, SentenceTransformer, self.model
            )

            self._initialized = True
            logger.info(f"Initialized SentenceTransformer model: {self.model}")

        except ImportError:
            raise ImportError(
                "sentence-transformers package not installed. "
                "Run: pip install sentence-transformers"
            ) from None
        except Exception as e:
            logger.error(f"Failed to initialize SentenceTransformer: {e}")
            raise

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts"""
        await self._initialize()

        try:
            logger.info(
                f"Generating embeddings for {len(texts)} texts using {self.model}"
            )

            # Run encoding in executor to avoid blocking
            if self.model_instance is None:
                raise RuntimeError("SentenceTransformer model not initialized")

            embeddings = await asyncio.get_event_loop().run_in_executor(
                None,
                self.model_instance.encode,
                texts,
                {"convert_to_numpy": True, "show_progress_bar": False},
            )

            # Convert numpy arrays to lists
            embeddings_list = [embedding.tolist() for embedding in embeddings]

            logger.info(
                f"Generated {len(embeddings_list)} embeddings",
                extra={
                    "model": self.model,
                    "text_count": len(texts),
                    "embedding_dimensions": (
                        len(embeddings_list[0]) if embeddings_list else 0
                    ),
                    "event_type": "embeddings_success",
                },
            )

            return embeddings_list

        except Exception as e:
            logger.error(
                f"Failed to generate embeddings: {e}",
                extra={
                    "model": self.model,
                    "text_count": len(texts),
                    "error": str(e),
                    "event_type": "embeddings_error",
                },
            )
            raise

    async def get_embedding(self, text: str) -> list[float]:
        """Generate embedding for a single text"""
        embeddings = await self.get_embeddings([text])
        return embeddings[0]

    async def close(self):
        """Clean up resources"""
        self.model_instance = None
        self._initialized = False
