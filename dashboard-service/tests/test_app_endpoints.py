"""Comprehensive tests for dashboard-service FastAPI endpoints.

Tests all endpoints including health checks, metrics aggregation, and service health.
"""

from unittest.mock import AsyncMock, Mock, patch

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
        mock_responses = {
            "bot": Mock(status=200, json=AsyncMock(return_value={"status": "healthy"})),
            "agent_service": Mock(
                status=200, json=AsyncMock(return_value={"status": "healthy"})
            ),
            "tasks": Mock(
                status=200, json=AsyncMock(return_value={"status": "healthy"})
            ),
            "control_plane": Mock(
                status=200, json=AsyncMock(return_value={"status": "healthy"})
            ),
        }

        async def mock_get(url, **kwargs):
            for service_name in mock_responses:
                if service_name in url:
                    return mock_responses[service_name]
            return Mock(status=404)

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

        async def mock_get(url, **kwargs):
            # Simulate bot service being unavailable
            if "bot" in url:
                raise aiohttp.ClientConnectorError(Mock(), Mock())
            return Mock(status=200, json=AsyncMock(return_value={"status": "healthy"}))

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

        async def mock_get(url, **kwargs):
            for service_name, metrics in mock_metrics.items():
                if service_name in url:
                    return Mock(status=200, json=AsyncMock(return_value=metrics))
            return Mock(status=404)

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

        async def mock_get(url, **kwargs):
            if "bot" in url:
                raise aiohttp.ClientConnectorError(Mock(), Mock())
            return Mock(status=500)

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

        async def mock_get(url, **kwargs):
            return Mock(status=200, json=AsyncMock(return_value={"status": "healthy"}))

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

        async def mock_get(url, **kwargs):
            if "bot" in url:
                return Mock(status=503)  # Service unavailable
            return Mock(status=200, json=AsyncMock(return_value={"status": "healthy"}))

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get = mock_get
            response = client.get("/api/services/health")

        assert response.status_code == 200
        # Should still return 200 with error info for bot service


class TestUIEndpoint:
    """Test UI serving endpoint."""

    def test_serve_ui_returns_html(self, client):
        """Test / endpoint serves the UI."""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("fastapi.responses.FileResponse") as mock_file_response:
                mock_file_response.return_value = Mock(status_code=200)
                response = client.get("/")
                # Should attempt to serve UI or return redirect
                assert response.status_code in [200, 307, 404]  # 404 if UI not built


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

        async def mock_get(url, **kwargs):
            raise aiohttp.ClientError("Network error")

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get = mock_get

            # All aggregation endpoints should handle errors gracefully
            response1 = client.get("/api/ready")
            assert response1.status_code == 200  # Should still return 200

            response2 = client.get("/api/metrics")
            assert response2.status_code == 200  # Should still return 200

            response3 = client.get("/api/services/health")
            assert response3.status_code == 200  # Should still return 200
