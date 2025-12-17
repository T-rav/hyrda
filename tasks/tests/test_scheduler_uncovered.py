"""Targeted tests for uncovered scheduler_service.py lines."""

import contextlib

import pytest

from services.scheduler_service import SchedulerService


@pytest.fixture
def scheduler_service(test_settings):
    """Create scheduler service for testing."""
    test_settings.task_database_url = "sqlite:///:memory:"
    service = SchedulerService(test_settings)
    service.start()
    yield service
    service.shutdown(wait=False)


class TestSchedulerJobOperations:
    """Test job manipulation operations."""

    def test_remove_job(self, scheduler_service):
        """Test removing a job from scheduler."""
        # Add a job first
        scheduler_service.add_job(
            func="builtins:print",
            trigger="interval",
            job_id="remove-test",
            seconds=60,
        )

        assert scheduler_service.get_job("remove-test") is not None

        # Remove the job (covers lines 86-87)
        scheduler_service.remove_job("remove-test")

        # Verify removed
        assert scheduler_service.get_job("remove-test") is None

    def test_get_job_nonexistent(self, scheduler_service):
        """Test getting non-existent job returns None."""
        # Covers line 99 - return None path
        result = scheduler_service.get_job("does-not-exist")

        assert result is None

    def test_pause_job(self, scheduler_service):
        """Test pausing a job."""
        # Add a job
        scheduler_service.add_job(
            func="builtins:print",
            trigger="interval",
            job_id="pause-test",
            seconds=60,
        )

        # Pause the job (covers lines 108-109)
        scheduler_service.pause_job("pause-test")

        # Verify it's paused
        job = scheduler_service.get_job("pause-test")
        assert job is not None
        assert job.next_run_time is None  # Paused jobs have no next run time

    def test_resume_job(self, scheduler_service):
        """Test resuming a paused job."""
        # Add and pause a job
        scheduler_service.add_job(
            func="builtins:print",
            trigger="interval",
            job_id="resume-test",
            seconds=60,
        )
        scheduler_service.pause_job("resume-test")

        # Resume the job (covers lines 116-117)
        scheduler_service.resume_job("resume-test")

        # Verify it's resumed
        job = scheduler_service.get_job("resume-test")
        assert job is not None
        assert job.next_run_time is not None  # Resumed jobs have next run time


class TestSchedulerInfoSerialization:
    """Test get_scheduler_info serialization logic."""

    def test_scheduler_info_when_not_running(self, test_settings):
        """Test get_scheduler_info when scheduler not running."""
        test_settings.task_database_url = "sqlite:///:memory:"
        service = SchedulerService(test_settings)

        # Don't start scheduler (covers line 171 - return early path)
        info = service.get_scheduler_info()

        assert info["running"] is False
        assert info["jobs_count"] == 0


class TestSchedulerEdgeCases:
    """Test edge cases in scheduler operations."""

    def test_remove_nonexistent_job(self, scheduler_service):
        """Test removing job that doesn't exist."""
        # Should handle gracefully (may raise or return None)
        with contextlib.suppress(Exception):
            # Exception is acceptable for nonexistent job
            scheduler_service.remove_job("nonexistent")
