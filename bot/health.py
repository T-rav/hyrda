import logging
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

        # Services health endpoint
        app.router.add_get("/api/services/health", self.services_health)

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

    def _check_llm_api(self) -> tuple[dict, bool]:
        """Check LLM API connectivity.

        Returns:
            tuple: (check_result dict, is_healthy bool)
        """
        try:
            has_api_key = bool(self.settings.llm.api_key.get_secret_value())
            return {
                "status": "healthy" if has_api_key else "unhealthy",
                "provider": self.settings.llm.provider,
                "model": self.settings.llm.model,
            }, has_api_key
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}, False

    def _check_configuration(self) -> tuple[dict, bool]:
        """Check required environment variables.

        Returns:
            tuple: (check_result dict, is_healthy bool)
        """
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

        return {
            "status": "healthy" if not missing_vars else "unhealthy",
            "missing_variables": ", ".join(missing_vars) if missing_vars else "none",
        }, not bool(missing_vars)

    async def _check_cache(self) -> tuple[dict, bool]:
        """Check cache connectivity.

        Returns:
            tuple: (check_result dict, is_healthy bool)
        """
        if not self.conversation_cache:
            return {
                "status": "disabled",
                "message": "Cache service not configured - using Slack API only",
            }, True

        try:
            cache_stats = await self.conversation_cache.get_cache_stats()
            if cache_stats.get("status") == "available":
                return {
                    "status": "healthy",
                    "memory_used": cache_stats.get("memory_used", "unknown"),
                    "cached_conversations": cache_stats.get("cached_conversations", 0),
                    "redis_url": cache_stats.get("redis_url", "unknown"),
                }, True
            elif cache_stats.get("status") == "unavailable":
                return {
                    "status": "unhealthy",
                    "message": f"Configured but Redis unavailable at {cache_stats.get('redis_url', 'unknown')}",
                    "error": "Redis connection failed",
                }, False
            else:
                return {
                    "status": "unhealthy",
                    "error": cache_stats.get("error", "Unknown cache error"),
                }, False
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}, False

    def _check_langfuse(self) -> tuple[dict, bool]:
        """Check Langfuse connectivity.

        Returns:
            tuple: (check_result dict, is_healthy bool)
        """
        if not self.langfuse_service:
            try:
                import langfuse  # noqa: F401  # type: ignore[reportMissingImports,reportUnusedImport]

                langfuse_available = True
                message = "Langfuse package available but service not initialized"
            except ImportError:
                langfuse_available = False
                message = "Langfuse package not installed (pip install langfuse)"

            return {
                "status": "disabled",
                "enabled": False,
                "configured": False,
                "package_available": langfuse_available,
                "message": message,
            }, True

        if self.langfuse_service.enabled and self.langfuse_service.client:
            return {
                "status": "healthy",
                "enabled": True,
                "client_initialized": True,
                "configured": True,
                "host": self.langfuse_service.settings.host,
            }, True
        elif self.langfuse_service.enabled:
            return {
                "status": "unhealthy",
                "enabled": False,
                "configured": True,
                "message": "Enabled but client failed to initialize - check credentials and host",
                "host": self.langfuse_service.settings.host,
            }, False
        else:
            return {
                "status": "disabled",
                "enabled": False,
                "configured": True,
                "message": "Configured but disabled (check LANGFUSE_ENABLED or credentials)",
                "host": self.langfuse_service.settings.host,
            }, True

    def _check_metrics_service(self) -> tuple[dict, bool]:
        """Check metrics service status.

        Returns:
            tuple: (check_result dict, is_healthy bool)
        """
        metrics_service = get_metrics_service()

        if metrics_service and metrics_service.enabled:
            active_conversations = metrics_service.get_active_conversation_count()
            return {
                "status": "healthy",
                "enabled": True,
                "prometheus_available": True,
                "active_conversations": active_conversations,
                "endpoints": {
                    "metrics_json": "/api/metrics",
                    "prometheus": "/api/prometheus",
                },
                "description": "Prometheus metrics collection active",
            }, True
        elif metrics_service and not metrics_service.enabled:
            return {
                "status": "disabled",
                "enabled": False,
                "prometheus_available": True,
                "message": "Metrics service available but disabled",
            }, True
        else:
            try:
                import prometheus_client  # noqa: F401  # type: ignore[reportMissingImports,reportUnusedImport]

                prometheus_available = True
                message = "Metrics service not initialized - check app startup"
            except ImportError:
                prometheus_available = False
                message = "Prometheus client not available - install prometheus-client package"

            return {
                "status": "disabled",
                "enabled": False,
                "prometheus_available": prometheus_available,
                "message": message,
            }, True

    def _check_rag_service(self) -> tuple[dict, bool]:
        """Check RAG service status.

        Returns:
            tuple: (check_result dict, is_healthy bool)
        """
        metrics_service = get_metrics_service()

        if metrics_service and metrics_service.enabled:
            rag_stats = metrics_service.get_rag_stats()
            return {
                "status": "healthy",
                "total_queries": rag_stats["total_queries"],
                "success_rate": rag_stats["success_rate"],
                "miss_rate": rag_stats["miss_rate"],
                "avg_chunks": rag_stats["avg_chunks_per_query"],
                "documents_used": rag_stats["total_documents_used"],
                "description": "RAG query performance tracking",
            }, True
        else:
            return {
                "status": "disabled",
                "message": "RAG metrics require metrics service to be enabled",
            }, True

    async def readiness_check(self, request):
        """Readiness check - can the service handle requests?

        Orchestrates multiple health checks and returns aggregate status.
        Each check returns (result dict, is_healthy bool).
        """
        checks = {}
        all_healthy = True

        # Run all health checks
        checks["llm_api"], is_healthy = self._check_llm_api()
        all_healthy = all_healthy and is_healthy

        checks["configuration"], is_healthy = self._check_configuration()
        all_healthy = all_healthy and is_healthy

        checks["cache"], is_healthy = await self._check_cache()
        all_healthy = all_healthy and is_healthy

        checks["langfuse"], is_healthy = self._check_langfuse()
        all_healthy = all_healthy and is_healthy

        checks["metrics"], is_healthy = self._check_metrics_service()
        all_healthy = all_healthy and is_healthy

        checks["rag"], is_healthy = self._check_rag_service()
        all_healthy = all_healthy and is_healthy

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
            # Get active conversation count from metrics service (last 7 days)
            active_count = metrics_service.get_active_conversation_count()

            metrics["active_conversations"] = {
                "total": active_count,
                "description": "Active conversations (last 7 days)",
            }

            # Get RAG performance stats
            rag_stats = metrics_service.get_rag_stats()
            metrics["rag_performance"] = {
                "total_queries": rag_stats["total_queries"],
                "success_rate": rag_stats["success_rate"],
                "miss_rate": rag_stats["miss_rate"],
                "avg_chunks": rag_stats["avg_chunks_per_query"],
                "documents_used": rag_stats["total_documents_used"],
                "description": f"RAG queries processed (since {rag_stats['last_reset'].strftime('%H:%M')})",
            }

        # Add Langfuse lifetime stats
        if self.langfuse_service and self.langfuse_service.enabled:
            try:
                lifetime_stats = await self.langfuse_service.get_lifetime_stats(
                    start_date="2025-10-21"
                )
                metrics["lifetime_stats"] = {
                    "total_traces": lifetime_stats.get("total_traces", 0),
                    "total_observations": lifetime_stats.get("total_observations", 0),
                    "unique_threads": lifetime_stats.get("unique_sessions", 0),
                    "since_date": lifetime_stats.get("start_date", "2025-10-21"),
                    "description": "Lifetime statistics since Oct 21, 2025",
                }
                if "error" in lifetime_stats:
                    metrics["lifetime_stats"]["error"] = lifetime_stats["error"]
            except Exception as e:
                logger.error(f"Error fetching lifetime stats: {e}")
                metrics["lifetime_stats"] = {
                    "total_traces": 0,
                    "total_observations": 0,
                    "unique_threads": 0,
                    "since_date": "2025-10-21",
                    "error": str(e),
                    "description": "Lifetime statistics unavailable",
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

            # Serve the built React app
            with open(index_path, encoding="utf-8") as f:
                content = f.read()

            return web.Response(text=content, content_type="text/html")

        except Exception as e:
            logger.error(f"Error serving health UI: {e}")
            return web.Response(
                text="Health UI not available", content_type="text/plain", status=500
            )

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

    async def services_health(self, request):
        """Get health status of all services."""
        import aiohttp

        services = {}

        # Task Scheduler Health
        try:
            async with aiohttp.ClientSession() as session:
                # Get scheduler info and jobs count
                scheduler_resp = session.get(
                    "http://tasks:8081/api/scheduler/info", timeout=5
                )
                jobs_resp = session.get("http://tasks:8081/api/jobs", timeout=5)

                scheduler_result = await scheduler_resp
                jobs_result = await jobs_resp

                if scheduler_result.status == 200 and jobs_result.status == 200:
                    scheduler_data = await scheduler_result.json()
                    jobs_data = await jobs_result.json()

                    services["task_scheduler"] = {
                        "name": "Task Scheduler",
                        "status": "healthy",
                        "details": {
                            "running": scheduler_data.get("running", False),
                            "jobs_count": len(jobs_data.get("jobs", [])),
                        },
                    }
                else:
                    services["task_scheduler"] = {
                        "name": "Task Scheduler",
                        "status": "unhealthy",
                        "details": {
                            "error": f"Scheduler: HTTP {scheduler_result.status}, Jobs: HTTP {jobs_result.status}"
                        },
                    }
        except Exception as e:
            services["task_scheduler"] = {
                "name": "Task Scheduler",
                "status": "error",
                "details": {"error": str(e)},
            }

        # Database Health
        try:
            # Try to import pymysql - skip if not available
            try:
                import pymysql  # type: ignore[reportMissingModuleSource]
            except ImportError:
                services["database"] = {
                    "name": "MySQL Database",
                    "status": "disabled",
                    "details": {
                        "message": "pymysql not installed (optional dependency)"
                    },
                }
                raise  # Re-raise to skip to outer except

            # Try to connect to MySQL and list databases
            import os

            connection = pymysql.connect(
                host="mysql",
                port=3306,
                user="root",
                password=os.getenv("MYSQL_ROOT_PASSWORD", "password"),
                connect_timeout=5,
            )

            with connection.cursor() as cursor:
                cursor.execute("SHOW DATABASES")
                databases = [row[0] for row in cursor.fetchall()]
                # Filter out system databases
                user_databases = [
                    db
                    for db in databases
                    if db
                    not in ["information_schema", "performance_schema", "mysql", "sys"]
                ]

            connection.close()

            services["database"] = {
                "name": "MySQL Database",
                "status": "healthy",
                "details": {
                    "host": "mysql",
                    "port": "3306",
                    "databases": user_databases,
                    "total_databases": len(user_databases),
                },
            }
        except ImportError:
            # Already handled above - pymysql not available
            pass
        except Exception as e:
            services["database"] = {
                "name": "MySQL Database",
                "status": "error",
                "details": {"error": str(e)},
            }

        # Overall health status
        all_healthy = all(
            service["status"] == "healthy" for service in services.values()
        )

        return web.json_response(
            {
                "status": "healthy" if all_healthy else "degraded",
                "timestamp": datetime.now(UTC).isoformat(),
                "services": services,
            }
        )
