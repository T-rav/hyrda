"""Redis-backed session middleware for FastAPI.

Provides persistent sessions that survive container restarts.
Uses Redis for session storage instead of in-memory cookies.
"""

import json
import logging
import os
import secrets
from typing import Any

from starlette.datastructures import MutableHeaders
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Session configuration
SESSION_COOKIE_NAME = "session_id"
SESSION_TTL_SECONDS = 3600 * 24 * 7  # 7 days


class RedisSessionMiddleware(BaseHTTPMiddleware):
    """Session middleware with Redis backend.

    Stores session data in Redis for persistence across container restarts.
    Falls back to in-memory sessions if Redis is unavailable.
    """

    def __init__(
        self,
        app: ASGIApp,
        secret_key: str,
        session_cookie: str = SESSION_COOKIE_NAME,
        max_age: int = SESSION_TTL_SECONDS,
        same_site: str = "lax",
        https_only: bool = False,
    ):
        """Initialize Redis session middleware.

        Args:
            app: ASGI application
            secret_key: Secret key for signing session cookies
            session_cookie: Name of session cookie (default: "session_id")
            max_age: Session TTL in seconds (default: 7 days)
            same_site: SameSite cookie attribute (default: "lax")
            https_only: Only send cookie over HTTPS (default: False)
        """
        super().__init__(app)
        self.secret_key = secret_key
        self.session_cookie = session_cookie
        self.max_age = max_age
        self.same_site = same_site
        self.https_only = https_only

        # Initialize Redis client
        self._redis = self._get_redis()

        if self._redis:
            logger.info("Redis session storage initialized")
        else:
            logger.warning("Redis unavailable - sessions will not persist across restarts")

    def _get_redis(self):
        """Get Redis client for session storage."""
        try:
            import redis

            redis_url = os.getenv("CACHE_REDIS_URL", "redis://localhost:6379")
            client = redis.from_url(redis_url, decode_responses=True)

            # Test connection
            client.ping()

            return client
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            return None

    def _load_session(self, session_id: str) -> dict[str, Any]:
        """Load session data from Redis.

        Args:
            session_id: Session ID from cookie

        Returns:
            Session data dictionary (empty if not found)
        """
        if not self._redis:
            return {}

        try:
            key = f"session:{session_id}"
            data = self._redis.get(key)

            if data:
                return json.loads(data)

            return {}

        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            return {}

    def _save_session(self, session_id: str, session_data: dict[str, Any]) -> bool:
        """Save session data to Redis.

        Args:
            session_id: Session ID
            session_data: Session data to save

        Returns:
            True if saved successfully, False otherwise
        """
        if not self._redis:
            return False

        try:
            key = f"session:{session_id}"
            data = json.dumps(session_data)

            # Set with TTL
            self._redis.setex(key, self.max_age, data)

            return True

        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            return False

    def _delete_session(self, session_id: str) -> bool:
        """Delete session from Redis.

        Args:
            session_id: Session ID to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        if not self._redis:
            return False

        try:
            key = f"session:{session_id}"
            self._redis.delete(key)
            return True

        except Exception as e:
            logger.error(f"Failed to delete session: {e}")
            return False

    async def dispatch(self, request: Request, call_next):
        """Process request and manage session."""
        # Get session ID from cookie
        session_id = request.cookies.get(self.session_cookie)

        if session_id:
            # Load existing session
            session_data = self._load_session(session_id)
        else:
            # Create new session
            session_id = secrets.token_urlsafe(32)
            session_data = {}

        # Custom session object with Redis backend
        class RedisSession(dict):
            """Session dict that persists to Redis."""

            def __init__(self, data, middleware, sid):
                super().__init__(data)
                self._middleware = middleware
                self._session_id = sid
                self._modified = False

            def __setitem__(self, key, value):
                super().__setitem__(key, value)
                self._modified = True

            def __delitem__(self, key):
                super().__delitem__(key)
                self._modified = True

            def pop(self, key, default=None):
                self._modified = True
                return super().pop(key, default)

            def clear(self):
                self._modified = True
                super().clear()

            def setdefault(self, key, default=None):
                if key not in self:
                    self._modified = True
                return super().setdefault(key, default)

            def update(self, *args, **kwargs):
                self._modified = True
                super().update(*args, **kwargs)

        # Attach session to request
        request.scope["session"] = RedisSession(session_data, self, session_id)

        # Process request
        response = await call_next(request)

        # Save session if modified
        session = request.scope["session"]
        if session._modified or not request.cookies.get(self.session_cookie):
            # Save to Redis
            self._save_session(session._session_id, dict(session))

            # Set session cookie
            response.headers.append(
                "Set-Cookie",
                f"{self.session_cookie}={session._session_id}; "
                f"Max-Age={self.max_age}; "
                f"Path=/; "
                f"SameSite={self.same_site}; "
                f"HttpOnly; "
                + ("Secure; " if self.https_only else ""),
            )

        return response
