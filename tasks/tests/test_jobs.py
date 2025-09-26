"""Tests for job implementations."""

import asyncio
from unittest.mock import Mock, patch

import pytest

from jobs.base_job import BaseJob
from jobs.metrics_collection import MetricsCollectionJob
from jobs.slack_user_import import SlackUserImportJob


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

    def test_base_job_execution_success(self, test_settings):
        """Test successful job execution."""

        class TestJob(BaseJob):
            JOB_NAME = "Test Job"

            async def _execute_job(self):
                return {"result": "success", "data": "test_data"}

        job = TestJob(test_settings)
        result = job.execute()

        assert result["status"] == "success"
        assert result["job_name"] == "Test Job"
        assert result["result"]["result"] == "success"
        assert "execution_time_seconds" in result

    def test_base_job_execution_error(self, test_settings):
        """Test job execution with error."""

        class TestJob(BaseJob):
            JOB_NAME = "Test Job"

            async def _execute_job(self):
                raise ValueError("Test error")

        job = TestJob(test_settings)
        result = job.execute()

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

    @patch("jobs.slack_user_import.requests")
    @patch("slack_sdk.WebClient")
    def test_slack_user_import_execution(
        self, mock_web_client, mock_requests, test_settings, sample_slack_users
    ):
        """Test Slack user import execution."""
        # Mock Slack client
        mock_client_instance = Mock()
        mock_client_instance.users_list.return_value = {
            "ok": True,
            "members": sample_slack_users,
            "response_metadata": {},
        }
        mock_web_client.return_value = mock_client_instance

        # Mock requests
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"processed_count": 2}
        mock_requests.post.return_value = mock_response

        job = SlackUserImportJob(test_settings)
        job.slack_client = mock_client_instance

        # Execute job (synchronous wrapper for async method)
        with (
            patch.object(job, "_fetch_slack_users", return_value=sample_slack_users),
            patch.object(
                job, "_send_users_to_bot_api", return_value={"processed_count": 2}
            ),
        ):
            result = job.execute()

        assert result["status"] == "success"
        assert result["result"]["total_users_fetched"] == 2
        assert result["result"]["processed_users_count"] == 2

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


class TestMetricsCollectionJob:
    """Test metrics collection job."""

    def test_metrics_collection_job_init(self, test_settings):
        """Test metrics collection job initialization."""
        job = MetricsCollectionJob(test_settings)
        assert job.JOB_NAME == "Metrics Collection"

    @patch("jobs.metrics_collection.requests")
    def test_metrics_collection_execution(self, mock_requests, test_settings):
        """Test metrics collection execution."""
        # Mock API responses
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"metric": "value"}]}
        mock_requests.get.return_value = mock_response
        mock_requests.post.return_value = mock_response

        job = MetricsCollectionJob(test_settings)
        result = job.execute()

        assert result["status"] == "success"
        assert "collected_metrics" in result["result"]
        assert "aggregated_metrics" in result["result"]

    def test_metrics_aggregation(self, test_settings):
        """Test metrics aggregation logic."""
        job = MetricsCollectionJob(test_settings)

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

        job = MetricsCollectionJob(test_settings)

        # Use asyncio.run to run the async method
        result = asyncio.run(job._collect_usage_metrics(24))

        assert "error" in result
        assert result["error"] == "No bot API URL configured"
