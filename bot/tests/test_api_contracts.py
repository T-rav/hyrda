"""
API Contract Tests - Protect against API changes

Tests to ensure API endpoints maintain expected contracts and protect against
dashboard/frontend breaking changes.
"""

from unittest.mock import Mock, patch

from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase

from bot.health import HealthChecker
from config.settings import Settings


# TDD Factory Patterns for API Contract Testing
class APIContractFactory:
    """Factory for creating API contract test data and configurations"""

    @staticmethod
    def create_mock_settings():
        """Create mock settings for API testing"""
        settings = Mock(spec=Settings)
        settings.health_port = 8080
        settings.environment = "test"
        return settings

    @staticmethod
    def create_health_endpoints():
        """Create list of health API endpoints"""
        return [
            "/api/health",
            "/api/ready",
            "/api/metrics",
            "/api/prometheus",
            "/api/services/health",
            "/api/users/import",
            "/api/ingest/completed",
            "/api/metrics/usage",
            "/api/metrics/performance",
        ]


class TestHealthAPIContracts(AioHTTPTestCase):
    """Test health API endpoint contracts to prevent dashboard breakage"""

    async def get_application(self):
        """Create test application"""
        # Mock settings
        settings = Mock(spec=Settings)
        settings.health_port = 8080
        settings.environment = "test"

        # Create health checker
        health_checker = HealthChecker(settings)

        # Create app with routes
        app = web.Application()
        app.router.add_get("/api/health", health_checker.health_check)
        app.router.add_get("/api/ready", health_checker.readiness_check)
        app.router.add_get("/api/metrics", health_checker.metrics)
        app.router.add_get("/api/prometheus", health_checker.prometheus_metrics)
        app.router.add_get("/api/services/health", health_checker.services_health)
        app.router.add_post("/api/users/import", health_checker.handle_user_import)
        app.router.add_post(
            "/api/ingest/completed", health_checker.handle_ingest_completed
        )
        app.router.add_get("/api/metrics/usage", health_checker.get_usage_metrics)
        app.router.add_get(
            "/api/metrics/performance", health_checker.get_performance_metrics
        )

        return app

    async def test_health_endpoint_contract(self):
        """Test /api/health returns expected JSON structure"""
        resp = await self.client.request("GET", "/api/health")
        assert resp.status == 200
        assert resp.content_type == "application/json"

        data = await resp.json()

        # Verify required fields exist (contract)
        required_fields = ["status", "timestamp", "uptime_seconds", "version"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Verify data types (contract)
        assert isinstance(data["status"], str)
        assert isinstance(data["timestamp"], str)
        assert isinstance(data["uptime_seconds"], int | float)
        assert isinstance(data["version"], str)

        # Verify expected values
        assert data["status"] in ["healthy", "unhealthy"]

    async def test_metrics_endpoint_contract(self):
        """Test /api/metrics returns expected JSON structure for dashboard"""
        resp = await self.client.request("GET", "/api/metrics")
        assert resp.status == 200
        assert resp.content_type == "application/json"

        data = await resp.json()

        # Verify metrics structure that dashboard actually receives
        required_fields = ["uptime_seconds", "start_time", "current_time", "services"]
        for field in required_fields:
            assert field in data, f"Missing metrics field: {field}"

        # Verify services structure (what dashboard actually gets)
        services = data["services"]
        assert isinstance(services, dict)

        # Common service fields that dashboard expects
        for _service_name, service_info in services.items():
            if isinstance(service_info, dict):
                # Should have at least enabled or available status
                assert "enabled" in service_info or "available" in service_info

    async def test_services_health_contract(self):
        """Test /api/services/health returns expected structure"""
        with patch("bot.health.get_metrics_service") as mock_metrics:
            mock_metrics.return_value = Mock()

            resp = await self.client.request("GET", "/api/services/health")
            assert resp.status == 200

            data = await resp.json()

            # Verify services structure dashboard actually receives
            required_fields = [
                "services",
                "status",
                "timestamp",
            ]  # API returns "status" not "overall_status"
            for field in required_fields:
                assert field in data, f"Missing field: {field}"

            # Verify services is a dict with service names
            assert isinstance(data["services"], dict)
            assert data["status"] in ["healthy", "degraded", "unhealthy"]

    async def test_usage_metrics_contract(self):
        """Test /api/metrics/usage returns expected structure for dashboard charts"""
        with patch("bot.health.get_metrics_service") as mock_metrics:
            mock_service = Mock()
            mock_service.get_usage_metrics.return_value = {
                "requests_per_minute": 45.2,
                "active_users": 12,
                "total_queries_today": 1500,
                "avg_response_time_ms": 850,
                "error_rate_percent": 2.1,
            }
            mock_metrics.return_value = mock_service

            resp = await self.client.request("GET", "/api/metrics/usage")
            assert resp.status == 200

            data = await resp.json()

            # Verify dashboard chart data structure (actual API response format)
            expected_metrics = [
                "time_range_hours",
                "total_messages",
                "active_users",
                "response_time_avg",
                "success_rate",
            ]

            for metric in expected_metrics:
                assert metric in data, f"Missing usage metric: {metric}"
                assert isinstance(data[metric], int | float), (
                    f"Invalid type for {metric}"
                )

    async def test_user_import_endpoint_contract(self):
        """Test /api/users/import POST endpoint contract"""
        test_payload = {
            "users": [
                {"id": "U123", "name": "Test User", "email": "test@example.com"},
                {"id": "U456", "name": "Another User", "email": "another@example.com"},
            ]
        }

        resp = await self.client.request(
            "POST",
            "/api/users/import",
            json=test_payload,
            headers={"Content-Type": "application/json"},
        )

        # Should accept the request format
        assert resp.status in [200, 201, 202]  # Various success codes acceptable

        data = await resp.json()

        # Verify response contract
        expected_fields = ["status", "processed_count"]
        for field in expected_fields:
            assert field in data, f"Missing response field: {field}"

    async def test_ingest_completed_webhook_contract(self):
        """Test /api/ingest/completed webhook endpoint contract"""
        test_payload = {
            "job_id": "ingest-123",
            "status": "completed",
            "documents_processed": 45,
            "errors": 2,
            "completion_time": "2024-01-15T10:30:00Z",
        }

        resp = await self.client.request(
            "POST",
            "/api/ingest/completed",
            json=test_payload,
            headers={"Content-Type": "application/json"},
        )

        # Should handle webhook format
        assert resp.status in [200, 202]

        data = await resp.json()
        assert "received" in data or "status" in data
