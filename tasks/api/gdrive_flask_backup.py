"""Google Drive OAuth and integration endpoints."""

import json
import logging
import os
import sys
import uuid
from pathlib import Path

from flask import Blueprint, Response, jsonify, render_template, request, session
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from config.settings import get_settings
from models.base import get_db_session
from models.oauth_credential import OAuthCredential
from services.encryption_service import get_encryption_service

logger = logging.getLogger(__name__)

# Create blueprint
gdrive_bp = Blueprint("gdrive", __name__, url_prefix="/api/gdrive")


@gdrive_bp.route("/auth/initiate", methods=["POST"])
def initiate_gdrive_auth() -> Response | tuple[Response, int]:
    """Initiate Google Drive OAuth flow."""
    try:
        # Allow OAuth over HTTP for local development
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

        data = request.get_json()
        task_id = data.get("task_id")  # Unique identifier for this task
        credential_name = data.get("credential_name")  # Name for this credential

        if not task_id:
            return jsonify({"error": "task_id is required"}), 400

        if not credential_name:
            return jsonify({"error": "credential_name is required"}), 400

        # Generate UUID for credential_id
        credential_id = str(uuid.uuid4())

        # Add ingest path to sys.path
        ingest_path = str(Path(__file__).parent.parent.parent / "ingest")
        if ingest_path not in sys.path:
            sys.path.insert(0, ingest_path)

        # Define scopes
        scopes = [
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/drive.metadata.readonly",
        ]

        # Get OAuth app credentials from environment (shared for all users)
        client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")

        if not client_id or not client_secret:
            return (
                jsonify(
                    {
                        "error": "Google OAuth not configured",
                        "details": "GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET environment variables must be set",
                    }
                ),
                500,
            )

        # Build redirect URI from server base URL
        settings = get_settings()
        redirect_uri = f"{settings.server_base_url}/api/gdrive/auth/callback"

        # Create flow from client config (not from file)
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=scopes,
            redirect_uri=redirect_uri,
        )

        # Generate authorization URL
        authorization_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )

        # Store state, task_id, credential_id, and credential_name in session
        session["oauth_state"] = state
        session["oauth_task_id"] = task_id
        session["oauth_credential_id"] = credential_id
        session["oauth_credential_name"] = credential_name

        return jsonify(
            {
                "authorization_url": authorization_url,
                "state": state,
                "credential_id": credential_id,
            }
        )

    except Exception as e:
        logger.error(f"Error initiating Google Drive auth: {e}")
        return jsonify({"error": str(e)}), 500


@gdrive_bp.route("/auth/callback")
def gdrive_auth_callback() -> Response | tuple[Response, int]:
    """Handle Google Drive OAuth callback."""
    try:
        # Allow OAuth over HTTP for local development
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

        # Get state, task_id, credential_id, and credential_name from session
        state = session.get("oauth_state")
        task_id = session.get("oauth_task_id")
        credential_id = session.get("oauth_credential_id")
        credential_name = session.get("oauth_credential_name")

        if not state or not task_id or not credential_id or not credential_name:
            return jsonify({"error": "Invalid session state"}), 400

        # Add ingest path to sys.path
        ingest_path = str(Path(__file__).parent.parent.parent / "ingest")
        if ingest_path not in sys.path:
            sys.path.insert(0, ingest_path)

        # Define scopes
        scopes = [
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/drive.metadata.readonly",
        ]

        # Get OAuth app credentials from environment (shared for all users)
        client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")

        if not client_id or not client_secret:
            return jsonify({"error": "Google OAuth not configured"}), 500

        # Build redirect URI from server base URL
        settings = get_settings()
        redirect_uri = f"{settings.server_base_url}/api/gdrive/auth/callback"

        # Create flow from client config
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=scopes,
            redirect_uri=redirect_uri,
            state=state,
        )

        # Fetch token using authorization response
        authorization_response = request.url
        flow.fetch_token(authorization_response=authorization_response)

        # Get credentials (token)
        credentials = flow.credentials

        # Save encrypted token to database
        encryption_service = get_encryption_service()
        token_json = credentials.to_json()
        encrypted_token = encryption_service.encrypt(token_json)

        # Extract metadata (non-sensitive info including expiry)
        token_data = json.loads(token_json)
        token_metadata = {
            "scopes": token_data.get("scopes", []),
            "token_uri": token_data.get("token_uri"),
            "expiry": token_data.get("expiry"),  # ISO format timestamp
        }

        # Check if this is a refresh or new credential
        is_refresh = session.get("oauth_is_refresh", False)

        # Save to database (create or update)
        with get_db_session() as db_session:
            if is_refresh:
                # Update existing credential
                existing = (
                    db_session.query(OAuthCredential)
                    .filter(OAuthCredential.credential_id == credential_id)
                    .first()
                )
                if existing:
                    existing.encrypted_token = encrypted_token
                    existing.token_metadata = token_metadata
                    logger.info(
                        f"Google Drive token refreshed for credential: {credential_name} ({credential_id})"
                    )
                else:
                    logger.error(
                        f"Refresh failed: credential {credential_id} not found"
                    )
                    return jsonify({"error": "Credential not found"}), 404
            else:
                # Create new credential
                oauth_credential = OAuthCredential(
                    credential_id=credential_id,
                    credential_name=credential_name,
                    provider="google_drive",
                    encrypted_token=encrypted_token,
                    token_metadata=token_metadata,
                )
                db_session.add(oauth_credential)
                logger.info(
                    f"Google Drive token saved (encrypted) for credential: {credential_name} ({credential_id})"
                )

            db_session.commit()

        # Clear session
        session.pop("oauth_state", None)
        session.pop("oauth_task_id", None)
        session.pop("oauth_credential_id", None)
        session.pop("oauth_credential_name", None)
        session.pop("oauth_is_refresh", None)

        # Render success page with auto-close
        return render_template(
            "oauth_success.html",
            credential_name=credential_name,
            credential_id=credential_id,
        )

    except Exception as e:
        logger.error(f"Error handling Google Drive auth callback: {e}")
        return render_template("oauth_error.html", error=str(e)), 500


@gdrive_bp.route("/auth/status/<task_id>")
def check_gdrive_auth_status(task_id: str) -> Response | tuple[Response, int]:
    """Check if Google Drive authentication exists for a task."""
    try:
        token_file = (
            Path(__file__).parent.parent
            / "auth"
            / "gdrive_tokens"
            / f"{task_id}_token.json"
        )

        if token_file.exists():
            # Verify token is valid
            creds = Credentials.from_authorized_user_file(
                str(token_file),
                [
                    "https://www.googleapis.com/auth/drive.readonly",
                    "https://www.googleapis.com/auth/drive.metadata.readonly",
                ],
            )

            return jsonify(
                {
                    "authenticated": True,
                    "token_file": str(token_file),
                    "valid": creds.valid,
                    "expired": creds.expired if hasattr(creds, "expired") else False,
                }
            )
        else:
            return jsonify({"authenticated": False})

    except Exception as e:
        logger.error(f"Error checking Google Drive auth status: {e}")
        return jsonify({"error": str(e)}), 500
