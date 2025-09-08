"""
Tests for IngestionOrchestrator service - Fixed version matching actual implementation.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from services.ingestion_orchestrator import IngestionOrchestrator


class TestIngestionOrchestrator:
    """Test cases for IngestionOrchestrator service."""

    @pytest.fixture
    def orchestrator(self):
        """Create IngestionOrchestrator instance for testing."""
        return IngestionOrchestrator()

    @pytest.fixture
    def mock_vector_service(self):
        """Mock vector service for testing."""
        mock_service = AsyncMock()
        mock_service.add_documents = AsyncMock()
        return mock_service

    @pytest.fixture
    def mock_embedding_service(self):
        """Mock embedding service for testing."""
        mock_service = AsyncMock()
        mock_service.get_embeddings = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
        mock_service.settings = Mock()
        mock_service.settings.chunk_size = 1000
        mock_service.settings.chunk_overlap = 200
        return mock_service

    def test_init_default_values(self, orchestrator):
        """Test IngestionOrchestrator initialization with default values."""
        assert orchestrator.google_drive_client is not None
        assert orchestrator.vector_service is None
        assert orchestrator.embedding_service is None

    def test_init_with_custom_files(self):
        """Test initialization with custom credential files."""
        orchestrator = IngestionOrchestrator(
            credentials_file="custom_creds.json",
            token_file="custom_token.json"
        )

        assert orchestrator.google_drive_client.credentials_file == "custom_creds.json"
        assert orchestrator.google_drive_client.token_file == "custom_token.json"

    def test_authenticate(self, orchestrator):
        """Test authentication delegation."""
        orchestrator.google_drive_client.authenticate = Mock(return_value=True)

        result = orchestrator.authenticate()

        assert result is True
        orchestrator.google_drive_client.authenticate.assert_called_once()

    def test_set_services(self, orchestrator):
        """Test setting vector and embedding services."""
        mock_vector = Mock()
        mock_embedding = Mock()

        orchestrator.set_services(mock_vector, mock_embedding)

        assert orchestrator.vector_service == mock_vector
        assert orchestrator.embedding_service == mock_embedding

    @pytest.mark.asyncio
    async def test_ingest_files_no_vector_service(self, orchestrator):
        """Test ingestion without vector service."""
        files = [{'name': 'test.pdf', 'id': 'file1', 'mimeType': 'application/pdf'}]

        with pytest.raises(RuntimeError, match="Vector service not initialized"):
            await orchestrator.ingest_files(files)

    @pytest.mark.asyncio
    async def test_ingest_files_no_embedding_service(self, orchestrator, mock_vector_service):
        """Test ingestion without embedding service."""
        orchestrator.vector_service = mock_vector_service
        files = [{'name': 'test.pdf', 'id': 'file1', 'mimeType': 'application/pdf'}]

        with pytest.raises(RuntimeError, match="Embedding service not initialized"):
            await orchestrator.ingest_files(files)

    @pytest.mark.asyncio
    async def test_ingest_files_success(self, orchestrator, mock_vector_service, mock_embedding_service):
        """Test successful file ingestion."""
        # Setup orchestrator
        orchestrator.vector_service = mock_vector_service
        orchestrator.embedding_service = mock_embedding_service

        # Mock file data
        files = [
            {
                'id': 'file1',
                'name': 'document.pdf',
                'mimeType': 'application/pdf',
                'size': '1024',
                'modifiedTime': '2023-01-01T00:00:00.000Z',
                'createdTime': '2023-01-01T00:00:00.000Z',
                'webViewLink': 'https://drive.google.com/file/d/file1/view',
                'owners': [{'emailAddress': 'owner@example.com', 'displayName': 'Owner'}],
                'detailed_permissions': [],
                'folder_path': 'Documents',
                'full_path': 'Documents/document.pdf'
            }
        ]

        # Mock services
        orchestrator.google_drive_client.download_file_content = Mock(return_value="PDF text content")

        # Mock the chunk_text import by monkey-patching
        def mock_chunk_text(text, **kwargs):
            return ["chunk1", "chunk2"]

        with patch('sys.modules', {'services.embedding_service': Mock(chunk_text=mock_chunk_text)}):
            success_count, error_count = await orchestrator.ingest_files(files)

            assert success_count == 1
            assert error_count == 0

            # Verify service calls
            orchestrator.google_drive_client.download_file_content.assert_called_once()
            mock_embedding_service.get_embeddings.assert_called_once_with(["chunk1", "chunk2"])
            mock_vector_service.add_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_ingest_files_skip_folders(self, orchestrator, mock_vector_service, mock_embedding_service):
        """Test skipping folder files."""
        orchestrator.vector_service = mock_vector_service
        orchestrator.embedding_service = mock_embedding_service

        files = [
            {
                'id': 'folder1',
                'name': 'My Folder',
                'mimeType': 'application/vnd.google-apps.folder'
            }
        ]

        success_count, error_count = await orchestrator.ingest_files(files)

        assert success_count == 0
        assert error_count == 0

    @pytest.mark.asyncio
    async def test_ingest_files_download_failure(self, orchestrator, mock_vector_service, mock_embedding_service):
        """Test handling of download failures."""
        orchestrator.vector_service = mock_vector_service
        orchestrator.embedding_service = mock_embedding_service

        files = [
            {
                'id': 'file1',
                'name': 'document.pdf',
                'mimeType': 'application/pdf',
                'owners': [],
                'detailed_permissions': []
            }
        ]

        orchestrator.google_drive_client.download_file_content = Mock(return_value=None)

        success_count, error_count = await orchestrator.ingest_files(files)

        assert success_count == 0
        assert error_count == 1

    @pytest.mark.asyncio
    async def test_ingest_folder_success(self, orchestrator, mock_vector_service, mock_embedding_service):
        """Test successful folder ingestion."""
        orchestrator.vector_service = mock_vector_service
        orchestrator.embedding_service = mock_embedding_service

        # Mock files from folder
        mock_files = [
            {
                'id': 'file1',
                'name': 'document.pdf',
                'mimeType': 'application/pdf',
                'owners': [],
                'detailed_permissions': [],
                'full_path': 'document.pdf'
            }
        ]

        orchestrator.google_drive_client.list_folder_contents = Mock(return_value=mock_files)
        orchestrator.google_drive_client.download_file_content = Mock(return_value="PDF content")

        # Mock the chunk_text import by monkey-patching
        def mock_chunk_text(text, **kwargs):
            return ["chunk1"]

        with patch('sys.modules', {'services.embedding_service': Mock(chunk_text=mock_chunk_text)}):

            success_count, error_count = await orchestrator.ingest_folder("folder_id")

            assert success_count == 1
            assert error_count == 0

            orchestrator.google_drive_client.list_folder_contents.assert_called_once_with("folder_id", True, folder_path="")

    @pytest.mark.asyncio
    async def test_ingest_folder_empty(self, orchestrator, mock_vector_service, mock_embedding_service):
        """Test ingesting empty folder."""
        orchestrator.vector_service = mock_vector_service
        orchestrator.embedding_service = mock_embedding_service

        orchestrator.google_drive_client.list_folder_contents = Mock(return_value=[])

        success_count, error_count = await orchestrator.ingest_folder("folder_id")

        assert success_count == 0
        assert error_count == 0

    @pytest.mark.asyncio
    async def test_ingest_folder_with_metadata(self, orchestrator, mock_vector_service, mock_embedding_service):
        """Test folder ingestion with custom metadata."""
        orchestrator.vector_service = mock_vector_service
        orchestrator.embedding_service = mock_embedding_service

        mock_files = [
            {
                'id': 'file1',
                'name': 'document.pdf',
                'mimeType': 'application/pdf',
                'owners': [],
                'detailed_permissions': [],
                'full_path': 'document.pdf'
            }
        ]

        orchestrator.google_drive_client.list_folder_contents = Mock(return_value=mock_files)
        orchestrator.google_drive_client.download_file_content = Mock(return_value="PDF content")

        custom_metadata = {'department': 'engineering', 'project': 'docs'}

        # Mock the chunk_text import by monkey-patching
        def mock_chunk_text(text, **kwargs):
            return ["chunk1"]

        with patch('sys.modules', {'services.embedding_service': Mock(chunk_text=mock_chunk_text)}):

            success_count, error_count = await orchestrator.ingest_folder("folder_id", metadata=custom_metadata)

            assert success_count == 1
            assert error_count == 0

            # Verify metadata was passed
            call_kwargs = mock_vector_service.add_documents.call_args[1]
            metadata_list = call_kwargs['metadata']
            assert metadata_list[0]['department'] == 'engineering'
            assert metadata_list[0]['project'] == 'docs'
