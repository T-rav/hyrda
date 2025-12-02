"""Health check endpoint."""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health_check(request: Request):
    """Health check endpoint.

    Returns:
        Dictionary with scheduler running status
    """
    scheduler_service = request.app.state.scheduler_service

    return {
        "scheduler_running": (
            scheduler_service.scheduler.running
            if scheduler_service and scheduler_service.scheduler
            else False
        ),
    }


@router.get("/api/health")
async def health_check_api(request: Request):
    """Health check endpoint (alternative path).

    Returns:
        Dictionary with scheduler running status
    """
    return await health_check(request)
