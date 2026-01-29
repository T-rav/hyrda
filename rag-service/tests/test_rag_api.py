"""Comprehensive tests for RAG API endpoints.

Tests the main /v1/chat/completions endpoint and status endpoint.

NOTE: Most tests are marked as integration tests since they require full app setup.
Run with: pytest -m integration
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

# Mark most API tests as integration tests
pytestmark = pytest.mark.integration


class TestChatCompletionsEndpoint:
    """Test /v1/chat/completions endpoint."""

    @patch("api.rag.get_routing_service")
    @patch("api.rag.get_llm_service")
    def test_simple_rag_query_without_agent(
        self, mock_get_llm, mock_get_routing, client, signed_headers
    ):
        """Test simple RAG query that doesn't need agent routing."""
        # Mock routing service to return None (no agent needed)
        mock_routing = Mock()
        mock_routing.detect_agent.return_value = None
        mock_get_routing.return_value = mock_routing

        # Mock LLM service to return a response
        mock_llm = Mock()
        mock_llm.get_response = AsyncMock(return_value="The answer is 42.")
        mock_get_llm.return_value = mock_llm

        payload = {
            "query": "What is the answer to life?",
            "conversation_history": [],
            "use_rag": True,
            "user_id": "test_user",
        }

        response = client.post(
            "/api/v1/chat/completions",
            json=payload,
            headers=signed_headers(payload),
        )

        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert data["response"] == "The answer is 42."
        assert "citations" in data
        assert "metadata" in data
        assert data["metadata"]["routed_to_agent"] is False

    @patch("api.rag.get_routing_service")
    @patch("api.rag.get_llm_service")
    def test_custom_system_message_is_used(
        self, mock_get_llm, mock_get_routing, client, signed_headers
    ):
        """Test that custom system_message is passed to llm_service."""
        # Mock routing service to return None (no agent)
        mock_routing = Mock()
        mock_routing.detect_agent.return_value = None
        mock_get_routing.return_value = mock_routing

        # Mock LLM service
        mock_llm = Mock()
        mock_llm.get_response = AsyncMock(return_value="Custom prompt response")
        mock_get_llm.return_value = mock_llm

        custom_prompt = "You are a permission-aware assistant. User has access to projects A, B, C."
        payload = {
            "query": "What projects can I see?",
            "conversation_history": [],
            "system_message": custom_prompt,
            "use_rag": True,
        }

        response = client.post(
            "/api/v1/chat/completions",
            json=payload,
            headers=signed_headers(payload),
        )

        assert response.status_code == 200

        # Verify system_message was passed to llm_service
        mock_llm.get_response.assert_called_once()
        call_kwargs = mock_llm.get_response.call_args.kwargs
        assert call_kwargs["system_message"] == custom_prompt

    @patch("api.rag.get_routing_service")
    @patch("api.rag.get_llm_service")
    def test_no_system_message_uses_default(
        self, mock_get_llm, mock_get_routing, client, signed_headers
    ):
        """Test that when no system_message provided, None is passed (uses default)."""
        # Mock routing service to return None (no agent)
        mock_routing = Mock()
        mock_routing.detect_agent.return_value = None
        mock_get_routing.return_value = mock_routing

        # Mock LLM service
        mock_llm = Mock()
        mock_llm.get_response = AsyncMock(return_value="Default prompt response")
        mock_get_llm.return_value = mock_llm

        payload = {
            "query": "What is the answer?",
            "conversation_history": [],
            "use_rag": True,
            # No system_message provided
        }

        response = client.post(
            "/api/v1/chat/completions",
            json=payload,
            headers=signed_headers(payload),
        )

        assert response.status_code == 200

        # Verify system_message=None was passed (will use default in llm_service)
        mock_llm.get_response.assert_called_once()
        call_kwargs = mock_llm.get_response.call_args.kwargs
        assert call_kwargs["system_message"] is None

    @patch("api.rag.get_routing_service")
    @patch("api.rag.get_agent_client")
    def test_query_with_agent_routing(
        self, mock_get_agent_client, mock_get_routing, client, signed_headers
    ):
        """Test query that gets routed to an agent."""
        # Mock routing service to detect agent
        mock_routing = Mock()
        mock_routing.detect_agent.return_value = "research"
        mock_get_routing.return_value = mock_routing

        # Mock agent client with proper async generator
        mock_agent_client = Mock()

        # Create a proper async generator that can be awaited
        async def mock_stream_gen():
            # Yield individual chunks as the streaming API expects
            yield "Research results here..."

        # Make stream_agent return a fresh generator each time it's called
        def create_mock_stream(*args, **kwargs):
            return mock_stream_gen()

        mock_agent_client.stream_agent = create_mock_stream
        mock_get_agent_client.return_value = mock_agent_client

        payload = {
            "query": "/research quantum computing",
            "conversation_history": [],
            "user_id": "test_user",
        }

        response = client.post(
            "/api/v1/chat/completions",
            json=payload,
            headers=signed_headers(payload),
        )

        assert response.status_code == 200
        # Agent routing returns a streaming response (SSE format)
        # Check the response is text/event-stream
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        # Read the streaming response content
        content = response.text
        assert "Research results here" in content

    def test_missing_required_fields(self, client, signed_headers):
        """Test request with missing required fields."""
        payload = {
            "conversation_history": [],  # Missing 'query' field
        }

        response = client.post(
            "/api/v1/chat/completions",
            json=payload,
            headers=signed_headers(payload),
        )

        assert response.status_code == 422  # Validation error

    def test_missing_authentication(self, unauth_client):
        """Test request without authentication token."""
        payload = {
            "query": "Test query",
            "conversation_history": [],
        }

        response = unauth_client.post("/api/v1/chat/completions", json=payload)
        assert response.status_code == 401

    @patch("api.rag.get_routing_service")
    @patch("api.rag.get_llm_service")
    def test_query_with_conversation_history(
        self, mock_get_llm, mock_get_routing, client, signed_headers
    ):
        """Test query with conversation history."""
        mock_routing = Mock()
        mock_routing.detect_agent.return_value = None
        mock_get_routing.return_value = mock_routing

        mock_llm = Mock()
        mock_llm.get_response = AsyncMock(return_value="Based on our previous discussion...")
        mock_get_llm.return_value = mock_llm

        payload = {
            "query": "Can you elaborate on that?",
            "conversation_history": [
                {"role": "user", "content": "What is RAG?"},
                {
                    "role": "assistant",
                    "content": "RAG stands for Retrieval-Augmented Generation...",
                },
            ],
            "user_id": "test_user",
        }

        response = client.post(
            "/api/v1/chat/completions",
            json=payload,
            headers=signed_headers(payload),
        )

        assert response.status_code == 200
        data = response.json()
        assert "response" in data

    @patch("api.rag.get_routing_service")
    @patch("api.rag.get_llm_service")
    def test_query_with_document_content(
        self, mock_get_llm, mock_get_routing, client, signed_headers
    ):
        """Test query with uploaded document content."""
        mock_routing = Mock()
        mock_routing.detect_agent.return_value = None
        mock_get_routing.return_value = mock_routing

        mock_llm = Mock()
        mock_llm.get_response = AsyncMock(return_value="Based on the document provided...")
        mock_get_llm.return_value = mock_llm

        payload = {
            "query": "Summarize this document",
            "conversation_history": [],
            "document_content": "This is test document content...",
            "document_filename": "test.pdf",
            "user_id": "test_user",
        }

        response = client.post(
            "/api/v1/chat/completions",
            json=payload,
            headers=signed_headers(payload),
        )

        assert response.status_code == 200
        data = response.json()
        assert "response" in data

    @patch("api.rag.get_routing_service")
    @patch("api.rag.get_llm_service")
    def test_query_with_rag_disabled(self, mock_get_llm, mock_get_routing, client, signed_headers):
        """Test query with RAG retrieval disabled."""
        mock_routing = Mock()
        mock_routing.detect_agent.return_value = None
        mock_get_routing.return_value = mock_routing

        mock_llm = Mock()
        mock_llm.get_response = AsyncMock(return_value="Response without RAG retrieval")
        mock_get_llm.return_value = mock_llm

        payload = {
            "query": "Simple question",
            "conversation_history": [],
            "use_rag": False,  # RAG disabled
            "user_id": "test_user",
        }

        response = client.post(
            "/api/v1/chat/completions",
            json=payload,
            headers=signed_headers(payload),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["metadata"]["rag_used"] is False

    @patch("api.rag.get_routing_service")
    def test_error_handling_when_generation_fails(self, mock_get_routing, client, signed_headers):
        """Test error handling when LLM generation fails."""
        mock_routing = Mock()
        mock_routing.detect_agent.side_effect = Exception("Service unavailable")
        mock_get_routing.return_value = mock_routing

        payload = {
            "query": "Test query",
            "conversation_history": [],
        }

        response = client.post(
            "/api/v1/chat/completions",
            json=payload,
            headers=signed_headers(payload),
        )

        assert response.status_code == 500
        assert "detail" in response.json()

    def test_alias_endpoint_without_v1_prefix(self, client, signed_headers):
        """Test /chat/completions alias endpoint (without /v1 prefix)."""
        with patch("api.rag.get_routing_service") as mock_routing:
            with patch("api.rag.get_llm_service") as mock_llm:
                mock_routing.return_value.detect_agent.return_value = None
                mock_llm.return_value.get_response = AsyncMock(return_value="Response")

                payload = {"query": "Test", "conversation_history": []}

                response = client.post(
                    "/api/chat/completions",
                    json=payload,
                    headers=signed_headers(payload),
                )

                assert response.status_code == 200


class TestStatusEndpoint:
    """Test /v1/status endpoint."""

    @patch("api.rag.get_agent_client")
    @patch("api.rag.create_vector_store")
    @patch("api.rag.get_settings")
    def test_status_endpoint_with_vector_enabled(
        self,
        mock_get_settings,
        mock_create_vector_store,
        mock_get_agent_client,
        client,
        auth_headers,
    ):
        """Test status endpoint when vector DB is enabled."""
        mock_settings = Mock()
        mock_settings.vector.enabled = True
        mock_settings.vector.provider = "qdrant"
        mock_settings.llm.provider = "openai"
        mock_settings.embedding.provider = "openai"
        mock_settings.rag.enable_query_rewriting = False
        mock_settings.search.tavily_api_key = None
        mock_settings.search.perplexity_enabled = False
        mock_settings.search.perplexity_api_key = None
        mock_get_settings.return_value = mock_settings

        # Mock vector store health check
        mock_vector_store = AsyncMock()
        mock_vector_store.get_collection_info = AsyncMock(return_value={"vectors_count": 100})
        mock_create_vector_store.return_value = mock_vector_store

        # Mock agent client health check
        mock_agent_client = AsyncMock()
        mock_agent_client.list_agents = AsyncMock(return_value=[{"name": "test_agent"}])
        mock_get_agent_client.return_value = mock_agent_client

        response = client.get("/api/v1/status", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["vector_enabled"] is True
        assert data["llm_provider"] == "openai"
        assert data["embedding_provider"] == "openai"
        assert "capabilities" in data

    @patch("api.rag.get_agent_client")
    @patch("api.rag.get_settings")
    def test_status_endpoint_with_vector_disabled(
        self, mock_get_settings, mock_get_agent_client, client, auth_headers
    ):
        """Test status endpoint when vector DB is disabled."""
        mock_settings = Mock()
        mock_settings.vector.enabled = False
        mock_settings.llm.provider = "anthropic"
        mock_settings.embedding.provider = "openai"
        mock_settings.rag.enable_query_rewriting = False
        mock_settings.search.tavily_api_key = None
        mock_settings.search.perplexity_enabled = False
        mock_settings.search.perplexity_api_key = None
        mock_get_settings.return_value = mock_settings

        # Mock agent client health check
        mock_agent_client = AsyncMock()
        mock_agent_client.list_agents = AsyncMock(return_value=[{"name": "test_agent"}])
        mock_get_agent_client.return_value = mock_agent_client

        response = client.get("/api/v1/status", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["vector_enabled"] is False

    @patch("api.rag.get_agent_client")
    @patch("api.rag.create_vector_store")
    def test_status_alias_endpoint(
        self, mock_create_vector_store, mock_get_agent_client, client, auth_headers
    ):
        """Test /status alias endpoint (without /v1 prefix)."""
        with patch("api.rag.get_settings") as mock_settings:
            mock_settings.return_value.vector.enabled = True
            mock_settings.return_value.llm.provider = "openai"
            mock_settings.return_value.embedding.provider = "openai"
            mock_settings.return_value.rag.enable_query_rewriting = False
            mock_settings.return_value.search.tavily_api_key = None
            mock_settings.return_value.search.perplexity_enabled = False
            mock_settings.return_value.search.perplexity_api_key = None

            # Mock vector store health check
            mock_vector_store = AsyncMock()
            mock_vector_store.get_collection_info = AsyncMock(return_value={"vectors_count": 100})
            mock_create_vector_store.return_value = mock_vector_store

            # Mock agent client health check
            mock_agent_client = AsyncMock()
            mock_agent_client.list_agents = AsyncMock(return_value=[{"name": "test_agent"}])
            mock_get_agent_client.return_value = mock_agent_client

            response = client.get("/api/status", headers=auth_headers)
            assert response.status_code == 200


class TestRequestValidation:
    """Test request validation and edge cases."""

    def test_empty_query(self, client, signed_headers):
        """Test request with empty query string."""
        payload = {
            "query": "",  # Empty query
            "conversation_history": [],
        }

        response = client.post(
            "/api/v1/chat/completions",
            json=payload,
            headers=signed_headers(payload),
        )

        # Should accept but may return validation error or empty response
        assert response.status_code in [200, 422]

    def test_very_long_query(self, client, signed_headers):
        """Test request with very long query string."""
        with patch("api.rag.get_routing_service") as mock_routing:
            with patch("api.rag.get_llm_service") as mock_llm:
                mock_routing.return_value.detect_agent.return_value = None
                mock_llm.return_value.get_response = AsyncMock(return_value="Response")

                payload = {
                    "query": "Test query " * 1000,  # Very long query
                    "conversation_history": [],
                }

                response = client.post(
                    "/api/v1/chat/completions",
                    json=payload,
                    headers=signed_headers(payload),
                )

                # Should handle gracefully
                assert response.status_code in [200, 413, 422]

    def test_invalid_conversation_history_format(self, client, signed_headers):
        """Test request with invalid conversation history format."""
        payload = {
            "query": "Test",
            "conversation_history": "invalid format",  # Should be a list
        }

        response = client.post(
            "/api/v1/chat/completions",
            json=payload,
            headers=signed_headers(payload),
        )

        assert response.status_code == 422  # Validation error


class TestStreamingEndpoints:
    """Test streaming-specific functionality for RAG API."""

    @patch("api.rag.get_routing_service")
    @patch("api.rag.get_agent_client")
    def test_sse_format_validation(
        self, mock_get_agent_client, mock_get_routing, client, signed_headers
    ):
        """Test that streaming responses use proper SSE format."""
        # Arrange
        mock_routing = Mock()
        mock_routing.detect_agent.return_value = "research"
        mock_get_routing.return_value = mock_routing

        mock_agent_client = Mock()

        async def mock_stream_gen():
            yield "chunk1"
            yield "chunk2"
            yield "chunk3"

        def create_mock_stream(*args, **kwargs):
            return mock_stream_gen()

        mock_agent_client.stream_agent = create_mock_stream
        mock_get_agent_client.return_value = mock_agent_client

        payload = {
            "query": "/research AI safety",
            "conversation_history": [],
            "user_id": "test_user",
        }

        # Act
        response = client.post(
            "/api/v1/chat/completions",
            json=payload,
            headers=signed_headers(payload),
        )

        # Assert
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        assert response.headers["Cache-Control"] == "no-cache"
        assert response.headers["Connection"] == "keep-alive"
        assert response.headers["X-Accel-Buffering"] == "no"

        # Verify SSE format: data: {chunk}\n\n
        content = response.text
        assert "data: chunk1\n\n" in content
        assert "data: chunk2\n\n" in content
        assert "data: chunk3\n\n" in content

    @patch("api.rag.get_routing_service")
    @patch("api.rag.get_agent_client")
    def test_streaming_with_context_propagation(
        self, mock_get_agent_client, mock_get_routing, client, signed_headers
    ):
        """Test that context (channel, thread_ts) is propagated to agent."""
        # Arrange
        mock_routing = Mock()
        mock_routing.detect_agent.return_value = "research"
        mock_get_routing.return_value = mock_routing

        mock_agent_client = Mock()
        captured_context = {}

        async def mock_stream_gen():
            yield "result"

        def create_mock_stream(*args, **kwargs):
            # Capture the context passed to agent
            nonlocal captured_context
            captured_context = kwargs.get("context", {})
            return mock_stream_gen()

        mock_agent_client.stream_agent = create_mock_stream
        mock_get_agent_client.return_value = mock_agent_client

        payload = {
            "query": "/research quantum computing",
            "conversation_history": [],
            "user_id": "test_user",
            "context": {
                "channel": "C12345",
                "thread_ts": "1234567890.123456",
            },
        }

        # Act
        response = client.post(
            "/api/v1/chat/completions",
            json=payload,
            headers=signed_headers(payload),
        )

        # Assert
        assert response.status_code == 200
        assert captured_context.get("channel") == "C12345"
        assert captured_context.get("thread_ts") == "1234567890.123456"

    @patch("api.rag.get_routing_service")
    @patch("api.rag.get_agent_client")
    def test_metadata_header_parsing_deep_search(
        self, mock_get_agent_client, mock_get_routing, client, signed_headers
    ):
        """Test X-Conversation-Metadata header parsing for deep search."""
        # Arrange
        mock_routing = Mock()
        mock_routing.detect_agent.return_value = None  # Will be overridden by metadata
        mock_get_routing.return_value = mock_routing

        mock_agent_client = Mock()
        captured_agent_name = None
        captured_context = {}

        async def mock_stream_gen():
            yield "deep research results"

        def create_mock_stream(agent_name, *args, **kwargs):
            nonlocal captured_agent_name, captured_context
            captured_agent_name = agent_name
            captured_context = kwargs.get("context", {})
            return mock_stream_gen()

        mock_agent_client.stream_agent = create_mock_stream
        mock_get_agent_client.return_value = mock_agent_client

        payload = {
            "query": "Research AI trends",
            "conversation_history": [],
            "user_id": "test_user",
        }

        headers = signed_headers(payload)
        headers["X-Conversation-Metadata"] = (
            '{"deepSearchEnabled": true, "researchDepth": "comprehensive"}'
        )

        # Act
        response = client.post(
            "/api/v1/chat/completions",
            json=payload,
            headers=headers,
        )

        # Assert
        assert response.status_code == 200
        assert captured_agent_name == "research"
        assert captured_context.get("research_depth") == "comprehensive"
