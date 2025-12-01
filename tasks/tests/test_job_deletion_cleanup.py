"""Tests for job deletion and metadata cleanup."""

from unittest.mock import MagicMock, patch

import pytest

from models.task_metadata import TaskMetadata


class TestJobDeletionCleanup:
    """Test that deleting a job cleans up all related database records."""

    @pytest.fixture
    def client(self, monkeypatch):
        """Create a test client with mocked dependencies."""
        from app import create_app

        # Set OAuth env vars to avoid auth errors
        monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
        monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
        monkeypatch.setenv("SERVER_BASE_URL", "http://localhost:5001")
        monkeypatch.setenv("ALLOWED_EMAIL_DOMAIN", "@test.com")

        # Create mock scheduler
        mock_scheduler = MagicMock()
        mock_scheduler.remove_job = MagicMock()
        mock_scheduler.scheduler.running = True
        mock_scheduler.start.return_value = None

        # Create mock registry
        mock_registry = MagicMock()

        # Create mock settings
        from config.settings import TasksSettings

        mock_settings_obj = MagicMock(spec=TasksSettings)
        mock_settings_obj.secret_key = "test-secret"
        mock_settings_obj.flask_env = "testing"

        # Use monkeypatch to set up mocks
        monkeypatch.setattr("app.SchedulerService", Mock(return_value=mock_scheduler))
        monkeypatch.setattr("app.JobRegistry", Mock(return_value=mock_registry))
        monkeypatch.setattr("app.get_settings", Mock(return_value=mock_settings_obj))

        # Create app with mocks
        test_app = create_app()

        # Update blueprint services
        import api.jobs
        import api.health

        api.jobs.scheduler_service = mock_scheduler
        api.jobs.job_registry = mock_registry
        api.health.scheduler_service = mock_scheduler

        return test_app.test_client()

    def test_delete_job_removes_metadata(self, client):
        """Test that deleting a job removes its metadata from the database."""
        job_id = "test-job-123"

        # Mock the database session and metadata query
        with (
            patch("app.scheduler_service") as mock_scheduler,
            patch("app.get_db_session") as mock_get_session,
        ):
            # Mock successful job removal from scheduler
            mock_scheduler.remove_job = MagicMock()

            # Create mock metadata object
            mock_metadata = MagicMock(spec=TaskMetadata)
            mock_metadata.job_id = job_id
            mock_metadata.task_name = "Test Task"

            # Mock database session
            mock_session = MagicMock()
            mock_session.query.return_value.filter.return_value.first.return_value = (
                mock_metadata
            )
            mock_get_session.return_value.__enter__.return_value = mock_session
            mock_get_session.return_value.__exit__.return_value = None

            # Make the delete request
            response = client.delete(f"/api/jobs/{job_id}")

            # Assert success
            assert response.status_code == 200
            data = response.get_json()
            assert "message" in data
            assert job_id in data["message"]

            # Verify scheduler was called
            mock_scheduler.remove_job.assert_called_once_with(job_id)

            # Verify metadata was deleted from database
            mock_session.delete.assert_called_once_with(mock_metadata)
            mock_session.commit.assert_called_once()

    def test_delete_job_handles_missing_metadata(self, client):
        """Test that deleting a job works even if metadata doesn't exist."""
        job_id = "test-job-no-metadata"

        with (
            patch("app.scheduler_service") as mock_scheduler,
            patch("app.get_db_session") as mock_get_session,
        ):
            # Mock successful job removal from scheduler
            mock_scheduler.remove_job = MagicMock()

            # Mock database session with no metadata found
            mock_session = MagicMock()
            mock_session.query.return_value.filter.return_value.first.return_value = (
                None
            )
            mock_get_session.return_value.__enter__.return_value = mock_session
            mock_get_session.return_value.__exit__.return_value = None

            # Make the delete request
            response = client.delete(f"/api/jobs/{job_id}")

            # Assert success even without metadata
            assert response.status_code == 200
            data = response.get_json()
            assert "message" in data

            # Verify scheduler was called
            mock_scheduler.remove_job.assert_called_once_with(job_id)

            # Verify delete was NOT called (no metadata to delete)
            mock_session.delete.assert_not_called()

    def test_delete_job_handles_database_errors(self, client):
        """Test that database errors during cleanup are handled gracefully."""
        job_id = "test-job-db-error"

        with (
            patch("app.scheduler_service") as mock_scheduler,
            patch("app.get_db_session") as mock_get_session,
        ):
            # Mock successful job removal from scheduler
            mock_scheduler.remove_job = MagicMock()

            # Mock database session that raises an exception
            mock_session = MagicMock()
            mock_session.query.side_effect = Exception("Database connection error")
            mock_get_session.return_value.__enter__.return_value = mock_session
            mock_get_session.return_value.__exit__.return_value = None

            # Make the delete request
            response = client.delete(f"/api/jobs/{job_id}")

            # Should return error due to database failure
            assert response.status_code == 400
            data = response.get_json()
            assert "error" in data

    def test_delete_job_rolls_back_on_scheduler_failure(self, client):
        """Test that if scheduler fails, we still get proper error."""
        job_id = "test-job-scheduler-fail"

        with (
            patch("app.scheduler_service") as mock_scheduler,
            patch("app.get_db_session") as mock_get_session,
        ):
            # Mock scheduler failure
            mock_scheduler.remove_job.side_effect = Exception("Scheduler error")

            # Mock database session (shouldn't be reached)
            mock_session = MagicMock()
            mock_get_session.return_value.__enter__.return_value = mock_session
            mock_get_session.return_value.__exit__.return_value = None

            # Make the delete request
            response = client.delete(f"/api/jobs/{job_id}")

            # Should return error
            assert response.status_code == 400
            data = response.get_json()
            assert "error" in data

            # Verify database cleanup was not attempted
            mock_session.delete.assert_not_called()
            mock_session.commit.assert_not_called()
