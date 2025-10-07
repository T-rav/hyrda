"""Tests for job registry."""

import pytest

from jobs.job_registry import JobRegistry
from services.scheduler_service import SchedulerService


class TestJobRegistry:
    """Test the job registry."""

    def test_job_registry_initialization(self, test_settings):
        """Test job registry initialization."""
        scheduler_service = SchedulerService(test_settings)
        registry = JobRegistry(test_settings, scheduler_service)

        assert registry.settings == test_settings
        assert registry.scheduler_service == scheduler_service
        assert len(registry.job_types) > 0

    def test_get_available_job_types(self, test_settings):
        """Test getting available job types."""
        scheduler_service = SchedulerService(test_settings)
        registry = JobRegistry(test_settings, scheduler_service)

        job_types = registry.get_available_job_types()

        assert isinstance(job_types, list)
        assert len(job_types) > 0

        # Check that each job type has required fields
        for job_type in job_types:
            assert "type" in job_type
            assert "name" in job_type
            assert "description" in job_type
            assert "required_params" in job_type
            assert "optional_params" in job_type

        # Check for expected job types
        job_type_names = [jt["type"] for jt in job_types]
        assert "slack_user_import" in job_type_names
        assert "metric_sync" in job_type_names

    def test_create_slack_user_import_job(self, test_settings):
        """Test creating a Slack user import job."""
        scheduler_service = SchedulerService(test_settings)
        scheduler_service.start()
        registry = JobRegistry(test_settings, scheduler_service)

        job = registry.create_job(
            job_type="slack_user_import",
            job_id="test_slack_import",
            schedule={"trigger": "interval", "hours": 1},
            user_types=["member", "admin"],
        )

        assert job.id == "test_slack_import"
        assert job.name == "Slack User Import"

        # Cleanup
        scheduler_service.shutdown(wait=False)

    def test_create_metric_sync_job(self, test_settings):
        """Test creating a metric sync job."""
        scheduler_service = SchedulerService(test_settings)
        scheduler_service.start()
        registry = JobRegistry(test_settings, scheduler_service)

        job = registry.create_job(
            job_type="metric_sync",
            job_id="test_metrics",
            schedule={"trigger": "interval", "minutes": 30},
        )

        assert job.id == "test_metrics"
        assert job.name == "Metric.ai Data Sync"

        # Cleanup
        scheduler_service.shutdown(wait=False)

    def test_create_job_with_default_schedule(self, test_settings):
        """Test creating a job with default schedule."""
        scheduler_service = SchedulerService(test_settings)
        scheduler_service.start()
        registry = JobRegistry(test_settings, scheduler_service)

        job = registry.create_job(
            job_type="metric_sync", job_id="test_default_schedule"
        )

        assert job.id == "test_default_schedule"
        # Default schedule should be interval every 1 hour

        # Cleanup
        scheduler_service.shutdown(wait=False)

    def test_create_job_invalid_type(self, test_settings):
        """Test creating a job with invalid type."""
        scheduler_service = SchedulerService(test_settings)
        registry = JobRegistry(test_settings, scheduler_service)

        with pytest.raises(ValueError, match="Unknown job type"):
            registry.create_job(job_type="invalid_job_type", job_id="test_invalid")

    def test_get_job_class(self, test_settings):
        """Test getting job class by type."""
        scheduler_service = SchedulerService(test_settings)
        registry = JobRegistry(test_settings, scheduler_service)

        # Test valid job types
        slack_class = registry.get_job_class("slack_user_import")
        assert slack_class is not None

        metric_sync_class = registry.get_job_class("metric_sync")
        assert metric_sync_class is not None

        # Test invalid job type
        invalid_class = registry.get_job_class("invalid_type")
        assert invalid_class is None

    def test_create_job_with_cron_schedule(self, test_settings):
        """Test creating a job with cron schedule."""
        scheduler_service = SchedulerService(test_settings)
        scheduler_service.start()
        registry = JobRegistry(test_settings, scheduler_service)

        job = registry.create_job(
            job_type="metric_sync",
            job_id="test_cron_job",
            schedule={"trigger": "cron", "hour": 0, "minute": 0},
        )

        assert job.id == "test_cron_job"

        # Cleanup
        scheduler_service.shutdown(wait=False)

    def test_create_job_auto_generated_id(self, test_settings):
        """Test creating a job with auto-generated ID."""
        scheduler_service = SchedulerService(test_settings)
        scheduler_service.start()
        registry = JobRegistry(test_settings, scheduler_service)

        job = registry.create_job(
            job_type="metric_sync",
            # No job_id provided, should be auto-generated
            schedule={"trigger": "interval", "minutes": 15},
        )

        assert job.id.startswith("metric_sync_")

        # Cleanup
        scheduler_service.shutdown(wait=False)
