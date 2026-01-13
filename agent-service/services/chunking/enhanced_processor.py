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
