"""Tests for job implementations."""

import asyncio
from unittest.mock import patch

import pytest

from jobs.base_job import BaseJob

# MetricsCollectionJob removed - module doesn't exist
# from jobs.metrics_collection import MetricsCollectionJob
from jobs.system.slack_user_import.job import SlackUserImportJob

# Import test utilities from centralized location
from tests.utils import (
    HTTPResponseMockFactory,
    SlackClientMockFactory,
)


class TestBaseJob:
    """Test the base job class."""

    def test_base_job_initialization(self, test_settings):
        """Test base job initialization."""

        class TestJob(BaseJob):
            JOB_NAME = "Test Job"
            JOB_DESCRIPTION = "A test job"

            async def _execute_job(self):
                return {"result": "success"}

        job = TestJob(test_settings, param1="value1")

        assert job.settings == test_settings
        assert job.params["param1"] == "value1"
        assert job.job_id.startswith("testjob_")

    def test_base_job_validation(self, test_settings):
        """Test job parameter validation."""

        class TestJob(BaseJob):
            REQUIRED_PARAMS = ["required_param"]

            async def _execute_job(self):
                return {"result": "success"}

        # Should work with required param
        job1 = TestJob(test_settings, required_param="value")
        assert job1.validate_params() is True

        # Should fail without required param
        job2 = TestJob(test_settings)
        with pytest.raises(ValueError, match="Required parameter missing"):
            job2.validate_params()

    @pytest.mark.asyncio
    async def test_base_job_execution_success(self, test_settings):
        """Test successful job execution."""

        class TestJob(BaseJob):
            JOB_NAME = "Test Job"

            async def _execute_job(self):
                return {"result": "success", "data": "test_data"}

        job = TestJob(test_settings)
        result = await job.execute()

        assert result["status"] == "success"
        assert result["job_name"] == "Test Job"
        assert result["result"]["result"] == "success"
        assert "execution_time_seconds" in result

    @pytest.mark.asyncio
    async def test_base_job_execution_error(self, test_settings):
        """Test job execution with error."""

        class TestJob(BaseJob):
            JOB_NAME = "Test Job"

            async def _execute_job(self):
                raise ValueError("Test error")

        job = TestJob(test_settings)
        result = await job.execute()

        assert result["status"] == "error"
        assert result["error"] == "Test error"
        assert "execution_time_seconds" in result


class TestSlackUserImportJob:
    """Test Slack user import job."""

    def test_slack_user_import_job_init(self, test_settings):
        """Test Slack user import job initialization."""
        job = SlackUserImportJob(test_settings)
        assert job.JOB_NAME == "Slack User Import"
        assert job.slack_client is not None

    def test_slack_user_import_job_validation_no_token(self, test_settings):
        """Test validation fails without Slack token."""
        # Remove Slack token from settings
        test_settings.slack_bot_token = None

        with pytest.raises(ValueError, match="SLACK_BOT_TOKEN is required"):
            SlackUserImportJob(test_settings)

    @pytest.mark.asyncio
    @patch("slack_sdk.WebClient")
    async def test_slack_user_import_execution(
        self, mock_web_client, test_settings, sample_slack_users
    ):
        """Test Slack user import execution."""
        # Mock Slack client using factory
        mock_client_instance = SlackClientMockFactory.create_client_with_users(
            sample_slack_users
        )
        mock_web_client.return_value = mock_client_instance

        # Note: HTTP requests are mocked via patch.object on internal methods

        job = SlackUserImportJob(test_settings)
        job.slack_client = mock_client_instance

        # Execute job (synchronous wrapper for async method)
        with (
            patch.object(job, "_fetch_slack_users", return_value=sample_slack_users),
            patch.object(
                job, "_store_users_in_database", return_value={"processed_count": 2}
            ),
        ):
            result = await job.execute()

        assert result["status"] == "success"
        assert "total_users_fetched" in result["result"]
        assert "records_processed" in result["result"]

    def test_filter_users(self, test_settings, sample_slack_users):
        """Test user filtering logic."""
        job = SlackUserImportJob(test_settings)

        # Filter for members only
        filtered = job._filter_users(sample_slack_users, ["member"])
        assert len(filtered) == 1
        assert filtered[0]["id"] == "U1234567"

        # Filter for admins only
        filtered = job._filter_users(sample_slack_users, ["admin"])
        assert len(filtered) == 1
        assert filtered[0]["id"] == "U2345678"

        # Filter for all types
        filtered = job._filter_users(sample_slack_users, ["member", "admin"])
        assert len(filtered) == 2


@pytest.mark.skip(reason="MetricsCollectionJob module doesn't exist")
class TestMetricsCollectionJob:
    """Test metrics collection job."""

    def test_metrics_collection_job_init(self, test_settings):
        """Test metrics collection job initialization."""
        job = MetricsCollectionJob(test_settings)  # noqa: F821
        assert job.JOB_NAME == "Metrics Collection"

    @pytest.mark.asyncio
    @patch("jobs.metrics_collection.requests")
    async def test_metrics_collection_execution(self, mock_requests, test_settings):
        """Test metrics collection execution."""
        # Mock API responses using factory
        mock_response = HTTPResponseMockFactory.create_metrics_response(
            [{"metric": "value"}]
        )
        mock_requests.get.return_value = mock_response
        mock_requests.post.return_value = mock_response

        job = MetricsCollectionJob(test_settings)  # noqa: F821
        result = await job.execute()

        assert result["status"] == "success"
        assert "collected_metrics" in result["result"]
        assert "aggregated_metrics" in result["result"]

    def test_metrics_aggregation(self, test_settings):
        """Test metrics aggregation logic."""
        job = MetricsCollectionJob(test_settings)  # noqa: F821

        sample_metrics = {
            "usage": {"data": [1, 2, 3]},
            "performance": {"error": "API unavailable"},
        }

        aggregated = job._aggregate_metrics(sample_metrics, "hourly")

        assert aggregated["aggregation_level"] == "hourly"
        assert aggregated["summary"]["usage"]["status"] == "success"
        assert aggregated["summary"]["performance"]["status"] == "error"

    @patch("jobs.metrics_collection.requests.get")
    def test_collect_usage_metrics_no_api(self, mock_get, test_settings):
        """Test collecting usage metrics without API URL."""
        # Remove API URL
        test_settings.slack_bot_api_url = None

        job = MetricsCollectionJob(test_settings)  # noqa: F821

        # Use asyncio.run to run the async method
        result = asyncio.run(job._collect_usage_metrics(24))

        assert "error" in result
        assert result["error"] == "No bot API URL configured"
