"""
Document Processor Service

Handles processing and preparation of documents before ingestion.
Supports various file formats and text extraction methods.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Helper service for processing documents before ingestion"""

    def process_text_file(
        self, content: str, metadata: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Process plain text files into chunks.

        Args:
            content: Raw text content
            metadata: Optional metadata to include

        Returns:
            List of processed document chunks
        """
        if not content.strip():
            return []

        # Simple chunking by paragraphs for text files
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]

        if not paragraphs:
            # Fallback: treat entire content as single chunk
            paragraphs = [content.strip()]

        chunks = []
        base_metadata = metadata or {}

        for i, paragraph in enumerate(paragraphs):
            if len(paragraph) > 50:  # Only include substantial chunks
                chunk_metadata = base_metadata.copy()
                chunk_metadata.update(
                    {
                        "chunk_id": i,
                        "content_type": "text",
                        "chunk_size": len(paragraph),
                    }
                )

                chunks.append({"content": paragraph, "metadata": chunk_metadata})

        logger.debug(f"📄 Processed text file into {len(chunks)} chunks")
        return chunks

    def process_markdown_file(
        self, content: str, metadata: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Process Markdown files with section-aware chunking.

        Args:
            content: Raw markdown content
            metadata: Optional metadata to include

        Returns:
            List of processed document chunks
        """
        if not content.strip():
            return []

        chunks = []
        base_metadata = metadata or {}

        # Split by headers (basic approach)
        sections = []
        current_section = []
        current_header = None

        for line in content.split("\n"):
            stripped_line = line.strip()
            if stripped_line.startswith("#"):
                # New header found
                if current_section:
                    sections.append(
                        {
                            "header": current_header,
                            "content": "\n".join(current_section),
                        }
                    )
                current_header = stripped_line
                current_section = [stripped_line]
            else:
                current_section.append(stripped_line)

        # Don't forget the last section
        if current_section:
            sections.append(
                {"header": current_header, "content": "\n".join(current_section)}
            )

        # Convert sections to chunks
        for i, section in enumerate(sections):
            if len(section["content"]) > 100:  # Only substantial sections
                chunk_metadata = base_metadata.copy()
                chunk_metadata.update(
                    {
                        "chunk_id": i,
                        "content_type": "markdown",
                        "section_header": section.get("header"),
                        "chunk_size": len(section["content"]),
                    }
                )

                chunks.append(
                    {"content": section["content"], "metadata": chunk_metadata}
                )

        logger.debug(f"📝 Processed markdown file into {len(chunks)} sections")
        return chunks

    def process_json_file(
        self, content: str, metadata: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Process JSON files by extracting meaningful text content.

        Args:
            content: Raw JSON content
            metadata: Optional metadata to include

        Returns:
            List of processed document chunks
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON content: {e}")
            return []

        chunks = []
        base_metadata = metadata or {}

        def extract_text_from_json(obj: Any, path: str = "") -> list[str]:
            """Recursively extract text values from JSON"""
            texts = []

            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    if isinstance(value, str) and len(value.strip()) > 20:
                        texts.append(f"{key}: {value}")
                    else:
                        texts.extend(extract_text_from_json(value, current_path))
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    current_path = f"{path}[{i}]" if path else f"[{i}]"
                    texts.extend(extract_text_from_json(item, current_path))
            elif isinstance(obj, str) and len(obj.strip()) > 20:
                texts.append(obj)

            return texts

        text_chunks = extract_text_from_json(data)

        # Combine small chunks and create document chunks
        combined_chunks = []
        current_chunk = []
        current_size = 0
        max_chunk_size = 1000  # characters

        for text in text_chunks:
            if current_size + len(text) > max_chunk_size and current_chunk:
                # Save current chunk and start new one
                combined_chunks.append("\n".join(current_chunk))
                current_chunk = [text]
                current_size = len(text)
            else:
                current_chunk.append(text)
                current_size += len(text)

        # Don't forget the last chunk
        if current_chunk:
            combined_chunks.append("\n".join(current_chunk))

        # Convert to final format
        for i, chunk_content in enumerate(combined_chunks):
            chunk_metadata = base_metadata.copy()
            chunk_metadata.update(
                {
                    "chunk_id": i,
                    "content_type": "json",
                    "chunk_size": len(chunk_content),
                }
            )

            chunks.append({"content": chunk_content, "metadata": chunk_metadata})

        logger.debug(f"📊 Processed JSON file into {len(chunks)} chunks")
        return chunks

    def process_generic_document(
        self, content: str, file_type: str, metadata: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Process any document type with generic chunking strategy.

        Args:
            content: Document content
            file_type: Type/extension of the file
            metadata: Optional metadata to include

        Returns:
            List of processed document chunks
        """
        if not content.strip():
            return []

        # Determine processing strategy based on file type
        if file_type.lower() in ["md", "markdown"]:
            return self.process_markdown_file(content, metadata)
        elif file_type.lower() == "json":
            return self.process_json_file(content, metadata)
        else:
            return self.process_text_file(content, metadata)

    def validate_document_content(self, content: str) -> dict[str, Any]:
        """
        Validate document content quality and characteristics.

        Args:
            content: Document content to validate

        Returns:
            Validation results and metrics
        """
        if not content:
            return {
                "valid": False,
                "issues": ["Content is empty"],
                "metrics": {"length": 0, "lines": 0, "words": 0},
            }

        issues = []
        metrics = {
            "length": len(content),
            "lines": len(content.split("\n")),
            "words": len(content.split()),
            "paragraphs": len([p for p in content.split("\n\n") if p.strip()]),
        }

        # Check for potential issues
        if metrics["length"] < 50:
            issues.append("Content is very short")

        if metrics["words"] < 10:
            issues.append("Very few words detected")

        # Check for mostly non-text content
        non_text_chars = sum(
            1 for c in content if not c.isprintable() and c not in "\n\r\t"
        )
        if non_text_chars > metrics["length"] * 0.1:
            issues.append("High ratio of non-printable characters")

        return {"valid": len(issues) == 0, "issues": issues, "metrics": metrics}
