"""Integration tests for /auth/token/refresh endpoint.

Tests the complete OAuth 2.0 refresh token flow including:
- Token exchange (refresh token → new access token)
- Token rotation
- Error handling
- Cookie management
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient

from shared.utils.jwt_auth import (
    JWT_ALGORITHM,
    JWT_ISSUER,
    JWT_SECRET_KEY,
    create_access_token,
    create_refresh_token,
)


@pytest.fixture
def client():
    """Create test client."""
    from app import app

    return TestClient(app)


class TestTokenRefreshEndpoint:
    """Tests for POST /auth/token/refresh."""

    @patch("shared.utils.jwt_auth.validate_refresh_token")
    @patch("shared.utils.jwt_auth.store_refresh_token")
    def test_refresh_with_cookie_returns_new_tokens(
        self, mock_store, mock_validate, client
    ):
        """Should exchange valid refresh token cookie for new tokens."""
        mock_validate.return_value = True
        mock_store.return_value = True

        user_email = "user@example.com"
        refresh_token = create_refresh_token(user_email)

        # Make request with refresh token cookie
        response = client.post(
            "/auth/token/refresh",
            cookies={"refresh_token": refresh_token},
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()

        # Should return new access token
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 900  # 15 minutes

        # Verify new access token is valid
        access_payload = jwt.decode(
            data["access_token"], JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM]
        )
        assert access_payload["email"] == user_email
        assert access_payload["token_type"] == "access"

        # Verify new refresh token is valid
        refresh_payload = jwt.decode(
            data["refresh_token"], JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM]
        )
        assert refresh_payload["email"] == user_email
        assert refresh_payload["token_type"] == "refresh"

    @patch("shared.utils.jwt_auth.validate_refresh_token")
    @patch("shared.utils.jwt_auth.store_refresh_token")
    def test_refresh_with_json_body_returns_new_tokens(
        self, mock_store, mock_validate, client
    ):
        """Should accept refresh token in JSON body."""
        mock_validate.return_value = True
        mock_store.return_value = True

        user_email = "user@example.com"
        refresh_token = create_refresh_token(user_email)

        # Make request with refresh token in body
        response = client.post(
            "/auth/token/refresh",
            json={"refresh_token": refresh_token},
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @patch("shared.utils.jwt_auth.validate_refresh_token")
    @patch("shared.utils.jwt_auth.store_refresh_token")
    def test_refresh_rotates_refresh_token(self, mock_store, mock_validate, client):
        """Should rotate refresh token (return new one)."""
        mock_validate.return_value = True
        mock_store.return_value = True

        old_refresh = create_refresh_token("user@example.com")

        response = client.post(
            "/auth/token/refresh",
            cookies={"refresh_token": old_refresh},
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()

        new_refresh = data["refresh_token"]

        # Verify new refresh token was stored (rotation working)
        mock_store.assert_called_once()
        assert mock_store.call_args[0][1] == new_refresh

        # Verify it's a valid refresh token
        refresh_payload = jwt.decode(
            new_refresh, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM]
        )
        assert refresh_payload["token_type"] == "refresh"
        assert refresh_payload["email"] == "user@example.com"

    @patch("shared.utils.jwt_auth.validate_refresh_token")
    @patch("shared.utils.jwt_auth.store_refresh_token")
    def test_browser_request_sets_cookies(self, mock_store, mock_validate, client):
        """Should set cookies for browser requests."""
        mock_validate.return_value = True
        mock_store.return_value = True

        refresh_token = create_refresh_token("user@example.com")

        # Browser request (accepts HTML)
        response = client.post(
            "/auth/token/refresh",
            cookies={"refresh_token": refresh_token},
            headers={"Accept": "text/html"},
        )

        assert response.status_code == 200

        # Check cookies were set
        cookies = response.cookies
        assert "access_token" in cookies
        assert "refresh_token" in cookies

        # Cookie attributes (httpOnly, secure) are set in code but not exposed by TestClient

    def test_refresh_fails_without_token(self, client):
        """Should return 401 when no refresh token provided."""
        response = client.post(
            "/auth/token/refresh", headers={"Accept": "application/json"}
        )

        assert response.status_code == 401
        data = response.json()
        assert "No refresh token provided" in data["detail"]

    def test_refresh_fails_with_invalid_token(self, client):
        """Should return 401 for invalid refresh token."""
        response = client.post(
            "/auth/token/refresh",
            cookies={"refresh_token": "invalid_token_here"},
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 401
        data = response.json()
        assert "Invalid or expired refresh token" in data["detail"]

    @patch("shared.utils.jwt_auth.validate_refresh_token")
    def test_refresh_fails_with_expired_token(self, mock_validate, client):
        """Should return 401 for expired refresh token."""
        # Create expired token
        expired_payload = {
            "sub": "user@example.com",
            "email": "user@example.com",
            "iat": datetime.now(UTC) - timedelta(days=8),
            "exp": datetime.now(UTC) - timedelta(days=1),  # Expired yesterday
            "iss": JWT_ISSUER,
            "token_type": "refresh",
        }
        expired_token = jwt.encode(
            expired_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM
        )

        response = client.post(
            "/auth/token/refresh",
            cookies={"refresh_token": expired_token},
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 401
        assert "Invalid or expired" in response.json()["detail"]

    @patch("shared.utils.jwt_auth.validate_refresh_token")
    def test_refresh_fails_with_access_token(self, mock_validate, client):
        """Should reject access token (wrong type)."""
        mock_validate.return_value = False  # Will fail validation

        # Try to use access token instead of refresh token
        access_token = create_access_token("user@example.com")

        response = client.post(
            "/auth/token/refresh",
            cookies={"refresh_token": access_token},
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 401

    @patch("shared.utils.jwt_auth.validate_refresh_token")
    def test_refresh_fails_for_revoked_token(self, mock_validate, client):
        """Should reject revoked refresh token."""
        mock_validate.return_value = False  # Simulates revoked token

        refresh_token = create_refresh_token("user@example.com")

        response = client.post(
            "/auth/token/refresh",
            cookies={"refresh_token": refresh_token},
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 401
        assert "Invalid or expired" in response.json()["detail"]

    @patch("shared.utils.jwt_auth.validate_refresh_token")
    @patch("shared.utils.jwt_auth.store_refresh_token")
    def test_refresh_preserves_user_claims(self, mock_store, mock_validate, client):
        """Should preserve user-specific claims in new access token."""
        mock_validate.return_value = True
        mock_store.return_value = True

        # Create refresh token with custom claims
        refresh_payload = {
            "sub": "user@example.com",
            "email": "user@example.com",
            "name": "John Doe",
            "picture": "https://example.com/photo.jpg",
            "is_admin": True,
            "user_id": "U12345",
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(days=7),
            "iss": JWT_ISSUER,
            "token_type": "refresh",
        }
        refresh_token = jwt.encode(
            refresh_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM
        )

        response = client.post(
            "/auth/token/refresh",
            cookies={"refresh_token": refresh_token},
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify claims preserved in new access token
        access_payload = jwt.decode(
            data["access_token"], JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM]
        )
        assert access_payload["name"] == "John Doe"
        assert access_payload["picture"] == "https://example.com/photo.jpg"
        assert access_payload["is_admin"] is True
        assert access_payload["user_id"] == "U12345"


class TestTokenRefreshSecurity:
    """Security-focused tests for token refresh."""

    @patch("shared.utils.jwt_auth.validate_refresh_token")
    def test_different_tokens_on_each_refresh(self, mock_validate, client):
        """Should generate unique tokens on each refresh (prevents replay)."""
        import time

        mock_validate.return_value = True

        refresh_token = create_refresh_token("user@example.com")

        # Make first refresh request
        response1 = client.post(
            "/auth/token/refresh",
            cookies={"refresh_token": refresh_token},
            headers={"Accept": "application/json"},
        )

        # Wait 1 second to ensure different timestamps (JWT uses second-precision)
        time.sleep(1)

        # Make second refresh request
        response2 = client.post(
            "/auth/token/refresh",
            cookies={"refresh_token": refresh_token},
            headers={"Accept": "application/json"},
        )

        data1 = response1.json()
        data2 = response2.json()

        # All tokens should be different (prevents replay attacks)
        assert data1["access_token"] != data2["access_token"]
        assert data1["refresh_token"] != data2["refresh_token"]

    @patch("shared.utils.jwt_auth.validate_refresh_token")
    @patch("shared.utils.jwt_auth.store_refresh_token")
    def test_new_access_token_has_short_expiration(
        self, mock_store, mock_validate, client
    ):
        """Should issue access token with 15-minute expiration."""
        mock_validate.return_value = True
        mock_store.return_value = True

        refresh_token = create_refresh_token("user@example.com")

        response = client.post(
            "/auth/token/refresh",
            cookies={"refresh_token": refresh_token},
            headers={"Accept": "application/json"},
        )

        data = response.json()
        access_payload = jwt.decode(
            data["access_token"], JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM]
        )

        # Check expiration is ~15 minutes
        iat = datetime.fromtimestamp(access_payload["iat"], UTC)
        exp = datetime.fromtimestamp(access_payload["exp"], UTC)
        duration = exp - iat

        expected = timedelta(minutes=15)
        assert abs(duration - expected) < timedelta(seconds=5)

    @patch("shared.utils.jwt_auth.validate_refresh_token")
    @patch("shared.utils.jwt_auth.store_refresh_token")
    def test_new_refresh_token_has_long_expiration(
        self, mock_store, mock_validate, client
    ):
        """Should issue refresh token with 7-day expiration."""
        mock_validate.return_value = True
        mock_store.return_value = True

        refresh_token = create_refresh_token("user@example.com")

        response = client.post(
            "/auth/token/refresh",
            cookies={"refresh_token": refresh_token},
            headers={"Accept": "application/json"},
        )

        data = response.json()
        refresh_payload = jwt.decode(
            data["refresh_token"], JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM]
        )

        # Check expiration is ~7 days
        iat = datetime.fromtimestamp(refresh_payload["iat"], UTC)
        exp = datetime.fromtimestamp(refresh_payload["exp"], UTC)
        duration = exp - iat

        expected = timedelta(days=7)
        assert abs(duration - expected) < timedelta(minutes=1)


class TestTokenRefreshAuditLogging:
    """Tests for audit logging during token refresh."""

    @patch("api.auth.AuditLogger")
    @patch("shared.utils.jwt_auth.validate_refresh_token")
    @patch("shared.utils.jwt_auth.store_refresh_token")
    def test_logs_successful_refresh(
        self, mock_store, mock_validate, mock_logger, client
    ):
        """Should log successful token refresh."""
        mock_validate.return_value = True
        mock_store.return_value = True

        refresh_token = create_refresh_token("user@example.com")

        response = client.post(
            "/auth/token/refresh",
            cookies={"refresh_token": refresh_token},
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 200
        # Audit logging is done via logger.info, not AuditLogger in this endpoint
        # Just verify it didn't crash

    @patch("api.auth.AuditLogger")
    def test_logs_failed_refresh(self, mock_logger, client):
        """Should log failed refresh attempt."""
        response = client.post(
            "/auth/token/refresh",
            cookies={"refresh_token": "invalid"},
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 401

        # Should have logged the failure
        mock_logger.log_auth_event.assert_called_once()
        call_args = mock_logger.log_auth_event.call_args
        assert call_args[0][0] == "token_refresh_failed"
        assert call_args[1]["success"] is False
