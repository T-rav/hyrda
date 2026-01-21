"""Tests for DocumentTrackingService.

Tests the document tracking service's database connection and basic operations.
"""

import pytest

from services.gdrive.document_tracking_service import DocumentTrackingService


@pytest.mark.integration
class TestDocumentTrackingServiceIntegration:
    """Integration tests for document tracking with real database."""

    def setup_method(self):
        """Set up test environment."""
        self.service = DocumentTrackingService()
        self.test_google_drive_id = "test-file-id-12345"

    def teardown_method(self):
        """Clean up test data."""
        # Clean up any test documents created during tests
        from models.base import get_data_db_session
        from services.gdrive.document_tracking_service import GoogleDriveDocument

        with get_data_db_session() as session:
            session.query(GoogleDriveDocument).filter(
                GoogleDriveDocument.google_drive_id == self.test_google_drive_id
            ).delete()
            session.commit()

    def test_database_connection_uses_data_db(self):
        """Test that service connects to insightmesh_data database."""
        # This test verifies the fix - should not raise an error
        needs_reindex, uuid = self.service.check_document_needs_reindex(
            google_drive_id=self.test_google_drive_id, content="test content"
        )

        # New document should need indexing
        assert needs_reindex is True
        assert uuid is None

    def test_record_document_ingestion(self):
        """Test recording a document ingestion."""
        vector_uuid = self.service.generate_base_uuid(self.test_google_drive_id)

        self.service.record_document_ingestion(
            google_drive_id=self.test_google_drive_id,
            file_path="/test/path/file.pdf",
            document_name="test_file.pdf",
            content="test content for hashing",
            vector_uuid=vector_uuid,
            chunk_count=3,
            mime_type="application/pdf",
            file_size=1024,
            metadata={"test": "metadata"},
            status="success",
        )

        # Verify document was recorded
        needs_reindex, existing_uuid = self.service.check_document_needs_reindex(
            google_drive_id=self.test_google_drive_id,
            content="test content for hashing",
        )

        # Same content should not need reindexing
        assert needs_reindex is False
        assert existing_uuid == vector_uuid

    def test_content_hash_change_triggers_reindex(self):
        """Test that changed content triggers reindexing."""
        vector_uuid = self.service.generate_base_uuid(self.test_google_drive_id)

        # Record initial document
        self.service.record_document_ingestion(
            google_drive_id=self.test_google_drive_id,
            file_path="/test/path/file.pdf",
            document_name="test_file.pdf",
            content="original content",
            vector_uuid=vector_uuid,
            chunk_count=2,
            status="success",
        )

        # Check with different content
        needs_reindex, existing_uuid = self.service.check_document_needs_reindex(
            google_drive_id=self.test_google_drive_id,
            content="modified content",  # Different content
        )

        # Changed content should trigger reindex
        assert needs_reindex is True
        assert existing_uuid == vector_uuid

    def test_failed_ingestion_recorded(self):
        """Test that failed ingestions are recorded properly."""
        vector_uuid = self.service.generate_base_uuid(self.test_google_drive_id)
        error_message = "Test error: failed to download"

        self.service.record_document_ingestion(
            google_drive_id=self.test_google_drive_id,
            file_path="/test/path/failed_file.pdf",
            document_name="failed_file.pdf",
            content="",  # Empty content for failed ingestion
            vector_uuid=vector_uuid,
            chunk_count=0,
            status="failed",
            error_message=error_message,
        )

        # Verify error was recorded
        from models.base import get_data_db_session
        from services.gdrive.document_tracking_service import GoogleDriveDocument

        with get_data_db_session() as session:
            doc = (
                session.query(GoogleDriveDocument)
                .filter(
                    GoogleDriveDocument.google_drive_id == self.test_google_drive_id
                )
                .first()
            )

            assert doc is not None
            assert doc.ingestion_status == "failed"
            assert doc.error_message == error_message
            assert doc.chunk_count == 0


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
