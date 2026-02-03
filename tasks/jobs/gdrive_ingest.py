"""Google Drive document ingestion job for scheduled RAG updates."""

import logging
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
        "credential_id",
    ]
    # Define parameter groups: at least one from each group is required
    PARAM_GROUPS = [
        {
            "name": "source",
            "description": "Google Drive source",
            "params": ["folder_id", "file_id"],
            "min_required": 1,
            "max_required": 1,
            "error_message": "Provide either folder_id OR file_id (not both, not neither)",
        }
    ]

    def __init__(self, settings: TasksSettings, **kwargs: Any):
        super().__init__(settings, **kwargs)
        self.validate_params()

    def validate_params(self) -> bool:
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
        # Get job parameters
        folder_id = self.params.get("folder_id")
        file_id = self.params.get("file_id")
        recursive = self.params.get("recursive", True)
        metadata = self.params.get("metadata", {})
        credential_id = self.params.get("credential_id")

        if not credential_id:
            raise ValueError("credential_id is required")

        logger.info(
            f"Starting Google Drive ingestion: "
            f"folder_id={folder_id}, file_id={file_id}, "
            f"recursive={recursive}, credential={credential_id}"
        )

        try:
            # Import services (now located in tasks/services/gdrive)
            from models.base import get_db_session
            from models.oauth_credential import OAuthCredential
            from services.encryption_service import get_encryption_service
            from services.gdrive.ingestion_orchestrator import IngestionOrchestrator

            encryption_service = get_encryption_service()

            with get_db_session() as db_session:
                credential = (
                    db_session.query(OAuthCredential)
                    .filter(OAuthCredential.credential_id == credential_id)
                    .first()
                )

                if not credential:
                    raise FileNotFoundError(
                        f"Credential not found in database: {credential_id}"
                    )

                # Decrypt token
                token_json = encryption_service.decrypt(credential.encrypted_token)

                # Check if token is expired or expiring soon and refresh if needed
                import json
                from datetime import UTC, datetime, timedelta

                from google.auth.transport.requests import Request
                from google.oauth2.credentials import Credentials

                token_data = json.loads(token_json)
                should_refresh = False

                # Check token expiry
                if token_data.get("expiry"):
                    try:
                        expiry = datetime.fromisoformat(
                            token_data["expiry"].replace("Z", "+00:00")
                        )
                        now = datetime.now(UTC)
                        # Refresh if expired or expiring within 5 minutes
                        # Since tokens expire after 1 hour, this handles both:
                        # - Frequent jobs: proactively refreshes before expiry
                        # - Infrequent jobs: token already expired, gets refreshed
                        if expiry <= now + timedelta(minutes=5):
                            should_refresh = True
                            logger.info(
                                f"Token expired or expiring soon for {credential_id}, refreshing..."
                            )
                    except Exception as e:
                        logger.warning(f"Could not parse token expiry: {e}")

                # Refresh token if needed
                if should_refresh and token_data.get("refresh_token"):
                    try:
                        creds = Credentials.from_authorized_user_info(token_data)
                        creds.refresh(Request())

                        # Update token in database
                        new_token_json = creds.to_json()
                        new_encrypted_token = encryption_service.encrypt(new_token_json)

                        new_token_data = json.loads(new_token_json)
                        new_token_metadata = {
                            "scopes": new_token_data.get("scopes", []),
                            "token_uri": new_token_data.get("token_uri"),
                            "expiry": new_token_data.get("expiry"),
                        }

                        credential.encrypted_token = new_encrypted_token
                        credential.token_metadata = new_token_metadata
                        logger.info(f"Token refreshed successfully for {credential_id}")

                        # Use the new token
                        token_json = new_token_json
                    except Exception as e:
                        logger.error(f"Token refresh failed: {e}")
                        # Continue with old token and let it fail if truly expired
                        # This allows Google's library to handle the error gracefully

                # Update last_used_at
                credential.last_used_at = datetime.now(UTC)
                db_session.commit()

            # Create temporary token file for ingestion orchestrator
            # (Orchestrator expects a file path - we can refactor this later)
            import tempfile

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                f.write(token_json)
                token_file = f.name

            try:
                # Get OpenAI API key for audio/video transcription
                import os

                openai_api_key = os.getenv("OPENAI_API_KEY")

                # Initialize orchestrator with temporary token file
                orchestrator = IngestionOrchestrator(
                    credentials_file=None,  # Not used - OAuth handled by env vars
                    token_file=token_file,
                    openai_api_key=openai_api_key,
                )

                # Authenticate with Google Drive
                logger.info("Authenticating with Google Drive...")
                if not orchestrator.authenticate():
                    raise RuntimeError("Google Drive authentication failed")

                # Initialize vector and embedding services using environment variables
                logger.info("Initializing vector database and embedding service...")
                from services.openai_embeddings import OpenAIEmbeddings
                from services.qdrant_client import QdrantClient

                # Initialize embedding provider (reads from env vars)
                embedding_provider = OpenAIEmbeddings()

                # Initialize vector store (reads from env vars)
                vector_store = QdrantClient()
                await vector_store.initialize()

                # Initialize LLM service for contextual retrieval if enabled
                # Note: Contextual retrieval is currently disabled as SimpleLLMService
                # is not implemented in the tasks service yet
                llm_service = None
                logger.info("Contextual retrieval not available in tasks service")

                # Set services in orchestrator
                orchestrator.set_services(
                    vector_store,
                    embedding_provider,
                    llm_service=llm_service,
                    enable_contextual_retrieval=llm_service is not None,
                )

                # Execute ingestion based on folder_id or file_id
                if folder_id:
                    logger.info(
                        f"Ingesting folder: {folder_id} (recursive={recursive})"
                    )
                    (
                        success_count,
                        error_count,
                        skipped_count,
                    ) = await orchestrator.ingest_folder(
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
                        file_info.get("parents", [""])[0]
                        if file_info.get("parents")
                        else ""
                    )

                    # Ingest as single-item list
                    files = [file_info]
                    (
                        success_count,
                        error_count,
                        skipped_count,
                    ) = await orchestrator.ingest_files(files, metadata=metadata)

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

            finally:
                # Clean up temporary token file
                import os

                if os.path.exists(token_file):
                    os.unlink(token_file)
                    logger.debug(f"Cleaned up temporary token file: {token_file}")

        except Exception as e:
            logger.error(f"Error in Google Drive ingestion: {str(e)}")
            raise
