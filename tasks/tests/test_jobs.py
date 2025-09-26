"""Tests for job implementations."""

import asyncio
from unittest.mock import Mock, patch

import pytest

from jobs.base_job import BaseJob
from jobs.metrics_collection import MetricsCollectionJob
from jobs.slack_user_import import SlackUserImportJob


# TDD Factory Patterns for Tasks Test Suite
class SlackClientMockFactory:
    """Factory for creating Slack client mocks"""

    @staticmethod
    def create_basic_client() -> Mock:
        """Create basic Slack client mock"""
        mock_client = Mock()
        mock_client.users_list.return_value = {
            "ok": True,
            "members": [],
            "response_metadata": {},
        }
        return mock_client

    @staticmethod
    def create_client_with_users(users: list) -> Mock:
        """Create Slack client mock with specific users"""
        mock_client = SlackClientMockFactory.create_basic_client()
        mock_client.users_list.return_value["members"] = users
        return mock_client

    @staticmethod
    def create_failing_client(error: str = "API Error") -> Mock:
        """Create Slack client mock that fails"""
        mock_client = Mock()
        mock_client.users_list.side_effect = Exception(error)
        return mock_client


class HTTPResponseMockFactory:
    """Factory for creating HTTP response mocks"""

    @staticmethod
    def create_success_response(data: dict = None) -> Mock:
        """Create successful HTTP response mock"""
        if data is None:
            data = {"processed_count": 2}

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = data
        return mock_response

    @staticmethod
    def create_metrics_response(metrics_data: list = None) -> Mock:
        """Create HTTP response mock for metrics data"""
        if metrics_data is None:
            metrics_data = [{"metric": "value"}]

        return HTTPResponseMockFactory.create_success_response({"data": metrics_data})

    @staticmethod
    def create_error_response(
        status_code: int = 500, error: str = "Server Error"
    ) -> Mock:
        """Create error HTTP response mock"""
        mock_response = Mock()
        mock_response.status_code = status_code
        mock_response.json.return_value = {"error": error}
        return mock_response


class JobTestDataFactory:
    """Factory for creating job test data"""

    @staticmethod
    def create_sample_slack_users() -> list:
        """Create sample Slack users data"""
        return [
            {
                "id": "U1234567",
                "name": "test.user",
                "is_admin": False,
                "is_owner": False,
                "profile": {"email": "test.user@example.com"},
            },
            {
                "id": "U2345678",
                "name": "admin.user",
                "is_admin": True,
                "is_owner": False,
                "profile": {"email": "admin.user@example.com"},
            },
        ]

    @staticmethod
    def create_metrics_data(metric_type: str = "usage", values: list = None) -> dict:
        """Create sample metrics data"""
        if values is None:
            values = [1, 2, 3]

        return {metric_type: {"data": values}}

    @staticmethod
    def create_job_execution_result(
        status: str = "success", job_name: str = "Test Job", result_data: dict = None
    ) -> dict:
        """Create job execution result"""
        if result_data is None:
            result_data = {"result": "success"}

        return {
            "status": status,
            "job_name": job_name,
            "result": result_data,
            "execution_time_seconds": 0.1,
        }


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

    @patch("slack_sdk.WebClient")
    def test_slack_user_import_execution(
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
            result = job.execute()

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


class TestMetricsCollectionJob:
    """Test metrics collection job."""

    def test_metrics_collection_job_init(self, test_settings):
        """Test metrics collection job initialization."""
        job = MetricsCollectionJob(test_settings)
        assert job.JOB_NAME == "Metrics Collection"

    @patch("jobs.metrics_collection.requests")
    def test_metrics_collection_execution(self, mock_requests, test_settings):
        """Test metrics collection execution."""
        # Mock API responses using factory
        mock_response = HTTPResponseMockFactory.create_metrics_response(
            [{"metric": "value"}]
        )
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
