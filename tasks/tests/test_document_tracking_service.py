"""Tests for DocumentTrackingService.

Tests the document tracking service's database connection and basic operations.
"""

from services.gdrive.document_tracking_service import DocumentTrackingService


class TestDocumentTrackingServiceUnit:
    """Unit tests for document tracking service."""

    def test_compute_content_hash(self):
        """Test content hash computation."""
        service = DocumentTrackingService()

        content = "test content"
        hash1 = service.compute_content_hash(content)
        hash2 = service.compute_content_hash(content)

        # Same content should produce same hash
        assert hash1 == hash2

        # Different content should produce different hash
        hash3 = service.compute_content_hash("different content")
        assert hash1 != hash3

    def test_generate_base_uuid(self):
        """Test UUID generation."""
        service = DocumentTrackingService()

        google_drive_id = "test-file-12345"
        uuid1 = service.generate_base_uuid(google_drive_id)
        uuid2 = service.generate_base_uuid(google_drive_id)

        # Same ID should produce same UUID (deterministic)
        assert uuid1 == uuid2

        # Different ID should produce different UUID
        uuid3 = service.generate_base_uuid("different-file-67890")
        assert uuid1 != uuid3

        # UUIDs should be valid format (36 chars with dashes)
        assert len(uuid1) == 36
        assert uuid1.count("-") == 4
