import logging
import os
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
                "version": "1.0.0",
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
                checks["cache"] = {
                    "status": "healthy"
                    if cache_stats.get("status") == "available"
                    else "unhealthy",
                    "memory_used": cache_stats.get("memory_used", "unknown"),
                    "cached_conversations": cache_stats.get("cached_conversations", 0),
                }
            except Exception as e:
                checks["cache"] = {"status": "unhealthy", "error": str(e)}
                all_healthy = False
        else:
            checks["cache"] = {
                "status": "disabled",
                "message": "Cache service not configured",
            }

        # Check Langfuse connectivity
        if self.langfuse_service:
            checks["langfuse"] = {
                "status": "healthy" if self.langfuse_service.enabled else "disabled",
                "enabled": self.langfuse_service.enabled,
            }
        else:
            checks["langfuse"] = {
                "status": "disabled",
                "message": "Langfuse service not configured",
            }

        # Check metrics service
        metrics_service = get_metrics_service()
        checks["metrics"] = {
            "status": "healthy"
            if metrics_service and metrics_service.enabled
            else "disabled",
            "enabled": metrics_service.enabled if metrics_service else False,
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

                # Update metrics service with cache data
                metrics_service = get_metrics_service()
                if metrics_service and cache_stats.get("cached_conversations"):
                    metrics_service.update_active_conversations(
                        int(cache_stats["cached_conversations"])
                    )
            except Exception as e:
                metrics["cache"] = {"status": "error", "error": str(e)}

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
        return web.Response(
            text=metrics_data, content_type=metrics_service.get_content_type()
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
    <title>AI Slack Bot - Health Dashboard</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            margin: 0;
            padding: 20px;
            min-height: 100vh;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.95);
            border-radius: 12px;
            padding: 2rem;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }
        .header {
            text-align: center;
            margin-bottom: 2rem;
        }
        .header h1 {
            color: #1a202c;
            margin: 0 0 0.5rem 0;
        }
        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        .status-card {
            background: white;
            border-radius: 8px;
            padding: 1rem;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }
        .api-links {
            background: #f8fafc;
            border-radius: 8px;
            padding: 1.5rem;
        }
        .api-links h3 {
            margin: 0 0 1rem 0;
            color: #1a202c;
        }
        .api-links a {
            display: inline-block;
            margin: 0.25rem 0.5rem;
            padding: 0.5rem 1rem;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            font-size: 0.875rem;
        }
        .api-links a:hover {
            background: #5a67d8;
        }
        .build-info {
            margin-top: 1rem;
            padding: 1rem;
            background: #fef3cd;
            border-radius: 4px;
            font-size: 0.875rem;
        }
        .status-healthy { color: #10b981; }
        .status-error { color: #ef4444; }
        .auto-refresh { font-size: 0.875rem; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 AI Slack Bot Health Dashboard</h1>
            <p class="auto-refresh">Auto-refreshing every 10 seconds...</p>
        </div>

        <div class="status-grid">
            <div class="status-card">
                <h3>System Status</h3>
                <div id="system-status" class="status-error">Loading...</div>
            </div>
            <div class="status-card">
                <h3>LLM Service</h3>
                <div id="llm-status" class="status-error">Loading...</div>
            </div>
            <div class="status-card">
                <h3>Cache Service</h3>
                <div id="cache-status" class="status-error">Loading...</div>
            </div>
            <div class="status-card">
                <h3>Metrics</h3>
                <div id="metrics-status" class="status-error">Loading...</div>
            </div>
        </div>

        <div class="api-links">
            <h3>API Endpoints</h3>
            <a href="/api/health" target="_blank">Health Check</a>
            <a href="/api/ready" target="_blank">Readiness Check</a>
            <a href="/api/metrics" target="_blank">Metrics (JSON)</a>
            <a href="/api/prometheus" target="_blank">Prometheus Metrics</a>
        </div>

        <div class="build-info">
            <strong>ℹ️ Development Mode:</strong>
            This is a simple fallback UI. For the full React dashboard, run:
            <br><br>
            <code>cd bot/health_ui && npm install && npm run build</code>
        </div>
    </div>

    <script>
        async function updateStatus() {
            try {
                // Fetch health data
                const [health, ready] = await Promise.all([
                    fetch('/api/health').then(r => r.json()),
                    fetch('/api/ready').then(r => r.json())
                ]);

                // Update system status
                const systemEl = document.getElementById('system-status');
                systemEl.textContent = health.status === 'healthy' ? '✅ Healthy' : '❌ Unhealthy';
                systemEl.className = health.status === 'healthy' ? 'status-healthy' : 'status-error';

                // Update LLM status
                const llmEl = document.getElementById('llm-status');
                const llmStatus = ready.checks?.llm_api?.status;
                llmEl.textContent = llmStatus === 'healthy' ? '✅ Connected' : '❌ Error';
                llmEl.className = llmStatus === 'healthy' ? 'status-healthy' : 'status-error';

                // Update cache status
                const cacheEl = document.getElementById('cache-status');
                const cacheStatus = ready.checks?.cache?.status;
                if (cacheStatus === 'healthy') {
                    cacheEl.textContent = '✅ Available';
                    cacheEl.className = 'status-healthy';
                } else if (cacheStatus === 'disabled') {
                    cacheEl.textContent = '⚪ Disabled';
                    cacheEl.className = 'status-healthy';
                } else {
                    cacheEl.textContent = '❌ Error';
                    cacheEl.className = 'status-error';
                }

                // Update metrics status
                const metricsEl = document.getElementById('metrics-status');
                const metricsStatus = ready.checks?.metrics?.status;
                if (metricsStatus === 'healthy') {
                    metricsEl.textContent = '✅ Enabled';
                    metricsEl.className = 'status-healthy';
                } else if (metricsStatus === 'disabled') {
                    metricsEl.textContent = '⚪ Disabled';
                    metricsEl.className = 'status-healthy';
                } else {
                    metricsEl.textContent = '❌ Error';
                    metricsEl.className = 'status-error';
                }

            } catch (error) {
                console.error('Error updating status:', error);
                document.querySelectorAll('[id$="-status"]').forEach(el => {
                    el.textContent = '❌ Error';
                    el.className = 'status-error';
                });
            }
        }

        // Initial load and auto-refresh
        updateStatus();
        setInterval(updateStatus, 10000);
    </script>
</body>
</html>
        """.strip()
