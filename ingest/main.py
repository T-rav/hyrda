#!/usr/bin/env python3
"""
Google Drive Document Ingester - THE ONLY SUPPORTED INGESTION METHOD

This is the sole document ingestion system for the RAG pipeline.
It authenticates with Google Drive, scans folders, and upserts documents
with comprehensive metadata including file paths and permissions.

Refactored into modular services for better maintainability:
- DocumentProcessor: Text extraction from various formats
- GoogleDriveClient: Google Drive API operations
- IngestionOrchestrator: Main workflow coordination
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Load .env file from current directory or parent directories
from dotenv import load_dotenv


def find_and_load_env():
    """Find and load .env file from current directory or parent directories"""
    current_path = Path.cwd()
    for path in [current_path] + list(current_path.parents):
        env_file = path / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            print(f"📄 Loaded environment from: {env_file}")
            return True
    print("⚠️  No .env file found in current directory or parent directories")
    return False


# Load environment variables
find_and_load_env()

# Import local ingestion orchestrator (no bot dependencies)
from services import IngestionOrchestrator


async def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Ingest documents from Google Drive")

    # Either folder-id OR file-id is required (mutually exclusive)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--folder-id", help="Google Drive folder ID to ingest recursively")
    group.add_argument("--file-id", help="Google Drive file ID to ingest (single file)")

    parser.add_argument(
        "--credentials", help="Path to Google OAuth2 credentials JSON file"
    )
    parser.add_argument("--token", help="Path to store OAuth2 token")
    parser.add_argument(
        "--recursive",
        action="store_true",
        default=True,
        help="Include subfolders (default: True, only applies to --folder-id)",
    )
    parser.add_argument("--metadata", help="Additional metadata as JSON string")
    parser.add_argument(
        "--reauth",
        action="store_true",
        help="Force re-authentication (useful for shared drive access)",
    )

    args = parser.parse_args()

    # Parse metadata if provided
    metadata = None
    if args.metadata:
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError as e:
            print(f"Error parsing metadata JSON: {e}")
            sys.exit(1)

    # Handle re-authentication if requested
    if args.reauth:
        token_file = args.token or "auth/token.json"
        if os.path.exists(token_file):
            print(f"🔄 Removing existing token file: {token_file}")
            os.remove(token_file)

    # Initialize database connection for document tracking
    # This must happen before creating orchestrator to avoid import conflicts
    database_url = os.getenv(
        "DATA_DATABASE_URL",
        "mysql+pymysql://insightmesh_data:insightmesh_data_password@localhost:3306/insightmesh_data",
    )

    # Import and initialize database
    tasks_path = str(Path(__file__).parent.parent / "tasks")
    if tasks_path not in sys.path:
        sys.path.append(tasks_path)

    from models.base import init_db

    init_db(database_url)
    print("✅ Database connection initialized")

    # Initialize orchestrator
    orchestrator = IngestionOrchestrator(args.credentials, args.token)

    # Authenticate
    print("Authenticating with Google Drive...")
    if not orchestrator.authenticate():
        print("❌ Authentication failed")
        sys.exit(1)

    print("✅ Authentication successful")

    # Initialize services
    print("Initializing vector database and embedding service...")
    try:
        # Use local config and minimal services (no bot dependencies)
        from ingest_config import EmbeddingConfig, LLMConfig, RAGConfig, VectorConfig
        from services.embedding_provider import OpenAIEmbeddingProvider
        from services.llm_wrapper import SimpleLLMService
        from services.vector_store import QdrantVectorStore

        vector_config = VectorConfig.from_env()
        embedding_config = EmbeddingConfig.from_env()
        llm_config = LLMConfig.from_env()
        rag_config = RAGConfig.from_env()

        # Initialize minimal embedding provider FIRST (need dimension for vector store)
        embedding_provider = OpenAIEmbeddingProvider(
            api_key=embedding_config.api_key,
            model=embedding_config.model,
        )

        # Initialize minimal vector store with correct dimension
        vector_store = QdrantVectorStore(
            host=vector_config.host,
            port=vector_config.port,
            collection_name=vector_config.collection_name,
            api_key=vector_config.api_key,
            use_https=vector_config.use_https,
        )
        print(
            f"🔗 Connecting to Qdrant at {'https' if vector_config.use_https else 'http'}://{vector_config.host}:{vector_config.port}"
        )
        print(
            f"📐 Using {embedding_config.model} with dimension: {embedding_provider.get_dimension()}"
        )
        await vector_store.initialize(
            embedding_dimension=embedding_provider.get_dimension()
        )

        # Initialize minimal LLM service for contextual retrieval if enabled
        llm_service = None
        if rag_config.enable_contextual_retrieval and llm_config.api_key:
            llm_service = SimpleLLMService(
                api_key=llm_config.api_key,
                model=llm_config.model,
            )
            print(
                "✅ Contextual retrieval enabled - chunks will be enhanced with context"
            )

        # Set services in orchestrator
        orchestrator.set_services(
            vector_store,
            embedding_provider,
            llm_service=llm_service,
            enable_contextual_retrieval=llm_service is not None,
        )

        print("✅ Vector services initialized successfully")
    except Exception as e:
        print(f"❌ Service initialization failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # Ingest folder or single file
    try:
        if args.folder_id:
            print(f"\n📂 Ingesting folder: {args.folder_id}")
            success_count, error_count = await orchestrator.ingest_folder(
                args.folder_id, recursive=args.recursive, metadata=metadata
            )
        else:  # args.file_id
            print(f"\n📄 Ingesting single file: {args.file_id}")
            # Get file info from Google Drive
            file_info = orchestrator.drive_client.api_service.service.files().get(
                fileId=args.file_id,
                fields="id, name, mimeType, size, webViewLink, parents, owners, permissions, createdTime, modifiedTime"
            ).execute()

            # Add folder path context
            file_info["folder_path"] = "/"  # Root level for single file
            file_info["folder_id"] = file_info.get("parents", [""])[0] if file_info.get("parents") else ""

            # Ingest as single-item list
            files = [file_info]
            results = await orchestrator.ingest_files(files, base_metadata=metadata)
            success_count = sum(1 for r in results if r["success"])
            error_count = len(results) - success_count

        print("\n📊 Ingestion Summary:")
        print(f"✅ Successfully processed: {success_count}")
        print(f"❌ Errors: {error_count}")
        print(f"📊 Total items: {success_count + error_count}")

    except Exception as e:
        print(f"❌ Ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
