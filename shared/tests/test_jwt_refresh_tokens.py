"""Unit tests for JWT refresh token functionality.

Tests the OAuth 2.0 refresh token flow including:
- Token creation and validation
- Redis storage and retrieval
- Token rotation
- Revocation
- Error handling
"""

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import jwt
import pytest

from shared.utils.jwt_auth import (
    JWT_ALGORITHM,
    JWT_ISSUER,
    JWT_SECRET_KEY,
    JWTAuthError,
    create_access_token,
    create_refresh_token,
    refresh_access_token_with_refresh,
    revoke_refresh_token,
    store_refresh_token,
    validate_refresh_token,
    verify_token,
)


class TestRefreshTokenCreation:
    """Tests for create_refresh_token()."""

    def test_creates_valid_refresh_token(self):
        """Should create a valid JWT refresh token."""
        user_email = "user@example.com"

        token = create_refresh_token(user_email)

        # Decode and verify structure
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])

        assert payload["email"] == user_email
        assert payload["sub"] == user_email
        assert payload["token_type"] == "refresh"
        assert payload["iss"] == JWT_ISSUER
        assert "iat" in payload
        assert "exp" in payload

    def test_refresh_token_expires_in_7_days(self):
        """Should set expiration to 7 days by default."""
        token = create_refresh_token("user@example.com")

        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])

        # Check expiration is ~7 days from now (within 1 minute tolerance)
        iat = datetime.fromtimestamp(payload["iat"], UTC)
        exp = datetime.fromtimestamp(payload["exp"], UTC)
        duration = exp - iat

        expected_duration = timedelta(days=7)
        assert abs(duration - expected_duration) < timedelta(minutes=1)

    def test_includes_additional_claims(self):
        """Should include additional claims in token."""
        token = create_refresh_token(
            "user@example.com", additional_claims={"custom_field": "value123"}
        )

        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])

        assert payload["custom_field"] == "value123"


class TestAccessTokenCreation:
    """Tests for create_access_token() with new 15-minute expiration."""

    def test_access_token_expires_in_15_minutes(self):
        """Should set expiration to 15 minutes by default."""
        token = create_access_token("user@example.com")

        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])

        # Check expiration is ~15 minutes from now
        iat = datetime.fromtimestamp(payload["iat"], UTC)
        exp = datetime.fromtimestamp(payload["exp"], UTC)
        duration = exp - iat

        expected_duration = timedelta(minutes=15)
        assert abs(duration - expected_duration) < timedelta(seconds=5)

    def test_access_token_has_correct_type(self):
        """Should mark token as 'access' type."""
        token = create_access_token("user@example.com")

        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])

        assert payload["token_type"] == "access"


class TestTokenTypeValidation:
    """Tests for verify_token() with token type checking."""

    def test_verify_access_token_with_type_check(self):
        """Should verify access token when expected_type='access'."""
        token = create_access_token("user@example.com", user_name="Test User")

        payload = verify_token(token, expected_type="access")

        assert payload["email"] == "user@example.com"
        assert payload["token_type"] == "access"

    def test_verify_refresh_token_with_type_check(self):
        """Should verify refresh token when expected_type='refresh'."""
        token = create_refresh_token("user@example.com")

        payload = verify_token(token, expected_type="refresh")

        assert payload["email"] == "user@example.com"
        assert payload["token_type"] == "refresh"

    def test_rejects_access_token_when_refresh_expected(self):
        """Should reject access token if refresh token expected."""
        token = create_access_token("user@example.com")

        with pytest.raises(JWTAuthError) as exc:
            verify_token(token, expected_type="refresh")

        assert "Invalid token type" in str(exc.value)
        assert "expected 'refresh'" in str(exc.value)
        assert "got 'access'" in str(exc.value)

    def test_rejects_refresh_token_when_access_expected(self):
        """Should reject refresh token if access token expected."""
        token = create_refresh_token("user@example.com")

        with pytest.raises(JWTAuthError) as exc:
            verify_token(token, expected_type="access")

        assert "Invalid token type" in str(exc.value)

    def test_accepts_any_token_when_no_type_specified(self):
        """Should accept any token type when expected_type=None."""
        access_token = create_access_token("user@example.com")
        refresh_token = create_refresh_token("user@example.com")

        # Both should work without type check
        payload1 = verify_token(access_token)
        payload2 = verify_token(refresh_token)

        assert payload1["token_type"] == "access"
        assert payload2["token_type"] == "refresh"


@patch("shared.utils.jwt_auth._get_redis")
class TestRefreshTokenStorage:
    """Tests for store_refresh_token() and validate_refresh_token()."""

    def test_store_refresh_token_in_redis(self, mock_get_redis):
        """Should store refresh token in Redis with 7-day TTL."""
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis

        user_email = "user@example.com"
        token = create_refresh_token(user_email)

        result = store_refresh_token(user_email, token)

        assert result is True
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == f"refresh_token:{user_email}"
        assert call_args[0][1] == 7 * 24 * 60 * 60  # 7 days in seconds
        assert call_args[0][2] == token

    def test_store_fails_when_redis_unavailable(self, mock_get_redis):
        """Should return False when Redis unavailable."""
        mock_get_redis.return_value = None

        result = store_refresh_token("user@example.com", "token123")

        assert result is False

    def test_validate_refresh_token_success(self, mock_get_redis):
        """Should validate refresh token against Redis."""
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis

        user_email = "user@example.com"
        token = create_refresh_token(user_email)
        mock_redis.get.return_value = token

        result = validate_refresh_token(user_email, token)

        assert result is True
        mock_redis.get.assert_called_once_with(f"refresh_token:{user_email}")

    def test_validate_fails_for_wrong_token(self, mock_get_redis):
        """Should reject mismatched token."""
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis

        mock_redis.get.return_value = "stored_token"

        result = validate_refresh_token("user@example.com", "different_token")

        assert result is False

    def test_validate_fails_for_nonexistent_token(self, mock_get_redis):
        """Should reject when no token stored."""
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis

        mock_redis.get.return_value = None

        result = validate_refresh_token("user@example.com", "token123")

        assert result is False

    def test_validate_fallback_when_redis_unavailable(self, mock_get_redis):
        """Should fall back to JWT signature verification when Redis unavailable."""
        mock_get_redis.return_value = None

        user_email = "user@example.com"
        token = create_refresh_token(user_email)

        # Should validate based on JWT signature only
        result = validate_refresh_token(user_email, token)

        assert result is True

    def test_validate_fallback_rejects_invalid_token(self, mock_get_redis):
        """Should reject invalid token even in fallback mode."""
        mock_get_redis.return_value = None

        result = validate_refresh_token("user@example.com", "invalid_token")

        assert result is False


@patch("shared.utils.jwt_auth._get_redis")
class TestRefreshTokenRevocation:
    """Tests for revoke_refresh_token()."""

    def test_revoke_deletes_token_from_redis(self, mock_get_redis):
        """Should delete refresh token from Redis."""
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis

        user_email = "user@example.com"

        result = revoke_refresh_token(user_email)

        assert result is True
        mock_redis.delete.assert_called_once_with(f"refresh_token:{user_email}")

    def test_revoke_fails_when_redis_unavailable(self, mock_get_redis):
        """Should return False when Redis unavailable."""
        mock_get_redis.return_value = None

        result = revoke_refresh_token("user@example.com")

        assert result is False

    def test_revoke_handles_redis_error(self, mock_get_redis):
        """Should handle Redis errors gracefully."""
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis
        mock_redis.delete.side_effect = Exception("Redis connection failed")

        result = revoke_refresh_token("user@example.com")

        assert result is False


@patch("shared.utils.jwt_auth.store_refresh_token")
@patch("shared.utils.jwt_auth.validate_refresh_token")
class TestTokenRefreshFlow:
    """Tests for refresh_access_token_with_refresh() - complete flow."""

    def test_refresh_access_token_success(self, mock_validate, mock_store):
        """Should exchange valid refresh token for new access token."""
        mock_validate.return_value = True
        mock_store.return_value = True

        user_email = "user@example.com"
        refresh_token = create_refresh_token(user_email)

        new_access, new_refresh = refresh_access_token_with_refresh(
            refresh_token, rotate_refresh=False
        )

        # Should return new access token
        assert new_access is not None
        payload = jwt.decode(new_access, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        assert payload["email"] == user_email
        assert payload["token_type"] == "access"

        # Should not rotate refresh token
        assert new_refresh is None

    def test_refresh_with_token_rotation(self, mock_validate, mock_store):
        """Should rotate refresh token when rotate_refresh=True."""
        mock_validate.return_value = True
        mock_store.return_value = True

        user_email = "user@example.com"
        old_refresh = create_refresh_token(user_email)

        new_access, new_refresh = refresh_access_token_with_refresh(
            old_refresh, rotate_refresh=True
        )

        # Should return both new tokens
        assert new_access is not None
        assert new_refresh is not None

        # Verify new refresh token was created and stored
        # (tokens might be identical if created in same second due to JWT second-precision)
        mock_store.assert_called_once_with(user_email, new_refresh)

        # Verify it's a valid refresh token
        payload = jwt.decode(new_refresh, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        assert payload["token_type"] == "refresh"
        assert payload["email"] == user_email

    def test_refresh_preserves_additional_claims(self, mock_validate, mock_store):
        """Should preserve additional claims in new access token."""
        mock_validate.return_value = True

        refresh_token = create_refresh_token(
            "user@example.com", additional_claims={"is_admin": True, "user_id": "U123"}
        )

        new_access, _ = refresh_access_token_with_refresh(
            refresh_token, rotate_refresh=False
        )

        payload = jwt.decode(new_access, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        assert payload["is_admin"] is True
        assert payload["user_id"] == "U123"

    def test_refresh_fails_for_invalid_token(self, mock_validate, mock_store):
        """Should reject invalid refresh token."""
        with pytest.raises(JWTAuthError):
            refresh_access_token_with_refresh("invalid_token")

    def test_refresh_fails_for_expired_token(self, mock_validate, mock_store):
        """Should reject expired refresh token."""
        # Create token that's already expired
        with patch("shared.utils.jwt_auth.REFRESH_TOKEN_DAYS", -1):
            expired_token = create_refresh_token("user@example.com")

        # Wait a moment to ensure expiration
        time.sleep(0.1)

        with pytest.raises(JWTAuthError) as exc:
            refresh_access_token_with_refresh(expired_token)

        assert "expired" in str(exc.value).lower()

    def test_refresh_fails_for_access_token(self, mock_validate, mock_store):
        """Should reject access token (wrong type)."""
        access_token = create_access_token("user@example.com")

        with pytest.raises(JWTAuthError) as exc:
            refresh_access_token_with_refresh(access_token)

        assert "Invalid token type" in str(exc.value)

    def test_refresh_fails_when_validation_fails(self, mock_validate, mock_store):
        """Should reject when Redis validation fails."""
        mock_validate.return_value = False  # Token not in Redis or doesn't match

        refresh_token = create_refresh_token("user@example.com")

        with pytest.raises(JWTAuthError) as exc:
            refresh_access_token_with_refresh(refresh_token)

        assert "not valid or has been revoked" in str(exc.value)


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_refresh_token_without_email(self):
        """Should handle refresh token missing email."""
        # Manually create malformed token
        payload = {
            "sub": "test",
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(days=7),
            "iss": JWT_ISSUER,
            "token_type": "refresh",
            # Missing email field
        }
        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

        with pytest.raises(JWTAuthError) as exc:
            verify_token(token)

        assert "missing required 'email' field" in str(exc.value)

    @patch("shared.utils.jwt_auth.validate_refresh_token")
    def test_refresh_with_name_and_picture(self, mock_validate):
        """Should preserve name and picture in refreshed access token."""
        mock_validate.return_value = True

        # Create refresh token with user info
        refresh_token = jwt.encode(
            {
                "sub": "user@example.com",
                "email": "user@example.com",
                "name": "John Doe",
                "picture": "https://example.com/photo.jpg",
                "iat": datetime.now(UTC),
                "exp": datetime.now(UTC) + timedelta(days=7),
                "iss": JWT_ISSUER,
                "token_type": "refresh",
            },
            JWT_SECRET_KEY,
            algorithm=JWT_ALGORITHM,
        )

        new_access, _ = refresh_access_token_with_refresh(
            refresh_token, rotate_refresh=False
        )

        payload = jwt.decode(new_access, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        assert payload["name"] == "John Doe"
        assert payload["picture"] == "https://example.com/photo.jpg"
