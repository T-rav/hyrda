"""
Tests for RAG Service functionality.

Tests RAG service orchestration and integration.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import SecretStr

from bot.services.rag_service import RAGService
from config.settings import EmbeddingSettings, LLMSettings, Settings, VectorSettings


# TDD Factory Patterns for RAG Service Testing
class SettingsFactory:
    """Factory for creating various Settings configurations"""

    @staticmethod
    def create_complete_rag_settings(
        embedding_provider: str = "openai",
        llm_provider: str = "openai",
        vector_provider: str = "pinecone",
    ) -> Settings:
        """Create complete RAG settings with all components"""
        return Settings(
            embedding=EmbeddingSettings(
                provider=embedding_provider,
                model="text-embedding-ada-002",
                api_key=SecretStr("test-key"),
            ),
            llm=LLMSettings(
                provider=llm_provider,
                model="gpt-4",
                api_key=SecretStr("test-key"),
            ),
            vector=VectorSettings(
                provider=vector_provider,
                api_key=SecretStr("test-key"),
                collection_name="test",
                enabled=True,
            ),
        )

    @staticmethod
    def create_vector_disabled_settings() -> Settings:
        """Create settings with vector storage disabled"""
        settings = SettingsFactory.create_complete_rag_settings()
        settings.vector.enabled = False
        return settings


class VectorStoreMockFactory:
    """Factory for creating vector store mocks"""

    @staticmethod
    def create_basic_vector_store() -> AsyncMock:
        """Create basic vector store mock"""
        mock_store = AsyncMock()
        mock_store.initialize = AsyncMock()
        mock_store.close = AsyncMock()
        mock_store.add_documents = AsyncMock(return_value=5)  # Default documents added
        mock_store.search = AsyncMock(return_value=[])  # Default empty search
        return mock_store

    @staticmethod
    def create_vector_store_with_documents(doc_count: int = 5) -> AsyncMock:
        """Create vector store mock that returns specific document count"""
        mock_store = VectorStoreMockFactory.create_basic_vector_store()
        mock_store.add_documents = AsyncMock(return_value=doc_count)
        return mock_store

    @staticmethod
    def create_failing_vector_store(error: str = "Vector store error") -> AsyncMock:
        """Create vector store mock that fails operations"""
        mock_store = AsyncMock()
        mock_store.initialize = AsyncMock(side_effect=Exception(error))
        mock_store.close = AsyncMock()
        mock_store.add_documents = AsyncMock(side_effect=Exception(error))
        return mock_store


class EmbeddingProviderMockFactory:
    """Factory for creating embedding provider mocks"""

    @staticmethod
    def create_basic_embedding_provider() -> AsyncMock:
        """Create basic embedding provider mock"""
        mock_provider = AsyncMock()
        mock_provider.get_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
        mock_provider.get_embeddings = AsyncMock(return_value=[[0.1, 0.2], [0.4, 0.5]])
        mock_provider.close = AsyncMock()
        return mock_provider

    @staticmethod
    def create_embedding_provider_with_error(
        error: str = "Embedding error",
    ) -> AsyncMock:
        """Create embedding provider mock that fails"""
        mock_provider = AsyncMock()
        mock_provider.get_embedding = AsyncMock(side_effect=Exception(error))
        mock_provider.close = AsyncMock()
        return mock_provider


class LLMProviderMockFactory:
    """Factory for creating LLM provider mocks"""

    @staticmethod
    def create_basic_llm_provider(response: str = "Test LLM response") -> AsyncMock:
        """Create basic LLM provider mock"""
        mock_provider = AsyncMock()
        mock_provider.get_response = AsyncMock(return_value=response)
        mock_provider.close = AsyncMock()
        return mock_provider

    @staticmethod
    def create_failing_llm_provider(error: str = "LLM error") -> AsyncMock:
        """Create LLM provider mock that fails"""
        mock_provider = AsyncMock()
        mock_provider.get_response = AsyncMock(side_effect=Exception(error))
        mock_provider.close = AsyncMock()
        return mock_provider


class RAGServiceMockFactory:
    """Factory for creating RAG service with configured mocks"""

    @staticmethod
    def create_service_with_mocks(
        settings: Settings,
        vector_store: AsyncMock = None,
        embedding_provider: AsyncMock = None,
        llm_provider: AsyncMock = None,
    ) -> RAGService:
        """Create RAG service with specific mocks"""
        with (
            patch("bot.services.rag_service.create_vector_store") as mock_vector_store,
            patch(
                "bot.services.rag_service.create_embedding_provider"
            ) as mock_embedding,
            patch("bot.services.rag_service.create_llm_provider") as mock_llm,
        ):
            # Use provided mocks or create defaults
            vector_store_instance = (
                vector_store or VectorStoreMockFactory.create_basic_vector_store()
            )
            embedding_instance = (
                embedding_provider
                or EmbeddingProviderMockFactory.create_basic_embedding_provider()
            )
            llm_instance = (
                llm_provider or LLMProviderMockFactory.create_basic_llm_provider()
            )

            mock_vector_store.return_value = vector_store_instance
            mock_embedding.return_value = embedding_instance
            mock_llm.return_value = llm_instance

            service = RAGService(settings)

            # Ensure the service has the expected attributes
            service.vector_store = vector_store_instance
            service.embedding_provider = embedding_instance
            service.llm_provider = llm_instance

            return service


class RetrievalServiceMockFactory:
    """Factory for creating retrieval service mocks"""

    @staticmethod
    def create_basic_retrieval_service() -> Mock:
        """Create basic retrieval service mock"""
        mock_service = Mock()
        mock_service.retrieve_context = AsyncMock(return_value=[])
        return mock_service

    @staticmethod
    def create_retrieval_service_with_context(context: list = None) -> Mock:
        """Create retrieval service with specific context"""
        if context is None:
            context = [{"content": "Test context", "metadata": {"source": "test"}}]

        mock_service = RetrievalServiceMockFactory.create_basic_retrieval_service()
        mock_service.retrieve_context = AsyncMock(return_value=context)
        return mock_service


class DocumentTestDataFactory:
    """Factory for creating test documents"""

    @staticmethod
    def create_simple_documents(count: int = 5) -> list:
        """Create simple test documents"""
        return [
            {
                "content": f"Document {i} content",
                "metadata": {"source": f"doc{i}.txt", "page": i},
            }
            for i in range(count)
        ]

    @staticmethod
    def create_complex_documents() -> list:
        """Create complex test documents with various metadata"""
        return [
            {
                "content": "Complex document with detailed content for testing",
                "metadata": {
                    "source": "complex_doc.pdf",
                    "page": 1,
                    "title": "Complex Document",
                    "author": "Test Author",
                },
            },
            {
                "content": "Another document with different structure",
                "metadata": {
                    "source": "another_doc.txt",
                    "section": "Introduction",
                    "category": "research",
                },
            },
        ]


class TestRAGService:
    """Test cases for RAG service"""

    @pytest.fixture
    def settings(self):
        """Create settings for testing"""
        return SettingsFactory.create_complete_rag_settings()

    @pytest.fixture
    def rag_service(self, settings):
        """Create RAG service for testing"""
        return RAGServiceMockFactory.create_service_with_mocks(settings)

    def test_init(self, rag_service, settings):
        """Test service initialization"""
        assert rag_service.settings == settings
        assert hasattr(rag_service, "retrieval_service")
        assert hasattr(rag_service, "citation_service")
        assert hasattr(rag_service, "context_builder")

    @pytest.mark.asyncio
    async def test_initialization_success(self, rag_service):
        """Test successful initialization"""
        # The RAG service initialize method only calls vector_store.initialize() if vector_store exists
        rag_service.vector_store.initialize = AsyncMock()

        await rag_service.initialize()

        # The actual initialize method calls vector_store.initialize(), not retrieval_service
        rag_service.vector_store.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialization_failure(self, rag_service):
        """Test initialization failure"""
        rag_service.vector_store.initialize = AsyncMock(
            side_effect=Exception("Init failed")
        )

        with pytest.raises(Exception, match="Init failed"):
            await rag_service.initialize()

    @pytest.mark.asyncio
    async def test_ingest_documents_success(self, rag_service):
        """Test successful document ingestion"""
        # Set up embedding provider and vector store mocks
        rag_service.embedding_provider.get_embedding = AsyncMock(
            return_value=[0.1, 0.2, 0.3]
        )
        rag_service.vector_store.add_documents = AsyncMock()

        documents = [
            {
                "content": "test document content that is long enough to be processed",
                "metadata": {"file_name": "test.pdf"},
            }
        ]

        result = await rag_service.ingest_documents(documents)

        assert result == (1, 0)  # (success_count, error_count)
        rag_service.vector_store.add_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_response_success(self, rag_service):
        """Test successful response generation"""
        # Set up all the method mocks explicitly
        rag_service.retrieval_service.retrieve_context = AsyncMock(
            return_value=[
                {
                    "content": "context",
                    "similarity": 0.8,
                    "metadata": {"file_name": "test.pdf"},
                }
            ]
        )
        rag_service.context_builder.build_rag_prompt = Mock(
            return_value=(
                "system",
                [{"role": "user", "content": "query"}],
            )
        )
        rag_service.llm_provider.get_response = AsyncMock(return_value="LLM response")
        rag_service.citation_service.add_source_citations = Mock(
            return_value="Final response with citations"
        )

        response = await rag_service.generate_response("query", [])

        assert "Final response with citations" in response
        # The actual method signature includes vector_store, embedding_provider, and conversation_history
        rag_service.retrieval_service.retrieve_context.assert_called_once_with(
            "query",
            rag_service.vector_store,
            rag_service.embedding_provider,
            conversation_history=[],
        )

    @pytest.mark.asyncio
    async def test_get_system_status(self, rag_service):
        """Test getting system status"""
        rag_service.retrieval_service = Mock()
        rag_service.retrieval_service.get_status.return_value = {"status": "ready"}

        status = await rag_service.get_system_status()

        assert isinstance(status, dict)
        assert "services" in status
        assert "vector_enabled" in status

    @pytest.mark.asyncio
    async def test_close(self, rag_service):
        """Test closing the service"""
        # The vector_store should be AsyncMock from fixture
        await rag_service.close()

        # Only vector_store.close() is called in the actual implementation
        rag_service.vector_store.close.assert_called_once()
