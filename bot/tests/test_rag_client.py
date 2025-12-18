"""Tests for RAG client service with HMAC signature authentication."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.rag_client import RAGClient, RAGClientError


class TestRAGClient:
    """Test RAG client with HMAC signature authentication."""

    @pytest.fixture
    def rag_client(self):
        """Create RAG client instance for testing."""
        with patch.dict("os.environ", {"BOT_SERVICE_TOKEN": "test-token-123"}):
            return RAGClient(base_url="http://test-rag:8002")

    @pytest.mark.asyncio
    async def test_generate_response_success(self, rag_client):
        """Test successful response generation with HMAC signatures."""
        # Mock httpx client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Test response",
            "citations": [],
            "metadata": {},
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.is_closed = False

        rag_client._client = mock_client

        # Call generate_response
        result = await rag_client.generate_response(
            query="test query",
            conversation_history=[],
            use_rag=True,
        )

        # Verify response
        assert result["response"] == "Test response"
        assert result["citations"] == []

        # Verify HMAC signature headers were added
        call_args = mock_client.post.call_args
        headers = call_args.kwargs["headers"]

        assert "X-Service-Token" in headers
        assert headers["X-Service-Token"] == "test-token-123"
        assert "X-Request-Timestamp" in headers
        assert "X-Request-Signature" in headers

        # Verify request body was sent as content (not json)
        assert "content" in call_args.kwargs
        assert "json" not in call_args.kwargs

    @pytest.mark.asyncio
    async def test_generate_response_with_document(self, rag_client):
        """Test response generation with document content."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Document response"}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.is_closed = False

        rag_client._client = mock_client

        result = await rag_client.generate_response(
            query="test query",
            conversation_history=[],
            document_content="Test document content",
            document_filename="test.pdf",
        )

        assert result["response"] == "Document response"

        # Verify document content was included in request
        call_args = mock_client.post.call_args
        request_body = json.loads(call_args.kwargs["content"])
        assert request_body["document_content"] == "Test document content"
        assert request_body["document_filename"] == "test.pdf"

    @pytest.mark.asyncio
    async def test_generate_response_authentication_failure(self, rag_client):
        """Test handling of 401 authentication failure."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.is_closed = False

        rag_client._client = mock_client

        with pytest.raises(RAGClientError, match="Authentication failed"):
            await rag_client.generate_response(
                query="test query",
                conversation_history=[],
            )

    @pytest.mark.asyncio
    async def test_generate_response_server_error(self, rag_client):
        """Test handling of 500 server error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.is_closed = False

        rag_client._client = mock_client

        with pytest.raises(RAGClientError, match="RAG service failed: 500"):
            await rag_client.generate_response(
                query="test query",
                conversation_history=[],
            )

    @pytest.mark.asyncio
    async def test_hmac_signature_consistency(self, rag_client):
        """Test that HMAC signature is generated consistently."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Test"}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.is_closed = False

        rag_client._client = mock_client

        # Make call to generate response
        await rag_client.generate_response(
            query="test",
            conversation_history=[],
            use_rag=True,
        )

        # Get content from call
        content = mock_client.post.call_args.kwargs["content"]

        # Verify content matches expected structure
        parsed_content = json.loads(content)
        assert "query" in parsed_content
        assert parsed_content["query"] == "test"

    @pytest.mark.asyncio
    async def test_client_initialization_without_token(self):
        """Test client initialization warns when token is missing."""
        with (
            patch.dict("os.environ", {"BOT_SERVICE_TOKEN": ""}, clear=True),
            patch("services.rag_client.logger") as mock_logger,
        ):
            client = RAGClient()
            assert client.service_token == ""
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_client(self, rag_client):
        """Test closing HTTP client."""
        mock_client = AsyncMock()
        mock_client.is_closed = False
        rag_client._client = mock_client

        await rag_client.close()

        mock_client.aclose.assert_called_once()
        assert rag_client._client is None
