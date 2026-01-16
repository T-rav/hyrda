"""
HTTP-based internal search tool for agents.

This version uses rag-service's /api/v1/retrieve endpoint instead of direct Qdrant access.
Provides the same interface as the original internal_search.py but with centralized vector access.
"""

import logging
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class InternalSearchInput(BaseModel):
    """Input schema for internal search tool."""

    query: str = Field(
        min_length=3,
        description="What to search for in internal knowledge base. Be specific about what you're looking for. MUST be a meaningful search query (minimum 3 characters). DO NOT call with empty string.",
    )
    max_chunks: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Maximum chunks to return (1-20). Default: 10",
    )
    similarity_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score (0.0-1.0). Default: 0.7",
    )


class InternalSearchToolHTTP(BaseTool):
    """Search the internal knowledge base via rag-service HTTP API.

    Use this FIRST before web search to check if we already have information about:
    - Existing customers or past clients
    - Previous projects or engagements
    - Internal documentation
    - Historical company data

    This version uses HTTP retrieval API instead of direct Qdrant access.
    """

    name: str = "internal_search_tool"
    description: str = (
        "Search the internal knowledge base for existing information. "
        "Use this FIRST before web search to check our internal docs, customer history, past projects, and internal documentation. "
        "IMPORTANT: Only call if you have a specific company name or topic to search for (minimum 3 characters). "
        "DO NOT call with empty query."
    )
    args_schema: type[BaseModel] = InternalSearchInput

    # User context for permission-based filtering (optional)
    user_id: str | None = None
    user_permissions: dict[str, Any] | None = None

    class Config:
        """Config class."""

        arbitrary_types_allowed = True

    async def _arun(
        self,
        query: str,
        max_chunks: int = 10,
        similarity_threshold: float = 0.7,
    ) -> str:
        """Execute internal search via HTTP retrieval API.

        Args:
            query: Search query
            max_chunks: Maximum chunks to return
            similarity_threshold: Minimum similarity score

        Returns:
            Formatted search results with metadata
        """
        try:
            logger.info(f"🔍 Internal search (HTTP): {query[:100]}...")

            # Import retrieval client
            from services.retrieval_client import get_retrieval_client

            retrieval_client = get_retrieval_client()

            # Build system message with permissions if available
            system_message = None
            if self.user_permissions:
                system_message = self._build_permission_context(self.user_permissions)

            # Call retrieval API
            chunks = await retrieval_client.retrieve(
                query=query,
                user_id=self.user_id or "research_agent@system",
                system_message=system_message,
                max_chunks=max_chunks,
                similarity_threshold=similarity_threshold,
                enable_query_rewriting=True,  # Enable for better results
            )

            if not chunks:
                logger.info("❌ No results found in internal knowledge base")
                return self._format_no_results(query)

            # Format results
            formatted_result = self._format_results(chunks, query)

            logger.info(
                f"✅ Internal search found {len(chunks)} chunks from internal knowledge base"
            )

            return formatted_result

        except Exception as e:
            logger.error(f"Internal search failed: {e}")
            return f"Internal search error: {str(e)}"

    def _run(self, query: str, max_chunks: int = 10, similarity_threshold: float = 0.7) -> str:
        """Sync wrapper - not implemented (use async version)."""
        return "Internal search requires async execution. Use ainvoke() instead."

    def _build_permission_context(self, permissions: dict[str, Any]) -> str:
        """Build system message with user permissions."""
        lines = []

        if user := permissions.get("user_id"):
            lines.append(f"User: {user}")

        if role := permissions.get("role"):
            lines.append(f"Role: {role}")

        if projects := permissions.get("projects"):
            lines.append(f"Accessible Projects: {', '.join(projects)}")

        if clearance := permissions.get("clearance"):
            lines.append(f"Clearance Level: {clearance}")

        return "\n".join(lines) if lines else None

    def _format_results(self, chunks: list[dict[str, Any]], query: str) -> str:
        """Format retrieved chunks as structured text."""
        # Group chunks by source document
        docs_by_source = {}
        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            source = metadata.get("file_name", "Unknown")

            if source not in docs_by_source:
                docs_by_source[source] = []

            docs_by_source[source].append(
                {
                    "content": chunk.get("content", ""),
                    "similarity": chunk.get("similarity", 0.0),
                    "metadata": metadata,
                }
            )

        # Check if we found relationship information
        has_relationship = self._detect_relationship(chunks)

        # Build formatted output
        lines = []

        # Add relationship status
        if has_relationship:
            lines.append("Relationship status: Existing client")
            lines.append("")
        else:
            lines.append("Relationship status: No prior engagement found")
            lines.append("")

        lines.append(f"Internal search results for: {query}")
        lines.append(f"Found {len(chunks)} relevant chunks from {len(docs_by_source)} documents")
        lines.append("")

        # Format each document
        for doc_num, (source, doc_chunks) in enumerate(docs_by_source.items(), 1):
            lines.append(f"[Document {doc_num}: {source}]")

            # Sort by similarity
            doc_chunks.sort(key=lambda x: x["similarity"], reverse=True)

            for chunk in doc_chunks:
                content = chunk["content"][:500]  # Truncate long content
                similarity = chunk["similarity"]
                lines.append(f"  (Relevance: {similarity:.2f})")
                lines.append(f"  {content}")
                lines.append("")

        return "\n".join(lines)

    def _format_no_results(self, query: str) -> str:
        """Format message when no results found."""
        return f"""Relationship status: No prior engagement found

Internal search results for: {query}
No relevant information found in internal knowledge base.

This suggests:
- We do not have prior engagement history with this entity
- No internal documentation exists
- This may be a new prospect

Recommendation: Use web search to gather external information."""

    def _detect_relationship(self, chunks: list[dict[str, Any]]) -> bool:
        """
        Detect if chunks indicate an existing client relationship.

        Looks for indicators like:
        - Project documents
        - Client notes
        - Engagement records
        - Historical data
        """
        relationship_indicators = [
            "project",
            "client",
            "engagement",
            "contract",
            "proposal",
            "statement of work",
            "sow",
            "deliverable",
            "milestone",
            "invoice",
            "meeting notes",
            "kickoff",
        ]

        for chunk in chunks:
            content = chunk.get("content", "").lower()
            metadata = chunk.get("metadata", {})

            # Check content for relationship indicators
            if any(indicator in content for indicator in relationship_indicators):
                return True

            # Check metadata for relationship indicators
            source = metadata.get("source", "").lower()
            file_name = metadata.get("file_name", "").lower()
            doc_type = metadata.get("document_type", "").lower()

            if any(
                indicator in source or indicator in file_name or indicator in doc_type
                for indicator in relationship_indicators
            ):
                return True

        return False
