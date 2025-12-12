"""Tests for Google Drive ingestion job.

These tests focus on validation logic and parameter handling.
Integration tests with actual database/services would require complex test infrastructure.
"""

from unittest.mock import Mock

import pytest

from config.settings import TasksSettings
from jobs.system.gdrive_ingest.job import GDriveIngestJob


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = Mock(spec=TasksSettings)
    settings.tasks_port = 5001
    settings.tasks_host = "localhost"
    return settings


class TestGDriveIngestJobValidation:
    """Test job parameter validation."""

    def test_job_name_and_description(self, mock_settings):
        """Test job has proper name and description."""
        job = GDriveIngestJob(mock_settings, folder_id="test-folder")
        assert job.JOB_NAME == "Google Drive Ingestion"
        assert "OAuth" in job.JOB_DESCRIPTION

    def test_requires_folder_or_file_id(self, mock_settings):
        """Test job requires either folder_id or file_id."""
        with pytest.raises(
            ValueError, match="Must provide either 'folder_id' or 'file_id'"
        ):
            GDriveIngestJob(mock_settings)

    def test_cannot_provide_both_folder_and_file_id(self, mock_settings):
        """Test job rejects both folder_id and file_id."""
        with pytest.raises(ValueError, match="Cannot provide both"):
            GDriveIngestJob(mock_settings, folder_id="folder", file_id="file")

    def test_accepts_folder_id_only(self, mock_settings):
        """Test job accepts folder_id parameter."""
        job = GDriveIngestJob(mock_settings, folder_id="test-folder")
        assert job.params["folder_id"] == "test-folder"

    def test_accepts_file_id_only(self, mock_settings):
        """Test job accepts file_id parameter."""
        job = GDriveIngestJob(mock_settings, file_id="test-file")
        assert job.params["file_id"] == "test-file"

    def test_optional_parameters(self, mock_settings):
        """Test job accepts optional parameters."""
        job = GDriveIngestJob(
            mock_settings,
            folder_id="test-folder",
            recursive=False,
            metadata={"department": "engineering"},
            credential_id="cred-123",
        )
        assert job.params["recursive"] is False
        assert job.params["metadata"] == {"department": "engineering"}
        assert job.params["credential_id"] == "cred-123"


class TestGDriveIngestJobExecution:
    """Test job execution logic - basic tests only."""

    @pytest.mark.asyncio
    async def test_requires_credential_id(self, mock_settings):
        """Test job fails without credential_id."""
        job = GDriveIngestJob(mock_settings, folder_id="test-folder")

        with pytest.raises(ValueError, match="credential_id is required"):
            await job._execute_job()

    def test_job_has_required_attributes(self, mock_settings):
        """Test job has all required attributes."""
        job = GDriveIngestJob(
            mock_settings, folder_id="test-folder", credential_id="cred-123"
        )

        assert hasattr(job, "JOB_NAME")
        assert hasattr(job, "JOB_DESCRIPTION")
        assert hasattr(job, "REQUIRED_PARAMS")
        assert hasattr(job, "OPTIONAL_PARAMS")
        assert hasattr(job, "params")

    def test_job_stores_parameters(self, mock_settings):
        """Test job properly stores all parameters."""
        job = GDriveIngestJob(
            mock_settings,
            folder_id="test-folder",
            credential_id="cred-123",
            recursive=False,
            metadata={"key": "value"},
        )

        assert job.params["folder_id"] == "test-folder"
        assert job.params["credential_id"] == "cred-123"
        assert job.params["recursive"] is False
        assert job.params["metadata"] == {"key": "value"}


class TestGDriveIngestJobParamGroups:
    """Test parameter group validation."""

    def test_param_groups_defined(self, mock_settings):
        """Test job defines parameter groups."""
        job = GDriveIngestJob(mock_settings, folder_id="test-folder")
        assert hasattr(job, "PARAM_GROUPS")
        assert len(job.PARAM_GROUPS) > 0

    def test_source_param_group(self, mock_settings):
        """Test source parameter group configuration."""
        job = GDriveIngestJob(mock_settings, folder_id="test-folder")
        source_group = [g for g in job.PARAM_GROUPS if g["name"] == "source"][0]

        assert source_group["min_required"] == 1
        assert source_group["max_required"] == 1
        assert "folder_id" in source_group["params"]
        assert "file_id" in source_group["params"]
