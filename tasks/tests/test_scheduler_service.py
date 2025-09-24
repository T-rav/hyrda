"""Tests for scheduler service - fixed version."""

import pytest

from services.scheduler_service import SchedulerService


class TestSchedulerService:
    """Test the scheduler service."""

    def test_scheduler_initialization(self, test_settings):
        """Test scheduler service initialization."""
        service = SchedulerService(test_settings)

        assert service.settings == test_settings
        assert service.scheduler is not None
        assert not service.scheduler.running

    def test_scheduler_start_stop(self, test_settings):
        """Test starting and stopping the scheduler."""
        # Use in-memory database for tests
        test_settings.database_url = "sqlite:///:memory:"
        service = SchedulerService(test_settings)

        # Test start
        service.start()
        assert service.scheduler.running

        # Test stop
        service.shutdown(wait=False)
        assert not service.scheduler.running

    def test_add_job(self, test_settings):
        """Test adding a job to the scheduler."""
        # Use in-memory scheduler for tests
        test_settings.database_url = "sqlite:///:memory:"
        service = SchedulerService(test_settings)
        service.start()

        # Use string reference instead of function object for serialization
        job = service.add_job(
            func="builtins:print",  # Built-in function that can be serialized
            trigger="interval",
            job_id="test_job",
            seconds=10,
            args=["test result"],
        )

        assert job.id == "test_job"

        # Cleanup
        service.shutdown(wait=False)

    def test_get_jobs(self, test_settings):
        """Test getting all jobs."""
        test_settings.database_url = "sqlite:///:memory:"
        service = SchedulerService(test_settings)
        service.start()

        # Add a test job
        service.add_job(
            func="builtins:print",
            trigger="interval",
            job_id="test_job_1",
            seconds=10,
            args=["test result"],
        )

        jobs = service.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == "test_job_1"

        # Cleanup
        service.shutdown(wait=False)

    def test_get_job_info_nonexistent(self, test_settings):
        """Test getting info for non-existent job."""
        service = SchedulerService(test_settings)

        job_info = service.get_job_info("nonexistent_job")
        assert job_info is None

    def test_get_scheduler_info_stopped(self, test_settings):
        """Test getting scheduler information when stopped."""
        service = SchedulerService(test_settings)

        # Test when not running
        info = service.get_scheduler_info()
        assert info["running"] is False
        assert info["jobs_count"] == 0

    def test_scheduler_error_handling(self, test_settings):
        """Test scheduler error handling."""
        service = SchedulerService(test_settings)
        # Don't start scheduler to test error handling

        # Test operations without initialized scheduler
        with pytest.raises(RuntimeError):
            service.add_job("builtins:print", "interval", seconds=1)

        with pytest.raises(RuntimeError):
            service.remove_job("nonexistent")

        with pytest.raises(RuntimeError):
            service.pause_job("nonexistent")

        with pytest.raises(RuntimeError):
            service.resume_job("nonexistent")

        with pytest.raises(RuntimeError):
            service.modify_job("nonexistent", name="test")
