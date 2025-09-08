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

# Local imports (assuming we'll use the existing ingestion logic)
sys.path.append(str(Path(__file__).parent.parent / "bot"))

from services import IngestionOrchestrator


async def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Ingest documents from Google Drive")
    parser.add_argument("--folder-id", required=True, help="Google Drive folder ID")
    parser.add_argument("--credentials", help="Path to Google OAuth2 credentials JSON file")
    parser.add_argument("--token", help="Path to store OAuth2 token")
    parser.add_argument("--recursive", action="store_true", default=True,
                       help="Include subfolders (default: True)")
    parser.add_argument("--metadata", help="Additional metadata as JSON string")
    parser.add_argument("--reauth", action="store_true",
                       help="Force re-authentication (useful for shared drive access)")

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
        token_file = args.token or 'token.json'
        if os.path.exists(token_file):
            print(f"🔄 Removing existing token file: {token_file}")
            os.remove(token_file)

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
        from config.settings import VectorSettings, EmbeddingSettings, LLMSettings, HybridSettings, Settings

        # Try to use full settings first to detect hybrid mode
        try:
            # This will work if minimal .env is configured
            settings = Settings()
            use_hybrid = settings.hybrid.enabled and settings.vector.enabled
            if use_hybrid:
                print("🔄 Hybrid RAG mode detected - using title injection and dual indexing")
        except:
            # Fallback to individual settings if full Settings fails
            use_hybrid = False
            print("🔄 Single vector mode - using basic ingestion")

        if use_hybrid:
            # Use hybrid RAG service with title injection
            from services.hybrid_rag_service import create_hybrid_rag_service
            hybrid_service = await create_hybrid_rag_service(settings)

            # Set hybrid service in orchestrator (no separate embedding service needed)
            orchestrator.set_services(hybrid_service)

        else:
            # Fallback to single vector store
            vector_settings = VectorSettings()
            embedding_settings = EmbeddingSettings()
            llm_settings = LLMSettings()

            # Initialize vector store
            from services.vector_service import create_vector_store
            vector_store = create_vector_store(vector_settings)
            await vector_store.initialize()

            # Initialize embedding service
            from services.embedding_service import create_embedding_provider
            embedding_provider = create_embedding_provider(embedding_settings, llm_settings)

            # Set services in orchestrator
            orchestrator.set_services(vector_store, embedding_provider)

        if use_hybrid:
            print("✅ Hybrid RAG services initialized successfully (Pinecone + Elasticsearch + Title Injection)")
        else:
            print("✅ Single vector services initialized successfully")
    except Exception as e:
        print(f"❌ Service initialization failed: {e}")
        sys.exit(1)

    # Ingest folder
    try:
        success_count, error_count = await orchestrator.ingest_folder(
            args.folder_id,
            recursive=args.recursive,
            metadata=metadata
        )

        print(f"\n📊 Ingestion Summary:")
        print(f"✅ Successfully processed: {success_count}")
        print(f"❌ Errors: {error_count}")
        print(f"📊 Total items: {success_count + error_count}")

    except Exception as e:
        print(f"❌ Ingestion failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
