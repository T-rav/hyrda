"""
Abstract base class for cross-encoder rerankers
"""

from abc import ABC, abstractmethod

from models import RetrievalResult


class Reranker(ABC):
    """Abstract base class for cross-encoder rerankers"""

    @abstractmethod
    async def rerank(
        self, query: str, documents: list[RetrievalResult], top_k: int = 10
    ) -> list[RetrievalResult]:
        """
        Rerank documents using cross-encoder

        Args:
            query: Search query
            documents: List of documents to rerank
            top_k: Number of top documents to return

        Returns:
            Reranked list of documents
        """
        pass
