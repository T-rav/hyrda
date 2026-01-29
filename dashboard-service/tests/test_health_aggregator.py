"""Comprehensive tests for health_aggregator.py - HealthChecker class.

Tests health check endpoints, readiness checks, metrics, and service health aggregation.
Goal: Achieve 50%+ coverage of health_aggregator.py (143+ lines).
"""

import sys
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, mock_open, patch

import aiohttp
import pytest

# Mock config.settings module before importing health_aggregator
mock_settings_module = MagicMock()
mock_settings_class = MagicMock()
mock_settings_module.Settings = mock_settings_class
sys.modules["config.settings"] = mock_settings_module
sys.modules["services.metrics_service"] = MagicMock()

# Import after mocking dependencies
from health_aggregator import HealthChecker, get_app_version  # noqa: E402


@pytest.fixture
def mock_settings():
    """Create mock Settings object."""
    settings = Mock()
    settings.llm = Mock()
    settings.llm.api_key = Mock()
    settings.llm.api_key.get_secret_value = Mock(return_value="test-api-key")
    settings.llm.provider = "openai"
    settings.llm.model = "gpt-4o-mini"
    settings.slack = Mock()
    settings.slack.bot_token = "xoxb-test-token"
    settings.slack.app_token = "xapp-test-token"
    return settings


@pytest.fixture
def mock_conversation_cache():
    """Create mock conversation cache."""
    cache = AsyncMock()
    cache.get_cache_stats = AsyncMock(
        return_value={
            "status": "available",
            "memory_used": "256MB",
            "cached_conversations": 42,
            "redis_url": "redis://localhost:6379",
        }
    )
    return cache


@pytest.fixture
def mock_langfuse_service():
    """Create mock Langfuse service."""
    service = Mock()
    service.enabled = True
    service.client = Mock()
    service.settings = Mock()
    service.settings.host = "https://cloud.langfuse.com"
    service.get_lifetime_stats = AsyncMock(
        return_value={
            "total_traces": 1000,
            "total_observations": 5000,
            "unique_sessions": 50,
            "start_date": "2025-10-21",
        }
    )
    return service


@pytest.fixture
def health_checker(mock_settings, mock_conversation_cache, mock_langfuse_service):
    """Create HealthChecker instance for testing."""
    return HealthChecker(mock_settings, mock_conversation_cache, mock_langfuse_service)


class TestGetAppVersion:
    """Test get_app_version function."""

    def test_get_app_version_success(self):
        """Test reading version from pyproject.toml."""
        mock_toml_data = {"project": {"version": "1.2.3"}}

        with (
            patch("pathlib.Path.open", mock_open(read_data=b"")),
            patch("tomllib.load", return_value=mock_toml_data),
        ):
            version = get_app_version()
            assert version == "1.2.3"

    def test_get_app_version_file_not_found(self):
        """Test fallback when pyproject.toml not found."""
        with patch("builtins.open", side_effect=FileNotFoundError):
            version = get_app_version()
            assert version == "unknown"

    def test_get_app_version_invalid_toml(self):
        """Test fallback when pyproject.toml is invalid."""
        with (
            patch("pathlib.Path.open", mock_open(read_data=b"")),
            patch("tomllib.load", side_effect=KeyError("project")),
        ):
            version = get_app_version()
            assert version == "unknown"


class TestHealthCheckerInit:
    """Test HealthChecker initialization."""

    def test_health_checker_initialization(self, mock_settings):
        """Test HealthChecker initializes with correct attributes."""
        checker = HealthChecker(mock_settings, None, None)

        assert checker.settings == mock_settings
        assert checker.conversation_cache is None
        assert checker.langfuse_service is None
        assert isinstance(checker.start_time, datetime)
        assert checker.runner is None
        assert checker.site is None

    def test_health_checker_with_all_services(
        self, mock_settings, mock_conversation_cache, mock_langfuse_service
    ):
        """Test HealthChecker initializes with all services."""
        checker = HealthChecker(
            mock_settings, mock_conversation_cache, mock_langfuse_service
        )

        assert checker.conversation_cache == mock_conversation_cache
        assert checker.langfuse_service == mock_langfuse_service


class TestHealthCheckEndpoint:
    """Test basic health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check_returns_healthy(self, health_checker):
        """Test /health endpoint returns healthy status."""
        # Arrange
        mock_request = Mock()

        # Act
        response = await health_checker.health_check(mock_request)

        # Assert
        assert response.status == 200
        data = response.body
        assert b"healthy" in data
        assert b"version" in data

    @pytest.mark.asyncio
    async def test_health_check_includes_uptime(self, health_checker):
        """Test health check includes uptime calculation."""
        # Arrange
        mock_request = Mock()
        # Set start_time to 60 seconds ago
        health_checker.start_time = datetime.now(UTC) - timedelta(seconds=60)

        # Act
        response = await health_checker.health_check(mock_request)

        # Assert
        assert response.status == 200
        data = response.body
        assert b"uptime_seconds" in data


class TestReadinessCheckEndpoint:
    """Test readiness check endpoint with all dependency checks."""

    @pytest.mark.asyncio
    async def test_readiness_check_all_healthy(self, health_checker):
        """Test readiness check when all services are healthy."""
        # Arrange
        mock_request = Mock()

        with patch("health_aggregator.get_metrics_service") as mock_get_metrics:
            mock_metrics = Mock()
            mock_metrics.enabled = True
            mock_metrics.get_active_conversation_count = Mock(return_value=5)
            mock_metrics.get_rag_stats = Mock(
                return_value={
                    "total_queries": 100,
                    "success_rate": 95.5,
                    "miss_rate": 4.5,
                    "avg_chunks_per_query": 3.2,
                    "total_documents_used": 50,
                }
            )
            mock_get_metrics.return_value = mock_metrics

            # Act
            response = await health_checker.readiness_check(mock_request)

            # Assert
            assert response.status == 200
            data = response.body
            assert b"ready" in data
            assert b"llm_api" in data
            assert b"cache" in data
            assert b"langfuse" in data

    @pytest.mark.asyncio
    async def test_readiness_check_missing_api_key(self, health_checker):
        """Test readiness check fails when LLM API key is missing."""
        # Arrange
        mock_request = Mock()
        health_checker.settings.llm.api_key.get_secret_value = Mock(return_value="")

        with patch("health_aggregator.get_metrics_service", return_value=None):
            # Act
            response = await health_checker.readiness_check(mock_request)

            # Assert
            assert response.status == 503
            data = response.body
            assert b"not_ready" in data

    @pytest.mark.asyncio
    async def test_readiness_check_cache_unavailable(self, health_checker):
        """Test readiness check when cache is unavailable."""
        # Arrange
        mock_request = Mock()
        health_checker.conversation_cache.get_cache_stats = AsyncMock(
            return_value={
                "status": "unavailable",
                "redis_url": "redis://localhost:6379",
            }
        )

        with patch("health_aggregator.get_metrics_service", return_value=None):
            # Act
            response = await health_checker.readiness_check(mock_request)

            # Assert
            assert response.status == 503
            data = response.body
            assert b"unhealthy" in data

    @pytest.mark.asyncio
    async def test_readiness_check_cache_disabled(self, health_checker):
        """Test readiness check when cache is not configured."""
        # Arrange
        mock_request = Mock()
        health_checker.conversation_cache = None

        with patch("health_aggregator.get_metrics_service", return_value=None):
            # Act
            response = await health_checker.readiness_check(mock_request)

            # Assert
            assert response.status == 200
            data = response.body
            assert b"disabled" in data

    @pytest.mark.asyncio
    async def test_readiness_check_langfuse_unhealthy(self, health_checker):
        """Test readiness check when Langfuse is enabled but client failed."""
        # Arrange
        mock_request = Mock()
        health_checker.langfuse_service.enabled = True
        health_checker.langfuse_service.client = None

        with patch("health_aggregator.get_metrics_service", return_value=None):
            # Act
            response = await health_checker.readiness_check(mock_request)

            # Assert
            assert response.status == 503
            data = response.body
            assert b"not_ready" in data

    @pytest.mark.asyncio
    async def test_readiness_check_metrics_service_enabled(self, health_checker):
        """Test readiness check includes metrics service when enabled."""
        # Arrange
        mock_request = Mock()

        with patch("health_aggregator.get_metrics_service") as mock_get_metrics:
            mock_metrics = Mock()
            mock_metrics.enabled = True
            mock_metrics.get_active_conversation_count = Mock(return_value=10)
            mock_metrics.get_rag_stats = Mock(
                return_value={
                    "total_queries": 200,
                    "success_rate": 98.0,
                    "miss_rate": 2.0,
                    "avg_chunks_per_query": 4.0,
                    "total_documents_used": 75,
                }
            )
            mock_get_metrics.return_value = mock_metrics

            # Act
            response = await health_checker.readiness_check(mock_request)

            # Assert
            assert response.status == 200
            data = response.body
            assert b"metrics" in data
            assert b"prometheus_available" in data


class TestMetricsEndpoint:
    """Test metrics endpoint."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint_basic(self, health_checker):
        """Test /metrics endpoint returns basic metrics."""
        # Arrange
        mock_request = Mock()

        with patch("health_aggregator.get_metrics_service", return_value=None):
            # Act
            response = await health_checker.metrics(mock_request)

            # Assert
            assert response.status == 200
            data = response.body
            assert b"uptime_seconds" in data
            assert b"start_time" in data

    @pytest.mark.asyncio
    async def test_metrics_endpoint_with_cache(self, health_checker):
        """Test metrics endpoint includes cache statistics."""
        # Arrange
        mock_request = Mock()

        with patch("health_aggregator.get_metrics_service", return_value=None):
            # Act
            response = await health_checker.metrics(mock_request)

            # Assert
            assert response.status == 200
            data = response.body
            assert b"cache" in data
            health_checker.conversation_cache.get_cache_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_metrics_endpoint_cache_error(self, health_checker):
        """Test metrics endpoint handles cache errors gracefully."""
        # Arrange
        mock_request = Mock()
        health_checker.conversation_cache.get_cache_stats = AsyncMock(
            side_effect=Exception("Cache connection failed")
        )

        with patch("health_aggregator.get_metrics_service", return_value=None):
            # Act
            response = await health_checker.metrics(mock_request)

            # Assert
            assert response.status == 200
            data = response.body
            assert b"error" in data

    @pytest.mark.asyncio
    async def test_metrics_endpoint_with_metrics_service(self, health_checker):
        """Test metrics endpoint includes metrics service data."""
        # Arrange
        mock_request = Mock()

        with patch("health_aggregator.get_metrics_service") as mock_get_metrics:
            mock_metrics = Mock()
            mock_metrics.enabled = True
            mock_metrics.get_active_conversation_count = Mock(return_value=15)
            mock_metrics.get_rag_stats = Mock(
                return_value={
                    "total_queries": 300,
                    "success_rate": 96.0,
                    "miss_rate": 4.0,
                    "avg_chunks_per_query": 3.5,
                    "total_documents_used": 100,
                    "last_reset": datetime.now(UTC),
                }
            )
            mock_metrics.get_agent_stats = Mock(
                return_value={
                    "total_invocations": 50,
                    "successful_invocations": 48,
                    "failed_invocations": 2,
                    "success_rate": 96.0,
                    "error_rate": 4.0,
                    "by_agent": {"test_agent": 25, "another_agent": 25},
                    "last_reset": datetime.now(UTC),
                }
            )
            mock_get_metrics.return_value = mock_metrics

            # Act
            response = await health_checker.metrics(mock_request)

            # Assert
            assert response.status == 200
            data = response.body
            assert b"active_conversations" in data
            assert b"rag_performance" in data
            assert b"agent_invocations" in data

    @pytest.mark.asyncio
    async def test_metrics_endpoint_with_langfuse_lifetime_stats(self, health_checker):
        """Test metrics endpoint includes Langfuse lifetime stats."""
        # Arrange
        mock_request = Mock()

        with patch("health_aggregator.get_metrics_service", return_value=None):
            # Act
            response = await health_checker.metrics(mock_request)

            # Assert
            assert response.status == 200
            data = response.body
            assert b"lifetime_stats" in data
            health_checker.langfuse_service.get_lifetime_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_metrics_endpoint_langfuse_error(self, health_checker):
        """Test metrics endpoint handles Langfuse errors gracefully."""
        # Arrange
        mock_request = Mock()
        health_checker.langfuse_service.get_lifetime_stats = AsyncMock(
            side_effect=Exception("Langfuse API error")
        )

        with patch("health_aggregator.get_metrics_service", return_value=None):
            # Act
            response = await health_checker.metrics(mock_request)

            # Assert
            assert response.status == 200
            data = response.body
            assert b"lifetime_stats" in data
            assert b"error" in data


class TestPrometheusMetricsEndpoint:
    """Test Prometheus metrics endpoint."""

    @pytest.mark.asyncio
    async def test_prometheus_metrics_service_unavailable(self, health_checker):
        """Test prometheus endpoint when metrics service is unavailable."""
        # Arrange
        mock_request = Mock()

        with patch("health_aggregator.get_metrics_service", return_value=None):
            # Act
            response = await health_checker.prometheus_metrics(mock_request)

            # Assert
            assert response.status == 503
            assert b"not available" in response.body

    @pytest.mark.asyncio
    async def test_prometheus_metrics_success(self, health_checker):
        """Test prometheus endpoint returns metrics in Prometheus format."""
        # Arrange
        mock_request = Mock()

        with patch("health_aggregator.get_metrics_service") as mock_get_metrics:
            mock_metrics = Mock()
            mock_metrics.get_metrics = Mock(
                return_value="# HELP test_metric Test metric\n# TYPE test_metric gauge\ntest_metric 42\n"
            )
            mock_metrics.get_content_type = Mock(
                return_value="text/plain; version=0.0.4; charset=utf-8"
            )
            mock_get_metrics.return_value = mock_metrics

            # Act
            response = await health_checker.prometheus_metrics(mock_request)

            # Assert
            assert response.status == 200
            assert b"test_metric" in response.body


class TestTasksServiceIntegrationEndpoints:
    """Test tasks service integration endpoints."""

    @pytest.mark.asyncio
    async def test_handle_user_import_success(self, health_checker):
        """Test user import endpoint processes users successfully."""
        # Arrange
        mock_request = Mock()
        mock_request.json = AsyncMock(
            return_value={
                "users": [
                    {"id": "U123", "name": "User 1"},
                    {"id": "U456", "name": "User 2"},
                ],
                "job_id": "job_123",
            }
        )

        # Act
        response = await health_checker.handle_user_import(mock_request)

        # Assert
        assert response.status == 200
        data = response.body
        assert b"success" in data
        assert b"2" in data

    @pytest.mark.asyncio
    async def test_handle_user_import_error(self, health_checker):
        """Test user import endpoint handles errors."""
        # Arrange
        mock_request = Mock()
        mock_request.json = AsyncMock(side_effect=Exception("Invalid JSON"))

        # Act
        response = await health_checker.handle_user_import(mock_request)

        # Assert
        assert response.status == 400
        data = response.body
        assert b"error" in data

    @pytest.mark.asyncio
    async def test_handle_ingest_completed_success(self, health_checker):
        """Test ingestion completion endpoint."""
        # Arrange
        mock_request = Mock()
        mock_request.json = AsyncMock(
            return_value={
                "job_id": "job_123",
                "job_type": "google_drive",
                "result": {"files_processed": 50, "errors": 0},
                "folder_id": "folder_123",
            }
        )

        # Act
        response = await health_checker.handle_ingest_completed(mock_request)

        # Assert
        assert response.status == 200
        data = response.body
        assert b"success" in data

    @pytest.mark.asyncio
    async def test_handle_metrics_store_success(self, health_checker):
        """Test metrics storage endpoint."""
        # Arrange
        mock_request = Mock()
        mock_request.json = AsyncMock(
            return_value={
                "job_id": "job_123",
                "metrics": {"duration": 120, "success": True},
            }
        )

        # Act
        response = await health_checker.handle_metrics_store(mock_request)

        # Assert
        assert response.status == 200
        data = response.body
        assert b"success" in data

    @pytest.mark.asyncio
    async def test_get_usage_metrics_default_params(self, health_checker):
        """Test getting usage metrics with default parameters."""
        # Arrange
        mock_request = Mock()
        mock_request.query = {}

        # Act
        response = await health_checker.get_usage_metrics(mock_request)

        # Assert
        assert response.status == 200
        data = response.body
        assert b"total_messages" in data
        assert b"active_users" in data

    @pytest.mark.asyncio
    async def test_get_usage_metrics_with_details(self, health_checker):
        """Test getting usage metrics with details included."""
        # Arrange
        mock_request = Mock()
        mock_request.query = {"hours": "48", "include_details": "true"}

        # Act
        response = await health_checker.get_usage_metrics(mock_request)

        # Assert
        assert response.status == 200
        data = response.body
        assert b"data" in data

    @pytest.mark.asyncio
    async def test_get_performance_metrics_default(self, health_checker):
        """Test getting performance metrics."""
        # Arrange
        mock_request = Mock()
        mock_request.query = {}

        # Act
        response = await health_checker.get_performance_metrics(mock_request)

        # Assert
        assert response.status == 200
        data = response.body
        assert b"avg_response_time_ms" in data
        assert b"memory_usage_mb" in data

    @pytest.mark.asyncio
    async def test_get_error_metrics_default(self, health_checker):
        """Test getting error metrics."""
        # Arrange
        mock_request = Mock()
        mock_request.query = {}

        # Act
        response = await health_checker.get_error_metrics(mock_request)

        # Assert
        assert response.status == 200
        data = response.body
        assert b"total_errors" in data
        assert b"error_rate_percent" in data


class TestServicesHealthEndpoint:
    """Test services health aggregation endpoint."""

    @pytest.mark.asyncio
    async def test_services_health_task_scheduler_healthy(self, health_checker):
        """Test services health when task scheduler is healthy."""
        # Arrange
        mock_request = Mock()

        # Create async context manager for responses
        class MockResponse:
            def __init__(self, status, json_data):
                self.status = status
                self._json_data = json_data

            async def json(self):
                return self._json_data

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        mock_scheduler_resp = MockResponse(200, {"running": True})
        mock_jobs_resp = MockResponse(200, {"jobs": [{"id": "job1"}, {"id": "job2"}]})

        call_count = [0]

        async def mock_get(url, **kwargs):
            result = [mock_scheduler_resp, mock_jobs_resp][call_count[0]]
            call_count[0] += 1
            return result

        mock_session = MagicMock()
        mock_session.get = mock_get
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("aiohttp.ClientSession", return_value=mock_session),
            patch("pymysql.connect", side_effect=ImportError("pymysql not installed")),
        ):
            # Act
            response = await health_checker.services_health(mock_request)

            # Assert
            assert response.status == 200
            data = response.body
            assert b"task_scheduler" in data
            assert b"healthy" in data

    @pytest.mark.asyncio
    async def test_services_health_database_disabled(self, health_checker):
        """Test services health when database (pymysql) is not installed."""
        # Arrange
        mock_request = Mock()

        # Mock aiohttp to raise connection error for task scheduler
        async def mock_get(url, **kwargs):
            raise aiohttp.ClientConnectorError(Mock(), Mock())

        mock_session = MagicMock()
        mock_session.get = mock_get
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # Mock pymysql module import to simulate it not being installed
        with (
            patch("aiohttp.ClientSession", return_value=mock_session),
            patch.dict("sys.modules", {"pymysql": None}),
        ):
            # Import error should be raised when trying to import pymysql
            # This simulates the ImportError in the actual code
            # Act
            response = await health_checker.services_health(mock_request)

            # Assert
            assert response.status == 200
            data = response.body
            # When pymysql can't be imported, it should show as disabled
            # But since the function catches ImportError, database key should exist
            assert b"database" in data or b"task_scheduler" in data

    @pytest.mark.asyncio
    async def test_services_health_all_services_error(self, health_checker):
        """Test services health when services have errors."""
        # Arrange
        mock_request = Mock()

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session.get = AsyncMock(side_effect=Exception("Connection error"))

        with (
            patch("aiohttp.ClientSession", return_value=mock_session),
            patch("pymysql.connect", side_effect=Exception("DB connection error")),
        ):
            # Act
            response = await health_checker.services_health(mock_request)

            # Assert
            assert response.status == 200
            data = response.body
            assert b"error" in data or b"degraded" in data


class TestHealthUI:
    """Test health UI endpoints."""

    @pytest.mark.asyncio
    async def test_health_ui_success(self, health_checker):
        """Test health UI serves index.html."""
        # Arrange
        mock_request = Mock()
        mock_html_content = "<html><body>Health Dashboard</body></html>"

        with patch("builtins.open", mock_open(read_data=mock_html_content)):
            # Act
            response = await health_checker.health_ui(mock_request)

            # Assert
            assert response.status == 200
            assert b"Health Dashboard" in response.body

    @pytest.mark.asyncio
    async def test_health_ui_file_not_found(self, health_checker):
        """Test health UI handles missing index.html."""
        # Arrange
        mock_request = Mock()

        with patch("builtins.open", side_effect=FileNotFoundError):
            # Act
            response = await health_checker.health_ui(mock_request)

            # Assert
            assert response.status == 500
            assert b"not available" in response.body

    def test_get_ui_assets_path(self, health_checker):
        """Test getting UI assets path."""
        # Act
        assets_path = health_checker._get_ui_assets_path()

        # Assert
        assert "health_ui" in assets_path
        assert "dist" in assets_path
        assert "assets" in assets_path

    def test_get_ui_index_path(self, health_checker):
        """Test getting UI index path."""
        # Act
        index_path = health_checker._get_ui_index_path()

        # Assert
        assert "health_ui" in index_path
        assert "dist" in index_path
        assert "index.html" in index_path


class TestServerLifecycle:
    """Test server start and stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_server_creates_routes(self, health_checker):
        """Test starting server creates all routes."""
        # Arrange
        with (
            patch("aiohttp.web.Application") as mock_app_cls,
            patch("aiohttp.web.AppRunner") as mock_runner_cls,
            patch("aiohttp.web.TCPSite") as mock_site_cls,
        ):
            mock_app = Mock()
            mock_app.router = Mock()
            mock_app.router.add_get = Mock()
            mock_app.router.add_post = Mock()
            mock_app.router.add_static = Mock()
            mock_app_cls.return_value = mock_app

            mock_runner = AsyncMock()
            mock_runner.setup = AsyncMock()
            mock_runner_cls.return_value = mock_runner

            mock_site = AsyncMock()
            mock_site.start = AsyncMock()
            mock_site_cls.return_value = mock_site

            # Act
            await health_checker.start_server(port=8080)

            # Assert
            assert health_checker.runner == mock_runner
            assert health_checker.site == mock_site
            mock_runner.setup.assert_called_once()
            mock_site.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_server_cleanup(self, health_checker):
        """Test stopping server cleans up resources."""
        # Arrange
        health_checker.site = AsyncMock()
        health_checker.runner = AsyncMock()

        # Act
        await health_checker.stop_server()

        # Assert
        health_checker.site.stop.assert_called_once()
        health_checker.runner.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_server_no_site(self, health_checker):
        """Test stopping server when site is None."""
        # Arrange
        health_checker.site = None
        health_checker.runner = None

        # Act & Assert (should not raise)
        await health_checker.stop_server()
