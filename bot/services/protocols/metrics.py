"""
Metrics Service Protocol

Defines the interface for metrics collection services.
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MetricsServiceProtocol(Protocol):
    """Protocol for metrics service implementations."""

    def record_request(
        self, endpoint: str, user_id: str | None = None, **metadata
    ) -> None:
        """
        Record a request metric.

        Args:
            endpoint: API endpoint or service method called
            user_id: Optional user identifier
            **metadata: Additional metadata to record
        """
        ...

    def record_response_time(
        self, operation: str, duration_ms: float, success: bool = True, **metadata
    ) -> None:
        """
        Record response time metric.

        Args:
            operation: Name of the operation
            duration_ms: Duration in milliseconds
            success: Whether the operation succeeded
            **metadata: Additional metadata
        """
        ...

    def record_error(
        self, operation: str, error_type: str | None = None, **metadata
    ) -> None:
        """
        Record an error metric.

        Args:
            operation: Name of the operation that failed
            error_type: Type of error that occurred
            **metadata: Additional metadata
        """
        ...

    def get_usage_metrics(self) -> dict[str, Any]:
        """
        Get current usage metrics.

        Returns:
            Dict containing usage statistics
        """
        ...

    def get_performance_metrics(self) -> dict[str, Any]:
        """
        Get current performance metrics.

        Returns:
            Dict containing performance statistics
        """
        ...

    async def close(self) -> None:
        """Clean up resources."""
        ...

    def health_check(self) -> dict[str, str]:
        """Check service health status."""
        ...
