"""Test suite for JWT token admin claims.

Tests that JWT tokens correctly include is_admin and user_id claims
when users authenticate via OAuth.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add control_plane and shared to path
control_plane_dir = Path(__file__).parent.parent
shared_dir = control_plane_dir.parent / "shared"
if str(control_plane_dir) not in sys.path:
    sys.path.insert(0, str(control_plane_dir))
if str(shared_dir) not in sys.path:
    sys.path.insert(0, str(shared_dir))


@pytest.fixture
def mock_oauth_env():
    """Mock OAuth environment variables."""
    with patch.dict(
        os.environ,
        {
            "GOOGLE_OAUTH_CLIENT_ID": "test-client-id.apps.googleusercontent.com",
            "GOOGLE_OAUTH_CLIENT_SECRET": "test-client-secret",
            "ALLOWED_EMAIL_DOMAIN": "@8thlight.com",
            "CONTROL_PLANE_BASE_URL": "http://localhost:6001",
            "JWT_SECRET_KEY": "test-secret-key-for-jwt-tokens-min-32-chars",
        },
        clear=False,
    ):
        yield


@pytest.fixture
def mock_db_admin_user():
    """Mock database with an admin user."""
    mock_user = Mock()
    mock_user.email = "admin@8thlight.com"
    mock_user.is_admin = True
    mock_user.slack_user_id = "U12345ADMIN"
    return mock_user


@pytest.fixture
def mock_db_regular_user():
    """Mock database with a regular (non-admin) user."""
    mock_user = Mock()
    mock_user.email = "user@8thlight.com"
    mock_user.is_admin = False
    mock_user.slack_user_id = "U12345USER"
    return mock_user


class TestJWTAdminClaim:
    """Test that JWT tokens include correct is_admin claim."""

    @patch("models.get_db_session")
    def test_jwt_includes_admin_status_for_admin_user(
        self,
        mock_get_db_session,
        mock_oauth_env,
        mock_db_admin_user,
    ):
        """Test that create_access_token includes is_admin from database for admin users."""
        # Arrange - Mock database to return admin user
        mock_session = MagicMock()
        mock_query = mock_session.query.return_value
        mock_filter = mock_query.filter.return_value
        mock_filter.first.return_value = mock_db_admin_user
        mock_get_db_session.return_value.__enter__.return_value = mock_session

        # Import after mocking to get the mocked database
        from models import User, get_db_session
        from shared.utils.jwt_auth import create_access_token, verify_token

        # Act - Look up user and create token (mimics what auth.py does)
        email = "admin@8thlight.com"
        is_admin = False
        user_id = None

        with get_db_session() as db_session:
            user = db_session.query(User).filter(User.email == email).first()
            if user:
                is_admin = user.is_admin
                user_id = user.slack_user_id

        jwt_token = create_access_token(
            user_email=email,
            user_name="Admin User",
            user_picture="https://example.com/pic.jpg",
            additional_claims={"is_admin": is_admin, "user_id": user_id},
        )

        # Assert - Decode and verify JWT token contains correct is_admin
        payload = verify_token(jwt_token)
        assert payload["email"] == "admin@8thlight.com"
        assert payload["is_admin"] is True, "Admin user should have is_admin=true in JWT"
        assert (
            payload["user_id"] == "U12345ADMIN"
        ), "JWT should include user_id from database"

    @patch("models.get_db_session")
    def test_jwt_includes_admin_status_for_regular_user(
        self,
        mock_get_db_session,
        mock_oauth_env,
        mock_db_regular_user,
    ):
        """Test that create_access_token includes is_admin from database for regular users."""
        # Arrange - Mock database to return regular user
        mock_session = MagicMock()
        mock_query = mock_session.query.return_value
        mock_filter = mock_query.filter.return_value
        mock_filter.first.return_value = mock_db_regular_user
        mock_get_db_session.return_value.__enter__.return_value = mock_session

        # Import after mocking
        from models import User, get_db_session
        from shared.utils.jwt_auth import create_access_token, verify_token

        # Act - Look up user and create token
        email = "user@8thlight.com"
        is_admin = False
        user_id = None

        with get_db_session() as db_session:
            user = db_session.query(User).filter(User.email == email).first()
            if user:
                is_admin = user.is_admin
                user_id = user.slack_user_id

        jwt_token = create_access_token(
            user_email=email,
            user_name="Regular User",
            user_picture="https://example.com/pic.jpg",
            additional_claims={"is_admin": is_admin, "user_id": user_id},
        )

        # Assert
        payload = verify_token(jwt_token)
        assert payload["email"] == "user@8thlight.com"
        assert (
            payload["is_admin"] is False
        ), "Regular user should have is_admin=false in JWT"
        assert (
            payload["user_id"] == "U12345USER"
        ), "JWT should include user_id from database"

    @patch("models.get_db_session")
    def test_jwt_handles_user_not_in_database(
        self,
        mock_get_db_session,
        mock_oauth_env,
    ):
        """Test that JWT creation handles users not in database gracefully."""
        # Arrange - Mock database to return None (user not found)
        mock_session = MagicMock()
        mock_query = mock_session.query.return_value
        mock_filter = mock_query.filter.return_value
        mock_filter.first.return_value = None
        mock_get_db_session.return_value.__enter__.return_value = mock_session

        # Import after mocking
        from models import User, get_db_session
        from shared.utils.jwt_auth import create_access_token, verify_token

        # Act - Look up user (not found) and create token
        email = "newuser@8thlight.com"
        is_admin = False
        user_id = None

        with get_db_session() as db_session:
            user = db_session.query(User).filter(User.email == email).first()
            if user:
                is_admin = user.is_admin
                user_id = user.slack_user_id

        jwt_token = create_access_token(
            user_email=email,
            user_name="New User",
            user_picture="https://example.com/pic.jpg",
            additional_claims={"is_admin": is_admin, "user_id": user_id},
        )

        # Assert - Should succeed with is_admin=false
        payload = verify_token(jwt_token)
        assert payload["email"] == "newuser@8thlight.com"
        assert (
            payload["is_admin"] is False
        ), "User not in database should have is_admin=false"
        assert payload["user_id"] is None, "User not in database should have user_id=None"

    def test_jwt_without_additional_claims_has_no_is_admin(self, mock_oauth_env):
        """Test that JWT without additional_claims does not include is_admin (regression test for bug)."""
        from shared.utils.jwt_auth import create_access_token, verify_token

        # Act - Create token WITHOUT additional_claims (the old buggy behavior)
        jwt_token = create_access_token(
            user_email="user@8thlight.com",
            user_name="Test User",
            user_picture="https://example.com/pic.jpg",
            # NOTE: No additional_claims parameter (simulates old code)
        )

        # Assert - JWT should not have is_admin field
        payload = verify_token(jwt_token)
        assert payload["email"] == "user@8thlight.com"
        assert (
            "is_admin" not in payload
        ), "JWT without additional_claims should not have is_admin field"
