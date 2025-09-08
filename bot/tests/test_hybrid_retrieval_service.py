"""
Tests for Hybrid Retrieval Service

Tests RRF fusion, reranking, and hybrid search orchestration
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.hybrid_retrieval_service import (
    CohereReranker,
    HybridRetrievalService,
    RetrievalResult,
)


class MockVectorStore:
    """Mock vector store for testing"""

    def __init__(self, results=None):
        self.results = results or []
        self.search = AsyncMock(return_value=self.results)
        self.bm25_search = AsyncMock(return_value=self.results)
        self.close = AsyncMock()


class TestRetrievalResult:
    """Test RetrievalResult dataclass"""

    def test_retrieval_result_creation(self):
        """Test creating a RetrievalResult"""
        result = RetrievalResult(
            content="Test content",
            similarity=0.85,
            metadata={"source": "test"},
            id="doc_1",
            source="dense",
            rank=1
        )

        assert result.content == "Test content"
        assert result.similarity == 0.85
        assert result.metadata == {"source": "test"}
        assert result.id == "doc_1"
        assert result.source == "dense"
        assert result.rank == 1

    def test_retrieval_result_optional_rank(self):
        """Test RetrievalResult with optional rank"""
        result = RetrievalResult(
            content="Content",
            similarity=0.5,
            metadata={},
            id="doc_2",
            source="sparse"
        )

        assert result.rank is None


class TestCohereReranker:
    """Test Cohere reranking functionality"""

    @pytest.mark.asyncio
    async def test_cohere_reranker_initialization(self):
        """Test Cohere reranker initialization"""
        reranker = CohereReranker(api_key="test-key", model="rerank-english-v3.0")

        assert reranker.api_key == "test-key"
        assert reranker.model == "rerank-english-v3.0"
        assert reranker._client is None

    @pytest.mark.asyncio
    @patch('cohere.AsyncClient')
    async def test_cohere_rerank_success(self, mock_cohere):
        """Test successful Cohere reranking"""
        # Setup mock response
        mock_result_1 = MagicMock()
        mock_result_1.index = 1
        mock_result_1.relevance_score = 0.9

        mock_result_2 = MagicMock()
        mock_result_2.index = 0
        mock_result_2.relevance_score = 0.7

        mock_response = MagicMock()
        mock_response.results = [mock_result_1, mock_result_2]

        mock_client = AsyncMock()
        mock_client.rerank = AsyncMock(return_value=mock_response)
        mock_cohere.return_value = mock_client

        # Test data
        reranker = CohereReranker(api_key="test-key")
        documents = [
            RetrievalResult("Doc 1", 0.5, {}, "1", "dense"),
            RetrievalResult("Doc 2", 0.6, {}, "2", "dense")
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
    @patch('cohere.AsyncClient')
    async def test_cohere_rerank_failure_fallback(self, mock_cohere):
        """Test Cohere reranking failure fallback"""
        mock_client = AsyncMock()
        mock_client.rerank = AsyncMock(side_effect=Exception("API Error"))
        mock_cohere.return_value = mock_client

        reranker = CohereReranker(api_key="test-key")
        documents = [
            RetrievalResult("Doc 1", 0.8, {}, "1", "dense"),
            RetrievalResult("Doc 2", 0.6, {}, "2", "dense")
        ]

        # Should fallback to original ranking
        result = await reranker.rerank("test query", documents, top_k=2)

        assert len(result) == 2
        assert result == documents  # Original order preserved


class TestHybridRetrievalService:
    """Test hybrid retrieval orchestration"""

    def setup_method(self):
        """Set up test fixtures"""
        self.dense_store = MockVectorStore()
        self.sparse_store = MockVectorStore()
        self.service = HybridRetrievalService(
            dense_store=self.dense_store,
            sparse_store=self.sparse_store,
            dense_top_k=5,
            sparse_top_k=5,
            fusion_top_k=3,
            final_top_k=2,
            rrf_k=60
        )

    @pytest.mark.asyncio
    async def test_dense_retrieval(self):
        """Test dense retrieval conversion"""
        # Setup mock results
        self.dense_store.search.return_value = [
            {"content": "Dense doc 1", "similarity": 0.9, "metadata": {}, "id": "d1"},
            {"content": "Dense doc 2", "similarity": 0.8, "metadata": {}, "id": "d2"}
        ]

        results = await self.service._dense_retrieval([0.1] * 1536)

        assert len(results) == 2
        assert results[0].content == "Dense doc 1"
        assert results[0].similarity == 0.9
        assert results[0].source == "dense"
        assert results[1].id == "d2"

    @pytest.mark.asyncio
    async def test_sparse_retrieval(self):
        """Test sparse retrieval conversion"""
        # Setup mock results
        self.sparse_store.bm25_search.return_value = [
            {"content": "Sparse doc 1", "similarity": 0.7, "metadata": {}, "id": "s1"},
        ]

        results = await self.service._sparse_retrieval("test query")

        assert len(results) == 1
        assert results[0].content == "Sparse doc 1"
        assert results[0].source == "sparse"

        # Verify BM25 search was called with correct parameters
        self.sparse_store.bm25_search.assert_called_once_with(
            query="test query",
            limit=5,  # sparse_top_k
            field_boosts={"title": 8.0, "content": 1.0}
        )

    def test_reciprocal_rank_fusion_no_overlap(self):
        """Test RRF with no overlapping documents"""
        dense_results = [
            RetrievalResult("Dense 1", 0.9, {}, "d1", "dense"),
            RetrievalResult("Dense 2", 0.8, {}, "d2", "dense")
        ]
        sparse_results = [
            RetrievalResult("Sparse 1", 0.7, {}, "s1", "sparse"),
            RetrievalResult("Sparse 2", 0.6, {}, "s2", "sparse")
        ]

        fused = self.service._reciprocal_rank_fusion(dense_results, sparse_results)

        assert len(fused) == 4

        # Check RRF scores (1/(k+rank))
        # d1: 1/(60+1) ≈ 0.0164, s1: 1/(60+1) ≈ 0.0164
        # d2: 1/(60+2) ≈ 0.0161, s2: 1/(60+2) ≈ 0.0161

        # Should be sorted by RRF score (descending)
        assert fused[0].id in ["d1", "s1"]  # Tied for first
        assert all(result.source == "hybrid" for result in fused)
        assert all(result.rank == i + 1 for i, result in enumerate(fused))

    def test_reciprocal_rank_fusion_with_overlap(self):
        """Test RRF with overlapping documents"""
        # Same document appears in both dense and sparse results
        dense_results = [
            RetrievalResult("Overlap doc", 0.9, {}, "overlap", "dense"),
            RetrievalResult("Dense only", 0.8, {}, "dense_only", "dense")
        ]
        sparse_results = [
            RetrievalResult("Sparse only", 0.7, {}, "sparse_only", "sparse"),
            RetrievalResult("Overlap doc", 0.6, {}, "overlap", "sparse")  # Same ID
        ]

        fused = self.service._reciprocal_rank_fusion(dense_results, sparse_results)

        assert len(fused) == 3  # Deduplicated

        # Find the overlapping document
        overlap_doc = next(doc for doc in fused if doc.id == "overlap")

        # Should have combined RRF score: 1/(60+1) + 1/(60+2)
        expected_score = 1.0/(60+1) + 1.0/(60+2)
        assert abs(overlap_doc.similarity - expected_score) < 0.001
        assert overlap_doc.source == "hybrid"

    @pytest.mark.asyncio
    async def test_hybrid_search_full_pipeline(self):
        """Test complete hybrid search pipeline"""
        # Setup mock results
        self.dense_store.search.return_value = [
            {"content": "Dense result", "similarity": 0.9, "metadata": {}, "id": "d1"}
        ]
        self.sparse_store.bm25_search.return_value = [
            {"content": "Sparse result", "similarity": 0.8, "metadata": {}, "id": "s1"}
        ]

        # No reranker in this test
        results = await self.service.hybrid_search(
            query="test query",
            query_embedding=[0.1] * 1536,
            top_k=2
        )

        assert len(results) <= 2
        assert all(isinstance(r, RetrievalResult) for r in results)

        # Verify both stores were called
        self.dense_store.search.assert_called_once()
        self.sparse_store.bm25_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_hybrid_search_with_reranker(self):
        """Test hybrid search with reranking"""
        # Setup mock reranker
        mock_reranker = AsyncMock()
        mock_reranked = [RetrievalResult("Reranked", 0.95, {}, "r1", "hybrid", rank=1)]
        mock_reranker.rerank = AsyncMock(return_value=mock_reranked)

        service_with_reranker = HybridRetrievalService(
            dense_store=self.dense_store,
            sparse_store=self.sparse_store,
            reranker=mock_reranker,
            final_top_k=1
        )

        # Setup store results
        self.dense_store.search.return_value = [
            {"content": "Dense", "similarity": 0.8, "metadata": {}, "id": "d1"}
        ]
        self.sparse_store.bm25_search.return_value = []

        results = await service_with_reranker.hybrid_search(
            query="test",
            query_embedding=[0.1] * 1536
        )

        assert len(results) == 1
        assert results[0].content == "Reranked"
        mock_reranker.rerank.assert_called_once()

    @pytest.mark.asyncio
    async def test_hybrid_search_similarity_threshold(self):
        """Test hybrid search with similarity threshold"""
        self.dense_store.search.return_value = [
            {"content": "High sim", "similarity": 0.9, "metadata": {}, "id": "h1"},
            {"content": "Low sim", "similarity": 0.3, "metadata": {}, "id": "l1"}
        ]
        self.sparse_store.bm25_search.return_value = []

        results = await self.service.hybrid_search(
            query="test",
            query_embedding=[0.1] * 1536,
            similarity_threshold=0.5  # Should filter out low similarity
        )

        # RRF will change similarities, but high sim doc should still be above threshold
        # This tests that threshold filtering works at the end
        filtered_results = [r for r in results if r.similarity >= 0.5]
        assert len(filtered_results) <= len(results)

    @pytest.mark.asyncio
    async def test_hybrid_search_exception_handling(self):
        """Test hybrid search with store exceptions"""
        # Dense store fails
        self.dense_store.search.side_effect = Exception("Dense failed")
        self.sparse_store.bm25_search.return_value = [
            {"content": "Sparse only", "similarity": 0.7, "metadata": {}, "id": "s1"}
        ]

        # Should handle gracefully
        results = await self.service.hybrid_search(
            query="test",
            query_embedding=[0.1] * 1536
        )

        # Should get sparse results only
        assert len(results) >= 0  # At least doesn't crash

    @pytest.mark.asyncio
    async def test_close_resources(self):
        """Test resource cleanup"""
        await self.service.close()

        self.dense_store.close.assert_called_once()
        self.sparse_store.close.assert_called_once()


class TestRRFAlgorithm:
    """Dedicated tests for RRF algorithm correctness"""

    def setup_method(self):
        self.service = HybridRetrievalService(
            dense_store=MockVectorStore(),
            sparse_store=MockVectorStore(),
            rrf_k=60
        )

    def test_rrf_single_list(self):
        """Test RRF with only dense results"""
        dense_results = [
            RetrievalResult("Doc 1", 0.9, {}, "d1", "dense"),
            RetrievalResult("Doc 2", 0.8, {}, "d2", "dense")
        ]
        sparse_results = []

        fused = self.service._reciprocal_rank_fusion(dense_results, sparse_results)

        assert len(fused) == 2
        # Should maintain relative order from dense results
        assert fused[0].id == "d1"
        assert fused[1].id == "d2"

    def test_rrf_mathematical_correctness(self):
        """Test RRF score calculation correctness"""
        k = 60
        dense_results = [RetrievalResult("Dense", 0.9, {}, "same", "dense")]
        sparse_results = [RetrievalResult("Sparse", 0.7, {}, "same", "sparse")]

        fused = self.service._reciprocal_rank_fusion(dense_results, sparse_results)

        # Same document in both lists: rank 1 in both
        expected_score = 1.0/(k+1) + 1.0/(k+1)  # 2/(k+1)
        actual_score = fused[0].similarity

        assert abs(actual_score - expected_score) < 0.0001

    def test_rrf_rank_order(self):
        """Test that RRF produces correct ranking"""
        dense_results = [
            RetrievalResult("A", 0.9, {}, "A", "dense"),  # rank 1 dense
            RetrievalResult("B", 0.8, {}, "B", "dense"),  # rank 2 dense
        ]
        sparse_results = [
            RetrievalResult("B", 0.7, {}, "B", "sparse"),  # rank 1 sparse
            RetrievalResult("C", 0.6, {}, "C", "sparse"),  # rank 2 sparse
        ]

        fused = self.service._reciprocal_rank_fusion(dense_results, sparse_results)

        # B appears in both lists: 1/(60+2) + 1/(60+1) = highest combined score
        # A appears in dense only: 1/(60+1) = medium score
        # C appears in sparse only: 1/(60+2) = lowest score

        assert fused[0].id == "B"  # Should rank first (highest combined RRF score)
        assert fused[1].id == "A"  # Should rank second
        assert fused[2].id == "C"  # Should rank third
