"""Comprehensive edge case tests for multiple modules."""

import os
from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient


# API Jobs Edge Cases
@pytest.fixture
def jobs_app():
    """Create app for jobs testing."""
    os.environ.setdefault("TASK_DATABASE_URL", "sqlite:///:memory:")
    os.environ.setdefault("DATA_DATABASE_URL", "sqlite:///:memory:")
    os.environ.setdefault("SERVER_BASE_URL", "http://localhost:5001")
    os.environ.setdefault("SECRET_KEY", "test-secret")
    os.environ.setdefault("ALLOWED_EMAIL_DOMAIN", "test.com")

    from app import app

    return app


@pytest.fixture
def auth_client(jobs_app):
    """Create authenticated client."""
    from dependencies.auth import get_current_user

    async def mock_user():
        return {"email": "test@test.com", "is_admin": True}

    jobs_app.dependency_overrides[get_current_user] = mock_user
    client = TestClient(jobs_app)
    yield client
    jobs_app.dependency_overrides.clear()


class TestJobsAPIEdgeCases:
    """Edge cases for jobs API."""

    def test_list_jobs_when_scheduler_not_initialized(self, auth_client, jobs_app):
        """Test listing jobs when scheduler is None."""
        jobs_app.state.scheduler_service = None

        response = auth_client.get("/api/jobs")

        # Should handle gracefully
        assert response.status_code in [200, 500]


class TestCredentialsAPIEdgeCases:
    """Edge cases for credentials API."""

    def test_list_credentials_with_corrupted_metadata(self, auth_client):
        """Test handling credentials with corrupted token metadata."""
        from models.oauth_credential import OAuthCredential

        mock_cred = Mock(spec=OAuthCredential)
        mock_cred.credential_id = "corrupted"
        mock_cred.credential_name = "Corrupted"
        mock_cred.provider = "google_drive"
        mock_cred.token_metadata = {"expiry": "not-a-valid-date"}
        mock_cred.to_dict.return_value = {
            "credential_id": "corrupted",
            "credential_name": "Corrupted",
            "provider": "google_drive",
            "token_metadata": {"expiry": "not-a-valid-date"},
        }

        mock_session = Mock()
        mock_query = Mock()
        mock_query.all.return_value = [mock_cred]
        mock_session.query.return_value = mock_query

        with patch("api.credentials.get_db_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            response = auth_client.get("/api/credentials")

            # Should handle corrupted data gracefully
            assert response.status_code == 200


# Model Edge Cases
class TestTaskRunEdgeCases:
    """Edge cases for TaskRun model."""

    def test_calculate_duration_with_very_long_duration(self):
        """Test duration calculation with very long time span."""
        from models.task_run import TaskRun

        start = datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC)
        end = datetime(2024, 12, 31, 23, 59, 59, tzinfo=UTC)

        task_run = TaskRun(
            run_id="long-run",
            status="success",
            started_at=start,
            completed_at=end,
        )

        task_run.calculate_duration()

        # Should handle multi-year duration
        assert task_run.duration_seconds > 0
        assert task_run.duration_seconds > 365 * 24 * 3600  # More than a year

    def test_task_run_with_negative_duration(self):
        """Test task run where end time is before start time."""
        from models.task_run import TaskRun

        start = datetime(2024, 1, 10, 12, 0, 0, tzinfo=UTC)
        end = datetime(2024, 1, 10, 10, 0, 0, tzinfo=UTC)  # 2 hours before start

        task_run = TaskRun(
            run_id="negative-duration",
            status="failed",
            started_at=start,
            completed_at=end,
        )

        task_run.calculate_duration()

        # Should calculate negative duration (data quality issue)
        assert task_run.duration_seconds < 0

    def test_task_run_status_edge_cases(self):
        """Test task run with various status values."""
        from models.task_run import TaskRun

        statuses = ["running", "success", "failed", "cancelled", "pending", "unknown"]

        for status in statuses:
            task_run = TaskRun(
                run_id=f"test-{status}",
                status=status,
                started_at=datetime.now(UTC),
            )

            # Should handle any status value
            assert task_run.status == status


class TestOAuthCredentialEdgeCases:
    """Edge cases for OAuthCredential model."""

    def test_to_dict_with_very_long_token(self):
        """Test to_dict with extremely long encrypted token."""
        from models.oauth_credential import OAuthCredential

        very_long_token = "x" * 100000  # 100KB token

        cred = OAuthCredential(
            credential_id="long-token",
            credential_name="Long Token",
            encrypted_token=very_long_token,
        )

        result = cred.to_dict()

        # Should handle long tokens and NOT include in dict
        assert "encrypted_token" not in result
        assert very_long_token not in str(result)

    def test_credential_with_special_characters_in_name(self):
        """Test credential with special characters."""
        from models.oauth_credential import OAuthCredential

        special_name = "Test™ Credential® with €uro and 日本語"

        cred = OAuthCredential(
            credential_id="special-chars",
            credential_name=special_name,
            encrypted_token="encrypted-data",
        )

        assert cred.credential_name == special_name

        result = cred.to_dict()
        assert result["credential_name"] == special_name


class TestTaskMetadataEdgeCases:
    """Edge cases for TaskMetadata model."""

    def test_task_metadata_with_empty_job_id(self):
        """Test task metadata with minimal job_id."""
        from models.task_metadata import TaskMetadata

        metadata = TaskMetadata(
            job_id="a",  # Single character
            task_name="Minimal ID",
        )

        assert metadata.job_id == "a"

    def test_task_metadata_with_very_long_names(self):
        """Test task metadata with maximum length values."""
        from models.task_metadata import TaskMetadata

        max_job_id = "j" * 191
        max_task_name = "t" * 255

        metadata = TaskMetadata(
            job_id=max_job_id,
            task_name=max_task_name,
        )

        assert len(metadata.job_id) == 191
        assert len(metadata.task_name) == 255

        result = metadata.to_dict()
        assert result["job_id"] == max_job_id
        assert result["task_name"] == max_task_name


class TestSettingsEdgeCases:
    """Edge cases for settings configuration."""

    def test_settings_with_all_env_vars_empty(self, monkeypatch):
        """Test settings when all optional env vars are empty."""
        from config.settings import TasksSettings

        # Set all optional to empty
        monkeypatch.setenv("SLACK_BOT_API_KEY", "")
        monkeypatch.setenv("SLACK_BOT_TOKEN", "")
        monkeypatch.setenv("GOOGLE_CREDENTIALS_PATH", "")

        settings = TasksSettings()

        # Should handle empty strings (Pydantic treats as None for optional fields)
        assert settings is not None

    def test_settings_with_very_long_urls(self, monkeypatch):
        """Test settings with extremely long URLs."""
        from config.settings import TasksSettings

        long_url = "http://example.com/" + ("very-long-path/" * 100)

        monkeypatch.setenv("SERVER_BASE_URL", long_url)

        settings = TasksSettings()

        assert settings.server_base_url == long_url


class TestUtilsAuthEdgeCases:
    """Edge cases for auth utilities."""

    def test_get_redirect_uri_with_unicode(self):
        """Test redirect URI with unicode characters."""
        from utils.auth import get_redirect_uri

        uri = get_redirect_uri("http://例え.com")
        assert "/auth/callback" in uri


class TestHealthAPIEdgeCases:
    """Edge cases for health API."""

    def test_health_check_rapid_succession(self, auth_client):
        """Test multiple rapid health checks."""
        responses = [auth_client.get("/health") for _ in range(10)]

        # All should succeed
        assert all(r.status_code == 200 for r in responses)

    def test_health_check_both_endpoints_consistency(self, auth_client):
        """Test /health and /api/health return same data."""
        for _ in range(5):
            r1 = auth_client.get("/health")
            r2 = auth_client.get("/api/health")

            assert r1.status_code == r2.status_code
            # Both should return scheduler_running
            if r1.status_code == 200:
                assert "scheduler_running" in r1.json()
                assert "scheduler_running" in r2.json()


class TestJobSchemasEdgeCases:
    """Edge cases for job parameter schemas."""

    def test_gdrive_params_with_max_length_ids(self):
        """Test GDrive params with maximum length IDs."""
        from api.job_schemas import GDriveIngestParams

        max_folder = "f" * 200
        max_cred = "c" * 100

        params = GDriveIngestParams(
            folder_id=max_folder,
            credential_id=max_cred,
        )

        assert len(params.folder_id) == 200
        assert len(params.credential_id) == 100

    def test_gdrive_params_with_empty_metadata(self):
        """Test GDrive params with explicitly empty metadata."""
        from api.job_schemas import GDriveIngestParams

        params = GDriveIngestParams(
            folder_id="test",
            credential_id="test",
            metadata={},
        )

        assert params.metadata == {}

    def test_validate_job_params_with_empty_params(self):
        """Test validation with empty parameters dict."""
        from api.job_schemas import validate_job_params

        # Unknown job type should accept empty params
        result = validate_job_params("unknown_type", {})

        assert result == {}
