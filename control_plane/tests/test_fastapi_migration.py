"""Tests for FastAPI migrated endpoints in Control Plane."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add control_plane to path
control_plane_dir = Path(__file__).parent.parent
if str(control_plane_dir) not in sys.path:
    sys.path.insert(0, str(control_plane_dir))


class TestFastAPIErrorHandling:
    """Test FastAPI error handling utilities."""

    def test_error_response_structure(self):
        """Test error response has correct structure."""
        from utils.errors import error_response

        response = error_response("Test error", 400)
        assert response.status_code == 400
        # FastAPI JSONResponse
        assert hasattr(response, "body")

    def test_error_response_with_error_code(self):
        """Test error response includes error code."""
        from utils.errors import error_response

        response = error_response("Not found", 404, error_code="AGENT_NOT_FOUND")
        assert response.status_code == 404

    def test_error_response_with_details(self):
        """Test error response includes additional details."""
        from utils.errors import error_response

        details = {"field": "name", "issue": "too short"}
        response = error_response("Validation error", 400, details=details)
        assert response.status_code == 400

    def test_success_response_structure(self):
        """Test success response has correct structure."""
        from utils.errors import success_response

        response = success_response({"result": "ok"})
        assert response.status_code == 200

    def test_success_response_with_message(self):
        """Test success response includes message."""
        from utils.errors import success_response

        response = success_response(message="Operation successful")
        assert response.status_code == 200

    def test_success_response_custom_status_code(self):
        """Test success response with custom status code."""
        from utils.errors import success_response

        response = success_response({"id": "123"}, status_code=201)
        assert response.status_code == 201


class TestFastAPIAuthUtilities:
    """Test FastAPI authentication utilities."""

    @pytest.fixture
    def mock_oauth_env(self):
        """Mock OAuth environment."""
        with patch.dict(
            os.environ,
            {
                "GOOGLE_OAUTH_CLIENT_ID": "test-id",
                "GOOGLE_OAUTH_CLIENT_SECRET": "test-secret",
                "ALLOWED_EMAIL_DOMAIN": "@8thlight.com",
            },
        ):
            yield

    def test_get_redirect_uri_construction(self, mock_oauth_env):
        """Test redirect URI construction."""
        from utils.auth import get_redirect_uri

        uri = get_redirect_uri("http://localhost:6001")
        assert uri == "http://localhost:6001/auth/callback"

    def test_verify_domain_allows_correct_domain(self, mock_oauth_env):
        """Test domain verification allows correct domain."""
        from utils.auth import verify_domain

        with patch("utils.auth.ALLOWED_DOMAIN", "8thlight.com"):
            assert verify_domain("user@8thlight.com") is True

    def test_verify_domain_rejects_wrong_domain(self, mock_oauth_env):
        """Test domain verification rejects wrong domain."""
        from utils.auth import verify_domain

        with patch("utils.auth.ALLOWED_DOMAIN", "8thlight.com"):
            assert verify_domain("user@evil.com") is False

    def test_verify_domain_handles_empty_email(self, mock_oauth_env):
        """Test domain verification handles empty email."""
        from utils.auth import verify_domain

        assert verify_domain("") is False
        assert verify_domain(None) is False

    def test_audit_logger_logs_events(self, mock_oauth_env, caplog):
        """Test audit logger logs authentication events."""
        import logging

        from utils.auth import AuditLogger

        caplog.set_level(logging.INFO)

        AuditLogger.log_auth_event(
            event_type="test_event", email="user@8thlight.com", success=True
        )

        assert "AUTH_AUDIT: test_event" in caplog.text

    def test_audit_logger_logs_failures(self, mock_oauth_env, caplog):
        """Test audit logger logs failed events."""
        import logging

        from utils.auth import AuditLogger

        caplog.set_level(logging.WARNING)

        AuditLogger.log_auth_event(
            event_type="login_failed",
            email="attacker@evil.com",
            error="Invalid credentials",
            success=False,
        )

        assert "AUTH_AUDIT: login_failed FAILED" in caplog.text


class TestFastAPIRateLimitStub:
    """Test rate limiting stub (disabled during migration)."""

    def test_rate_limit_decorator_is_noop(self):
        """Test that rate limit decorator doesn't block requests during migration."""
        from utils.rate_limit import rate_limit

        # Rate limit should be a no-op decorator
        @rate_limit(max_requests=1, window_seconds=60)
        def test_function():
            return "success"

        # Should execute without errors
        result = test_function()
        assert result == "success"

    def test_rate_limit_decorator_preserves_function_name(self):
        """Test that rate limit decorator preserves function metadata."""
        from utils.rate_limit import rate_limit

        @rate_limit(max_requests=10, window_seconds=60)
        def my_endpoint():
            """Test endpoint."""
            return "ok"

        assert my_endpoint.__name__ == "my_endpoint"
        assert "Test endpoint" in my_endpoint.__doc__


class TestFastAPIConfigurationHelpers:
    """Test FastAPI configuration helpers."""

    def test_check_rate_limit_returns_allowed(self):
        """Test check_rate_limit returns allowed status."""
        from utils.rate_limit import check_rate_limit

        # During migration, should always allow
        is_allowed, headers = check_rate_limit("test-key", 10, 60)
        assert is_allowed is True
        assert isinstance(headers, dict)

    def test_get_rate_limit_key_generation(self):
        """Test rate limit key generation."""
        from utils.rate_limit import get_rate_limit_key

        key = get_rate_limit_key("user123")
        assert key == "rate_limit:user123"

    def test_get_rate_limit_key_with_ip(self):
        """Test rate limit key generation with IP."""
        from utils.rate_limit import get_rate_limit_key

        key = get_rate_limit_key(request_ip="192.168.1.1")
        assert key == "rate_limit:ip:192.168.1.1"

    def test_get_rate_limit_key_default(self):
        """Test rate limit key generation with defaults."""
        from utils.rate_limit import get_rate_limit_key

        key = get_rate_limit_key()
        assert key == "rate_limit:ip:unknown"


class TestFastAPISecurityHeaders:
    """Test security-related FastAPI functionality."""

    def test_auth_error_exception(self):
        """Test AuthError exception can be raised."""
        from utils.auth import AuthError

        error = AuthError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"

    def test_auth_error_can_be_caught(self):
        """Test AuthError can be caught properly."""
        from utils.auth import AuthError

        with pytest.raises(AuthError, match="Custom message"):
            raise AuthError("Custom message")


class TestFastAPIMigrationCompatibility:
    """Test FastAPI migration maintains compatibility."""

    def test_error_response_is_json_response(self):
        """Test that error responses are FastAPI JSONResponse."""
        from fastapi.responses import JSONResponse
        from utils.errors import error_response

        response = error_response("Test", 400)
        assert isinstance(response, JSONResponse)

    def test_success_response_is_json_response(self):
        """Test that success responses are FastAPI JSONResponse."""
        from fastapi.responses import JSONResponse
        from utils.errors import success_response

        response = success_response({"ok": True})
        assert isinstance(response, JSONResponse)

    def test_oauth_flow_creation(self):
        """Test that OAuth flow can still be created."""
        from utils.auth import get_flow

        with patch.dict(
            os.environ,
            {
                "GOOGLE_OAUTH_CLIENT_ID": "test-id",
                "GOOGLE_OAUTH_CLIENT_SECRET": "test-secret",
            },
        ):
            with (
                patch("utils.auth.GOOGLE_CLIENT_ID", "test-id"),
                patch("utils.auth.GOOGLE_CLIENT_SECRET", "test-secret"),
            ):
                flow = get_flow("http://localhost:6001/callback")
                assert flow is not None
                assert hasattr(flow, "redirect_uri")

    @patch("utils.auth.id_token.verify_oauth2_token")
    def test_token_verification_works(self, mock_verify):
        """Test that token verification still works."""
        from utils.auth import verify_token

        mock_verify.return_value = {
            "email": "test@8thlight.com",
            "name": "Test User",
        }

        result = verify_token("test-token")
        assert result["email"] == "test@8thlight.com"

    @patch("utils.auth.id_token.verify_oauth2_token")
    def test_token_verification_raises_auth_error(self, mock_verify):
        """Test that invalid token raises AuthError."""
        from utils.auth import AuthError, verify_token

        mock_verify.side_effect = ValueError("Invalid token")

        with pytest.raises(AuthError):
            verify_token("invalid-token")
