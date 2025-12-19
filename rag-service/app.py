"""RAG Service - FastAPI server for retrieval-augmented generation.

This service provides RAG capabilities that can be called from:
- Bot service (Slack bot)
- LibreChat (future)
- Other internal services

The service handles:
- Agent routing (decides when to use agents vs LLM)
- RAG retrieval and context building
- LLM generation with tools (web search, deep research)
- Response generation with citations
"""

import logging
import os
import sys
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Add shared directory to path
sys.path.insert(0, "/app")
from shared.middleware.prometheus_metrics import (
    PrometheusMetricsMiddleware,
    create_metrics_endpoint,
)
from shared.middleware.tracing import TracingMiddleware
from shared.utils.otel_tracing import instrument_fastapi

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI application."""
    logger.info("Starting RAG Service...")

    # Initialize metrics service
    from services.metrics_service import initialize_metrics_service

    initialize_metrics_service(enabled=True)
    logger.info("Metrics service initialized")

    # Initialize RAG service components
    from config.settings import get_settings

    settings = get_settings()
    logger.info(
        f"RAG Service starting on port {settings.port} (environment: {settings.environment})"
    )
    logger.info(f"Vector DB enabled: {settings.vector.enabled}")
    logger.info(f"Query rewriting enabled: {settings.rag.enable_query_rewriting}")

    # Initialize vector store
    if settings.vector.enabled:
        try:
            from services.vector_service import create_vector_store, set_vector_store

            vector_store = create_vector_store(settings.vector)
            await vector_store.initialize()
            set_vector_store(vector_store)  # Store as global singleton
            logger.info("✅ Vector store initialized")
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")

    # Initialize search clients (Tavily, Perplexity)
    try:
        from services.search_clients import initialize_search_clients

        await initialize_search_clients(
            tavily_api_key=settings.search.tavily_api_key,
            perplexity_api_key=settings.search.perplexity_api_key,
        )
    except Exception as e:
        logger.warning(f"Search clients initialization failed (tools will be unavailable): {e}")

    yield
    logger.info("Shutting down RAG Service...")

    # Cleanup search clients
    try:
        from services.search_clients import close_search_clients

        await close_search_clients()
    except Exception:
        pass


# Create FastAPI app
def get_app_version() -> str:
    """Get application version from .version file at project root."""
    try:
        version_file = Path(__file__).parent.parent / ".version"
        if version_file.exists():
            return version_file.read_text().strip()
        return "0.0.0"
    except Exception:
        return "0.0.0"


app = FastAPI(
    title="RAG Service",
    description="Retrieval-Augmented Generation service with agent routing",
    version=get_app_version(),
    lifespan=lifespan,
)

# Add custom trace ID middleware (must be first for complete request tracking)
app.add_middleware(TracingMiddleware, service_name="rag-service")

# Add OpenTelemetry instrumentation (automatic span creation)
instrument_fastapi(app, "rag-service")

# Add Prometheus metrics middleware
app.add_middleware(PrometheusMetricsMiddleware, service_name="rag-service")

# Add CORS middleware - restrict to specific origins
allowed_origins = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:8000,http://localhost:3000,http://localhost:8002"
)
origins_list = [origin.strip() for origin in allowed_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include routers after app is created
from api.rag import router as rag_router  # noqa: E402

app.include_router(rag_router, prefix="/api")


@app.get("/health")
@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"service": "rag-service", "status": "healthy"}


@app.get("/ready")
@app.get("/api/ready")
async def ready():
    """Readiness probe - checks if service dependencies are available."""
    from config.settings import get_settings

    settings = get_settings()
    checks = {"status": "ready"}

    # Check vector DB if enabled
    if settings.vector.enabled:
        try:
            from services.vector_service import create_vector_store

            vector_store = create_vector_store(settings.vector)
            # Simple health check - try to get collection info
            collection_info = await vector_store.get_collection_info()
            checks["vector_db"] = "healthy" if collection_info else "degraded"
        except Exception as e:
            logger.error(f"Vector DB health check failed: {e}")
            checks["vector_db"] = "unhealthy"
            checks["status"] = "degraded"

    # Check Redis cache if enabled
    if settings.cache.enabled:
        try:
            from services.conversation_cache import ConversationCache

            cache = ConversationCache(settings.cache.redis_url)
            # Simple ping check
            await cache._redis.ping()
            checks["cache"] = "healthy"
        except Exception as e:
            logger.error(f"Cache health check failed: {e}")
            checks["cache"] = "unhealthy"
            checks["status"] = "degraded"

    return checks


@app.get("/api/metrics")
@app.get("/metrics")
async def rag_metrics():
    """RAG service metrics."""
    from services.metrics_service import get_metrics_service

    metrics_service = get_metrics_service()
    if not metrics_service:
        return {"error": "Metrics service not available"}

    return {
        "service": "rag-service",
        "metrics": {
            "description": "RAG generation and retrieval metrics",
            # Add specific RAG metrics here
        },
    }


# Prometheus metrics endpoint
app.get("/prometheus")(create_metrics_endpoint())


@app.get("/")
async def root():
    """Root endpoint with service info."""
    from config.settings import get_settings

    settings = get_settings()

    return {
        "service": "rag-service",
        "version": get_app_version(),
        "capabilities": [
            "RAG generation",
            "Agent routing",
            "Web search (Tavily)",
            "Deep research (Perplexity)" if settings.search.perplexity_enabled else None,
            "Query rewriting" if settings.rag.enable_query_rewriting else None,
        ],
        "vector_db": {
            "enabled": settings.vector.enabled,
            "provider": settings.vector.provider if settings.vector.enabled else None,
        },
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

    from config.settings import get_settings

    settings = get_settings()
    port = settings.port

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        reload=settings.environment != "production",
    )
