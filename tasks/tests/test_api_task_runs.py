"""Comprehensive tests for Task Runs API (api/task_runs.py)."""

import os
from datetime import UTC, datetime
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
    """Create authenticated test client."""
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


def create_mock_task_run(run_id, job_type="slack_user_import", status="completed",
                         job_id=None, task_name=None):
    """Helper to create mock task run."""
    mock_run = Mock()
    mock_run.id = run_id
    mock_run.run_id = f"run-{run_id}"
    mock_run.status = status
    mock_run.started_at = datetime.now(UTC)
    mock_run.completed_at = datetime.now(UTC)
    mock_run.duration_seconds = 120
    mock_run.triggered_by = "auto"
    mock_run.triggered_by_user = None
    mock_run.error_message = None if status == "completed" else "Test error"
    mock_run.records_processed = 100
    mock_run.records_success = 95
    mock_run.records_failed = 5

    # Task config snapshot
    config = {"job_type": job_type}
    if job_id:
        config["job_id"] = job_id
    if task_name:
        config["task_name"] = task_name
    mock_run.task_config_snapshot = config

    return mock_run


class TestListTaskRunsEndpoint:
    """Test GET /api/task-runs endpoint."""

    @patch("api.task_runs.get_db_session")
    def test_list_task_runs_success(self, mock_db_session, authenticated_client):
        """Test listing task runs successfully."""
        # Create mock task runs
        mock_runs = [
            create_mock_task_run(1, "slack_user_import"),
            create_mock_task_run(2, "google_drive_ingest"),
        ]

        # Mock database session
        mock_query = MagicMock()
        mock_query.order_by().count.return_value = 2
        mock_query.order_by().offset().limit().all.return_value = mock_runs

        mock_session = MagicMock()
        mock_session.query.return_value = mock_query
        mock_db_session.return_value.__enter__.return_value = mock_session

        response = authenticated_client.get("/api/task-runs")

        assert response.status_code == 200
        data = response.json()
        assert "task_runs" in data
        assert "pagination" in data
        assert len(data["task_runs"]) == 2
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["total"] == 2

    @patch("api.task_runs.get_db_session")
    def test_list_task_runs_empty(self, mock_db_session, authenticated_client):
        """Test listing task runs when none exist."""
        # Mock empty results
        mock_query = MagicMock()
        mock_query.order_by().count.return_value = 0
        mock_query.order_by().offset().limit().all.return_value = []

        mock_session = MagicMock()
        mock_session.query.return_value = mock_query
        mock_db_session.return_value.__enter__.return_value = mock_session

        response = authenticated_client.get("/api/task-runs")

        assert response.status_code == 200
        data = response.json()
        assert data["task_runs"] == []
        assert data["pagination"]["total"] == 0
        assert data["pagination"]["total_pages"] == 0

    @patch("api.task_runs.get_db_session")
    def test_list_task_runs_with_pagination(self, mock_db_session, authenticated_client):
        """Test pagination parameters."""
        # Mock 150 total runs
        mock_query = MagicMock()
        mock_query.order_by().count.return_value = 150

        mock_runs = [create_mock_task_run(i) for i in range(25)]
        mock_query.order_by().offset().limit().all.return_value = mock_runs

        mock_session = MagicMock()
        mock_session.query.return_value = mock_query
        mock_db_session.return_value.__enter__.return_value = mock_session

        response = authenticated_client.get("/api/task-runs?page=2&per_page=25")

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["page"] == 2
        assert data["pagination"]["per_page"] == 25
        assert data["pagination"]["total"] == 150
        assert data["pagination"]["total_pages"] == 6
        assert data["pagination"]["has_prev"] is True
        assert data["pagination"]["has_next"] is True

    @patch("api.task_runs.get_db_session")
    def test_list_task_runs_max_page_size_cap(self, mock_db_session, authenticated_client):
        """Test that per_page is capped at MAX_PAGE_SIZE."""
        mock_query = MagicMock()
        mock_query.order_by().count.return_value = 200
        mock_query.order_by().offset().limit().all.return_value = []

        mock_session = MagicMock()
        mock_session.query.return_value = mock_query
        mock_db_session.return_value.__enter__.return_value = mock_session

        # Request 500 items per page (should be capped at 100)
        response = authenticated_client.get("/api/task-runs?per_page=500")

        assert response.status_code == 200
        data = response.json()
        # Should be silently capped at MAX_PAGE_SIZE (100)
        assert data["pagination"]["per_page"] == 100

    @patch("api.task_runs.get_db_session")
    def test_list_task_runs_with_custom_task_name(self, mock_db_session, authenticated_client):
        """Test task runs with custom task names."""
        # Create run with task_name in snapshot
        mock_run = create_mock_task_run(1, job_type="slack_user_import",
                                       job_id="job-1", task_name="Daily User Sync")

        mock_query = MagicMock()
        mock_query.order_by().count.return_value = 1
        mock_query.order_by().offset().limit().all.return_value = [mock_run]

        mock_session = MagicMock()
        mock_session.query.return_value = mock_query
        mock_db_session.return_value.__enter__.return_value = mock_session

        response = authenticated_client.get("/api/task-runs")

        assert response.status_code == 200
        data = response.json()
        assert data["task_runs"][0]["job_name"] == "Daily User Sync"

    @patch("api.task_runs.get_db_session")
    def test_list_task_runs_with_metadata_fallback(self, mock_db_session, authenticated_client):
        """Test task runs fall back to metadata for job name."""
        from models.task_metadata import TaskMetadata

        # Create run without task_name in snapshot
        mock_run = create_mock_task_run(1, job_type="slack_user_import", job_id="job-1")

        # Create metadata
        mock_metadata = Mock(spec=TaskMetadata)
        mock_metadata.job_id = "job-1"
        mock_metadata.task_name = "Metadata Task Name"

        # Mock both queries
        mock_run_query = MagicMock()
        mock_run_query.order_by().count.return_value = 1
        mock_run_query.order_by().offset().limit().all.return_value = [mock_run]

        mock_metadata_query = MagicMock()
        mock_metadata_query.filter().all.return_value = [mock_metadata]

        mock_session = MagicMock()
        # query() is called twice: once for TaskRun, once for TaskMetadata
        mock_session.query.side_effect = [mock_run_query, mock_metadata_query]
        mock_db_session.return_value.__enter__.return_value = mock_session

        response = authenticated_client.get("/api/task-runs")

        assert response.status_code == 200
        data = response.json()
        assert data["task_runs"][0]["job_name"] == "Metadata Task Name"

    @patch("api.task_runs.get_db_session")
    def test_list_task_runs_with_job_type_fallback(self, mock_db_session, authenticated_client):
        """Test task runs fall back to job type names."""
        # Create run without task_name or metadata
        mock_run = create_mock_task_run(1, job_type="slack_user_import")

        mock_query = MagicMock()
        mock_query.order_by().count.return_value = 1
        mock_query.order_by().offset().limit().all.return_value = [mock_run]

        # No metadata found
        mock_metadata_query = MagicMock()
        mock_metadata_query.filter().all.return_value = []

        mock_session = MagicMock()
        mock_session.query.side_effect = [mock_query, mock_metadata_query]
        mock_db_session.return_value.__enter__.return_value = mock_session

        response = authenticated_client.get("/api/task-runs")

        assert response.status_code == 200
        data = response.json()
        # Should use job_type_names mapping
        assert data["task_runs"][0]["job_name"] == "Slack User Import"

    @patch("api.task_runs.get_db_session")
    def test_list_task_runs_with_unknown_job_type(self, mock_db_session, authenticated_client):
        """Test task runs with unknown job type."""
        # Create run with unknown job type
        mock_run = create_mock_task_run(1, job_type="unknown_job_type")

        mock_query = MagicMock()
        mock_query.order_by().count.return_value = 1
        mock_query.order_by().offset().limit().all.return_value = [mock_run]

        mock_metadata_query = MagicMock()
        mock_metadata_query.filter().all.return_value = []

        mock_session = MagicMock()
        mock_session.query.side_effect = [mock_query, mock_metadata_query]
        mock_db_session.return_value.__enter__.return_value = mock_session

        response = authenticated_client.get("/api/task-runs")

        assert response.status_code == 200
        data = response.json()
        # Should convert to title case
        assert data["task_runs"][0]["job_name"] == "Unknown Job Type"

    @patch("api.task_runs.get_db_session")
    def test_list_task_runs_with_failed_status(self, mock_db_session, authenticated_client):
        """Test task runs with failed status."""
        mock_run = create_mock_task_run(1, status="failed")
        mock_run.error_message = "Database connection timeout"

        mock_query = MagicMock()
        mock_query.order_by().count.return_value = 1
        mock_query.order_by().offset().limit().all.return_value = [mock_run]

        mock_session = MagicMock()
        mock_session.query.return_value = mock_query
        mock_db_session.return_value.__enter__.return_value = mock_session

        response = authenticated_client.get("/api/task-runs")

        assert response.status_code == 200
        data = response.json()
        assert data["task_runs"][0]["status"] == "failed"
        assert data["task_runs"][0]["error_message"] == "Database connection timeout"

    @patch("api.task_runs.get_db_session")
    def test_list_task_runs_pagination_edge_cases(self, mock_db_session, authenticated_client):
        """Test pagination edge cases."""
        mock_query = MagicMock()
        mock_query.order_by().count.return_value = 55  # Not evenly divisible
        mock_query.order_by().offset().limit().all.return_value = []

        mock_session = MagicMock()
        mock_session.query.return_value = mock_query
        mock_db_session.return_value.__enter__.return_value = mock_session

        response = authenticated_client.get("/api/task-runs?per_page=10")

        assert response.status_code == 200
        data = response.json()
        # 55 items / 10 per page = 6 pages (ceiling division)
        assert data["pagination"]["total_pages"] == 6

    @patch("api.task_runs.get_db_session")
    def test_list_task_runs_metadata_error_handling(self, mock_db_session, authenticated_client):
        """Test graceful handling of metadata loading errors."""
        mock_run = create_mock_task_run(1, job_id="job-1")

        mock_query = MagicMock()
        mock_query.order_by().count.return_value = 1
        mock_query.order_by().offset().limit().all.return_value = [mock_run]

        # Metadata query raises error
        mock_metadata_query = MagicMock()
        mock_metadata_query.filter().all.side_effect = Exception("Database error")

        mock_session = MagicMock()
        mock_session.query.side_effect = [mock_query, mock_metadata_query]
        mock_db_session.return_value.__enter__.return_value = mock_session

        response = authenticated_client.get("/api/task-runs")

        # Should still succeed, just without metadata
        assert response.status_code == 200
        data = response.json()
        assert len(data["task_runs"]) == 1

    @patch("api.task_runs.get_db_session")
    def test_list_task_runs_database_error(self, mock_db_session, authenticated_client):
        """Test handling of database errors."""
        mock_db_session.side_effect = Exception("Database connection failed")

        response = authenticated_client.get("/api/task-runs")

        # Should raise HTTPException with 500 status
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Database connection failed" in data["detail"]

    @patch("api.task_runs.get_db_session")
    def test_list_task_runs_all_fields_present(self, mock_db_session, authenticated_client):
        """Test that all expected fields are present in response."""
        mock_run = create_mock_task_run(1)
        mock_run.triggered_by_user = "user@example.com"

        mock_query = MagicMock()
        mock_query.order_by().count.return_value = 1
        mock_query.order_by().offset().limit().all.return_value = [mock_run]

        mock_session = MagicMock()
        mock_session.query.return_value = mock_query
        mock_db_session.return_value.__enter__.return_value = mock_session

        response = authenticated_client.get("/api/task-runs")

        assert response.status_code == 200
        data = response.json()
        run = data["task_runs"][0]

        # Verify all fields are present
        assert "id" in run
        assert "run_id" in run
        assert "job_type" in run
        assert "job_name" in run
        assert "status" in run
        assert "started_at" in run
        assert "completed_at" in run
        assert "duration_seconds" in run
        assert "triggered_by" in run
        assert "triggered_by_user" in run
        assert "error_message" in run
        assert "records_processed" in run
        assert "records_success" in run
        assert "records_failed" in run
