"""Unit tests for RetrievalClient."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
import httpx

from ..config import RetrievalClientConfig
from ..exceptions import (
    RetrievalAuthError,
    RetrievalConnectionError,
    RetrievalServiceError,
    RetrievalTimeoutError,
)
from ..models import RetrievalRequest
from ..retrieval_client import RetrievalClient


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    return RetrievalClientConfig(
        base_url="http://test:8002",
        service_token="test-token",
        request_timeout=30.0,
    )


@pytest.fixture
def client(mock_config):
    """Create retrieval client for testing."""
    return RetrievalClient(config=mock_config)


class TestRetrievalClientInit:
    """Test RetrievalClient initialization."""

    def test_init_with_config(self, mock_config):
        """Test initialization with custom config."""
        client = RetrievalClient(config=mock_config)
        assert client.config.base_url == "http://test:8002"
        assert client.config.service_token == "test-token"

    def test_init_without_config(self):
        """Test initialization without config uses defaults from env."""
        with patch.dict("os.environ", {"RAG_SERVICE_TOKEN": "env-token"}):
            client = RetrievalClient()
            assert client.config.service_token == "env-token"


class TestBuildPayload:
    """Test payload building."""

    def test_build_payload_minimal(self, client):
        """Test minimal payload construction."""
        request = RetrievalRequest(query="test")
        payload = client._build_payload(request)

        assert payload["query"] == "test"
        assert payload["user_id"] == "agent@system"
        assert payload["max_chunks"] == 10
        assert payload["similarity_threshold"] == 0.7
        assert payload["enable_query_rewriting"] is True

    def test_build_payload_full(self, client):
        """Test full payload with all optional fields."""
        request = RetrievalRequest(
            query="test",
            user_id="user@test.com",
            system_message="User: test\nRole: admin",
            max_chunks=5,
            similarity_threshold=0.8,
            filters={"type": "document"},
            conversation_history=[{"role": "user", "content": "hello"}],
            enable_query_rewriting=False,
        )
        payload = client._build_payload(request)

        assert payload["query"] == "test"
        assert payload["user_id"] == "user@test.com"
        assert payload["system_message"] == "User: test\nRole: admin"
        assert payload["max_chunks"] == 5
        assert payload["similarity_threshold"] == 0.8
        assert payload["filters"] == {"type": "document"}
        assert payload["conversation_history"] == [{"role": "user", "content": "hello"}]
        assert payload["enable_query_rewriting"] is False


class TestBuildHeaders:
    """Test header building."""

    def test_build_headers(self, client):
        """Test header construction."""
        headers = client._build_headers("user@test.com")

        assert headers["Content-Type"] == "application/json"
        assert headers["X-Service-Token"] == "test-token"
        assert headers["X-User-Email"] == "user@test.com"


class TestExecuteRequest:
    """Test HTTP request execution."""

    @pytest.mark.asyncio
    async def test_execute_request_success(self, client):
        """Test successful HTTP request."""
        # Mock HTTP response
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.json.return_value = {
            "chunks": [
                {
                    "content": "test content",
                    "similarity": 0.9,
                    "metadata": {"file_name": "test.pdf"},
                }
            ],
            "metadata": {"total_chunks": 1, "unique_sources": 1, "avg_similarity": 0.9},
        }

        # Mock httpx.AsyncClient
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("httpx.AsyncClient", return_value=mock_client):
            response = await client._execute_request('{"query":"test"}', {})
            assert response == mock_response
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_request_raises_on_error(self, client):
        """Test HTTP request raises on error status."""
        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error", request=Mock(), response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await client._execute_request('{"query":"test"}', {})


class TestHandleHttpError:
    """Test HTTP error handling."""

    def test_handle_401_raises_auth_error(self, client):
        """Test 401 error raises RetrievalAuthError."""
        mock_response = Mock()
        mock_response.status_code = 401
        error = httpx.HTTPStatusError("Unauthorized", request=Mock(), response=mock_response)

        with pytest.raises(RetrievalAuthError):
            client._handle_http_error(error)

    def test_handle_500_raises_service_error(self, client):
        """Test 500 error raises RetrievalServiceError."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        error = httpx.HTTPStatusError("Server error", request=Mock(), response=mock_response)

        with pytest.raises(RetrievalServiceError) as exc_info:
            client._handle_http_error(error)

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Internal server error"


class TestRetrieve:
    """Test main retrieve method."""

    @pytest.mark.asyncio
    async def test_retrieve_success(self, client):
        """Test successful retrieval."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.json.return_value = {
            "chunks": [
                {
                    "content": "test content",
                    "similarity": 0.9,
                    "metadata": {"file_name": "test.pdf"},
                }
            ],
            "metadata": {
                "total_chunks": 1,
                "unique_sources": 1,
                "avg_similarity": 0.9,
            },
        }

        # Mock httpx.AsyncClient
        mock_http_client = AsyncMock()
        mock_http_client.post.return_value = mock_response
        mock_http_client.__aenter__.return_value = mock_http_client
        mock_http_client.__aexit__.return_value = None

        with patch("httpx.AsyncClient", return_value=mock_http_client):
            chunks = await client.retrieve(query="test")

        assert len(chunks) == 1
        assert chunks[0]["content"] == "test content"
        assert chunks[0]["similarity"] == 0.9

    @pytest.mark.asyncio
    async def test_retrieve_auth_error(self, client):
        """Test retrieval with auth error."""
        # Mock 401 response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=Mock(), response=mock_response
        )

        mock_http_client = AsyncMock()
        mock_http_client.post.return_value = mock_response
        mock_http_client.__aenter__.return_value = mock_http_client
        mock_http_client.__aexit__.return_value = None

        with patch("httpx.AsyncClient", return_value=mock_http_client):
            with pytest.raises(RetrievalAuthError):
                await client.retrieve(query="test")

    @pytest.mark.asyncio
    async def test_retrieve_timeout_error(self, client):
        """Test retrieval with timeout error."""
        mock_http_client = AsyncMock()
        mock_http_client.post.side_effect = httpx.TimeoutException("Timeout")
        mock_http_client.__aenter__.return_value = mock_http_client
        mock_http_client.__aexit__.return_value = None

        with patch("httpx.AsyncClient", return_value=mock_http_client):
            with pytest.raises(RetrievalTimeoutError) as exc_info:
                await client.retrieve(query="test")

        assert exc_info.value.timeout_seconds == 30.0

    @pytest.mark.asyncio
    async def test_retrieve_connection_error(self, client):
        """Test retrieval with connection error."""
        mock_http_client = AsyncMock()
        mock_http_client.post.side_effect = httpx.ConnectError("Cannot connect")
        mock_http_client.__aenter__.return_value = mock_http_client
        mock_http_client.__aexit__.return_value = None

        with patch("httpx.AsyncClient", return_value=mock_http_client):
            with pytest.raises(RetrievalConnectionError) as exc_info:
                await client.retrieve(query="test")

        assert exc_info.value.base_url == "http://test:8002"


class TestParseResponse:
    """Test response parsing."""

    def test_parse_response(self, client):
        """Test response parsing and logging."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "chunks": [
                {"content": "chunk1", "similarity": 0.9, "metadata": {}},
                {"content": "chunk2", "similarity": 0.8, "metadata": {}},
            ],
            "metadata": {
                "total_chunks": 2,
                "unique_sources": 1,
                "avg_similarity": 0.85,
            },
        }

        chunks = client._parse_response(mock_response)

        assert len(chunks) == 2
        assert chunks[0]["content"] == "chunk1"
        assert chunks[1]["content"] == "chunk2"
