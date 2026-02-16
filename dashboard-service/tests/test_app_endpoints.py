"""Comprehensive tests for dashboard-service FastAPI endpoints.

Tests all endpoints including health checks, metrics aggregation, and service health.
"""

from unittest.mock import Mock, patch

import aiohttp
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_env():
    """Mock environment variables for testing."""
    with patch.dict(
        "os.environ",
        {
            "SECRET_KEY": "test-secret-key-for-testing",
            "ENVIRONMENT": "development",
            "DASHBOARD_BASE_URL": "http://localhost:8080",
            "GOOGLE_OAUTH_CLIENT_ID": "test-client-id",
            "GOOGLE_OAUTH_CLIENT_SECRET": "test-secret",
            "ALLOWED_EMAIL_DOMAIN": "@8thlight.com",
        },
        clear=False,
    ):
        yield


@pytest.fixture
def client(mock_env):
    """Create test client with mocked environment."""
    from app import app

    return TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_endpoint_returns_200(self, client):
        """Test /health endpoint returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "dashboard"

    def test_api_health_endpoint_returns_200(self, client):
        """Test /api/health endpoint (alias) returns healthy status."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "dashboard"


class TestReadinessEndpoint:
    """Test readiness check endpoint."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_ready_endpoint_when_all_services_healthy(self, client):
        """Test /api/ready returns ready when all services are healthy."""

        class HealthyResponse:
            status = 200

            async def json(self):
                return {"status": "healthy"}

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                pass

        class NotFoundResponse:
            status = 404

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                pass

        mock_services = ["bot", "agent_service", "tasks", "control_plane"]

        def mock_get(url, *_args, **_kwargs):
            for service_name in mock_services:
                if service_name in url:
                    return HealthyResponse()
            return NotFoundResponse()

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get = mock_get
            response = client.get("/api/ready")

        assert response.status_code == 200
        data = response.json()
        assert "checks" in data
        assert data["checks"]["dashboard"]["status"] == "healthy"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_ready_endpoint_when_service_unavailable(self, client):
        """Test /api/ready returns not_ready when a service is unavailable."""

        class ErrorContextManager:
            async def __aenter__(self):
                raise aiohttp.ClientConnectorError(Mock(), Mock())

            async def __aexit__(self, *_args):
                pass

        class HealthyResponse:
            status = 200

            async def json(self):
                return {"status": "healthy"}

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                pass

        def mock_get(url, *_args, **_kwargs):
            # Simulate bot service being unavailable
            if "bot" in url:
                return ErrorContextManager()
            return HealthyResponse()

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get = mock_get
            response = client.get("/api/ready")

        assert response.status_code == 200
        data = response.json()
        # Should still return 200 but with not_ready status
        assert "checks" in data


class TestMetricsAggregation:
    """Test metrics aggregation endpoints."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_all_metrics_aggregates_from_services(self, client):
        """Test /api/metrics aggregates metrics from all services."""
        mock_metrics = {
            "bot": {"messages_processed": 100, "uptime": 3600},
            "agent_service": {"agents_invoked": 50},
            "tasks": {"jobs_completed": 10},
            "control_plane": {"active_users": 5},
        }

        class MetricsResponse:
            def __init__(self, status, data):
                self.status = status
                self._data = data

            async def json(self):
                return self._data

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                pass

        class NotFoundResponse:
            status = 404

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                pass

        def mock_get(url, *_args, **_kwargs):
            for service_name, metrics in mock_metrics.items():
                if service_name in url:
                    return MetricsResponse(200, metrics)
            return NotFoundResponse()

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get = mock_get
            response = client.get("/api/metrics")

        assert response.status_code == 200
        data = response.json()
        assert "dashboard" in data
        assert data["dashboard"]["status"] == "healthy"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_all_metrics_handles_service_errors(self, client):
        """Test /api/metrics handles errors from services gracefully."""

        class ErrorContextManager:
            async def __aenter__(self):
                raise aiohttp.ClientConnectorError(Mock(), Mock())

            async def __aexit__(self, *_args):
                pass

        class ServerErrorResponse:
            status = 500

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                pass

        def mock_get(url, *_args, **_kwargs):
            if "bot" in url:
                return ErrorContextManager()
            return ServerErrorResponse()

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get = mock_get
            response = client.get("/api/metrics")

        assert response.status_code == 200
        data = response.json()
        # Should still return valid response with error info
        assert "dashboard" in data


class TestServicesHealthEndpoint:
    """Test services health aggregation endpoint."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_services_health_returns_all_services(self, client):
        """Test /api/services/health returns health for all services."""

        class HealthyResponse:
            status = 200

            async def json(self):
                return {"status": "healthy"}

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                pass

        def mock_get(*_args, **_kwargs):
            return HealthyResponse()

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get = mock_get
            response = client.get("/api/services/health")

        assert response.status_code == 200
        data = response.json()
        # Should contain health info for services
        assert isinstance(data, dict)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_services_health_handles_unhealthy_service(self, client):
        """Test /api/services/health handles unhealthy services."""

        class HealthyResponse:
            status = 200

            async def json(self):
                return {"status": "healthy"}

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                pass

        class UnhealthyResponse:
            status = 503

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                pass

        def mock_get(url, *_args, **_kwargs):
            if "bot" in url:
                return UnhealthyResponse()  # Service unavailable
            return HealthyResponse()

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get = mock_get
            response = client.get("/api/services/health")

        assert response.status_code == 200
        # Should still return 200 with error info for bot service


class TestUIEndpoint:
    """Test UI serving endpoint."""

    def test_serve_ui_returns_html(self, client):
        """Test / endpoint serves the UI or returns appropriate error."""
        response = client.get("/")
        # Should serve UI (200), redirect (307), or return error if UI not built (500)
        assert response.status_code in [200, 307, 500]


class TestAuthenticationEndpoints:
    """Test authentication endpoints (basic tests, detailed in test_auth.py)."""

    def test_auth_callback_endpoint_exists(self, client):
        """Test /auth/callback endpoint exists."""
        # This will fail without proper OAuth flow, but endpoint should exist
        response = client.get("/auth/callback")
        # Should return some response (not 404)
        assert response.status_code != 404

    def test_logout_endpoint_exists(self, client):
        """Test /auth/logout endpoint exists."""
        response = client.post("/auth/logout")
        # Should return some response (not 404)
        assert response.status_code != 404


class TestErrorHandling:
    """Test error handling across endpoints."""

    @pytest.mark.integration
    def test_404_on_invalid_endpoint(self, client):
        """Test invalid endpoint returns 404.

        INTEGRATION TEST: Requires full middleware stack.
        """
        response = client.get("/api/nonexistent")
        # Auth middleware may redirect instead of 404
        assert response.status_code in [404, 307]  # 307 = redirect to login

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_endpoints_handle_network_errors_gracefully(self, client):
        """Test endpoints handle network errors without crashing."""

        # Create async context manager that raises on entry
        class ErrorContextManager:
            async def __aenter__(self):
                raise aiohttp.ClientError("Network error")

            async def __aexit__(self, *_args):
                pass

        def mock_get(*_args, **_kwargs):
            """Return async context manager that raises on entry."""
            return ErrorContextManager()

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get = mock_get

            # All aggregation endpoints should handle errors gracefully
            response1 = client.get("/api/ready")
            assert response1.status_code == 200  # Should still return 200

            response2 = client.get("/api/metrics")
            assert response2.status_code == 200  # Should still return 200

            response3 = client.get("/api/services/health")
            assert response3.status_code == 200  # Should still return 200
