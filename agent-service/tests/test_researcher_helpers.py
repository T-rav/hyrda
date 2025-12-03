"""Unit tests for researcher helper functions.

Tests the refactored helper functions extracted from researcher_tools.
Note: Tool invocation helpers (_execute_*) are thin wrappers around Langchain tools,
so we test them with real tools rather than mocking complex Langchain internals.
"""

import pytest
from unittest.mock import AsyncMock
from langchain_core.messages import ToolMessage

from agents.profiler.nodes.researcher import (
    _execute_web_search,
    _execute_scrape_url,
    _execute_deep_research,
)


class TestResearcherHelpers:
    """Test suite for researcher helper functions."""

    # Tests for _execute_web_search
    @pytest.mark.asyncio
    async def test_execute_web_search_success(self):
        """Test successful web search."""
        # Arrange
        tool_args = {"query": "Tesla AI", "max_results": 5}
        tool_id = "call_123"
        mock_client = AsyncMock()
        mock_client.search.return_value = [
            {"title": "Tesla AI", "url": "https://example.com", "snippet": "Summary"}
        ]

        # Act
        result, note = await _execute_web_search(tool_args, tool_id, mock_client)

        # Assert
        assert isinstance(result, ToolMessage)
        assert "Tesla AI" in note
        assert note is not None

    @pytest.mark.asyncio
    async def test_execute_web_search_error(self):
        """Test web search error handling."""
        # Arrange
        tool_args = {"query": "test"}
        tool_id = "call_123"
        mock_client = AsyncMock()
        mock_client.search.side_effect = Exception("API error")

        # Act
        result, note = await _execute_web_search(tool_args, tool_id, mock_client)

        # Assert
        assert "error" in result.content.lower()
        assert note is None

    # Tests for _execute_scrape_url
    @pytest.mark.asyncio
    async def test_execute_scrape_url_success(self):
        """Test successful URL scraping."""
        # Arrange
        tool_args = {"url": "https://example.com"}
        tool_id = "call_123"
        mock_client = AsyncMock()
        mock_client.scrape_url.return_value = {
            "success": True,
            "content": "Page content",
            "title": "Example Page",
        }

        # Act
        result, note = await _execute_scrape_url(tool_args, tool_id, mock_client)

        # Assert
        assert isinstance(result, ToolMessage)
        assert "Example Page" in note
        assert note is not None

    @pytest.mark.asyncio
    async def test_execute_scrape_url_failure(self):
        """Test scraping failure."""
        # Arrange
        tool_args = {"url": "https://example.com"}
        tool_id = "call_123"
        mock_client = AsyncMock()
        mock_client.scrape_url.return_value = {
            "success": False,
            "error": "404 Not Found",
        }

        # Act
        result, note = await _execute_scrape_url(tool_args, tool_id, mock_client)

        # Assert
        assert "failed" in result.content.lower()
        assert note is None

    # Tests for _execute_deep_research
    @pytest.mark.asyncio
    async def test_execute_deep_research_success(self):
        """Test successful deep research."""
        # Arrange
        tool_args = {"query": "Tesla AI strategy"}
        tool_id = "call_123"
        mock_client = AsyncMock()
        mock_client.deep_research.return_value = {
            "success": True,
            "answer": "Tesla is investing heavily in AI",
            "sources": ["https://example.com"],
        }

        # Act
        result, note = await _execute_deep_research(tool_args, tool_id, mock_client)

        # Assert
        assert isinstance(result, ToolMessage)
        assert "Tesla is investing" in note
        assert "Sources" in note

    @pytest.mark.asyncio
    async def test_execute_deep_research_with_dict_sources(self):
        """Test deep research with dict source objects."""
        # Arrange
        tool_args = {"query": "test"}
        tool_id = "call_123"
        mock_client = AsyncMock()
        mock_client.deep_research.return_value = {
            "success": True,
            "answer": "Answer",
            "sources": [{"url": "https://example.com", "title": "Example"}],
        }

        # Act
        result, note = await _execute_deep_research(tool_args, tool_id, mock_client)

        # Assert
        assert "https://example.com" in note
        assert "Example" in note

    @pytest.mark.asyncio
    async def test_execute_deep_research_failure(self):
        """Test deep research failure."""
        # Arrange
        tool_args = {"query": "test"}
        tool_id = "call_123"
        mock_client = AsyncMock()
        mock_client.deep_research.return_value = {
            "success": False,
            "error": "Rate limit exceeded",
        }

        # Act
        result, note = await _execute_deep_research(tool_args, tool_id, mock_client)

        # Assert
        assert "failed" in result.content.lower()
        assert note is None
