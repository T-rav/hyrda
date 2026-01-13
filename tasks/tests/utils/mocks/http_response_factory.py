"""Factory for creating HTTP response mocks."""

from unittest.mock import Mock


class HTTPResponseMockFactory:
    """Factory for creating HTTP response mocks."""

    @staticmethod
    def create_success_response(data: dict | None = None) -> Mock:
        """Create successful HTTP response mock.

        Args:
            data: Response data to return. Defaults to {"processed_count": 2}

        Returns:
            Mock: HTTP response mock with status 200 and data
        """
        if data is None:
            data = {"processed_count": 2}

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = data
        return mock_response

    @staticmethod
    def create_metrics_response(metrics_data: list | None = None) -> Mock:
        """Create HTTP response mock for metrics data.

        Args:
            metrics_data: List of metric dictionaries. Defaults to [{"metric": "value"}]

        Returns:
            Mock: HTTP response mock with metrics data
        """
        if metrics_data is None:
            metrics_data = [{"metric": "value"}]

        return HTTPResponseMockFactory.create_success_response({"data": metrics_data})

    @staticmethod
    def create_error_response(
        status_code: int = 500, error: str = "Server Error"
    ) -> Mock:
        """Create error HTTP response mock.

        Args:
            status_code: HTTP error status code
            error: Error message to return

        Returns:
            Mock: HTTP response mock with error status and message
        """
        mock_response = Mock()
        mock_response.status_code = status_code
        mock_response.json.return_value = {"error": error}
        return mock_response
