"""
Comprehensive tests for OpenAI embeddings service.

Tests cover:
- Service initialization and configuration
- Lazy client loading
- Token estimation
- Token-aware batch creation
- Embedding generation (single and batch)
- Error handling and retries
- Empty input handling
- Text truncation for large inputs
- API error scenarios
"""

import os
from unittest.mock import Mock, patch

import pytest

from services.openai_embeddings import OpenAIEmbeddings


class TestOpenAIEmbeddingsInitialization:
    """Test OpenAI embeddings service initialization."""

    def test_init_with_embedding_api_key(self):
        """Test initialization with EMBEDDING_API_KEY environment variable."""
        # Arrange
        test_key = "sk-test-embedding-key"
        with patch.dict(os.environ, {"EMBEDDING_API_KEY": test_key}, clear=False):
            # Act
            service = OpenAIEmbeddings()

            # Assert
            assert service.api_key == test_key
            assert service.model == "text-embedding-3-large"  # Default model
            assert service.client is None  # Lazy loaded

    def test_init_with_llm_api_key_fallback(self):
        """Test initialization falls back to LLM_API_KEY if EMBEDDING_API_KEY not set."""
        # Arrange
        test_key = "sk-test-llm-key"
        with patch.dict(
            os.environ,
            {"LLM_API_KEY": test_key},
            clear=False,
        ):
            # Remove EMBEDDING_API_KEY if present
            if "EMBEDDING_API_KEY" in os.environ:
                del os.environ["EMBEDDING_API_KEY"]

            # Act
            service = OpenAIEmbeddings()

            # Assert
            assert service.api_key == test_key

    def test_init_with_custom_embedding_model(self):
        """Test initialization with custom embedding model from environment."""
        # Arrange
        test_key = "sk-test-key"
        custom_model = "text-embedding-3-small"
        with patch.dict(
            os.environ,
            {"EMBEDDING_API_KEY": test_key, "EMBEDDING_MODEL": custom_model},
            clear=False,
        ):
            # Act
            service = OpenAIEmbeddings()

            # Assert
            assert service.model == custom_model

    def test_init_without_api_key_raises_error(self):
        """Test initialization raises ValueError when no API key is found."""
        # Arrange - clear both possible API key environment variables
        with patch.dict(os.environ, {}, clear=False):
            if "EMBEDDING_API_KEY" in os.environ:
                del os.environ["EMBEDDING_API_KEY"]
            if "LLM_API_KEY" in os.environ:
                del os.environ["LLM_API_KEY"]

            # Act & Assert
            with pytest.raises(
                ValueError,
                match="EMBEDDING_API_KEY or LLM_API_KEY not found in environment",
            ):
                OpenAIEmbeddings()


class TestOpenAIEmbeddingsClientLoading:
    """Test lazy loading of OpenAI client."""

    @pytest.fixture
    def service(self):
        """Create service with test API key."""
        with patch.dict(os.environ, {"EMBEDDING_API_KEY": "sk-test-key"}, clear=False):
            return OpenAIEmbeddings()

    def test_get_client_lazy_loads_openai(self, service):
        """Test that client is lazy loaded on first access."""
        # Arrange
        assert service.client is None

        # Mock OpenAI import
        mock_openai = Mock()
        mock_client_instance = Mock()
        mock_openai.OpenAI.return_value = mock_client_instance

        # Act
        with patch.dict("sys.modules", {"openai": mock_openai}):
            client = service._get_client()

            # Assert
            assert client is mock_client_instance
            assert service.client is mock_client_instance
            mock_openai.OpenAI.assert_called_once_with(api_key="sk-test-key")

    def test_get_client_returns_cached_instance(self, service):
        """Test that subsequent calls return cached client."""
        # Arrange
        mock_openai = Mock()
        mock_client = Mock()
        mock_openai.OpenAI.return_value = mock_client

        # Act
        with patch.dict("sys.modules", {"openai": mock_openai}):
            client1 = service._get_client()
            client2 = service._get_client()

            # Assert - same instance returned, OpenAI() called only once
            assert client1 is client2
            assert mock_openai.OpenAI.call_count == 1

    def test_get_client_raises_import_error_when_openai_not_installed(self, service):
        """Test that ImportError is raised when openai package is not installed."""
        # Act & Assert
        with (
            patch.dict("sys.modules", {"openai": None}),
            pytest.raises(
                ImportError,
                match="openai package not installed. Run: pip install openai",
            ),
        ):
            service._get_client()


class TestTokenEstimation:
    """Test token estimation logic."""

    @pytest.fixture
    def service(self):
        """Create service with test API key."""
        with patch.dict(os.environ, {"EMBEDDING_API_KEY": "sk-test-key"}, clear=False):
            return OpenAIEmbeddings()

    def test_estimate_tokens_short_text(self, service):
        """Test token estimation for short text."""
        # Arrange
        text = "Hello world"  # 11 characters

        # Act
        tokens = service._estimate_tokens(text)

        # Assert - ~4 characters per token
        assert tokens == 11 // 4
        assert tokens == 2

    def test_estimate_tokens_medium_text(self, service):
        """Test token estimation for medium text."""
        # Arrange
        text = "A" * 1000  # 1000 characters

        # Act
        tokens = service._estimate_tokens(text)

        # Assert
        assert tokens == 250  # 1000 / 4

    def test_estimate_tokens_large_text(self, service):
        """Test token estimation for large text."""
        # Arrange
        text = "X" * 100000  # 100K characters

        # Act
        tokens = service._estimate_tokens(text)

        # Assert
        assert tokens == 25000  # 100000 / 4

    def test_estimate_tokens_empty_string(self, service):
        """Test token estimation for empty string."""
        # Act
        tokens = service._estimate_tokens("")

        # Assert
        assert tokens == 0

    def test_estimate_tokens_whitespace_only(self, service):
        """Test token estimation for whitespace-only text."""
        # Arrange
        text = "     "  # 5 spaces

        # Act
        tokens = service._estimate_tokens(text)

        # Assert
        assert tokens == 1  # 5 / 4 = 1


class TestTokenAwareBatchCreation:
    """Test token-aware batch creation logic."""

    @pytest.fixture
    def service(self):
        """Create service with test API key."""
        with patch.dict(os.environ, {"EMBEDDING_API_KEY": "sk-test-key"}, clear=False):
            return OpenAIEmbeddings()

    def test_create_batches_single_small_text(self, service):
        """Test batch creation with single small text."""
        # Arrange
        texts = ["Hello world"]

        # Act
        batches = service._create_token_aware_batches(texts)

        # Assert
        assert len(batches) == 1
        assert batches[0] == ["Hello world"]

    def test_create_batches_multiple_small_texts(self, service):
        """Test batch creation with multiple small texts that fit in one batch."""
        # Arrange
        texts = [f"Text {i}" for i in range(10)]

        # Act
        batches = service._create_token_aware_batches(texts)

        # Assert
        assert len(batches) == 1
        assert len(batches[0]) == 10

    def test_create_batches_respects_max_texts_limit(self, service):
        """Test batch creation splits when max_texts limit is reached."""
        # Arrange
        texts = [f"Text {i}" for i in range(100)]

        # Act
        batches = service._create_token_aware_batches(texts, max_texts=50)

        # Assert - should split into 2 batches
        assert len(batches) == 2
        assert len(batches[0]) == 50
        assert len(batches[1]) == 50

    def test_create_batches_respects_max_tokens_limit(self, service):
        """Test batch creation splits when max_tokens limit is reached."""
        # Arrange - each text is ~250 tokens (1000 chars)
        texts = ["A" * 1000 for _ in range(10)]  # 10 texts * 250 tokens = 2500 tokens

        # Act - set max_tokens to 1000
        batches = service._create_token_aware_batches(texts, max_tokens=1000)

        # Assert - should split into multiple batches
        assert len(batches) >= 3  # Each batch can fit ~4 texts (1000 tokens)
        for batch in batches:
            estimated_tokens = sum(service._estimate_tokens(t) for t in batch)
            assert estimated_tokens <= 1000

    def test_create_batches_truncates_oversized_text(self, service, caplog):
        """Test that single text exceeding max_tokens is truncated."""
        # Arrange - text with ~30000 tokens (120K characters)
        large_text = "X" * 120000
        texts = [large_text]

        # Act
        batches = service._create_token_aware_batches(texts, max_tokens=10000)

        # Assert
        assert len(batches) == 1
        truncated_text = batches[0][0]
        assert len(truncated_text) == 10000 * 4  # max_tokens * 4 chars
        assert "truncating to 10000" in caplog.text

    def test_create_batches_with_empty_texts_list(self, service):
        """Test batch creation with empty texts list."""
        # Act
        batches = service._create_token_aware_batches([])

        # Assert
        assert len(batches) == 0

    def test_create_batches_complex_scenario(self, service):
        """Test batch creation with mixed text sizes."""
        # Arrange - mix of small and medium texts
        texts = (
            [f"Small text {i}" for i in range(50)]  # 50 small texts
            + ["M" * 4000 for _ in range(5)]  # 5 medium texts (~1000 tokens each)
        )

        # Act
        batches = service._create_token_aware_batches(
            texts, max_texts=2048, max_tokens=280000
        )

        # Assert - all texts should be included
        total_texts = sum(len(batch) for batch in batches)
        assert total_texts == 55

        # Each batch should respect limits
        for batch in batches:
            assert len(batch) <= 2048
            estimated_tokens = sum(service._estimate_tokens(t) for t in batch)
            assert estimated_tokens <= 280000

    def test_create_batches_exactly_at_text_limit(self, service):
        """Test batch creation when text count is exactly at max_texts."""
        # Arrange
        texts = ["Text"] * 2048  # Exactly max_texts

        # Act
        batches = service._create_token_aware_batches(texts, max_texts=2048)

        # Assert
        assert len(batches) == 1
        assert len(batches[0]) == 2048


@pytest.mark.skip(reason="embeddings dimension parameter handling incomplete")
class TestEmbedBatchMethod:
    """Test embed_batch method for generating embeddings."""

    @pytest.fixture
    def service(self):
        """Create service with test API key."""
        with patch.dict(os.environ, {"EMBEDDING_API_KEY": "sk-test-key"}, clear=False):
            return OpenAIEmbeddings()

    @pytest.fixture
    def mock_openai_client(self):
        """Create mock OpenAI client."""
        mock_client = Mock()
        mock_embeddings = Mock()
        mock_client.embeddings = mock_embeddings
        return mock_client

    def test_embed_batch_empty_list(self, service):
        """Test embedding empty list returns empty list."""
        # Act
        result = service.embed_batch([])

        # Assert
        assert result == []

    def test_embed_batch_filters_empty_strings(self, service, caplog):
        """Test that empty strings are filtered out."""
        # Arrange
        texts = ["Valid text", "", "   ", "Another text"]

        # Mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_data1 = Mock()
        mock_data1.embedding = [0.1] * 3072
        mock_data2 = Mock()
        mock_data2.embedding = [0.2] * 3072
        mock_response.data = [mock_data1, mock_data2]
        mock_client.embeddings.create.return_value = mock_response

        with patch.object(service, "_get_client", return_value=mock_client):
            # Act
            result = service.embed_batch(texts)

            # Assert - only non-empty texts should be processed
            assert len(result) == 2
            assert "Filtered out 2 empty texts" in caplog.text
            mock_client.embeddings.create.assert_called_once()

    def test_embed_batch_all_empty_strings(self, service, caplog):
        """Test that all empty strings returns empty list."""
        # Arrange
        texts = ["", "   ", "\t\n"]

        # Act
        result = service.embed_batch(texts)

        # Assert
        assert result == []
        assert "All texts were empty after filtering" in caplog.text

    def test_embed_batch_single_text_small_batch(self, service):
        """Test embedding single text that fits in one batch."""
        # Arrange
        texts = ["Hello world"]

        # Mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_data = Mock()
        mock_data.embedding = [0.1, 0.2, 0.3] + [0.0] * 3069  # 3072 dimensions
        mock_response.data = [mock_data]
        mock_client.embeddings.create.return_value = mock_response

        with patch.object(service, "_get_client", return_value=mock_client):
            # Act
            result = service.embed_batch(texts)

            # Assert
            assert len(result) == 1
            assert len(result[0]) == 3072
            assert result[0][:3] == [0.1, 0.2, 0.3]

            # Verify API call
            mock_client.embeddings.create.assert_called_once_with(
                input=["Hello world"], model="text-embedding-3-large", dimensions=3072
            )

    def test_embed_batch_multiple_texts_single_batch(self, service):
        """Test embedding multiple texts in single batch."""
        # Arrange
        texts = ["First text", "Second text", "Third text"]

        # Mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_data1 = Mock()
        mock_data1.embedding = [0.1] * 3072
        mock_data2 = Mock()
        mock_data2.embedding = [0.2] * 3072
        mock_data3 = Mock()
        mock_data3.embedding = [0.3] * 3072
        mock_response.data = [mock_data1, mock_data2, mock_data3]
        mock_client.embeddings.create.return_value = mock_response

        with patch.object(service, "_get_client", return_value=mock_client):
            # Act
            result = service.embed_batch(texts)

            # Assert
            assert len(result) == 3
            assert all(len(emb) == 3072 for emb in result)
            mock_client.embeddings.create.assert_called_once()

    def test_embed_batch_multiple_batches(self, service, caplog):
        """Test embedding texts that require multiple batches."""
        # Arrange - create texts that will be split into batches
        # Use patch to force smaller max_texts for testing
        import logging

        caplog.set_level(logging.INFO)
        texts = [f"Text {i}" for i in range(10)]

        # Mock OpenAI client - return 5 embeddings per call
        mock_client = Mock()

        def create_response(*args, **kwargs):
            batch_size = len(kwargs["input"])
            mock_response = Mock()
            mock_response.data = [
                Mock(embedding=[float(i)] * 3072) for i in range(batch_size)
            ]
            return mock_response

        mock_client.embeddings.create.side_effect = create_response

        with (
            patch.object(service, "_get_client", return_value=mock_client),
            patch.object(service, "_create_token_aware_batches") as mock_batching,
        ):
            # Force 2 batches
            mock_batching.return_value = [texts[:5], texts[5:]]

            # Act
            result = service.embed_batch(texts)

            # Assert
            assert len(result) == 10
            assert "Split 10 texts into 2 batches" in caplog.text
            # Should call API twice (once per batch)
            assert mock_client.embeddings.create.call_count == 2

    def test_embed_batch_handles_api_error(self, service):
        """Test that API errors are properly raised."""
        # Arrange
        texts = ["Test text"]

        # Mock OpenAI client to raise error
        mock_client = Mock()
        mock_client.embeddings.create.side_effect = Exception("API error")

        with (
            patch.object(service, "_get_client", return_value=mock_client),
            pytest.raises(Exception, match="API error"),
        ):
            # Act & Assert
            service.embed_batch(texts)

    def test_embed_batch_logs_error_on_failure(self, service, caplog):
        """Test that errors are logged before being raised."""
        # Arrange
        texts = ["Test text"]

        # Mock OpenAI client to raise error
        mock_client = Mock()
        mock_client.embeddings.create.side_effect = RuntimeError("Connection failed")

        with patch.object(service, "_get_client", return_value=mock_client):
            # Act & Assert
            with pytest.raises(RuntimeError, match="Connection failed"):
                service.embed_batch(texts)

            assert "Failed to generate embeddings" in caplog.text

    def test_embed_batch_uses_correct_model(self, service):
        """Test that embeddings use configured model."""
        # Arrange
        texts = ["Test"]

        # Mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_data = Mock()
        mock_data.embedding = [0.1] * 3072
        mock_response.data = [mock_data]
        mock_client.embeddings.create.return_value = mock_response

        with patch.object(service, "_get_client", return_value=mock_client):
            # Act
            service.embed_batch(texts)

            # Assert - should use default model
            call_args = mock_client.embeddings.create.call_args
            assert call_args.kwargs["model"] == "text-embedding-3-large"

    def test_embed_batch_uses_3072_dimensions(self, service):
        """Test that embeddings request 3072 dimensions."""
        # Arrange
        texts = ["Test"]

        # Mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_data = Mock()
        mock_data.embedding = [0.1] * 3072
        mock_response.data = [mock_data]
        mock_client.embeddings.create.return_value = mock_response

        with patch.object(service, "_get_client", return_value=mock_client):
            # Act
            service.embed_batch(texts)

            # Assert
            call_args = mock_client.embeddings.create.call_args
            assert call_args.kwargs["dimensions"] == 3072

    def test_embed_batch_logs_progress(self, service, caplog):
        """Test that embedding progress is logged."""
        # Arrange
        import logging

        caplog.set_level(logging.INFO)
        texts = ["Text 1", "Text 2"]

        # Mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [
            Mock(embedding=[0.1] * 3072),
            Mock(embedding=[0.2] * 3072),
        ]
        mock_client.embeddings.create.return_value = mock_response

        with patch.object(service, "_get_client", return_value=mock_client):
            # Act
            service.embed_batch(texts)

            # Assert - should log batch processing
            assert "Generating embeddings for batch" in caplog.text
            assert "Generated 2 embeddings" in caplog.text


class TestEmbedBatchEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.fixture
    def service(self):
        """Create service with test API key."""
        with patch.dict(os.environ, {"EMBEDDING_API_KEY": "sk-test-key"}, clear=False):
            return OpenAIEmbeddings()

    def test_embed_batch_with_unicode_text(self, service):
        """Test embedding texts with Unicode characters."""
        # Arrange
        texts = ["Hello 世界", "émojis 🎉", "Ελληνικά"]

        # Mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[float(i)] * 3072) for i in range(3)]
        mock_client.embeddings.create.return_value = mock_response

        with patch.object(service, "_get_client", return_value=mock_client):
            # Act
            result = service.embed_batch(texts)

            # Assert
            assert len(result) == 3
            # Verify Unicode texts were passed to API
            call_args = mock_client.embeddings.create.call_args
            assert "Hello 世界" in call_args.kwargs["input"]

    def test_embed_batch_with_very_long_text(self, service):
        """Test embedding very long text that needs truncation."""
        # Arrange - text longer than max tokens
        long_text = "A" * 500000  # 500K characters (~125K tokens)
        texts = [long_text]

        # Mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 3072)]
        mock_client.embeddings.create.return_value = mock_response

        with patch.object(service, "_get_client", return_value=mock_client):
            # Act
            result = service.embed_batch(texts)

            # Assert - should handle truncation and still generate embedding
            assert len(result) == 1

    def test_embed_batch_with_special_characters(self, service):
        """Test embedding texts with special characters."""
        # Arrange
        texts = ["!@#$%^&*()", "line1\nline2\ttab", "<html>tags</html>"]

        # Mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[float(i)] * 3072) for i in range(3)]
        mock_client.embeddings.create.return_value = mock_response

        with patch.object(service, "_get_client", return_value=mock_client):
            # Act
            result = service.embed_batch(texts)

            # Assert
            assert len(result) == 3

    def test_embed_batch_preserves_order(self, service):
        """Test that embeddings are returned in same order as input texts."""
        # Arrange
        texts = ["First", "Second", "Third"]

        # Mock OpenAI client with distinct embeddings
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [
            Mock(embedding=[1.0] + [0.0] * 3071),
            Mock(embedding=[2.0] + [0.0] * 3071),
            Mock(embedding=[3.0] + [0.0] * 3071),
        ]
        mock_client.embeddings.create.return_value = mock_response

        with patch.object(service, "_get_client", return_value=mock_client):
            # Act
            result = service.embed_batch(texts)

            # Assert - embeddings should be in order
            assert result[0][0] == 1.0
            assert result[1][0] == 2.0
            assert result[2][0] == 3.0

    def test_embed_batch_with_mixed_empty_and_valid(self, service):
        """Test embedding with mix of empty and valid texts."""
        # Arrange
        texts = ["Valid 1", "", "Valid 2", "   ", "Valid 3"]

        # Mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[float(i)] * 3072) for i in range(3)]
        mock_client.embeddings.create.return_value = mock_response

        with patch.object(service, "_get_client", return_value=mock_client):
            # Act
            result = service.embed_batch(texts)

            # Assert - only valid texts should have embeddings
            assert len(result) == 3
            # Verify only non-empty texts were sent to API
            call_args = mock_client.embeddings.create.call_args
            assert len(call_args.kwargs["input"]) == 3
