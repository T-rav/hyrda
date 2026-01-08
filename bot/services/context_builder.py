"""
Context Builder Service

Handles building context for LLM prompts from retrieved chunks.
Manages prompt engineering and context formatting.
"""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Service for building LLM context from retrieved chunks"""

    def build_rag_prompt(
        self,
        query: str,
        context_chunks: list[dict[str, Any]],
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
        final_system_message = system_message

        # Add current date to system message so LLM knows the correct year
        current_date = datetime.now().strftime("%B %d, %Y")
        current_year = datetime.now().year
        date_context = f"**IMPORTANT - Current Date Information:**\n- Today's date: {current_date}\n- Current year: {current_year}\n- When using web_search tool, do NOT add years to search queries unless the user explicitly mentions a specific year. Use the current year ({current_year}) only if the user asks about 'this year' or 'current year'."

        if final_system_message:
            final_system_message = f"{final_system_message}\n\n{date_context}"
        else:
            final_system_message = date_context

        if context_chunks:
            # Separate uploaded documents from RAG-retrieved chunks
            uploaded_docs = []
            retrieved_chunks = []

            for chunk in context_chunks:
                metadata = chunk.get("metadata", {})
                source = metadata.get("source", "")
                if source == "uploaded_document":
                    uploaded_docs.append(chunk)
                else:
                    retrieved_chunks.append(chunk)

            # Build context sections
            context_parts = []

            # Add uploaded document section first (user's primary content)
            if uploaded_docs:
                uploaded_texts = []
                for chunk in uploaded_docs:
                    content = chunk["content"]
                    metadata = chunk.get("metadata", {})
                    doc_name = metadata.get("file_name", "uploaded_document")
                    uploaded_texts.append(f"[Uploaded File: {doc_name}]\n{content}")

                uploaded_section = "\n\n".join(uploaded_texts)
                context_parts.append(
                    f"=== UPLOADED DOCUMENT (Primary user content for analysis) ===\n\n{uploaded_section}"
                )

            # Add retrieved knowledge section
            if retrieved_chunks:
                retrieved_texts = []
                for chunk in retrieved_chunks:
                    content = chunk["content"]
                    similarity = chunk.get("similarity", 0)
                    metadata = chunk.get("metadata", {})
                    source_doc = metadata.get("file_name", "Unknown")
                    retrieved_texts.append(
                        f"[Source: {source_doc}, Score: {similarity:.2f}]\n{content}"
                    )

                retrieved_section = "\n\n".join(retrieved_texts)
                context_parts.append(
                    f"=== KNOWLEDGE BASE (Retrieved relevant information) ===\n\n{retrieved_section}"
                )

            # Combine context with clear separation
            context_section = "\n\n---\n\n".join(context_parts)

            # RAG instruction for retrieved context
            rag_instruction = (
                "You have access to relevant information from the knowledge base below. "
                "Use this context to answer the user's question directly and naturally. "
                "The context may include structured data, document content, or other information. "
                "Reference specific details when relevant and answer naturally based on what's provided. "
                "Do not add inline source citations like '[Source: ...]' since "
                "complete source citations will be automatically added at the end of your response.\n\n"
                f"Context:\n{context_section}\n\n"
            )

            final_system_message = f"{final_system_message}\n\n{rag_instruction}"

            logger.info(f"🔍 Using RAG with {len(context_chunks)} context chunks")
        else:
            logger.info("🤖 No relevant context found, using LLM knowledge only")

        # Prepare messages for LLM
        messages = conversation_history.copy()
        messages.append({"role": "user", "content": query})

        return final_system_message, messages

    def format_context_summary(self, context_chunks: list[dict[str, Any]]) -> str:
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
            sources[source]["max_similarity"] = max(
                sources[source]["max_similarity"], similarity
            )

        # Build summary
        summary_parts = []
        for source, info in sources.items():
            summary_parts.append(
                f"{source} ({info['count']} chunks, max score: {info['max_similarity']:.2f})"
            )

        return f"Retrieved from {len(sources)} documents: " + "; ".join(summary_parts)

    def validate_context_quality(
        self, context_chunks: list[dict[str, Any]], min_similarity: float = 0.5
    ) -> dict[str, Any]:
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
            warnings.append(
                "Low average similarity - query may not match available content"
            )

        return {
            "quality_score": quality_score,
            "high_quality_chunks": high_quality_count,
            "avg_similarity": avg_similarity,
            "unique_sources": len(unique_sources),
            "warnings": warnings,
        }
