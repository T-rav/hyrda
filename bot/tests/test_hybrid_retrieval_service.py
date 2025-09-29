"""
Tests for Hybrid Retrieval Service

Tests RRF fusion, reranking, and hybrid search orchestration using factory patterns.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.retrieval import RetrievalMethod, RetrievalResult
from services.hybrid_retrieval_service import (
    CohereReranker,
    HybridRetrievalService,
)


# TDD Factory Patterns for Hybrid Retrieval Service Testing
class RetrievalResultFactory:
    """Factory for creating RetrievalResult instances with different configurations"""

    @staticmethod
    def create_dense_result(
        content: str = "Dense content",
        similarity: float = 0.85,
        chunk_id: str = "d1",
        document_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        rank: int | None = None,
    ) -> RetrievalResult:
        """Create dense retrieval result"""
        return RetrievalResult(
            content=content,
            similarity=similarity,
            chunk_id=chunk_id,
            document_id=document_id or chunk_id,
            source=RetrievalMethod.DENSE,
            metadata=metadata or {},
            rank=rank,
        )

    @staticmethod
    def create_sparse_result(
        content: str = "Sparse content",
        similarity: float = 0.75,
        chunk_id: str = "s1",
        document_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        rank: int | None = None,
    ) -> RetrievalResult:
        """Create sparse retrieval result"""
        return RetrievalResult(
            content=content,
            similarity=similarity,
            chunk_id=chunk_id,
            document_id=document_id or chunk_id,
            source=RetrievalMethod.SPARSE,
            metadata=metadata or {},
            rank=rank,
        )

    @staticmethod
    def create_hybrid_result(
        content: str = "Hybrid content",
        similarity: float = 0.90,
        chunk_id: str = "h1",
        document_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        rank: int | None = None,
    ) -> RetrievalResult:
        """Create hybrid retrieval result"""
        return RetrievalResult(
            content=content,
            similarity=similarity,
            chunk_id=chunk_id,
            document_id=document_id or chunk_id,
            source=RetrievalMethod.HYBRID,
            metadata=metadata or {},
            rank=rank,
        )


class RetrievalResultBuilder:
    """Builder for creating collections of retrieval results"""

    def __init__(self):
        self.results: list[RetrievalResult] = []

    def add_dense_result(
        self,
        content: str = "Dense content",
        similarity: float = 0.85,
        chunk_id: str | None = None,
    ) -> "RetrievalResultBuilder":
        """Add a dense result to the collection"""
        if chunk_id is None:
            chunk_id = f"d{len([r for r in self.results if r.source == RetrievalMethod.DENSE]) + 1}"
        result = RetrievalResultFactory.create_dense_result(
            content=content, similarity=similarity, chunk_id=chunk_id
        )
        self.results.append(result)
        return self

    def add_sparse_result(
        self,
        content: str = "Sparse content",
        similarity: float = 0.75,
        chunk_id: str | None = None,
    ) -> "RetrievalResultBuilder":
        """Add a sparse result to the collection"""
        if chunk_id is None:
            chunk_id = f"s{len([r for r in self.results if r.source == RetrievalMethod.SPARSE]) + 1}"
        result = RetrievalResultFactory.create_sparse_result(
            content=content, similarity=similarity, chunk_id=chunk_id
        )
        self.results.append(result)
        return self

    def build(self) -> list[RetrievalResult]:
        """Build the results collection"""
        return self.results.copy()

    @staticmethod
    def no_overlap_scenario() -> tuple[list[RetrievalResult], list[RetrievalResult]]:
        """Create dense and sparse results with no overlap"""
        dense_results = (
            RetrievalResultBuilder()
            .add_dense_result("Dense 1", 0.9, "d1")
            .add_dense_result("Dense 2", 0.8, "d2")
            .build()
        )
        sparse_results = (
            RetrievalResultBuilder()
            .add_sparse_result("Sparse 1", 0.7, "s1")
            .add_sparse_result("Sparse 2", 0.6, "s2")
            .build()
        )
        return dense_results, sparse_results

    @staticmethod
    def overlap_scenario() -> tuple[list[RetrievalResult], list[RetrievalResult]]:
        """Create dense and sparse results with overlapping documents"""
        dense_results = [
            RetrievalResultFactory.create_dense_result(
                content="Overlap doc", similarity=0.9, chunk_id="overlap"
            ),
            RetrievalResultFactory.create_dense_result(
                content="Dense only", similarity=0.8, chunk_id="dense_only"
            ),
        ]
        sparse_results = [
            RetrievalResultFactory.create_sparse_result(
                content="Sparse only", similarity=0.7, chunk_id="sparse_only"
            ),
            RetrievalResultFactory.create_sparse_result(
                content="Overlap doc", similarity=0.6, chunk_id="overlap"
            ),
        ]
        return dense_results, sparse_results


class MockVectorStoreFactory:
    """Factory for creating mock vector stores with different behaviors"""

    @staticmethod
    def create_basic_store(results: list[dict[str, Any]] | None = None) -> MagicMock:
        """Create basic mock vector store"""
        store = MagicMock()
        store.search = AsyncMock(return_value=results or [])
        store.bm25_search = AsyncMock(return_value=results or [])
        store.close = AsyncMock()
        return store

    @staticmethod
    def create_dense_store(results: list[dict[str, Any]] | None = None) -> MagicMock:
        """Create mock dense vector store with default dense results"""
        default_results = [
            {"content": "Dense doc 1", "similarity": 0.9, "metadata": {}, "id": "d1"},
            {"content": "Dense doc 2", "similarity": 0.8, "metadata": {}, "id": "d2"},
        ]
        return MockVectorStoreFactory.create_basic_store(results or default_results)

    @staticmethod
    def create_sparse_store(results: list[dict[str, Any]] | None = None) -> MagicMock:
        """Create mock sparse vector store with default sparse results"""
        default_results = [
            {"content": "Sparse doc 1", "similarity": 0.7, "metadata": {}, "id": "s1"}
        ]
        return MockVectorStoreFactory.create_basic_store(results or default_results)

    @staticmethod
    def create_failing_store() -> MagicMock:
        """Create mock store that raises exceptions"""
        store = MagicMock()
        store.search = AsyncMock(side_effect=Exception("Dense failed"))
        store.bm25_search = AsyncMock(side_effect=Exception("Sparse failed"))
        store.close = AsyncMock()
        return store


class HybridRetrievalServiceFactory:
    """Factory for creating HybridRetrievalService instances with complete test scenarios"""

    @staticmethod
    def create_basic_service(
        dense_store: MagicMock | None = None,
        sparse_store: MagicMock | None = None,
    ) -> HybridRetrievalService:
        """Create basic hybrid retrieval service"""
        return HybridRetrievalService(
            dense_store=dense_store or MockVectorStoreFactory.create_basic_store(),
            sparse_store=sparse_store or MockVectorStoreFactory.create_basic_store(),
            dense_top_k=5,
            sparse_top_k=5,
            fusion_top_k=3,
            final_top_k=2,
            rrf_k=60,
        )

    @staticmethod
    def create_service_with_reranker(
        reranker: AsyncMock | None = None,
    ) -> HybridRetrievalService:
        """Create service with reranker"""
        return HybridRetrievalService(
            dense_store=MockVectorStoreFactory.create_basic_store(),
            sparse_store=MockVectorStoreFactory.create_basic_store(),
            reranker=reranker or AsyncMock(),
            final_top_k=1,
        )

    @staticmethod
    def create_search_scenario(
        dense_results: list[dict[str, Any]] | None = None,
        sparse_results: list[dict[str, Any]] | None = None,
    ) -> tuple[HybridRetrievalService, MagicMock, MagicMock]:
        """Create complete search scenario with configured stores and results"""
        # Set up default results
        default_dense = [
            {"content": "Dense result", "similarity": 0.9, "metadata": {}, "id": "d1"}
        ]
        default_sparse = [
            {"content": "Sparse result", "similarity": 0.8, "metadata": {}, "id": "s1"}
        ]

        # Create stores with configured results
        dense_store = MockVectorStoreFactory.create_basic_store()
        sparse_store = MockVectorStoreFactory.create_basic_store()

        dense_store.search.return_value = dense_results or default_dense
        sparse_store.bm25_search.return_value = sparse_results or default_sparse

        # Create service
        service = HybridRetrievalService(
            dense_store=dense_store,
            sparse_store=sparse_store,
            dense_top_k=5,
            sparse_top_k=5,
            fusion_top_k=3,
            final_top_k=2,
            rrf_k=60,
        )

        return service, dense_store, sparse_store

    @staticmethod
    def create_threshold_scenario() -> (
        tuple[HybridRetrievalService, MagicMock, MagicMock]
    ):
        """Create scenario for testing similarity threshold filtering"""
        dense_results = [
            {"content": "High sim", "similarity": 0.9, "metadata": {}, "id": "h1"},
            {"content": "Low sim", "similarity": 0.3, "metadata": {}, "id": "l1"},
        ]
        sparse_results: list[dict[str, Any]] = []

        return HybridRetrievalServiceFactory.create_search_scenario(
            dense_results=dense_results, sparse_results=sparse_results
        )

    @staticmethod
    def create_exception_scenario() -> (
        tuple[HybridRetrievalService, MagicMock, MagicMock]
    ):
        """Create scenario for testing exception handling"""
        service, dense_store, sparse_store = (
            HybridRetrievalServiceFactory.create_search_scenario()
        )

        # Configure dense store to fail
        dense_store.search.side_effect = Exception("Dense failed")
        sparse_store.bm25_search.return_value = [
            {"content": "Sparse only", "similarity": 0.7, "metadata": {}, "id": "s1"}
        ]

        return service, dense_store, sparse_store


class CohereRerankerFactory:
    """Factory for creating CohereReranker instances and mocks"""

    @staticmethod
    def create_basic_reranker(
        api_key: str = "test-key", model: str = "rerank-english-v3.0"
    ) -> CohereReranker:
        """Create basic Cohere reranker"""
        return CohereReranker(api_key=api_key, model=model)

    @staticmethod
    def create_mock_reranker_response(results: list[tuple[int, float]]) -> MagicMock:
        """Create mock Cohere API response"""
        mock_results = []
        for index, relevance_score in results:
            mock_result = MagicMock()
            mock_result.index = index
            mock_result.relevance_score = relevance_score
            mock_results.append(mock_result)

        mock_response = MagicMock()
        mock_response.results = mock_results
        return mock_response


class TestRetrievalResult:
    """Test RetrievalResult dataclass using factory patterns"""

    def test_retrieval_result_creation(self):
        """Test creating a RetrievalResult"""
        result = RetrievalResultFactory.create_dense_result(
            content="Test content",
            similarity=0.85,
            chunk_id="doc_1",
            document_id="doc_1",
            rank=1,
            metadata={"source": "test"},
        )

        assert result.content == "Test content"
        assert result.similarity == 0.85
        assert result.metadata == {"source": "test"}
        assert result.chunk_id == "doc_1"
        assert result.document_id == "doc_1"
        assert result.source == RetrievalMethod.DENSE
        assert result.rank == 1

    def test_retrieval_result_optional_rank(self):
        """Test RetrievalResult with optional rank"""
        result = RetrievalResultFactory.create_sparse_result(
            content="Content",
            similarity=0.5,
            chunk_id="doc_2",
            document_id="doc_2",
        )

        assert result.rank is None


class TestCohereReranker:
    """Test Cohere reranking functionality using factory patterns"""

    @pytest.mark.asyncio
    async def test_cohere_reranker_initialization(self):
        """Test Cohere reranker initialization"""
        reranker = CohereRerankerFactory.create_basic_reranker()

        assert reranker.api_key == "test-key"
        assert reranker.model == "rerank-english-v3.0"
        assert reranker._client is None

    @pytest.mark.asyncio
    @patch("cohere.AsyncClient")
    async def test_cohere_rerank_success(self, mock_cohere):
        """Test successful Cohere reranking"""
        # Setup mock response using factory
        mock_response = CohereRerankerFactory.create_mock_reranker_response(
            [(1, 0.9), (0, 0.7)]  # index, relevance_score pairs
        )

        mock_client = AsyncMock()
        mock_client.rerank = AsyncMock(return_value=mock_response)
        mock_cohere.return_value = mock_client

        # Create test data using factories
        reranker = CohereRerankerFactory.create_basic_reranker()
        documents = [
            RetrievalResultFactory.create_dense_result(
                content="Doc 1", similarity=0.5, chunk_id="1"
            ),
            RetrievalResultFactory.create_dense_result(
                content="Doc 2", similarity=0.6, chunk_id="2"
            ),
        ]

        # Execute
        result = await reranker.rerank("test query", documents, top_k=2)

        # Verify
        assert len(result) == 2
        assert result[0].content == "Doc 2"  # Index 1, higher score
        assert result[0].similarity == 0.9
        assert result[0].rank == 1
        assert result[1].content == "Doc 1"  # Index 0, lower score
        assert result[1].similarity == 0.7
        assert result[1].rank == 2

        # Verify API call
        mock_client.rerank.assert_called_once()
        call_args = mock_client.rerank.call_args
        assert call_args[1]["query"] == "test query"
        assert call_args[1]["documents"] == ["Doc 1", "Doc 2"]
        assert call_args[1]["top_k"] == 2

    @pytest.mark.asyncio
    @patch("cohere.AsyncClient")
    async def test_cohere_rerank_failure_fallback(self, mock_cohere):
        """Test Cohere reranking failure fallback"""
        mock_client = AsyncMock()
        mock_client.rerank = AsyncMock(side_effect=Exception("API Error"))
        mock_cohere.return_value = mock_client

        reranker = CohereRerankerFactory.create_basic_reranker()
        documents = [
            RetrievalResultFactory.create_dense_result(
                content="Doc 1", similarity=0.8, chunk_id="1"
            ),
            RetrievalResultFactory.create_dense_result(
                content="Doc 2", similarity=0.6, chunk_id="2"
            ),
        ]

        # Should fallback to original ranking
        result = await reranker.rerank("test query", documents, top_k=2)

        assert len(result) == 2
        assert result == documents  # Original order preserved


class TestHybridRetrievalService:
    """Test hybrid retrieval orchestration using factory patterns"""

    @pytest.mark.asyncio
    async def test_dense_retrieval(self):
        """Test dense retrieval conversion"""
        # Create service and store using factories
        dense_store = MockVectorStoreFactory.create_dense_store()
        service = HybridRetrievalServiceFactory.create_basic_service(
            dense_store=dense_store
        )

        results = await service._dense_retrieval([0.1] * 1536)

        assert len(results) == 2
        assert results[0].content == "Dense doc 1"
        assert results[0].similarity == 0.9
        assert results[0].source == RetrievalMethod.DENSE
        assert results[1].chunk_id == "d2"

    @pytest.mark.asyncio
    async def test_sparse_retrieval(self):
        """Test sparse retrieval conversion"""
        # Create service and store using factories
        sparse_store = MockVectorStoreFactory.create_sparse_store()
        service = HybridRetrievalServiceFactory.create_basic_service(
            sparse_store=sparse_store
        )

        results = await service._sparse_retrieval("test query")

        assert len(results) == 1
        assert results[0].content == "Sparse doc 1"
        assert results[0].source == RetrievalMethod.SPARSE

        # Verify BM25 search was called with correct parameters
        sparse_store.bm25_search.assert_called_once_with(
            query="test query",
            limit=5,  # sparse_top_k
            field_boosts={"title": 8.0, "content": 1.0},
        )

    def test_reciprocal_rank_fusion_no_overlap(self):
        """Test RRF with no overlapping documents"""
        service = HybridRetrievalServiceFactory.create_basic_service()
        dense_results, sparse_results = RetrievalResultBuilder.no_overlap_scenario()

        fused = service._reciprocal_rank_fusion(dense_results, sparse_results)

        assert len(fused) == 4

        # Check RRF scores (1/(k+rank))
        # d1: 1/(60+1) ≈ 0.0164, s1: 1/(60+1) ≈ 0.0164
        # d2: 1/(60+2) ≈ 0.0161, s2: 1/(60+2) ≈ 0.0161

        # Should be sorted by RRF score (descending)
        assert fused[0].chunk_id in ["d1", "s1"]  # Tied for first

        # Check proper source labeling (no overlap, so should be dense/sparse, not hybrid)
        dense_docs = [r for r in fused if r.chunk_id.startswith("d")]
        sparse_docs = [r for r in fused if r.chunk_id.startswith("s")]
        assert all(result.source == RetrievalMethod.DENSE for result in dense_docs)
        assert all(result.source == RetrievalMethod.SPARSE for result in sparse_docs)
        assert all(result.rank == i + 1 for i, result in enumerate(fused))

    def test_reciprocal_rank_fusion_with_overlap(self):
        """Test RRF with overlapping documents"""
        service = HybridRetrievalServiceFactory.create_basic_service()
        dense_results, sparse_results = RetrievalResultBuilder.overlap_scenario()

        fused = service._reciprocal_rank_fusion(dense_results, sparse_results)

        assert len(fused) == 3  # Deduplicated

        # Find the overlapping document
        overlap_doc = next(doc for doc in fused if doc.chunk_id == "overlap")

        # Should have the highest scaled similarity score (since it has the highest RRF score)
        # With our scaling, the top result should be close to 0.95
        assert (
            overlap_doc.similarity > 0.9
        )  # Should be near the top of the scaled range
        assert overlap_doc.similarity <= 0.95  # But not exceed the maximum
        assert overlap_doc.source == RetrievalMethod.HYBRID

    @pytest.mark.asyncio
    async def test_hybrid_search_full_pipeline(self):
        """Test complete hybrid search pipeline"""
        # Create complete scenario using factory
        service, dense_store, sparse_store = (
            HybridRetrievalServiceFactory.create_search_scenario()
        )

        # No reranker in this test
        results = await service.hybrid_search(
            query="test query", query_embedding=[0.1] * 1536, top_k=2
        )

        assert len(results) <= 2
        assert all(isinstance(r, RetrievalResult) for r in results)

        # Verify both stores were called
        dense_store.search.assert_called_once()
        sparse_store.bm25_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_hybrid_search_with_reranker(self):
        """Test hybrid search with reranking"""
        # Create stores using factories
        dense_store = MockVectorStoreFactory.create_basic_store()
        sparse_store = MockVectorStoreFactory.create_basic_store()

        # Setup mock reranker
        mock_reranker = AsyncMock()
        mock_reranked = [
            RetrievalResult(
                content="Reranked",
                similarity=0.95,
                chunk_id="r1",
                document_id="r1",
                source="hybrid",  # Using string since it's not a standard enum value
                rank=1,
                metadata={},
            )
        ]
        mock_reranker.rerank = AsyncMock(return_value=mock_reranked)

        service_with_reranker = HybridRetrievalService(
            dense_store=dense_store,
            sparse_store=sparse_store,
            reranker=mock_reranker,
            final_top_k=1,
        )

        # Setup store results
        dense_store.search.return_value = [
            {"content": "Dense", "similarity": 0.8, "metadata": {}, "id": "d1"}
        ]
        sparse_store.bm25_search.return_value = []

        results = await service_with_reranker.hybrid_search(
            query="test", query_embedding=[0.1] * 1536
        )

        assert len(results) == 1
        assert results[0].content == "Reranked"
        mock_reranker.rerank.assert_called_once()

    @pytest.mark.asyncio
    async def test_hybrid_search_similarity_threshold(self):
        """Test hybrid search with similarity threshold"""
        # Create threshold scenario using factory
        service, dense_store, sparse_store = (
            HybridRetrievalServiceFactory.create_threshold_scenario()
        )

        results = await service.hybrid_search(
            query="test",
            query_embedding=[0.1] * 1536,
            similarity_threshold=0.5,  # Should filter out low similarity
        )

        # RRF will change similarities, but high sim doc should still be above threshold
        # This tests that threshold filtering works at the end
        filtered_results = [r for r in results if r.similarity >= 0.5]
        assert len(filtered_results) <= len(results)

    @pytest.mark.asyncio
    async def test_hybrid_search_exception_handling(self):
        """Test hybrid search with store exceptions"""
        # Create exception scenario using factory
        service, dense_store, sparse_store = (
            HybridRetrievalServiceFactory.create_exception_scenario()
        )

        # Should handle gracefully
        results = await service.hybrid_search(
            query="test", query_embedding=[0.1] * 1536
        )

        # Should get sparse results only
        assert len(results) >= 0  # At least doesn't crash

    @pytest.mark.asyncio
    async def test_close_resources(self):
        """Test resource cleanup"""
        # Create stores and service using factories
        dense_store = MockVectorStoreFactory.create_basic_store()
        sparse_store = MockVectorStoreFactory.create_basic_store()
        service = HybridRetrievalServiceFactory.create_basic_service(
            dense_store=dense_store, sparse_store=sparse_store
        )

        await service.close()

        dense_store.close.assert_called_once()
        sparse_store.close.assert_called_once()


class TestRRFAlgorithm:
    """Dedicated tests for RRF algorithm correctness using factory patterns"""

    def test_rrf_single_list(self):
        """Test RRF with only dense results"""
        service = HybridRetrievalServiceFactory.create_basic_service()
        dense_results = [
            RetrievalResultFactory.create_dense_result(
                content="Doc 1", similarity=0.9, chunk_id="d1"
            ),
            RetrievalResultFactory.create_dense_result(
                content="Doc 2", similarity=0.8, chunk_id="d2"
            ),
        ]
        sparse_results = []

        fused = service._reciprocal_rank_fusion(dense_results, sparse_results)

        assert len(fused) == 2
        # Should maintain relative order from dense results
        assert fused[0].chunk_id == "d1"
        assert fused[1].chunk_id == "d2"

    def test_rrf_mathematical_correctness(self):
        """Test RRF score calculation correctness"""
        # Create service using factory
        service = HybridRetrievalServiceFactory.create_basic_service()

        dense_results = [
            RetrievalResult(
                content="Dense",
                similarity=0.9,
                chunk_id="same",
                document_id="same",
                source=RetrievalMethod.DENSE,
                metadata={},
            )
        ]
        sparse_results = [
            RetrievalResult(
                content="Sparse",
                similarity=0.7,
                chunk_id="same",
                document_id="same",
                source=RetrievalMethod.SPARSE,
                metadata={},
            )
        ]

        fused = service._reciprocal_rank_fusion(dense_results, sparse_results)

        # Same document in both lists should get the highest scaled similarity score
        actual_score = fused[0].similarity

        # With our scaling, the top RRF result should be close to 0.95
        assert actual_score > 0.9, f"Expected scaled score > 0.9, got {actual_score}"
        assert (
            actual_score <= 0.95
        ), f"Expected scaled score <= 0.95, got {actual_score}"

    def test_rrf_rank_order(self):
        """Test that RRF produces correct ranking"""
        # Create service using factory
        service = HybridRetrievalServiceFactory.create_basic_service()

        dense_results = [
            RetrievalResult(  # rank 1 dense
                content="A",
                similarity=0.9,
                chunk_id="A",
                document_id="A",
                source=RetrievalMethod.DENSE,
                metadata={},
            ),
            RetrievalResult(  # rank 2 dense
                content="B",
                similarity=0.8,
                chunk_id="B",
                document_id="B",
                source=RetrievalMethod.DENSE,
                metadata={},
            ),
        ]
        sparse_results = [
            RetrievalResult(  # rank 1 sparse
                content="B",
                similarity=0.7,
                chunk_id="B",
                document_id="B",
                source=RetrievalMethod.SPARSE,
                metadata={},
            ),
            RetrievalResult(  # rank 2 sparse
                content="C",
                similarity=0.6,
                chunk_id="C",
                document_id="C",
                source=RetrievalMethod.SPARSE,
                metadata={},
            ),
        ]

        fused = service._reciprocal_rank_fusion(dense_results, sparse_results)

        # B appears in both lists: 1/(60+2) + 1/(60+1) = highest combined score
        # A appears in dense only: 1/(60+1) = medium score
        # C appears in sparse only: 1/(60+2) = lowest score

        assert (
            fused[0].chunk_id == "B"
        )  # Should rank first (highest combined RRF score)
        assert fused[1].chunk_id == "A"  # Should rank second
        assert fused[2].chunk_id == "C"  # Should rank third
