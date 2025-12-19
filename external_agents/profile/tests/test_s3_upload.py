"""Tests for S3 report upload functionality."""

import os
from unittest.mock import MagicMock, patch

import pytest


def test_upload_report_to_s3_success():
    """Test successful report upload to S3."""
    from external_agents.profile.nodes.final_report import upload_report_to_s3

    mock_s3_client = MagicMock()
    mock_s3_client.generate_presigned_url.return_value = (
        "https://minio:9000/profile-reports/profile_Costco_20251219_120000.md?signature=abc123"
    )

    with patch("boto3.client", return_value=mock_s3_client):
        url = upload_report_to_s3("# Company Profile\n\nTest report content", "Costco")

    # Should return a presigned URL
    assert url is not None
    assert "profile-reports" in url
    assert "profile_Costco_" in url
    assert ".md" in url

    # Should have called S3 operations
    mock_s3_client.head_bucket.assert_called_once()
    mock_s3_client.put_object.assert_called_once()
    mock_s3_client.generate_presigned_url.assert_called_once()


def test_upload_report_to_s3_sanitizes_filename():
    """Test that company names with special characters are sanitized."""
    from external_agents.profile.nodes.final_report import upload_report_to_s3

    mock_s3_client = MagicMock()
    mock_s3_client.generate_presigned_url.return_value = "https://minio/report.md"

    with patch("boto3.client", return_value=mock_s3_client):
        url = upload_report_to_s3("# Report", "Costco & Co. (USA)")

    # Check that filename was sanitized (no special chars)
    put_object_call = mock_s3_client.put_object.call_args
    filename = put_object_call[1]["Key"]

    assert "profile_Costco___Co___USA_" in filename
    assert "&" not in filename
    assert "(" not in filename
    assert ")" not in filename
    assert "." not in filename or filename.endswith(".md")


def test_upload_report_to_s3_creates_bucket_if_not_exists():
    """Test that bucket is created if it doesn't exist."""
    from external_agents.profile.nodes.final_report import upload_report_to_s3

    mock_s3_client = MagicMock()
    # Simulate bucket not existing (head_bucket raises exception)
    mock_s3_client.head_bucket.side_effect = Exception("Bucket not found")
    mock_s3_client.generate_presigned_url.return_value = "https://minio/report.md"

    with patch("boto3.client", return_value=mock_s3_client):
        url = upload_report_to_s3("# Report", "TestCo")

    # Should have tried to create bucket
    mock_s3_client.create_bucket.assert_called_once()
    assert url is not None


def test_upload_report_to_s3_handles_failure():
    """Test that S3 upload failures are handled gracefully."""
    from external_agents.profile.nodes.final_report import upload_report_to_s3

    with patch("boto3.client", side_effect=Exception("Connection failed")):
        url = upload_report_to_s3("# Report", "TestCo")

    # Should return None on failure, not crash
    assert url is None


def test_upload_report_uses_env_config():
    """Test that S3 upload uses environment configuration."""
    from external_agents.profile.nodes.final_report import upload_report_to_s3

    mock_s3_client = MagicMock()
    mock_s3_client.generate_presigned_url.return_value = "https://custom/report.md"

    with (
        patch.dict(
            os.environ,
            {
                "MINIO_ENDPOINT": "http://custom-minio:9000",
                "MINIO_ACCESS_KEY": "custom-key",
                "MINIO_SECRET_KEY": "custom-secret",
                "REPORTS_BUCKET": "custom-bucket",
            },
        ),
        patch("boto3.client", return_value=mock_s3_client) as mock_boto,
    ):
        upload_report_to_s3("# Report", "TestCo")

    # Check that boto3 client was created with custom config
    mock_boto.assert_called_once_with(
        "s3",
        endpoint_url="http://custom-minio:9000",
        aws_access_key_id="custom-key",
        aws_secret_access_key="custom-secret",
    )

    # Check that custom bucket was used
    put_object_call = mock_s3_client.put_object.call_args
    assert put_object_call[1]["Bucket"] == "custom-bucket"
