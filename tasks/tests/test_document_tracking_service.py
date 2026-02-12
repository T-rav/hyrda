"""Tests for DocumentTrackingService.

Tests the document tracking service's database connection and basic operations.
"""

from datetime import UTC, datetime
from unittest.mock import Mock, patch

from services.gdrive.document_tracking_service import (
    DocumentTrackingService,
    GoogleDriveDocument,
)


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

    def test_check_document_needs_reindex_by_metadata_new_document(self):
        """Test metadata-based check for new document (avoids download cost)."""
        service = DocumentTrackingService()

        with patch(
            "services.gdrive.document_tracking_service.get_data_db_session"
        ) as mock_session:
            mock_session.return_value.__enter__.return_value.query.return_value.filter_by.return_value.first.return_value = None

            needs_reindex, existing_uuid = (
                service.check_document_needs_reindex_by_metadata(
                    "new-file-id", "2024-01-01T12:00:00Z", 1024
                )
            )

            assert needs_reindex is True
            assert existing_uuid is None

    def test_check_document_needs_reindex_by_metadata_unchanged(self):
        """Test metadata-based check skips unchanged document (avoids download/transcription cost)."""
        service = DocumentTrackingService()

        # Create mock document that was ingested recently
        mock_doc = Mock(spec=GoogleDriveDocument)
        mock_doc.vector_uuid = "existing-uuid-123"
        mock_doc.last_ingested_at = datetime(2024, 1, 2, tzinfo=UTC)
        mock_doc.file_size = 1024

        with patch(
            "services.gdrive.document_tracking_service.get_data_db_session"
        ) as mock_session:
            mock_session.return_value.__enter__.return_value.query.return_value.filter_by.return_value.first.return_value = mock_doc

            # File modified before last ingestion - unchanged!
            needs_reindex, existing_uuid = (
                service.check_document_needs_reindex_by_metadata(
                    "existing-file-id", "2024-01-01T12:00:00Z", 1024
                )
            )

            assert needs_reindex is False
            assert existing_uuid == "existing-uuid-123"

    def test_check_document_needs_reindex_by_metadata_changed(self):
        """Test metadata-based check detects modified document."""
        service = DocumentTrackingService()

        # Create mock document that was ingested before modification
        mock_doc = Mock(spec=GoogleDriveDocument)
        mock_doc.vector_uuid = "existing-uuid-123"
        mock_doc.last_ingested_at = datetime(2024, 1, 1, tzinfo=UTC)
        mock_doc.file_size = 1024

        with patch(
            "services.gdrive.document_tracking_service.get_data_db_session"
        ) as mock_session:
            mock_session.return_value.__enter__.return_value.query.return_value.filter_by.return_value.first.return_value = mock_doc

            # File modified AFTER last ingestion - needs reindex!
            needs_reindex, existing_uuid = (
                service.check_document_needs_reindex_by_metadata(
                    "existing-file-id", "2024-01-02T12:00:00Z", 2048
                )
            )

            assert needs_reindex is True
            assert existing_uuid == "existing-uuid-123"

    def test_check_document_needs_reindex_by_metadata_size_match(self):
        """Test metadata-based check uses file size when timestamp unavailable."""
        service = DocumentTrackingService()

        mock_doc = Mock(spec=GoogleDriveDocument)
        mock_doc.vector_uuid = "existing-uuid-123"
        mock_doc.last_ingested_at = datetime(2024, 1, 1, tzinfo=UTC)
        mock_doc.file_size = 1024

        with patch(
            "services.gdrive.document_tracking_service.get_data_db_session"
        ) as mock_session:
            mock_session.return_value.__enter__.return_value.query.return_value.filter_by.return_value.first.return_value = mock_doc

            # Same size, assume unchanged
            needs_reindex, existing_uuid = (
                service.check_document_needs_reindex_by_metadata(
                    "existing-file-id", None, 1024
                )
            )

            assert needs_reindex is False
            assert existing_uuid == "existing-uuid-123"


class TestWebPageTrackingService:
    """Tests for web page tracking service (HTTP conditional requests)."""

    def test_get_conditional_headers_new_page(self):
        """Test conditional headers for new page (none available)."""
        from services.web_page_tracking_service import WebPageTrackingService

        service = WebPageTrackingService()

        with patch(
            "services.web_page_tracking_service.get_data_db_session"
        ) as mock_session:
            mock_session.return_value.__enter__.return_value.query.return_value.filter_by.return_value.first.return_value = None

            headers = service.get_conditional_headers("https://example.com/page")

            assert headers == {}  # No headers for new page

    def test_get_conditional_headers_with_last_modified(self):
        """Test conditional headers include If-Modified-Since."""
        from services.web_page_tracking_service import (
            ScrapedWebPage,
            WebPageTrackingService,
        )

        service = WebPageTrackingService()

        mock_page = Mock(spec=ScrapedWebPage)
        mock_page.last_modified = "Mon, 01 Jan 2024 12:00:00 GMT"
        mock_page.etag = None

        with patch(
            "services.web_page_tracking_service.get_data_db_session"
        ) as mock_session:
            mock_session.return_value.__enter__.return_value.query.return_value.filter_by.return_value.first.return_value = mock_page

            headers = service.get_conditional_headers("https://example.com/page")

            assert headers == {"If-Modified-Since": "Mon, 01 Jan 2024 12:00:00 GMT"}

    def test_get_conditional_headers_with_etag(self):
        """Test conditional headers include If-None-Match."""
        from services.web_page_tracking_service import (
            ScrapedWebPage,
            WebPageTrackingService,
        )

        service = WebPageTrackingService()

        mock_page = Mock(spec=ScrapedWebPage)
        mock_page.last_modified = None
        mock_page.etag = '"abc123"'

        with patch(
            "services.web_page_tracking_service.get_data_db_session"
        ) as mock_session:
            mock_session.return_value.__enter__.return_value.query.return_value.filter_by.return_value.first.return_value = mock_page

            headers = service.get_conditional_headers("https://example.com/page")

            assert headers == {"If-None-Match": '"abc123"'}

    def test_get_conditional_headers_with_both(self):
        """Test conditional headers include both If-Modified-Since and If-None-Match."""
        from services.web_page_tracking_service import (
            ScrapedWebPage,
            WebPageTrackingService,
        )

        service = WebPageTrackingService()

        mock_page = Mock(spec=ScrapedWebPage)
        mock_page.last_modified = "Mon, 01 Jan 2024 12:00:00 GMT"
        mock_page.etag = '"abc123"'

        with patch(
            "services.web_page_tracking_service.get_data_db_session"
        ) as mock_session:
            mock_session.return_value.__enter__.return_value.query.return_value.filter_by.return_value.first.return_value = mock_page

            headers = service.get_conditional_headers("https://example.com/page")

            assert headers == {
                "If-Modified-Since": "Mon, 01 Jan 2024 12:00:00 GMT",
                "If-None-Match": '"abc123"',
            }
