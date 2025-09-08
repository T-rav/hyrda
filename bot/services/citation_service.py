"""
Citation Service

Handles formatting and adding source citations to RAG responses.
Provides clean separation of citation logic from core RAG functionality.
"""

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

        # Extract unique sources with their metadata
        sources = []
        seen_sources = set()

        for i, chunk in enumerate(context_chunks, 1):
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
            doc_title = file_name.replace('.pdf', '').replace('.docx', '').replace('.txt', '')
            
            # Format: Title • Subtitle (if available) (:file_folder: Knowledge Base) • Relevance: XX.X%
            citation = f"{len(sources) + 1}. {doc_title}"
            
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

        # Append sources section if we have any
        if sources:
            citations_section = "\n\n**📚 Sources:**\n" + "\n".join(sources)
            return response + citations_section

        return response

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
