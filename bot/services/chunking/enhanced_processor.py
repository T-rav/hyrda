"""
Enhanced chunk processor combining chunking with title injection
"""

import logging
from typing import Any

from services.chunking.title_injection_service import TitleInjectionService

logger = logging.getLogger(__name__)


class EnhancedChunkProcessor:
    """
    Processor that combines chunking with title injection
    for seamless integration with existing pipelines
    """

    def __init__(self, title_injection_service: TitleInjectionService):
        self.title_injection = title_injection_service

    def process_documents_for_embedding(
        self, documents: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Process documents with title injection before embedding

        Args:
            documents: List of dicts with 'content' and 'metadata' keys

        Returns:
            List of processed documents with enhanced content
        """
        processed_docs = []

        for doc in documents:
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})

            # Create enhanced content with title injection
            enhanced_content = self.title_injection.inject_titles(
                [content], [metadata]
            )[0]

            # Create new document with enhanced content
            enhanced_doc = doc.copy()
            enhanced_doc["content"] = enhanced_content
            enhanced_doc["original_content"] = content  # Keep original for reference

            processed_docs.append(enhanced_doc)

        logger.info(f"Processed {len(processed_docs)} documents with title injection")
        return processed_docs

    def prepare_for_dual_indexing(
        self, documents: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Prepare documents for dual indexing (Pinecone + Elasticsearch)

        Returns:
            {
                'dense': documents with enhanced content for embedding,
                'sparse': documents with title field separation for BM25
            }
        """
        dense_docs = []
        sparse_docs = []

        for doc in documents:
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})

            # For dense indexing: use enhanced content
            enhanced_content = self.title_injection.inject_titles(
                [content], [metadata]
            )[0]
            dense_doc = doc.copy()
            dense_doc["content"] = enhanced_content
            dense_docs.append(dense_doc)

            # For sparse indexing: separate title and content fields
            sparse_doc = doc.copy()
            sparse_doc["content"] = content  # Original content
            sparse_doc["title"] = self.title_injection._extract_title(metadata) or ""
            sparse_docs.append(sparse_doc)

        logger.info(f"Prepared {len(dense_docs)} documents for dual indexing")
        return {"dense": dense_docs, "sparse": sparse_docs}
