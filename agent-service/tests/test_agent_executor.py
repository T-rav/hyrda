"""Unit tests for AgentExecutor (dual-mode execution router)."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.agent_executor import AgentExecutor, ExecutionMode


class TestAgentExecutorInitialization:
    """Test AgentExecutor initialization with different modes."""

    def test_embedded_mode_initialization(self):
        """Test initialization in embedded mode (default)."""
        with patch.dict(os.environ, {"AGENT_EXECUTION_MODE": "embedded"}, clear=False):
            executor = AgentExecutor()

            assert executor.mode == ExecutionMode.EMBEDDED
            assert executor.langgraph_client is None

    def test_embedded_mode_default(self):
        """Test that embedded mode is default when env var not set."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove AGENT_EXECUTION_MODE if it exists
            os.environ.pop("AGENT_EXECUTION_MODE", None)
            executor = AgentExecutor()

            assert executor.mode == ExecutionMode.EMBEDDED

    @patch("services.agent_executor.get_client")
    def test_cloud_mode_initialization(self, mock_get_client):
        """Test initialization in cloud mode."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        with patch.dict(
            os.environ,
            {
                "AGENT_EXECUTION_MODE": "cloud",
                "LANGGRAPH_CLOUD_URL": "https://test.langraph.api",
                "LANGGRAPH_API_KEY": "test-key",
            },
            clear=False,
        ):
            executor = AgentExecutor()

            assert executor.mode == ExecutionMode.CLOUD
            assert executor.langgraph_url == "https://test.langraph.api"
            assert executor.langgraph_api_key == "test-key"
            assert executor.langgraph_client == mock_client
            mock_get_client.assert_called_once_with(
                url="https://test.langraph.api", api_key="test-key"
            )

    def test_cloud_mode_missing_url_raises_error(self):
        """Test that cloud mode without URL raises ValueError."""
        with patch.dict(
            os.environ,
            {"AGENT_EXECUTION_MODE": "cloud", "LANGGRAPH_API_KEY": "test-key"},
            clear=False,
        ):
            os.environ.pop("LANGGRAPH_CLOUD_URL", None)

            with pytest.raises(ValueError, match="LANGGRAPH_CLOUD_URL"):
                AgentExecutor()

    def test_cloud_mode_missing_api_key_raises_error(self):
        """Test that cloud mode without API key raises ValueError."""
        with patch.dict(
            os.environ,
            {
                "AGENT_EXECUTION_MODE": "cloud",
                "LANGGRAPH_CLOUD_URL": "https://test.api",
            },
            clear=False,
        ):
            os.environ.pop("LANGGRAPH_API_KEY", None)

            with pytest.raises(ValueError, match="LANGGRAPH_API_KEY"):
                AgentExecutor()


class TestAgentExecutorEmbeddedMode:
    """Test AgentExecutor in embedded mode."""

    @pytest.fixture
    def executor(self):
        """Create executor in embedded mode."""
        with patch.dict(os.environ, {"AGENT_EXECUTION_MODE": "embedded"}, clear=False):
            return AgentExecutor()

    @pytest.mark.asyncio
    async def test_invoke_agent_embedded_mode(self, executor):
        """Test agent invocation in embedded mode."""
        # Mock agent
        mock_agent = MagicMock()
        mock_agent.invoke = AsyncMock(
            return_value={"response": "Test response", "metadata": {}}
        )

        with patch("services.agent_executor.get_agent", return_value=mock_agent):
            result = await executor.invoke_agent(
                agent_name="test_agent", query="test query", context={"user_id": "123"}
            )

            assert result == {"response": "Test response", "metadata": {}}
            mock_agent.invoke.assert_called_once_with("test query", {"user_id": "123"})

    @pytest.mark.asyncio
    async def test_invoke_agent_routes_to_embedded(self, executor):
        """Test that invoke_agent routes to embedded executor."""
        with patch.object(
            executor, "_invoke_embedded", new_callable=AsyncMock
        ) as mock_embedded:
            mock_embedded.return_value = {"response": "embedded result"}

            result = await executor.invoke_agent("test", "query", {})

            assert result == {"response": "embedded result"}
            mock_embedded.assert_called_once_with("test", "query", {})


class TestAgentExecutorCloudMode:
    """Test AgentExecutor in cloud mode."""

    @pytest.fixture
    def executor(self):
        """Create executor in cloud mode."""
        mock_client = MagicMock()
        with patch("services.agent_executor.get_client", return_value=mock_client):
            with patch.dict(
                os.environ,
                {
                    "AGENT_EXECUTION_MODE": "cloud",
                    "LANGGRAPH_CLOUD_URL": "https://test.api",
                    "LANGGRAPH_API_KEY": "test-key",
                },
                clear=False,
            ):
                return AgentExecutor()

    @pytest.mark.asyncio
    async def test_invoke_agent_routes_to_cloud(self, executor):
        """Test that invoke_agent routes to cloud executor."""
        with patch.object(
            executor, "_invoke_cloud", new_callable=AsyncMock
        ) as mock_cloud:
            mock_cloud.return_value = {"response": "cloud result"}

            result = await executor.invoke_agent("test", "query", {})

            assert result == {"response": "cloud result"}
            mock_cloud.assert_called_once_with("test", "query", {})

    @pytest.mark.asyncio
    async def test_invoke_cloud_fetches_agent_metadata(self, executor):
        """Test that cloud mode fetches agent metadata from control-plane."""
        # Mock control-plane response
        mock_metadata = {
            "name": "test_agent",
            "langgraph_assistant_id": "asst_123",
            "langgraph_url": "https://test.api",
        }

        # Mock LangGraph client
        mock_thread = {"thread_id": "thread_123"}
        mock_run = {"run_id": "run_123"}
        mock_result = {"response": "cloud response"}

        executor.langgraph_client.threads.create = AsyncMock(return_value=mock_thread)
        executor.langgraph_client.runs.create = AsyncMock(return_value=mock_run)
        executor.langgraph_client.runs.join = AsyncMock(return_value=mock_result)

        with patch.object(
            executor, "_get_agent_metadata", new_callable=AsyncMock
        ) as mock_get_metadata:
            mock_get_metadata.return_value = mock_metadata

            result = await executor.invoke_agent(
                agent_name="test_agent", query="test query", context={"user": "123"}
            )

            # Verify metadata was fetched
            mock_get_metadata.assert_called_once_with("test_agent")

            # Verify LangGraph Cloud was called correctly
            executor.langgraph_client.threads.create.assert_called_once()
            executor.langgraph_client.runs.create.assert_called_once_with(
                thread_id="thread_123",
                assistant_id="asst_123",
                input={"messages": [{"role": "user", "content": "test query"}]},
                config={"user": "123"},
            )
            executor.langgraph_client.runs.join.assert_called_once_with(
                thread_id="thread_123", run_id="run_123"
            )

            assert result == mock_result

    @pytest.mark.asyncio
    async def test_invoke_cloud_raises_error_if_no_assistant_id(self, executor):
        """Test that cloud mode raises error if agent not deployed."""
        # Mock metadata without assistant_id
        mock_metadata = {"name": "test_agent", "langgraph_assistant_id": None}

        with patch.object(
            executor, "_get_agent_metadata", new_callable=AsyncMock
        ) as mock_get_metadata:
            mock_get_metadata.return_value = mock_metadata

            with pytest.raises(ValueError, match="not deployed to LangGraph Cloud"):
                await executor.invoke_agent("test_agent", "query", {})

    @pytest.mark.asyncio
    async def test_get_agent_metadata_success(self, executor):
        """Test fetching agent metadata from control-plane."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "test",
            "langgraph_assistant_id": "asst_123",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await executor._get_agent_metadata("test_agent")

            assert result == {"name": "test", "langgraph_assistant_id": "asst_123"}
            mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_agent_metadata_not_found(self, executor):
        """Test fetching metadata for non-existent agent."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with pytest.raises(ValueError, match="not found in control-plane"):
                await executor._get_agent_metadata("nonexistent")


class TestExecutionModeEnum:
    """Test ExecutionMode enum."""

    def test_execution_mode_values(self):
        """Test that ExecutionMode enum has correct values."""
        assert ExecutionMode.EMBEDDED.value == "embedded"
        assert ExecutionMode.CLOUD.value == "cloud"

    def test_execution_mode_from_string(self):
        """Test creating ExecutionMode from string."""
        assert ExecutionMode("embedded") == ExecutionMode.EMBEDDED
        assert ExecutionMode("cloud") == ExecutionMode.CLOUD


class TestGetAgentExecutor:
    """Test get_agent_executor singleton."""

    def test_get_agent_executor_returns_singleton(self):
        """Test that get_agent_executor returns same instance."""
        from services.agent_executor import get_agent_executor

        with patch.dict(os.environ, {"AGENT_EXECUTION_MODE": "embedded"}, clear=False):
            executor1 = get_agent_executor()
            executor2 = get_agent_executor()

            assert executor1 is executor2
