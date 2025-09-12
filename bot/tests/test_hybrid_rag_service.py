"""
Tests for HybridRAGService functionality.

Tests complete hybrid RAG pipeline with dual indexing, title injection,
hybrid retrieval, and response generation.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import SecretStr

from bot.services.hybrid_rag_service import HybridRAGService, create_hybrid_rag_service
from config.settings import (
    EmbeddingSettings,
    HybridSettings,
    LLMSettings,
    Settings,
    VectorSettings,
)


class TestHybridRAGService:
    """Test cases for HybridRAGService"""

    @pytest.fixture
    def settings(self):
        """Create settings for testing"""
        return Settings(
            vector=VectorSettings(
                provider="pinecone",
                api_key=SecretStr("test-key"),
                collection_name="test-collection",
                environment="test-env",
                url="http://localhost:9200",
            ),
            hybrid=HybridSettings(
                enabled=True,
                dense_top_k=10,
                sparse_top_k=10,
                fusion_top_k=15,
                final_top_k=5,
                rrf_k=60,
                reranker_enabled=True,
                reranker_provider="cohere",
                reranker_api_key=SecretStr("cohere-key"),
                reranker_model="rerank-english-v2.0",
            ),
            embedding=EmbeddingSettings(
                provider="openai",
                model="text-embedding-ada-002",
                api_key=SecretStr("openai-key"),
            ),
            llm=LLMSettings(
                provider="openai", api_key=SecretStr("openai-key"), model="gpt-4"
            ),
        )

    @pytest.fixture
    def hybrid_rag_service(self, settings):
        """Create HybridRAGService instance for testing"""
        return HybridRAGService(settings)

    def test_init(self, hybrid_rag_service, settings):
        """Test service initialization"""
        assert hybrid_rag_service.settings == settings
        assert hybrid_rag_service.vector_settings == settings.vector
        assert hybrid_rag_service.hybrid_settings == settings.hybrid
        assert hybrid_rag_service._initialized is False
        assert hybrid_rag_service.dense_store is None
        assert hybrid_rag_service.sparse_store is None

    @pytest.mark.asyncio
    async def test_initialize_success(self, hybrid_rag_service):
        """Test successful initialization of all components"""
        # Mock all dependencies
        with (
            patch(
                "bot.services.hybrid_rag_service.create_embedding_provider"
            ) as mock_embedding,
            patch("bot.services.hybrid_rag_service.create_llm_provider") as mock_llm,
            patch(
                "bot.services.hybrid_rag_service.TitleInjectionService"
            ) as mock_title,
            patch(
                "bot.services.hybrid_rag_service.EnhancedChunkProcessor"
            ) as mock_processor,
            patch(
                "bot.services.hybrid_rag_service.create_vector_store"
            ) as mock_vector_store,
            patch("bot.services.hybrid_rag_service.CohereReranker") as mock_reranker,
            patch(
                "bot.services.hybrid_rag_service.HybridRetrievalService"
            ) as mock_hybrid_retrieval,
        ):
            # Setup mocks
            mock_embedding.return_value = Mock()
            mock_llm.return_value = Mock()
            mock_title_instance = Mock()
            mock_title.return_value = mock_title_instance
            mock_processor.return_value = Mock()

            mock_dense_store = AsyncMock()
            mock_sparse_store = AsyncMock()
            mock_vector_store.side_effect = [mock_dense_store, mock_sparse_store]

            mock_reranker_instance = Mock()
            mock_reranker.return_value = mock_reranker_instance

            mock_hybrid_retrieval.return_value = Mock()

            await hybrid_rag_service.initialize()

            # Verify initialization
            assert hybrid_rag_service._initialized is True
            assert hybrid_rag_service.embedding_service is not None
            assert hybrid_rag_service.llm_provider is not None
            assert hybrid_rag_service.dense_store == mock_dense_store
            assert hybrid_rag_service.sparse_store == mock_sparse_store
            assert hybrid_rag_service.hybrid_retrieval is not None

            # Verify store initialization was called
            mock_dense_store.initialize.assert_called_once()
            mock_sparse_store.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_without_reranker_api_key(self, settings):
        """Test initialization without reranker API key"""
        settings.hybrid.reranker_api_key = None
        service = HybridRAGService(settings)

        with (
            patch(
                "bot.services.hybrid_rag_service.create_embedding_provider"
            ) as mock_embedding,
            patch("bot.services.hybrid_rag_service.create_llm_provider") as mock_llm,
            patch("bot.services.hybrid_rag_service.TitleInjectionService"),
            patch("bot.services.hybrid_rag_service.EnhancedChunkProcessor"),
            patch(
                "bot.services.hybrid_rag_service.create_vector_store"
            ) as mock_vector_store,
            patch(
                "bot.services.hybrid_rag_service.HybridRetrievalService"
            ) as mock_hybrid_retrieval,
        ):
            mock_embedding.return_value = Mock()
            mock_llm.return_value = Mock()
            mock_dense_store = AsyncMock()
            mock_sparse_store = AsyncMock()
            mock_vector_store.side_effect = [mock_dense_store, mock_sparse_store]

            await service.initialize()

            # Verify reranker was passed as None to HybridRetrievalService
            mock_hybrid_retrieval.assert_called_once()
            call_kwargs = mock_hybrid_retrieval.call_args[1]
            assert call_kwargs["reranker"] is None

    @pytest.mark.asyncio
    async def test_initialize_failure(self, hybrid_rag_service):
        """Test initialization failure handling"""
        with patch(
            "bot.services.hybrid_rag_service.create_embedding_provider",
            side_effect=Exception("Init failed"),
        ):
            with pytest.raises(Exception, match="Init failed"):
                await hybrid_rag_service.initialize()

            assert hybrid_rag_service._initialized is False

    @pytest.mark.asyncio
    async def test_ingest_documents_not_initialized(self, hybrid_rag_service):
        """Test document ingestion when service not initialized"""
        with pytest.raises(RuntimeError, match="HybridRAGService not initialized"):
            await hybrid_rag_service.ingest_documents(
                ["text"], [[0.1, 0.2]], [{"key": "value"}]
            )

    @pytest.mark.asyncio
    async def test_ingest_documents_success(self, hybrid_rag_service):
        """Test successful document ingestion"""
        # Initialize service
        hybrid_rag_service._initialized = True
        hybrid_rag_service.chunk_processor = Mock()
        hybrid_rag_service.dense_store = AsyncMock()
        hybrid_rag_service.sparse_store = AsyncMock()

        # Mock chunk processor output
        mock_dual_docs = {
            "dense": [{"content": "dense content", "metadata": {"key": "value"}}],
            "sparse": [
                {
                    "content": "sparse content",
                    "title": "test title",
                    "metadata": {"key": "value"},
                }
            ],
        }
        hybrid_rag_service.chunk_processor.prepare_for_dual_indexing.return_value = (
            mock_dual_docs
        )

        # Mock store operations
        hybrid_rag_service.dense_store.add_documents.return_value = AsyncMock()
        hybrid_rag_service.sparse_store.add_documents.return_value = AsyncMock()

        texts = ["test document"]
        embeddings = [[0.1, 0.2, 0.3]]
        metadata = [{"file_name": "test.pdf"}]

        result = await hybrid_rag_service.ingest_documents(texts, embeddings, metadata)

        assert result is True
        hybrid_rag_service.chunk_processor.prepare_for_dual_indexing.assert_called_once()
        hybrid_rag_service.dense_store.add_documents.assert_called_once()
        hybrid_rag_service.sparse_store.add_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_ingest_documents_failure(self, hybrid_rag_service):
        """Test document ingestion failure handling"""
        hybrid_rag_service._initialized = True
        hybrid_rag_service.chunk_processor = Mock()
        hybrid_rag_service.chunk_processor.prepare_for_dual_indexing.side_effect = (
            Exception("Processing failed")
        )

        result = await hybrid_rag_service.ingest_documents(
            ["text"], [[0.1]], [{"key": "value"}]
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_hybrid_search_not_initialized(self, hybrid_rag_service):
        """Test hybrid search when service not initialized"""
        with pytest.raises(RuntimeError, match="HybridRAGService not initialized"):
            await hybrid_rag_service.hybrid_search("query", [0.1, 0.2])

    @pytest.mark.asyncio
    async def test_hybrid_search_disabled(self, settings):
        """Test hybrid search when hybrid is disabled"""
        settings.hybrid.enabled = False
        service = HybridRAGService(settings)
        service._initialized = True
        service.dense_store = AsyncMock()

        # Mock dense store search
        expected_results = [{"content": "result", "similarity": 0.8}]
        service.dense_store.search.return_value = expected_results

        results = await service.hybrid_search("query", [0.1, 0.2], top_k=5)

        assert results == expected_results
        service.dense_store.search.assert_called_once_with(
            query_embedding=[0.1, 0.2], limit=5, similarity_threshold=0.0
        )

    @pytest.mark.asyncio
    async def test_hybrid_search_enabled(self, hybrid_rag_service):
        """Test hybrid search when enabled"""
        hybrid_rag_service._initialized = True
        hybrid_rag_service.hybrid_retrieval = AsyncMock()

        # Mock retrieval results
        mock_result = Mock()
        mock_result.content = "test content"
        mock_result.similarity = 0.85
        mock_result.metadata = {"file_name": "test.pdf"}
        mock_result.id = "doc1"
        mock_result.source = "dense"
        mock_result.rank = 1

        hybrid_rag_service.hybrid_retrieval.hybrid_search.return_value = [mock_result]

        results = await hybrid_rag_service.hybrid_search("query", [0.1, 0.2])

        assert len(results) == 1
        assert results[0]["content"] == "test content"
        assert results[0]["similarity"] == 0.85
        assert results[0]["_hybrid_source"] == "dense"
        assert results[0]["_hybrid_rank"] == 1

    @pytest.mark.asyncio
    async def test_generate_response_not_initialized(self, hybrid_rag_service):
        """Test response generation when service not initialized"""
        with pytest.raises(RuntimeError, match="HybridRAGService not initialized"):
            await hybrid_rag_service.generate_response("query", [])

    @pytest.mark.asyncio
    async def test_generate_response_without_rag(self, hybrid_rag_service):
        """Test response generation without RAG"""
        hybrid_rag_service._initialized = True
        hybrid_rag_service.llm_provider = AsyncMock()
        hybrid_rag_service.llm_provider.get_response.return_value = (
            "Direct LLM response"
        )

        response = await hybrid_rag_service.generate_response(
            "query", [{"role": "user", "content": "previous"}], use_rag=False
        )

        assert response == "Direct LLM response"
        hybrid_rag_service.llm_provider.get_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_response_with_rag(self, hybrid_rag_service):
        """Test response generation with RAG"""
        hybrid_rag_service._initialized = True
        hybrid_rag_service.embedding_service = AsyncMock()
        hybrid_rag_service.llm_provider = AsyncMock()
        hybrid_rag_service.hybrid_retrieval = AsyncMock()

        # Mock embedding
        hybrid_rag_service.embedding_service.get_embedding.return_value = [
            0.1,
            0.2,
            0.3,
        ]

        # Mock search results
        mock_result = Mock()
        mock_result.content = "retrieved content"
        mock_result.similarity = 0.85
        mock_result.metadata = {"file_name": "test.pdf"}
        mock_result.source = "dense"
        mock_result.rank = 1
        hybrid_rag_service.hybrid_retrieval.hybrid_search.return_value = [mock_result]

        # Mock LLM response
        hybrid_rag_service.llm_provider.get_response.return_value = (
            "RAG enhanced response"
        )

        response = await hybrid_rag_service.generate_response("query", [])

        assert "RAG enhanced response" in response
        assert "**📚 Sources:**" in response  # Citations added
        assert "test.pdf" in response
        hybrid_rag_service.embedding_service.get_embedding.assert_called_once_with(
            "query"
        )

    @pytest.mark.asyncio
    async def test_generate_response_empty_llm_response(self, hybrid_rag_service):
        """Test handling of empty LLM response"""
        hybrid_rag_service._initialized = True
        hybrid_rag_service.llm_provider = AsyncMock()
        hybrid_rag_service.llm_provider.get_response.return_value = ""

        response = await hybrid_rag_service.generate_response(
            "query", [], use_rag=False
        )

        assert response == "I'm sorry, I couldn't generate a response right now."

    @pytest.mark.asyncio
    async def test_generate_response_error_handling(self, hybrid_rag_service):
        """Test error handling in response generation"""
        hybrid_rag_service._initialized = True
        hybrid_rag_service.llm_provider = AsyncMock()
        hybrid_rag_service.llm_provider.get_response.side_effect = Exception(
            "LLM error"
        )

        response = await hybrid_rag_service.generate_response(
            "query", [], use_rag=False
        )

        assert (
            response == "I'm sorry, I encountered an error while generating a response."
        )

    def test_add_citations_to_response(self, hybrid_rag_service):
        """Test adding citations to response"""
        response = "This is a response."
        context_chunks = [
            {
                "content": "chunk 1",
                "similarity": 0.85,
                "metadata": {
                    "file_name": "doc1.pdf",
                    "folder_path": "/docs",
                    "web_view_link": "https://example.com",
                },
                "_hybrid_source": "dense",
            },
            {
                "content": "chunk 2",
                "similarity": 0.75,
                "metadata": {"file_name": "doc2.pdf"},
                "_hybrid_source": "sparse",
            },
        ]

        result = hybrid_rag_service._add_citations_to_response(response, context_chunks)

        assert "This is a response." in result
        assert "**📚 Sources:**" in result
        assert "doc1.pdf" in result
        assert "doc2.pdf" in result
        assert "85.0%" in result  # Similarity as percentage
        assert "Via: dense" in result
        assert "Via: sparse" in result
        assert "📁 /docs" in result
        assert "[" in result and "](https://example.com)" in result  # Web link

    def test_add_citations_empty_chunks(self, hybrid_rag_service):
        """Test adding citations with no chunks"""
        response = "This is a response."
        result = hybrid_rag_service._add_citations_to_response(response, [])
        assert result == response

    def test_add_citations_duplicate_sources(self, hybrid_rag_service):
        """Test citations with duplicate source files"""
        response = "Response"
        chunks = [
            {
                "metadata": {"file_name": "doc1.pdf"},
                "similarity": 0.8,
                "_hybrid_source": "dense",
            },
            {
                "metadata": {"file_name": "doc1.pdf"},
                "similarity": 0.7,
                "_hybrid_source": "sparse",
            },  # Duplicate
            {
                "metadata": {"file_name": "doc2.pdf"},
                "similarity": 0.6,
                "_hybrid_source": "dense",
            },
        ]

        result = hybrid_rag_service._add_citations_to_response(response, chunks)

        # Should only have 2 citations (duplicates removed)
        citations = (
            result.split("**📚 Sources:**")[1] if "**📚 Sources:**" in result else ""
        )
        assert citations.count("doc1.pdf") == 1  # Only one citation for doc1
        assert "doc2.pdf" in citations

    @pytest.mark.asyncio
    async def test_get_system_status_not_initialized(self, hybrid_rag_service):
        """Test system status when not initialized"""
        status = await hybrid_rag_service.get_system_status()

        assert status["initialized"] is False
        assert status["hybrid_enabled"] is True  # From settings
        assert status["components"] == {}

    @pytest.mark.asyncio
    async def test_get_system_status_initialized(self, hybrid_rag_service):
        """Test system status when initialized"""
        hybrid_rag_service._initialized = True

        status = await hybrid_rag_service.get_system_status()

        assert status["initialized"] is True
        assert "dense_store" in status["components"]
        assert "sparse_store" in status["components"]
        assert "reranker" in status["components"]
        assert "title_injection" in status["components"]

    @pytest.mark.asyncio
    async def test_close(self, hybrid_rag_service):
        """Test resource cleanup"""
        hybrid_rag_service.hybrid_retrieval = AsyncMock()

        await hybrid_rag_service.close()

        hybrid_rag_service.hybrid_retrieval.close.assert_called_once()


class TestCreateHybridRAGService:
    """Test cases for factory function"""

    @pytest.mark.asyncio
    async def test_create_hybrid_rag_service(self):
        """Test factory function creates and initializes service"""
        settings = Settings(
            vector=VectorSettings(
                provider="pinecone",
                api_key=SecretStr("test-key"),
                collection_name="test",
            ),
            hybrid=HybridSettings(enabled=True),
            embedding=EmbeddingSettings(
                provider="openai",
                model="text-embedding-ada-002",
                api_key=SecretStr("key"),
            ),
            llm=LLMSettings(provider="openai", api_key=SecretStr("key"), model="gpt-4"),
        )

        with patch.object(
            HybridRAGService, "initialize", new_callable=AsyncMock
        ) as mock_init:
            service = await create_hybrid_rag_service(settings)

            assert isinstance(service, HybridRAGService)
            mock_init.assert_called_once()
