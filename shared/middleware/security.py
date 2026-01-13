"""Security middleware for HTTPS enforcement and security headers."""

import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

logger = logging.getLogger(__name__)


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce HTTPS in production environments.

    Redirects HTTP requests to HTTPS in production.
    Disabled in development to allow local testing.
    """

    async def dispatch(self, request: Request, call_next):
        """Process request and enforce HTTPS if in production."""
        environment = os.getenv("ENVIRONMENT", "development")

        # Only enforce HTTPS in production
        if environment == "production":
            # Check if request is HTTP (not HTTPS)
            scheme = request.url.scheme
            forwarded_proto = request.headers.get("X-Forwarded-Proto", "")

            # Check actual scheme or proxy header (for load balancers)
            is_https = scheme == "https" or forwarded_proto == "https"

            if not is_https:
                # Redirect to HTTPS
                https_url = str(request.url).replace("http://", "https://", 1)
                logger.info(f"Redirecting HTTP to HTTPS: {https_url}")
                return RedirectResponse(url=https_url, status_code=301)

        # Process request normally
        response = await call_next(request)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses.

    Adds HSTS, CSP, X-Frame-Options, and other security headers.
    """

    async def dispatch(self, request: Request, call_next):
        """Add security headers to response."""
        response: Response = await call_next(request)

        environment = os.getenv("ENVIRONMENT", "development")

        # HSTS (HTTP Strict Transport Security) - only in production
        if environment == "production":
            # Tell browsers to only use HTTPS for 1 year, including subdomains
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # X-Frame-Options - prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # X-Content-Type-Options - prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # X-XSS-Protection - enable browser XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer-Policy - control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Content-Security-Policy - restrict resource loading
        # Note: Adjust CSP based on your application's needs
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "  # Allow inline scripts for now
            "style-src 'self' 'unsafe-inline'; "  # Allow inline styles
            "img-src 'self' data: https:; "  # Allow images from HTTPS
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        )

        # Permissions-Policy (formerly Feature-Policy) - control browser features
        response.headers["Permissions-Policy"] = (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=(), "
            "accelerometer=()"
        )

        return response
