"""Unit tests for LangSmith-to-Langfuse proxy."""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from app import (
    convert_langsmith_to_langfuse,
    validate_api_key,
    app
)
from fastapi.testclient import TestClient
from fastapi.security import HTTPAuthorizationCredentials


@pytest.fixture
def mock_langfuse_client():
    """Mock Langfuse client."""
    client = Mock()

    # Mock observation
    mock_obs = Mock()
    mock_obs.id = "abcd1234567890ab"
    mock_obs.trace_id = "1234567890abcdef1234567890abcdef"

    client.start_observation.return_value = mock_obs
    client.start_generation.return_value = mock_obs
    client.start_span.return_value = mock_obs
    client.flush.return_value = None

    return client


class TestConvertLangsmithToLangfuse:
    """Test LangSmith to Langfuse format conversion."""

    def test_basic_conversion(self):
        """Test basic run data conversion."""
        run_data = {
            "id": "run-123",
            "name": "test-agent",
            "run_type": "chain",
            "inputs": {"query": "test"},
            "outputs": {"result": "success"},
            "start_time": "2024-01-01T00:00:00.000Z",
            "end_time": "2024-01-01T00:00:01.000Z",
            "parent_run_id": None,
            "error": None,
            "extra": {"metadata": "value"}
        }

        result = convert_langsmith_to_langfuse(run_data)

        assert result["run_id"] == "run-123"
        assert result["name"] == "test-agent"
        assert result["run_type"] == "chain"
        assert result["inputs"] == {"query": "test"}
        assert result["outputs"] == {"result": "success"}
        assert isinstance(result["start_time"], datetime)
        assert isinstance(result["end_time"], datetime)
        assert result["parent_id"] is None

    def test_token_usage_extraction_langchain_format(self):
        """Test token usage extraction from LangChain format."""
        run_data = {
            "id": "run-123",
            "name": "ChatOpenAI",
            "run_type": "llm",
            "inputs": {},
            "outputs": {
                "usage_metadata": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "total_tokens": 150
                }
            },
            "extra": {}
        }

        result = convert_langsmith_to_langfuse(run_data)

        assert result["token_usage"] == {
            "input": 100,
            "output": 50,
            "total": 150
        }

    def test_token_usage_extraction_openai_format(self):
        """Test token usage extraction from OpenAI format."""
        run_data = {
            "id": "run-123",
            "name": "ChatOpenAI",
            "run_type": "llm",
            "inputs": {},
            "outputs": {
                "llm_output": {
                    "token_usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 50,
                        "total_tokens": 150
                    }
                }
            },
            "extra": {}
        }

        result = convert_langsmith_to_langfuse(run_data)

        assert result["token_usage"] == {
            "input": 100,
            "output": 50,
            "total": 150
        }

    def test_model_info_extraction(self):
        """Test model information extraction."""
        run_data = {
            "id": "run-123",
            "name": "ChatOpenAI",
            "run_type": "llm",
            "inputs": {},
            "outputs": {},
            "extra": {
                "invocation_params": {
                    "model_name": "gpt-4o-mini",
                    "temperature": 0.7,
                    "max_tokens": 1000,
                    "top_p": 0.9
                }
            }
        }

        result = convert_langsmith_to_langfuse(run_data)

        assert result["model_name"] == "gpt-4o-mini"
        assert result["model_params"] == {
            "temperature": 0.7,
            "max_tokens": 1000,
            "top_p": 0.9
        }

    def test_child_run_conversion(self):
        """Test child run with parent_run_id."""
        run_data = {
            "id": "child-123",
            "name": "tool-call",
            "run_type": "tool",
            "inputs": {},
            "outputs": {},
            "parent_run_id": "parent-456",
            "extra": {}
        }

        result = convert_langsmith_to_langfuse(run_data)

        assert result["run_id"] == "child-123"
        assert result["parent_id"] == "parent-456"


class TestAPIKeyValidation:
    """Test API key validation."""

    def test_valid_api_key(self):
        """Test validation with valid API key."""
        with patch('app.PROXY_API_KEY', 'test-key-123'):
            creds = HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="test-key-123"
            )

            result = validate_api_key(creds)
            assert result is True

    def test_invalid_api_key(self):
        """Test validation with invalid API key."""
        from fastapi import HTTPException

        with patch('app.PROXY_API_KEY', 'test-key-123'):
            creds = HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="wrong-key"
            )

            with pytest.raises(HTTPException) as exc_info:
                validate_api_key(creds)

            assert exc_info.value.status_code == 401

    def test_missing_credentials(self):
        """Test validation with missing credentials."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            validate_api_key(None)

        assert exc_info.value.status_code == 401


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_endpoint(self, mock_langfuse_client):
        """Test /health endpoint returns healthy status."""
        with patch('app.langfuse_client', mock_langfuse_client):
            client = TestClient(app)
            response = client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["langfuse_available"] is True

    def test_health_without_langfuse(self):
        """Test /health endpoint when Langfuse is unavailable."""
        with patch('app.langfuse_client', None):
            client = TestClient(app)
            response = client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["langfuse_available"] is False


class TestTraceIDPropagation:
    """Test trace ID propagation for unified hierarchy."""

    def test_root_observation_stores_trace_id(self, mock_langfuse_client):
        """Test that root observations store trace_id for children."""
        with patch('app.langfuse_client', mock_langfuse_client):
            with patch('app.run_id_map', {}):
                with patch('app.PROXY_API_KEY', 'test-key'):
                    client = TestClient(app)

                    response = client.post(
                        "/runs",
                        json={
                            "id": "root-123",
                            "name": "test-root",
                            "run_type": "chain",
                            "inputs": {},
                            "outputs": {},
                            "parent_run_id": None,
                            "extra": {}
                        },
                        headers={"Authorization": "Bearer test-key"}
                    )

                    assert response.status_code == 200

    def test_child_uses_parent_trace_id(self, mock_langfuse_client):
        """Test that child observations use parent's trace_id."""
        # Setup parent in run_id_map
        parent_trace_id = "abcd1234567890abcdef1234567890ab"

        with patch('app.langfuse_client', mock_langfuse_client):
            with patch('app.run_id_map', {
                "parent-123": {
                    "type": "observation",
                    "langfuse_id": "parentobs123456",
                    "trace_id": parent_trace_id,
                    "observation": Mock()
                }
            }):
                with patch('app.PROXY_API_KEY', 'test-key'):
                    client = TestClient(app)

                    response = client.post(
                        "/runs",
                        json={
                            "id": "child-456",
                            "name": "test-child",
                            "run_type": "llm",
                            "inputs": {},
                            "outputs": {},
                            "parent_run_id": "parent-123",
                            "extra": {
                                "invocation_params": {
                                    "model_name": "gpt-4o-mini"
                                }
                            }
                        },
                        headers={"Authorization": "Bearer test-key"}
                    )

                    assert response.status_code == 200

                    # Verify start_generation was called with correct trace_context
                    call_args = mock_langfuse_client.start_generation.call_args
                    if call_args:
                        kwargs = call_args[1]
                        assert "trace_context" in kwargs
                        assert kwargs["trace_context"]["trace_id"] == parent_trace_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
