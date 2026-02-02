"""Health check endpoints for monitoring and load balancer probes."""

import logging
import os

import httpx
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()


async def check_langsmith_proxy_status() -> dict:
    """Check if LangSmith proxy is active and proxying traces to Langfuse.

    Returns:
        Dict with proxy status information
    """
    langchain_endpoint = os.getenv("LANGCHAIN_ENDPOINT", "")
    proxy_url = "http://langsmith-proxy:8003"

    is_configured = proxy_url in langchain_endpoint

    proxy_status = {
        "configured": is_configured,
        "active": False,
        "message": "Not configured",
    }

    if is_configured:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{proxy_url}/health")
                if response.status_code == 200:
                    proxy_status["active"] = True
                    proxy_status["message"] = (
                        "✅ Active - Proxying LangSmith traces to Langfuse"
                    )
                else:
                    proxy_status["message"] = "⚠️ Configured but not responding"
        except Exception as e:
            proxy_status["message"] = f"⚠️ Configured but unreachable: {str(e)}"
            logger.debug(f"LangSmith proxy health check failed: {e}")
    else:
        if (
            "langsmith" in langchain_endpoint.lower()
            or "smith.langchain" in langchain_endpoint.lower()
        ):
            proxy_status["message"] = "Using LangSmith cloud directly (not proxied)"
        else:
            proxy_status["message"] = "LangSmith tracing not configured"

    return proxy_status


@router.get("/health")
@router.get("/api/health")
async def health_check():
    """Basic health check endpoint.

    Returns:
        JSON response with status and LangSmith proxy information
    """
    proxy_status = await check_langsmith_proxy_status()

    return {
        "status": "healthy",
        "service": "control-plane",
        "langsmith_proxy": proxy_status,
    }


@router.get("/ready")
@router.get("/api/ready")
async def ready_check():
    """Readiness check endpoint for Kubernetes/Docker health probes.

    Returns:
        JSON response indicating if the service is ready to accept traffic
    """
    return {
        "status": "ready",
        "service": "control-plane",
    }
