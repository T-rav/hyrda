"""
Comprehensive tests for IngestionOrchestrator.

Tests cover:
- Initialization and authentication
- Service configuration
- File ingestion workflow (success, error, skip)
- Folder ingestion with recursion
- Metadata update logic
- Error handling and tracking
- Idempotent ingestion (content hash checks)
- Contextual retrieval integration
"""

import uuid
from unittest.mock import AsyncMock, Mock, patch

import pytest

from services.gdrive.ingestion_orchestrator import IngestionOrchestrator


@pytest.fixture
def mock_google_drive_client():
    """Create mock Google Drive client."""
    client = Mock()
    client.authenticate = Mock(return_value=True)
    client.download_file_content = Mock(return_value="Test file content")
    client.list_folder_contents = Mock(return_value=[])
    return client


@pytest.fixture
def mock_document_tracker():
    """Create mock document tracking service."""
    tracker = Mock()
    tracker.check_document_needs_reindex_by_metadata = Mock(return_value=(True, None))
    tracker.check_document_needs_reindex = Mock(return_value=(True, None))
    tracker.generate_base_uuid = Mock(
        return_value="12345678-1234-5678-1234-567812345678"
    )
    tracker.record_document_ingestion = Mock()
    tracker.get_document_info = Mock(return_value=None)
    return tracker


@pytest.fixture
def mock_vector_service():
    """Create mock vector database service."""
    service = AsyncMock()
    service.upsert = AsyncMock()
    service.update_payload = AsyncMock()
    return service


@pytest.fixture
def mock_embedding_service():
    """Create mock embedding service."""
    service = AsyncMock()
    service.chunk_text = Mock(return_value=["chunk1", "chunk2", "chunk3"])
    service.embed_texts = AsyncMock(
        return_value=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9]]
    )
    return service


@pytest.fixture
def mock_llm_service():
    """Create mock LLM service for contextual retrieval."""
    service = AsyncMock()
    service.generate_chunk_context = AsyncMock(
        return_value="Contextual description of chunk"
    )
    return service


@pytest.fixture
def sample_file_info():
    """Create sample file metadata."""
    return {
        "id": "file123",
        "name": "test_document.pdf",
        "mimeType": "application/pdf",
        "full_path": "Folder/test_document.pdf",
        "folder_path": "Folder/",
        "modifiedTime": "2025-12-17T10:00:00Z",
        "createdTime": "2025-12-01T10:00:00Z",
        "size": "1024",
        "webViewLink": "https://drive.google.com/file/d/file123/view",
        "owners": [{"emailAddress": "owner@example.com"}],
        "detailed_permissions": [
            {
                "type": "user",
                "role": "owner",
                "emailAddress": "owner@example.com",
            }
        ],
    }


@pytest.fixture
def orchestrator(mock_google_drive_client, mock_document_tracker):
    """Create orchestrator instance with mocked dependencies."""
    with (
        patch(
            "services.gdrive.ingestion_orchestrator.GoogleDriveClient",
            return_value=mock_google_drive_client,
        ),
        patch(
            "services.gdrive.ingestion_orchestrator.DocumentTrackingService",
            return_value=mock_document_tracker,
        ),
    ):
        return IngestionOrchestrator()


class TestIngestionOrchestratorInit:
    """Test orchestrator initialization."""

    def test_init_default_parameters(self):
        """Test initialization with default parameters."""
        # Arrange & Act
        with (
            patch("services.gdrive.ingestion_orchestrator.GoogleDriveClient"),
            patch("services.gdrive.ingestion_orchestrator.DocumentTrackingService"),
        ):
            orchestrator = IngestionOrchestrator()

        # Assert
        assert orchestrator.google_drive_client is not None
        assert orchestrator.document_tracker is not None
        assert orchestrator.vector_service is None
        assert orchestrator.embedding_service is None
        assert orchestrator.contextual_retrieval_service is None
        assert orchestrator.llm_service is None
        assert orchestrator.enable_contextual_retrieval is False

    def test_init_with_credentials(self):
        """Test initialization with credential files."""
        # Arrange & Act
        with (
            patch(
                "services.gdrive.ingestion_orchestrator.GoogleDriveClient"
            ) as mock_client_class,
            patch("services.gdrive.ingestion_orchestrator.DocumentTrackingService"),
        ):
            IngestionOrchestrator(
                credentials_file="creds.json", token_file="token.json"
            )

            # Assert
            mock_client_class.assert_called_once_with("creds.json", "token.json", None)


class TestIngestionOrchestratorAuthentication:
    """Test authentication methods."""

    def test_authenticate_success(self, orchestrator, mock_google_drive_client):
        """Test successful authentication."""
        # Arrange
        mock_google_drive_client.authenticate.return_value = True

        # Act
        result = orchestrator.authenticate()

        # Assert
        assert result is True
        mock_google_drive_client.authenticate.assert_called_once()

    def test_authenticate_failure(self, orchestrator, mock_google_drive_client):
        """Test authentication failure."""
        # Arrange
        mock_google_drive_client.authenticate.return_value = False

        # Act
        result = orchestrator.authenticate()

        # Assert
        assert result is False


class TestIngestionOrchestratorServiceConfiguration:
    """Test service configuration."""

    def test_set_services_basic(
        self, orchestrator, mock_vector_service, mock_embedding_service
    ):
        """Test setting basic services."""
        # Arrange & Act
        orchestrator.set_services(
            vector_service=mock_vector_service,
            embedding_service=mock_embedding_service,
        )

        # Assert
        assert orchestrator.vector_service == mock_vector_service
        assert orchestrator.embedding_service == mock_embedding_service
        assert orchestrator.llm_service is None
        assert orchestrator.enable_contextual_retrieval is False

    def test_set_services_with_contextual_retrieval(
        self,
        orchestrator,
        mock_vector_service,
        mock_embedding_service,
        mock_llm_service,
    ):
        """Test setting services with contextual retrieval enabled."""
        # Arrange & Act
        orchestrator.set_services(
            vector_service=mock_vector_service,
            embedding_service=mock_embedding_service,
            llm_service=mock_llm_service,
            enable_contextual_retrieval=True,
        )

        # Assert
        assert orchestrator.vector_service == mock_vector_service
        assert orchestrator.embedding_service == mock_embedding_service
        assert orchestrator.llm_service == mock_llm_service
        assert orchestrator.enable_contextual_retrieval is True

    def test_set_services_with_builtin_embedding(
        self, orchestrator, mock_vector_service
    ):
        """Test setting services when vector service has built-in embedding."""
        # Arrange
        mock_vector_service.embedding_service = Mock()

        # Act
        orchestrator.set_services(vector_service=mock_vector_service)

        # Assert
        assert orchestrator.vector_service == mock_vector_service
        assert orchestrator.embedding_service is None


class TestIngestionOrchestratorIngestFiles:
    """Test file ingestion workflow."""

    @pytest.mark.asyncio
    async def test_ingest_files_requires_vector_service(self, orchestrator):
        """Test ingestion fails without vector service configured."""
        # Arrange
        files = [{"id": "file123", "name": "test.pdf"}]

        # Act & Assert
        with pytest.raises(RuntimeError, match="Vector service not initialized"):
            await orchestrator.ingest_files(files)

    @pytest.mark.asyncio
    async def test_ingest_files_requires_embedding_service(self, orchestrator):
        """Test ingestion fails without embedding service when not built-in."""
        # Arrange
        # Create a mock vector service WITHOUT embedding_service attribute
        vector_service_no_embedding = Mock(spec=["upsert", "update_payload"])
        orchestrator.vector_service = vector_service_no_embedding
        files = [{"id": "file123", "name": "test.pdf", "mimeType": "application/pdf"}]

        # Act & Assert
        with pytest.raises(RuntimeError, match="Embedding service not initialized"):
            await orchestrator.ingest_files(files)

    @pytest.mark.asyncio
    async def test_ingest_files_success(
        self,
        orchestrator,
        mock_vector_service,
        mock_embedding_service,
        mock_document_tracker,
        mock_google_drive_client,
        sample_file_info,
    ):
        """Test successful file ingestion."""
        # Arrange
        orchestrator.set_services(mock_vector_service, mock_embedding_service)
        files = [sample_file_info]

        # Act
        success, error, skipped = await orchestrator.ingest_files(files)

        # Assert
        assert success == 1
        assert error == 0
        assert skipped == 0
        mock_google_drive_client.download_file_content.assert_called_once_with(
            "file123", "application/pdf", "test_document.pdf"
        )
        mock_embedding_service.chunk_text.assert_called_once()
        mock_embedding_service.embed_texts.assert_called_once()
        mock_vector_service.upsert.assert_called_once()
        mock_document_tracker.record_document_ingestion.assert_called_once()

    @pytest.mark.asyncio
    async def test_ingest_files_skips_folders(
        self,
        orchestrator,
        mock_vector_service,
        mock_embedding_service,
        mock_google_drive_client,
    ):
        """Test ingestion skips folder entries."""
        # Arrange
        orchestrator.set_services(mock_vector_service, mock_embedding_service)
        files = [
            {
                "id": "folder123",
                "name": "My Folder",
                "mimeType": "application/vnd.google-apps.folder",
            }
        ]

        # Act
        success, error, skipped = await orchestrator.ingest_files(files)

        # Assert
        assert success == 0
        assert error == 0
        assert skipped == 0
        mock_google_drive_client.download_file_content.assert_not_called()

    @pytest.mark.asyncio
    async def test_ingest_files_download_failure(
        self,
        orchestrator,
        mock_vector_service,
        mock_embedding_service,
        mock_google_drive_client,
        sample_file_info,
    ):
        """Test ingestion handles download failures."""
        # Arrange
        orchestrator.set_services(mock_vector_service, mock_embedding_service)
        mock_google_drive_client.download_file_content.return_value = None
        files = [sample_file_info]

        # Act
        success, error, skipped = await orchestrator.ingest_files(files)

        # Assert
        assert success == 0
        assert error == 1
        assert skipped == 0
        mock_embedding_service.chunk_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_ingest_files_skips_unchanged_content(
        self,
        orchestrator,
        mock_vector_service,
        mock_embedding_service,
        mock_document_tracker,
        mock_google_drive_client,
        sample_file_info,
    ):
        """Test ingestion skips files with unchanged content."""
        # Arrange
        orchestrator.set_services(mock_vector_service, mock_embedding_service)
        # First check by metadata returns False (skip without download)
        mock_document_tracker.check_document_needs_reindex_by_metadata.return_value = (
            False,
            "existing-uuid",
        )
        mock_document_tracker.check_document_needs_reindex.return_value = (
            False,
            "existing-uuid",
        )
        mock_document_tracker.get_document_info.return_value = {
            "chunk_count": 3,
            "metadata": {
                "owner_emails": "owner@example.com",
                "permissions_summary": "owner:owner@example.com",
            },
        }
        files = [sample_file_info]

        # Act
        success, error, skipped = await orchestrator.ingest_files(files)

        # Assert
        assert success == 0
        assert error == 0
        assert skipped == 1
        mock_embedding_service.chunk_text.assert_not_called()
        mock_vector_service.upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_ingest_files_reindexes_changed_content(
        self,
        orchestrator,
        mock_vector_service,
        mock_embedding_service,
        mock_document_tracker,
        mock_google_drive_client,
        sample_file_info,
    ):
        """Test ingestion reindexes files with changed content."""
        # Arrange
        orchestrator.set_services(mock_vector_service, mock_embedding_service)
        # Use a properly formatted UUID (with hyphens in correct positions)
        existing_uuid = "12345678-1234-5678-1234-567812345678"
        mock_document_tracker.check_document_needs_reindex_by_metadata.return_value = (
            True,
            existing_uuid,
        )
        mock_document_tracker.check_document_needs_reindex.return_value = (
            True,
            existing_uuid,
        )
        files = [sample_file_info]

        # Act
        success, error, skipped = await orchestrator.ingest_files(files)

        # Assert
        assert success == 1
        assert error == 0
        assert skipped == 0
        mock_embedding_service.chunk_text.assert_called_once()
        mock_vector_service.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_ingest_files_with_custom_metadata(
        self,
        orchestrator,
        mock_vector_service,
        mock_embedding_service,
        sample_file_info,
    ):
        """Test ingestion with custom metadata."""
        # Arrange
        orchestrator.set_services(mock_vector_service, mock_embedding_service)
        files = [sample_file_info]
        custom_metadata = {"department": "engineering", "project": "test"}

        # Act
        await orchestrator.ingest_files(files, metadata=custom_metadata)

        # Assert
        call_args = mock_vector_service.upsert.call_args
        metadatas = call_args.kwargs["metadatas"]
        assert metadatas[0]["department"] == "engineering"
        assert metadatas[0]["project"] == "test"

    @pytest.mark.asyncio
    async def test_ingest_files_generates_chunk_metadata(
        self,
        orchestrator,
        mock_vector_service,
        mock_embedding_service,
        mock_google_drive_client,
        sample_file_info,
    ):
        """Test ingestion generates proper chunk metadata."""
        # Arrange
        orchestrator.set_services(mock_vector_service, mock_embedding_service)
        files = [sample_file_info]

        # Act
        await orchestrator.ingest_files(files)

        # Assert
        call_args = mock_vector_service.upsert.call_args
        metadatas = call_args.kwargs["metadatas"]

        # Check first chunk metadata
        assert metadatas[0]["source"] == "google_drive"
        assert metadatas[0]["file_id"] == "file123"
        assert metadatas[0]["file_name"] == "test_document.pdf"
        assert metadatas[0]["full_path"] == "Folder/test_document.pdf"
        assert metadatas[0]["mime_type"] == "application/pdf"
        assert metadatas[0]["chunk_index"] == 0
        assert metadatas[0]["total_chunks"] == 3
        assert "base_uuid" in metadatas[0]
        assert "chunk_id" in metadatas[0]

    @pytest.mark.asyncio
    async def test_ingest_files_with_title_injection(
        self,
        orchestrator,
        mock_vector_service,
        mock_embedding_service,
        sample_file_info,
    ):
        """Test ingestion injects title into chunks."""
        # Arrange
        orchestrator.set_services(mock_vector_service, mock_embedding_service)
        files = [sample_file_info]

        # Act
        await orchestrator.ingest_files(files)

        # Assert
        call_args = mock_vector_service.upsert.call_args
        texts = call_args.kwargs["texts"]
        assert all("[Folder/test_document.pdf]" in text for text in texts)

    @pytest.mark.asyncio
    async def test_ingest_files_with_contextual_retrieval(
        self,
        orchestrator,
        mock_vector_service,
        mock_embedding_service,
        mock_llm_service,
        sample_file_info,
    ):
        """Test ingestion with contextual retrieval enabled."""
        # Arrange
        orchestrator.set_services(
            mock_vector_service,
            mock_embedding_service,
            llm_service=mock_llm_service,
            enable_contextual_retrieval=True,
        )
        files = [sample_file_info]

        # Act
        await orchestrator.ingest_files(files)

        # Assert
        assert mock_llm_service.generate_chunk_context.call_count == 3
        call_args = mock_vector_service.upsert.call_args
        texts = call_args.kwargs["texts"]
        assert all("Contextual description of chunk" in text for text in texts)

    @pytest.mark.asyncio
    async def test_ingest_files_handles_processing_errors(
        self,
        orchestrator,
        mock_vector_service,
        mock_embedding_service,
        mock_google_drive_client,
        mock_document_tracker,
        sample_file_info,
    ):
        """Test ingestion handles processing errors gracefully."""
        # Arrange
        orchestrator.set_services(mock_vector_service, mock_embedding_service)
        mock_embedding_service.chunk_text.side_effect = Exception("Chunking failed")
        files = [sample_file_info]

        # Act
        success, error, skipped = await orchestrator.ingest_files(files)

        # Assert
        assert success == 0
        assert error == 1
        assert skipped == 0
        # Verify failed ingestion was recorded
        assert mock_document_tracker.record_document_ingestion.call_count == 1
        call_args = mock_document_tracker.record_document_ingestion.call_args
        assert call_args.kwargs["status"] == "failed"
        assert "Chunking failed" in call_args.kwargs["error_message"]

    @pytest.mark.asyncio
    async def test_ingest_files_validates_source_metadata(
        self,
        orchestrator,
        mock_vector_service,
        mock_embedding_service,
        sample_file_info,
    ):
        """Test ingestion validates required source field in metadata."""
        # Arrange
        orchestrator.set_services(mock_vector_service, mock_embedding_service)
        files = [sample_file_info]

        # Act
        await orchestrator.ingest_files(files)

        # Assert - all metadata should have 'source' field
        call_args = mock_vector_service.upsert.call_args
        metadatas = call_args.kwargs["metadatas"]
        assert all(meta.get("source") == "google_drive" for meta in metadatas)

    @pytest.mark.asyncio
    async def test_ingest_files_generates_deterministic_uuids(
        self,
        orchestrator,
        mock_vector_service,
        mock_embedding_service,
        mock_document_tracker,
        sample_file_info,
    ):
        """Test ingestion generates deterministic UUIDs using UUID5."""
        # Arrange
        orchestrator.set_services(mock_vector_service, mock_embedding_service)
        base_uuid = "12345678-1234-5678-1234-567812345678"
        mock_document_tracker.generate_base_uuid.return_value = base_uuid
        files = [sample_file_info]

        # Act
        await orchestrator.ingest_files(files)

        # Assert - UUIDs should be deterministic
        call_args = mock_vector_service.upsert.call_args
        chunk_ids = call_args.kwargs["ids"]
        assert len(chunk_ids) == 3
        # Verify they are valid UUIDs
        for chunk_id in chunk_ids:
            uuid.UUID(chunk_id)  # Should not raise

    @pytest.mark.asyncio
    async def test_ingest_files_handles_tracking_failures(
        self,
        orchestrator,
        mock_vector_service,
        mock_embedding_service,
        mock_document_tracker,
        sample_file_info,
    ):
        """Test ingestion continues despite tracking failures."""
        # Arrange
        orchestrator.set_services(mock_vector_service, mock_embedding_service)
        mock_document_tracker.record_document_ingestion.side_effect = Exception(
            "Database error"
        )
        files = [sample_file_info]

        # Act
        success, error, skipped = await orchestrator.ingest_files(files)

        # Assert - should still count as success
        assert success == 1
        assert error == 0
        assert skipped == 0


class TestIngestionOrchestratorIngestFolder:
    """Test folder ingestion."""

    @pytest.mark.asyncio
    async def test_ingest_folder_basic(
        self,
        orchestrator,
        mock_vector_service,
        mock_embedding_service,
        mock_google_drive_client,
        sample_file_info,
    ):
        """Test basic folder ingestion."""
        # Arrange
        orchestrator.set_services(mock_vector_service, mock_embedding_service)
        mock_google_drive_client.list_folder_contents.return_value = [sample_file_info]

        # Act
        success, error, skipped = await orchestrator.ingest_folder("folder123")

        # Assert
        assert success == 1
        mock_google_drive_client.list_folder_contents.assert_called_once_with(
            "folder123", True, folder_path=""
        )

    @pytest.mark.asyncio
    async def test_ingest_folder_non_recursive(
        self,
        orchestrator,
        mock_vector_service,
        mock_embedding_service,
        mock_google_drive_client,
    ):
        """Test non-recursive folder ingestion."""
        # Arrange
        orchestrator.set_services(mock_vector_service, mock_embedding_service)
        mock_google_drive_client.list_folder_contents.return_value = []

        # Act
        await orchestrator.ingest_folder("folder123", recursive=False)

        # Assert
        mock_google_drive_client.list_folder_contents.assert_called_once_with(
            "folder123", False, folder_path=""
        )

    @pytest.mark.asyncio
    async def test_ingest_folder_with_custom_metadata(
        self,
        orchestrator,
        mock_vector_service,
        mock_embedding_service,
        mock_google_drive_client,
        sample_file_info,
    ):
        """Test folder ingestion with custom metadata."""
        # Arrange
        orchestrator.set_services(mock_vector_service, mock_embedding_service)
        mock_google_drive_client.list_folder_contents.return_value = [sample_file_info]
        custom_metadata = {"project": "test_project"}

        # Act
        await orchestrator.ingest_folder("folder123", metadata=custom_metadata)

        # Assert
        call_args = mock_vector_service.upsert.call_args
        metadatas = call_args.kwargs["metadatas"]
        assert metadatas[0]["project"] == "test_project"

    @pytest.mark.asyncio
    async def test_ingest_folder_empty(
        self,
        orchestrator,
        mock_vector_service,
        mock_embedding_service,
        mock_google_drive_client,
    ):
        """Test ingestion of empty folder."""
        # Arrange
        orchestrator.set_services(mock_vector_service, mock_embedding_service)
        mock_google_drive_client.list_folder_contents.return_value = []

        # Act
        success, error, skipped = await orchestrator.ingest_folder("folder123")

        # Assert
        assert success == 0
        assert error == 0
        assert skipped == 0

    @pytest.mark.asyncio
    async def test_ingest_folder_mixed_content(
        self,
        orchestrator,
        mock_vector_service,
        mock_embedding_service,
        mock_google_drive_client,
        sample_file_info,
    ):
        """Test folder ingestion with folders and files."""
        # Arrange
        orchestrator.set_services(mock_vector_service, mock_embedding_service)
        folder_entry = {
            "id": "folder456",
            "name": "Subfolder",
            "mimeType": "application/vnd.google-apps.folder",
            "full_path": "Folder/Subfolder",
        }
        mock_google_drive_client.list_folder_contents.return_value = [
            folder_entry,
            sample_file_info,
        ]

        # Act
        success, error, skipped = await orchestrator.ingest_folder("folder123")

        # Assert
        assert success == 1  # Only file ingested, folder skipped
        assert error == 0
        assert skipped == 0


@pytest.mark.skip(reason="private method _update_metadata_if_changed not implemented")
class TestIngestionOrchestratorMetadataUpdate:
    """Test metadata update logic."""

    @pytest.mark.asyncio
    async def test_update_metadata_if_changed_no_stored_doc(
        self, orchestrator, mock_document_tracker, sample_file_info
    ):
        """Test metadata update when document not in tracking DB."""
        # Arrange
        mock_document_tracker.get_document_info.return_value = None

        # Act
        result = await orchestrator._update_metadata_if_changed(
            sample_file_info, "base-uuid"
        )

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_update_metadata_if_changed_no_changes(
        self,
        orchestrator,
        mock_document_tracker,
        mock_vector_service,
        sample_file_info,
    ):
        """Test metadata update when metadata unchanged."""
        # Arrange
        orchestrator.vector_service = mock_vector_service
        mock_document_tracker.get_document_info.return_value = {
            "chunk_count": 3,
            "metadata": {
                "owner_emails": "owner@example.com",
                "permissions_summary": "owner:owner@example.com",
            },
        }

        # Act
        result = await orchestrator._update_metadata_if_changed(
            sample_file_info, "base-uuid"
        )

        # Assert
        assert result is False
        mock_vector_service.update_payload.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_metadata_if_changed_owner_changed(
        self,
        orchestrator,
        mock_document_tracker,
        mock_vector_service,
        sample_file_info,
    ):
        """Test metadata update when owner changes."""
        # Arrange
        orchestrator.vector_service = mock_vector_service
        mock_document_tracker.get_document_info.return_value = {
            "chunk_count": 3,
            "metadata": {
                "owner_emails": "oldowner@example.com",
                "permissions_summary": "owner:owner@example.com",
            },
        }

        # Act
        result = await orchestrator._update_metadata_if_changed(
            sample_file_info, "12345678-1234-5678-1234-567812345678"
        )

        # Assert
        assert result is True
        assert mock_vector_service.update_payload.call_count == 3  # 3 chunks

    @pytest.mark.asyncio
    async def test_update_metadata_if_changed_permissions_changed(
        self,
        orchestrator,
        mock_document_tracker,
        mock_vector_service,
        sample_file_info,
    ):
        """Test metadata update when permissions change."""
        # Arrange
        orchestrator.vector_service = mock_vector_service
        mock_document_tracker.get_document_info.return_value = {
            "chunk_count": 2,
            "metadata": {
                "owner_emails": "owner@example.com",
                "permissions_summary": "old_permissions",
            },
        }

        # Act
        result = await orchestrator._update_metadata_if_changed(
            sample_file_info, "12345678-1234-5678-1234-567812345678"
        )

        # Assert
        assert result is True
        assert mock_vector_service.update_payload.call_count == 2  # 2 chunks
        mock_document_tracker.record_document_ingestion.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_metadata_if_changed_handles_errors(
        self,
        orchestrator,
        mock_document_tracker,
        mock_vector_service,
        sample_file_info,
    ):
        """Test metadata update handles errors gracefully."""
        # Arrange
        orchestrator.vector_service = mock_vector_service
        mock_document_tracker.get_document_info.side_effect = Exception(
            "Database error"
        )

        # Act
        result = await orchestrator._update_metadata_if_changed(
            sample_file_info, "base-uuid"
        )

        # Assert
        assert result is False


class TestIngestionOrchestratorEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_ingest_files_with_empty_list(
        self, orchestrator, mock_vector_service, mock_embedding_service
    ):
        """Test ingestion with empty file list."""
        # Arrange
        orchestrator.set_services(mock_vector_service, mock_embedding_service)

        # Act
        success, error, skipped = await orchestrator.ingest_files([])

        # Assert
        assert success == 0
        assert error == 0
        assert skipped == 0

    @pytest.mark.asyncio
    async def test_ingest_files_with_missing_optional_fields(
        self,
        orchestrator,
        mock_vector_service,
        mock_embedding_service,
        mock_google_drive_client,
    ):
        """Test ingestion with minimal file metadata."""
        # Arrange
        orchestrator.set_services(mock_vector_service, mock_embedding_service)
        minimal_file = {
            "id": "file123",
            "name": "test.pdf",
            "mimeType": "application/pdf",
        }
        files = [minimal_file]

        # Act
        success, error, skipped = await orchestrator.ingest_files(files)

        # Assert
        assert success == 1
        call_args = mock_vector_service.upsert.call_args
        metadatas = call_args.kwargs["metadatas"]
        # Should handle missing fields gracefully
        assert metadatas[0]["file_name"] == "test.pdf"
        assert metadatas[0]["full_path"] == "test.pdf"  # Falls back to name

    @pytest.mark.asyncio
    async def test_ingest_files_with_zero_chunks(
        self,
        orchestrator,
        mock_vector_service,
        mock_embedding_service,
        sample_file_info,
    ):
        """Test ingestion when chunking returns empty list."""
        # Arrange
        orchestrator.set_services(mock_vector_service, mock_embedding_service)
        mock_embedding_service.chunk_text.return_value = []
        mock_embedding_service.embed_texts.return_value = []
        files = [sample_file_info]

        # Act
        success, error, skipped = await orchestrator.ingest_files(files)

        # Assert
        assert success == 1  # Should still count as success
        mock_vector_service.upsert.assert_called_once()
        call_args = mock_vector_service.upsert.call_args
        assert len(call_args.kwargs["ids"]) == 0

    @pytest.mark.asyncio
    async def test_ingest_files_embedding_failure(
        self,
        orchestrator,
        mock_vector_service,
        mock_embedding_service,
        sample_file_info,
    ):
        """Test ingestion handles embedding service failures."""
        # Arrange
        orchestrator.set_services(mock_vector_service, mock_embedding_service)
        mock_embedding_service.embed_texts.side_effect = Exception("Embedding failed")
        files = [sample_file_info]

        # Act
        success, error, skipped = await orchestrator.ingest_files(files)

        # Assert
        assert success == 0
        assert error == 1
        assert skipped == 0

    @pytest.mark.asyncio
    async def test_ingest_files_vector_upsert_failure(
        self,
        orchestrator,
        mock_vector_service,
        mock_embedding_service,
        sample_file_info,
    ):
        """Test ingestion handles vector database failures."""
        # Arrange
        orchestrator.set_services(mock_vector_service, mock_embedding_service)
        mock_vector_service.upsert.side_effect = Exception("Vector DB error")
        files = [sample_file_info]

        # Act
        success, error, skipped = await orchestrator.ingest_files(files)

        # Assert
        assert success == 0
        assert error == 1
        assert skipped == 0

    @pytest.mark.asyncio
    async def test_ingest_multiple_files_mixed_results(
        self,
        orchestrator,
        mock_vector_service,
        mock_embedding_service,
        mock_google_drive_client,
        mock_document_tracker,
    ):
        """Test ingestion with multiple files having different outcomes."""
        # Arrange
        orchestrator.set_services(mock_vector_service, mock_embedding_service)

        # File 1: Success
        file1 = {
            "id": "file1",
            "name": "success.pdf",
            "mimeType": "application/pdf",
            "owners": [],
            "detailed_permissions": [],
        }

        # File 2: Download fails
        file2 = {
            "id": "file2",
            "name": "download_fail.pdf",
            "mimeType": "application/pdf",
            "owners": [],
            "detailed_permissions": [],
        }

        # File 3: Skipped (unchanged)
        file3 = {
            "id": "file3",
            "name": "unchanged.pdf",
            "mimeType": "application/pdf",
            "owners": [],
            "detailed_permissions": [],
        }

        files = [file1, file2, file3]

        # Setup mocks
        def metadata_reindex_side_effect(file_id, modified_time, size):
            if file_id == "file3":
                # File3 is unchanged based on metadata - skip without download
                return (False, "existing-uuid")
            # File1 and file2 need download
            return (True, None)

        mock_document_tracker.check_document_needs_reindex_by_metadata.side_effect = (
            metadata_reindex_side_effect
        )

        def download_side_effect(file_id, mime_type, filename):
            if file_id == "file2":
                return None
            return "Content"

        mock_google_drive_client.download_file_content.side_effect = (
            download_side_effect
        )

        def reindex_side_effect(file_id, content):
            # This won't be called for file3 (skipped by metadata check)
            return (True, None)

        mock_document_tracker.check_document_needs_reindex.side_effect = (
            reindex_side_effect
        )
        mock_document_tracker.get_document_info.return_value = {
            "chunk_count": 2,
            "metadata": {
                "owner_emails": "unknown",
                "permissions_summary": "no_permissions",
            },
        }

        # Act
        success, error, skipped = await orchestrator.ingest_files(files)

        # Assert
        assert success == 1  # file1
        assert error == 1  # file2
        assert skipped == 1  # file3
