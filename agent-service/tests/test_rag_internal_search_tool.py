"""Tests for RAGInternalSearchTool."""

from unittest.mock import AsyncMock

import pytest

from agents.system.research.tools.rag_internal_search import RAGInternalSearchTool


@pytest.fixture
def mock_rag_service():
    """Mock RAG service."""
    service = AsyncMock()
    service.deep_research_for_agent = AsyncMock()
    return service


@pytest.fixture
def rag_search_tool(mock_rag_service):
    """Create RAG search tool with mocked service."""
    tool = RAGInternalSearchTool(
        rag_service=mock_rag_service,
        research_topic="Test Research",
        focus_area="Test Focus",
    )
    return tool


@pytest.mark.asyncio
async def test_rag_internal_search_success(rag_search_tool, mock_rag_service):
    """Test successful internal search via RAG service."""
    # Mock successful RAG response
    mock_rag_service.deep_research_for_agent.return_value = {
        "success": True,
        "content": "**Research Summary:**\nTest findings about AI implementation.\n\n**Sources:**\n[1] ai_guide.pdf",
        "chunks": [
            {
                "content": "AI implementation best practices",
                "metadata": {"file_name": "ai_guide.pdf"},
            }
        ],
        "sources": ["ai_guide.pdf"],
        "summary": "Test summary",
        "unique_documents": 1,
        "total_chunks": 1,
    }

    result = await rag_search_tool._arun(
        query="What are our AI best practices?", effort="medium"
    )

    # Verify result
    assert "Research Summary:" in result
    assert "ai_guide.pdf" in result
    assert "1 relevant sections from 1 internal documents" in result

    # Verify RAG service was called correctly
    mock_rag_service.deep_research_for_agent.assert_called_once()
    call_kwargs = mock_rag_service.deep_research_for_agent.call_args.kwargs
    assert call_kwargs["query"] == "What are our AI best practices?"
    assert call_kwargs["effort"] == "medium"
    assert call_kwargs["agent_context"]["research_topic"] == "Test Research"
    assert call_kwargs["agent_context"]["focus_area"] == "Test Focus"


@pytest.mark.asyncio
async def test_rag_internal_search_service_unavailable(mock_rag_service):
    """Test behavior when RAG service is unavailable."""
    tool = RAGInternalSearchTool(rag_service=None)

    result = await tool._arun(query="test query", effort="low")

    assert "not available" in result
    assert "not configured" in result


@pytest.mark.asyncio
async def test_rag_internal_search_error_handling(rag_search_tool, mock_rag_service):
    """Test error handling when RAG service fails."""
    # Mock RAG service error
    mock_rag_service.deep_research_for_agent.return_value = {
        "success": False,
        "error": "Vector database connection failed",
    }

    result = await rag_search_tool._arun(query="test", effort="medium")

    assert "Internal search failed" in result
    assert "Vector database connection failed" in result


@pytest.mark.asyncio
async def test_rag_internal_search_exception_handling(
    rag_search_tool, mock_rag_service
):
    """Test exception handling during search."""
    # Mock exception
    mock_rag_service.deep_research_for_agent.side_effect = Exception("Unexpected error")

    result = await rag_search_tool._arun(query="test", effort="medium")

    assert "Internal search error" in result
    assert "Unexpected error" in result


@pytest.mark.asyncio
async def test_rag_internal_search_effort_levels(rag_search_tool, mock_rag_service):
    """Test that different effort levels are passed correctly."""
    mock_rag_service.deep_research_for_agent.return_value = {
        "success": True,
        "content": "Test results",
        "chunks": [],
        "sources": [],
        "summary": "",
        "unique_documents": 0,
        "total_chunks": 0,
    }

    # Test all effort levels
    for effort in ["low", "medium", "high"]:
        await rag_search_tool._arun(query="test", effort=effort)

        call_kwargs = mock_rag_service.deep_research_for_agent.call_args.kwargs
        assert call_kwargs["effort"] == effort


@pytest.mark.asyncio
async def test_rag_internal_search_without_context(mock_rag_service):
    """Test internal search without optional context."""
    tool = RAGInternalSearchTool(
        rag_service=mock_rag_service,
        # No research_topic or focus_area
    )

    mock_rag_service.deep_research_for_agent.return_value = {
        "success": True,
        "content": "Test results",
        "chunks": [],
        "sources": [],
        "summary": "",
        "unique_documents": 0,
        "total_chunks": 0,
    }

    await tool._arun(query="test", effort="medium")

    call_kwargs = mock_rag_service.deep_research_for_agent.call_args.kwargs
    # Should not include agent_context or it should be None
    assert call_kwargs["agent_context"] is None or not call_kwargs["agent_context"]


@pytest.mark.asyncio
async def test_rag_internal_search_formatting(rag_search_tool, mock_rag_service):
    """Test result formatting with multiple sources."""
    mock_rag_service.deep_research_for_agent.return_value = {
        "success": True,
        "content": "**Research Summary:**\nFindings\n\n**Sources:**\n[1] doc1.pdf\n[2] doc2.pdf",
        "chunks": [],
        "sources": ["doc1.pdf", "doc2.pdf"],
        "summary": "Summary",
        "unique_documents": 2,
        "total_chunks": 5,
    }

    result = await rag_search_tool._arun(query="test", effort="high")

    # Verify formatting
    assert "Research Summary:" in result
    assert "Sources:" in result
    assert "5 relevant sections from 2 internal documents" in result


@pytest.mark.asyncio
async def test_rag_internal_search_system_prompt(rag_search_tool, mock_rag_service):
    """Test that custom system prompt is passed."""
    mock_rag_service.deep_research_for_agent.return_value = {
        "success": True,
        "content": "Test",
        "chunks": [],
        "sources": [],
        "summary": "",
        "unique_documents": 0,
        "total_chunks": 0,
    }

    await rag_search_tool._arun(query="test", effort="medium")

    call_kwargs = mock_rag_service.deep_research_for_agent.call_args.kwargs
    system_prompt = call_kwargs["system_prompt"]

    # Verify prompt contains research-specific guidance
    assert "deep research" in system_prompt.lower()
    assert "comprehensive" in system_prompt.lower()


def test_rag_internal_search_sync_not_supported(rag_search_tool):
    """Test that sync execution raises NotImplementedError."""
    with pytest.raises(NotImplementedError):
        rag_search_tool._run(query="test", effort="medium")


def test_rag_internal_search_tool_creation_without_service():
    """Test that tool can be created without RAG service (will lazy-load)."""
    # Should not raise error - lazy initialization will happen on first use
    tool = RAGInternalSearchTool()

    # Verify tool was created
    assert tool is not None
    assert tool.name == "internal_search_tool"

    # Service should be None initially (or lazy-loaded)
    # Will be initialized when _arun is called
