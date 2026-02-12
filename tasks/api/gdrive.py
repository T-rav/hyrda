"""Google Drive OAuth and integration endpoints."""

import html
import json
import logging
import os
import re
import sys
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from config.settings import get_settings
from dependencies.auth import get_current_user
from models.base import get_db_session
from models.oauth_credential import OAuthCredential
from services.encryption_service import get_encryption_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gdrive")


@router.post("/auth/initiate")
async def initiate_gdrive_auth(request: Request):
    try:
        # Allow OAuth over HTTP ONLY in local development (not production)
        if os.getenv("ENVIRONMENT") != "production":
            os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

        data = await request.json()
        task_id = data.get("task_id")  # Unique identifier for this task
        credential_name = data.get("credential_name")  # Name for this credential

        if not task_id:
            raise HTTPException(status_code=400, detail="task_id is required")

        if not credential_name:
            raise HTTPException(status_code=400, detail="credential_name is required")

        # Validate credential_name (prevent buffer overflow, storage DoS, XSS)
        if len(credential_name) > 255:
            raise HTTPException(
                status_code=400, detail="credential_name must be 255 characters or less"
            )

        # Allow alphanumeric, spaces, hyphens, underscores, and dots
        if not re.match(r"^[a-zA-Z0-9 _\-\.]+$", credential_name):
            raise HTTPException(
                status_code=400,
                detail="credential_name contains invalid characters. "
                "Only alphanumeric characters, spaces, hyphens, underscores, and dots are allowed.",
            )

        # Generate UUID for credential_id
        credential_id = str(uuid.uuid4())

        # Add ingest path to sys.path
        ingest_path = str(Path(__file__).parent.parent.parent / "ingest")
        if ingest_path not in sys.path:
            sys.path.insert(0, ingest_path)

        # Define scopes (includes Drive + Sites for website scraping)
        scopes = [
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/drive.metadata.readonly",
            "https://www.googleapis.com/auth/sites.readonly",  # For Google Sites access
        ]

        # Get OAuth app credentials from environment (shared for all users)
        client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")

        if not client_id or not client_secret:
            raise HTTPException(
                status_code=500,
                detail="Google OAuth not configured - GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET environment variables must be set",
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
        request.session["oauth_state"] = state
        request.session["oauth_task_id"] = task_id
        request.session["oauth_credential_id"] = credential_id
        request.session["oauth_credential_name"] = credential_name

        return {
            "authorization_url": authorization_url,
            "state": state,
            "credential_id": credential_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating Google Drive auth: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/auth/callback", response_class=HTMLResponse)
async def gdrive_auth_callback(request: Request):
    try:
        # Allow OAuth over HTTP ONLY in local development (not production)
        if os.getenv("ENVIRONMENT") != "production":
            os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

        # Get state, task_id, credential_id, and credential_name from session
        state = request.session.get("oauth_state")
        task_id = request.session.get("oauth_task_id")
        credential_id = request.session.get("oauth_credential_id")
        credential_name = request.session.get("oauth_credential_name")

        if not state or not task_id or not credential_id or not credential_name:
            raise HTTPException(status_code=400, detail="Invalid session state")

        # Add ingest path to sys.path
        ingest_path = str(Path(__file__).parent.parent.parent / "ingest")
        if ingest_path not in sys.path:
            sys.path.insert(0, ingest_path)

        # Define scopes (includes Drive + Sites for website scraping)
        scopes = [
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/drive.metadata.readonly",
            "https://www.googleapis.com/auth/sites.readonly",  # For Google Sites access
        ]

        # Get OAuth app credentials from environment (shared for all users)
        client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")

        if not client_id or not client_secret:
            raise HTTPException(status_code=500, detail="Google OAuth not configured")

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
        authorization_response = str(request.url)
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
        is_refresh = request.session.get("oauth_is_refresh", False)

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
                    raise HTTPException(status_code=404, detail="Credential not found")
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
        request.session.pop("oauth_state", None)
        request.session.pop("oauth_task_id", None)
        request.session.pop("oauth_credential_id", None)
        request.session.pop("oauth_credential_name", None)
        request.session.pop("oauth_is_refresh", None)

        # Render success page with auto-close
        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Google Drive Authentication Successful</title>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    }}
                    .container {{
                        background: white;
                        padding: 3rem;
                        border-radius: 12px;
                        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
                        text-align: center;
                        max-width: 500px;
                    }}
                    h1 {{
                        color: #2d3748;
                        margin-bottom: 1rem;
                        font-size: 2rem;
                    }}
                    .success-icon {{
                        font-size: 4rem;
                        color: #48bb78;
                        margin-bottom: 1rem;
                    }}
                    p {{
                        color: #4a5568;
                        line-height: 1.6;
                        margin-bottom: 1rem;
                    }}
                    .credential-info {{
                        background: #f7fafc;
                        padding: 1rem;
                        border-radius: 8px;
                        margin: 1rem 0;
                        font-family: monospace;
                    }}
                    .auto-close {{
                        color: #718096;
                        font-size: 0.875rem;
                        margin-top: 1rem;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="success-icon">✓</div>
                    <h1>Authentication Successful!</h1>
                    <p>Your Google Drive credentials have been saved securely.</p>
                    <div class="credential-info">
                        <strong>Credential:</strong> {html.escape(credential_name)}<br>
                        <strong>ID:</strong> {html.escape(credential_id)}
                    </div>
                    <p>You can now use this credential in your Google Drive ingestion tasks.</p>
                    <p class="auto-close">This window will close automatically in 3 seconds...</p>
                </div>
                <script>
                    setTimeout(function() {{
                        window.close();
                    }}, 3000);
                </script>
            </body>
            </html>
            """
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling Google Drive auth callback: {e}")
        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Authentication Error</title>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                    }}
                    .container {{
                        background: white;
                        padding: 3rem;
                        border-radius: 12px;
                        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
                        text-align: center;
                        max-width: 500px;
                    }}
                    h1 {{
                        color: #742a2a;
                        margin-bottom: 1rem;
                        font-size: 2rem;
                    }}
                    .error-icon {{
                        font-size: 4rem;
                        color: #f56565;
                        margin-bottom: 1rem;
                    }}
                    p {{
                        color: #4a5568;
                        line-height: 1.6;
                    }}
                    .error-details {{
                        background: #fff5f5;
                        padding: 1rem;
                        border-radius: 8px;
                        margin: 1rem 0;
                        font-family: monospace;
                        color: #742a2a;
                        font-size: 0.875rem;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="error-icon">✗</div>
                    <h1>Authentication Failed</h1>
                    <p>There was an error during authentication.</p>
                    <div class="error-details">{str(e)}</div>
                    <p>Please try again or contact your administrator.</p>
                </div>
            </body>
            </html>
            """,
            status_code=500,
        )


@router.get("/auth/status/{task_id}")
async def check_gdrive_auth_status(
    request: Request, task_id: str, user: dict = Depends(get_current_user)
):
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

            return {
                "authenticated": True,
                "token_file": str(token_file),
                "valid": creds.valid,
                "expired": creds.expired if hasattr(creds, "expired") else False,
            }
        else:
            return {"authenticated": False}

    except Exception as e:
        logger.error(f"Error checking Google Drive auth status: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
