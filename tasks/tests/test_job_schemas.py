"""Tests for job parameter validation schemas (api/job_schemas.py)."""

import json

import pytest
from pydantic import ValidationError

from api.job_schemas import GDriveIngestParams, validate_job_params


class TestGDriveIngestParams:
    """Test GDriveIngestParams validation."""

    def test_valid_params_with_folder_id(self):
        """Test creating params with valid folder_id."""
        params = GDriveIngestParams(
            folder_id="test-folder-123",
            credential_id="prod_gdrive",
            recursive=True,
            metadata={"source": "test", "priority": 1},
        )
        assert params.folder_id == "test-folder-123"
        assert params.credential_id == "prod_gdrive"
        assert params.recursive is True
        assert params.metadata == {"source": "test", "priority": 1}
        assert params.file_id is None

    def test_valid_params_with_file_id(self):
        """Test creating params with valid file_id."""
        params = GDriveIngestParams(
            file_id="test-file-456",
            credential_id="prod_gdrive",
            recursive=False,
        )
        assert params.file_id == "test-file-456"
        assert params.credential_id == "prod_gdrive"
        assert params.recursive is False
        assert params.folder_id is None

    def test_defaults(self):
        """Test default values for optional fields."""
        params = GDriveIngestParams(
            folder_id="test-folder",
            credential_id="test-cred",
        )
        assert params.recursive is True
        assert params.metadata == {}

    def test_missing_both_folder_and_file_id(self):
        """Test validation fails when neither folder_id nor file_id provided."""
        with pytest.raises(ValidationError) as exc_info:
            GDriveIngestParams(
                credential_id="test-cred",
            )
        assert "Must provide either 'folder_id' or 'file_id'" in str(exc_info.value)

    def test_both_folder_and_file_id(self):
        """Test validation fails when both folder_id and file_id provided."""
        with pytest.raises(ValidationError) as exc_info:
            GDriveIngestParams(
                folder_id="test-folder",
                file_id="test-file",
                credential_id="test-cred",
            )
        assert "Cannot provide both 'folder_id' and 'file_id'" in str(exc_info.value)

    def test_missing_credential_id(self):
        """Test validation fails when credential_id is missing."""
        with pytest.raises(ValidationError) as exc_info:
            GDriveIngestParams(folder_id="test-folder")
        assert "credential_id" in str(exc_info.value)

    def test_empty_folder_id(self):
        """Test validation fails with empty folder_id."""
        with pytest.raises(ValidationError) as exc_info:
            GDriveIngestParams(
                folder_id="",
                credential_id="test-cred",
            )
        assert "at least 1 character" in str(exc_info.value).lower()

    def test_empty_credential_id(self):
        """Test validation fails with empty credential_id."""
        with pytest.raises(ValidationError) as exc_info:
            GDriveIngestParams(
                folder_id="test-folder",
                credential_id="",
            )
        assert "at least 1 character" in str(exc_info.value).lower()

    def test_folder_id_too_long(self):
        """Test validation fails when folder_id exceeds max length."""
        long_id = "x" * 201
        with pytest.raises(ValidationError) as exc_info:
            GDriveIngestParams(
                folder_id=long_id,
                credential_id="test-cred",
            )
        assert "at most 200 characters" in str(exc_info.value).lower()

    def test_credential_id_too_long(self):
        """Test validation fails when credential_id exceeds max length."""
        long_id = "x" * 101
        with pytest.raises(ValidationError) as exc_info:
            GDriveIngestParams(
                folder_id="test-folder",
                credential_id=long_id,
            )
        assert "at most 100 characters" in str(exc_info.value).lower()


class TestMetadataValidation:
    """Test metadata validation logic."""

    def test_valid_metadata_simple_types(self):
        """Test metadata with valid simple types."""
        params = GDriveIngestParams(
            folder_id="test-folder",
            credential_id="test-cred",
            metadata={
                "string_val": "test",
                "int_val": 42,
                "float_val": 3.14,
                "bool_val": True,
                "null_val": None,
            },
        )
        assert params.metadata["string_val"] == "test"
        assert params.metadata["int_val"] == 42
        assert params.metadata["float_val"] == 3.14
        assert params.metadata["bool_val"] is True
        assert params.metadata["null_val"] is None

    def test_metadata_empty_dict(self):
        """Test empty metadata is allowed."""
        params = GDriveIngestParams(
            folder_id="test-folder",
            credential_id="test-cred",
            metadata={},
        )
        assert params.metadata == {}

    def test_metadata_not_dict(self):
        """Test metadata validation fails with non-dict type."""
        with pytest.raises(ValidationError) as exc_info:
            GDriveIngestParams(
                folder_id="test-folder",
                credential_id="test-cred",
                metadata="not a dict",  # type: ignore
            )
        # Pydantic v2 error message
        error_str = str(exc_info.value)
        assert (
            "Input should be a valid dictionary" in error_str
            or "metadata must be a dictionary" in error_str
        )

    def test_metadata_with_list_value(self):
        """Test metadata validation fails with list value."""
        with pytest.raises(ValidationError) as exc_info:
            GDriveIngestParams(
                folder_id="test-folder",
                credential_id="test-cred",
                metadata={"items": ["a", "b", "c"]},
            )
        assert "metadata values must be simple types" in str(exc_info.value)

    def test_metadata_with_dict_value(self):
        """Test metadata validation fails with nested dict value."""
        with pytest.raises(ValidationError) as exc_info:
            GDriveIngestParams(
                folder_id="test-folder",
                credential_id="test-cred",
                metadata={"nested": {"key": "value"}},
            )
        assert "metadata values must be simple types" in str(exc_info.value)

    def test_metadata_with_non_string_key(self):
        """Test metadata validation fails with non-string keys."""
        with pytest.raises(ValidationError) as exc_info:
            GDriveIngestParams(
                folder_id="test-folder",
                credential_id="test-cred",
                metadata={123: "value"},  # type: ignore
            )
        # Pydantic will catch this at the dict level
        assert "metadata" in str(exc_info.value).lower()

    def test_metadata_exceeds_size_limit(self):
        """Test metadata validation fails when size exceeds 10KB."""
        # Create metadata that exceeds 10KB when serialized
        large_value = "x" * 9000
        large_metadata = {
            "large1": large_value,
            "large2": large_value,
        }

        with pytest.raises(ValidationError) as exc_info:
            GDriveIngestParams(
                folder_id="test-folder",
                credential_id="test-cred",
                metadata=large_metadata,
            )
        assert "exceeds maximum size of 10KB" in str(exc_info.value)

    def test_metadata_at_size_limit(self):
        """Test metadata at exactly size limit is accepted."""
        # Create metadata just under 10KB
        value = "x" * 4000
        metadata = {"val1": value, "val2": value}

        # Verify it's under 10KB
        metadata_json = json.dumps(metadata)
        assert len(metadata_json) < 10000

        params = GDriveIngestParams(
            folder_id="test-folder",
            credential_id="test-cred",
            metadata=metadata,
        )
        assert params.metadata == metadata


class TestValidateJobParams:
    """Test validate_job_params function."""

    def test_validate_known_job_type_valid_params(self):
        """Test validating known job type with valid parameters."""
        params = {
            "folder_id": "test-folder-123",
            "credential_id": "prod_gdrive",
            "recursive": True,
            "metadata": {"source": "test"},
        }

        result = validate_job_params("google_drive_ingest", params)

        assert result["folder_id"] == "test-folder-123"
        assert result["credential_id"] == "prod_gdrive"
        assert result["recursive"] is True
        assert result["metadata"] == {"source": "test"}

    def test_validate_known_job_type_invalid_params(self):
        """Test validating known job type with invalid parameters."""
        params = {
            # Missing both folder_id and file_id
            "credential_id": "test-cred",
        }

        with pytest.raises(ValueError) as exc_info:
            validate_job_params("google_drive_ingest", params)

        assert "Invalid parameters for job type 'google_drive_ingest'" in str(
            exc_info.value
        )
        assert "Must provide either 'folder_id' or 'file_id'" in str(exc_info.value)

    def test_validate_unknown_job_type_returns_params_as_is(self):
        """Test unknown job type returns parameters without validation."""
        params = {
            "custom_param1": "value1",
            "custom_param2": 42,
        }

        result = validate_job_params("unknown_job_type", params)

        # Should return params unchanged (no validation)
        assert result == params

    def test_validate_unknown_job_type_logs_warning(self, caplog):
        """Test unknown job type logs warning."""
        import logging

        caplog.set_level(logging.WARNING)

        params = {"custom": "param"}
        validate_job_params("custom_job", params)

        assert "No validation schema for job type 'custom_job'" in caplog.text
        assert "Parameters accepted as-is" in caplog.text

    def test_validate_with_extra_params_for_known_type(self):
        """Test validation strips extra params for known types."""
        params = {
            "folder_id": "test-folder",
            "credential_id": "test-cred",
            "extra_param": "should_be_ignored",  # Extra param
        }

        result = validate_job_params("google_drive_ingest", params)

        # Pydantic strips extra fields by default
        assert "extra_param" not in result
        assert result["folder_id"] == "test-folder"
        assert result["credential_id"] == "test-cred"

    def test_validate_returns_dict(self):
        """Test validate_job_params returns dict, not Pydantic model."""
        params = {
            "file_id": "test-file",
            "credential_id": "test-cred",
        }

        result = validate_job_params("google_drive_ingest", params)

        assert isinstance(result, dict)
        assert not hasattr(result, "model_dump")

    def test_validate_with_missing_required_field(self):
        """Test validation fails when required field is missing."""
        params = {
            "folder_id": "test-folder",
            # Missing credential_id (required)
        }

        with pytest.raises(ValueError) as exc_info:
            validate_job_params("google_drive_ingest", params)

        assert "Invalid parameters for job type 'google_drive_ingest'" in str(
            exc_info.value
        )
        assert "credential_id" in str(exc_info.value)

    def test_validate_with_type_mismatch(self):
        """Test validation fails with wrong parameter type."""
        params = {
            "folder_id": "test-folder",
            "credential_id": "test-cred",
            "recursive": "not_a_boolean",  # Wrong type
        }

        with pytest.raises(ValueError) as exc_info:
            validate_job_params("google_drive_ingest", params)

        assert "Invalid parameters for job type 'google_drive_ingest'" in str(
            exc_info.value
        )
