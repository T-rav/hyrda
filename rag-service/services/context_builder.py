"""
Context Builder Service

Handles building context for LLM prompts from retrieved chunks.
Manages prompt engineering and context formatting.
"""

import logging
from datetime import datetime

from rag_types import ContextChunk, ContextQuality

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Service for building LLM context from retrieved chunks"""

    def build_rag_prompt(
        self,
        query: str,
        context_chunks: list[ContextChunk],
        conversation_history: list[dict[str, str]],
        system_message: str | None = None,
    ) -> tuple[str | None, list[dict[str, str]]]:
        """
        Build a complete RAG prompt with context and conversation history.

        Args:
            query: User query
            context_chunks: Retrieved context chunks
            conversation_history: Previous messages
            system_message: Custom system prompt

        Returns:
            Tuple of (final_system_message, messages_for_llm)
            final_system_message can be None if no system message or context provided
        """
        final_system_message = self._add_date_context(system_message)

        if context_chunks:
            context_section = self._build_context_sections(context_chunks)
            rag_instruction = self._build_rag_instruction(context_section)
            final_system_message = f"{final_system_message}\n\n{rag_instruction}"
            logger.info(f"🔍 Using RAG with {len(context_chunks)} context chunks")
        else:
            logger.info("🤖 No relevant context found, using LLM knowledge only")

        messages = conversation_history.copy()
        messages.append({"role": "user", "content": query})

        return final_system_message, messages

    def _add_date_context(self, system_message: str | None) -> str:
        """Add current date context to system message.

        Args:
            system_message: Existing system message or None

        Returns:
            System message with date context appended
        """
        current_date = datetime.now().strftime("%B %d, %Y")
        current_year = datetime.now().year
        date_context = (
            f"**IMPORTANT - Current Date Information:**\n"
            f"- Today's date: {current_date}\n"
            f"- Current year: {current_year}\n"
            f"- When using web_search tool, do NOT add years to search queries unless the user explicitly mentions a specific year. "
            f"Use the current year ({current_year}) only if the user asks about 'this year' or 'current year'."
        )

        if system_message:
            return f"{system_message}\n\n{date_context}"
        return date_context

    def _build_context_sections(self, context_chunks: list[ContextChunk]) -> str:
        """Build formatted context sections from chunks.

        Args:
            context_chunks: List of context chunks to format

        Returns:
            Formatted context sections as a string
        """
        uploaded_docs, retrieved_chunks = self._separate_chunks(context_chunks)
        context_parts = []

        if uploaded_docs:
            uploaded_section = self._format_uploaded_docs(uploaded_docs)
            context_parts.append(
                f"=== UPLOADED DOCUMENT (Primary user content for analysis) ===\n\n{uploaded_section}"
            )

        if retrieved_chunks:
            retrieved_section = self._format_retrieved_chunks(retrieved_chunks)
            context_parts.append(
                f"=== KNOWLEDGE BASE (Retrieved relevant information) ===\n\n{retrieved_section}"
            )

        return "\n\n---\n\n".join(context_parts)

    def _separate_chunks(
        self, context_chunks: list[ContextChunk]
    ) -> tuple[list[ContextChunk], list[ContextChunk]]:
        """Separate uploaded documents from RAG-retrieved chunks.

        Args:
            context_chunks: List of all context chunks

        Returns:
            Tuple of (uploaded_docs, retrieved_chunks)
        """
        uploaded_docs = []
        retrieved_chunks = []

        for chunk in context_chunks:
            metadata = chunk.get("metadata", {})
            source = metadata.get("source", "")
            if source == "uploaded_document":
                uploaded_docs.append(chunk)
            else:
                retrieved_chunks.append(chunk)

        return uploaded_docs, retrieved_chunks

    def _format_uploaded_docs(self, uploaded_docs: list[ContextChunk]) -> str:
        """Format uploaded document chunks."""
        uploaded_texts = []
        for chunk in uploaded_docs:
            content = chunk["content"]
            metadata = chunk.get("metadata", {})
            doc_name = metadata.get("file_name", "uploaded_document")
            uploaded_texts.append(f"[Uploaded File: {doc_name}]\n{content}")
        return "\n\n".join(uploaded_texts)

    def _format_retrieved_chunks(self, retrieved_chunks: list[ContextChunk]) -> str:
        """Format RAG-retrieved chunks."""
        retrieved_texts = []
        for chunk in retrieved_chunks:
            content = chunk["content"]
            similarity = chunk.get("similarity", 0)
            metadata = chunk.get("metadata", {})
            source_doc = metadata.get("file_name", "Unknown")
            retrieved_texts.append(f"[Source: {source_doc}, Score: {similarity:.2f}]\n{content}")
        return "\n\n".join(retrieved_texts)

    def _build_rag_instruction(self, context_section: str) -> str:
        """Build RAG instruction with context."""
        return (
            "You have access to relevant information from the knowledge base below. "
            "Use this context to answer the user's question directly and naturally. "
            "The context may include structured data, document content, or other information. "
            "Reference specific details when relevant and answer naturally based on what's provided. "
            "Do not add inline source citations like '[Source: ...]' since "
            "complete source citations will be automatically added at the end of your response.\n\n"
            f"Context:\n{context_section}\n\n"
        )

    def format_context_summary(self, context_chunks: list[ContextChunk]) -> str:
        """
        Create a summary of retrieved context for logging/debugging.

        Args:
            context_chunks: Retrieved context chunks

        Returns:
            Human-readable summary string
        """
        if not context_chunks:
            return "No context retrieved"

        # Group by source document
        sources = {}
        for chunk in context_chunks:
            metadata = chunk.get("metadata", {})
            source = metadata.get("file_name", "Unknown")
            similarity = chunk.get("similarity", 0)

            if source not in sources:
                sources[source] = {"count": 0, "max_similarity": 0}
            sources[source]["count"] += 1
            sources[source]["max_similarity"] = max(sources[source]["max_similarity"], similarity)

        # Build summary
        summary_parts = []
        for source, info in sources.items():
            summary_parts.append(
                f"{source} ({info['count']} chunks, max score: {info['max_similarity']:.2f})"
            )

        return f"Retrieved from {len(sources)} documents: " + "; ".join(summary_parts)

    def validate_context_quality(
        self, context_chunks: list[ContextChunk], min_similarity: float = 0.5
    ) -> ContextQuality:
        """
        Validate the quality of retrieved context chunks.

        Args:
            context_chunks: Retrieved context chunks
            min_similarity: Minimum similarity threshold for quality

        Returns:
            Quality metrics dictionary
        """
        if not context_chunks:
            return {
                "quality_score": 0.0,
                "high_quality_chunks": 0,
                "avg_similarity": 0.0,
                "unique_sources": 0,
                "warnings": ["No context chunks provided"],
            }

        similarities = [chunk.get("similarity", 0) for chunk in context_chunks]
        high_quality_count = sum(1 for s in similarities if s >= min_similarity)

        # Count unique sources
        unique_sources = set()
        for chunk in context_chunks:
            metadata = chunk.get("metadata", {})
            source = metadata.get("file_name", "Unknown")
            unique_sources.add(source)

        avg_similarity = sum(similarities) / len(similarities)
        quality_score = (high_quality_count / len(context_chunks)) * avg_similarity

        warnings = []
        if high_quality_count == 0:
            warnings.append("No high-quality chunks found")
        if len(unique_sources) == 1 and len(context_chunks) > 3:
            warnings.append("All chunks from single source - consider broader search")
        if avg_similarity < 0.3:
            warnings.append("Low average similarity - query may not match available content")

        return {
            "quality_score": quality_score,
            "high_quality_chunks": high_quality_count,
            "avg_similarity": avg_similarity,
            "unique_sources": len(unique_sources),
            "warnings": warnings,
        }
