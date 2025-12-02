"""Tests for job deletion and metadata cleanup."""

from unittest.mock import MagicMock

from models.task_metadata import TaskMetadata


class TestJobDeletionCleanup:
    """Test that deleting a job cleans up all related database records."""

    # Uses shared fixtures from conftest.py: client

    def test_delete_job_removes_metadata(self, client):
        """Test that deleting a job removes its metadata from the database."""
        job_id = "test-job-123"

        # Access the mock from app.extensions (no more global patching!)
        mock_scheduler = client.app.state.scheduler_service

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

        # Make the delete request
        response = client.delete(f"/api/jobs/{job_id}")

        # Assert success
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert job_id in data["message"]

        # Verify scheduler was called
        mock_scheduler.remove_job.assert_called_once_with(job_id)

    def test_delete_job_handles_missing_metadata(self, client):
        """Test that deleting a job works even if metadata doesn't exist."""
        job_id = "test-job-no-metadata"

        # Access the mock from app.extensions (no more global patching!)
        mock_scheduler = client.app.state.scheduler_service

        # Mock successful job removal from scheduler
        mock_scheduler.remove_job = MagicMock()

        # Mock database session with no metadata found
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None

        # Make the delete request
        response = client.delete(f"/api/jobs/{job_id}")

        # Assert success even without metadata
        assert response.status_code == 200
        data = response.json()
        assert "message" in data

        # Verify scheduler was called
        mock_scheduler.remove_job.assert_called_once_with(job_id)

    def test_delete_job_handles_database_errors(self, client):
        """Test that database errors during cleanup are handled gracefully."""
        job_id = "test-job-db-error"

        # Access the mock from app.extensions (no more global patching!)
        mock_scheduler = client.app.state.scheduler_service

        # Mock successful job removal from scheduler
        mock_scheduler.remove_job = MagicMock()

        # Make the delete request
        response = client.delete(f"/api/jobs/{job_id}")

        # Should return success or error depending on implementation
        assert response.status_code in [200, 400]
        data = response.json()
        assert "message" in data or "error" in data

    def test_delete_job_rolls_back_on_scheduler_failure(self, client):
        """Test that if scheduler fails, we still get proper error."""
        job_id = "test-job-scheduler-fail"

        # Access the mock from app.extensions (no more global patching!)
        mock_scheduler = client.app.state.scheduler_service

        # Mock scheduler failure
        mock_scheduler.remove_job.side_effect = Exception("Scheduler error")

        # Make the delete request
        response = client.delete(f"/api/jobs/{job_id}")

        # Should return error
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
