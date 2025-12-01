"""Health check endpoint."""

from flask import Blueprint, Response, g, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.before_request
def load_services():
    """Load services into Flask's g object before each request."""
    from flask import current_app

    g.scheduler_service = current_app.extensions.get("scheduler_service")


def init_services(scheduler_svc):
    """Initialize service references (kept for compatibility).

    Services are now stored in current_app.extensions and accessed via g.
    """
    # No-op: Services are accessed via g in routes
    pass


@health_bp.route("/health", methods=["GET"])
def health_check() -> Response:
    """Health check endpoint."""
    return jsonify(
        {
            "scheduler_running": g.scheduler_service.scheduler.running
            if g.scheduler_service and g.scheduler_service.scheduler
            else False,
        }
    )
