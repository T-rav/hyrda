"""Health check endpoints for monitoring and load balancer probes."""

import logging

from flask import Blueprint, jsonify

logger = logging.getLogger(__name__)

# Create blueprint
health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
@health_bp.route("/api/health", methods=["GET"])
def health_check():
    """Basic health check endpoint.

    Returns:
        JSON response with status
    """
    return jsonify({"status": "healthy", "service": "control-plane"})
