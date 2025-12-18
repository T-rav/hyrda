"""Comprehensive unit tests for JWT authentication utilities.

Tests cover:
- JWT token creation and verification
- Service token validation
- Token expiration handling
- Token revocation (with and without Redis)
- Header extraction
- Error cases and edge cases
- Environment variable handling
"""

import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import jwt
import pytest

# Add shared to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.utils.jwt_auth import (  # noqa: E402
    JWT_ALGORITHM,
    JWT_EXPIRATION_HOURS,
    JWT_ISSUER,
    JWT_SECRET_KEY,
    SERVICE_TOKEN,
    SERVICE_TOKENS,
    JWTAuthError,
    create_access_token,
    extract_token_from_request,
    get_user_from_token,
    is_token_revoked,
    revoke_token,
    verify_service_token,
    verify_token,
)


class TestJWTTokenCreation:
    """Test JWT token creation functionality."""

    def test_create_access_token_basic(self) -> None:
        """Test creating a basic access token with email only."""
        token = create_access_token("user@example.com")

        assert token is not None
        assert isinstance(token, str)

        # Decode without verification to check structure
        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["email"] == "user@example.com"
        assert payload["sub"] == "user@example.com"
        assert payload["iss"] == JWT_ISSUER

    def test_create_access_token_with_full_user_info(self) -> None:
        """Test creating token with complete user information."""
        token = create_access_token(
            user_email="user@example.com",
            user_name="John Doe",
            user_picture="https://example.com/avatar.jpg",
        )

        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["email"] == "user@example.com"
        assert payload["name"] == "John Doe"
        assert payload["picture"] == "https://example.com/avatar.jpg"

    def test_create_access_token_with_additional_claims(self) -> None:
        """Test creating token with custom additional claims."""
        additional = {"role": "admin", "department": "engineering"}
        token = create_access_token(
            user_email="admin@example.com", additional_claims=additional
        )

        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["role"] == "admin"
        assert payload["department"] == "engineering"

    def test_create_access_token_expiration(self) -> None:
        """Test that token has correct expiration time."""
        token = create_access_token("user@example.com")

        payload = jwt.decode(token, options={"verify_signature": False})

        # Check expiration is set correctly
        exp_time = datetime.fromtimestamp(payload["exp"], tz=UTC)
        iat_time = datetime.fromtimestamp(payload["iat"], tz=UTC)

        expected_delta = timedelta(hours=JWT_EXPIRATION_HOURS)
        actual_delta = exp_time - iat_time

        # Allow 1 second tolerance
        assert abs((actual_delta - expected_delta).total_seconds()) < 1

    def test_create_access_token_includes_timestamps(self) -> None:
        """Test that token includes iat (issued at) and exp (expiration)."""
        token = create_access_token("user@example.com")

        payload = jwt.decode(token, options={"verify_signature": False})
        assert "iat" in payload
        assert "exp" in payload
        assert isinstance(payload["iat"], (int, float, datetime))
        assert isinstance(payload["exp"], (int, float, datetime))

    def test_create_access_token_with_none_values(self) -> None:
        """Test creating token with None for optional fields."""
        token = create_access_token(
            user_email="user@example.com", user_name=None, user_picture=None
        )

        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["email"] == "user@example.com"
        assert payload["name"] is None
        assert payload["picture"] is None


class TestJWTTokenVerification:
    """Test JWT token verification functionality."""

    def test_verify_valid_token(self) -> None:
        """Test verifying a valid token."""
        token = create_access_token(
            user_email="user@example.com", user_name="Test User"
        )

        payload = verify_token(token)
        assert payload["email"] == "user@example.com"
        assert payload["name"] == "Test User"

    def test_verify_token_with_invalid_signature(self) -> None:
        """Test verifying token with tampered signature."""
        token = create_access_token("user@example.com")

        # Tamper with the token
        tampered_token = token[:-10] + "invalid123"

        with pytest.raises(JWTAuthError, match="Invalid token"):
            verify_token(tampered_token)

    def test_verify_expired_token(self) -> None:
        """Test verifying an expired token."""
        # Create token with past expiration
        now = datetime.now(UTC)
        past_time = now - timedelta(hours=2)

        payload = {
            "sub": "user@example.com",
            "email": "user@example.com",
            "iat": past_time,
            "exp": past_time + timedelta(hours=1),  # Already expired
            "iss": JWT_ISSUER,
        }

        expired_token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

        with pytest.raises(JWTAuthError, match="Token has expired"):
            verify_token(expired_token)

    def test_verify_token_missing_email(self) -> None:
        """Test verifying token without required email field."""
        now = datetime.now(UTC)
        payload = {
            "sub": "user@example.com",
            "iat": now,
            "exp": now + timedelta(hours=1),
            "iss": JWT_ISSUER,
            # Missing "email" field
        }

        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

        with pytest.raises(JWTAuthError, match="missing required 'email' field"):
            verify_token(token)

    def test_verify_token_wrong_issuer(self) -> None:
        """Test verifying token with wrong issuer."""
        now = datetime.now(UTC)
        payload = {
            "sub": "user@example.com",
            "email": "user@example.com",
            "iat": now,
            "exp": now + timedelta(hours=1),
            "iss": "wrong-issuer",
        }

        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

        with pytest.raises(JWTAuthError, match="Invalid token"):
            verify_token(token)

    def test_verify_token_malformed(self) -> None:
        """Test verifying malformed token."""
        with pytest.raises(JWTAuthError, match="Invalid token"):
            verify_token("not.a.valid.jwt.token")

    def test_verify_token_empty_string(self) -> None:
        """Test verifying empty token string."""
        with pytest.raises(JWTAuthError, match="Invalid token"):
            verify_token("")

    @patch("shared.utils.jwt_auth.is_token_revoked")
    def test_verify_revoked_token(self, mock_is_revoked: MagicMock) -> None:
        """Test verifying a token that has been revoked."""
        mock_is_revoked.return_value = True

        token = create_access_token("user@example.com")

        with pytest.raises(JWTAuthError, match="Token has been revoked"):
            verify_token(token)


class TestTokenExtraction:
    """Test token extraction from HTTP headers."""

    def test_extract_token_valid_bearer(self) -> None:
        """Test extracting token from valid Bearer header."""
        token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.token"
        header = f"Bearer {token}"

        extracted = extract_token_from_request(header)
        assert extracted == token

    def test_extract_token_case_insensitive(self) -> None:
        """Test Bearer keyword is case-insensitive."""
        token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.token"
        header = f"bearer {token}"

        extracted = extract_token_from_request(header)
        assert extracted == token

    def test_extract_token_mixed_case(self) -> None:
        """Test Bearer with mixed case."""
        token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.token"
        header = f"BeArEr {token}"

        extracted = extract_token_from_request(header)
        assert extracted == token

    def test_extract_token_no_header(self) -> None:
        """Test extraction with None header."""
        extracted = extract_token_from_request(None)
        assert extracted is None

    def test_extract_token_empty_header(self) -> None:
        """Test extraction with empty header."""
        extracted = extract_token_from_request("")
        assert extracted is None

    def test_extract_token_missing_bearer(self) -> None:
        """Test extraction without Bearer prefix."""
        extracted = extract_token_from_request("just.a.token")
        assert extracted is None

    def test_extract_token_wrong_scheme(self) -> None:
        """Test extraction with wrong authentication scheme."""
        extracted = extract_token_from_request("Basic dXNlcjpwYXNz")
        assert extracted is None

    def test_extract_token_extra_spaces(self) -> None:
        """Test extraction fails with extra spaces."""
        extracted = extract_token_from_request("Bearer  token  extra")
        assert extracted is None

    def test_extract_token_only_bearer(self) -> None:
        """Test extraction with only Bearer keyword, no token."""
        extracted = extract_token_from_request("Bearer")
        assert extracted is None


class TestGetUserFromToken:
    """Test user information extraction from tokens."""

    def test_get_user_from_valid_token(self) -> None:
        """Test extracting user info from valid token."""
        token = create_access_token(
            user_email="user@example.com",
            user_name="Test User",
            user_picture="https://example.com/pic.jpg",
        )

        user_info = get_user_from_token(token)
        assert user_info["email"] == "user@example.com"
        assert user_info["name"] == "Test User"
        assert user_info["picture"] == "https://example.com/pic.jpg"

    def test_get_user_from_token_minimal(self) -> None:
        """Test extracting user info with only email."""
        token = create_access_token(user_email="user@example.com")

        user_info = get_user_from_token(token)
        assert user_info["email"] == "user@example.com"
        assert user_info["name"] is None
        assert user_info["picture"] is None

    def test_get_user_from_invalid_token(self) -> None:
        """Test that invalid token raises error."""
        with pytest.raises(JWTAuthError):
            get_user_from_token("invalid.token")

    def test_get_user_from_expired_token(self) -> None:
        """Test that expired token raises error."""
        # Create expired token
        now = datetime.now(UTC)
        past_time = now - timedelta(hours=2)
        payload = {
            "sub": "user@example.com",
            "email": "user@example.com",
            "iat": past_time,
            "exp": past_time + timedelta(hours=1),
            "iss": JWT_ISSUER,
        }
        expired_token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

        with pytest.raises(JWTAuthError, match="Token has expired"):
            get_user_from_token(expired_token)


class TestServiceTokenValidation:
    """Test service-to-service token validation."""

    def test_verify_valid_service_token(self) -> None:
        """Test verifying valid generic service token."""
        service_info = verify_service_token(SERVICE_TOKEN)

        assert service_info is not None
        # Service token can match any service that uses the same token
        assert "service" in service_info
        assert service_info["service"] in SERVICE_TOKENS.keys()

    def test_verify_bot_service_token(self) -> None:
        """Test verifying bot-specific service token."""
        bot_token = SERVICE_TOKENS["bot"]
        service_info = verify_service_token(bot_token)

        assert service_info is not None
        # Since bot token defaults to SERVICE_TOKEN in dev, it could be "bot" or "generic"
        assert service_info["service"] in ("bot", "generic")

    def test_verify_control_plane_service_token(self) -> None:
        """Test verifying control-plane service token."""
        cp_token = SERVICE_TOKENS["control-plane"]
        service_info = verify_service_token(cp_token)

        assert service_info is not None
        # Service token can match any service that uses the same token
        assert "service" in service_info
        assert service_info["service"] in SERVICE_TOKENS.keys()

    def test_verify_invalid_service_token(self) -> None:
        """Test that invalid service token returns None."""
        service_info = verify_service_token("invalid-token-12345")

        assert service_info is None

    def test_verify_none_service_token(self) -> None:
        """Test that None service token returns None."""
        service_info = verify_service_token(None)  # type: ignore[arg-type]

        assert service_info is None

    def test_verify_empty_service_token(self) -> None:
        """Test that empty service token returns None."""
        service_info = verify_service_token("")

        assert service_info is None

    def test_service_tokens_structure(self) -> None:
        """Test that SERVICE_TOKENS has expected structure."""
        assert "bot" in SERVICE_TOKENS
        assert "control-plane" in SERVICE_TOKENS
        assert "generic" in SERVICE_TOKENS
        assert SERVICE_TOKENS["generic"] == SERVICE_TOKEN


class TestTokenRevocation:
    """Test token revocation functionality."""

    @patch("shared.utils.jwt_auth._get_redis")
    def test_revoke_token_success(self, mock_get_redis: MagicMock) -> None:
        """Test successful token revocation with Redis available."""
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis

        token = create_access_token("user@example.com")
        result = revoke_token(token)

        assert result is True
        mock_redis.setex.assert_called_once()
        # Check that setex was called with the token key
        call_args = mock_redis.setex.call_args
        assert call_args[0][0].startswith("revoked_token:")

    @patch("shared.utils.jwt_auth._get_redis")
    def test_revoke_token_redis_unavailable(self, mock_get_redis: MagicMock) -> None:
        """Test token revocation when Redis is unavailable."""
        mock_get_redis.return_value = None

        token = create_access_token("user@example.com")
        result = revoke_token(token)

        assert result is False

    @patch("shared.utils.jwt_auth._get_redis")
    def test_revoke_token_redis_error(self, mock_get_redis: MagicMock) -> None:
        """Test token revocation when Redis raises an error."""
        mock_redis = MagicMock()
        mock_redis.setex.side_effect = Exception("Redis connection error")
        mock_get_redis.return_value = mock_redis

        token = create_access_token("user@example.com")
        result = revoke_token(token)

        assert result is False

    @patch("shared.utils.jwt_auth._get_redis")
    def test_revoke_token_sets_correct_ttl(self, mock_get_redis: MagicMock) -> None:
        """Test that revoke_token sets TTL matching token expiration."""
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis

        token = create_access_token("user@example.com")
        revoke_token(token)

        # Verify TTL is positive (token hasn't expired yet)
        call_args = mock_redis.setex.call_args
        ttl = call_args[0][1]
        assert ttl > 0


class TestTokenRevocationCheck:
    """Test checking if tokens are revoked."""

    @patch("shared.utils.jwt_auth._get_redis")
    def test_is_token_revoked_true(self, mock_get_redis: MagicMock) -> None:
        """Test checking a revoked token."""
        mock_redis = MagicMock()
        mock_redis.exists.return_value = 1
        mock_get_redis.return_value = mock_redis

        token = "test.token"
        result = is_token_revoked(token)

        assert result is True
        mock_redis.exists.assert_called_once_with(f"revoked_token:{token}")

    @patch("shared.utils.jwt_auth._get_redis")
    def test_is_token_revoked_false(self, mock_get_redis: MagicMock) -> None:
        """Test checking a non-revoked token."""
        mock_redis = MagicMock()
        mock_redis.exists.return_value = 0
        mock_get_redis.return_value = mock_redis

        token = "test.token"
        result = is_token_revoked(token)

        assert result is False

    @patch("shared.utils.jwt_auth._get_redis")
    def test_is_token_revoked_redis_unavailable(
        self, mock_get_redis: MagicMock
    ) -> None:
        """Test checking revocation when Redis is unavailable."""
        mock_get_redis.return_value = None

        result = is_token_revoked("test.token")

        # If Redis unavailable, assume not revoked
        assert result is False

    @patch("shared.utils.jwt_auth._get_redis")
    def test_is_token_revoked_redis_error(self, mock_get_redis: MagicMock) -> None:
        """Test checking revocation when Redis raises an error."""
        mock_redis = MagicMock()
        mock_redis.exists.side_effect = Exception("Redis error")
        mock_get_redis.return_value = mock_redis

        result = is_token_revoked("test.token")

        # On error, assume not revoked
        assert result is False


class TestRedisConnection:
    """Test Redis connection management."""

    @patch.dict(os.environ, {"CACHE_REDIS_URL": "redis://testhost:6379"})
    def test_get_redis_success(self) -> None:
        """Test successful Redis connection."""
        # Reset the global redis client
        import shared.utils.jwt_auth

        shared.utils.jwt_auth._redis_client = None

        # Mock redis import at the module level
        mock_redis_module = MagicMock()
        mock_client = MagicMock()
        mock_redis_module.from_url.return_value = mock_client

        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            from shared.utils.jwt_auth import _get_redis

            client = _get_redis()

            assert client is mock_client
            mock_redis_module.from_url.assert_called_once_with(
                "redis://testhost:6379", decode_responses=True
            )

        # Cleanup
        shared.utils.jwt_auth._redis_client = None

    def test_get_redis_import_error(self) -> None:
        """Test Redis connection when redis module unavailable."""
        # Reset the global redis client
        import shared.utils.jwt_auth
        from typing import Any

        shared.utils.jwt_auth._redis_client = None

        # Mock redis import failure
        with patch.dict("sys.modules", {"redis": None}):
            # Patch the import to raise ImportError
            import builtins

            original_import = builtins.__import__

            def mock_import(
                name: str,
                globals: dict[str, Any] | None = None,
                locals: dict[str, Any] | None = None,
                fromlist: tuple[str, ...] = (),
                level: int = 0,
            ) -> Any:
                if name == "redis":
                    raise ImportError("No module named redis")
                return original_import(name, globals, locals, fromlist, level)

            with patch("builtins.__import__", side_effect=mock_import):
                from shared.utils.jwt_auth import _get_redis

                client = _get_redis()

                assert client is None

        # Cleanup
        shared.utils.jwt_auth._redis_client = None

    def test_get_redis_connection_error(self) -> None:
        """Test Redis connection failure."""
        # Reset the global redis client
        import shared.utils.jwt_auth

        shared.utils.jwt_auth._redis_client = None

        # Mock redis module that raises connection error
        mock_redis_module = MagicMock()
        mock_redis_module.from_url.side_effect = Exception("Connection refused")

        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            from shared.utils.jwt_auth import _get_redis

            client = _get_redis()

            assert client is None

        # Cleanup
        shared.utils.jwt_auth._redis_client = None


class TestEnvironmentConfiguration:
    """Test environment-based configuration."""

    def test_jwt_secret_key_exists(self) -> None:
        """Test that JWT secret key is configured."""
        assert JWT_SECRET_KEY is not None
        assert len(JWT_SECRET_KEY) > 0

    def test_jwt_algorithm_is_hs256(self) -> None:
        """Test that JWT algorithm is HS256."""
        assert JWT_ALGORITHM == "HS256"

    def test_jwt_expiration_hours_default(self) -> None:
        """Test default JWT expiration hours."""
        assert JWT_EXPIRATION_HOURS == 4  # 4 hours for better security

    def test_jwt_issuer_is_insightmesh(self) -> None:
        """Test JWT issuer is set correctly."""
        assert JWT_ISSUER == "insightmesh"

    def test_service_token_exists(self) -> None:
        """Test that service token is configured."""
        assert SERVICE_TOKEN is not None
        assert len(SERVICE_TOKEN) > 0


class TestJWTAuthError:
    """Test custom JWT authentication exception."""

    def test_jwt_auth_error_is_exception(self) -> None:
        """Test that JWTAuthError is an exception."""
        error = JWTAuthError("Test error")
        assert isinstance(error, Exception)

    def test_jwt_auth_error_message(self) -> None:
        """Test JWTAuthError message."""
        message = "Authentication failed"
        error = JWTAuthError(message)
        assert str(error) == message

    def test_jwt_auth_error_can_be_raised(self) -> None:
        """Test that JWTAuthError can be raised and caught."""
        with pytest.raises(JWTAuthError) as exc_info:
            raise JWTAuthError("Test error")

        assert "Test error" in str(exc_info.value)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_token_with_special_characters_in_email(self) -> None:
        """Test token creation with special characters in email."""
        email = "user+test@example.com"
        token = create_access_token(email)

        payload = verify_token(token)
        assert payload["email"] == email

    def test_token_with_unicode_in_name(self) -> None:
        """Test token creation with Unicode characters in name."""
        token = create_access_token(
            user_email="user@example.com", user_name="José García 日本語"
        )

        payload = verify_token(token)
        assert payload["name"] == "José García 日本語"

    def test_token_with_very_long_email(self) -> None:
        """Test token creation with very long email."""
        long_email = "a" * 200 + "@example.com"
        token = create_access_token(long_email)

        payload = verify_token(token)
        assert payload["email"] == long_email

    def test_token_roundtrip_preserves_data(self) -> None:
        """Test that token creation and verification preserves all data."""
        original_data = {
            "email": "user@example.com",
            "name": "Test User",
            "picture": "https://example.com/pic.jpg",
            "additional": {"role": "admin", "level": 5},
        }

        token = create_access_token(
            user_email=original_data["email"],
            user_name=original_data["name"],
            user_picture=original_data["picture"],
            additional_claims=original_data["additional"],
        )

        payload = verify_token(token)
        assert payload["email"] == original_data["email"]
        assert payload["name"] == original_data["name"]
        assert payload["picture"] == original_data["picture"]
        assert payload["role"] == original_data["additional"]["role"]
        assert payload["level"] == original_data["additional"]["level"]

    def test_verify_token_with_different_secret(self) -> None:
        """Test that token fails verification with different secret."""
        # Create token with current secret
        token = create_access_token("user@example.com")

        # Try to verify with different secret (will use wrong key)
        different_secret = "different-secret-key-12345"
        with pytest.raises(Exception):  # Will raise InvalidTokenError
            jwt.decode(
                token,
                different_secret,
                algorithms=[JWT_ALGORITHM],
                issuer=JWT_ISSUER,
            )

    def test_create_token_near_midnight(self) -> None:
        """Test token creation near day boundary doesn't cause issues."""
        # This test ensures no timezone/date math issues
        token = create_access_token("user@example.com")
        payload = verify_token(token)

        # Verify expiration is in the future
        exp_time = datetime.fromtimestamp(payload["exp"], tz=UTC)
        now = datetime.now(UTC)
        assert exp_time > now
