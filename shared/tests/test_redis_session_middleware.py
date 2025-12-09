"""Tests for Redis session middleware with domain cookie support."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route
from starlette.testclient import TestClient

from shared.middleware.redis_session import RedisSessionMiddleware


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    return redis


@pytest.fixture
def app_with_session_middleware(mock_redis):
    """Create test app with session middleware."""

    async def homepage(request: Request):
        return Response("Hello")

    async def set_session(request: Request):
        request.session["user"] = "testuser"
        return Response("Session set")

    async def get_session(request: Request):
        user = request.session.get("user", "none")
        return Response(f"User: {user}")

    app = Starlette(
        routes=[
            Route("/", homepage),
            Route("/set", set_session),
            Route("/get", get_session),
        ],
        middleware=[
            Middleware(
                RedisSessionMiddleware,
                secret_key="test-secret-key",
                session_cookie="test_session",
                domain="localhost",
            )
        ],
    )

    return app


class TestDomainCookieSupport:
    """Test domain cookie functionality in session middleware."""

    def test_middleware_accepts_domain_parameter(self):
        """Test that middleware accepts domain parameter."""
        middleware = RedisSessionMiddleware(
            app=MagicMock(),
            secret_key="test",
            domain="localhost",
        )

        assert middleware.domain == "localhost"

    def test_middleware_domain_defaults_to_none(self):
        """Test that domain defaults to None if not provided."""
        middleware = RedisSessionMiddleware(
            app=MagicMock(),
            secret_key="test",
        )

        assert middleware.domain is None

    @patch("shared.middleware.redis_session.get_redis_client")
    def test_set_cookie_includes_domain_when_specified(self, mock_get_redis, mock_redis):
        """Test that Set-Cookie header includes Domain when specified."""
        mock_get_redis.return_value = mock_redis

        app = Starlette(
            routes=[
                Route(
                    "/set",
                    lambda request: Response(
                        "OK", headers={"Set-Cookie": "test_session=abc123"}
                    ),
                )
            ],
            middleware=[
                Middleware(
                    RedisSessionMiddleware,
                    secret_key="test-secret-key",
                    session_cookie="test_session",
                    domain="localhost",
                )
            ],
        )

        client = TestClient(app)
        response = client.get("/set")

        # Check Set-Cookie header
        set_cookie = response.headers.get("set-cookie")
        assert set_cookie is not None

        # Should include Domain=localhost
        assert "Domain=localhost" in set_cookie

    @patch("shared.middleware.redis_session.get_redis_client")
    def test_set_cookie_excludes_domain_when_not_specified(
        self, mock_get_redis, mock_redis
    ):
        """Test that Set-Cookie header excludes Domain when not specified."""
        mock_get_redis.return_value = mock_redis

        app = Starlette(
            routes=[
                Route(
                    "/set",
                    lambda request: Response(
                        "OK", headers={"Set-Cookie": "test_session=abc123"}
                    ),
                )
            ],
            middleware=[
                Middleware(
                    RedisSessionMiddleware,
                    secret_key="test-secret-key",
                    session_cookie="test_session",
                    # No domain parameter
                )
            ],
        )

        client = TestClient(app)
        response = client.get("/set")

        # Check Set-Cookie header
        set_cookie = response.headers.get("set-cookie")
        assert set_cookie is not None

        # Should NOT include Domain
        assert "Domain=" not in set_cookie

    @patch("shared.middleware.redis_session.get_redis_client")
    def test_cookie_includes_expected_attributes(self, mock_get_redis, mock_redis):
        """Test that cookie includes all expected attributes."""
        mock_get_redis.return_value = mock_redis

        app = Starlette(
            routes=[
                Route(
                    "/set",
                    lambda request: Response(
                        "OK", headers={"Set-Cookie": "test_session=abc123"}
                    ),
                )
            ],
            middleware=[
                Middleware(
                    RedisSessionMiddleware,
                    secret_key="test-secret-key",
                    session_cookie="test_session",
                    domain="localhost",
                    same_site="lax",
                    https_only=False,
                )
            ],
        )

        client = TestClient(app)
        response = client.get("/set")

        set_cookie = response.headers.get("set-cookie")
        assert set_cookie is not None

        # Should include all attributes
        assert "test_session=" in set_cookie
        assert "Max-Age=" in set_cookie
        assert "Path=/" in set_cookie
        assert "Domain=localhost" in set_cookie
        assert "SameSite=lax" in set_cookie
        assert "HttpOnly" in set_cookie

        # Should NOT include Secure when https_only=False
        assert "Secure" not in set_cookie

    @patch("shared.middleware.redis_session.get_redis_client")
    def test_cookie_includes_secure_when_https_only(self, mock_get_redis, mock_redis):
        """Test that cookie includes Secure flag when https_only=True."""
        mock_get_redis.return_value = mock_redis

        app = Starlette(
            routes=[
                Route(
                    "/set",
                    lambda request: Response(
                        "OK", headers={"Set-Cookie": "test_session=abc123"}
                    ),
                )
            ],
            middleware=[
                Middleware(
                    RedisSessionMiddleware,
                    secret_key="test-secret-key",
                    session_cookie="test_session",
                    domain="localhost",
                    https_only=True,
                )
            ],
        )

        client = TestClient(app)
        response = client.get("/set")

        set_cookie = response.headers.get("set-cookie")
        assert set_cookie is not None

        # Should include Secure when https_only=True
        assert "Secure" in set_cookie
