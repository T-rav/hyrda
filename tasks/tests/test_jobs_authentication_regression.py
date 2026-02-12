"""
REGRESSION TESTS: Jobs API Authentication

These tests prevent the authentication regression where:
1. Scheduler has jobs loaded (5 jobs in database)
2. API returns empty jobs list {"jobs": []}
3. Root cause: Session cookies not forwarded to control-plane for auth

This happened multiple times during development. These tests ensure it never happens again.
"""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient


class TestJobsAPIAuthenticationRegression:
    """
    CRITICAL REGRESSION TESTS: Ensure /api/jobs always requires and validates auth.

    Background:
    - Scheduler loaded 5 jobs from database successfully
    - API endpoint returned {"jobs": []} (empty list)
    - Users could see UI but got "0 tasks" on dashboard
    - Root cause: Auth dependency not properly forwarding cookies to control-plane
    """

    def test_api_jobs_requires_authentication(self, app):
        """REGRESSION: /api/jobs must return 401 when not authenticated."""
        from dependencies.auth import get_current_user

        async def override_get_current_user():
            raise HTTPException(status_code=401, detail="Not authenticated")

        app.dependency_overrides[get_current_user] = override_get_current_user

        client = TestClient(app)
        response = client.get("/api/jobs")

        # CRITICAL: Must return 401, not 200 with empty jobs
        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

        app.dependency_overrides.clear()

    @patch("api.jobs.get_db_session")
    def test_api_jobs_returns_scheduler_jobs_when_authenticated(
        self, mock_db_session, app
    ):
        """REGRESSION: /api/jobs must return actual jobs from scheduler when authenticated."""
        from dependencies.auth import get_current_user

        # Override auth to return authenticated user
        async def override_get_current_user():
            return {"email": "user@8thlight.com", "name": "Test User", "is_admin": True}

        app.dependency_overrides[get_current_user] = override_get_current_user

        # Mock scheduler with 5 jobs (like production)
        mock_scheduler = MagicMock()
        mock_job1 = Mock()
        mock_job1.id = "gdrive_ingest_job1"
        mock_job2 = Mock()
        mock_job2.id = "slack_user_import_job1"
        mock_job3 = Mock()
        mock_job3.id = "website_scrape_job1"
        mock_job4 = Mock()
        mock_job4.id = "youtube_ingest_job1"
        mock_job5 = Mock()
        mock_job5.id = "gdrive_ingest_job2"

        mock_scheduler.get_jobs.return_value = [
            mock_job1,
            mock_job2,
            mock_job3,
            mock_job4,
            mock_job5,
        ]
        mock_scheduler.get_job_info.side_effect = [
            {
                "id": "gdrive_ingest_job1",
                "name": "Google Drive Ingestion",
                "next_run_time": "2024-01-20T10:00:00Z",
            },
            {
                "id": "slack_user_import_job1",
                "name": "Slack User Import",
                "next_run_time": None,
            },
            {
                "id": "website_scrape_job1",
                "name": "Website Scraping",
                "next_run_time": None,
            },
            {
                "id": "youtube_ingest_job1",
                "name": "YouTube Channel Ingestion",
                "next_run_time": None,
            },
            {
                "id": "gdrive_ingest_job2",
                "name": "Google Drive Ingestion",
                "next_run_time": "2026-02-11T16:42:04Z",
            },
        ]

        # Mock empty metadata
        mock_session = MagicMock()
        mock_session.query().all.return_value = []
        mock_db_session.return_value.__enter__.return_value = mock_session

        app.state.scheduler_service = mock_scheduler

        client = TestClient(app)
        response = client.get("/api/jobs")

        # CRITICAL: Must return 200 with actual jobs, not empty list
        assert response.status_code == 200
        data = response.json()
        assert "jobs" in data
        assert len(data["jobs"]) == 5  # Must have all 5 jobs
        assert data["jobs"][0]["id"] == "gdrive_ingest_job1"
        assert data["jobs"][4]["id"] == "gdrive_ingest_job2"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_auth_dependency_forwards_cookies_to_control_plane(self):
        """REGRESSION: Auth dependency must forward cookies to control-plane for validation."""
        with patch("httpx.AsyncClient") as mock_async_client:
            from fastapi import Request

            from dependencies.auth import get_current_user

            # Mock control-plane response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "email": "user@8thlight.com",
                "name": "Test User",
            }

            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_async_client.return_value.__aenter__.return_value = (
                mock_client_instance
            )

            # Create mock request with session cookies
            mock_request = Mock(spec=Request)
            mock_request.cookies = {
                "session": "test-session-id",
                "access_token": "test-jwt-token",
            }
            mock_request.headers.get.return_value = None

            # Call the dependency
            user = await get_current_user(mock_request)

            # CRITICAL: Verify cookies were forwarded to control-plane
            mock_client_instance.get.assert_called_once()
            call_args = mock_client_instance.get.call_args
            assert call_args[1]["cookies"] == mock_request.cookies
            assert "session" in call_args[1]["cookies"]
            assert "access_token" in call_args[1]["cookies"]

            # Verify user was returned
            assert user["email"] == "user@8thlight.com"

    @pytest.mark.asyncio
    async def test_auth_dependency_returns_401_when_control_plane_returns_401(self):
        """REGRESSION: Auth dependency must propagate 401 from control-plane."""
        with patch("httpx.AsyncClient") as mock_async_client:
            from fastapi import Request

            from dependencies.auth import get_current_user

            # Mock control-plane 401 response
            mock_response = Mock()
            mock_response.status_code = 401

            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_async_client.return_value.__aenter__.return_value = (
                mock_client_instance
            )

            # Create mock request
            mock_request = Mock(spec=Request)
            mock_request.cookies = {}
            mock_request.headers.get.return_value = None

            # Call the dependency - should raise HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_request)

            # CRITICAL: Must raise 401, not return None or empty dict
            assert exc_info.value.status_code == 401
            assert "Not authenticated" in exc_info.value.detail

    def test_scheduler_info_requires_authentication(self, app):
        """REGRESSION: /api/scheduler/info must also require authentication."""
        from dependencies.auth import get_current_user

        async def override_get_current_user():
            raise HTTPException(status_code=401, detail="Not authenticated")

        app.dependency_overrides[get_current_user] = override_get_current_user

        client = TestClient(app)
        response = client.get("/api/scheduler/info")

        # CRITICAL: Must return 401, not 200
        assert response.status_code == 401

        app.dependency_overrides.clear()

    def test_task_runs_requires_authentication(self, app):
        """REGRESSION: /api/task-runs must also require authentication."""
        from dependencies.auth import get_current_user

        async def override_get_current_user():
            raise HTTPException(status_code=401, detail="Not authenticated")

        app.dependency_overrides[get_current_user] = override_get_current_user

        client = TestClient(app)
        response = client.get("/api/task-runs")

        # CRITICAL: Must return 401, not 200
        assert response.status_code == 401

        app.dependency_overrides.clear()

    @patch("api.jobs.get_db_session")
    def test_jobs_api_with_credentials_include_from_browser(self, mock_db_session, app):
        """
        REGRESSION: Browser sends credentials:'include', API must accept and validate.

        This simulates the actual browser behavior where fetch() uses credentials:'include'.
        """
        from dependencies.auth import get_current_user

        # Override auth to simulate successful control-plane validation
        async def override_get_current_user():
            return {"email": "user@8thlight.com", "name": "Test User", "is_admin": True}

        app.dependency_overrides[get_current_user] = override_get_current_user

        # Mock scheduler with jobs
        mock_scheduler = MagicMock()
        mock_job = Mock()
        mock_job.id = "test-job-1"
        mock_scheduler.get_jobs.return_value = [mock_job]
        mock_scheduler.get_job_info.return_value = {
            "id": "test-job-1",
            "name": "Test Job",
            "next_run_time": "2024-01-20T10:00:00Z",
        }

        # Mock empty metadata
        mock_session = MagicMock()
        mock_session.query().all.return_value = []
        mock_db_session.return_value.__enter__.return_value = mock_session

        app.state.scheduler_service = mock_scheduler

        # Simulate browser request with cookies (credentials: 'include')
        client = TestClient(app)
        response = client.get(
            "/api/jobs",
            cookies={"session": "test-session", "access_token": "test-token"},
        )

        # CRITICAL: Must return 200 with jobs, not 401 or empty
        assert response.status_code == 200
        data = response.json()
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["id"] == "test-job-1"

        app.dependency_overrides.clear()


class TestAuthEndpointProxyToControlPlane:
    """Test /auth/me endpoint that proxies to control-plane."""

    @pytest.mark.asyncio
    async def test_auth_me_forwards_cookies_to_control_plane(self):
        """REGRESSION: /auth/me must forward cookies to control-plane."""
        with patch("httpx.AsyncClient") as mock_async_client:
            from fastapi import Request

            from api.auth import get_current_user as auth_me_endpoint

            # Mock control-plane response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"email": "user@8thlight.com"}

            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_async_client.return_value.__aenter__.return_value = (
                mock_client_instance
            )

            # Create mock request with cookies
            mock_request = Mock(spec=Request)
            mock_request.cookies = {
                "session": "test-session",
                "access_token": "test-token",
            }

            # Call the endpoint
            await auth_me_endpoint(mock_request)

            # Verify cookies were forwarded
            mock_client_instance.get.assert_called_once()
            call_args = mock_client_instance.get.call_args
            assert call_args[1]["cookies"] == mock_request.cookies

    @pytest.mark.asyncio
    async def test_auth_me_returns_401_when_not_authenticated(self):
        """REGRESSION: /auth/me must return 401 when control-plane says not authenticated."""
        with patch("httpx.AsyncClient") as mock_async_client:
            from fastapi import Request

            from api.auth import get_current_user as auth_me_endpoint

            # Mock control-plane 401 response
            mock_response = Mock()
            mock_response.status_code = 401

            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_async_client.return_value.__aenter__.return_value = (
                mock_client_instance
            )

            # Create mock request
            mock_request = Mock(spec=Request)
            mock_request.cookies = {}

            # Call the endpoint
            response = await auth_me_endpoint(mock_request)

            # Must return JSONResponse with 401
            assert response.status_code == 401
            assert (
                response.body == b'{"authenticated":false,"error":"Not authenticated"}'
            )
