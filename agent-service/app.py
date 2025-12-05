"""Agent Service - FastAPI server for LangGraph agent execution.

This service exposes agents as REST APIs that can be called from:
- Slack bot
- LibreChat
- Web UI
- API clients
"""

import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Import tracing middleware from shared
sys.path.insert(0, "/app")
from shared.middleware.tracing import TracingMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Import agents after logging is configured
from agents import agent_registry  # noqa: E402
from api import agents_router  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI application."""
    logger.info("Starting Agent Service...")

    # Initialize metrics service
    from services.metrics_service import initialize_metrics_service

    initialize_metrics_service(enabled=True)
    logger.info("Metrics service initialized")

    # Sync agents to control plane on startup
    from services.agent_sync import sync_agents_to_control_plane

    sync_agents_to_control_plane()

    # Log registered agents
    from services import agent_registry as dynamic_registry

    agents = dynamic_registry.list_agents()
    logger.info(f"Registered agents: {[a['name'] for a in agents]}")

    yield
    logger.info("Shutting down Agent Service...")


# Create FastAPI app
app = FastAPI(
    title="Agent Service",
    description="LangGraph agent execution service",
    version="1.0.0",
    lifespan=lifespan,
)

# Add tracing middleware (must be first for complete request tracking)
app.add_middleware(TracingMiddleware, service_name="agent-service")

# Add CORS middleware - restrict to specific origins
allowed_origins = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:8000,http://localhost:3000"
)
origins_list = [origin.strip() for origin in allowed_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(agents_router, prefix="/api")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"service": "agent-service"}


@app.get("/api/metrics")
async def metrics():
    """Agent service metrics including invocation stats."""
    from services.metrics_service import get_metrics_service

    metrics_service = get_metrics_service()
    if not metrics_service:
        return {"agent_invocations": {"error": "Metrics service not available"}}

    agent_stats = metrics_service.get_agent_stats()

    return {
        "service": "agent-service",
        "agent_invocations": {
            "total": agent_stats["total_invocations"],
            "successful": agent_stats["successful_invocations"],
            "failed": agent_stats["failed_invocations"],
            "success_rate": agent_stats["success_rate"],
            "error_rate": agent_stats["error_rate"],
            "by_agent": agent_stats["by_agent"],
            "description": f"Agent invocations across all clients (since {agent_stats['last_reset'].strftime('%H:%M')})",
        },
    }


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "agent-service",
        "version": "1.0.0",
        "agents": [
            {
                "name": agent["name"],
                "aliases": agent.get("aliases", []),
            }
            for agent in agent_registry.list_agents()
        ],
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("ENVIRONMENT") != "production",
    )
