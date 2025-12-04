"""Dashboard Service - System-wide health and metrics dashboard.

Aggregates metrics from all services:
- Bot (Slack integration)
- Agent Service (LangGraph agents)
- Tasks (Scheduled jobs)
- Control Plane (Admin UI)
"""

import logging
import os
from pathlib import Path

import aiohttp
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from utils.auth import FastAPIAuthMiddleware, fastapi_auth_callback, fastapi_logout

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# HTTP client configuration constants
DEFAULT_SERVICE_TIMEOUT = 5  # Timeout for service health checks in seconds

app = FastAPI(
    title="InsightMesh Dashboard",
    description="System-wide health and metrics dashboard",
    version="1.0.0",
)

# Add session middleware for authentication
from starlette.middleware.sessions import SessionMiddleware

# Validate SECRET_KEY in production
secret_key = os.getenv("SECRET_KEY", "dev-secret-change-in-prod")
environment = os.getenv("ENVIRONMENT", "development")
is_production = environment == "production"
is_default_key = secret_key in [
    "dev-secret-key-change-in-production",
    "dev-secret-key-change-in-prod",
    "dev-secret-change-in-prod",
]
if is_production and is_default_key:
    raise ValueError(
        "SECRET_KEY must be set to a secure value in production. "
        "Current value is the default development key."
    )

app.add_middleware(SessionMiddleware, secret_key=secret_key)

# Add authentication middleware
service_base_url = os.getenv("DASHBOARD_BASE_URL", "http://localhost:8080")
app.add_middleware(
    FastAPIAuthMiddleware,
    service_base_url=service_base_url,
    callback_path="/auth/callback",
)


# Service URLs (Docker service names)
SERVICES = {
    "bot": "http://bot:8080",
    "agent_service": "http://agent_service:8000",
    "tasks": "http://tasks:8081",
    "control_plane": "http://control_plane:6001",
}


# Authentication routes
@app.get("/auth/callback")
async def auth_callback(request: Request):
    """Handle OAuth callback."""
    return await fastapi_auth_callback(request, service_base_url, "/auth/callback")


@app.post("/auth/logout")
async def logout():
    """Handle logout."""
    return await fastapi_logout()


@app.get("/health")
@app.get("/api/health")
async def health():
    """Health check for dashboard service itself."""
    return {"status": "healthy", "service": "dashboard"}


@app.get("/api/ready")
async def ready():
    """Readiness check - aggregates health from all services."""
    checks = {
        "dashboard": {"status": "healthy"},
    }

    # Check all services
    async with aiohttp.ClientSession() as session:
        for service_name, base_url in SERVICES.items():
            try:
                async with session.get(
                    f"{base_url}/health", timeout=aiohttp.ClientTimeout(total=DEFAULT_SERVICE_TIMEOUT)
                ) as response:
                    if response.status == 200:
                        checks[service_name] = {
                            "status": "healthy",
                            "url": base_url,
                        }
                    else:
                        checks[service_name] = {
                            "status": "unhealthy",
                            "error": f"HTTP {response.status}",
                        }
            except aiohttp.ClientConnectorError:
                checks[service_name] = {
                    "status": "unavailable",
                    "error": "Service not reachable",
                }
            except Exception as e:
                checks[service_name] = {"status": "error", "error": str(e)}

        # Fetch additional data from bot metrics for the UI
        try:
            async with session.get(
                f"{SERVICES['bot']}/api/metrics", timeout=aiohttp.ClientTimeout(total=DEFAULT_SERVICE_TIMEOUT)
            ) as response:
                if response.status == 200:
                    bot_metrics = await response.json()

                    # RAG performance data
                    rag_data = bot_metrics.get("rag_performance", {})
                    if rag_data:
                        checks["rag"] = {
                            "status": "enabled",
                            **rag_data,
                        }

                    # Cache data
                    cache_data = bot_metrics.get("cache", {})
                    if cache_data:
                        checks["cache"] = {
                            "status": "healthy"
                            if cache_data.get("status") == "available"
                            else "unhealthy",
                            "cached_conversations": cache_data.get(
                                "cached_conversations", 0
                            ),
                            "memory_used": cache_data.get("memory_used", "N/A"),
                        }

                    # Langfuse data
                    langfuse_data = bot_metrics.get("services", {}).get("langfuse", {})
                    if langfuse_data:
                        checks["langfuse"] = {
                            "status": "healthy"
                            if langfuse_data.get("enabled")
                            and langfuse_data.get("available")
                            else "disabled",
                            "host": "cloud.langfuse.com",
                        }

                    # LLM API data from bot metrics
                    llm_data = bot_metrics.get("llm", {})
                    if llm_data:
                        checks["llm_api"] = {
                            "status": "healthy",
                            "provider": llm_data.get("provider", "Unknown"),
                            "model": llm_data.get("model", "Unknown"),
                        }
                    else:
                        checks["llm_api"] = {
                            "status": "unknown",
                            "provider": "Not configured",
                            "model": "N/A",
                        }
        except Exception as e:
            logger.error(
                f"Failed to fetch bot metrics: {type(e).__name__}: {e}", exc_info=True
            )

    # Overall readiness - consider "enabled" status as healthy for optional features like RAG
    all_healthy = all(
        c.get("status") in ["healthy", "enabled"] for c in checks.values()
    )

    return {
        "status": "ready" if all_healthy else "not_ready",
        "checks": checks,
    }


@app.get("/api/metrics")
async def get_all_metrics():
    """Aggregate metrics from all services."""
    metrics = {
        "dashboard": {
            "status": "healthy",
            "service": "dashboard-service",
        }
    }

    # Fetch metrics from each service
    async with aiohttp.ClientSession() as session:
        for service_name, base_url in SERVICES.items():
            try:
                async with session.get(
                    f"{base_url}/api/metrics", timeout=aiohttp.ClientTimeout(total=DEFAULT_SERVICE_TIMEOUT)
                ) as response:
                    if response.status == 200:
                        metrics[service_name] = await response.json()
                    else:
                        metrics[service_name] = {
                            "status": "error",
                            "error": f"HTTP {response.status}",
                        }
            except aiohttp.ClientConnectorError:
                metrics[service_name] = {
                    "status": "unavailable",
                    "error": "Service not reachable",
                }
            except Exception as e:
                metrics[service_name] = {"status": "error", "error": str(e)}

    # Flatten lifetime_stats to top level for UI compatibility
    if "bot" in metrics and "lifetime_stats" in metrics["bot"]:
        metrics["lifetime_stats"] = metrics["bot"]["lifetime_stats"]

    return metrics


@app.get("/api/services/health")
async def get_services_health():
    """Get health status of all services."""
    services = {}

    async with aiohttp.ClientSession() as session:
        for service_name, base_url in SERVICES.items():
            try:
                async with session.get(
                    f"{base_url}/health", timeout=aiohttp.ClientTimeout(total=DEFAULT_SERVICE_TIMEOUT)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        services[service_name] = {
                            "name": service_name.replace("_", " ").title(),
                            "status": "healthy",
                            "url": base_url,
                            "details": data,
                        }
                    else:
                        services[service_name] = {
                            "name": service_name.replace("_", " ").title(),
                            "status": "unhealthy",
                            "url": base_url,
                            "details": {"error": f"HTTP {response.status}"},
                        }
            except aiohttp.ClientConnectorError:
                services[service_name] = {
                    "name": service_name.replace("_", " ").title(),
                    "status": "unavailable",
                    "url": base_url,
                    "details": {"error": "Service not reachable"},
                }
            except Exception as e:
                services[service_name] = {
                    "name": service_name.replace("_", " ").title(),
                    "status": "error",
                    "url": base_url,
                    "details": {"error": str(e)},
                }

    overall_healthy = all(s.get("status") == "healthy" for s in services.values())

    return {
        "status": "healthy" if overall_healthy else "degraded",
        "services": services,
    }


@app.get("/api/agent-metrics")
async def get_agent_metrics():
    """Get agent-specific metrics from agent-service.

    NOTE: Metrics are tracked at the source (agent-service) to count
    ALL invocations regardless of client (Slack, LibreChat, direct API).
    """
    try:
        async with aiohttp.ClientSession() as session, session.get(
            f"{SERVICES['agent_service']}/api/metrics",
            timeout=aiohttp.ClientTimeout(total=5),
        ) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("agent_invocations", {})
            else:
                return {"error": f"HTTP {response.status}"}
    except Exception as e:
        return {"error": str(e)}


# Serve the React dashboard UI
@app.get("/")
@app.get("/ui")
async def serve_ui():
    """Serve the dashboard UI."""
    ui_path = Path(__file__).parent / "health_ui" / "dist" / "index.html"
    if ui_path.exists():
        return FileResponse(ui_path)
    else:
        return JSONResponse(
            {"error": "Dashboard UI not built"},
            status_code=500,
        )


# Mount static assets
ui_assets_path = Path(__file__).parent / "health_ui" / "dist" / "assets"
if ui_assets_path.exists():
    app.mount("/assets", StaticFiles(directory=str(ui_assets_path)), name="assets")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
    )
