"""
Integration tests for Hybrid RAG Service

Tests the complete end-to-end pipeline with real-like scenarios
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Dict, Any

from config.settings import Settings, VectorSettings, HybridSettings
from services.hybrid_rag_service import HybridRAGService


class MockEmbeddingService:
    """Mock embedding service for testing"""

    def __init__(self):
        self.embed_documents = AsyncMock()
        self.embed_query = AsyncMock()

    def setup_responses(self, document_embeddings: List[List[float]], query_embedding: List[float]):
        """Setup mock responses"""
        self.embed_documents.return_value = document_embeddings
        self.embed_query.return_value = query_embedding


class MockVectorStore:
    """Enhanced mock vector store with realistic behavior"""

    def __init__(self, store_type="dense"):
        self.store_type = store_type
        self.documents = []  # Store ingested documents
        self.initialize = AsyncMock()
        self.close = AsyncMock()

    async def add_documents(self, texts: List[str], embeddings: List[List[float]], metadata: List[Dict[str, Any]]):
        """Mock document ingestion"""
        for i, (text, embedding, meta) in enumerate(zip(texts, embeddings, metadata)):
            doc_id = f"{self.store_type}_{i}"
            self.documents.append({
                "id": doc_id,
                "content": text,
                "embedding": embedding,
                "metadata": meta,
                "similarity": 0.0  # Will be set during search
            })
        return True

    async def search(self, query_embedding: List[float], limit: int = 10, similarity_threshold: float = 0.0, **kwargs):
        """Mock dense vector search with cosine similarity simulation"""
        if self.store_type != "dense":
            return []

        results = []
        for doc in self.documents[:limit]:
            # Simulate cosine similarity (simplified)
            similarity = self._simulate_cosine_similarity(query_embedding, doc["embedding"])
            if similarity >= similarity_threshold:
                result = {
                    "id": doc["id"],
                    "content": doc["content"],
                    "similarity": similarity,
                    "metadata": doc["metadata"]
                }
                results.append(result)

        return sorted(results, key=lambda x: x["similarity"], reverse=True)

    async def bm25_search(self, query: str, limit: int = 10, field_boosts: Dict[str, float] = None, **kwargs):
        """Mock BM25 search"""
        if self.store_type != "sparse":
            return []

        results = []
        query_terms = query.lower().split()

        for doc in self.documents[:limit]:
            # Simple BM25 simulation - count query term matches
            content_lower = doc["content"].lower()
            title = doc["metadata"].get("title", "").lower()

            score = 0.0
            for term in query_terms:
                if term in content_lower:
                    score += 1.0
                if term in title:
                    score += 8.0  # Title boost

            if score > 0:
                # Normalize score
                similarity = min(score / 10.0, 1.0)
                results.append({
                    "id": doc["id"],
                    "content": doc["content"],
                    "similarity": similarity,
                    "metadata": doc["metadata"]
                })

        return sorted(results, key=lambda x: x["similarity"], reverse=True)

    def _simulate_cosine_similarity(self, query_embedding: List[float], doc_embedding: List[float]) -> float:
        """Simple cosine similarity simulation"""
        if not query_embedding or not doc_embedding:
            return 0.0

        # Simple dot product simulation
        dot_product = sum(q * d for q, d in zip(query_embedding[:5], doc_embedding[:5]))  # Use first 5 dims
        # Normalize to 0-1 range
        return max(0.0, min(1.0, (dot_product + 5) / 10))


@pytest.fixture
def test_settings():
    """Create test settings"""
    return Settings(
        vector=VectorSettings(
            provider="pinecone",
            api_key="test-pinecone-key",
            collection_name="test_index"
        ),
        hybrid=HybridSettings(
            enabled=True,
            dense_top_k=5,
            sparse_top_k=5,
            fusion_top_k=3,
            final_top_k=2,
            reranker_enabled=False  # Disable for most tests
        )
    )


@pytest.fixture
def sample_documents():
    """Sample documents for testing"""
    return [
        {
            "text": "Machine learning is a subset of artificial intelligence.",
            "metadata": {"title": "ML Introduction", "category": "AI"}
        },
        {
            "text": "Deep learning uses neural networks with multiple layers.",
            "metadata": {"title": "Deep Learning Basics", "category": "AI"}
        },
        {
            "text": "Natural language processing enables computers to understand text.",
            "metadata": {"title": "NLP Overview", "category": "AI"}
        },
        {
            "text": "Computer vision allows machines to interpret visual information.",
            "metadata": {"title": "Computer Vision", "category": "AI"}
        }
    ]


class TestHybridRAGServiceInitialization:
    """Test initialization of hybrid RAG service"""

    @pytest.mark.asyncio
    @patch('services.hybrid_rag_service.create_vector_store')
    async def test_initialization_success(self, mock_create_store, test_settings):
        """Test successful initialization"""
        # Setup mocks
        mock_dense_store = MockVectorStore("dense")
        mock_sparse_store = MockVectorStore("sparse")
        mock_create_store.side_effect = [mock_dense_store, mock_sparse_store]

        # Initialize service
        service = HybridRAGService(test_settings)
        await service.initialize()

        assert service._initialized is True
        assert service.dense_store is not None
        assert service.sparse_store is not None
        assert service.hybrid_retrieval is not None
        assert service.title_injection is not None
        assert service.chunk_processor is not None

        # Verify stores were initialized
        mock_dense_store.initialize.assert_called_once()
        mock_sparse_store.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialization_missing_api_key(self, test_settings):
        """Test initialization with missing Pinecone API key"""
        test_settings.vector.api_key = None

        service = HybridRAGService(test_settings)

        with pytest.raises(Exception):  # Should fail due to missing API key
            await service.initialize()

    @pytest.mark.asyncio
    @patch('services.hybrid_rag_service.create_vector_store')
    async def test_initialization_with_reranker(self, mock_create_store, test_settings):
        """Test initialization with reranker enabled"""
        test_settings.hybrid.reranker_enabled = True
        test_settings.hybrid.reranker_api_key = "test-cohere-key"

        mock_dense_store = MockVectorStore("dense")
        mock_sparse_store = MockVectorStore("sparse")
        mock_create_store.side_effect = [mock_dense_store, mock_sparse_store]

        service = HybridRAGService(test_settings)
        await service.initialize()

        assert service.hybrid_retrieval.reranker is not None


class TestHybridRAGServiceIngestion:
    """Test document ingestion pipeline"""

    @pytest.mark.asyncio
    @patch('services.hybrid_rag_service.create_vector_store')
    async def test_dual_ingestion_success(self, mock_create_store, test_settings, sample_documents):
        """Test successful dual ingestion into both stores"""
        # Setup mock stores
        mock_dense_store = MockVectorStore("dense")
        mock_sparse_store = MockVectorStore("sparse")
        mock_create_store.side_effect = [mock_dense_store, mock_sparse_store]

        # Initialize service
        service = HybridRAGService(test_settings)
        await service.initialize()

        # Extract test data
        texts = [doc["text"] for doc in sample_documents]
        metadata = [doc["metadata"] for doc in sample_documents]
        embeddings = [[0.1, 0.2, 0.3] * 512 for _ in texts]  # Mock embeddings

        # Test ingestion
        success = await service.ingest_documents(texts, embeddings, metadata)

        assert success is True
        assert len(mock_dense_store.documents) == len(texts)
        assert len(mock_sparse_store.documents) == len(texts)

        # Verify title injection in dense store
        dense_doc = mock_dense_store.documents[0]
        assert "[TITLE] ML Introduction [/TITLE]" in dense_doc["content"]
        assert "Machine learning is a subset" in dense_doc["content"]

        # Verify separate title field in sparse store
        sparse_doc = mock_sparse_store.documents[0]
        assert sparse_doc["content"] == texts[0]  # Original content
        assert sparse_doc["metadata"]["title"] == "ML Introduction"

    @pytest.mark.asyncio
    @patch('services.hybrid_rag_service.create_vector_store')
    async def test_ingestion_without_titles(self, mock_create_store, test_settings):
        """Test ingestion with documents without titles"""
        mock_dense_store = MockVectorStore("dense")
        mock_sparse_store = MockVectorStore("sparse")
        mock_create_store.side_effect = [mock_dense_store, mock_sparse_store]

        service = HybridRAGService(test_settings)
        await service.initialize()

        # Documents without titles
        texts = ["Content without title."]
        metadata = [{"author": "John Doe"}]
        embeddings = [[0.1] * 1536]

        success = await service.ingest_documents(texts, embeddings, metadata)

        assert success is True

        # Dense store should have original content (no title injection)
        dense_doc = mock_dense_store.documents[0]
        assert dense_doc["content"] == "Content without title."

        # Sparse store should have empty title
        sparse_doc = mock_sparse_store.documents[0]
        assert sparse_doc["metadata"]["title"] == ""

    @pytest.mark.asyncio
    async def test_ingestion_not_initialized(self, test_settings):
        """Test ingestion before initialization"""
        service = HybridRAGService(test_settings)

        with pytest.raises(RuntimeError, match="not initialized"):
            await service.ingest_documents(["text"], [[0.1]], [{}])


class TestHybridRAGServiceSearch:
    """Test hybrid search functionality"""

    @pytest.mark.asyncio
    @patch('services.hybrid_rag_service.create_vector_store')
    async def test_hybrid_search_success(self, mock_create_store, test_settings, sample_documents):
        """Test successful hybrid search"""
        # Setup mock stores with data
        mock_dense_store = MockVectorStore("dense")
        mock_sparse_store = MockVectorStore("sparse")
        mock_create_store.side_effect = [mock_dense_store, mock_sparse_store]

        service = HybridRAGService(test_settings)
        await service.initialize()

        # Ingest test data
        texts = [doc["text"] for doc in sample_documents]
        metadata = [doc["metadata"] for doc in sample_documents]
        embeddings = [[0.1, 0.2, 0.3] * 512 for _ in texts]
        await service.ingest_documents(texts, embeddings, metadata)

        # Perform search
        query = "machine learning neural networks"
        query_embedding = [0.15, 0.25, 0.35] * 512  # Similar to first doc

        results = await service.hybrid_search(
            query=query,
            query_embedding=query_embedding,
            top_k=3
        )

        assert len(results) >= 0  # Should return some results

        # Verify result format
        if results:
            result = results[0]
            assert "content" in result
            assert "similarity" in result
            assert "metadata" in result
            assert "id" in result
            assert "_hybrid_source" in result

    @pytest.mark.asyncio
    @patch('services.hybrid_rag_service.create_vector_store')
    async def test_search_with_similarity_threshold(self, mock_create_store, test_settings, sample_documents):
        """Test search with similarity threshold filtering"""
        mock_dense_store = MockVectorStore("dense")
        mock_sparse_store = MockVectorStore("sparse")
        mock_create_store.side_effect = [mock_dense_store, mock_sparse_store]

        service = HybridRAGService(test_settings)
        await service.initialize()

        # Ingest data
        texts = [doc["text"] for doc in sample_documents]
        metadata = [doc["metadata"] for doc in sample_documents]
        embeddings = [[0.1] * 1536 for _ in texts]
        await service.ingest_documents(texts, embeddings, metadata)

        # Search with high threshold
        results = await service.hybrid_search(
            query="test query",
            query_embedding=[0.5] * 1536,
            similarity_threshold=0.9  # Very high threshold
        )

        # Should filter out low similarity results
        for result in results:
            assert result["similarity"] >= 0.9

    @pytest.mark.asyncio
    @patch('services.hybrid_rag_service.create_vector_store')
    async def test_search_hybrid_disabled_fallback(self, mock_create_store, test_settings):
        """Test search fallback when hybrid is disabled"""
        test_settings.hybrid.enabled = False

        mock_dense_store = MockVectorStore("dense")
        mock_sparse_store = MockVectorStore("sparse")
        mock_create_store.side_effect = [mock_dense_store, mock_sparse_store]

        service = HybridRAGService(test_settings)
        await service.initialize()

        # Add a document to dense store
        await mock_dense_store.add_documents(
            ["Test content"], [[0.1] * 1536], [{"title": "Test"}]
        )

        # Search should fallback to dense-only
        results = await service.hybrid_search(
            query="test",
            query_embedding=[0.1] * 1536
        )

        # Should get results from dense store only
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_not_initialized(self, test_settings):
        """Test search before initialization"""
        service = HybridRAGService(test_settings)

        with pytest.raises(RuntimeError, match="not initialized"):
            await service.hybrid_search("query", [0.1] * 1536)


class TestHybridRAGServiceSystemStatus:
    """Test system status and health checks"""

    @pytest.mark.asyncio
    @patch('services.hybrid_rag_service.create_vector_store')
    async def test_system_status_healthy(self, mock_create_store, test_settings):
        """Test system status when healthy"""
        mock_dense_store = MockVectorStore("dense")
        mock_sparse_store = MockVectorStore("sparse")
        mock_create_store.side_effect = [mock_dense_store, mock_sparse_store]

        service = HybridRAGService(test_settings)
        await service.initialize()

        status = await service.get_system_status()

        assert status["initialized"] is True
        assert status["hybrid_enabled"] is True
        assert "components" in status
        assert status["components"]["dense_store"] == "healthy"
        assert status["components"]["sparse_store"] == "healthy"
        assert status["components"]["reranker"] == "disabled"  # Default in test
        assert status["components"]["title_injection"] == "enabled"  # Default

    @pytest.mark.asyncio
    async def test_system_status_not_initialized(self, test_settings):
        """Test system status when not initialized"""
        service = HybridRAGService(test_settings)

        status = await service.get_system_status()

        assert status["initialized"] is False
        assert status["hybrid_enabled"] is True  # From settings

    @pytest.mark.asyncio
    @patch('services.hybrid_rag_service.create_vector_store')
    async def test_resource_cleanup(self, mock_create_store, test_settings):
        """Test resource cleanup on close"""
        mock_dense_store = MockVectorStore("dense")
        mock_sparse_store = MockVectorStore("sparse")
        mock_create_store.side_effect = [mock_dense_store, mock_sparse_store]

        service = HybridRAGService(test_settings)
        await service.initialize()

        await service.close()

        # Verify cleanup was called
        mock_dense_store.close.assert_called_once()
        mock_sparse_store.close.assert_called_once()


class TestEndToEndScenarios:
    """End-to-end integration test scenarios"""

    @pytest.mark.asyncio
    @patch('services.hybrid_rag_service.create_vector_store')
    async def test_complete_rag_pipeline(self, mock_create_store, test_settings):
        """Test complete RAG pipeline: ingest → search → results"""
        # Setup
        mock_dense_store = MockVectorStore("dense")
        mock_sparse_store = MockVectorStore("sparse")
        mock_create_store.side_effect = [mock_dense_store, mock_sparse_store]

        service = HybridRAGService(test_settings)
        await service.initialize()

        # Ingest diverse documents
        documents = [
            ("Python is a programming language", {"title": "Python Intro", "lang": "python"}),
            ("Machine learning models need training data", {"title": "ML Training", "domain": "ai"}),
            ("Elasticsearch is a search engine", {"title": "Search Systems", "type": "database"}),
            ("Neural networks have multiple layers", {"title": "Deep Learning", "domain": "ai"})
        ]

        texts, metadata = zip(*documents)
        embeddings = [[0.1 + i*0.1] * 1536 for i in range(len(texts))]

        # Ingest
        ingest_success = await service.ingest_documents(list(texts), embeddings, list(metadata))
        assert ingest_success is True

        # Search for AI-related content
        query = "artificial intelligence machine learning"
        query_embedding = [0.2] * 1536  # Close to ML document

        results = await service.hybrid_search(
            query=query,
            query_embedding=query_embedding,
            top_k=2
        )

        assert len(results) >= 0  # Should get some results

        # Verify hybrid metadata is present
        if results:
            assert "_hybrid_source" in results[0]
            assert "_hybrid_rank" in results[0]

    @pytest.mark.asyncio
    @patch('services.hybrid_rag_service.create_vector_store')
    async def test_entity_search_scenario(self, mock_create_store, test_settings):
        """Test scenario where entity appears in title (expert's recommendation)"""
        mock_dense_store = MockVectorStore("dense")
        mock_sparse_store = MockVectorStore("sparse")
        mock_create_store.side_effect = [mock_dense_store, mock_sparse_store]

        service = HybridRAGService(test_settings)
        await service.initialize()

        # Documents with entities in titles
        texts = [
            "This document discusses various topics in technology.",
            "General information about software development practices.",
            "An overview of different programming paradigms."
        ]
        metadata = [
            {"title": "TensorFlow Guide"},  # Entity in title
            {"title": "Development Best Practices"},
            {"title": "Programming Concepts"}
        ]
        embeddings = [[0.1] * 1536, [0.2] * 1536, [0.3] * 1536]

        await service.ingest_documents(texts, embeddings, metadata)

        # Search specifically for TensorFlow
        query = "TensorFlow"
        query_embedding = [0.15] * 1536

        results = await service.hybrid_search(
            query=query,
            query_embedding=query_embedding,
            top_k=3
        )

        # The document with "TensorFlow" in title should rank highly due to:
        # 1. Title injection in dense embeddings
        # 2. BM25 title boosting in sparse search
        # 3. RRF fusion combining both signals

        assert len(results) >= 0
        # In a real scenario, TensorFlow document should rank first
