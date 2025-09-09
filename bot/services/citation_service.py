"""
Citation Service

Handles formatting and adding source citations to RAG responses.
Provides clean separation of citation logic from core RAG functionality.
"""

import re
from typing import Any


class CitationService:
    """Service for adding source citations to generated responses"""

    def add_source_citations(
        self, response: str, context_chunks: list[dict[str, Any]]
    ) -> str:
        """
        Add source citations to a response based on retrieved context chunks.

        Args:
            response: The generated response text
            context_chunks: List of context chunks with metadata

        Returns:
            Response with source citations appended
        """
        if not context_chunks:
            return response

        # Parse which sources the LLM actually used
        used_sources = self._parse_used_sources(response)
        if not used_sources:
            # Remove the SOURCES_USED line and return clean response
            return self._clean_response(response)

        # Filter context chunks to only include used sources
        relevant_chunks = [
            chunk
            for chunk in context_chunks
            if any(
                used_source.lower()
                in chunk.get("metadata", {}).get("file_name", "").lower()
                for used_source in used_sources
            )
        ]

        if not relevant_chunks:
            return self._clean_response(response)

        # Extract sources with enhanced deduplication logic
        sources = []
        file_chunk_counts = {}  # Track chunks per file

        # First pass: count chunks per file
        for chunk in relevant_chunks:
            metadata = chunk.get("metadata", {})
            file_name = metadata.get("file_name", "Unknown")
            file_chunk_counts[file_name] = file_chunk_counts.get(file_name, 0) + 1

        # Second pass: build citations with chunk info when needed
        seen_sources = set()
        for i, chunk in enumerate(relevant_chunks, 1):
            metadata = chunk.get("metadata", {})
            file_name = metadata.get("file_name", f"Document {i}")
            similarity = chunk.get("similarity", 0)

            # Create unique identifier for deduplication
            source_key = file_name.lower()
            if source_key in seen_sources:
                continue
            seen_sources.add(source_key)

            # Build citation with improved formatting
            # Extract document title from file_name (remove file extension)
            doc_title = (
                file_name.replace(".pdf", "").replace(".docx", "").replace(".txt", "")
            )

            # Format: Title • Subtitle (if available) (:file_folder: Knowledge Base) • Relevance: XX.X%
            citation = f"{len(sources) + 1}. {doc_title}"

            # Add chunk count if multiple chunks from same file
            chunk_count = file_chunk_counts.get(file_name, 1)
            if chunk_count > 1:
                citation += f" • {chunk_count} sections"

            # Add subtitle/description if available in metadata
            subtitle = metadata.get("title") or metadata.get("description")
            if subtitle and subtitle != doc_title:
                citation += f" • {subtitle}"

            # Add folder indication
            citation += " (:file_folder: Knowledge Base)"

            # Add relevance score
            citation += f" • Relevance: {similarity:.1%}"

            # Add web view link if available (Google Drive)
            web_view_link = metadata.get("web_view_link")
            if web_view_link:
                citation = f"[{citation}]({web_view_link})"

            sources.append(citation)

        # Clean the response and append sources section if we have any
        clean_response = self._clean_response(response)
        if sources:
            citations_section = "\n\n**📚 Sources:**\n" + "\n".join(sources)
            return clean_response + citations_section

        return clean_response

    def format_context_for_llm(self, context_chunks: list[dict[str, Any]]) -> str:
        """
        Format context chunks for inclusion in LLM prompt.

        Args:
            context_chunks: List of retrieved context chunks

        Returns:
            Formatted context string for LLM consumption
        """
        if not context_chunks:
            return ""

        context_texts = []
        for chunk in context_chunks:
            content = chunk["content"]
            similarity = chunk.get("similarity", 0)

            # Include metadata if available
            metadata = chunk.get("metadata", {})
            if metadata:
                source_doc = metadata.get("file_name", "Unknown")
                context_texts.append(
                    f"[Source: {source_doc}, Score: {similarity:.2f}]\n{content}"
                )
            else:
                context_texts.append(f"[Score: {similarity:.2f}]\n{content}")

        return "\n\n".join(context_texts)

    def _parse_used_sources(self, response: str) -> list[str]:
        """
        Parse the SOURCES_USED line from the LLM response.

        Args:
            response: The LLM response text

        Returns:
            List of source names the LLM indicated it used
        """
        # Look for SOURCES_USED: line
        match = re.search(r"SOURCES_USED:\s*(.+)", response, re.IGNORECASE)
        if not match:
            return []

        sources_text = match.group(1).strip()
        if sources_text.lower() in ["none", "null", "n/a", ""]:
            return []

        # Split by comma and clean up
        sources = [s.strip() for s in sources_text.split(",")]
        return [s for s in sources if s]

    def _clean_response(self, response: str) -> str:
        """
        Remove the SOURCES_USED line from the response.

        Args:
            response: The LLM response text

        Returns:
            Response with SOURCES_USED line removed
        """
        # Remove SOURCES_USED line
        cleaned = re.sub(
            r"\n*SOURCES_USED:.*$", "", response, flags=re.IGNORECASE | re.MULTILINE
        )
        return cleaned.strip()
