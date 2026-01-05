"""Tests for agent API authentication with service tokens."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


class TestAgentAPIServiceTokenAuth:
    """Test service token authentication in agents API."""

    @pytest.mark.asyncio
    async def test_invoke_agent_with_valid_rag_service_token(self):
        """Test that RAG service can invoke agents with RAG_SERVICE_TOKEN."""
        from api.agents import AgentInvokeRequest, invoke_agent

        # Mock request with RAG service token
        mock_request = MagicMock()
        mock_request.headers = {
            "X-Service-Token": "rag-service-secret-token-test123"
        }

        # Mock agent client
        with patch("api.agents.agent_client") as mock_agent_client:
            with patch("shared.utils.jwt_auth.verify_service_token") as mock_verify:
                # Mock successful token verification
                mock_verify.return_value = {"service": "rag"}

                # Mock agent discovery
                mock_agent_client.discover_agent = AsyncMock(
                    return_value={"agent_name": "profile", "enabled": True}
                )

                # Mock agent invocation (invoke, not execute_agent)
                mock_agent_client.invoke = AsyncMock(
                    return_value={
                        "response": "Test profile response",
                        "metadata": {},
                    }
                )

                # Call endpoint
                result = await invoke_agent(
                    agent_name="profile",
                    request=AgentInvokeRequest(query="test company", context={}),
                    http_request=mock_request,
                )

                # Verify token was verified with correct value
                mock_verify.assert_called_once_with("rag-service-secret-token-test123")

                # Verify agent was executed
                assert result.response == "Test profile response"

    @pytest.mark.asyncio
    async def test_invoke_agent_with_valid_bot_service_token(self):
        """Test that bot service can invoke agents with BOT_SERVICE_TOKEN."""
        from api.agents import AgentInvokeRequest, invoke_agent

        # Mock request with bot service token
        mock_request = MagicMock()
        mock_request.headers = {
            "X-Service-Token": "bot-service-secret-token-test123"
        }

        # Mock agent client
        with patch("api.agents.agent_client") as mock_agent_client:
            with patch("shared.utils.jwt_auth.verify_service_token") as mock_verify:
                # Mock successful token verification
                mock_verify.return_value = {"service": "bot"}

                # Mock agent discovery
                mock_agent_client.discover_agent = AsyncMock(
                    return_value={"agent_name": "profile", "enabled": True}
                )

                # Mock agent execution
                mock_agent_client.invoke = AsyncMock(
                    return_value={
                        "response": "Test response",
                        "metadata": {},
                    }
                )

                # Call endpoint
                result = await invoke_agent(
                    agent_name="profile",
                    request=AgentInvokeRequest(query="test company", context={}),
                    http_request=mock_request,
                )

                # Verify token was verified
                mock_verify.assert_called_once_with("bot-service-secret-token-test123")
                assert result.response == "Test response"

    @pytest.mark.asyncio
    async def test_invoke_agent_rejects_invalid_service_token(self):
        """Test that invalid service tokens are rejected."""
        from api.agents import AgentInvokeRequest, invoke_agent

        # Mock request with invalid token
        mock_request = MagicMock()
        mock_request.headers = {
            "X-Service-Token": "invalid-token"
        }

        with patch("api.agents.agent_client") as mock_agent_client:
            with patch("shared.utils.jwt_auth.verify_service_token") as mock_verify:
                # Mock failed token verification
                mock_verify.return_value = None

                # Mock agent discovery
                mock_agent_client.discover_agent = AsyncMock(
                    return_value={"agent_name": "profile", "enabled": True}
                )

                # Call endpoint - should raise 401
                with pytest.raises(HTTPException) as exc_info:
                    await invoke_agent(
                        agent_name="profile",
                        request=AgentInvokeRequest(query="test", context={}),
                        http_request=mock_request,
                    )

                assert exc_info.value.status_code == 401
                assert "Authentication required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invoke_agent_rejects_missing_service_token(self):
        """Test that requests without service tokens are rejected."""
        from api.agents import AgentInvokeRequest, invoke_agent

        # Mock request without token
        mock_request = MagicMock()
        mock_request.headers = {}

        with patch("api.agents.agent_client") as mock_agent_client:
            with patch("shared.utils.jwt_auth.verify_service_token") as mock_verify:
                # Mock agent discovery
                mock_agent_client.discover_agent = AsyncMock(
                    return_value={"agent_name": "profile", "enabled": True}
                )

                # Call endpoint - should raise 401
                with pytest.raises(HTTPException) as exc_info:
                    await invoke_agent(
                        agent_name="profile",
                        request=AgentInvokeRequest(query="test", context={}),
                        http_request=mock_request,
                    )

                assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_stream_agent_with_valid_rag_service_token(self):
        """Test that RAG service can stream agents with RAG_SERVICE_TOKEN."""
        from api.agents import AgentInvokeRequest, stream_agent

        # Mock request with RAG service token
        mock_request = MagicMock()
        mock_request.headers = {
            "X-Service-Token": "rag-service-secret-token-test123"
        }

        with patch("api.agents.agent_client") as mock_agent_client:
            with patch("shared.utils.jwt_auth.verify_service_token") as mock_verify:
                # Mock successful token verification
                mock_verify.return_value = {"service": "rag"}

                # Mock agent discovery
                mock_agent_client.discover_agent = AsyncMock(
                    return_value={"agent_name": "profile", "enabled": True}
                )

                # Mock streaming response
                async def mock_stream():
                    yield "Test"
                    yield " streaming"
                    yield " response"

                mock_agent_client.stream_agent_execution = mock_stream

                # Call endpoint
                response = await stream_agent(
                    agent_name="profile",
                    request=AgentInvokeRequest(query="test company", context={}),
                    http_request=mock_request,
                )

                # Verify token was verified
                mock_verify.assert_called_once_with("rag-service-secret-token-test123")

    @pytest.mark.asyncio
    async def test_stream_agent_rejects_invalid_service_token(self):
        """Test that streaming rejects invalid service tokens."""
        from api.agents import AgentInvokeRequest, stream_agent

        # Mock request with invalid token
        mock_request = MagicMock()
        mock_request.headers = {
            "X-Service-Token": "invalid-token"
        }

        with patch("api.agents.agent_client") as mock_agent_client:
            with patch("shared.utils.jwt_auth.verify_service_token") as mock_verify:
                # Mock failed token verification
                mock_verify.return_value = None

                # Mock agent discovery
                mock_agent_client.discover_agent = AsyncMock(
                    return_value={"agent_name": "profile", "enabled": True}
                )

                # Call endpoint - should raise 401
                with pytest.raises(HTTPException) as exc_info:
                    await stream_agent(
                        agent_name="profile",
                        request=AgentInvokeRequest(query="test", context={}),
                        http_request=mock_request,
                    )

                assert exc_info.value.status_code == 401
                assert "Authentication required" in exc_info.value.detail


class TestSharedJWTAuthServiceTokens:
    """Test SERVICE_TOKENS configuration in shared JWT auth."""

    def test_service_tokens_includes_rag_service(self):
        """Test that SERVICE_TOKENS includes rag service."""
        import sys
        sys.path.insert(0, "/app")
        from shared.utils.jwt_auth import SERVICE_TOKENS

        # Verify all service tokens are registered
        assert "rag" in SERVICE_TOKENS
        assert "bot" in SERVICE_TOKENS
        assert "control-plane" in SERVICE_TOKENS
        assert "librechat" in SERVICE_TOKENS
        # Ensure no "generic" fallback (security risk)
        assert "generic" not in SERVICE_TOKENS

    def test_verify_service_token_accepts_rag_token(self):
        """Test that verify_service_token accepts RAG_SERVICE_TOKEN."""
        import os
        import sys
        sys.path.insert(0, "/app")

        # Set test tokens
        test_rag_token = "test-rag-token-123"
        with patch.dict(os.environ, {"RAG_SERVICE_TOKEN": test_rag_token}):
            # Reimport to pick up new env var
            import importlib

            from shared.utils import jwt_auth
            importlib.reload(jwt_auth)

            # Verify token
            service_info = jwt_auth.verify_service_token(test_rag_token)

            assert service_info is not None
            assert service_info["service"] == "rag"

    def test_verify_service_token_rejects_invalid_token(self):
        """Test that verify_service_token rejects invalid tokens."""
        import sys
        sys.path.insert(0, "/app")
        from shared.utils.jwt_auth import verify_service_token

        # Try invalid token
        service_info = verify_service_token("invalid-token-xyz")

        assert service_info is None
