"""
Citation Service

Handles formatting and adding source citations to RAG responses.
Provides clean separation of citation logic from core RAG functionality.
"""

from rag_types import ContextChunk


class CitationService:
    """Service for adding source citations to generated responses"""

    def add_source_citations(self, response: str, context_chunks: list[ContextChunk]) -> str:
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

        citation_chunks = self._filter_citation_chunks(context_chunks)
        if not citation_chunks:
            return response

        file_chunk_counts = self._count_chunks_per_file(citation_chunks)
        sources = self._build_citation_list(citation_chunks, file_chunk_counts)

        if sources:
            citations_section = "\n\n**📚 Sources:**\n" + "\n".join(sources)
            return response + citations_section

        return response

    def _filter_citation_chunks(self, context_chunks: list[ContextChunk]) -> list[ContextChunk]:
        """Filter out uploaded documents from citations."""
        return [
            chunk
            for chunk in context_chunks
            if chunk.get("metadata", {}).get("source") != "uploaded_document"
        ]

    def _count_chunks_per_file(self, chunks: list[ContextChunk]) -> dict[str, int]:
        """Count how many chunks come from each file."""
        counts = {}
        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            file_name = metadata.get("file_name", "Unknown")
            counts[file_name] = counts.get(file_name, 0) + 1
        return counts

    def _build_citation_list(
        self, chunks: list[ContextChunk], file_chunk_counts: dict[str, int]
    ) -> list[str]:
        """Build list of formatted citations."""
        sources = []
        seen_sources = set()

        for i, chunk in enumerate(chunks, 1):
            metadata = chunk.get("metadata", {})
            source_type = metadata.get("source", "google_drive")

            file_name, data_type = self._extract_file_info(metadata, source_type, i)
            source_key = file_name.lower()

            if source_key in seen_sources:
                continue
            seen_sources.add(source_key)

            citation = self._format_single_citation(
                chunk,
                file_name,
                data_type,
                source_type,
                file_chunk_counts,
                len(sources),
            )
            sources.append(citation)

        return sources

    def _extract_file_info(self, metadata: dict, source_type: str, index: int) -> tuple[str, str]:
        """Extract file name and data type from metadata."""
        if source_type == "metric":
            file_name = metadata.get("name", f"Metric Record {index}")
            data_type = metadata.get("data_type", "record")
        else:
            file_name = metadata.get("file_name", f"Document {index}")
            data_type = "document"
        return file_name, data_type

    def _format_single_citation(
        self,
        chunk: ContextChunk,
        file_name: str,
        data_type: str,
        source_type: str,
        file_chunk_counts: dict[str, int],
        citation_number: int,
    ) -> str:
        """Format a single citation with all metadata."""
        metadata = chunk.get("metadata", {})
        similarity = chunk.get("similarity", 0)

        # Build base citation
        doc_title = self._get_document_title(file_name, source_type)
        citation = f"{citation_number + 1}. {doc_title}"

        # Add chunk count if multiple chunks
        chunk_count = file_chunk_counts.get(file_name, 1)
        if chunk_count > 1:
            citation += f" • {chunk_count} sections"

        # Add subtitle/context
        citation += self._add_citation_context(metadata, source_type, data_type, doc_title)

        # Add source indicator and similarity
        citation += self._format_source_indicator(source_type)
        citation += f" • Match: {similarity:.1%}"

        # Add link if available
        if source_type != "metric":
            web_view_link = metadata.get("web_view_link")
            if web_view_link:
                citation = f"[{citation}]({web_view_link})"

        return citation

    def _get_document_title(self, file_name: str, source_type: str) -> str:
        """Extract document title from file name."""
        if source_type == "metric":
            return file_name
        return file_name.replace(".pdf", "").replace(".docx", "").replace(".txt", "")

    def _add_citation_context(
        self, metadata: dict, source_type: str, data_type: str, doc_title: str
    ) -> str:
        """Add contextual information to citation."""
        if source_type == "metric":
            if data_type == "employee" and metadata.get("role"):
                return f" • {metadata.get('role')}"
            elif data_type == "project" and metadata.get("client"):
                return f" • {metadata.get('client')}"
        else:
            subtitle = metadata.get("title") or metadata.get("description")
            if subtitle and subtitle != doc_title:
                return f" • {subtitle}"
        return ""

    def _format_source_indicator(self, source_type: str) -> str:
        """Format the source type indicator."""
        if source_type == "metric":
            return " (📊 Metric.ai)"
        return " (:file_folder: Knowledge Base)"

    def format_context_for_llm(self, context_chunks: list[ContextChunk]) -> str:
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
                context_texts.append(f"[Source: {source_doc}, Score: {similarity:.2f}]\n{content}")
            else:
                context_texts.append(f"[Score: {similarity:.2f}]\n{content}")

        return "\n\n".join(context_texts)
