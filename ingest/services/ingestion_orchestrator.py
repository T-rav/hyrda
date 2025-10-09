"""
Ingestion Orchestrator

Main service that coordinates the ingestion process by:
- Managing Google Drive client and document processor
- Orchestrating file scanning and processing
- Coordinating with vector database and embedding services
- Managing the overall ingestion workflow
"""

import sys
from datetime import datetime
from pathlib import Path

from .document_tracking_service import DocumentTrackingService
from .google_drive_client import GoogleDriveClient


class IngestionOrchestrator:
    """Main orchestrator for the document ingestion process."""

    def __init__(
        self, credentials_file: str | None = None, token_file: str | None = None
    ):
        """
        Initialize the ingestion orchestrator.

        Args:
            credentials_file: Path to Google OAuth2 credentials JSON file
            token_file: Path to store/retrieve OAuth2 token
        """
        self.google_drive_client = GoogleDriveClient(credentials_file, token_file)
        self.document_tracker = DocumentTrackingService()
        self.vector_service = None
        self.embedding_service = None
        self.contextual_retrieval_service = None
        self.llm_service = None
        self.enable_contextual_retrieval = False

    def authenticate(self) -> bool:
        """
        Authenticate with Google Drive API.

        Returns:
            bool: True if authentication successful, False otherwise
        """
        return self.google_drive_client.authenticate()

    def set_services(
        self,
        vector_service,
        embedding_service=None,
        llm_service=None,
        enable_contextual_retrieval=False,
    ):
        """
        Set the vector database and embedding services.

        Args:
            vector_service: Vector database service instance
            embedding_service: Embedding service instance
            llm_service: LLM service for contextual retrieval
            enable_contextual_retrieval: Whether to use contextual retrieval
        """
        self.vector_service = vector_service
        self.embedding_service = embedding_service
        self.llm_service = llm_service
        self.enable_contextual_retrieval = enable_contextual_retrieval

    async def ingest_files(
        self, files: list[dict], metadata: dict | None = None
    ) -> tuple[int, int]:
        """
        Ingest files into the vector database.

        Args:
            files: List of file metadata from Google Drive
            metadata: Additional metadata to add to each document

        Returns:
            Tuple of (success_count, error_count)
        """
        # Check that services are properly initialized
        if not self.vector_service:
            raise RuntimeError(
                "Vector service not initialized. Services must be set before calling ingest_files."
            )

        # Some services have built-in embedding service
        if hasattr(self.vector_service, "embedding_service"):
            # Service has built-in embedding service
            pass
        elif not self.embedding_service:
            raise RuntimeError(
                "Embedding service not initialized. Services must be set before calling ingest_files."
            )

        success_count = 0
        error_count = 0

        for file_info in files:
            try:
                # Skip folders and unsupported file types
                if file_info["mimeType"] == "application/vnd.google-apps.folder":
                    continue

                print(f"Processing: {file_info['name']}")

                # Download file content
                content = self.google_drive_client.download_file_content(
                    file_info["id"], file_info["mimeType"]
                )
                if not content:
                    print(f"Failed to download: {file_info['name']}")
                    error_count += 1
                    continue

                # Check if document needs reindexing (idempotent ingestion)
                needs_reindex, existing_uuid = (
                    self.document_tracker.check_document_needs_reindex(
                        file_info["id"], content
                    )
                )

                if not needs_reindex:
                    print(f"⏭️  Skipping (unchanged): {file_info['name']}")
                    success_count += 1
                    continue

                if existing_uuid:
                    print(f"🔄 Content changed, reindexing: {file_info['name']}")

                # Generate or reuse UUID for this document
                base_uuid = existing_uuid or self.document_tracker.generate_base_uuid(
                    file_info["id"]
                )

                # Prepare comprehensive document metadata
                doc_metadata = {
                    "source": "google_drive",
                    "file_id": file_info["id"],
                    "file_name": file_info["name"],
                    "full_path": file_info.get("full_path", file_info["name"]),
                    "folder_path": file_info.get("folder_path", ""),
                    "mime_type": file_info["mimeType"],
                    "modified_time": file_info.get("modifiedTime"),
                    "created_time": file_info.get("createdTime"),
                    "size": file_info.get("size"),
                    "web_view_link": file_info.get("webViewLink"),
                    "owner_emails": GoogleDriveClient.get_owner_emails(
                        file_info.get("owners", [])
                    ),
                    "permissions_summary": GoogleDriveClient.get_permissions_summary(
                        file_info.get("detailed_permissions", [])
                    ),
                    "ingested_at": datetime.utcnow().isoformat(),
                }

                # Add any additional metadata provided
                if metadata:
                    doc_metadata.update(metadata)

                # Chunk the content using embedding service
                chunks = self.embedding_service.chunk_text(content)

                # Add contextual descriptions if enabled
                if self.enable_contextual_retrieval and self.llm_service:
                    print(f"Adding contextual descriptions to {len(chunks)} chunks...")
                    enhanced_chunks = []
                    for chunk in chunks:
                        context = await self.llm_service.generate_chunk_context(
                            content, chunk
                        )
                        enhanced_chunk = f"{context}\n\n{chunk}"
                        enhanced_chunks.append(enhanced_chunk)
                    chunks = enhanced_chunks

                # Generate embeddings
                embeddings = await self.embedding_service.embed_texts(chunks)

                # Prepare metadata for each chunk
                chunk_metadata = []
                chunk_ids = []
                for i, chunk in enumerate(chunks):
                    chunk_meta = doc_metadata.copy()
                    chunk_meta["chunk_id"] = f"{file_info['id']}_chunk_{i}"
                    chunk_meta["chunk_index"] = i
                    chunk_meta["total_chunks"] = len(chunks)
                    chunk_metadata.append(chunk_meta)
                    chunk_ids.append(f"{base_uuid}_{i}")

                # Upsert to vector store
                await self.vector_service.upsert(
                    ids=chunk_ids,
                    embeddings=embeddings,
                    metadatas=chunk_metadata,
                    texts=chunks,
                )
                print(f"   📊 Ingested {len(chunks)} chunks")

                # Record successful ingestion in tracking table
                try:
                    # Determine chunk count based on which path we took
                    chunk_count = len(chunks)

                    self.document_tracker.record_document_ingestion(
                        google_drive_id=file_info["id"],
                        file_path=file_info.get("full_path", file_info["name"]),
                        document_name=file_info["name"],
                        content=content,
                        vector_uuid=base_uuid,
                        chunk_count=chunk_count,
                        mime_type=file_info["mimeType"],
                        file_size=int(file_info.get("size", 0))
                        if file_info.get("size")
                        else None,
                        metadata={
                            "owner_emails": GoogleDriveClient.get_owner_emails(
                                file_info.get("owners", [])
                            ),
                            "permissions_summary": GoogleDriveClient.get_permissions_summary(
                                file_info.get("detailed_permissions", [])
                            ),
                            "web_view_link": file_info.get("webViewLink"),
                        },
                        status="success",
                    )
                except Exception as tracking_error:
                    print(f"⚠️  Failed to record ingestion tracking: {tracking_error}")

                print(f"✅ Successfully ingested: {file_info['name']}")
                success_count += 1

            except Exception as e:
                print(f"❌ Error processing {file_info.get('name', 'unknown')}: {e}")
                error_count += 1

                # Record failed ingestion
                try:
                    base_uuid = self.document_tracker.generate_base_uuid(
                        file_info["id"]
                    )
                    self.document_tracker.record_document_ingestion(
                        google_drive_id=file_info["id"],
                        file_path=file_info.get("full_path", file_info["name"]),
                        document_name=file_info["name"],
                        content="",  # No content on failure
                        vector_uuid=base_uuid,
                        chunk_count=0,
                        mime_type=file_info["mimeType"],
                        file_size=int(file_info.get("size", 0))
                        if file_info.get("size")
                        else None,
                        status="failed",
                        error_message=str(e),
                    )
                except Exception:
                    pass  # Don't fail on tracking failures

        return success_count, error_count

    async def ingest_folder(
        self, folder_id: str, recursive: bool = True, metadata: dict | None = None
    ) -> tuple[int, int]:
        """
        Ingest all files from a Google Drive folder.

        Args:
            folder_id: Google Drive folder ID
            recursive: Whether to include subfolders
            metadata: Additional metadata to add to each document

        Returns:
            Tuple of (success_count, error_count)
        """
        print(f"Scanning folder: {folder_id} (recursive: {recursive})")
        files = self.google_drive_client.list_folder_contents(
            folder_id, recursive, folder_path=""
        )

        # Debug output
        if not files:
            print("Found 0 items - folder appears to be empty or inaccessible")
        else:
            folders = [
                f
                for f in files
                if f["mimeType"] == "application/vnd.google-apps.folder"
            ]
            documents = [
                f
                for f in files
                if f["mimeType"] != "application/vnd.google-apps.folder"
            ]

            print(f"Found {len(files)} total items:")
            print(f"  📁 {len(folders)} folders")
            print(f"  📄 {len(documents)} documents")

            if folders:
                print("  Folders found:")
                for folder in folders[:5]:  # Show first 5 folders
                    print(f"    - {folder['full_path']}")
                if len(folders) > 5:
                    print(f"    ... and {len(folders) - 5} more folders")

            if documents:
                print("  Documents found:")
                for doc in documents[:5]:  # Show first 5 documents
                    print(f"    - {doc['full_path']} ({doc['mimeType']})")
                if len(documents) > 5:
                    print(f"    ... and {len(documents) - 5} more documents")

        return await self.ingest_files(files, metadata)
