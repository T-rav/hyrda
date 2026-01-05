"""RAG-based internal search tool for research agent.

This tool calls the centralized RAG service instead of directly accessing the vector database.
This makes the research agent portable and environment-agnostic.
"""

import logging
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RAGInternalSearchInput(BaseModel):
    """Input schema for RAG-based internal search tool."""

    query: str = Field(
        min_length=3,
        description="What to search for in internal knowledge base. Be specific about what you're looking for. MUST be a meaningful search query (minimum 3 characters). DO NOT call with empty string.",
    )
    effort: str = Field(
        default="medium",
        description='Research depth - "low" (quick), "medium" (balanced), "high" (comprehensive). Default: "medium"',
    )


class RAGInternalSearchTool(BaseTool):
    """Search the internal knowledge base via centralized RAG service.

    Use this FIRST before web search to check if we already have information about:
    - Existing customers or past clients
    - Previous projects or engagements
    - Internal documentation
    - Historical company data

    This tool is portable and calls the RAG service instead of directly accessing the vector database.
    """

    name: str = "internal_search_tool"
    description: str = (
        "Search the internal knowledge base for existing information. "
        "Use this FIRST before web search to check our internal docs, customer history, past projects, and internal documentation. "
        "IMPORTANT: Only call if you have a specific company name or topic to search for (minimum 3 characters). "
        "DO NOT call with empty query."
    )
    args_schema: type[BaseModel] = RAGInternalSearchInput

    # RAG service (injected at initialization)
    rag_service: Any = None  # RAGService instance

    # Research context (optional, for agent-specific behavior)
    research_topic: str | None = None
    focus_area: str | None = None

    class Config:
        """Config class."""

        arbitrary_types_allowed = True

    def __init__(
        self,
        rag_service: Any = None,
        research_topic: str | None = None,
        focus_area: str | None = None,
        **kwargs,
    ):
        """Initialize with RAG service.

        Args:
            rag_service: RAG service instance (must have deep_research_for_agent method)
            research_topic: Optional research topic for context
            focus_area: Optional focus area for context
            **kwargs: Additional BaseTool arguments
        """
        # Pass components as kwargs to avoid Pydantic issues
        kwargs["rag_service"] = rag_service
        kwargs["research_topic"] = research_topic
        kwargs["focus_area"] = focus_area

        super().__init__(**kwargs)

        # Lazy-load RAG service if not provided
        if not self.rag_service:
            self._initialize_rag_service()

    def _initialize_rag_service(self):
        """Initialize RAG service from environment (fallback only).

        Uses the agent-service's RAG service singleton.
        """
        try:
            from config.settings import Settings
            from services.rag_service import RAGService

            settings = Settings()
            self.rag_service = RAGService(settings)

            logger.info("✅ Initialized RAG service for internal search tool")

        except Exception as e:
            logger.error(f"Failed to initialize RAG service: {e}")
            logger.warning("Internal search tool will be unavailable")

    async def _arun(
        self,
        query: str,
        effort: str = "medium",
    ) -> str:
        """Execute internal search via RAG service asynchronously.

        Args:
            query: Search query
            effort: Research depth level ("low", "medium", "high")

        Returns:
            Formatted search results with citations
        """
        # Check if RAG service is available
        if not self.rag_service:
            return (
                "Internal search service not available (RAG service not configured)"
            )

        try:
            logger.info(f"🔍 RAG-based internal search ({effort}): {query[:100]}...")

            # Build agent context for better retrieval
            agent_context = {}
            if self.research_topic:
                agent_context["research_topic"] = self.research_topic
            if self.focus_area:
                agent_context["focus_area"] = self.focus_area

            # Build custom system prompt for research agent
            system_prompt = """You are conducting deep research for a research report.
Focus on finding comprehensive, accurate information from the internal knowledge base.
Pay special attention to:
- Historical context and past projects
- Technical details and specifications
- Business relationships and partnerships
- Key findings and insights"""

            # Call RAG service's deep research method
            result = await self.rag_service.deep_research_for_agent(
                query=query,
                system_prompt=system_prompt,
                effort=effort,
                agent_context=agent_context if agent_context else None,
                user_id=None,  # Research agent doesn't have user context
            )

            if not result.get("success"):
                error = result.get("error", "Unknown error")
                logger.warning(f"RAG-based internal search failed: {error}")
                return f"Internal search failed: {error}"

            # Return formatted content with citations
            content = result.get("content", "")
            unique_documents = result.get("unique_documents", 0)
            total_chunks = result.get("total_chunks", 0)

            logger.info(
                f"✅ RAG-based internal search complete: {total_chunks} chunks from {unique_documents} documents"
            )

            # Add metadata footer
            footer = f"\n\n---\n*Found {total_chunks} relevant sections from {unique_documents} internal documents*"

            return content + footer

        except Exception as e:
            logger.error(f"RAG-based internal search error: {e}")
            return f"Internal search error: {str(e)}"

    def _run(self, query: str, effort: str = "medium") -> str:
        """Synchronous version (not supported)."""
        raise NotImplementedError("This tool only supports async execution")
