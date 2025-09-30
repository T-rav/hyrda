"""
RetrievalResultFactory for test utilities
"""

from datetime import datetime

from models import RetrievalResult
from models.retrieval import RetrievalMethod


class RetrievalResultFactory:
    """Factory for creating retrieval result objects"""

    @staticmethod
    def create_basic_result(
        content: str = "Test content",
        similarity: float = 0.9,
        source: RetrievalMethod = RetrievalMethod.DENSE,
    ) -> RetrievalResult:
        """Create basic retrieval result"""
        return RetrievalResult(
            content=content,
            similarity=similarity,
            chunk_id="chunk-1",
            document_id="doc-1",
            source=source,
            metadata={},
            retrieved_at=datetime.now(),
        )

    @staticmethod
    def create_results_list(
        count: int = 3,
        similarity_range: tuple[float, float] = (0.7, 0.9),
    ) -> list[RetrievalResult]:
        """Create list of retrieval results with varying similarity"""
        results = []
        sim_min, sim_max = similarity_range
        sim_step = (sim_max - sim_min) / (count - 1) if count > 1 else 0

        for i in range(count):
            similarity = sim_max - (i * sim_step)
            result = RetrievalResultFactory.create_basic_result(
                content=f"Content {i + 1}",
                similarity=similarity,
            )
            results.append(result)

        return results

    @staticmethod
    def create_dense_result(content: str = "Dense content") -> RetrievalResult:
        """Create dense retrieval result"""
        return RetrievalResultFactory.create_basic_result(
            content=content, source=RetrievalMethod.DENSE
        )

    @staticmethod
    def create_sparse_result(content: str = "Sparse content") -> RetrievalResult:
        """Create sparse retrieval result"""
        return RetrievalResultFactory.create_basic_result(
            content=content, source=RetrievalMethod.SPARSE
        )

    @staticmethod
    def create_hybrid_result(content: str = "Hybrid content") -> RetrievalResult:
        """Create hybrid retrieval result"""
        return RetrievalResultFactory.create_basic_result(
            content=content, source=RetrievalMethod.HYBRID
        )
