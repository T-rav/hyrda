"""Tests for WebPageTrackingService.

These tests focus on pure functions that don't require database access.
Database-dependent methods require integration testing infrastructure.
"""

import hashlib

import pytest

from services.web_page_tracking_service import WebPageTrackingService


@pytest.fixture
def tracking_service():
    """Create tracking service instance."""
    return WebPageTrackingService()


class TestWebPageTrackingServiceHashing:
    """Test URL and content hashing."""

    def test_compute_url_hash(self, tracking_service):
        """Test URL hashing produces consistent results."""
        url = "https://example.com/page1"
        hash1 = tracking_service.compute_url_hash(url)
        hash2 = tracking_service.compute_url_hash(url)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 produces 64 hex characters

    def test_compute_url_hash_different_urls(self, tracking_service):
        """Test different URLs produce different hashes."""
        url1 = "https://example.com/page1"
        url2 = "https://example.com/page2"

        hash1 = tracking_service.compute_url_hash(url1)
        hash2 = tracking_service.compute_url_hash(url2)

        assert hash1 != hash2

    def test_compute_content_hash(self, tracking_service):
        """Test content hashing produces consistent results."""
        content = "This is test content."
        hash1 = tracking_service.compute_content_hash(content)
        hash2 = tracking_service.compute_content_hash(content)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 produces 64 hex characters

    def test_compute_content_hash_different_content(self, tracking_service):
        """Test different content produces different hashes."""
        content1 = "This is test content."
        content2 = "This is different content."

        hash1 = tracking_service.compute_content_hash(content1)
        hash2 = tracking_service.compute_content_hash(content2)

        assert hash1 != hash2

    def test_compute_content_hash_whitespace_sensitive(self, tracking_service):
        """Test content hash is sensitive to whitespace changes."""
        content1 = "This is test content."
        content2 = "This  is  test  content."  # Extra spaces

        hash1 = tracking_service.compute_content_hash(content1)
        hash2 = tracking_service.compute_content_hash(content2)

        # Should be different (whitespace matters)
        assert hash1 != hash2

    def test_compute_hash_matches_sha256(self, tracking_service):
        """Test hash computation matches standard SHA-256."""
        content = "Test content"
        expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        actual_hash = tracking_service.compute_content_hash(content)

        assert actual_hash == expected_hash


class TestWebPageTrackingServiceUUID:
    """Test UUID generation."""

    def test_generate_base_uuid(self, tracking_service):
        """Test UUID generation is consistent for same URL."""
        url = "https://example.com/page1"
        uuid1 = tracking_service.generate_base_uuid(url)
        uuid2 = tracking_service.generate_base_uuid(url)

        assert uuid1 == uuid2
        assert len(uuid1) == 36  # Standard UUID format with hyphens
        assert uuid1.count("-") == 4  # UUID has 4 hyphens

    def test_generate_base_uuid_different_urls(self, tracking_service):
        """Test different URLs produce different UUIDs."""
        url1 = "https://example.com/page1"
        url2 = "https://example.com/page2"

        uuid1 = tracking_service.generate_base_uuid(url1)
        uuid2 = tracking_service.generate_base_uuid(url2)

        assert uuid1 != uuid2

    def test_generate_base_uuid_format(self, tracking_service):
        """Test UUID has valid format."""
        import re

        url = "https://example.com/page1"
        uuid_str = tracking_service.generate_base_uuid(url)

        # UUID format: 8-4-4-4-12 hex digits
        uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        assert re.match(uuid_pattern, uuid_str)


class TestWebPageTrackingServiceDomainExtraction:
    """Test domain extraction logic."""

    def test_extract_domain_simple(self, tracking_service):
        """Test domain extraction from simple URL."""
        url = "https://example.com/page1"
        domain = tracking_service.extract_domain(url)
        assert domain == "example.com"

    def test_extract_domain_with_subdomain(self, tracking_service):
        """Test domain extraction includes subdomain."""
        url = "https://docs.example.com/page1"
        domain = tracking_service.extract_domain(url)
        assert domain == "docs.example.com"

    def test_extract_domain_with_www(self, tracking_service):
        """Test domain extraction includes www."""
        url = "https://www.example.com/page1"
        domain = tracking_service.extract_domain(url)
        assert domain == "www.example.com"

    def test_extract_domain_with_port(self, tracking_service):
        """Test domain extraction includes port (by design)."""
        url = "https://example.com:8080/page1"
        domain = tracking_service.extract_domain(url)
        # netloc includes port
        assert domain == "example.com:8080"

    def test_extract_domain_http(self, tracking_service):
        """Test domain extraction works with HTTP."""
        url = "http://example.com/page1"
        domain = tracking_service.extract_domain(url)
        assert domain == "example.com"

    def test_extract_domain_with_path(self, tracking_service):
        """Test domain extraction ignores path."""
        url = "https://example.com/path/to/page"
        domain = tracking_service.extract_domain(url)
        assert domain == "example.com"

    def test_extract_domain_with_query_params(self, tracking_service):
        """Test domain extraction ignores query parameters."""
        url = "https://example.com/page?param=value"
        domain = tracking_service.extract_domain(url)
        assert domain == "example.com"


class TestWebPageTrackingServiceIntegration:
    """Integration tests that require database would go here.

    These tests would need proper database setup/teardown:
    - test_check_page_needs_rescrape_new_page
    - test_check_page_needs_rescrape_unchanged_page
    - test_check_page_needs_rescrape_changed_page
    - test_record_page_scrape_creates_new_record
    - test_record_page_scrape_updates_existing_record
    - test_get_pages_by_domain
    - test_get_page_info

    Skipped for now as they require complex database mocking.
    """

    pass
