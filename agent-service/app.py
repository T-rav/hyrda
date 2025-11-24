"""Agent Service - FastAPI server for LangGraph agent execution.

This service exposes agents as REST APIs that can be called from:
- Slack bot
- LibreChat
- Web UI
- API clients
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
    logger.info(f"Registered agents: {[a['name'] for a in agent_registry.list_agents()]}")
    yield
    logger.info("Shutting down Agent Service...")


# Create FastAPI app
app = FastAPI(
    title="Agent Service",
    description="LangGraph agent execution service",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this based on your needs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(agents_router, prefix="/api")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "agent-service"}


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
