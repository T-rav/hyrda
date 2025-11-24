"""Dashboard Service - System-wide health and metrics dashboard.

Aggregates metrics from all services:
- Bot (Slack integration)
- Agent Service (LangGraph agents)
- Tasks (Scheduled jobs)
- Control Plane (Admin UI)
"""

import logging
from pathlib import Path

import aiohttp
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="InsightMesh Dashboard",
    description="System-wide health and metrics dashboard",
    version="1.0.0",
)


# Service URLs (Docker service names)
SERVICES = {
    "bot": "http://bot:8080",
    "agent_service": "http://agent_service:8000",
    "tasks": "http://tasks:8081",
    "control_plane": "http://control_plane:6001",
}


@app.get("/health")
@app.get("/api/health")
async def health():
    """Health check for dashboard service itself."""
    return {"status": "healthy", "service": "dashboard"}


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
                    f"{base_url}/api/metrics", timeout=aiohttp.ClientTimeout(total=5)
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

    return metrics


@app.get("/api/services/health")
async def get_services_health():
    """Get health status of all services."""
    services = {}

    async with aiohttp.ClientSession() as session:
        for service_name, base_url in SERVICES.items():
            try:
                async with session.get(
                    f"{base_url}/health", timeout=aiohttp.ClientTimeout(total=5)
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

    overall_healthy = all(
        s.get("status") == "healthy" for s in services.values()
    )

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
        async with aiohttp.ClientSession() as session:
            async with session.get(
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
