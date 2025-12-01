"""Health check endpoint."""

from flask import Blueprint, Response, jsonify

health_bp = Blueprint("health", __name__)

# Global service reference (injected by app.py)
scheduler_service = None


def init_services(scheduler_svc):
    """Initialize global service references."""
    global scheduler_service
    scheduler_service = scheduler_svc


@health_bp.route("/health", methods=["GET"])
def health_check() -> Response:
    """Health check endpoint."""
    return jsonify(
        {
            "scheduler_running": scheduler_service.scheduler.running
            if scheduler_service and scheduler_service.scheduler
            else False,
        }
    )
