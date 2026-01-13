"""Tests for company profile clarification node."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from langgraph.types import Command

from agents.profiler.nodes.clarification import clarify_with_user
from agents.profiler.state import ProfileAgentState


@pytest.mark.asyncio
class TestClarificationUrlHandling:
    """Tests for URL detection and company name extraction in clarification node."""

    async def test_detects_url_and_extracts_company_name(self):
        """Test that URLs in query are detected and replaced with company name."""
        state: ProfileAgentState = {"query": "profile www.costco.com"}
        config = {"configurable": {"allow_clarification": True}}

        with patch("agents.profiler.utils.extract_company_from_url") as mock_extract:
            mock_extract.return_value = "Costco"

            result = await clarify_with_user(state, config)

            # Should extract company name and update query
            mock_extract.assert_called_once_with("www.costco.com")
            assert isinstance(result, Command)
            assert result.goto == "write_research_brief"
            assert result.update["query"] == "profile Costco"

    async def test_handles_https_urls(self):
        """Test that https URLs are detected."""
        state: ProfileAgentState = {"query": "profile https://stripe.com"}
        config = {"configurable": {"allow_clarification": True}}

        with patch("agents.profiler.utils.extract_company_from_url") as mock_extract:
            mock_extract.return_value = "Stripe"

            result = await clarify_with_user(state, config)

            mock_extract.assert_called_once_with("https://stripe.com")
            assert result.update["query"] == "profile Stripe"

    async def test_handles_url_with_path(self):
        """Test that URLs with paths are detected."""
        state: ProfileAgentState = {"query": "profile www.example.com/about"}
        config = {"configurable": {"allow_clarification": True}}

        with patch("agents.profiler.utils.extract_company_from_url") as mock_extract:
            mock_extract.return_value = "Example Corp"

            result = await clarify_with_user(state, config)

            mock_extract.assert_called_once_with("www.example.com/about")
            assert result.update["query"] == "profile Example Corp"

    async def test_continues_with_original_query_if_extraction_fails(self):
        """Test that if extraction fails, original query is used."""
        state: ProfileAgentState = {"query": "profile www.invalid.com"}
        config = {"configurable": {"allow_clarification": True}}

        with patch("agents.profiler.utils.extract_company_from_url") as mock_extract:
            mock_extract.return_value = None  # Extraction failed

            with patch("config.settings.Settings"):
                # Mock LLM response for clarification check
                mock_llm = AsyncMock()
                mock_response = Mock()
                mock_response.content = "need_clarification: false"
                mock_llm.ainvoke = AsyncMock(return_value=mock_response)

                with patch(
                    "langchain_openai.ChatOpenAI",
                    return_value=mock_llm,
                ):
                    result = await clarify_with_user(state, config)

                    # Should proceed with original query
                    assert result.goto == "write_research_brief"

    async def test_no_url_detection_proceeds_normally(self):
        """Test that queries without URLs proceed through normal clarification."""
        state: ProfileAgentState = {"query": "profile Tesla"}
        config = {"configurable": {"allow_clarification": True}}

        with patch("config.settings.Settings"):
            # Mock LLM response
            mock_llm = AsyncMock()
            mock_response = Mock()
            mock_response.content = "need_clarification: false"
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)

            with patch(
                "langchain_openai.ChatOpenAI",
                return_value=mock_llm,
            ):
                result = await clarify_with_user(state, config)

                # Should proceed to research brief without URL extraction
                assert result.goto == "write_research_brief"

    async def test_clarification_disabled_skips_url_extraction(self):
        """Test that when clarification is disabled, URL extraction is skipped."""
        state: ProfileAgentState = {"query": "profile www.example.com"}
        config = {"configurable": {"allow_clarification": False}}

        with patch("agents.profiler.utils.extract_company_from_url") as mock_extract:
            result = await clarify_with_user(state, config)

            # Should not call extraction when clarification disabled
            mock_extract.assert_not_called()
            assert result.goto == "write_research_brief"
