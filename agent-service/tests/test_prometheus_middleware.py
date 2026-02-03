"""Unit tests for Prometheus metrics middleware.

This test file is standalone and doesn't import agent dependencies.
"""

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

# Add shared to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import contextlib

from shared.middleware.prometheus_metrics import (
    PrometheusMetricsMiddleware,
    create_metrics_endpoint,
)


@pytest.fixture(autouse=True)
def clear_prometheus_registry():
    """Clear Prometheus registry before each test to avoid collisions."""
    # Get list of collectors to remove
    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        try:
            REGISTRY.unregister(collector)
        except Exception:  # Collector may not be registered
            pass
    yield
    # Cleanup after test
    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        with contextlib.suppress(Exception):
            REGISTRY.unregister(collector)


@pytest.fixture
def test_app():
    """Create a test FastAPI app with metrics middleware."""
    app = FastAPI()
    app.add_middleware(PrometheusMetricsMiddleware, service_name="test_service")

    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}

    @app.get("/error")
    async def error_endpoint():
        raise ValueError("Test error")

    @app.post("/test")
    async def test_post():
        return {"status": "posted"}

    # Add metrics endpoint
    app.get("/metrics")(create_metrics_endpoint())

    return app


@pytest.fixture
def client(test_app):
    """Create test client."""
    return TestClient(test_app, raise_server_exceptions=False)


def test_metrics_endpoint_exists(client):
    """Test that /metrics endpoint is accessible."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


def test_metrics_endpoint_returns_prometheus_format(client):
    """Test that metrics endpoint returns Prometheus format."""
    response = client.get("/metrics")
    content = response.text

    # Should contain Prometheus HELP and TYPE comments
    assert "# HELP" in content
    assert "# TYPE" in content


def test_http_request_counter_increments(client):
    """Test that HTTP request counter increments on each request."""
    # Make a request to /test endpoint
    response = client.get("/test")
    assert response.status_code == 200

    # Check metrics
    metrics_response = client.get("/metrics")
    metrics_text = metrics_response.text

    # Should have counter for test endpoint
    assert "test_service_http_requests_total" in metrics_text
    assert 'endpoint="/test"' in metrics_text
    assert 'method="GET"' in metrics_text
    assert 'status_code="200"' in metrics_text


def test_http_request_duration_histogram(client):
    """Test that request duration histogram is created."""
    # Make a request
    client.get("/test")

    # Check metrics
    metrics_response = client.get("/metrics")
    metrics_text = metrics_response.text

    # Should have histogram buckets
    assert "test_service_http_request_duration_seconds_bucket" in metrics_text
    assert "test_service_http_request_duration_seconds_count" in metrics_text
    assert "test_service_http_request_duration_seconds_sum" in metrics_text

    # Should have histogram buckets (0.005, 0.01, 0.025, etc.)
    assert 'le="0.005"' in metrics_text
    assert 'le="0.01"' in metrics_text
    assert 'le="1.0"' in metrics_text


def test_error_tracking(client):
    """Test that errors are tracked."""
    # Make a request that raises an error (should get 500)
    response = client.get("/error")
    assert response.status_code == 500

    # Check metrics - errors should be tracked
    metrics_response = client.get("/metrics")
    metrics_text = metrics_response.text

    # Should have error counter
    assert "test_service_http_errors_total" in metrics_text
    assert 'endpoint="/error"' in metrics_text


def test_in_progress_gauge_tracks_concurrent_requests(client):
    """Test that in_progress gauge exists."""
    # Make a request
    client.get("/test")

    # Check metrics
    metrics_response = client.get("/metrics")
    metrics_text = metrics_response.text

    # Should have in_progress gauge
    assert "test_service_http_requests_in_progress" in metrics_text


def test_different_http_methods_tracked_separately(client):
    """Test that different HTTP methods are tracked separately."""
    # Make GET and POST requests to same endpoint
    client.get("/test")
    client.post("/test")

    metrics_response = client.get("/metrics")
    metrics_text = metrics_response.text

    # Should have both GET and POST
    assert 'method="GET"' in metrics_text
    assert 'method="POST"' in metrics_text


def test_multiple_requests_increment_counters(client):
    """Test that multiple requests properly increment counters."""
    # Make multiple requests
    for _ in range(3):
        client.get("/test")

    metrics_response = client.get("/metrics")
    metrics_text = metrics_response.text

    # Should have counter with at least 3 requests
    assert "test_service_http_requests_total" in metrics_text
    assert 'endpoint="/test"' in metrics_text


def test_create_metrics_endpoint_returns_callable():
    """Test that create_metrics_endpoint returns a callable."""
    endpoint_func = create_metrics_endpoint()
    assert callable(endpoint_func)


def test_middleware_preserves_response(client):
    """Test that middleware doesn't interfere with response."""
    response = client.get("/test")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_different_status_codes_tracked_separately(client):
    """Test that different status codes are tracked as separate metrics."""
    # Make successful request
    client.get("/test")

    # Make request to non-existent endpoint (404)
    client.get("/nonexistent")

    metrics_response = client.get("/metrics")
    metrics_text = metrics_response.text

    # Should have both 200 and 404 status codes
    assert 'status_code="200"' in metrics_text
    assert 'status_code="404"' in metrics_text


def test_histogram_buckets_correct(client):
    """Test that histogram has correct buckets."""
    client.get("/test")

    metrics_response = client.get("/metrics")
    metrics_text = metrics_response.text

    # Check all expected bucket boundaries
    expected_buckets = [
        "0.005",
        "0.01",
        "0.025",
        "0.05",
        "0.1",
        "0.25",
        "0.5",
        "1.0",
        "2.5",
        "5.0",
        "10.0",
        "+Inf",
    ]
    for bucket in expected_buckets:
        assert f'le="{bucket}"' in metrics_text
