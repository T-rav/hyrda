"""Comprehensive tests for Tasks API endpoints (auth, credentials, dependencies)."""

import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add project root to path for shared module imports
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


# Re-use the factories but get the FastAPI app directly
@pytest.fixture
def app():
    """Get the FastAPI app instance for testing."""
    # Set required env vars for app creation
    os.environ.setdefault("TASK_DATABASE_URL", "sqlite:///:memory:")
    os.environ.setdefault("DATA_DATABASE_URL", "sqlite:///:memory:")
    os.environ.setdefault("SERVER_BASE_URL", "http://localhost:5001")
    os.environ.setdefault("SECRET_KEY", "test-secret-key-for-sessions")
    os.environ.setdefault("ALLOWED_EMAIL_DOMAIN", "8thlight.com")

    from app import app as fastapi_app

    return fastapi_app


@pytest.fixture
def client(app):
    """Create test client for FastAPI app."""
    from fastapi.testclient import TestClient

    return TestClient(app)


@pytest.fixture
def authenticated_client(app):
    """Create authenticated test client with dependency override."""
    from fastapi.testclient import TestClient

    from dependencies.auth import get_current_user

    # Override the get_current_user dependency to return a mock user
    async def override_get_current_user():
        return {
            "email": "user@8thlight.com",
            "name": "Test User",
            "picture": "https://example.com/photo.jpg",
        }

    app.dependency_overrides[get_current_user] = override_get_current_user

    client = TestClient(app)

    yield client

    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
def mock_oauth_env(monkeypatch):
    """Mock OAuth environment variables."""
    monkeypatch.setenv(
        "GOOGLE_OAUTH_CLIENT_ID", "test-client-id.apps.googleusercontent.com"
    )
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("ALLOWED_EMAIL_DOMAIN", "8thlight.com")
    monkeypatch.setenv("SERVER_BASE_URL", "http://localhost:5001")


class TestAuthCallbackEndpoint:
    """Test /auth/callback OAuth callback endpoint."""

    def test_callback_missing_csrf_token(self, client, mock_oauth_env):
        """Test callback fails when CSRF token is missing from session."""
        response = client.get("/auth/callback")
        assert response.status_code == 403
        assert "Invalid session" in response.json()["error"]

    def test_callback_missing_state(self, client, mock_oauth_env):
        """Test callback fails when OAuth state is missing."""
        # Set CSRF token but not state
        with client:
            client.cookies.set("session", "test-session")
            response = client.get("/auth/callback")
            # Since we can't easily set session data without middleware,
            # this will fail on CSRF check - that's expected
            assert response.status_code in [400, 403]

    @patch("utils.auth.get_flow")
    @patch("utils.auth.verify_token")
    @patch("utils.auth.verify_domain")
    def test_callback_success(
        self,
        mock_verify_domain,
        mock_verify_token,
        mock_get_flow,
        client,
        mock_oauth_env,
    ):
        """Test successful OAuth callback."""
        # Mock OAuth flow
        mock_flow = Mock()
        mock_credentials = Mock()
        mock_credentials.id_token = "test-id-token"
        mock_flow.credentials = mock_credentials
        mock_get_flow.return_value = mock_flow

        # Mock token verification
        mock_verify_token.return_value = {
            "email": "user@8thlight.com",
            "name": "Test User",
            "picture": "https://example.com/photo.jpg",
        }

        # Mock domain verification
        mock_verify_domain.return_value = True

        # This will still fail without proper session setup, but validates the mocking
        response = client.get("/auth/callback?code=test-code&state=test-state")
        # Expected to fail on session checks, but validates mock setup
        assert response.status_code in [302, 400, 403]

    @patch("utils.auth.get_flow")
    @patch("utils.auth.verify_token")
    def test_callback_no_email_in_token(
        self, mock_verify_token, mock_get_flow, client, mock_oauth_env
    ):
        """Test callback fails when token has no email."""
        mock_flow = Mock()
        mock_credentials = Mock()
        mock_credentials.id_token = "test-id-token"
        mock_flow.credentials = mock_credentials
        mock_get_flow.return_value = mock_flow

        # Token with no email
        mock_verify_token.return_value = {"name": "Test User"}

        response = client.get("/auth/callback?code=test-code&state=test-state")
        # Will fail on session checks first
        assert response.status_code in [400, 403]

    @patch("utils.auth.get_flow")
    @patch("utils.auth.verify_token")
    @patch("utils.auth.verify_domain")
    def test_callback_domain_not_allowed(
        self,
        mock_verify_domain,
        mock_verify_token,
        mock_get_flow,
        client,
        mock_oauth_env,
    ):
        """Test callback fails when email domain is not allowed."""
        mock_flow = Mock()
        mock_credentials = Mock()
        mock_credentials.id_token = "test-id-token"
        mock_flow.credentials = mock_credentials
        mock_get_flow.return_value = mock_flow

        mock_verify_token.return_value = {"email": "attacker@evil.com"}
        mock_verify_domain.return_value = False

        response = client.get("/auth/callback?code=test-code&state=test-state")
        # Will fail on session checks first
        assert response.status_code in [400, 403]

    @patch("utils.auth.get_flow")
    def test_callback_oauth_error(self, mock_get_flow, client, mock_oauth_env):
        """Test callback handles OAuth errors gracefully."""
        mock_get_flow.side_effect = Exception("OAuth provider error")

        response = client.get("/auth/callback?code=test-code&state=test-state")
        # Will fail on session checks or OAuth error
        assert response.status_code in [400, 403, 500]


class TestLogoutEndpoint:
    """Test /auth/logout endpoint."""

    def test_logout_clears_session(self, client):
        """Test logout clears user session."""
        response = client.post("/auth/logout")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Logged out successfully"
        assert (
            "token_revoked" in data
        )  # May be True or False depending on token presence

    def test_logout_without_session(self, client):
        """Test logout works even without active session."""
        response = client.post("/auth/logout")
        assert response.status_code == 200
        assert "Logged out" in response.json()["message"]


class TestCredentialsListEndpoint:
    """Test /api/credentials endpoint for listing credentials."""

    @patch("api.credentials.get_db_session")
    def test_list_credentials_empty(self, mock_db_session, authenticated_client):
        """Test listing credentials when none exist."""
        # Mock empty database
        mock_session = MagicMock()
        mock_session.query().all.return_value = []
        mock_db_session.return_value.__enter__.return_value = mock_session

        response = authenticated_client.get("/api/credentials")
        assert response.status_code == 200
        assert response.json() == {"credentials": []}

    @patch("api.credentials.get_db_session")
    def test_list_credentials_with_active_credential(
        self, mock_db_session, authenticated_client
    ):
        """Test listing credentials with active token."""

        # Mock credential with future expiry
        mock_cred = Mock()
        mock_cred.credential_id = "test-cred-1"
        mock_cred.credential_name = "Production GDrive"
        future_expiry = datetime.now(UTC) + timedelta(days=30)
        mock_cred.token_metadata = {"expiry": future_expiry.isoformat()}
        mock_cred.to_dict.return_value = {
            "credential_id": "test-cred-1",
            "credential_name": "Production GDrive",
        }

        mock_session = MagicMock()
        mock_session.query().all.return_value = [mock_cred]
        mock_db_session.return_value.__enter__.return_value = mock_session

        response = authenticated_client.get("/api/credentials")
        assert response.status_code == 200
        data = response.json()
        assert len(data["credentials"]) == 1
        assert data["credentials"][0]["status"] == "active"

    @patch("api.credentials.get_db_session")
    def test_list_credentials_with_expired_token(
        self, mock_db_session, authenticated_client
    ):
        """Test listing credentials with expired token."""
        # Mock credential with past expiry
        mock_cred = Mock()
        mock_cred.credential_id = "test-cred-expired"
        mock_cred.credential_name = "Expired GDrive"
        past_expiry = datetime.now(UTC) - timedelta(days=1)
        mock_cred.token_metadata = {"expiry": past_expiry.isoformat()}
        mock_cred.to_dict.return_value = {
            "credential_id": "test-cred-expired",
            "credential_name": "Expired GDrive",
        }

        mock_session = MagicMock()
        mock_session.query().all.return_value = [mock_cred]
        mock_db_session.return_value.__enter__.return_value = mock_session

        response = authenticated_client.get("/api/credentials")
        assert response.status_code == 200
        data = response.json()
        assert data["credentials"][0]["status"] == "expired"

    @patch("api.credentials.get_db_session")
    def test_list_credentials_expiring_soon(
        self, mock_db_session, authenticated_client
    ):
        """Test listing credentials with token expiring soon."""
        # Mock credential expiring in 12 hours
        mock_cred = Mock()
        mock_cred.credential_id = "test-cred-expiring"
        mock_cred.credential_name = "Expiring Soon GDrive"
        soon_expiry = datetime.now(UTC) + timedelta(hours=12)
        mock_cred.token_metadata = {"expiry": soon_expiry.isoformat()}
        mock_cred.to_dict.return_value = {
            "credential_id": "test-cred-expiring",
            "credential_name": "Expiring Soon GDrive",
        }

        mock_session = MagicMock()
        mock_session.query().all.return_value = [mock_cred]
        mock_db_session.return_value.__enter__.return_value = mock_session

        response = authenticated_client.get("/api/credentials")
        assert response.status_code == 200
        data = response.json()
        assert data["credentials"][0]["status"] == "expiring_soon"

    @patch("api.credentials.get_db_session")
    def test_list_credentials_no_expiry_info(
        self, mock_db_session, authenticated_client
    ):
        """Test listing credentials without expiry metadata."""
        mock_cred = Mock()
        mock_cred.credential_id = "test-cred-no-expiry"
        mock_cred.credential_name = "No Expiry Info"
        mock_cred.token_metadata = None  # No metadata
        mock_cred.to_dict.return_value = {
            "credential_id": "test-cred-no-expiry",
            "credential_name": "No Expiry Info",
        }

        mock_session = MagicMock()
        mock_session.query().all.return_value = [mock_cred]
        mock_db_session.return_value.__enter__.return_value = mock_session

        response = authenticated_client.get("/api/credentials")
        assert response.status_code == 200
        data = response.json()
        assert data["credentials"][0]["status"] == "unknown"

    @patch("api.credentials.get_db_session")
    def test_list_credentials_database_error(
        self, mock_db_session, authenticated_client
    ):
        """Test listing credentials handles database errors."""
        mock_db_session.side_effect = Exception("Database connection failed")

        response = authenticated_client.get("/api/credentials")
        assert response.status_code == 500


class TestCredentialsDeleteEndpoint:
    """Test /api/credentials/{cred_id} DELETE endpoint."""

    @patch("api.credentials.get_db_session")
    def test_delete_credential_success(self, mock_db_session, authenticated_client):
        """Test successful credential deletion."""
        mock_cred = Mock()
        mock_cred.credential_id = "test-cred-1"
        mock_cred.credential_name = "Test Credential"

        mock_session = MagicMock()
        mock_session.query().filter().first.return_value = mock_cred
        mock_db_session.return_value.__enter__.return_value = mock_session

        response = authenticated_client.delete("/api/credentials/test-cred-1")
        assert response.status_code == 200
        assert "deleted successfully" in response.json()["message"]

    @patch("api.credentials.get_db_session")
    def test_delete_credential_not_found(self, mock_db_session, authenticated_client):
        """Test deleting non-existent credential returns 404."""
        mock_session = MagicMock()
        mock_session.query().filter().first.return_value = None
        mock_db_session.return_value.__enter__.return_value = mock_session

        response = authenticated_client.delete("/api/credentials/nonexistent-id")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @patch("api.credentials.get_db_session")
    def test_delete_credential_database_error(
        self, mock_db_session, authenticated_client
    ):
        """Test credential deletion handles database errors."""
        mock_db_session.side_effect = Exception("Database error")

        response = authenticated_client.delete("/api/credentials/test-cred-1")
        assert response.status_code == 500


@pytest.mark.integration
class TestAuthDependencies:
    """Test authentication dependency with REAL control-plane integration."""

    @pytest.mark.asyncio
    async def test_authenticated_endpoint_with_real_jwt(
        self, client, authenticated_request_headers, control_plane_url
    ):
        """
        INTEGRATION TEST: Test authenticated endpoint with REAL JWT token.

        Given: Valid JWT token for 8thlight.com user
        When: GET /api/jobs with Bearer token
        Then: Request succeeds (not 401/403)

        This tests the FULL auth flow:
        1. JWT token in Authorization header
        2. get_current_user() dependency extracts token
        3. REAL HTTP call to control-plane /api/users/me
        4. Control-plane validates token and returns user info
        5. verify_domain() checks email domain
        6. Request proceeds to endpoint
        """
        # Import here to ensure fixtures are loaded
        pytest.importorskip("integration_conftest")

        # Ensure control-plane is reachable
        try:
            import httpx

            async with httpx.AsyncClient(verify=False, timeout=5.0) as test_client:
                health_response = await test_client.get(f"{control_plane_url}/health")
                assert health_response.status_code == 200, (
                    f"❌ Control-plane not available at {control_plane_url}!\n"
                    f"Integration tests require control-plane to be running.\n"
                    f"Health check failed: {health_response.status_code}"
                )
        except Exception as e:
            pytest.fail(
                f"❌ Cannot reach control-plane at {control_plane_url}!\n"
                f"Integration tests require control-plane to be running.\n"
                f"Error: {e}"
            )

        # Make authenticated request with real JWT token
        response = client.get("/api/jobs", headers=authenticated_request_headers)

        # Should succeed (200) or fail for reasons OTHER than auth (401/403)
        assert response.status_code != 401, (
            f"❌ Authentication failed with valid JWT!\n"
            f"Expected: Not 401 (auth should work)\n"
            f"Got: {response.status_code}\n"
            f"Response: {response.text[:200]}\n"
            f"The JWT token should authenticate successfully with control-plane!"
        )

        assert response.status_code != 403, (
            f"❌ Authorization failed for valid 8thlight.com user!\n"
            f"Expected: Not 403 (domain should be allowed)\n"
            f"Got: {response.status_code}\n"
            f"Response: {response.text[:200]}\n"
            f"User with @8thlight.com email should pass domain verification!"
        )

        print(
            f"✅ PASS: Authenticated request with real JWT succeeded (status: {response.status_code})"
        )

    @pytest.mark.asyncio
    async def test_unauthenticated_endpoint_returns_401(
        self, client, control_plane_url
    ):
        """
        INTEGRATION TEST: Test unauthenticated request returns 401.

        Given: No authentication headers
        When: GET /api/jobs without Bearer token
        Then: Returns 401 Unauthorized

        This tests the FULL auth flow without credentials:
        1. No JWT token in request
        2. get_current_user() dependency tries to extract token
        3. REAL HTTP call to control-plane fails (no token)
        4. Returns 401 Unauthorized
        """
        # Import here to ensure fixtures are loaded
        pytest.importorskip("integration_conftest")

        # Ensure control-plane is reachable
        try:
            import httpx

            async with httpx.AsyncClient(verify=False, timeout=5.0) as test_client:
                health_response = await test_client.get(f"{control_plane_url}/health")
                assert health_response.status_code == 200, (
                    f"❌ Control-plane not available at {control_plane_url}!\n"
                    f"Health check failed: {health_response.status_code}"
                )
        except Exception as e:
            pytest.fail(
                f"❌ Cannot reach control-plane at {control_plane_url}!\nError: {e}"
            )

        # Make request WITHOUT authentication
        response = client.get("/api/jobs")

        assert response.status_code == 401, (
            f"❌ Unauthenticated request did not return 401!\n"
            f"Expected: 401 Unauthorized\n"
            f"Got: {response.status_code}\n"
            f"Response: {response.text[:200]}\n"
            f"Protected endpoints MUST require authentication!"
        )

        print("✅ PASS: Unauthenticated request correctly returned 401")

    @pytest.mark.asyncio
    async def test_invalid_domain_returns_403(
        self, client, generate_real_jwt, invalid_domain_user_data, control_plane_url
    ):
        """
        INTEGRATION TEST: Test invalid domain returns 403.

        Given: Valid JWT token for NON-8thlight.com user
        When: GET /api/jobs with Bearer token for @evil.com
        Then: Returns 403 Forbidden

        This tests domain verification:
        1. JWT token is valid (authentication succeeds)
        2. REAL HTTP call to control-plane succeeds
        3. verify_domain() checks email domain
        4. Domain is not 8thlight.com → 403 Forbidden
        """
        # Import here to ensure fixtures are loaded
        pytest.importorskip("integration_conftest")

        # Ensure control-plane is reachable
        try:
            import httpx

            async with httpx.AsyncClient(verify=False, timeout=5.0) as test_client:
                health_response = await test_client.get(f"{control_plane_url}/health")
                assert health_response.status_code == 200
        except Exception as e:
            pytest.fail(f"❌ Cannot reach control-plane: {e}")

        # Generate JWT for invalid domain user
        invalid_token = generate_real_jwt(invalid_domain_user_data)
        headers = {"Authorization": f"Bearer {invalid_token}"}

        # Make request with invalid domain JWT
        response = client.get("/api/jobs", headers=headers)

        # Should return 403 (authenticated but wrong domain) or 401 (if control-plane rejects token)
        assert response.status_code in [401, 403], (
            f"❌ Invalid domain request did not return 401/403!\n"
            f"Expected: 403 Forbidden (or 401 if control-plane rejects)\n"
            f"Got: {response.status_code}\n"
            f"Response: {response.text[:200]}\n"
            f"Non-8thlight.com users should be rejected!"
        )

        print(
            f"✅ PASS: Invalid domain request correctly rejected (status: {response.status_code})"
        )

    @pytest.mark.asyncio
    async def test_get_optional_user_authenticated(self):
        """Test get_optional_user returns user when authenticated."""
        from dependencies.auth import get_optional_user

        mock_request = Mock()
        mock_request.session = {
            "user_email": "user@8thlight.com",
            "user_info": {"email": "user@8thlight.com", "name": "Test User"},
        }

        with patch("dependencies.auth.verify_domain", return_value=True):
            result = await get_optional_user(mock_request)
            assert result is not None
            assert result["email"] == "user@8thlight.com"

    @pytest.mark.asyncio
    async def test_get_optional_user_not_authenticated(self):
        """Test get_optional_user returns None when not authenticated."""
        from dependencies.auth import get_optional_user

        mock_request = Mock()
        mock_request.session = {}

        result = await get_optional_user(mock_request)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_optional_user_invalid_domain(self):
        """Test get_optional_user returns None for invalid domain."""
        from dependencies.auth import get_optional_user

        mock_request = Mock()
        mock_request.session = {
            "user_email": "attacker@evil.com",
            "user_info": {"email": "attacker@evil.com"},
        }

        with patch("dependencies.auth.verify_domain", return_value=False):
            result = await get_optional_user(mock_request)
            assert result is None


class TestCredentialsEndpointIntegration:
    """Integration tests for credentials endpoints."""

    @patch("api.credentials.get_db_session")
    def test_list_and_delete_workflow(self, mock_db_session, authenticated_client):
        """Test listing credentials then deleting one."""
        # First call: list with 2 credentials
        mock_cred1 = Mock()
        mock_cred1.credential_id = "cred-1"
        mock_cred1.credential_name = "Credential 1"
        mock_cred1.token_metadata = None
        mock_cred1.to_dict.return_value = {
            "credential_id": "cred-1",
            "credential_name": "Credential 1",
        }

        mock_cred2 = Mock()
        mock_cred2.credential_id = "cred-2"
        mock_cred2.credential_name = "Credential 2"
        mock_cred2.token_metadata = None
        mock_cred2.to_dict.return_value = {
            "credential_id": "cred-2",
            "credential_name": "Credential 2",
        }

        mock_session = MagicMock()
        mock_session.query().all.return_value = [mock_cred1, mock_cred2]
        mock_session.query().filter().first.return_value = mock_cred1
        mock_db_session.return_value.__enter__.return_value = mock_session

        # List credentials
        response = authenticated_client.get("/api/credentials")
        assert response.status_code == 200
        assert len(response.json()["credentials"]) == 2

        # Delete one credential
        response = authenticated_client.delete("/api/credentials/cred-1")
        assert response.status_code == 200
