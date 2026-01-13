"""Health check endpoints for monitoring and load balancer probes."""

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


@router.get("/health")
@router.get("/api/health")
async def health_check():
    """Basic health check endpoint.

    Returns:
        JSON response with status
    """
    return {"status": "healthy", "service": "control-plane"}
