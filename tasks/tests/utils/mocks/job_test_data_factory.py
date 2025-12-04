"""Factory for creating job test data."""


class JobTestDataFactory:
    """Factory for creating job test data."""

    @staticmethod
    def create_sample_slack_users() -> list:
        """Create sample Slack users data for testing.

        Returns:
            list: List of user dictionaries with realistic Slack user structure
        """
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
    def create_metrics_data(
        metric_type: str = "usage", values: list | None = None
    ) -> dict:
        """Create sample metrics data for testing.

        Args:
            metric_type: Type of metric (e.g., "usage", "performance")
            values: List of metric values. Defaults to [1, 2, 3]

        Returns:
            dict: Metrics data structure
        """
        if values is None:
            values = [1, 2, 3]

        return {metric_type: {"data": values}}

    @staticmethod
    def create_job_execution_result(
        status: str = "success",
        job_name: str = "Test Job",
        result_data: dict | None = None,
    ) -> dict:
        """Create job execution result for testing.

        Args:
            status: Execution status (e.g., "success", "failure")
            job_name: Name of the job
            result_data: Job result data. Defaults to {"result": "success"}

        Returns:
            dict: Job execution result structure
        """
        if result_data is None:
            result_data = {"result": "success"}

        return {
            "status": status,
            "job_name": job_name,
            "result": result_data,
            "execution_time_seconds": 0.1,
        }
