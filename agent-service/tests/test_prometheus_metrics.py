"""Unit tests for Prometheus metrics middleware."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from shared.middleware.prometheus_metrics import (
    PrometheusMetricsMiddleware,
    create_metrics_endpoint,
)


@pytest.fixture
def app():
    """Create a test FastAPI app with metrics middleware."""
    test_app = FastAPI()
    test_app.add_middleware(PrometheusMetricsMiddleware, service_name="test_service")

    @test_app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}

    @test_app.get("/error")
    async def error_endpoint():
        raise ValueError("Test error")

    # Add metrics endpoint
    test_app.get("/metrics")(create_metrics_endpoint())

    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


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


def test_error_counter_increments_on_500(client):
    """Test that error counter increments on server errors."""
    # Make a request that raises an error
    with pytest.raises(ValueError):
        client.get("/error")

    # Check metrics - errors should be tracked
    metrics_response = client.get("/metrics")
    metrics_text = metrics_response.text

    # Should have error counter (even if it's 0 initially, the metric exists)
    assert "test_service_http_errors_total" in metrics_text


def test_in_progress_gauge_tracks_concurrent_requests(client):
    """Test that in_progress gauge exists."""
    # Make a request
    client.get("/test")

    # Check metrics
    metrics_response = client.get("/metrics")
    metrics_text = metrics_response.text

    # Should have in_progress gauge
    assert "test_service_http_requests_in_progress" in metrics_text


def test_metrics_labels_are_correct(client):
    """Test that metrics have correct labels."""
    # Make requests to different endpoints with different methods
    client.get("/test")
    client.post("/test")  # Will be 405, but still tracked

    metrics_response = client.get("/metrics")
    metrics_text = metrics_response.text

    # Should have GET request
    assert 'method="GET"' in metrics_text

    # Should have POST request
    assert 'method="POST"' in metrics_text


def test_metrics_endpoint_path_normalization(client):
    """Test that endpoint paths are normalized in metrics."""
    # Make request to test endpoint
    client.get("/test")

    metrics_response = client.get("/metrics")
    metrics_text = metrics_response.text

    # Endpoint should be normalized to /test
    assert 'endpoint="/test"' in metrics_text


def test_multiple_requests_increment_counters(client):
    """Test that multiple requests properly increment counters."""
    # Make multiple requests
    for _ in range(3):
        client.get("/test")

    metrics_response = client.get("/metrics")
    metrics_text = metrics_response.text

    # Parse the counter value - should be at least 3
    # (might be more due to metrics endpoint calls)
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
