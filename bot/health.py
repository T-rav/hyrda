import logging
import os
import tomllib
from datetime import UTC, datetime
from pathlib import Path

from aiohttp import web
from aiohttp.web_runner import AppRunner, TCPSite

from config.settings import Settings
from services.metrics_service import get_metrics_service

logger = logging.getLogger(__name__)

# Constants
HTTP_OK = 200
HEALTH_CHECK_TIMEOUT = 5


def get_app_version() -> str:
    """Get application version from pyproject.toml"""
    try:
        pyproject_path = Path(__file__).parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            pyproject_data = tomllib.load(f)
        return pyproject_data["project"]["version"]
    except Exception as e:
        logger.warning(f"Failed to read version from pyproject.toml: {e}")
        return "unknown"


class HealthChecker:
    """Health check service for monitoring bot status"""

    def __init__(
        self, settings: Settings, conversation_cache=None, langfuse_service=None
    ):
        self.settings = settings
        self.conversation_cache = conversation_cache
        self.langfuse_service = langfuse_service
        self.start_time = datetime.now(UTC)
        self.app = None
        self.runner: AppRunner | None = None
        self.site: TCPSite | None = None

    async def start_server(self, port: int = 8080):
        """Start health check HTTP server"""
        app = web.Application()

        # API routes with /api prefix
        app.router.add_get("/api/health", self.health_check)
        app.router.add_get("/api/ready", self.readiness_check)
        app.router.add_get("/api/metrics", self.metrics)
        app.router.add_get("/api/prometheus", self.prometheus_metrics)

        # Tasks service integration endpoints
        app.router.add_post("/api/users/import", self.handle_user_import)
        app.router.add_post("/api/ingest/completed", self.handle_ingest_completed)
        app.router.add_post("/api/metrics/store", self.handle_metrics_store)
        app.router.add_get("/api/metrics/usage", self.get_usage_metrics)
        app.router.add_get("/api/metrics/performance", self.get_performance_metrics)
        app.router.add_get("/api/metrics/errors", self.get_error_metrics)

        # Legacy routes (without /api prefix for backward compatibility)
        app.router.add_get("/health", self.health_check)
        app.router.add_get("/ready", self.readiness_check)
        app.router.add_get("/metrics", self.metrics)
        app.router.add_get("/prometheus", self.prometheus_metrics)

        # Health UI routes
        app.router.add_get("/", self.health_ui)
        app.router.add_get("/ui", self.health_ui)
        app.router.add_static("/assets", self._get_ui_assets_path())

        self.runner = web.AppRunner(app)
        await self.runner.setup()

        # Bind to all interfaces for containerized deployment
        self.site = web.TCPSite(self.runner, "0.0.0.0", port)  # nosec B104
        await self.site.start()

        logger.info(f"Health check server started on port {port}")
        logger.info(f"Health UI available at: http://localhost:{port}/ui")

    async def stop_server(self):
        """Stop health check HTTP server"""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()

    async def health_check(self, request):
        """Basic health check - is the service running?"""
        uptime = datetime.now(UTC) - self.start_time

        return web.json_response(
            {
                "status": "healthy",
                "uptime_seconds": int(uptime.total_seconds()),
                "timestamp": datetime.now(UTC).isoformat(),
                "version": get_app_version(),
            }
        )

    async def readiness_check(self, request):
        """Readiness check - can the service handle requests?"""
        checks = {}
        all_healthy = True

        # Check LLM API connectivity
        try:
            # Skip actual HTTP check for now, just validate settings
            checks["llm_api"] = {
                "status": "healthy"
                if self.settings.llm.api_key.get_secret_value()
                else "unhealthy",
                "provider": self.settings.llm.provider,
                "model": self.settings.llm.model,
            }
            if not self.settings.llm.api_key.get_secret_value():
                all_healthy = False
        except Exception as e:
            checks["llm_api"] = {"status": "unhealthy", "error": str(e)}
            all_healthy = False

        # Check if we have required environment variables
        required_vars = ["SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "LLM_API_KEY"]
        missing_vars = []

        for var in required_vars:
            if (
                var == "SLACK_BOT_TOKEN"
                and not self.settings.slack.bot_token
                or var == "SLACK_APP_TOKEN"
                and not self.settings.slack.app_token
                or (
                    var == "LLM_API_KEY"
                    and not self.settings.llm.api_key.get_secret_value()
                )
            ):
                missing_vars.append(var)

        checks["configuration"] = {
            "status": "healthy" if not missing_vars else "unhealthy",
            "missing_variables": ", ".join(missing_vars) if missing_vars else "none",
        }

        if missing_vars:
            all_healthy = False

        # Check cache connectivity
        if self.conversation_cache:
            try:
                cache_stats = await self.conversation_cache.get_cache_stats()
                if cache_stats.get("status") == "available":
                    checks["cache"] = {
                        "status": "healthy",
                        "memory_used": cache_stats.get("memory_used", "unknown"),
                        "cached_conversations": cache_stats.get(
                            "cached_conversations", 0
                        ),
                        "redis_url": cache_stats.get("redis_url", "unknown"),
                    }
                elif cache_stats.get("status") == "unavailable":
                    checks["cache"] = {
                        "status": "unhealthy",
                        "message": f"Configured but Redis unavailable at {cache_stats.get('redis_url', 'unknown')}",
                        "error": "Redis connection failed",
                    }
                    all_healthy = False
                else:
                    checks["cache"] = {
                        "status": "unhealthy",
                        "error": cache_stats.get("error", "Unknown cache error"),
                    }
                    all_healthy = False
            except Exception as e:
                checks["cache"] = {"status": "unhealthy", "error": str(e)}
                all_healthy = False
        else:
            checks["cache"] = {
                "status": "disabled",
                "message": "Cache service not configured - using Slack API only",
            }

        # Check Langfuse connectivity
        if self.langfuse_service:
            if self.langfuse_service.enabled and self.langfuse_service.client:
                checks["langfuse"] = {
                    "status": "healthy",
                    "enabled": True,
                    "client_initialized": True,
                    "configured": True,
                    "host": self.langfuse_service.settings.host,
                }
            elif self.langfuse_service.enabled:
                checks["langfuse"] = {
                    "status": "unhealthy",
                    "enabled": False,  # Service disabled due to initialization failure
                    "configured": True,
                    "message": "Enabled but client failed to initialize - check credentials and host",
                    "host": self.langfuse_service.settings.host,
                }
                all_healthy = False
            else:
                checks["langfuse"] = {
                    "status": "disabled",
                    "enabled": False,
                    "configured": True,
                    "message": "Configured but disabled (check LANGFUSE_ENABLED or credentials)",
                    "host": self.langfuse_service.settings.host,
                }
        else:
            # Check if langfuse package is available
            try:
                import langfuse  # noqa: F401

                langfuse_available = True
                message = "Langfuse package available but service not initialized"
            except ImportError:
                langfuse_available = False
                message = "Langfuse package not installed (pip install langfuse)"

            checks["langfuse"] = {
                "status": "disabled",
                "enabled": False,
                "configured": False,
                "package_available": langfuse_available,
                "message": message,
            }

        # Check metrics service
        metrics_service = get_metrics_service()
        if metrics_service and metrics_service.enabled:
            active_conversations = metrics_service.get_active_conversation_count()
            checks["metrics"] = {
                "status": "healthy",
                "enabled": True,
                "prometheus_available": True,
                "active_conversations": active_conversations,
                "endpoints": {
                    "metrics_json": "/api/metrics",
                    "prometheus": "/api/prometheus",
                },
                "description": "Prometheus metrics collection active",
            }
        elif metrics_service and not metrics_service.enabled:
            checks["metrics"] = {
                "status": "disabled",
                "enabled": False,
                "prometheus_available": True,
                "message": "Metrics service available but disabled",
            }
        else:
            # Check if prometheus client is actually available
            try:
                import prometheus_client  # noqa: F401

                prometheus_available = True
                message = "Metrics service not initialized - check app startup"
            except ImportError:
                prometheus_available = False
                message = "Prometheus client not available - install prometheus-client package"

            checks["metrics"] = {
                "status": "disabled",
                "enabled": False,
                "prometheus_available": prometheus_available,
                "message": message,
            }

        response_data = {
            "status": "ready" if all_healthy else "not_ready",
            "checks": checks,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        status_code = 200 if all_healthy else 503
        return web.json_response(response_data, status=status_code)

    async def metrics(self, request):
        """Basic metrics endpoint (JSON format)"""
        uptime = datetime.now(UTC) - self.start_time

        metrics = {
            "uptime_seconds": int(uptime.total_seconds()),
            "start_time": self.start_time.isoformat(),
            "current_time": datetime.now(UTC).isoformat(),
        }

        # Add cache statistics if available
        if self.conversation_cache:
            try:
                cache_stats = await self.conversation_cache.get_cache_stats()
                metrics["cache"] = cache_stats
            except Exception as e:
                metrics["cache"] = {"status": "error", "error": str(e)}

        # Add metrics service data
        metrics_service = get_metrics_service()
        if metrics_service and metrics_service.enabled:
            # Get active conversation count from metrics service
            active_count = metrics_service.get_active_conversation_count()

            # If we have cache stats, compare with cached conversations
            if (
                self.conversation_cache
                and "cache" in metrics
                and metrics["cache"].get("cached_conversations") is not None
            ):
                cache_count = int(metrics["cache"]["cached_conversations"])
                # Use the higher of the two counts as active conversations might not all be cached
                final_active_count = max(active_count, cache_count)
            else:
                final_active_count = active_count

            metrics["active_conversations"] = {
                "total": final_active_count,
                "tracked_by_metrics": active_count,
                "cached_conversations": metrics.get("cache", {}).get(
                    "cached_conversations", 0
                )
                if self.conversation_cache
                else 0,
                "description": "Active conversations being tracked",
            }

        # Add service status
        metrics["services"] = {
            "langfuse": {
                "enabled": self.langfuse_service.enabled
                if self.langfuse_service
                else False,
                "available": bool(self.langfuse_service),
            },
            "metrics": {
                "enabled": bool(
                    get_metrics_service() and get_metrics_service().enabled
                ),
                "available": bool(get_metrics_service()),
            },
            "cache": {
                "available": bool(self.conversation_cache),
            },
        }

        return web.json_response(metrics)

    async def prometheus_metrics(self, request):
        """Prometheus metrics endpoint"""
        metrics_service = get_metrics_service()
        if not metrics_service:
            return web.Response(
                text="# Metrics service not available\n",
                content_type="text/plain",
                status=503,
            )

        metrics_data = metrics_service.get_metrics()
        content_type = metrics_service.get_content_type()

        # aiohttp doesn't want charset in content_type, so strip it
        if ";" in content_type:
            content_type = content_type.split(";")[0].strip()

        return web.Response(
            text=metrics_data, content_type=content_type, charset="utf-8"
        )

    def _get_ui_assets_path(self) -> str:
        """Get the path to the built UI assets"""
        current_dir = Path(__file__).parent
        ui_dist_path = current_dir / "health_ui" / "dist" / "assets"
        return str(ui_dist_path)

    def _get_ui_index_path(self) -> str:
        """Get the path to the UI index.html file"""
        current_dir = Path(__file__).parent
        ui_index_path = current_dir / "health_ui" / "dist" / "index.html"
        return str(ui_index_path)

    async def health_ui(self, request):
        """Serve the health dashboard UI"""
        try:
            index_path = self._get_ui_index_path()

            # Check if built UI exists
            if not os.path.exists(index_path):
                # Serve a simple fallback HTML page
                return web.Response(
                    text=self._get_fallback_ui(), content_type="text/html"
                )

            # Serve the built React app
            with open(index_path, encoding="utf-8") as f:
                content = f.read()

            return web.Response(text=content, content_type="text/html")

        except Exception as e:
            logger.error(f"Error serving health UI: {e}")
            return web.Response(text=self._get_fallback_ui(), content_type="text/html")

    def _get_fallback_ui(self) -> str:
        """Fallback HTML page when React app is not built"""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Health Dashboard - InsightMesh</title>

    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">

    <!-- Font Awesome -->
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">

    <!-- Lucide Icons -->
    <script src="https://unpkg.com/lucide@latest/dist/umd/lucide.js"></script>

    <style>
        /* Design System - Color Tokens */
        :root {
            --purple-400: #a78bfa;
            --purple-500: #9f7aea;
            --purple-600: #8b5cf6;
            --purple-700: #7c3aed;
            --emerald-500: #10b981;
            --emerald-600: #059669;
            --emerald-700: #047857;
            --slate-600: #64748b;
            --blue-500: #3b82f6;
            --amber-400: #fbbf24;
            --amber-500: #f59e0b;
            --red-500: #ef4444;

            --color-primary: var(--purple-500);
            --color-primary-hover: var(--purple-600);
            --color-success: var(--emerald-500);
            --color-info: var(--blue-500);
            --color-warning: var(--amber-400);
            --color-danger: var(--red-500);
        }

        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }

        .glass-card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 16px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            padding: 1.5rem;
        }

        .stat-card {
            transition: all 0.3s ease;
            border-left: 4px solid transparent;
        }

        .stat-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15);
        }

        .stat-card-primary { border-left-color: var(--color-primary); }
        .stat-card-success { border-left-color: var(--color-success); }
        .stat-card-info { border-left-color: var(--color-info); }
        .stat-card-warning { border-left-color: var(--color-warning); }

        .stat-number {
            font-size: 2rem;
            font-weight: 700;
            margin: 0;
            color: #1a202c;
        }

        .stat-label {
            font-size: 0.875rem;
            color: #64748b;
            margin: 0;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .stat-icon {
            opacity: 0.7;
            color: var(--color-primary);
        }

        .icon { width: 20px; height: 20px; }
        .icon-sm { width: 16px; height: 16px; }
        .icon-lg { width: 32px; height: 32px; }

        .text-primary { color: var(--color-primary) !important; }
        .text-success { color: var(--color-success) !important; }
        .text-danger { color: var(--color-danger) !important; }

        .btn-outline-primary {
            color: var(--color-primary);
            border-color: var(--color-primary);
        }
        .btn-outline-primary:hover {
            background-color: var(--color-primary);
            border-color: var(--color-primary);
        }
    </style>
</head>
<body>
    <div class="container-fluid py-4">
        <!-- Header -->
        <div class="glass-card mb-4">
            <div class="d-flex justify-content-between align-items-center">
                <h2 class="mb-0">
                    <i data-lucide="activity" class="icon text-primary me-2"></i>Health Dashboard
                </h2>
                <div>
                    <button id="auto-refresh-btn" class="btn btn-outline-primary me-2" onclick="toggleAutoRefresh()">
                        <i data-lucide="play" class="icon-sm me-1"></i>Auto-refresh
                    </button>
                    <button class="btn btn-outline-secondary" onclick="refreshData()">
                        <i data-lucide="refresh-cw" class="icon-sm me-1"></i>Refresh
                    </button>
                </div>
            </div>
        </div>

        <!-- Statistics Cards -->
        <div class="row mb-4">
            <div class="col-md-3 mb-3">
                <div class="glass-card stat-card stat-card-primary">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <h3 class="stat-number" id="system-status">-</h3>
                            <p class="stat-label">System Status</p>
                        </div>
                        <div class="stat-icon">
                            <i data-lucide="server" class="icon-lg"></i>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-3 mb-3">
                <div class="glass-card stat-card stat-card-success">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <h3 class="stat-number" id="llm-status">-</h3>
                            <p class="stat-label">LLM Service</p>
                        </div>
                        <div class="stat-icon">
                            <i data-lucide="brain" class="icon-lg"></i>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-3 mb-3">
                <div class="glass-card stat-card stat-card-info">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <h3 class="stat-number" id="cache-status">-</h3>
                            <p class="stat-label">Cache Service</p>
                        </div>
                        <div class="stat-icon">
                            <i data-lucide="database" class="icon-lg"></i>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-3 mb-3">
                <div class="glass-card stat-card stat-card-warning">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <h3 class="stat-number" id="metrics-status">-</h3>
                            <p class="stat-label">Metrics</p>
                        </div>
                        <div class="stat-icon">
                            <i data-lucide="bar-chart-3" class="icon-lg"></i>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- API Endpoints -->
        <div class="glass-card">
            <h3 class="mb-3">
                <i data-lucide="link" class="icon text-primary me-2"></i>API Endpoints
            </h3>
            <div class="d-flex flex-wrap gap-2">
                <a href="/api/health" class="btn btn-outline-primary btn-sm">
                    <i data-lucide="heart" class="icon-sm me-1"></i>Health Check
                </a>
                <a href="/api/ready" class="btn btn-outline-primary btn-sm">
                    <i data-lucide="check-circle" class="icon-sm me-1"></i>Readiness Check
                </a>
                <a href="/api/metrics" class="btn btn-outline-primary btn-sm">
                    <i data-lucide="bar-chart" class="icon-sm me-1"></i>Metrics (JSON)
                </a>
                <a href="/api/prometheus" class="btn btn-outline-primary btn-sm">
                    <i data-lucide="trending-up" class="icon-sm me-1"></i>Prometheus Metrics
                </a>
            </div>
        </div>
    </div>

    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>

    <script>
        let autoRefreshInterval = null;
        let isAutoRefreshing = false;

        async function updateStatus() {
            try {
                // Fetch health data
                const [health, ready] = await Promise.all([
                    fetch('/api/health').then(r => r.json()),
                    fetch('/api/ready').then(r => r.json())
                ]);

                // Update system status
                const systemEl = document.getElementById('system-status');
                systemEl.innerHTML = health.status === 'healthy' ?
                    '<span class="text-success">✅ Healthy</span>' :
                    '<span class="text-danger">❌ Unhealthy</span>';

                // Update LLM status
                const llmEl = document.getElementById('llm-status');
                const llmStatus = ready.checks?.llm_api?.status;
                llmEl.innerHTML = llmStatus === 'healthy' ?
                    '<span class="text-success">✅ Connected</span>' :
                    '<span class="text-danger">❌ Error</span>';

                // Update cache status
                const cacheEl = document.getElementById('cache-status');
                const cacheStatus = ready.checks?.cache?.status;
                if (cacheStatus === 'healthy') {
                    cacheEl.innerHTML = '<span class="text-success">✅ Available</span>';
                } else if (cacheStatus === 'disabled') {
                    cacheEl.innerHTML = '<span class="text-success">⚪ Disabled</span>';
                } else {
                    cacheEl.innerHTML = '<span class="text-danger">❌ Error</span>';
                }

                // Update metrics status
                const metricsEl = document.getElementById('metrics-status');
                const metricsStatus = ready.checks?.metrics?.status;
                if (metricsStatus === 'healthy') {
                    metricsEl.innerHTML = '<span class="text-success">✅ Enabled</span>';
                } else if (metricsStatus === 'disabled') {
                    metricsEl.innerHTML = '<span class="text-success">⚪ Disabled</span>';
                } else {
                    metricsEl.innerHTML = '<span class="text-danger">❌ Error</span>';
                }

            } catch (error) {
                console.error('Error updating status:', error);
                document.querySelectorAll('[id$="-status"]').forEach(el => {
                    el.innerHTML = '<span class="text-danger">❌ Error</span>';
                });
            }
        }

        function toggleAutoRefresh() {
            const btn = document.getElementById('auto-refresh-btn');
            const icon = btn.querySelector('i');

            if (isAutoRefreshing) {
                clearInterval(autoRefreshInterval);
                isAutoRefreshing = false;
                icon.setAttribute('data-lucide', 'play');
                btn.innerHTML = '<i data-lucide="play" class="icon-sm me-1"></i>Auto-refresh';
            } else {
                autoRefreshInterval = setInterval(updateStatus, 10000);
                isAutoRefreshing = true;
                icon.setAttribute('data-lucide', 'pause');
                btn.innerHTML = '<i data-lucide="pause" class="icon-sm me-1"></i>Auto-refresh';
            }
            lucide.createIcons();
        }

        function refreshData() {
            updateStatus();
        }

        // Initialize
        updateStatus();
        lucide.createIcons();
    </script>
</body>
</html>
        """.strip()

    # Tasks Service Integration Endpoints

    async def handle_user_import(self, request):
        """Handle user import from tasks service."""
        try:
            data = await request.json()
            users = data.get("users", [])
            job_id = data.get("job_id", "unknown")

            logger.info(f"Received user import from job {job_id}: {len(users)} users")

            # Here you would implement the actual user storage logic
            # For example: store in database, update user cache, etc.

            # Mock implementation - in a real scenario you'd store these users
            processed_count = len(users)

            return web.json_response(
                {
                    "status": "success",
                    "processed_count": processed_count,
                    "job_id": job_id,
                    "message": f"Successfully processed {processed_count} users",
                }
            )

        except Exception as e:
            logger.error(f"Error processing user import: {e}")
            return web.json_response({"status": "error", "error": str(e)}, status=400)

    async def handle_ingest_completed(self, request):
        """Handle document ingestion completion notification."""
        try:
            data = await request.json()
            job_id = data.get("job_id", "unknown")
            job_type = data.get("job_type", "unknown")
            result = data.get("result", {})
            folder_id = data.get("folder_id", "unknown")

            logger.info(
                f"Received ingestion completion from job {job_id}: {job_type} with result: {result}"
            )

            # Here you would implement post-ingestion logic
            # For example: update search indexes, notify users, etc.

            return web.json_response(
                {
                    "status": "success",
                    "job_id": job_id,
                    "message": f"Successfully processed ingestion completion for {folder_id}",
                }
            )

        except Exception as e:
            logger.error(f"Error processing ingestion completion: {e}")
            return web.json_response({"status": "error", "error": str(e)}, status=400)

    async def handle_metrics_store(self, request):
        """Handle metrics storage from tasks service."""
        try:
            data = await request.json()
            job_id = data.get("job_id", "unknown")
            metrics = data.get("metrics", {})

            logger.info(f"Received metrics from job {job_id}: {metrics}")

            # Here you would implement metrics storage logic
            # For example: store in time-series database, update dashboards, etc.

            return web.json_response(
                {
                    "status": "success",
                    "job_id": job_id,
                    "message": "Metrics stored successfully",
                }
            )

        except Exception as e:
            logger.error(f"Error storing metrics: {e}")
            return web.json_response({"status": "error", "error": str(e)}, status=400)

    async def get_usage_metrics(self, request):
        """Get usage metrics for tasks service."""
        try:
            hours = int(request.query.get("hours", 24))
            include_details = (
                request.query.get("include_details", "false").lower() == "true"
            )

            # Mock usage metrics - in a real implementation, fetch from database/cache
            metrics_data = {
                "time_range_hours": hours,
                "total_messages": 150,
                "active_users": 25,
                "response_time_avg": 2.3,
                "success_rate": 98.5,
                "data": [
                    {"hour": i, "messages": 10 + (i % 5) * 3, "users": 2 + (i % 3)}
                    for i in range(hours)
                ],
            }

            if not include_details:
                metrics_data.pop("data", None)

            return web.json_response(metrics_data)

        except Exception as e:
            logger.error(f"Error getting usage metrics: {e}")
            return web.json_response({"status": "error", "error": str(e)}, status=400)

    async def get_performance_metrics(self, request):
        """Get performance metrics for tasks service."""
        try:
            hours = int(request.query.get("hours", 24))
            include_system = (
                request.query.get("include_system", "false").lower() == "true"
            )

            # Mock performance metrics
            metrics_data = {
                "time_range_hours": hours,
                "avg_response_time_ms": 2300,
                "95th_percentile_ms": 4500,
                "99th_percentile_ms": 8000,
                "memory_usage_mb": 256,
                "cpu_usage_percent": 15.3,
                "data": [
                    {
                        "hour": i,
                        "response_time": 2000 + (i % 7) * 200,
                        "memory": 240 + (i % 5) * 10,
                    }
                    for i in range(min(hours, 24))
                ],
            }

            if not include_system:
                for item in metrics_data.get("data", []):
                    item.pop("memory", None)

            return web.json_response(metrics_data)

        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return web.json_response({"status": "error", "error": str(e)}, status=400)

    async def get_error_metrics(self, request):
        """Get error metrics for tasks service."""
        try:
            hours = int(request.query.get("hours", 24))
            severity = request.query.get("severity", "warning,error,critical")

            severities = [s.strip() for s in severity.split(",")]

            # Mock error metrics
            metrics_data = {
                "time_range_hours": hours,
                "total_errors": 12,
                "error_rate_percent": 1.5,
                "severities": severities,
                "data": [
                    {
                        "hour": i,
                        "warning": max(0, 2 - (i % 3)),
                        "error": max(0, 1 - (i % 5)),
                        "critical": 1 if i % 12 == 0 else 0,
                    }
                    for i in range(min(hours, 24))
                ],
            }

            return web.json_response(metrics_data)

        except Exception as e:
            logger.error(f"Error getting error metrics: {e}")
            return web.json_response({"status": "error", "error": str(e)}, status=400)
