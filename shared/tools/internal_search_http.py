"""
HTTP-based internal search tool for agents.

This version uses rag-service's /api/v1/retrieve endpoint instead of direct Qdrant access.
Provides centralized vector access for all agents.
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

            # Get retrieval client
            from shared.clients import (
                RetrievalAuthError,
                RetrievalConnectionError,
                RetrievalServiceError,
                RetrievalTimeoutError,
                get_retrieval_client,
            )

            retrieval_client = get_retrieval_client()

            # Build system message with permissions if available
            system_message = self._build_permission_context()

            # Call retrieval API
            chunks = await retrieval_client.retrieve(
                query=query,
                user_id=self.user_id or "research_agent@system",
                system_message=system_message,
                max_chunks=max_chunks,
                similarity_threshold=similarity_threshold,
                enable_query_rewriting=True,
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

        except RetrievalAuthError as e:
            logger.error(f"Authentication failed: {e}")
            return (
                "Internal search authentication failed. "
                "Please check RAG_SERVICE_TOKEN configuration."
            )
        except RetrievalTimeoutError as e:
            logger.error(f"Request timed out: {e}")
            return (
                f"Internal search timed out after {e.timeout_seconds}s. "
                "The service may be overloaded. Please try again."
            )
        except RetrievalConnectionError as e:
            logger.error(f"Connection error: {e}")
            return (
                f"Cannot connect to retrieval service at {e.base_url}. "
                "Please check that rag-service is running."
            )
        except RetrievalServiceError as e:
            logger.error(f"Service error: {e}")
            return f"Retrieval service returned error {e.status_code}: {e.detail}"
        except Exception as e:
            logger.error(f"Unexpected internal search error: {e}")
            return f"Internal search error: {str(e)}"

    def _run(
        self, query: str, max_chunks: int = 10, similarity_threshold: float = 0.7
    ) -> str:
        """Sync wrapper - not implemented (use async version)."""
        return "Internal search requires async execution. Use ainvoke() instead."

    def _build_permission_context(self) -> str | None:
        """Build system message with user permissions."""
        if not self.user_permissions:
            return None

        lines = []

        if user := self.user_permissions.get("user_id"):
            lines.append(f"User: {user}")

        if role := self.user_permissions.get("role"):
            lines.append(f"Role: {role}")

        if projects := self.user_permissions.get("projects"):
            lines.append(f"Accessible Projects: {', '.join(projects)}")

        if clearance := self.user_permissions.get("clearance"):
            lines.append(f"Clearance Level: {clearance}")

        return "\n".join(lines) if lines else None

    def _format_results(self, chunks: list[dict[str, Any]], query: str) -> str:
        """Format retrieved chunks as structured text."""
        docs_by_source = self._group_by_source(chunks)
        has_relationship = self._detect_relationship(chunks)

        parts = [
            self._format_relationship_status(has_relationship),
            self._format_summary(query, chunks, docs_by_source),
            self._format_documents(docs_by_source),
        ]

        return "\n".join(parts)

    def _group_by_source(self, chunks: list[dict[str, Any]]) -> dict[str, list[dict]]:
        """Group chunks by source document."""
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

        return docs_by_source

    def _format_relationship_status(self, has_relationship: bool) -> str:
        """Format relationship status header."""
        if has_relationship:
            return "Relationship status: Existing client\n"
        return "Relationship status: No prior engagement found\n"

    def _format_summary(
        self, query: str, chunks: list[dict], docs_by_source: dict
    ) -> str:
        """Format search summary."""
        return (
            f"Internal search results for: {query}\n"
            f"Found {len(chunks)} relevant chunks from {len(docs_by_source)} documents\n"
        )

    def _format_documents(self, docs_by_source: dict[str, list[dict]]) -> str:
        """Format document results."""
        lines = []

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
