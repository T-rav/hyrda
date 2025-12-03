"""Comprehensive tests for Jobs API endpoints (api/jobs.py)."""

import os
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    """Get the FastAPI app instance for testing."""
    os.environ.setdefault("TASK_DATABASE_URL", "sqlite:///:memory:")
    os.environ.setdefault("DATA_DATABASE_URL", "sqlite:///:memory:")
    os.environ.setdefault("SERVER_BASE_URL", "http://localhost:5001")
    os.environ.setdefault("SECRET_KEY", "test-secret-key-for-sessions")
    os.environ.setdefault("ALLOWED_EMAIL_DOMAIN", "8thlight.com")

    from app import app as fastapi_app
    return fastapi_app


@pytest.fixture
def authenticated_client(app):
    """Create authenticated test client with dependency override."""
    from dependencies.auth import get_current_user

    async def override_get_current_user():
        return {
            "email": "user@8thlight.com",
            "name": "Test User",
            "picture": "https://example.com/photo.jpg"
        }

    app.dependency_overrides[get_current_user] = override_get_current_user
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_scheduler():
    """Create mock scheduler service."""
    scheduler = MagicMock()
    scheduler.get_scheduler_info.return_value = {
        "state": "running",
        "jobs_count": 5
    }
    return scheduler


@pytest.fixture
def mock_job_registry():
    """Create mock job registry."""
    registry = MagicMock()
    registry.get_available_job_types.return_value = [
        {"type": "slack_user_import", "name": "Slack User Import"},
        {"type": "gdrive_ingest", "name": "Google Drive Ingestion"}
    ]
    return registry


@pytest.fixture
def client_with_services(app, mock_scheduler, mock_job_registry):
    """Create client with mocked services in app state."""
    from dependencies.auth import get_current_user

    async def override_get_current_user():
        return {"email": "user@8thlight.com", "name": "Test User"}

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.state.scheduler_service = mock_scheduler
    app.state.job_registry = mock_job_registry

    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


class TestSchedulerInfoEndpoint:
    """Test GET /api/scheduler/info endpoint."""

    def test_scheduler_info_success(self, client_with_services, mock_scheduler):
        """Test getting scheduler info successfully."""
        response = client_with_services.get("/api/scheduler/info")
        assert response.status_code == 200
        data = response.json()
        assert data["state"] == "running"
        assert data["jobs_count"] == 5

    def test_scheduler_info_not_initialized(self, authenticated_client, app):
        """Test scheduler info when scheduler not initialized."""
        app.state.scheduler_service = None
        response = authenticated_client.get("/api/scheduler/info")
        assert response.status_code == 500
        assert "Scheduler not initialized" in response.json()["detail"]


class TestListJobsEndpoint:
    """Test GET /api/jobs endpoint."""

    @patch("api.jobs.get_db_session")
    def test_list_jobs_success(self, mock_db_session, client_with_services, mock_scheduler):
        """Test listing jobs successfully."""
        mock_job1 = Mock()
        mock_job1.id = "job-1"
        mock_job2 = Mock()
        mock_job2.id = "job-2"

        mock_scheduler.get_jobs.return_value = [mock_job1, mock_job2]
        mock_scheduler.get_job_info.side_effect = [
            {"id": "job-1", "name": "Job 1", "next_run_time": "2024-01-20T10:00:00Z"},
            {"id": "job-2", "name": "Job 2", "next_run_time": "2024-01-20T11:00:00Z"}
        ]

        # Mock empty metadata
        mock_session = MagicMock()
        mock_session.query().all.return_value = []
        mock_db_session.return_value.__enter__.return_value = mock_session

        response = client_with_services.get("/api/jobs")
        assert response.status_code == 200
        data = response.json()
        assert len(data["jobs"]) == 2
        assert data["jobs"][0]["id"] == "job-1"
        assert data["jobs"][1]["id"] == "job-2"

    @patch("api.jobs.get_db_session")
    def test_list_jobs_with_custom_names(self, mock_db_session, client_with_services, mock_scheduler):
        """Test listing jobs with custom task names from metadata."""
        from models.task_metadata import TaskMetadata

        mock_job = Mock()
        mock_job.id = "job-1"
        mock_scheduler.get_jobs.return_value = [mock_job]
        mock_scheduler.get_job_info.return_value = {
            "id": "job-1",
            "name": "Default Name"
        }

        # Mock metadata with custom name
        mock_metadata = Mock(spec=TaskMetadata)
        mock_metadata.job_id = "job-1"
        mock_metadata.task_name = "Custom Task Name"

        mock_session = MagicMock()
        mock_session.query().all.return_value = [mock_metadata]
        mock_db_session.return_value.__enter__.return_value = mock_session

        response = client_with_services.get("/api/jobs")
        assert response.status_code == 200
        data = response.json()
        assert data["jobs"][0]["name"] == "Custom Task Name"

    def test_list_jobs_scheduler_not_initialized(self, authenticated_client, app):
        """Test listing jobs when scheduler not initialized."""
        app.state.scheduler_service = None
        response = authenticated_client.get("/api/jobs")
        assert response.status_code == 500


class TestGetJobEndpoint:
    """Test GET /api/jobs/{job_id} endpoint."""

    def test_get_job_success(self, client_with_services, mock_scheduler):
        """Test getting specific job successfully."""
        mock_scheduler.get_job_info.return_value = {
            "id": "job-1",
            "name": "Test Job",
            "next_run_time": "2024-01-20T10:00:00Z"
        }

        response = client_with_services.get("/api/jobs/job-1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "job-1"
        assert data["name"] == "Test Job"

    def test_get_job_not_found(self, client_with_services, mock_scheduler):
        """Test getting non-existent job returns 404."""
        mock_scheduler.get_job_info.return_value = None

        response = client_with_services.get("/api/jobs/nonexistent-id")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_get_job_scheduler_not_initialized(self, authenticated_client, app):
        """Test getting job when scheduler not initialized."""
        app.state.scheduler_service = None
        response = authenticated_client.get("/api/jobs/job-1")
        assert response.status_code == 500


class TestCreateJobEndpoint:
    """Test POST /api/jobs endpoint."""

    @patch("api.jobs.get_db_session")
    def test_create_job_success(self, mock_db_session, client_with_services, mock_job_registry):
        """Test creating job successfully."""
        mock_job = Mock()
        mock_job.id = "new-job-1"
        mock_job_registry.create_job.return_value = mock_job

        mock_session = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_session

        response = client_with_services.post("/api/jobs", json={
            "job_type": "slack_user_import",
            "schedule": {"type": "cron", "cron": "0 0 * * *"},
            "parameters": {},
            "task_name": "Daily User Import"
        })

        assert response.status_code == 200
        data = response.json()
        assert "created successfully" in data["message"]
        assert data["job_id"] == "new-job-1"

    def test_create_job_missing_job_type(self, client_with_services):
        """Test creating job without job_type returns 400."""
        response = client_with_services.post("/api/jobs", json={
            "schedule": {"type": "cron"},
            "parameters": {}
        })

        assert response.status_code == 400
        assert "job_type is required" in response.json()["detail"]

    def test_create_job_no_data(self, client_with_services):
        """Test creating job without data returns 400."""
        response = client_with_services.post("/api/jobs", json=None)
        assert response.status_code in [400, 422]  # FastAPI may return 422 for invalid JSON

    def test_create_job_services_not_initialized(self, authenticated_client, app):
        """Test creating job when services not initialized."""
        app.state.scheduler_service = None
        app.state.job_registry = None

        response = authenticated_client.post("/api/jobs", json={
            "job_type": "test_job",
            "schedule": {}
        })

        assert response.status_code == 500
        assert "not initialized" in response.json()["detail"]

    @patch("api.jobs.get_db_session")
    def test_create_job_registry_error(self, mock_db_session, client_with_services, mock_job_registry):
        """Test creating job handles registry errors."""
        mock_job_registry.create_job.side_effect = Exception("Invalid job type")

        response = client_with_services.post("/api/jobs", json={
            "job_type": "invalid_type",
            "schedule": {}
        })

        assert response.status_code == 400


class TestPauseJobEndpoint:
    """Test POST /api/jobs/{job_id}/pause endpoint."""

    def test_pause_job_success(self, client_with_services, mock_scheduler):
        """Test pausing job successfully."""
        response = client_with_services.post("/api/jobs/job-1/pause")
        assert response.status_code == 200
        assert "paused successfully" in response.json()["message"]
        mock_scheduler.pause_job.assert_called_once_with("job-1")

    def test_pause_job_error(self, client_with_services, mock_scheduler):
        """Test pausing job handles errors."""
        mock_scheduler.pause_job.side_effect = Exception("Job not found")

        response = client_with_services.post("/api/jobs/invalid-id/pause")
        assert response.status_code == 400

    def test_pause_job_scheduler_not_initialized(self, authenticated_client, app):
        """Test pausing job when scheduler not initialized."""
        app.state.scheduler_service = None
        response = authenticated_client.post("/api/jobs/job-1/pause")
        assert response.status_code == 500


class TestResumeJobEndpoint:
    """Test POST /api/jobs/{job_id}/resume endpoint."""

    def test_resume_job_success(self, client_with_services, mock_scheduler):
        """Test resuming job successfully."""
        response = client_with_services.post("/api/jobs/job-1/resume")
        assert response.status_code == 200
        assert "resumed successfully" in response.json()["message"]
        mock_scheduler.resume_job.assert_called_once_with("job-1")

    def test_resume_job_error(self, client_with_services, mock_scheduler):
        """Test resuming job handles errors."""
        mock_scheduler.resume_job.side_effect = Exception("Job not found")

        response = client_with_services.post("/api/jobs/invalid-id/resume")
        assert response.status_code == 400


class TestDeleteJobEndpoint:
    """Test DELETE /api/jobs/{job_id} endpoint."""

    @patch("api.jobs.get_db_session")
    def test_delete_job_success(self, mock_db_session, client_with_services, mock_scheduler):
        """Test deleting job successfully."""
        from models.task_metadata import TaskMetadata

        mock_metadata = Mock(spec=TaskMetadata)
        mock_metadata.job_id = "job-1"

        mock_session = MagicMock()
        mock_session.query().filter().first.return_value = mock_metadata
        mock_db_session.return_value.__enter__.return_value = mock_session

        response = client_with_services.delete("/api/jobs/job-1")
        assert response.status_code == 200
        assert "deleted successfully" in response.json()["message"]
        mock_scheduler.remove_job.assert_called_once_with("job-1")

    @patch("api.jobs.get_db_session")
    def test_delete_job_no_metadata(self, mock_db_session, client_with_services, mock_scheduler):
        """Test deleting job without metadata."""
        mock_session = MagicMock()
        mock_session.query().filter().first.return_value = None
        mock_db_session.return_value.__enter__.return_value = mock_session

        response = client_with_services.delete("/api/jobs/job-1")
        assert response.status_code == 200
        mock_scheduler.remove_job.assert_called_once()

    def test_delete_job_error(self, client_with_services, mock_scheduler):
        """Test deleting job handles errors."""
        mock_scheduler.remove_job.side_effect = Exception("Job not found")

        response = client_with_services.delete("/api/jobs/invalid-id")
        assert response.status_code == 400


class TestUpdateJobEndpoint:
    """Test PUT /api/jobs/{job_id} endpoint."""

    def test_update_job_success(self, client_with_services, mock_scheduler):
        """Test updating job successfully."""
        response = client_with_services.put("/api/jobs/job-1", json={
            "name": "Updated Job Name",
            "paused": False
        })

        assert response.status_code == 200
        assert "updated successfully" in response.json()["message"]
        mock_scheduler.modify_job.assert_called_once()

    def test_update_job_no_data(self, client_with_services):
        """Test updating job without data returns 400."""
        response = client_with_services.put("/api/jobs/job-1", json=None)
        assert response.status_code in [400, 422]

    def test_update_job_error(self, client_with_services, mock_scheduler):
        """Test updating job handles errors."""
        mock_scheduler.modify_job.side_effect = Exception("Job not found")

        response = client_with_services.put("/api/jobs/invalid-id", json={
            "name": "New Name"
        })

        assert response.status_code == 400


class TestRetryJobEndpoint:
    """Test POST /api/jobs/{job_id}/retry endpoint."""

    def test_retry_job_success(self, client_with_services, mock_scheduler):
        """Test retrying job successfully."""
        mock_job = Mock()
        mock_scheduler.get_job.return_value = mock_job

        response = client_with_services.post("/api/jobs/job-1/retry")
        assert response.status_code == 200
        assert "queued for immediate retry" in response.json()["message"]
        mock_scheduler.modify_job.assert_called_once()

    def test_retry_job_not_found(self, client_with_services, mock_scheduler):
        """Test retrying non-existent job returns 404."""
        mock_scheduler.get_job.return_value = None

        response = client_with_services.post("/api/jobs/nonexistent-id/retry")
        assert response.status_code == 404

    def test_retry_job_error(self, client_with_services, mock_scheduler):
        """Test retrying job handles errors."""
        mock_scheduler.get_job.side_effect = Exception("Internal error")

        response = client_with_services.post("/api/jobs/job-1/retry")
        assert response.status_code == 400


class TestRunJobOnceEndpoint:
    """Test POST /api/jobs/{job_id}/run-once endpoint."""

    def test_run_job_once_success(self, client_with_services, mock_scheduler):
        """Test running job once successfully."""
        mock_job = Mock()
        mock_job.id = "job-1"
        mock_job.name = "Test Job"
        mock_job.func = Mock()
        mock_job.args = ["arg1", "arg2"]
        mock_scheduler.get_job.return_value = mock_job

        response = client_with_services.post("/api/jobs/job-1/run-once")
        assert response.status_code == 200
        assert "Created one-time job" in response.json()["message"]
        assert "one_time_job_id" in response.json()
        mock_scheduler.add_job.assert_called_once()

    def test_run_job_once_not_found(self, client_with_services, mock_scheduler):
        """Test running non-existent job once returns 404."""
        mock_scheduler.get_job.return_value = None

        response = client_with_services.post("/api/jobs/nonexistent-id/run-once")
        assert response.status_code == 404

    def test_run_job_once_with_triggered_by(self, client_with_services, mock_scheduler):
        """Test running job once updates triggered_by parameter."""
        mock_job = Mock()
        mock_job.id = "job-1"
        mock_job.name = "Test Job"
        mock_job.func = Mock()
        mock_job.args = ["arg1", "arg2", "auto"]  # Has triggered_by
        mock_scheduler.get_job.return_value = mock_job

        response = client_with_services.post("/api/jobs/job-1/run-once")
        assert response.status_code == 200

        # Verify add_job was called with manual trigger
        call_args = mock_scheduler.add_job.call_args
        assert call_args[1]["args"][2] == "manual"


class TestJobHistoryEndpoint:
    """Test GET /api/jobs/{job_id}/history endpoint."""

    def test_get_job_history_success(self, client_with_services):
        """Test getting job history successfully (mock data)."""
        response = client_with_services.get("/api/jobs/job-1/history")
        assert response.status_code == 200
        data = response.json()
        assert "executions" in data
        assert "total_executions" in data
        assert "success_rate" in data
        assert data["job_id"] == "job-1"

    def test_get_job_history_scheduler_not_initialized(self, authenticated_client, app):
        """Test getting job history when scheduler not initialized."""
        app.state.scheduler_service = None
        response = authenticated_client.get("/api/jobs/job-1/history")
        assert response.status_code == 500


class TestListJobTypesEndpoint:
    """Test GET /api/job-types endpoint."""

    def test_list_job_types_success(self, client_with_services, mock_job_registry):
        """Test listing job types successfully."""
        response = client_with_services.get("/api/job-types")
        assert response.status_code == 200
        data = response.json()
        assert "job_types" in data
        assert len(data["job_types"]) == 2
        assert data["job_types"][0]["type"] == "slack_user_import"

    def test_list_job_types_registry_not_initialized(self, authenticated_client, app):
        """Test listing job types when registry not initialized."""
        app.state.job_registry = None
        response = authenticated_client.get("/api/job-types")
        assert response.status_code == 500
        assert "not initialized" in response.json()["detail"]
