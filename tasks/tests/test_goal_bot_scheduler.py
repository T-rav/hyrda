"""Tests for GoalBotSchedulerJob."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jobs.goal_bot_scheduler import GoalBotSchedulerJob


@pytest.fixture
def settings():
    """Create mock settings."""
    return MagicMock()


@pytest.fixture
def job(settings):
    """Create a GoalBotSchedulerJob instance."""
    with patch.dict(
        "os.environ",
        {
            "CONTROL_PLANE_URL": "http://control-plane:6001",
            "AGENT_SERVICE_URL": "http://agent-service:8000",
            "SERVICE_API_KEY": "test-key",
        },
    ):
        return GoalBotSchedulerJob(settings)


class TestGoalBotSchedulerJob:
    """Tests for GoalBotSchedulerJob."""

    def test_job_name(self, job):
        """Test job has correct name."""
        assert job.JOB_NAME == "Goal Bot Scheduler"

    def test_job_description(self, job):
        """Test job has correct description."""
        assert "goal bots" in job.JOB_DESCRIPTION.lower()

    @pytest.mark.asyncio
    async def test_execute_no_due_bots(self, job):
        """Test execution when no bots are due."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"due_bots": [], "count": 0}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await job._execute_job()

        assert result["due_bots_found"] == 0
        assert result["runs_created"] == 0
        assert result["runs_started"] == 0
        assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_execute_with_due_bot(self, job):
        """Test execution with a due bot."""
        due_bot = {
            "bot_id": "bot-123",
            "name": "test_bot",
            "agent_name": "research",
        }

        # Mock responses
        due_response = MagicMock()
        due_response.json.return_value = {"due_bots": [due_bot], "count": 1}
        due_response.raise_for_status = MagicMock()

        create_run_response = MagicMock()
        create_run_response.json.return_value = {
            "success": True,
            "run": {"run_id": "run-456"},
        }
        create_run_response.raise_for_status = MagicMock()

        start_run_response = MagicMock()
        start_run_response.raise_for_status = MagicMock()

        trigger_response = MagicMock()
        trigger_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = mock_client.return_value.__aenter__.return_value
            mock_instance.get = AsyncMock(return_value=due_response)
            mock_instance.post = AsyncMock(
                side_effect=[create_run_response, start_run_response, trigger_response]
            )

            result = await job._execute_job()

        assert result["due_bots_found"] == 1
        assert result["runs_created"] == 1
        assert result["runs_started"] == 1
        assert result["records_success"] == 1

    @pytest.mark.asyncio
    async def test_execute_handles_api_error(self, job):
        """Test execution handles API errors gracefully."""
        import httpx

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = mock_client.return_value.__aenter__.return_value
            mock_instance.get = AsyncMock(
                side_effect=httpx.HTTPError("Connection failed")
            )

            result = await job._execute_job()

        assert result["due_bots_found"] == 0
        assert len(result["errors"]) == 1
        assert "Connection failed" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_execute_bot_already_running(self, job):
        """Test execution when bot already has a running job."""
        due_bot = {
            "bot_id": "bot-123",
            "name": "test_bot",
        }

        due_response = MagicMock()
        due_response.json.return_value = {"due_bots": [due_bot], "count": 1}
        due_response.raise_for_status = MagicMock()

        create_run_response = MagicMock()
        create_run_response.json.return_value = {
            "success": False,
            "error": "Bot already has a running job",
        }
        create_run_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = mock_client.return_value.__aenter__.return_value
            mock_instance.get = AsyncMock(return_value=due_response)
            mock_instance.post = AsyncMock(return_value=create_run_response)

            result = await job._execute_job()

        assert result["due_bots_found"] == 1
        assert result["runs_created"] == 0  # No run created because bot is running


class TestGoalBotSchedulerJobRegistration:
    """Tests for job registration."""

    def test_job_in_registry(self):
        """Test that GoalBotSchedulerJob is registered."""
        from jobs.job_registry import JobRegistry
        from services.scheduler_service import SchedulerService

        mock_settings = MagicMock()
        mock_scheduler = MagicMock(spec=SchedulerService)

        registry = JobRegistry(mock_settings, mock_scheduler)

        assert "goal_bot_scheduler" in registry.job_types

    def test_job_types_list(self):
        """Test that goal_bot_scheduler appears in available job types."""
        from jobs.job_registry import JobRegistry
        from services.scheduler_service import SchedulerService

        mock_settings = MagicMock()
        mock_scheduler = MagicMock(spec=SchedulerService)

        registry = JobRegistry(mock_settings, mock_scheduler)
        job_types = registry.get_available_job_types()

        job_type_names = [jt["type"] for jt in job_types]
        assert "goal_bot_scheduler" in job_type_names
