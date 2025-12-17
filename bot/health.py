import logging
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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

    async def start_server(self, port: int = 8080) -> None:
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

    async def stop_server(self) -> None:
        """Stop health check HTTP server"""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()

    async def health_check(self, request) -> web.Response:
        """Basic health check - is the service running?"""
        return web.json_response(
            {
                "status": "healthy",
            }
        )

    async def readiness_check(self, request: web.Request) -> web.Response:
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
                import langfuse  # noqa: F401  # type: ignore[reportMissingImports,reportUnusedImport]

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
                import prometheus_client  # noqa: F401  # type: ignore[reportMissingImports,reportUnusedImport]

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

        # Add RAG service check
        if metrics_service and metrics_service.enabled:
            rag_stats = metrics_service.get_rag_stats()
            checks["rag"] = {
                "status": "healthy",
                "total_queries": rag_stats["total_queries"],
                "success_rate": rag_stats["success_rate"],
                "miss_rate": rag_stats["miss_rate"],
                "avg_chunks": rag_stats["avg_chunks_per_query"],
                "documents_used": rag_stats["total_documents_used"],
                "description": "RAG query performance tracking",
            }
        else:
            checks["rag"] = {
                "status": "disabled",
                "message": "RAG metrics require metrics service to be enabled",
            }

        response_data = {
            "status": "ready" if all_healthy else "not_ready",
            "checks": checks,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        status_code = 200 if all_healthy else 503
        return web.json_response(response_data, status=status_code)

    async def metrics(self, request: web.Request) -> web.Response:
        """Basic metrics endpoint (JSON format)"""
        uptime = datetime.now(UTC) - self.start_time

        metrics: dict[str, Any] = {
            "uptime_seconds": int(uptime.total_seconds()),
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

            # Get agent invocation stats
            agent_stats = metrics_service.get_agent_stats()
            metrics["agent_invocations"] = {
                "total": agent_stats["total_invocations"],
                "successful": agent_stats["successful_invocations"],
                "failed": agent_stats["failed_invocations"],
                "success_rate": agent_stats["success_rate"],
                "error_rate": agent_stats["error_rate"],
                "by_agent": agent_stats["by_agent"],
                "description": f"Agent invocations (since {agent_stats['last_reset'].strftime('%H:%M')})",
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

        # Add LLM configuration from settings
        if self.settings and self.settings.llm:
            metrics["llm"] = {
                "provider": self.settings.llm.provider,
                "model": self.settings.llm.model,
            }

        return web.json_response(metrics)

    async def prometheus_metrics(self, request) -> web.Response:
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

    async def health_ui(self, request) -> web.Response:
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

    async def handle_user_import(self, request) -> web.Response:
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

    async def handle_ingest_completed(self, request) -> web.Response:
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

    async def handle_metrics_store(self, request) -> web.Response:
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

    async def get_usage_metrics(self, request) -> web.Response:
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

    async def get_performance_metrics(self, request) -> web.Response:
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

    async def get_error_metrics(self, request) -> web.Response:
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

    async def services_health(self, request: web.Request) -> web.Response:
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
