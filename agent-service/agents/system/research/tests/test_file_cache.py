"""Tests for MinIO S3 file cache."""

import os
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from ..services.file_cache import ResearchFileCache
from ..state import CachedFile


@pytest.fixture
def mock_s3_client():
    """Mock boto3 S3 client."""
    with patch("boto3.client") as mock_boto3:
        mock_client = MagicMock()
        mock_boto3.return_value = mock_client

        # Mock list_buckets for connection test
        mock_client.list_buckets.return_value = {"Buckets": []}

        # Mock head_bucket to return bucket exists
        mock_client.head_bucket.return_value = {}

        yield mock_client


@pytest.fixture
def file_cache(mock_s3_client):
    """Create file cache with mocked S3."""
    with patch.dict(
        os.environ,
        {
            "MINIO_ENDPOINT": "http://localhost:9000",
            "MINIO_ACCESS_KEY": "test_key",
            "MINIO_SECRET_KEY": "test_secret",
        },
    ):
        cache = ResearchFileCache()
        return cache


class TestFileCache:
    """Test MinIO file cache functionality."""

    def test_init_success(self, mock_s3_client):
        """Test successful initialization with env vars."""
        with patch.dict(
            os.environ,
            {
                "MINIO_ENDPOINT": "http://localhost:9000",
                "MINIO_ACCESS_KEY": "test_key",
                "MINIO_SECRET_KEY": "test_secret",
            },
        ):
            cache = ResearchFileCache()
            assert cache.endpoint_url == "http://localhost:9000"
            assert cache.access_key == "test_key"
            assert cache.secret_key == "test_secret"
            mock_s3_client.list_buckets.assert_called_once()

    def test_init_missing_endpoint(self):
        """Test initialization fails without MINIO_ENDPOINT."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="MINIO_ENDPOINT not configured"):
                ResearchFileCache()

    def test_init_missing_access_key(self):
        """Test initialization fails without MINIO_ACCESS_KEY."""
        with patch.dict(os.environ, {"MINIO_ENDPOINT": "http://localhost:9000"}, clear=True):
            with pytest.raises(ValueError, match="MINIO_ACCESS_KEY not configured"):
                ResearchFileCache()

    def test_init_missing_secret_key(self):
        """Test initialization fails without MINIO_SECRET_KEY."""
        with patch.dict(
            os.environ,
            {"MINIO_ENDPOINT": "http://localhost:9000", "MINIO_ACCESS_KEY": "key"},
            clear=True,
        ):
            with pytest.raises(ValueError, match="MINIO_SECRET_KEY not configured"):
                ResearchFileCache()

    def test_init_connection_failure(self, mock_s3_client):
        """Test initialization fails if S3 connection fails."""
        mock_s3_client.list_buckets.side_effect = Exception("Connection failed")

        with patch.dict(
            os.environ,
            {
                "MINIO_ENDPOINT": "http://localhost:9000",
                "MINIO_ACCESS_KEY": "key",
                "MINIO_SECRET_KEY": "secret",
            },
        ):
            with pytest.raises(ValueError, match="Failed to connect to MinIO"):
                ResearchFileCache()

    def test_cache_file_success(self, file_cache):
        """Test successful file caching to S3."""
        content = "Test content"
        metadata = {"company": "TestCo", "form_type": "10K", "year": 2023}

        result = file_cache.cache_file("sec_filing", content, metadata)

        assert isinstance(result, CachedFile)
        assert result.file_type == "sec_filing"
        assert result.file_path.startswith("s3://research-sec-filings/")
        assert result.size_bytes == len(content.encode("utf-8"))
        assert len(result.file_id) == 12

        # Verify S3 upload called
        file_cache.s3_client.put_object.assert_called_once()

    def test_cache_file_invalid_type(self, file_cache):
        """Test caching with invalid file type raises error."""
        with pytest.raises(ValueError, match="Invalid file_type"):
            file_cache.cache_file("invalid_type", "content", {})

    def test_cache_file_bytes_content(self, file_cache):
        """Test caching bytes content."""
        content = b"Binary content"
        metadata = {"url": "https://example.com", "title": "Test Page"}

        result = file_cache.cache_file("web_page", content, metadata)

        assert result.size_bytes == len(content)
        # Verify put_object called with bytes
        call_args = file_cache.s3_client.put_object.call_args
        assert isinstance(call_args[1]["Body"], bytes)

    def test_cache_file_s3_error(self, file_cache):
        """Test caching handles S3 errors."""
        file_cache.s3_client.put_object.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "Server Error"}}, "PutObject"
        )

        with pytest.raises(ClientError):
            file_cache.cache_file("pdf", "content", {"source": "test", "title": "doc"})

    def test_retrieve_file_success(self, file_cache):
        """Test retrieving file from S3."""
        mock_response = {"Body": MagicMock()}
        mock_response["Body"].read.return_value = b"File content"
        file_cache.s3_client.get_object.return_value = mock_response

        result = file_cache.retrieve_file("s3://test-bucket/test.txt")

        assert result == "File content"
        file_cache.s3_client.get_object.assert_called_once_with(
            Bucket="test-bucket", Key="test.txt"
        )

    def test_retrieve_file_not_found(self, file_cache):
        """Test retrieving non-existent file returns None."""
        file_cache.s3_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}, "GetObject"
        )

        result = file_cache.retrieve_file("s3://test-bucket/missing.txt")

        assert result is None

    def test_retrieve_file_invalid_path(self, file_cache):
        """Test retrieving with invalid S3 path."""
        result = file_cache.retrieve_file("/local/path/file.txt")
        assert result is None

        result = file_cache.retrieve_file("s3://bucket-only")
        assert result is None

    def test_search_cache_with_matches(self, file_cache):
        """Test searching cache with matches."""
        from datetime import datetime
        file_cache.s3_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "testco_10k_2023.txt", "Size": 1000, "LastModified": datetime(2024, 1, 1)}
            ]
        }
        file_cache.s3_client.head_object.return_value = {
            "Metadata": {"company": "TestCo", "form_type": "10K"}
        }

        results = file_cache.search_cache("testco", "sec_filing")

        assert len(results) == 1
        assert results[0].file_type == "sec_filing"
        assert "testco" in results[0].file_path.lower()

    def test_search_cache_no_matches(self, file_cache):
        """Test searching with no matches."""
        file_cache.s3_client.list_objects_v2.return_value = {
            "Contents": [{"Key": "other_file.txt", "Size": 100, "LastModified": "2024-01-01"}]
        }

        results = file_cache.search_cache("nonexistent")

        assert len(results) == 0

    def test_search_cache_empty_bucket(self, file_cache):
        """Test searching empty bucket."""
        file_cache.s3_client.list_objects_v2.return_value = {}

        results = file_cache.search_cache("test")

        assert len(results) == 0

    def test_get_cache_stats(self, file_cache):
        """Test getting cache statistics."""
        file_cache.s3_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "file1.txt", "Size": 1000},
                {"Key": "file2.txt", "Size": 2000},
            ]
        }

        stats = file_cache.get_cache_stats()

        assert "total_files" in stats
        assert "total_size_mb" in stats
        assert "files_by_type" in stats
        assert stats["storage_backend"] == "MinIO S3"
        assert "endpoint" in stats

    def test_sanitize(self, file_cache):
        """Test filename sanitization."""
        assert file_cache._sanitize("Test Company Inc.") == "test_company_inc"
        assert file_cache._sanitize("File@#$Name") == "file_name"
        assert file_cache._sanitize("multiple___underscores") == "multiple_underscores"

    def test_generate_file_name_sec_filing(self, file_cache):
        """Test filename generation for SEC filing."""
        metadata = {"company": "TestCo", "form_type": "10K", "year": 2023, "quarter": "Q4"}
        filename = file_cache._generate_file_name("sec_filing", metadata)

        assert "testco" in filename
        assert "10k" in filename or "10K" in filename
        assert "2023" in filename

    def test_generate_file_name_web_page(self, file_cache):
        """Test filename generation for web page."""
        metadata = {"url": "https://example.com/article", "title": "Test Article"}
        filename = file_cache._generate_file_name("web_page", metadata)

        assert "example_com" in filename
        assert "test_article" in filename

    def test_buckets_created_on_init(self, mock_s3_client):
        """Test buckets are created if they don't exist."""
        # Simulate bucket doesn't exist
        mock_s3_client.head_bucket.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadBucket"
        )

        with patch.dict(
            os.environ,
            {
                "MINIO_ENDPOINT": "http://localhost:9000",
                "MINIO_ACCESS_KEY": "key",
                "MINIO_SECRET_KEY": "secret",
            },
        ):
            cache = ResearchFileCache()

            # Verify buckets creation attempted
            assert mock_s3_client.create_bucket.call_count == 4  # 4 bucket types
            assert mock_s3_client.put_bucket_lifecycle_configuration.call_count == 4


@pytest.mark.integration
class TestFileCacheIntegration:
    """Integration tests requiring real MinIO (skip if not available)."""

    def test_end_to_end_workflow(self):
        """Test complete workflow: cache, retrieve, search, stats."""
        # Skip if MinIO not configured
        if not os.getenv("MINIO_ENDPOINT"):
            pytest.skip("MinIO not configured")

        cache = ResearchFileCache()

        # Cache a file
        content = "Integration test content"
        metadata = {"company": "IntegrationCo", "form_type": "10K", "year": 2024}
        cached_file = cache.cache_file("sec_filing", content, metadata)

        # Retrieve the file
        retrieved = cache.retrieve_file(cached_file.file_path)
        assert retrieved == content

        # Search for the file
        results = cache.search_cache("integrationco", "sec_filing")
        assert len(results) > 0

        # Get stats
        stats = cache.get_cache_stats()
        assert stats["total_files"] > 0

    def test_get_presigned_url_success(self, file_cache):
        """Test generating presigned URL for valid S3 path."""
        file_cache.s3_client.generate_presigned_url.return_value = (
            "http://localhost:9000/research-pdfs/test.pdf?signature=abc123"
        )

        url = file_cache.get_presigned_url("s3://research-pdfs/test.pdf", expiration=3600)

        assert url == "http://localhost:9000/research-pdfs/test.pdf?signature=abc123"
        file_cache.s3_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "research-pdfs", "Key": "test.pdf"},
            ExpiresIn=3600,
        )

    def test_get_presigned_url_invalid_path(self, file_cache):
        """Test presigned URL with invalid S3 path."""
        # Non-S3 path
        url = file_cache.get_presigned_url("/local/path/file.pdf")
        assert url is None

        # S3 path without key
        url = file_cache.get_presigned_url("s3://bucket-only")
        assert url is None

    def test_get_presigned_url_client_error(self, file_cache):
        """Test presigned URL generation with S3 client error."""
        file_cache.s3_client.generate_presigned_url.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}, "GetObject"
        )

        url = file_cache.get_presigned_url("s3://research-pdfs/missing.pdf")

        assert url is None

    def test_get_presigned_url_custom_expiration(self, file_cache):
        """Test presigned URL with custom expiration time."""
        file_cache.s3_client.generate_presigned_url.return_value = "http://test-url"

        url = file_cache.get_presigned_url("s3://research-pdfs/test.pdf", expiration=604800)

        assert url == "http://test-url"
        file_cache.s3_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "research-pdfs", "Key": "test.pdf"},
            ExpiresIn=604800,  # 7 days
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
