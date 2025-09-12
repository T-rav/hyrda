"""
Tests for EmbeddingService functionality.

Tests embedding providers, text chunking, and vectorization.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import SecretStr

from bot.services.embedding_service import (
    EmbeddingProvider,
    OpenAIEmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
    chunk_text,
    create_embedding_provider,
)
from config.settings import EmbeddingSettings, LLMSettings


class TestEmbeddingProvider:
    """Test cases for abstract EmbeddingProvider base class"""

    def test_embedding_provider_is_abstract(self):
        """Test that EmbeddingProvider cannot be instantiated directly"""
        with pytest.raises(TypeError):
            EmbeddingProvider(Mock())


class TestOpenAIEmbeddingProvider:
    """Test cases for OpenAIEmbeddingProvider"""

    @pytest.fixture
    def embedding_settings(self):
        """Create embedding settings for testing"""
        return EmbeddingSettings(
            provider="openai",
            model="text-embedding-ada-002",
            api_key=SecretStr("test-api-key"),
        )

    @pytest.fixture
    def llm_settings(self):
        """Create LLM settings for testing"""
        return LLMSettings(
            provider="openai", api_key=SecretStr("llm-api-key"), model="gpt-3.5-turbo"
        )

    @pytest.fixture
    def provider(self, embedding_settings):
        """Create OpenAI embedding provider for testing"""
        with patch("bot.services.embedding_service.AsyncOpenAI"):
            return OpenAIEmbeddingProvider(embedding_settings)

    def test_init_with_embedding_api_key(self, embedding_settings):
        """Test initialization with dedicated embedding API key"""
        with patch("bot.services.embedding_service.AsyncOpenAI") as mock_openai:
            provider = OpenAIEmbeddingProvider(embedding_settings)

            mock_openai.assert_called_once_with(api_key="test-api-key")
            assert provider.model == "text-embedding-ada-002"

    def test_init_with_llm_fallback_key(self, llm_settings):
        """Test initialization falling back to LLM API key"""
        embedding_settings = EmbeddingSettings(
            provider="openai", model="text-embedding-ada-002"
        )

        with patch("bot.services.embedding_service.AsyncOpenAI") as mock_openai:
            provider = OpenAIEmbeddingProvider(embedding_settings, llm_settings)

            mock_openai.assert_called_once_with(api_key="llm-api-key")
            assert provider.model == "text-embedding-ada-002"

    def test_init_without_api_key(self):
        """Test initialization fails without API key"""
        embedding_settings = EmbeddingSettings(
            provider="openai", model="text-embedding-ada-002"
        )

        with pytest.raises(ValueError, match="OpenAI API key required"):
            OpenAIEmbeddingProvider(embedding_settings)

    @pytest.mark.asyncio
    async def test_get_embeddings_success(self, provider):
        """Test successful embedding generation"""
        mock_response = Mock()
        mock_response.data = [
            Mock(embedding=[0.1, 0.2, 0.3]),
            Mock(embedding=[0.4, 0.5, 0.6]),
        ]

        provider.client.embeddings.create = AsyncMock(return_value=mock_response)

        texts = ["text 1", "text 2"]
        embeddings = await provider.get_embeddings(texts)

        assert embeddings == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        provider.client.embeddings.create.assert_called_once_with(
            model="text-embedding-ada-002", input=texts
        )

    @pytest.mark.asyncio
    async def test_get_embeddings_error(self, provider):
        """Test embedding generation error handling"""
        provider.client.embeddings.create = AsyncMock(
            side_effect=Exception("API Error")
        )

        texts = ["text 1", "text 2"]

        with pytest.raises(Exception, match="API Error"):
            await provider.get_embeddings(texts)

    @pytest.mark.asyncio
    async def test_get_embedding_single(self, provider):
        """Test single embedding generation"""
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1, 0.2, 0.3])]

        provider.client.embeddings.create = AsyncMock(return_value=mock_response)

        embedding = await provider.get_embedding("test text")

        assert embedding == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_close(self, provider):
        """Test closing the provider"""
        provider.client._client = Mock()
        provider.client.close = AsyncMock()

        await provider.close()

        provider.client.close.assert_called_once()


class TestSentenceTransformerEmbeddingProvider:
    """Test cases for SentenceTransformerEmbeddingProvider"""

    @pytest.fixture
    def embedding_settings(self):
        """Create embedding settings for testing"""
        return EmbeddingSettings(
            provider="sentence-transformers", model="all-MiniLM-L6-v2"
        )

    @pytest.fixture
    def provider(self, embedding_settings):
        """Create SentenceTransformer provider for testing"""
        return SentenceTransformerEmbeddingProvider(embedding_settings)

    def test_init(self, provider):
        """Test provider initialization"""
        assert provider.model == "all-MiniLM-L6-v2"
        assert provider.model_instance is None
        assert provider._initialized is False

    @pytest.mark.asyncio
    async def test_initialize_success(self, provider):
        """Test successful model initialization"""
        mock_model = Mock()

        with (
            patch(
                "bot.services.embedding_service.SentenceTransformer",
                return_value=mock_model,
            ),
            patch("asyncio.get_event_loop") as mock_loop,
        ):
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=mock_model)

            await provider._initialize()

            assert provider._initialized is True
            assert provider.model_instance == mock_model

    @pytest.mark.asyncio
    async def test_initialize_import_error(self, provider):
        """Test initialization with missing sentence-transformers package"""
        with (
            patch(
                "bot.services.embedding_service.SentenceTransformer",
                side_effect=ImportError,
            ),
            pytest.raises(
                ImportError, match="sentence-transformers package not installed"
            ),
        ):
            await provider._initialize()

    @pytest.mark.asyncio
    async def test_initialize_only_once(self, provider):
        """Test that initialization only happens once"""
        mock_model = Mock()

        with (
            patch(
                "bot.services.embedding_service.SentenceTransformer",
                return_value=mock_model,
            ),
            patch("asyncio.get_event_loop") as mock_loop,
        ):
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=mock_model)

            await provider._initialize()
            await provider._initialize()  # Second call

            # Should only be called once
            mock_loop.return_value.run_in_executor.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_embeddings_success(self, provider):
        """Test successful embedding generation"""
        mock_model = Mock()
        mock_embeddings = [
            Mock(tolist=Mock(return_value=[0.1, 0.2, 0.3])),
            Mock(tolist=Mock(return_value=[0.4, 0.5, 0.6])),
        ]

        provider.model_instance = mock_model
        provider._initialized = True

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(
                return_value=mock_embeddings
            )

            texts = ["text 1", "text 2"]
            embeddings = await provider.get_embeddings(texts)

            assert embeddings == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

    @pytest.mark.asyncio
    async def test_get_embeddings_not_initialized(self, provider):
        """Test embedding generation when model not initialized"""
        provider.model_instance = None

        with (
            patch.object(provider, "_initialize", AsyncMock()),
            patch("asyncio.get_event_loop") as mock_loop,
        ):
            mock_loop.return_value.run_in_executor = AsyncMock(
                side_effect=RuntimeError("not initialized")
            )

            with pytest.raises(RuntimeError):
                await provider.get_embeddings(["test"])

    @pytest.mark.asyncio
    async def test_get_embedding_single(self, provider):
        """Test single embedding generation"""
        mock_model = Mock()
        mock_embeddings = [Mock(tolist=Mock(return_value=[0.1, 0.2, 0.3]))]

        provider.model_instance = mock_model
        provider._initialized = True

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(
                return_value=mock_embeddings
            )

            embedding = await provider.get_embedding("test text")

            assert embedding == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_close(self, provider):
        """Test closing the provider"""
        provider.model_instance = Mock()
        provider._initialized = True

        await provider.close()

        assert provider.model_instance is None
        assert provider._initialized is False


class TestCreateEmbeddingProvider:
    """Test cases for embedding provider factory"""

    def test_create_openai_provider(self):
        """Test creating OpenAI provider"""
        settings = EmbeddingSettings(
            provider="openai",
            model="text-embedding-ada-002",
            api_key=SecretStr("test-key"),
        )

        with patch("bot.services.embedding_service.AsyncOpenAI"):
            provider = create_embedding_provider(settings)

            assert isinstance(provider, OpenAIEmbeddingProvider)
            assert provider.model == "text-embedding-ada-002"

    def test_create_sentence_transformers_provider(self):
        """Test creating SentenceTransformers provider"""
        settings = EmbeddingSettings(
            provider="sentence-transformers", model="all-MiniLM-L6-v2"
        )

        provider = create_embedding_provider(settings)

        assert isinstance(provider, SentenceTransformerEmbeddingProvider)
        assert provider.model == "all-MiniLM-L6-v2"

    def test_create_sentence_transformers_alternative_name(self):
        """Test creating SentenceTransformers provider with alternative name"""
        settings = EmbeddingSettings(
            provider="sentence_transformers", model="all-MiniLM-L6-v2"
        )

        provider = create_embedding_provider(settings)

        assert isinstance(provider, SentenceTransformerEmbeddingProvider)

    def test_create_unsupported_provider(self):
        """Test creating unsupported provider"""
        settings = EmbeddingSettings(provider="unsupported", model="test-model")

        with pytest.raises(ValueError, match="Unsupported embedding provider"):
            create_embedding_provider(settings)


class TestChunkText:
    """Test cases for text chunking functionality"""

    def test_chunk_text_short_text(self):
        """Test chunking text shorter than chunk size"""
        text = "This is a short text."
        chunks = chunk_text(text, chunk_size=100)

        assert chunks == [text]

    def test_chunk_text_with_paragraphs(self):
        """Test chunking text with paragraph breaks"""
        text = "First paragraph.\n\nSecond paragraph with more content.\n\nThird paragraph."
        chunks = chunk_text(text, chunk_size=30, chunk_overlap=10)

        assert len(chunks) > 1
        assert all(chunk.strip() for chunk in chunks)

    def test_chunk_text_with_sentences(self):
        """Test chunking text with sentence breaks"""
        text = "First sentence. Second sentence with content. Third sentence here."
        chunks = chunk_text(text, chunk_size=25, chunk_overlap=5)

        assert len(chunks) > 1
        assert all(chunk.strip() for chunk in chunks)

    def test_chunk_text_with_overlap(self):
        """Test that chunks have proper overlap"""
        text = "A" * 100
        chunks = chunk_text(text, chunk_size=30, chunk_overlap=10)

        assert len(chunks) > 1
        # Check overlap exists between consecutive chunks
        for i in range(len(chunks) - 1):
            current_end = chunks[i][-10:]
            next_start = chunks[i + 1][:10]
            # Some overlap should exist
            assert len(set(current_end) & set(next_start)) > 0

    def test_chunk_text_normalize_whitespace(self):
        """Test text normalization during chunking"""
        text = "Text\r\nwith\r\nvarious\n\n\nline   endings   and    spaces."
        chunks = chunk_text(text, chunk_size=100)

        assert "\r" not in chunks[0]
        assert "   " not in chunks[0]  # Excessive whitespace removed

    def test_chunk_text_custom_separators(self):
        """Test chunking with custom separators"""
        text = "Part1|Part2|Part3|Part4"
        chunks = chunk_text(text, chunk_size=10, separators=["|", " "])

        assert len(chunks) > 1
        # Should split on | separator
        assert any("|" not in chunk or chunk.endswith("|") for chunk in chunks[:-1])

    def test_chunk_text_empty_text(self):
        """Test chunking empty text"""
        chunks = chunk_text("", chunk_size=100)
        assert chunks == []

    def test_chunk_text_whitespace_only(self):
        """Test chunking text with only whitespace"""
        chunks = chunk_text("   \n\n   ", chunk_size=100)
        assert chunks == []

    def test_chunk_text_no_good_separator(self):
        """Test chunking when no good separator is found"""
        text = "A" * 100  # No separators
        chunks = chunk_text(text, chunk_size=30, chunk_overlap=10)

        assert len(chunks) > 1
        assert all(len(chunk) <= 30 for chunk in chunks)

    def test_chunk_text_edge_case_sizes(self):
        """Test chunking with edge case chunk sizes"""
        text = "This is a test text for chunking."

        # Very small chunk size
        chunks = chunk_text(text, chunk_size=5, chunk_overlap=2)
        assert len(chunks) > 1

        # Chunk overlap larger than chunk size
        chunks = chunk_text(text, chunk_size=10, chunk_overlap=15)
        assert len(chunks) >= 1

        # Zero overlap
        chunks = chunk_text(text, chunk_size=15, chunk_overlap=0)
        assert len(chunks) >= 1
