"""Authentication endpoints for OAuth flow."""

import logging
import os

from flask import Blueprint, Response

from utils.auth import flask_auth_callback, flask_logout

logger = logging.getLogger(__name__)

# Create blueprint
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/callback")
def auth_callback() -> Response:
    """Handle OAuth callback."""
    service_base_url = os.getenv("SERVER_BASE_URL", "http://localhost:5001")
    return flask_auth_callback(service_base_url, "/auth/callback")


@auth_bp.route("/logout", methods=["POST"])
def logout() -> Response:
    """Handle logout."""
    return flask_logout()
