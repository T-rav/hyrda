"""Authentication endpoints for OAuth flow with JWT token generation."""

import logging
import os
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from utils.auth import (
    AuditLogger,
    get_flow,
    get_redirect_uri,
    verify_domain,
    verify_token,
)
from utils.rate_limit import rate_limit

# Import JWT utilities from shared directory
sys.path.insert(0, "/app")  # Add app root to path for shared imports
from shared.utils.jwt_auth import (
    create_access_token,
    create_refresh_token,
    extract_token_from_request,
    refresh_access_token_with_refresh,
    revoke_refresh_token,
    revoke_token,
    store_refresh_token,
)

logger = logging.getLogger(__name__)


def get_original_url(request: Request) -> str:
    """Reconstruct the original URL from forwarded headers (for reverse proxy setups).

    When behind nginx/reverse proxy, request.url shows the internal HTTP URL.
    This function uses X-Forwarded-* headers to reconstruct the original external URL.

    Args:
        request: The FastAPI request object

    Returns:
        The original URL as seen by the client (with https:// if forwarded)
    """
    from urllib.parse import urlunsplit

    # Get forwarded headers (fall back to request values if not present)
    scheme = request.headers.get("X-Forwarded-Proto", request.url.scheme)
    netloc = request.headers.get("X-Forwarded-Host", request.url.netloc)
    path = request.url.path
    query = request.url.query or ""

    # Build URL using urlunsplit to avoid formatted string detection
    # This is internal URL reconstruction for OAuth, not user-facing content
    return urlunsplit((scheme, netloc, path, query, ""))


router = APIRouter(prefix="/auth")


@router.get("/login")
async def auth_login_page():
    """Serve the login page HTML.

    Returns:
        HTML login page with "Sign in with Google" button
    """
    template_path = Path(__file__).parent.parent / "templates" / "login.html"
    if not template_path.exists():
        raise HTTPException(status_code=500, detail="Login template not found")

    return HTMLResponse(content=template_path.read_text())


@router.get("/start")
@rate_limit(max_requests=10, window_seconds=60)
async def auth_start(request: Request, redirect: str | None = None):
    """Initiate OAuth login flow.

    Rate limited to 10 requests per 60 seconds per IP to prevent abuse.

    Args:
        redirect: URL to redirect to after successful login

    Returns:
        Redirect to Google OAuth consent screen
    """
    import secrets

    service_base_url = os.getenv("CONTROL_PLANE_BASE_URL", "http://localhost:6001")
    redirect_uri = get_redirect_uri(service_base_url, "/auth/callback")

    # Generate OAuth state and CSRF token for security
    oauth_state = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)

    request.session["oauth_state"] = oauth_state
    request.session["oauth_csrf"] = csrf_token
    request.session["oauth_redirect"] = redirect or "/"

    flow = get_flow(redirect_uri)
    flow.state = oauth_state

    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="select_account",  # Show account picker, not consent screen every time
    )

    AuditLogger.log_auth_event(
        "login_initiated",
        path=str(request.url),
    )

    return RedirectResponse(url=authorization_url, status_code=302)


@router.get("/callback")
@rate_limit(max_requests=10, window_seconds=60)
async def auth_callback(request: Request):
    """Handle OAuth callback.

    Rate limited to prevent brute force attacks on OAuth flow.
    """
    service_base_url = os.getenv("CONTROL_PLANE_BASE_URL", "http://localhost:6001")
    redirect_uri = get_redirect_uri(service_base_url, "/auth/callback")

    state = request.session.get("oauth_state")
    csrf_token = request.session.get("oauth_csrf")
    redirect_url = request.session.get("oauth_redirect", "/")

    if not state:
        AuditLogger.log_auth_event(
            "callback_failed",
            success=False,
            error="Missing OAuth state - possible session timeout",
        )
        raise HTTPException(status_code=400, detail="Invalid session state")

    if not csrf_token:
        AuditLogger.log_auth_event(
            "callback_failed",
            success=False,
            error="CSRF token missing - potential session fixation attack",
        )
        request.session.clear()
        raise HTTPException(
            status_code=403, detail="Invalid session - please try again"
        )

    try:
        flow = get_flow(redirect_uri)
        # Use original URL from forwarded headers (nginx proxies as HTTP internally)
        authorization_response = get_original_url(request)
        logger.debug(f"OAuth callback URL: {authorization_response}")
        flow.fetch_token(authorization_response=authorization_response)

        credentials = flow.credentials
        idinfo = verify_token(credentials.id_token)
        email = idinfo.get("email")

        if not verify_domain(email):
            AuditLogger.log_auth_event(
                "callback_failed",
                email=email,
                success=False,
                error=f"Email domain not allowed: {email}",
            )
            raise HTTPException(status_code=403, detail="Access restricted")

        from models import User, get_db_session

        is_admin = False
        user_id = None

        with get_db_session() as db_session:
            user = db_session.query(User).filter(User.email == email).first()

            if user:
                # User exists in database
                is_admin = user.is_admin
                user_id = user.slack_user_id
                logger.info(
                    f"User {email} found in database: is_admin={is_admin}, user_id={user_id}"
                )
            else:
                # User not in database - try to sync from Slack
                logger.info(f"User {email} not in database - attempting Slack lookup")

                try:
                    from slack_sdk import WebClient

                    slack_token = os.getenv("SLACK_BOT_TOKEN")
                    if not slack_token:
                        logger.error("SLACK_BOT_TOKEN not configured")
                        raise HTTPException(
                            status_code=403,
                            detail="User not found and Slack integration not configured",
                        )

                    slack_client = WebClient(token=slack_token)

                    response = slack_client.users_lookupByEmail(email=email)

                    if response["ok"] and response.get("user"):
                        slack_user = response["user"]
                        slack_user_id = slack_user["id"]
                        slack_name = slack_user.get("real_name") or slack_user.get(
                            "name"
                        )

                        user_count = db_session.query(User).count()
                        is_first_user = user_count == 0
                        is_admin = is_first_user

                        new_user = User(
                            slack_user_id=slack_user_id,
                            email=email,
                            full_name=slack_name,
                            is_admin=is_admin,
                        )
                        db_session.add(new_user)
                        db_session.commit()

                        user_id = slack_user_id

                        logger.info(
                            f"User {email} found in Slack and created in database: user_id={user_id}, is_admin={is_admin}, first_user={is_first_user}"
                        )
                        AuditLogger.log_auth_event(
                            "user_created_from_slack", email=email, success=True
                        )
                    else:
                        logger.warning(
                            f"User {email} not found in Slack - denying access"
                        )
                        AuditLogger.log_auth_event(
                            "login_denied_not_in_slack",
                            email=email,
                            success=False,
                            error="User not found in Slack workspace",
                        )
                        raise HTTPException(
                            status_code=403,
                            detail="Access denied: User not found in Slack workspace. Please contact your administrator.",
                        )

                except HTTPException:
                    raise
                except Exception as e:
                    logger.error(f"Error looking up user in Slack: {e}", exc_info=True)
                    AuditLogger.log_auth_event(
                        "slack_lookup_failed", email=email, success=False, error=str(e)
                    )
                    raise HTTPException(
                        status_code=403,
                        detail="Unable to verify user access. Please contact your administrator.",
                    )

        user_name = idinfo.get("name")
        user_picture = idinfo.get("picture")

        # Create both access and refresh tokens
        jwt_token = create_access_token(
            user_email=email,
            user_name=user_name,
            user_picture=user_picture,
            additional_claims={"is_admin": is_admin, "user_id": user_id},
        )

        refresh_token = create_refresh_token(user_email=email)
        store_refresh_token(email, refresh_token)

        request.session["user_email"] = email
        request.session["user_info"] = {
            "email": email,
            "name": user_name,
            "picture": user_picture,
        }

        request.session.pop("oauth_state", None)
        request.session.pop("oauth_csrf", None)
        request.session.pop("oauth_redirect", None)

        AuditLogger.log_auth_event(
            "login_success",
            email=email,
        )

        logger.info(f"Redirecting to: {redirect_url}")

        from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

        parsed_url = urlparse(redirect_url)
        is_localhost = parsed_url.hostname in ("localhost", "127.0.0.1")
        current_port = request.url.port or (
            443 if request.url.scheme == "https" else 80
        )
        target_port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)

        if is_localhost and current_port != target_port:
            query_params = parse_qs(parsed_url.query)
            query_params["token"] = [jwt_token]
            new_query = urlencode(query_params, doseq=True)
            redirect_url = urlunparse(
                (
                    parsed_url.scheme,
                    parsed_url.netloc,
                    parsed_url.path,
                    parsed_url.params,
                    new_query,
                    parsed_url.fragment,
                )
            )
            logger.info(
                f"Added token to redirect URL for cross-port auth to {parsed_url.netloc}"
            )

        response = RedirectResponse(url=redirect_url, status_code=302)

        # Determine if we're serving over HTTPS (check forwarded headers for reverse proxy)
        is_secure = (
            request.headers.get("X-Forwarded-Proto", request.url.scheme) == "https"
        )

        # Set access token cookie (short-lived)
        response.set_cookie(
            key="access_token",
            value=jwt_token,
            httponly=True,
            secure=is_secure,
            samesite="lax",
            max_age=900,  # 15 minutes (matches JWT_EXPIRATION_MINUTES)
        )

        # Set refresh token cookie (long-lived)
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=is_secure,
            samesite="lax",
            max_age=604800,  # 7 days (matches REFRESH_TOKEN_DAYS)
        )

        logger.info(f"Set access and refresh cookies for {email}")

        return response

    except Exception as e:
        logger.error(f"OAuth callback error: {e}", exc_info=True)
        AuditLogger.log_auth_event(
            "callback_failed",
            success=False,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail="Authentication failed")


@router.get("/token")
async def get_token(request: Request):
    """Get JWT token for current authenticated user.

    This endpoint allows users to get a JWT token for API access.
    Requires existing session (user must be logged in via OAuth).

    Returns:
        JSON with access_token that can be used in Authorization header

    Example:
        # After logging in via OAuth:
        curl http://localhost:6001/auth/token
        # Returns: {"access_token": "eyJ0eXAi...", "token_type": "bearer"}

        # Use token in subsequent requests:
        curl -H "Authorization: Bearer eyJ0eXAi..." http://localhost:5001/api/jobs
    """
    user_email = request.session.get("user_email")
    user_info = request.session.get("user_info")

    if not user_email or not user_info:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated - please login first at /auth/callback",
        )

    from models import User, get_db_session

    is_admin = False
    user_id = None

    with get_db_session() as db_session:
        user = db_session.query(User).filter(User.email == user_email).first()
        if user:
            is_admin = user.is_admin
            user_id = user.slack_user_id
            logger.info(
                f"User {user_email} found in database: is_admin={is_admin}, user_id={user_id}"
            )
        else:
            logger.warning(
                f"User {user_email} not found in database - creating JWT without admin privileges"
            )

    # Create both access and refresh tokens
    jwt_token = create_access_token(
        user_email=user_email,
        user_name=user_info.get("name"),
        user_picture=user_info.get("picture"),
        additional_claims={"is_admin": is_admin, "user_id": user_id},
    )

    refresh_token = create_refresh_token(user_email=user_email)
    store_refresh_token(user_email, refresh_token)

    logger.info(f"Generated JWT tokens for {user_email} (is_admin={is_admin})")

    return {
        "access_token": jwt_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 900,  # 15 minutes in seconds
    }


@router.post("/token/refresh")
async def refresh_token_endpoint(request: Request):
    """Refresh an expired access token using a refresh token.

    This endpoint exchanges a valid refresh token for a new access token.
    The refresh token can be provided either as a cookie or in the request body.

    OAuth 2.0 Refresh Token Flow (RFC 6749):
    - Client sends refresh token
    - Server validates refresh token
    - Server issues new access token (and optionally rotates refresh token)
    - Client uses new access token for API requests

    Returns:
        JSON with new access_token and optionally new refresh_token

    Example:
        # With cookie (automatic):
        curl -X POST http://localhost:6001/auth/token/refresh --cookie "refresh_token=eyJ..."

        # With JSON body:
        curl -X POST http://localhost:6001/auth/token/refresh \
             -H "Content-Type: application/json" \
             -d '{"refresh_token": "eyJ..."}'

        # Returns:
        {
            "access_token": "eyJ...",
            "refresh_token": "eyJ...",  # New refresh token (rotated)
            "token_type": "bearer",
            "expires_in": 900
        }
    """
    # Try to get refresh token from cookie first, then from body
    refresh_token = request.cookies.get("refresh_token")

    if not refresh_token:
        try:
            body = await request.json()
            refresh_token = body.get("refresh_token")
        except Exception:
            pass

    if not refresh_token:
        raise HTTPException(
            status_code=401,
            detail="No refresh token provided. Please login again at /auth/login",
        )

    try:
        # Exchange refresh token for new access token (with rotation)
        new_access_token, new_refresh_token = refresh_access_token_with_refresh(
            refresh_token, rotate_refresh=True
        )

        logger.info("Successfully refreshed access token")

        # Return new tokens
        response_data = {
            "access_token": new_access_token,
            "token_type": "bearer",
            "expires_in": 900,  # 15 minutes
        }

        if new_refresh_token:
            response_data["refresh_token"] = new_refresh_token

        # If client accepts JSON, return tokens in body
        # If browser, set cookies and redirect
        accept_header = request.headers.get("accept", "")
        is_browser = "text/html" in accept_header

        if is_browser:
            # Browser - set cookies and redirect to referrer or home
            from fastapi.responses import JSONResponse

            response = JSONResponse(response_data)

            # Determine if we're serving over HTTPS (check forwarded headers for reverse proxy)
            is_secure = (
                request.headers.get("X-Forwarded-Proto", request.url.scheme) == "https"
            )

            # Set new access token cookie
            response.set_cookie(
                key="access_token",
                value=new_access_token,
                httponly=True,
                secure=is_secure,
                samesite="lax",
                max_age=900,  # 15 minutes
            )

            # Set new refresh token cookie if rotated
            if new_refresh_token:
                response.set_cookie(
                    key="refresh_token",
                    value=new_refresh_token,
                    httponly=True,
                    secure=is_secure,
                    samesite="lax",
                    max_age=604800,  # 7 days
                )

            return response

        # API client - return JSON
        return response_data

    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        AuditLogger.log_auth_event(
            "token_refresh_failed",
            success=False,
            error=str(e),
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired refresh token. Please login again at /auth/login",
        )


@router.post("/logout")
async def logout(request: Request):
    """Handle logout and revoke JWT token.

    Extracts JWT token from cookie or Authorization header,
    revokes it (adds to Redis blacklist), clears session, and removes cookie.

    Returns:
        JSON response with logout status and token revocation status
    """
    email = request.session.get("user_email")

    # Revoke access token
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        token = extract_token_from_request(auth_header)

    revoked = False
    if token:
        revoked = revoke_token(token)
        if revoked:
            logger.info(f"Revoked access token for {email}")
        else:
            logger.warning(
                f"Access token revocation failed for {email} (Redis unavailable?)"
            )

    # Revoke refresh token
    refresh_revoked = False
    if email:
        refresh_revoked = revoke_refresh_token(email)
        if refresh_revoked:
            logger.info(f"Revoked refresh token for {email}")
        else:
            logger.warning(
                f"Refresh token revocation failed for {email} (Redis unavailable?)"
            )

    request.session.clear()

    AuditLogger.log_auth_event(
        "logout",
        email=email,
    )

    response = RedirectResponse(url="/auth/logged-out", status_code=302)

    # Delete both cookies
    response.delete_cookie(
        key="access_token",
        path="/",
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        key="refresh_token",
        path="/",
        httponly=True,
        samesite="lax",
    )

    return response


@router.get("/logged-out")
async def auth_logged_out():
    """Serve the logout success page.

    Returns:
        HTML page confirming successful logout
    """
    template_path = Path(__file__).parent.parent / "templates" / "logout.html"
    if not template_path.exists():
        raise HTTPException(status_code=500, detail="Logout template not found")

    return HTMLResponse(content=template_path.read_text())
