"""Google Drive document ingestion job for scheduled RAG updates."""

import logging
import sys
from pathlib import Path
from typing import Any

from config.settings import TasksSettings

from .base_job import BaseJob

logger = logging.getLogger(__name__)


class GDriveIngestJob(BaseJob):
    """Job to ingest documents from Google Drive into RAG system."""

    JOB_NAME = "Google Drive Ingestion"
    JOB_DESCRIPTION = "Ingest documents from Google Drive folder or file into RAG system with OAuth credentials"
    REQUIRED_PARAMS = []
    OPTIONAL_PARAMS = [
        "folder_id",
        "file_id",
        "recursive",
        "metadata",
        "credentials_file",
        "token_file",
    ]

    def __init__(self, settings: TasksSettings, **kwargs: Any):
        """Initialize the Google Drive ingestion job."""
        super().__init__(settings, **kwargs)
        self.validate_params()

    def validate_params(self) -> bool:
        """Validate job parameters."""
        super().validate_params()

        # Must provide either folder_id or file_id
        folder_id = self.params.get("folder_id")
        file_id = self.params.get("file_id")

        if not folder_id and not file_id:
            raise ValueError("Must provide either 'folder_id' or 'file_id' parameter")

        if folder_id and file_id:
            raise ValueError("Cannot provide both 'folder_id' and 'file_id' parameters")

        # Validate credentials file path if provided
        credentials_file = self.params.get("credentials_file")
        if credentials_file and not Path(credentials_file).exists():
            raise ValueError(f"Credentials file not found: {credentials_file}")

        return True

    async def _execute_job(self) -> dict[str, Any]:
        """Execute the Google Drive ingestion job."""
        # Get job parameters
        folder_id = self.params.get("folder_id")
        file_id = self.params.get("file_id")
        recursive = self.params.get("recursive", True)
        metadata = self.params.get("metadata", {})
        credentials_file = self.params.get("credentials_file")
        token_file = self.params.get("token_file")

        logger.info(
            f"Starting Google Drive ingestion: "
            f"folder_id={folder_id}, file_id={file_id}, "
            f"recursive={recursive}"
        )

        try:
            # Add ingest directory to Python path
            ingest_path = str(Path(__file__).parent.parent.parent / "ingest")
            if ingest_path not in sys.path:
                sys.path.insert(0, ingest_path)

            # Import ingest orchestrator
            from ingest_config import EmbeddingConfig, LLMConfig, RAGConfig, VectorConfig
            from services import IngestionOrchestrator
            from services.embedding_provider import OpenAIEmbeddingProvider
            from services.llm_wrapper import SimpleLLMService
            from services.vector_store import QdrantVectorStore

            # Resolve token_file path relative to tasks directory if it's a relative path
            if token_file and not Path(token_file).is_absolute():
                tasks_dir = Path(__file__).parent.parent
                token_file = str(tasks_dir / token_file)

            # Initialize orchestrator with credentials
            orchestrator = IngestionOrchestrator(
                credentials_file=credentials_file,
                token_file=token_file,
            )

            # Authenticate with Google Drive
            logger.info("Authenticating with Google Drive...")
            if not orchestrator.authenticate():
                raise RuntimeError("Google Drive authentication failed")

            # Initialize vector and embedding services
            logger.info("Initializing vector database and embedding service...")
            vector_config = VectorConfig.from_env()
            embedding_config = EmbeddingConfig.from_env()
            llm_config = LLMConfig.from_env()
            rag_config = RAGConfig.from_env()

            # Initialize embedding provider
            embedding_provider = OpenAIEmbeddingProvider(
                api_key=embedding_config.api_key,
                model=embedding_config.model,
            )

            # Initialize vector store
            vector_store = QdrantVectorStore(
                host=vector_config.host,
                port=vector_config.port,
                collection_name=vector_config.collection_name,
                api_key=vector_config.api_key,
                use_https=vector_config.use_https,
            )

            await vector_store.initialize(
                embedding_dimension=embedding_provider.get_dimension()
            )

            # Initialize LLM service for contextual retrieval if enabled
            llm_service = None
            if rag_config.enable_contextual_retrieval and llm_config.api_key:
                llm_service = SimpleLLMService(
                    api_key=llm_config.api_key,
                    model=llm_config.model,
                )
                logger.info("Contextual retrieval enabled")

            # Set services in orchestrator
            orchestrator.set_services(
                vector_store,
                embedding_provider,
                llm_service=llm_service,
                enable_contextual_retrieval=llm_service is not None,
            )

            # Execute ingestion based on folder_id or file_id
            if folder_id:
                logger.info(f"Ingesting folder: {folder_id} (recursive={recursive})")
                success_count, error_count, skipped_count = await orchestrator.ingest_folder(
                    folder_id=folder_id,
                    recursive=recursive,
                    metadata=metadata,
                )
            else:  # file_id
                logger.info(f"Ingesting single file: {file_id}")
                # Get file info with Shared Drive support
                file_info = (
                    orchestrator.google_drive_client.api_service.service.files()
                    .get(
                        fileId=file_id,
                        fields="id, name, mimeType, size, webViewLink, parents, owners, permissions, createdTime, modifiedTime",
                        supportsAllDrives=True,
                    )
                    .execute()
                )

                # Add folder path context
                file_info["folder_path"] = "/"
                file_info["folder_id"] = (
                    file_info.get("parents", [""])[0] if file_info.get("parents") else ""
                )

                # Ingest as single-item list
                files = [file_info]
                success_count, error_count, skipped_count = await orchestrator.ingest_files(
                    files, metadata=metadata
                )

            # Standardized result structure
            processed_count = success_count + error_count + skipped_count

            logger.info(
                f"Google Drive ingestion completed: "
                f"success={success_count}, skipped={skipped_count}, errors={error_count}"
            )

            return {
                # Standardized fields for task run tracking
                "records_processed": processed_count,
                "records_success": success_count,
                "records_failed": error_count,
                # Job-specific details (stored in result_data JSON)
                "records_skipped": skipped_count,
                "folder_id": folder_id,
                "file_id": file_id,
                "recursive": recursive,
                "metadata": metadata,
            }

        except Exception as e:
            logger.error(f"Error in Google Drive ingestion: {str(e)}")
            raise
