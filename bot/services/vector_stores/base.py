"""
Base Vector Store Interface

Abstract base class defining the interface for all vector store implementations.
"""

from abc import ABC, abstractmethod
from typing import Any

from config.settings import VectorSettings


class VectorStore(ABC):
    """Abstract base class for vector stores"""

    def __init__(self, settings: VectorSettings):
        self.settings = settings
        self.collection_name = settings.collection_name

    @abstractmethod
    async def initialize(self):
        pass

    @abstractmethod
    async def add_documents(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadata: list[dict[str, Any]] | None = None,
    ):
        pass

    @abstractmethod
    async def search(
        self,
        query_embedding: list[float],
        limit: int = 5,
        similarity_threshold: float = 0.7,
    ) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def delete_documents(self, document_ids: list[str]):
        pass

    @abstractmethod
    async def close(self):
        pass
