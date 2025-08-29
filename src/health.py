import logging
from datetime import UTC, datetime

from aiohttp import ClientSession, ClientTimeout, web
from aiohttp.web_runner import AppRunner, TCPSite

from config.settings import Settings

logger = logging.getLogger(__name__)

# Constants
HTTP_OK = 200
HEALTH_CHECK_TIMEOUT = 5


class HealthChecker:
    """Health check service for monitoring bot status"""

    def __init__(
        self, settings: Settings, conversation_cache=None, prompt_service=None
    ):
        self.settings = settings
        self.conversation_cache = conversation_cache
        self.prompt_service = prompt_service
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
        app.router.add_get("/migrations", self.migration_status)

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
            async with (
                ClientSession() as session,
                session.get(
                    f"{self.settings.llm.base_url}/health",
                    timeout=ClientTimeout(total=HEALTH_CHECK_TIMEOUT),
                ) as resp,
            ):
                checks["llm_api"] = {
                    "status": "healthy" if resp.status == HTTP_OK else "unhealthy",
                    "response_code": resp.status,
                }
                if resp.status != HTTP_OK:
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

        response_data = {
            "status": "ready" if all_healthy else "not_ready",
            "checks": checks,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        status_code = 200 if all_healthy else 503
        return web.json_response(response_data, status=status_code)

    async def metrics(self, request):
        """Basic metrics endpoint"""
        uptime = datetime.now(UTC) - self.start_time

        metrics = {
            "uptime_seconds": int(uptime.total_seconds()),
            "start_time": self.start_time.isoformat(),
            "current_time": datetime.now(UTC).isoformat(),
        }

        # Add cache statistics if available
        if self.conversation_cache:
            cache_stats = await self.conversation_cache.get_cache_stats()
            metrics["cache"] = cache_stats

        return web.json_response(metrics)

    async def migration_status(self, request):
        """Database migration status endpoint"""
        if not self.prompt_service or not self.prompt_service.migration_manager:
            return web.json_response(
                {"status": "disabled", "message": "Database or migrations not enabled"}
            )

        try:
            status = await self.prompt_service.migration_manager.get_migration_status()
            return web.json_response(
                {
                    "status": "healthy",
                    "migrations": status,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
        except Exception as e:
            return web.json_response(
                {
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                status=500,
            )
