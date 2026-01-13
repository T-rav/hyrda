"""Tests for RAG service deep_research_for_agent method."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.rag_service import RAGService


@pytest.fixture
def mock_settings():
    """Mock settings for RAG service."""
    settings = MagicMock()
    settings.vector = MagicMock()
    settings.embedding = MagicMock()
    settings.llm = MagicMock()
    settings.rag = MagicMock()
    settings.rag.enable_query_rewriting = False
    settings.langfuse = MagicMock()
    settings.conversation = MagicMock()
    return settings


@pytest.fixture
def mock_internal_deep_research():
    """Mock internal deep research service."""
    service = AsyncMock()
    service.deep_research = AsyncMock()
    return service


@pytest.fixture
def rag_service(mock_internal_deep_research, mock_settings):
    """Create RAG service with mocked dependencies."""
    # Patch the factory functions to avoid real initialization
    with (
        patch("services.rag_service.create_vector_store", return_value=MagicMock()),
        patch(
            "services.rag_service.create_embedding_provider", return_value=MagicMock()
        ),
        patch("services.rag_service.create_llm_provider", return_value=MagicMock()),
        patch(
            "services.rag_service.create_internal_deep_research_service",
            return_value=mock_internal_deep_research,
        ),
    ):
        service = RAGService(mock_settings)
        return service


@pytest.mark.asyncio
async def test_deep_research_for_agent_success(
    rag_service, mock_internal_deep_research
):
    """Test successful deep research for agent."""
    # Mock successful deep research result
    mock_internal_deep_research.deep_research.return_value = {
        "success": True,
        "chunks": [
            {
                "content": "Test content about AI implementation best practices.",
                "metadata": {"file_name": "ai_guide.pdf"},
                "similarity": 0.95,
            },
            {
                "content": "More content about machine learning deployment.",
                "metadata": {"file_name": "ml_deployment.pdf"},
                "similarity": 0.92,
            },
        ],
        "summary": "Comprehensive guide to AI implementation with focus on best practices.",
        "unique_documents": 2,
        "total_chunks": 2,
    }

    result = await rag_service.deep_research_for_agent(
        query="What are our AI implementation best practices?",
        system_prompt="Custom research prompt",
        effort="high",
        agent_context={"research_topic": "AI Strategy"},
        user_id="user123",
    )

    # Verify result structure
    assert result["success"] is True
    assert "content" in result
    assert "chunks" in result
    assert "sources" in result
    assert "summary" in result
    assert result["unique_documents"] == 2
    assert result["total_chunks"] == 2

    # Verify content formatting
    assert "Research Summary:" in result["content"]
    assert "Sources:" in result["content"]
    assert "ai_guide.pdf" in result["content"]
    assert "Research Context:" in result["content"]
    assert "research_topic: AI Strategy" in result["content"]

    # Verify sources list
    assert len(result["sources"]) == 2
    assert "ai_guide.pdf" in result["sources"]
    assert "ml_deployment.pdf" in result["sources"]

    # Verify deep_research was called correctly
    mock_internal_deep_research.deep_research.assert_called_once()
    call_kwargs = mock_internal_deep_research.deep_research.call_args.kwargs
    assert call_kwargs["query"] == "What are our AI implementation best practices?"
    assert call_kwargs["effort"] == "high"
    assert call_kwargs["user_id"] == "user123"


@pytest.mark.asyncio
async def test_deep_research_for_agent_service_unavailable(mock_settings):
    """Test behavior when internal deep research service is unavailable."""
    # Patch factory functions to avoid real initialization
    with (
        patch("services.rag_service.create_vector_store", return_value=MagicMock()),
        patch(
            "services.rag_service.create_embedding_provider", return_value=MagicMock()
        ),
        patch("services.rag_service.create_llm_provider", return_value=MagicMock()),
        patch(
            "services.rag_service.create_internal_deep_research_service",
            return_value=None,
        ),
    ):
        service = RAGService(mock_settings)
        # Service will have internal_deep_research=None from the factory

        result = await service.deep_research_for_agent(
            query="test query",
            effort="medium",
        )

        assert result["success"] is False
        assert "not configured" in result["error"]
        assert result["query"] == "test query"


@pytest.mark.asyncio
async def test_deep_research_for_agent_no_results(
    rag_service, mock_internal_deep_research
):
    """Test deep research with no results found."""
    # Mock empty results
    mock_internal_deep_research.deep_research.return_value = {
        "success": True,
        "chunks": [],
        "summary": "",
        "unique_documents": 0,
        "total_chunks": 0,
    }

    result = await rag_service.deep_research_for_agent(
        query="nonexistent topic",
        effort="low",
    )

    assert result["success"] is True
    assert "No relevant information found" in result["content"]
    assert result["unique_documents"] == 0
    assert result["total_chunks"] == 0
    assert result["sources"] == []


@pytest.mark.asyncio
async def test_deep_research_for_agent_formatting(
    rag_service, mock_internal_deep_research
):
    """Test content formatting with multiple sources."""
    # Mock result with multiple chunks from same document
    mock_internal_deep_research.deep_research.return_value = {
        "success": True,
        "chunks": [
            {
                "content": "First chunk from document A" * 10,  # Long content
                "metadata": {"file_name": "doc_a.pdf"},
                "similarity": 0.95,
            },
            {
                "content": "Second chunk from document A",
                "metadata": {"file_name": "doc_a.pdf"},  # Duplicate
                "similarity": 0.90,
            },
            {
                "content": "Chunk from document B",
                "metadata": {"file_name": "doc_b.pdf"},
                "similarity": 0.88,
            },
        ],
        "summary": "Test summary",
        "unique_documents": 2,
        "total_chunks": 3,
    }

    result = await rag_service.deep_research_for_agent(
        query="test",
        effort="medium",
    )

    # Verify formatting
    content = result["content"]
    assert "**Research Summary:**" in content
    assert "Test summary" in content
    assert "**Sources:**" in content

    # Verify source deduplication (doc_a should appear only once)
    assert content.count("doc_a.pdf") == 1
    assert content.count("doc_b.pdf") == 1

    # Verify excerpt truncation (long content should be truncated)
    assert "Excerpt:" in content
    assert "..." in content


@pytest.mark.asyncio
async def test_deep_research_for_agent_error_handling(
    rag_service, mock_internal_deep_research
):
    """Test error handling when deep research fails."""
    # Mock deep research failure
    mock_internal_deep_research.deep_research.return_value = {
        "success": False,
        "error": "Vector database connection failed",
        "query": "test",
    }

    result = await rag_service.deep_research_for_agent(
        query="test",
        effort="low",
    )

    assert result["success"] is False
    assert "Vector database connection failed" in result["error"]


@pytest.mark.asyncio
async def test_deep_research_for_agent_exception_handling(
    rag_service, mock_internal_deep_research
):
    """Test exception handling during deep research."""
    # Mock exception
    mock_internal_deep_research.deep_research.side_effect = Exception(
        "Unexpected error"
    )

    result = await rag_service.deep_research_for_agent(
        query="test",
        effort="medium",
    )

    assert result["success"] is False
    assert "Unexpected error" in result["error"]
    assert result["query"] == "test"


@pytest.mark.asyncio
async def test_deep_research_for_agent_effort_levels(
    rag_service, mock_internal_deep_research
):
    """Test that different effort levels are passed through correctly."""
    mock_internal_deep_research.deep_research.return_value = {
        "success": True,
        "chunks": [],
        "summary": "",
        "unique_documents": 0,
        "total_chunks": 0,
    }

    # Test all effort levels
    for effort in ["low", "medium", "high"]:
        await rag_service.deep_research_for_agent(
            query="test",
            effort=effort,
        )

        # Verify effort was passed correctly
        call_kwargs = mock_internal_deep_research.deep_research.call_args.kwargs
        assert call_kwargs["effort"] == effort


@pytest.mark.asyncio
async def test_deep_research_for_agent_without_agent_context(
    rag_service, mock_internal_deep_research
):
    """Test deep research without optional agent context."""
    mock_internal_deep_research.deep_research.return_value = {
        "success": True,
        "chunks": [
            {
                "content": "Test content",
                "metadata": {"file_name": "test.pdf"},
                "similarity": 0.9,
            },
        ],
        "summary": "Test summary",
        "unique_documents": 1,
        "total_chunks": 1,
    }

    result = await rag_service.deep_research_for_agent(
        query="test",
        effort="medium",
        # No agent_context provided
    )

    assert result["success"] is True
    # Should not include Research Context section
    assert "Research Context:" not in result["content"]
