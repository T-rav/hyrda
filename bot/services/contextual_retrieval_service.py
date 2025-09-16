"""
Contextual Retrieval Service

Implements Anthropic's contextual retrieval technique by generating
contextual descriptions for document chunks before embedding.
"""

import asyncio
import logging
from typing import Any

from .llm_service import LLMService

logger = logging.getLogger(__name__)


class ContextualRetrievalService:
    """Service for generating contextual descriptions of document chunks"""

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    async def add_context_to_chunks(
        self,
        chunks: list[str],
        document_metadata: dict[str, Any],
        batch_size: int = 10,
    ) -> list[str]:
        """
        Add contextual descriptions to document chunks.

        Args:
            chunks: List of text chunks from a document
            document_metadata: Metadata about the source document
            batch_size: Number of chunks to process in parallel

        Returns:
            List of contextualized chunks with prepended context
        """
        if not chunks:
            return []

        logger.info(
            f"Adding context to {len(chunks)} chunks from {document_metadata.get('file_name', 'unknown')}"
        )

        # Process chunks in batches to avoid overwhelming the LLM
        contextualized_chunks = []

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            batch_contexts = await self._process_chunk_batch(batch, document_metadata)
            contextualized_chunks.extend(batch_contexts)

        logger.info(f"Successfully contextualized {len(contextualized_chunks)} chunks")
        return contextualized_chunks

    async def _process_chunk_batch(
        self,
        chunk_batch: list[str],
        document_metadata: dict[str, Any],
    ) -> list[str]:
        """Process a batch of chunks in parallel"""
        tasks = [
            self._generate_chunk_context(chunk, document_metadata)
            for chunk in chunk_batch
        ]

        contexts = await asyncio.gather(*tasks, return_exceptions=True)

        contextualized_chunks = []
        for i, (chunk, context) in enumerate(zip(chunk_batch, contexts, strict=False)):
            if isinstance(context, Exception):
                logger.warning(f"Failed to generate context for chunk {i}: {context}")
                # Fallback to original chunk
                contextualized_chunks.append(chunk)
            else:
                # Prepend context to original chunk
                contextualized_chunk = f"{context} {chunk}" if context else chunk
                contextualized_chunks.append(contextualized_chunk)

        return contextualized_chunks

    async def _generate_chunk_context(
        self,
        chunk: str,
        document_metadata: dict[str, Any],
    ) -> str:
        """Generate contextual description for a single chunk"""
        try:
            # Build document context from metadata
            doc_context = self._build_document_context(document_metadata)

            prompt = f"""Please provide a brief contextual description (50-100 tokens) for the following text chunk. The description should situate the chunk within the broader document context to improve retrieval accuracy.

Document Context: {doc_context}

Text Chunk:
{chunk[:500]}...

Provide only the contextual description without any preamble. The description should be concise and factual, helping to understand what this chunk is about within the document's context."""

            response = await self.llm_service.get_response(prompt)

            # Clean and validate the response
            context = response.strip()
            if len(context) > 200:  # Limit context length
                context = context[:200].rsplit(" ", 1)[0] + "..."

            return context

        except Exception as e:
            logger.error(f"Failed to generate context for chunk: {e}")
            return ""

    def _build_document_context(self, metadata: dict[str, Any]) -> str:
        """Build a concise document context string from metadata"""
        context_parts = []

        # File information
        file_name = metadata.get("file_name", "")
        if file_name:
            context_parts.append(f"File: {file_name}")

        # File path for additional context
        full_path = metadata.get("full_path", "")
        if full_path and full_path != file_name:
            context_parts.append(f"Path: {full_path}")

        # MIME type information
        mime_type = metadata.get("mimeType", "")
        doc_type = self._mime_to_document_type(mime_type)
        if doc_type:
            context_parts.append(f"Type: {doc_type}")

        # Creation/modification dates
        created_time = metadata.get("createdTime", "")
        if created_time:
            # Extract just the date part
            date = created_time.split("T")[0] if "T" in created_time else created_time
            context_parts.append(f"Created: {date}")

        # Owners/authors
        owners = metadata.get("owners", [])
        if owners:
            owner_names = [
                owner.get("displayName", "") for owner in owners[:2]
            ]  # Limit to 2 owners
            if owner_names:
                context_parts.append(f"Authors: {', '.join(filter(None, owner_names))}")

        return (
            "This chunk is from a document with the following context: "
            + "; ".join(context_parts)
            + "."
        )

    def _mime_to_document_type(self, mime_type: str) -> str:
        """Convert MIME type to human-readable document type"""
        mime_map = {
            "application/pdf": "PDF document",
            "application/vnd.google-apps.document": "Google Doc",
            "application/vnd.google-apps.spreadsheet": "Google Sheet",
            "application/vnd.google-apps.presentation": "Google Slides",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Word document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Excel spreadsheet",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": "PowerPoint presentation",
            "text/plain": "text file",
            "text/markdown": "Markdown document",
        }
        return mime_map.get(mime_type, "")
