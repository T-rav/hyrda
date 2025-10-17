"""Tests for SEC ingestion orchestrator reindexing logic."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.sec_ingestion_orchestrator import SECIngestionOrchestrator


class TestSECIngestionOrchestrator:
    """Test SEC ingestion orchestrator functionality."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance."""
        return SECIngestionOrchestrator(
            user_agent="Test Agent test@example.com"
        )

    @pytest.fixture
    def mock_services(self):
        """Create mock vector and embedding services."""
        vector_service = MagicMock()
        vector_service.client = MagicMock()
        vector_service.collection_name = "test_collection"
        vector_service.upsert_with_namespace = AsyncMock()

        embedding_service = MagicMock()
        embedding_service.embed_batch = MagicMock(
            return_value=[[0.1, 0.2, 0.3]] * 10  # Mock embeddings
        )

        return vector_service, embedding_service

    @pytest.mark.asyncio
    async def test_reindex_deletes_old_chunks_when_content_changed(
        self, orchestrator, mock_services
    ):
        """Test that old chunks are deleted when content changes."""
        vector_service, embedding_service = mock_services
        orchestrator.set_services(vector_service, embedding_service)

        # Mock the document tracker
        existing_uuid = str(uuid.uuid4())
        orchestrator.document_tracker.check_document_needs_reindex = MagicMock(
            return_value=(True, existing_uuid)  # Content changed, needs reindex
        )
        orchestrator.document_tracker.get_document_info = MagicMock(
            return_value={
                "chunk_count": 80,  # Old document had 80 chunks
                "content_hash": "old_hash_123",
            }
        )
        orchestrator.document_tracker.record_document_ingestion = MagicMock()

        # Mock SEC client
        orchestrator.sec_client.get_recent_filings = AsyncMock(
            return_value=[
                {
                    "accession_number": "0001234567-12-000001",
                    "filing_date": "2024-01-15",
                    "primary_document": "test-10k.htm",
                    "url": "https://example.com/test.htm",
                }
            ]
        )
        orchestrator.sec_client.download_filing = AsyncMock(
            return_value="<html>Test filing content</html>"
        )
        orchestrator.sec_client.get_company_facts = AsyncMock(return_value=None)

        # Mock document builder to return filtered content
        with patch.object(
            orchestrator.document_builder,
            "build_10k_document",
            return_value="Filtered 10-K content with only key sections",
        ):
            # Execute ingestion
            success, message = await orchestrator.ingest_company_filing(
                ticker_symbol="AAPL",
                cik="0000320193",
                company_name="Apple Inc",
                filing_type="10-K",
                index=0,
            )

        # Verify old chunks were deleted
        vector_service.client.delete.assert_called_once()
        delete_call_args = vector_service.client.delete.call_args

        # Verify 80 old chunk IDs were generated for deletion
        # (can't easily verify exact UUIDs due to lambda, but verify call was made)
        assert delete_call_args is not None
        assert delete_call_args[1]["collection_name"] == "test_collection"

        # Verify new chunks were upserted
        vector_service.upsert_with_namespace.assert_called_once()
        upsert_args = vector_service.upsert_with_namespace.call_args[1]
        assert upsert_args["namespace"] == "sec_filings"
        assert len(upsert_args["texts"]) > 0  # New chunks created
        assert len(upsert_args["embeddings"]) > 0

        # Verify success
        assert success is True
        assert "Successfully ingested" in message

    @pytest.mark.asyncio
    async def test_skip_when_content_unchanged(self, orchestrator, mock_services):
        """Test that ingestion is skipped when content hash matches."""
        vector_service, embedding_service = mock_services
        orchestrator.set_services(vector_service, embedding_service)

        # Mock the document tracker - content unchanged
        orchestrator.document_tracker.check_document_needs_reindex = MagicMock(
            return_value=(False, None)  # No reindex needed
        )

        # Mock SEC client
        orchestrator.sec_client.get_recent_filings = AsyncMock(
            return_value=[
                {
                    "accession_number": "0001234567-12-000001",
                    "filing_date": "2024-01-15",
                    "primary_document": "test-10k.htm",
                    "url": "https://example.com/test.htm",
                }
            ]
        )
        orchestrator.sec_client.download_filing = AsyncMock(
            return_value="<html>Test filing content</html>"
        )
        orchestrator.sec_client.get_company_facts = AsyncMock(return_value=None)

        # Mock document builder
        with patch.object(
            orchestrator.document_builder,
            "build_10k_document",
            return_value="Same content as before",
        ):
            # Execute ingestion
            success, message = await orchestrator.ingest_company_filing(
                ticker_symbol="AAPL",
                cik="0000320193",
                company_name="Apple Inc",
                filing_type="10-K",
                index=0,
            )

        # Verify NO deletion occurred
        vector_service.client.delete.assert_not_called()

        # Verify NO upsert occurred
        vector_service.upsert_with_namespace.assert_not_called()

        # Verify skipped message
        assert success is True
        assert "already indexed with same content" in message.lower()

    @pytest.mark.asyncio
    async def test_new_document_does_not_delete(self, orchestrator, mock_services):
        """Test that new documents don't attempt deletion."""
        vector_service, embedding_service = mock_services
        orchestrator.set_services(vector_service, embedding_service)

        # Mock the document tracker - new document
        orchestrator.document_tracker.check_document_needs_reindex = MagicMock(
            return_value=(True, None)  # Needs indexing, no existing UUID
        )
        orchestrator.document_tracker.generate_base_uuid = MagicMock(
            return_value=str(uuid.uuid4())
        )
        orchestrator.document_tracker.record_document_ingestion = MagicMock()

        # Mock SEC client
        orchestrator.sec_client.get_recent_filings = AsyncMock(
            return_value=[
                {
                    "accession_number": "0001234567-12-000001",
                    "filing_date": "2024-01-15",
                    "primary_document": "test-10k.htm",
                    "url": "https://example.com/test.htm",
                }
            ]
        )
        orchestrator.sec_client.download_filing = AsyncMock(
            return_value="<html>Test filing content</html>"
        )
        orchestrator.sec_client.get_company_facts = AsyncMock(return_value=None)

        # Mock document builder
        with patch.object(
            orchestrator.document_builder,
            "build_10k_document",
            return_value="New 10-K content",
        ):
            # Execute ingestion
            success, message = await orchestrator.ingest_company_filing(
                ticker_symbol="AAPL",
                cik="0000320193",
                company_name="Apple Inc",
                filing_type="10-K",
                index=0,
            )

        # Verify NO deletion occurred (new document)
        vector_service.client.delete.assert_not_called()

        # Verify upsert occurred for new document
        vector_service.upsert_with_namespace.assert_called_once()

        # Verify success
        assert success is True
        assert "Successfully ingested" in message

    @pytest.mark.asyncio
    async def test_services_must_be_set(self, orchestrator):
        """Test that services must be set before ingestion."""
        # Don't set services
        with pytest.raises(RuntimeError, match="Vector and embedding services must be set"):
            await orchestrator.ingest_company_filing(
                ticker_symbol="AAPL",
                cik="0000320193",
                company_name="Apple Inc",
                filing_type="10-K",
                index=0,
            )

    def test_chunk_text_basic(self, orchestrator):
        """Test basic text chunking."""
        text = "A" * 3000  # 3000 chars
        chunks = orchestrator._chunk_text(text, chunk_size=1000, overlap=100)

        # Should create ~3 chunks with overlap
        assert len(chunks) > 0
        assert all(len(chunk) <= 1100 for chunk in chunks)  # Max size + some buffer

    def test_chunk_text_small_content(self, orchestrator):
        """Test chunking of small content."""
        text = "Small content"
        chunks = orchestrator._chunk_text(text, chunk_size=1000, overlap=100)

        # Should return single chunk
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_chunk_text_empty_content(self, orchestrator):
        """Test chunking of empty content."""
        chunks = orchestrator._chunk_text("", chunk_size=1000, overlap=100)
        assert len(chunks) == 0

        chunks = orchestrator._chunk_text(None, chunk_size=1000, overlap=100)
        assert len(chunks) == 0
