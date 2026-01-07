"""Test suite for defense-in-depth security improvements.

Tests that critical operations (delete, pause, resume) re-verify admin status
from the database, not just from JWT token claims.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException

from dependencies.auth import require_admin_from_database, verify_admin_from_database


class TestDatabaseAdminVerification:
    """Test that admin status is verified from database, not just JWT."""

    @pytest.mark.asyncio
    async def test_verify_admin_from_database_returns_true_for_admin(self):
        """Test that verify_admin_from_database returns True when user is admin in DB."""
        # Arrange - Mock control-plane response
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"is_admin": True, "user_found": True}
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Act
            result = await verify_admin_from_database("admin@8thlight.com")

            # Assert
            assert result is True
            mock_client.get.assert_called_once()
            # Verify the call was made with verify-admin endpoint
            call_args = mock_client.get.call_args
            if call_args.args:
                # Positional argument
                assert "verify-admin" in call_args.args[0]
            else:
                # Keyword argument
                assert "verify-admin" in call_args.kwargs["url"]

    @pytest.mark.asyncio
    async def test_verify_admin_from_database_returns_false_for_non_admin(self):
        """Test that verify_admin_from_database returns False when user is not admin in DB."""
        # Arrange - Mock control-plane response
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"is_admin": False, "user_found": True}
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Act
            result = await verify_admin_from_database("user@8thlight.com")

            # Assert
            assert result is False

    @pytest.mark.asyncio
    async def test_verify_admin_from_database_returns_false_for_user_not_found(self):
        """Test that verify_admin_from_database returns False when user not in DB."""
        # Arrange - Mock control-plane response
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"is_admin": False, "user_found": False}
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Act
            result = await verify_admin_from_database("unknown@8thlight.com")

            # Assert - Fail closed: deny access if user not found
            assert result is False

    @pytest.mark.asyncio
    async def test_verify_admin_fails_closed_on_non_200_response(self):
        """SECURITY: Test that verification fails closed (denies) on HTTP error."""
        # Arrange - Mock control-plane returns 500
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 500
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Act
            result = await verify_admin_from_database("admin@8thlight.com")

            # Assert - Fail closed: deny access on error
            assert result is False

    @pytest.mark.asyncio
    async def test_verify_admin_fails_closed_on_network_error(self):
        """SECURITY: Test that verification fails closed on network errors."""
        # Arrange - Mock network failure
        with patch("httpx.AsyncClient") as mock_client_class:
            import httpx

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.RequestError("Connection failed")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Act
            result = await verify_admin_from_database("admin@8thlight.com")

            # Assert - Fail closed: deny access if control-plane unreachable
            assert result is False

    @pytest.mark.asyncio
    async def test_require_admin_allows_admin_user(self):
        """Test that require_admin_from_database allows admin users."""
        # Arrange - Mock authenticated admin user
        mock_request = Mock()

        with (
            patch("dependencies.auth.get_current_user") as mock_get_user,
            patch("dependencies.auth.verify_admin_from_database") as mock_verify,
        ):
            mock_get_user.return_value = {
                "email": "admin@8thlight.com",
                "name": "Admin User",
                "is_admin": True,
            }
            mock_verify.return_value = True

            # Act
            result = await require_admin_from_database(mock_request)

            # Assert
            assert result["email"] == "admin@8thlight.com"
            mock_verify.assert_called_once_with("admin@8thlight.com")

    @pytest.mark.asyncio
    async def test_require_admin_denies_non_admin_user(self):
        """SECURITY: Test that require_admin_from_database denies non-admin users."""
        # Arrange - Mock authenticated non-admin user
        mock_request = Mock()

        with (
            patch("dependencies.auth.get_current_user") as mock_get_user,
            patch("dependencies.auth.verify_admin_from_database") as mock_verify,
        ):
            mock_get_user.return_value = {
                "email": "user@8thlight.com",
                "name": "Regular User",
                "is_admin": False,
            }
            mock_verify.return_value = False  # Not admin in database

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await require_admin_from_database(mock_request)

            assert exc_info.value.status_code == 403
            assert "admin" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_require_admin_denies_user_with_revoked_admin_status(self):
        """SECURITY: Test that users with JWT is_admin=true but DB is_admin=false are denied.

        This is the critical defense-in-depth test: JWT says admin, but database
        says they're no longer admin (privileges revoked). Should deny access.
        """
        # Arrange - User has JWT with is_admin=true, but DB says is_admin=false
        mock_request = Mock()

        with (
            patch("dependencies.auth.get_current_user") as mock_get_user,
            patch("dependencies.auth.verify_admin_from_database") as mock_verify,
        ):
            # JWT token claims user is admin
            mock_get_user.return_value = {
                "email": "former-admin@8thlight.com",
                "name": "Former Admin",
                "is_admin": True,  # JWT says admin
            }
            # But database says they're NOT admin (revoked)
            mock_verify.return_value = False  # Database says NOT admin

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await require_admin_from_database(mock_request)

            # Should deny access despite JWT claiming admin status
            assert exc_info.value.status_code == 403
            assert "revoked" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_require_admin_fails_closed_if_control_plane_down(self):
        """SECURITY: Test fail-closed behavior when control-plane is unavailable."""
        # Arrange - Control-plane is down
        mock_request = Mock()

        with (
            patch("dependencies.auth.get_current_user") as mock_get_user,
            patch("dependencies.auth.verify_admin_from_database") as mock_verify,
        ):
            mock_get_user.return_value = {
                "email": "admin@8thlight.com",
                "name": "Admin User",
                "is_admin": True,
            }
            # Control-plane verification fails (returns False on error)
            mock_verify.return_value = False

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await require_admin_from_database(mock_request)

            # Should deny access if verification fails (fail closed)
            assert exc_info.value.status_code == 403


class TestJWTExpiry:
    """Test JWT token expiry time."""

    def test_jwt_expiration_is_4_hours(self):
        """SECURITY: Test that JWT tokens expire in 4 hours, not 24 hours."""
        # Import from shared module (already in path via PYTHONPATH)
        from shared.utils.jwt_auth import JWT_EXPIRATION_HOURS

        # Assert
        assert JWT_EXPIRATION_HOURS == 4, (
            f"JWT expiry should be 4 hours for security, not {JWT_EXPIRATION_HOURS}"
        )

    def test_jwt_token_contains_expiry_4_hours_from_now(self):
        """Test that generated JWT tokens expire in 4 hours."""
        from datetime import UTC, datetime, timedelta

        # Import from shared module (already in path via PYTHONPATH)
        from shared.utils.jwt_auth import create_access_token, verify_token

        # Arrange & Act
        token = create_access_token(
            user_email="test@8thlight.com",
            user_name="Test User",
        )

        # Assert
        payload = verify_token(token)
        exp = datetime.fromtimestamp(payload["exp"], UTC)
        iat = datetime.fromtimestamp(payload["iat"], UTC)

        # Token should expire 4 hours from issuance
        expected_expiry = iat + timedelta(hours=4)
        assert (
            abs((exp - expected_expiry).total_seconds()) < 2
        )  # Allow 2 second variance
