"""
Title Injection Service for Enhanced RAG

Implements the expert's recommendation to inject titles into chunk text
at embed time for better semantic understanding.

Pattern: "[FILENAME] <title> [/FILENAME]\n<content>"
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class TitleInjectionService:
    """
    Service to enhance document chunks with title information
    for improved semantic search performance
    """

    def __init__(  # nosec B107
        self,
        title_start_token: str = "[FILENAME]",
        title_end_token: str = "[/FILENAME]",
        separator: str = "\n",
    ):
        self.title_start_token = title_start_token
        self.title_end_token = title_end_token
        self.separator = separator

    def inject_titles(
        self, texts: list[str], metadata: list[dict[str, Any]]
    ) -> list[str]:
        """
        Inject titles into text chunks for better embeddings

        Args:
            texts: List of document chunks
            metadata: List of metadata dicts, each may contain 'title' key

        Returns:
            List of enhanced texts with title injection
        """
        enhanced_texts = []

        for i, (text, meta) in enumerate(zip(texts, metadata, strict=False)):
            title = self._extract_title(meta)

            if title:
                enhanced_text = self._create_enhanced_text(title, text)
                logger.debug(f"Enhanced chunk {i} with title: {title[:50]}...")
            else:
                enhanced_text = text
                logger.debug(f"No title found for chunk {i}, using original text")

            enhanced_texts.append(enhanced_text)

        logger.info(f"Enhanced {len(enhanced_texts)} chunks with title injection")
        return enhanced_texts

    def _extract_title(self, metadata: dict[str, Any]) -> str | None:
        """Extract title from metadata using various possible keys"""
        possible_title_keys = [
            "title",
            "document_title",
            "file_name",
            "filename",
            "name",
            "doc_title",
            "heading",
            "header",
        ]

        for key in possible_title_keys:
            if key in metadata and metadata[key]:
                title = str(metadata[key]).strip()
                if title:
                    # If this is a filename (contains extension), clean it up
                    if key in ["file_name", "filename", "name"] and self._is_filename(
                        title
                    ):
                        return self._extract_title_from_filename(title)
                    return title

        return None

    def _is_filename(self, text: str) -> bool:
        """Check if text appears to be a filename (contains file extension)"""
        common_extensions = [
            ".pdf",
            ".doc",
            ".docx",
            ".txt",
            ".md",
            ".rtf",
            ".ppt",
            ".pptx",
            ".xls",
            ".xlsx",
            ".csv",
            ".html",
            ".htm",
            ".xml",
            ".json",
        ]
        text_lower = text.lower()
        return any(text_lower.endswith(ext) for ext in common_extensions)

    def _extract_title_from_filename(self, filename: str) -> str:
        """Extract a clean, readable title from a filename"""
        # Remove file extension
        title = filename
        for ext in [
            ".pdf",
            ".doc",
            ".docx",
            ".txt",
            ".md",
            ".rtf",
            ".ppt",
            ".pptx",
            ".xls",
            ".xlsx",
            ".csv",
            ".html",
            ".htm",
            ".xml",
            ".json",
        ]:
            if title.lower().endswith(ext.lower()):
                title = title[: -len(ext)]
                break

        # Clean up common patterns
        title = self._clean_filename_patterns(title)

        # If still looks like a filename or is empty or starts with dot, return original
        if not title or len(title.strip()) < 3 or title.strip().startswith("."):
            return filename

        return title.strip()

    def _clean_filename_patterns(self, title: str) -> str:
        """Clean common filename patterns to create readable titles"""

        # Keep the full filename - don't remove company prefixes
        # Just clean up formatting while preserving full content

        # Replace underscores with spaces
        title = re.sub(r"[_]+", " ", title)

        # Replace remaining hyphens with spaces (for word separation, not compound words)
        title = re.sub(r"-", " ", title)

        # Replace multiple spaces with single space
        title = re.sub(r"\s+", " ", title)

        # Capitalize first letter of each word for readability
        title = title.title()

        # Fix common acronyms and abbreviations
        acronym_fixes = {
            "Ai": "AI",
            "Api": "API",
            "Ui": "UI",
            "Ux": "UX",
            "Ml": "ML",
            "Ios": "iOS",
            "Css": "CSS",
            "Html": "HTML",
            "Json": "JSON",
            "Pdf": "PDF",
            "Csv": "CSV",
            "Xml": "XML",
            "Sql": "SQL",
        }

        for wrong, correct in acronym_fixes.items():
            title = re.sub(r"\b" + wrong + r"\b", correct, title)

        return title

    def _create_enhanced_text(self, title: str, content: str) -> str:
        """Create enhanced text with title injection"""
        return (
            f"{self.title_start_token} {title} {self.title_end_token}"
            f"{self.separator}{content}"
        )

    def extract_title_from_enhanced_text(self, enhanced_text: str) -> str | None:
        """Extract title from enhanced text (for debugging/analysis)"""
        try:
            start_idx = enhanced_text.find(self.title_start_token)
            if start_idx == -1:
                return None

            start_idx += len(self.title_start_token)
            end_idx = enhanced_text.find(self.title_end_token, start_idx)

            if end_idx == -1:
                return None

            return enhanced_text[start_idx:end_idx].strip()
        except Exception as e:
            logger.warning(f"Failed to extract title from enhanced text: {e}")
            return None

    def remove_title_injection(self, enhanced_text: str) -> str:
        """Remove title injection to get original content"""
        try:
            title_section_end = enhanced_text.find(self.title_end_token)
            if title_section_end == -1:
                return enhanced_text

            title_section_end += len(self.title_end_token)
            separator_end = title_section_end + len(self.separator)

            if len(enhanced_text) > separator_end:
                return enhanced_text[separator_end:]
            else:
                return enhanced_text
        except Exception as e:
            logger.warning(f"Failed to remove title injection: {e}")
            return enhanced_text


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
