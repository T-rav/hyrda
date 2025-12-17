"""Pytest configuration - disable tracing during tests."""
import os

# Set environment variables BEFORE imports (critical for jwt_auth module initialization)
os.environ["OTEL_TRACES_ENABLED"] = "false"
if not os.getenv("SERVICE_TOKEN"):
    os.environ["SERVICE_TOKEN"] = "172b784535a9c8548b9a6f62c257e6410db2cb022e80a4fe31e7b6c3b0f06128"

# Set CONTROL_PLANE_URL to localhost for integration tests
if not os.getenv("CONTROL_PLANE_URL"):
    os.environ["CONTROL_PLANE_URL"] = "https://localhost:6001"

# Set API keys for tests (required for agent initialization)
if not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = "sk-test-key-for-testing-only"
if not os.getenv("LLM_API_KEY"):
    os.environ["LLM_API_KEY"] = "test-llm-api-key"
if not os.getenv("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = "test-anthropic-api-key"

# Set Slack tokens for tests (required for Settings initialization)
if not os.getenv("SLACK_BOT_TOKEN"):
    os.environ["SLACK_BOT_TOKEN"] = "xoxb-test-token"
if not os.getenv("SLACK_APP_TOKEN"):
    os.environ["SLACK_APP_TOKEN"] = "xapp-test-token"

import sys

# Add project root to Python path to access shared module
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

import pytest
from unittest.mock import Mock, AsyncMock, patch


@pytest.fixture(autouse=True)
def mock_openai_client():
    """Mock OpenAI client for all tests to avoid actual API calls."""
    with patch("openai.AsyncOpenAI") as mock_client:
        # Create a mock instance
        mock_instance = Mock()
        mock_instance.chat = Mock()
        mock_instance.chat.completions = Mock()
        mock_instance.chat.completions.create = AsyncMock(return_value=Mock(
            choices=[Mock(message=Mock(content="Test response"))],
            usage=Mock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        ))
        mock_client.return_value = mock_instance
        yield mock_client
