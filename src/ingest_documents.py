#!/usr/bin/env python3
"""
Document ingestion CLI for the RAG system

Usage:
    python ingest_documents.py --help
    python ingest_documents.py --file path/to/document.txt
    python ingest_documents.py --directory path/to/docs/
    python ingest_documents.py --url https://example.com/doc.md
    python ingest_documents.py --json data.json --content-field text
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiohttp

# Add the src directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from config.settings import Settings
from services.rag_service import DocumentProcessor, RAGService

logger = logging.getLogger(__name__)


async def ingest_file(
    rag_service: RAGService, file_path: str, metadata: dict[str, Any] = None
) -> int:
    """Ingest a single file"""
    try:
        path = Path(file_path)

        if not path.exists():
            print(f"❌ File not found: {file_path}")
            return 0

        print(f"📄 Processing file: {file_path}")

        # Determine file type and process accordingly
        suffix = path.suffix.lower()

        if suffix in [".txt", ".md", ".rst"]:
            if suffix == ".md":
                doc = DocumentProcessor.process_markdown_file(str(path), metadata)
            else:
                doc = DocumentProcessor.process_text_file(str(path), metadata)

            chunks = await rag_service.ingest_documents([doc])
            print(f"✅ Ingested {chunks} chunks from {file_path}")
            return chunks

        elif suffix == ".json":
            docs = DocumentProcessor.process_json_file(str(path), "content", metadata)
            chunks = await rag_service.ingest_documents(docs)
            print(
                f"✅ Ingested {chunks} chunks from {len(docs)} documents in {file_path}"
            )
            return chunks

        else:
            print(f"⚠️  Unsupported file type: {suffix}")
            return 0

    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")
        return 0


async def ingest_directory(
    rag_service: RAGService, directory: str, metadata: dict[str, Any] = None
) -> int:
    """Ingest all supported files in a directory"""
    try:
        path = Path(directory)

        if not path.exists() or not path.is_dir():
            print(f"❌ Directory not found: {directory}")
            return 0

        print(f"📁 Processing directory: {directory}")

        supported_extensions = {".txt", ".md", ".rst", ".json"}
        files = []

        # Find all supported files
        for ext in supported_extensions:
            files.extend(path.rglob(f"*{ext}"))

        if not files:
            print(f"⚠️  No supported files found in {directory}")
            return 0

        print(f"Found {len(files)} files to process")

        total_chunks = 0
        for file_path in files:
            chunks = await ingest_file(rag_service, str(file_path), metadata)
            total_chunks += chunks

        print(f"✅ Total ingested: {total_chunks} chunks from {len(files)} files")
        return total_chunks

    except Exception as e:
        print(f"❌ Error processing directory {directory}: {e}")
        return 0


async def ingest_url(
    rag_service: RAGService, url: str, metadata: dict[str, Any] = None
) -> int:
    """Ingest a document from a URL"""
    try:
        print(f"🌐 Fetching URL: {url}")

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    print(f"❌ Failed to fetch {url}: HTTP {response.status}")
                    return 0

                content = await response.text()

                # Create document
                parsed_url = urlparse(url)
                doc_metadata = metadata or {}
                doc_metadata.update(
                    {
                        "source_url": url,
                        "domain": parsed_url.netloc,
                        "path": parsed_url.path,
                        "content_type": response.headers.get("content-type", ""),
                    }
                )

                doc = {"content": content, "metadata": doc_metadata, "id": url}

                chunks = await rag_service.ingest_documents([doc])
                print(f"✅ Ingested {chunks} chunks from {url}")
                return chunks

    except Exception as e:
        print(f"❌ Error fetching {url}: {e}")
        return 0


async def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(description="Ingest documents into the RAG system")
    parser.add_argument("--file", "-f", help="Path to a single file to ingest")
    parser.add_argument(
        "--directory", "-d", help="Path to directory containing documents"
    )
    parser.add_argument("--url", "-u", help="URL to fetch and ingest")
    parser.add_argument("--json", "-j", help="Path to JSON file with documents")
    parser.add_argument(
        "--content-field",
        default="content",
        help="Field name for content in JSON documents",
    )
    parser.add_argument("--metadata", "-m", help="JSON string with additional metadata")
    parser.add_argument(
        "--batch-size", "-b", type=int, default=50, help="Batch size for processing"
    )
    parser.add_argument(
        "--status", "-s", action="store_true", help="Show system status"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    # Configure logging
    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    # Parse metadata if provided
    metadata = None
    if args.metadata:
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid metadata JSON: {e}")
            return 1

    try:
        # Initialize settings and RAG service
        print("🚀 Initializing RAG system...")
        settings = Settings()

        if not settings.vector.enabled:
            print("❌ Vector storage is disabled. Enable it in your .env file:")
            print("VECTOR_ENABLED=true")
            return 1

        rag_service = RAGService(settings)
        await rag_service.initialize()

        # Show status if requested
        if args.status:
            status = await rag_service.get_system_status()
            print("\n📊 System Status:")
            for key, value in status.items():
                print(f"  {key}: {value}")
            print()

        total_chunks = 0

        # Process based on arguments
        if args.file:
            total_chunks = await ingest_file(rag_service, args.file, metadata)

        elif args.directory:
            total_chunks = await ingest_directory(rag_service, args.directory, metadata)

        elif args.url:
            total_chunks = await ingest_url(rag_service, args.url, metadata)

        elif args.json:
            if args.content_field:
                docs = DocumentProcessor.process_json_file(
                    args.json, args.content_field, metadata
                )
                total_chunks = await rag_service.ingest_documents(docs)
                print(
                    f"✅ Ingested {total_chunks} chunks from {len(docs)} JSON documents"
                )
            else:
                print("❌ --content-field required for JSON ingestion")
                return 1

        else:
            parser.print_help()
            return 1

        if total_chunks > 0:
            print(f"\n🎉 Successfully ingested {total_chunks} total chunks!")
        else:
            print("\n⚠️  No chunks were ingested.")

        # Clean up
        await rag_service.close()

        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
