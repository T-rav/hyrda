"""
Integration Tests for RAG API Endpoints

Tests the full API flow for:
- /api/v1/chat/completions - RAG generation endpoint
- /api/v1/retrieve - Vector retrieval endpoint
- /api/v1/status - Service status endpoint

Mark: integration (run separately from unit tests)
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import app
from dependencies.auth import require_service_auth

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
def client():
    """Create test client for API testing."""
    return TestClient(app)


@pytest.fixture
def authenticated_client():
    """Create test client with auth bypassed."""

    # Override the auth dependency to bypass authentication
    async def mock_auth():
        return {
            "auth_method": "service_token",
            "user_email": "test@test.com",
            "is_internal_service": True,
        }

    app.dependency_overrides[require_service_auth] = mock_auth
    client = TestClient(app)
    yield client
    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
def mock_service_token():
    """Mock service token for authentication."""
    return "test-service-token"


@pytest.fixture
def auth_headers(mock_service_token):
    """Create authentication headers for API calls."""
    return {"X-Service-Token": mock_service_token}


class TestChatCompletionsEndpoint:
    """Integration tests for /api/v1/chat/completions endpoint."""

    def test_chat_completions_returns_401_without_auth(self, client):
        """Test that endpoint requires authentication."""
        response = client.post(
            "/api/v1/chat/completions",
            json={"query": "What is Python?"},
        )

        # Should require auth
        assert response.status_code in [401, 403]

    def test_chat_completions_validates_request_body(self, authenticated_client):
        """Test that endpoint validates request body schema."""
        # Empty body should fail validation
        response = authenticated_client.post(
            "/api/v1/chat/completions",
            json={},
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.skip(reason="Requires full LLM/agent service mocking - run with services")
    def test_chat_completions_accepts_valid_request(self, authenticated_client):
        """Test that endpoint accepts valid request and returns response.

        NOTE: This test requires extensive mocking of LLM and agent services.
        Run with real services for full integration testing.
        """
        pass

    @pytest.mark.skip(reason="Requires full LLM/agent service mocking - run with services")
    def test_chat_completions_alias_route(self, authenticated_client):
        """Test that /chat/completions alias works same as /v1/chat/completions.

        NOTE: This test requires extensive mocking of LLM and agent services.
        Run with real services for full integration testing.
        """
        pass


class TestRetrieveEndpoint:
    """Integration tests for /api/v1/retrieve endpoint."""

    def test_retrieve_returns_401_without_auth(self, client):
        """Test that retrieve endpoint requires authentication."""
        response = client.post(
            "/api/v1/retrieve",
            json={"query": "test query"},
        )

        assert response.status_code in [401, 403]

    def test_retrieve_validates_request(self, authenticated_client):
        """Test that retrieve validates request body."""
        response = authenticated_client.post(
            "/api/v1/retrieve",
            json={},  # Missing required query
        )

        assert response.status_code == 422

    @pytest.mark.skip(reason="Requires embedding service - run with OPENAI_API_KEY")
    def test_retrieve_returns_chunks_on_success(self, authenticated_client):
        """Test that retrieve returns chunks from vector store.

        NOTE: This test requires embedding service (OpenAI API key).
        Run with real services for full integration testing.
        """
        pass


class TestStatusEndpoint:
    """Integration tests for /api/v1/status endpoint."""

    def test_status_endpoint_returns_service_info(self, authenticated_client):
        """Test that status endpoint returns service configuration."""
        response = authenticated_client.get("/api/v1/status")

        assert response.status_code == 200
        data = response.json()

        # Verify required fields
        assert "status" in data
        assert "vector_enabled" in data
        assert "llm_provider" in data
        assert "embedding_provider" in data
        assert "capabilities" in data

    def test_status_alias_route(self, authenticated_client):
        """Test that /status alias works same as /v1/status."""
        response = authenticated_client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data


class TestTracingPropagation:
    """Integration tests for trace propagation through API."""

    def test_trace_id_header_is_returned(self, authenticated_client):
        """Test that X-Trace-Id header is returned in response."""
        response = authenticated_client.get("/api/v1/status")

        assert response.status_code == 200
        assert "X-Trace-Id" in response.headers

    def test_incoming_trace_id_is_preserved(self, authenticated_client):
        """Test that incoming X-Trace-Id is preserved in response."""
        incoming_trace = "trace_testincoming"

        response = authenticated_client.get(
            "/api/v1/status",
            headers={"X-Trace-Id": incoming_trace},
        )

        assert response.status_code == 200
        assert response.headers.get("X-Trace-Id") == incoming_trace


class TestErrorHandling:
    """Integration tests for API error handling."""

    def test_invalid_endpoint_returns_404(self, client):
        """Test that invalid endpoints return 404."""
        response = client.get("/api/v1/nonexistent")

        assert response.status_code == 404

    def test_method_not_allowed_returns_405(self, client):
        """Test that wrong HTTP method returns 405."""
        response = client.get("/api/v1/chat/completions")  # GET instead of POST

        assert response.status_code == 405

    def test_internal_error_returns_500(self, authenticated_client):
        """Test that internal errors return 500 with error details."""
        with patch("api.rag.get_llm_service", side_effect=Exception("Database error")):
            response = authenticated_client.post(
                "/api/v1/chat/completions",
                json={"query": "test", "use_rag": False},
            )

            assert response.status_code == 500
