"""Tests for goal bots API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.goal_bots import _running_tasks, router
from dependencies.auth import require_service_auth


@pytest.fixture
def app():
    """Create a test FastAPI app with auth override."""
    app = FastAPI()

    # Override auth dependency
    async def mock_auth():
        return "test-service"

    app.dependency_overrides[require_service_auth] = mock_auth
    app.include_router(router, prefix="/api")
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def sample_bot():
    """Sample goal bot configuration."""
    return {
        "bot_id": "bot-123",
        "name": "test_bot",
        "description": "A test goal bot",
        "agent_name": "research",
        "goal_prompt": "Test goal prompt",
        "max_iterations": 10,
    }


@pytest.fixture(autouse=True)
def clear_running_tasks():
    """Clear running tasks before each test."""
    _running_tasks.clear()
    yield
    _running_tasks.clear()


class TestExecuteGoalBot:
    """Tests for execute_goal_bot endpoint."""

    def test_execute_starts_background_task(self, client, sample_bot):
        """Test that execute endpoint starts a background task."""
        with patch("api.goal_bots.asyncio.create_task") as mock_create_task:
            mock_task = MagicMock()
            mock_create_task.return_value = mock_task

            response = client.post(
                "/api/goal-bots/bot-123/execute",
                json={
                    "run_id": "run-456",
                    "bot": sample_bot,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["run_id"] == "run-456"
        assert data["bot_id"] == "bot-123"
        assert "execution started" in data["message"].lower()

    def test_execute_rejects_duplicate_run(self, client, sample_bot):
        """Test that duplicate run_id is rejected."""
        # Simulate existing running task
        _running_tasks["run-456"] = MagicMock()

        response = client.post(
            "/api/goal-bots/bot-123/execute",
            json={
                "run_id": "run-456",
                "bot": sample_bot,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "already in progress" in data["message"].lower()


class TestGetExecutionStatus:
    """Tests for get_execution_status endpoint."""

    def test_status_running_task(self, client):
        """Test status of a running task."""
        mock_task = MagicMock()
        mock_task.done.return_value = False
        _running_tasks["run-456"] = mock_task

        response = client.get("/api/goal-bots/bot-123/status/run-456")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert data["in_memory"] is True

    def test_status_completed_task(self, client):
        """Test status of a completed task."""
        mock_task = MagicMock()
        mock_task.done.return_value = True
        _running_tasks["run-456"] = mock_task

        response = client.get("/api/goal-bots/bot-123/status/run-456")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    def test_status_unknown_task(self, client):
        """Test status of an unknown task."""
        response = client.get("/api/goal-bots/bot-123/status/run-999")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unknown"
        assert data["in_memory"] is False


class TestCancelExecution:
    """Tests for cancel_execution endpoint."""

    def test_cancel_running_task(self, client):
        """Test cancelling a running task."""
        mock_task = MagicMock()
        mock_task.done.return_value = False
        _running_tasks["run-456"] = mock_task

        with patch("api.goal_bots.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.put = AsyncMock()

            response = client.post("/api/goal-bots/bot-123/cancel/run-456")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_task.cancel.assert_called_once()
        assert "run-456" not in _running_tasks

    def test_cancel_completed_task(self, client):
        """Test cancelling an already completed task."""
        mock_task = MagicMock()
        mock_task.done.return_value = True
        _running_tasks["run-456"] = mock_task

        response = client.post("/api/goal-bots/bot-123/cancel/run-456")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "already completed" in data["message"].lower()

    def test_cancel_unknown_task(self, client):
        """Test cancelling an unknown task."""
        response = client.post("/api/goal-bots/bot-123/cancel/run-999")

        assert response.status_code == 404


class TestExecuteGoalBotBackground:
    """Tests for background execution function."""

    @pytest.mark.asyncio
    async def test_successful_execution(self):
        """Test successful goal bot execution."""
        from api.goal_bots import _execute_goal_bot_background

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(
            return_value={"messages": [MagicMock(content="Test response")]}
        )

        mock_registry = {
            "research": {
                "name": "research",
                "graph_func": lambda: mock_graph,
            }
        }

        with patch(
            "services.agent_registry.get_agent_registry", return_value=mock_registry
        ):
            with patch("api.goal_bots.httpx.AsyncClient") as mock_client:
                mock_instance = mock_client.return_value.__aenter__.return_value
                mock_instance.post = AsyncMock()
                mock_instance.put = AsyncMock()

                await _execute_goal_bot_background(
                    bot_id="bot-123",
                    run_id="run-456",
                    bot={
                        "name": "test_bot",
                        "agent_name": "research",
                        "goal_prompt": "Test goal",
                        "max_iterations": 10,
                    },
                    control_plane_url="http://control-plane:6001",
                    service_api_key="test-key",
                )

        # Verify graph was invoked
        mock_graph.ainvoke.assert_called_once()

        # Verify milestones were logged
        assert mock_instance.post.call_count >= 2  # At least start and completion

        # Verify run was updated to completed
        mock_instance.put.assert_called()

    @pytest.mark.asyncio
    async def test_execution_with_missing_agent(self):
        """Test execution when agent is not found."""
        from api.goal_bots import _execute_goal_bot_background

        with patch("services.agent_registry.get_agent_registry", return_value={}):
            with patch("api.goal_bots.httpx.AsyncClient") as mock_client:
                mock_instance = mock_client.return_value.__aenter__.return_value
                mock_instance.post = AsyncMock()
                mock_instance.put = AsyncMock()

                await _execute_goal_bot_background(
                    bot_id="bot-123",
                    run_id="run-456",
                    bot={
                        "name": "test_bot",
                        "agent_name": "nonexistent",
                        "max_iterations": 10,
                    },
                    control_plane_url="http://control-plane:6001",
                    service_api_key="test-key",
                )

        # Verify run was updated to failed
        put_calls = mock_instance.put.call_args_list
        assert len(put_calls) > 0
        # Check that status was set to failed
        last_put = put_calls[-1]
        assert "failed" in str(last_put)


class TestLogMilestone:
    """Tests for milestone logging."""

    @pytest.mark.asyncio
    async def test_log_milestone_success(self):
        """Test successful milestone logging."""
        from api.goal_bots import _log_milestone

        mock_client = MagicMock()
        mock_client.post = AsyncMock()

        await _log_milestone(
            client=mock_client,
            control_plane_url="http://control-plane:6001",
            headers={"X-Service-API-Key": "test"},
            run_id="run-456",
            milestone_type="execute",
            milestone_name="Test milestone",
            details={"key": "value"},
        )

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "run-456" in call_args[0][0]
        assert call_args[1]["json"]["milestone_type"] == "execute"

    @pytest.mark.asyncio
    async def test_log_milestone_handles_error(self):
        """Test that milestone logging handles errors gracefully."""
        from api.goal_bots import _log_milestone

        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=Exception("Network error"))

        # Should not raise
        await _log_milestone(
            client=mock_client,
            control_plane_url="http://control-plane:6001",
            headers={},
            run_id="run-456",
            milestone_type="execute",
            milestone_name="Test milestone",
        )
