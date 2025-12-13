"""Prometheus metrics middleware for FastAPI applications.

Automatically tracks:
- HTTP request count (by method, path, status code)
- Request duration (histogram with percentiles)
- Requests in progress (gauge)
- Error rates (by endpoint and error type)

Exports metrics at /metrics endpoint for Prometheus scraping.
"""

import logging
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.routing import Match
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Try to import prometheus_client
try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    logger.warning("prometheus_client not installed - metrics disabled")
    PROMETHEUS_AVAILABLE = False


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for Prometheus metrics collection.

    Tracks HTTP requests and exports metrics at /metrics endpoint.
    """

    def __init__(self, app: ASGIApp, service_name: str):
        """Initialize Prometheus metrics middleware.

        Args:
            app: ASGI application
            service_name: Name of this service (used as label)
        """
        super().__init__(app)
        self.service_name = service_name

        if not PROMETHEUS_AVAILABLE:
            logger.warning(
                f"Prometheus metrics disabled for {service_name} - install prometheus_client"
            )
            return

        # HTTP request counter
        self.requests_total = Counter(
            f"{service_name}_http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status_code"],
        )

        # HTTP request duration histogram
        self.request_duration = Histogram(
            f"{service_name}_http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint"],
            buckets=(
                0.005,
                0.01,
                0.025,
                0.05,
                0.1,
                0.25,
                0.5,
                1.0,
                2.5,
                5.0,
                10.0,
            ),  # 5ms to 10s
        )

        # Requests in progress gauge
        self.requests_in_progress = Gauge(
            f"{service_name}_http_requests_in_progress",
            "HTTP requests currently in progress",
            ["method", "endpoint"],
        )

        # Error counter
        self.errors_total = Counter(
            f"{service_name}_http_errors_total",
            "Total HTTP errors",
            ["method", "endpoint", "status_code"],
        )

        logger.info(f"Prometheus metrics initialized for {service_name}")

    def _get_endpoint_path(self, request: Request) -> str:
        """Get normalized endpoint path for metrics.

        Returns path template (e.g., /api/agents/{agent_name}/invoke)
        instead of actual path (e.g., /api/agents/profile/invoke)
        to avoid high cardinality.
        """
        # Try to get the route pattern
        for route in request.app.routes:
            match, _ = route.matches(request.scope)
            if match == Match.FULL:
                return route.path

        # Fallback to actual path
        return request.url.path

    async def dispatch(self, request: Request, call_next):
        """Process request and collect metrics."""
        if not PROMETHEUS_AVAILABLE:
            return await call_next(request)

        method = request.method
        endpoint = self._get_endpoint_path(request)

        # Track request in progress
        self.requests_in_progress.labels(method=method, endpoint=endpoint).inc()

        # Start timing
        start_time = time.time()

        try:
            # Process request
            response = await call_next(request)
            status_code = response.status_code

            # Record metrics
            duration = time.time() - start_time
            self.request_duration.labels(method=method, endpoint=endpoint).observe(
                duration
            )
            self.requests_total.labels(
                method=method, endpoint=endpoint, status_code=status_code
            ).inc()

            # Track errors (4xx, 5xx)
            if status_code >= 400:
                self.errors_total.labels(
                    method=method, endpoint=endpoint, status_code=status_code
                ).inc()

            return response

        except Exception:
            # Record error metrics
            duration = time.time() - start_time
            self.request_duration.labels(method=method, endpoint=endpoint).observe(
                duration
            )
            self.errors_total.labels(
                method=method, endpoint=endpoint, status_code="500"
            ).inc()

            # Re-raise
            raise

        finally:
            # Decrement in-progress counter
            self.requests_in_progress.labels(method=method, endpoint=endpoint).dec()


def create_metrics_endpoint() -> Callable:
    """Create /metrics endpoint handler for Prometheus scraping.

    Returns:
        FastAPI endpoint function

    Example:
        app.get("/metrics")(create_metrics_endpoint())
    """
    if not PROMETHEUS_AVAILABLE:

        async def metrics_disabled():
            return {"error": "Prometheus metrics not available"}

        return metrics_disabled

    async def metrics():
        """Metrics endpoint for Prometheus scraping."""
        from starlette.responses import Response

        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return metrics
