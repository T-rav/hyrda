import logging
from datetime import UTC, datetime

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
        app.router.add_get("/health", self.health_check)
        app.router.add_get("/ready", self.readiness_check)
        app.router.add_get("/metrics", self.metrics)
        app.router.add_get("/prometheus", self.prometheus_metrics)

        self.runner = web.AppRunner(app)
        await self.runner.setup()

        # Bind to all interfaces for containerized deployment
        self.site = web.TCPSite(self.runner, "0.0.0.0", port)  # nosec B104
        await self.site.start()

        logger.info(f"Health check server started on port {port}")

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
