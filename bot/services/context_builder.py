"""
Context Builder Service

Handles building context for LLM prompts from retrieved chunks.
Manages prompt engineering and context formatting.
"""

import logging
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
    ) -> tuple[str, list[dict[str, str]]]:
        """
        Build a complete RAG prompt with context and conversation history.

        Args:
            query: User query
            context_chunks: Retrieved context chunks
            conversation_history: Previous messages
            system_message: Custom system prompt

        Returns:
            Tuple of (final_system_message, messages_for_llm)
        """
        final_system_message = system_message

        if context_chunks:
            # Build context from retrieved chunks
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

            # Create RAG system message
            context_section = "\n\n".join(context_texts)

            # Check if we have uploaded document content
            has_uploaded_doc = any(
                chunk.get("metadata", {}).get("source") == "uploaded_document"
                for chunk in context_chunks
            )

            if has_uploaded_doc:
                rag_instruction = (
                    "IMPORTANT: The user has uploaded a document that you CAN access and analyze. "
                    "The document content is provided in the context below. Use this content to answer their questions about the document. "
                    "Do not say you cannot access documents - you have the full content available. "
                    "Answer naturally based on the provided document content without adding inline source citations like '[Source: ...]' since "
                    "complete source citations will be automatically added at the end of your response.\n\n"
                    f"Document Content and Related Information:\n{context_section}\n\n"
                )
            else:
                rag_instruction = (
                    "Use the following context to answer the user's question. "
                    "Answer naturally without adding inline source citations like '[Source: ...]' since "
                    "complete source citations will be automatically added at the end of your response. "
                    "If the context doesn't contain relevant information, "
                    "say so and provide a general response based on your knowledge.\n\n"
                    f"Context:\n{context_section}\n\n"
                )

            if final_system_message:
                final_system_message = f"{final_system_message}\n\n{rag_instruction}"
            else:
                final_system_message = rag_instruction

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
