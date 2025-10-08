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

        # Some services have built-in embedding service
        if hasattr(vector_service, "embedding_service"):
            self.embedding_service = vector_service.embedding_service

        # Initialize contextual retrieval service if enabled
        if enable_contextual_retrieval and llm_service:
            # Import here to avoid circular dependencies
            sys.path.append(str(Path(__file__).parent.parent.parent / "bot"))
            from services.contextual_retrieval_service import ContextualRetrievalService

            self.contextual_retrieval_service = ContextualRetrievalService(llm_service)

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

                # Check if we're using RAG service with batch ingestion
                if hasattr(self.vector_service, "ingest_documents"):
                    # For RAG service, we need to chunk and generate embeddings first
                    import sys
                    from pathlib import Path

                    sys.path.append(str(Path(__file__).parent.parent.parent / "bot"))
                    from services.embedding_service import chunk_text

                    # Chunk the content
                    chunk_size = getattr(self.vector_service, "embedding_service", None)
                    if chunk_size and hasattr(chunk_size, "settings"):
                        chunks = chunk_text(
                            content,
                            chunk_size=chunk_size.settings.chunk_size,
                            chunk_overlap=chunk_size.settings.chunk_overlap,
                        )
                    else:
                        # Use default chunking
                        chunks = chunk_text(content, chunk_size=1000, chunk_overlap=200)

                    # Add contextual descriptions if enabled
                    if (
                        self.enable_contextual_retrieval
                        and self.contextual_retrieval_service
                    ):
                        print(
                            f"Adding contextual descriptions to {len(chunks)} chunks..."
                        )
                        chunks = await self.contextual_retrieval_service.add_context_to_chunks(
                            chunks,
                            {
                                "file_name": file_info["name"],
                                "full_path": file_info.get(
                                    "full_path", file_info["name"]
                                ),
                                "mimeType": file_info["mimeType"],
                                "createdTime": file_info.get("createdTime"),
                                "owners": file_info.get("owners", []),
                            },
                        )

                    # Generate embeddings using service's embedding service
                    embeddings = (
                        await self.vector_service.embedding_service.get_embeddings(
                            chunks
                        )
                    )

                    # Prepare metadata for each chunk
                    chunk_metadata = []
                    for i, chunk in enumerate(chunks):
                        chunk_meta = doc_metadata.copy()
                        chunk_meta["chunk_id"] = f"{file_info['id']}_chunk_{i}"
                        chunk_meta["chunk_index"] = i
                        chunk_meta["total_chunks"] = len(chunks)
                        chunk_metadata.append(chunk_meta)

                    # Use batch ingestion with proper parameters
                    await self.vector_service.ingest_documents(
                        texts=chunks, embeddings=embeddings, metadata=chunk_metadata
                    )
                    print(
                        f"   📊 Used batch ingestion with title injection ({len(chunks)} chunks)"
                    )

                else:
                    # Fallback to single vector store ingestion with title injection
                    # Import required functions
                    import sys
                    from pathlib import Path

                    sys.path.append(str(Path(__file__).parent.parent.parent / "bot"))
                    from services.embedding_service import chunk_text
                    from services.title_injection_service import TitleInjectionService

                    # Initialize title injection service
                    title_injection = TitleInjectionService()

                    # Chunk the content and generate embeddings
                    chunks = chunk_text(
                        content,
                        chunk_size=self.embedding_service.settings.chunk_size,
                        chunk_overlap=self.embedding_service.settings.chunk_overlap,
                    )

                    # Add contextual descriptions if enabled
                    if (
                        self.enable_contextual_retrieval
                        and self.contextual_retrieval_service
                    ):
                        print(
                            f"Adding contextual descriptions to {len(chunks)} chunks..."
                        )
                        chunks = await self.contextual_retrieval_service.add_context_to_chunks(
                            chunks,
                            {
                                "file_name": file_info["name"],
                                "full_path": file_info.get(
                                    "full_path", file_info["name"]
                                ),
                                "mimeType": file_info["mimeType"],
                                "createdTime": file_info.get("createdTime"),
                                "owners": file_info.get("owners", []),
                            },
                        )

                    # Apply title injection to chunks for better semantic search
                    chunk_metadata = []
                    for i, chunk in enumerate(chunks):
                        chunk_meta = doc_metadata.copy()
                        chunk_meta["chunk_id"] = f"{file_info['id']}_chunk_{i}"
                        chunk_meta["chunk_index"] = i
                        chunk_meta["total_chunks"] = len(chunks)
                        chunk_metadata.append(chunk_meta)

                    # Inject titles into chunk text for better embedding semantic understanding
                    enhanced_chunks = title_injection.inject_titles(
                        chunks, chunk_metadata
                    )

                    # Generate embeddings for enhanced chunks (with title injection)
                    embeddings = await self.embedding_service.get_embeddings(
                        enhanced_chunks
                    )

                    # Add documents to vector store
                    await self.vector_service.add_documents(
                        texts=enhanced_chunks,  # Use enhanced chunks with title injection
                        embeddings=embeddings,
                        metadata=chunk_metadata,
                    )
                    print(
                        f"   📊 Used single vector store ingestion with title injection ({len(enhanced_chunks)} chunks)"
                    )

                print(f"✅ Successfully ingested: {file_info['name']}")
                success_count += 1

            except Exception as e:
                print(f"❌ Error processing {file_info.get('name', 'unknown')}: {e}")
                error_count += 1

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
