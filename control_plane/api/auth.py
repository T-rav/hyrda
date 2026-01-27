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
    extract_token_from_request,
    revoke_token,
)

logger = logging.getLogger(__name__)

# Create router
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

    # Store state in session
    request.session["oauth_state"] = oauth_state
    request.session["oauth_csrf"] = csrf_token
    request.session["oauth_redirect"] = redirect or "/"

    # Create OAuth flow
    flow = get_flow(redirect_uri)
    flow.state = oauth_state

    # Get authorization URL
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

    # Get state from session
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
        # Create OAuth flow
        flow = get_flow(redirect_uri)
        flow.fetch_token(authorization_response=str(request.url))

        # Get credentials and verify
        credentials = flow.credentials
        idinfo = verify_token(credentials.id_token)
        email = idinfo.get("email")

        # Verify domain
        if not verify_domain(email):
            AuditLogger.log_auth_event(
                "callback_failed",
                email=email,
                success=False,
                error=f"Email domain not allowed: {email}",
            )
            raise HTTPException(status_code=403, detail="Access restricted")

        # Look up user in database to get admin status and user_id
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
                            detail="User not found and Slack integration not configured"
                        )

                    slack_client = WebClient(token=slack_token)

                    # Look up user in Slack by email
                    response = slack_client.users_lookupByEmail(email=email)

                    if response["ok"] and response.get("user"):
                        slack_user = response["user"]
                        slack_user_id = slack_user["id"]
                        slack_name = slack_user.get("real_name") or slack_user.get("name")

                        # Check if this is the first user (bootstrap admin)
                        user_count = db_session.query(User).count()
                        is_first_user = user_count == 0
                        is_admin = is_first_user  # First user becomes admin

                        # Create user in database
                        new_user = User(
                            slack_user_id=slack_user_id,
                            email=email,
                            full_name=slack_name,
                            is_admin=is_admin
                        )
                        db_session.add(new_user)
                        db_session.commit()

                        user_id = slack_user_id

                        logger.info(
                            f"User {email} found in Slack and created in database: user_id={user_id}, is_admin={is_admin}, first_user={is_first_user}"
                        )
                        AuditLogger.log_auth_event(
                            "user_created_from_slack",
                            email=email,
                            success=True
                        )
                    else:
                        # User not found in Slack - deny access
                        logger.warning(f"User {email} not found in Slack - denying access")
                        AuditLogger.log_auth_event(
                            "login_denied_not_in_slack",
                            email=email,
                            success=False,
                            error="User not found in Slack workspace"
                        )
                        raise HTTPException(
                            status_code=403,
                            detail="Access denied: User not found in Slack workspace. Please contact your administrator."
                        )

                except HTTPException:
                    raise
                except Exception as e:
                    logger.error(f"Error looking up user in Slack: {e}", exc_info=True)
                    AuditLogger.log_auth_event(
                        "slack_lookup_failed",
                        email=email,
                        success=False,
                        error=str(e)
                    )
                    raise HTTPException(
                        status_code=403,
                        detail="Unable to verify user access. Please contact your administrator."
                    )

        # Generate JWT token with is_admin and user_id
        user_name = idinfo.get("name")
        user_picture = idinfo.get("picture")
        jwt_token = create_access_token(
            user_email=email,
            user_name=user_name,
            user_picture=user_picture,
            additional_claims={"is_admin": is_admin, "user_id": user_id},
        )

        # Store user info in session (for backward compatibility)
        request.session["user_email"] = email
        request.session["user_info"] = {
            "email": email,
            "name": user_name,
            "picture": user_picture,
        }

        # Clear OAuth state
        request.session.pop("oauth_state", None)
        request.session.pop("oauth_csrf", None)
        request.session.pop("oauth_redirect", None)

        AuditLogger.log_auth_event(
            "login_success",
            email=email,
        )

        # Create response with JWT token as HTTP-only cookie
        logger.info(f"Redirecting to: {redirect_url}")

        # Add JWT token to redirect URL if redirecting to a different port (e.g., tasks service)
        # Browsers don't share cookies across different ports, so we pass the token in URL
        from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

        parsed_url = urlparse(redirect_url)
        # Check if we need to pass token in URL (for cross-port/domain redirects)
        # We allow this for localhost/127.0.0.1 on different ports
        is_localhost = parsed_url.hostname in ('localhost', '127.0.0.1')
        current_port = request.url.port or (443 if request.url.scheme == 'https' else 80)
        target_port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)

        if is_localhost and current_port != target_port:
            # Redirecting to another service on localhost - add token as query param
            query_params = parse_qs(parsed_url.query)
            query_params['token'] = [jwt_token]
            new_query = urlencode(query_params, doseq=True)
            redirect_url = urlunparse((
                parsed_url.scheme,
                parsed_url.netloc,
                parsed_url.path,
                parsed_url.params,
                new_query,
                parsed_url.fragment
            ))
            logger.info(f"Added token to redirect URL for cross-port auth to {parsed_url.netloc}")

        response = RedirectResponse(url=redirect_url, status_code=302)
        response.set_cookie(
            key="access_token",
            value=jwt_token,
            httponly=True,  # Prevent XSS attacks
            secure=False,  # Allow over HTTP for local dev
            samesite="lax",  # CSRF protection
            max_age=86400,  # 24 hours (matches JWT expiration)
        )
        logger.info(f"Set cookie for {email}")

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
    # Check if user is authenticated via session
    user_email = request.session.get("user_email")
    user_info = request.session.get("user_info")

    if not user_email or not user_info:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated - please login first at /auth/callback",
        )

    # Look up user in database to get admin status and user_id
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

    # Generate JWT token with is_admin and user_id
    jwt_token = create_access_token(
        user_email=user_email,
        user_name=user_info.get("name"),
        user_picture=user_info.get("picture"),
        additional_claims={"is_admin": is_admin, "user_id": user_id},
    )

    logger.info(f"Generated JWT token for {user_email} (is_admin={is_admin})")

    return {
        "access_token": jwt_token,
        "token_type": "bearer",
        "expires_in": 86400,  # 24 hours in seconds
    }


@router.post("/logout")
async def logout(request: Request):
    """Handle logout and revoke JWT token.

    Extracts JWT token from cookie or Authorization header,
    revokes it (adds to Redis blacklist), clears session, and removes cookie.

    Returns:
        JSON response with logout status and token revocation status
    """
    email = request.session.get("user_email")

    # Try to extract and revoke JWT token
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        token = extract_token_from_request(auth_header)

    revoked = False
    if token:
        revoked = revoke_token(token)
        if revoked:
            logger.info(f"Revoked JWT token for {email}")
        else:
            logger.warning(f"Token revocation failed for {email} (Redis unavailable?)")

    # Clear session
    request.session.clear()

    AuditLogger.log_auth_event(
        "logout",
        email=email,
    )

    # Redirect to logout success page with cookie cleared
    response = RedirectResponse(url="/auth/logged-out", status_code=302)
    # Must match the parameters used when setting the cookie
    response.delete_cookie(
        key="access_token",
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
