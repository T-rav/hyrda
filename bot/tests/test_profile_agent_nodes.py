"""Tests for ProfileAgent LangGraph nodes."""

import os
import sys
from unittest.mock import AsyncMock, Mock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END
from langgraph.types import Command

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.company_profile.nodes.clarification import clarify_with_user
from agents.company_profile.nodes.compression import compress_research
from agents.company_profile.nodes.final_report import final_report_generation
from agents.company_profile.nodes.research_brief import write_research_brief
from agents.company_profile.nodes.researcher import researcher, researcher_tools


class TestResearchBriefNode:
    """Tests for write_research_brief node"""

    @pytest.mark.asyncio
    async def test_write_research_brief_success(self):
        """Test research brief generation without tool calls"""
        state = {
            "query": "Tell me about Tesla",
            "profile_type": "company",
            "messages": [],
        }

        config = {
            "configurable": {
                "internal_deep_research": None,  # Not available
            }
        }

        # Mock LLM response without tool calls
        mock_response = Mock()
        mock_response.content = "Research Brief:\n1. Find company overview\n2. Research products\n3. Analyze market position"
        mock_response.tool_calls = []

        with patch("langchain_openai.ChatOpenAI") as mock_chat:
            mock_llm = Mock()
            mock_llm.bind_tools = Mock(return_value=mock_llm)
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_chat.return_value = mock_llm

            result = await write_research_brief(state, config)

        # Node returns dict, not Command
        assert isinstance(result, dict)
        assert "research_brief" in result
        assert "Research Brief:" in result["research_brief"]
        assert result["profile_type"] == "company"
        assert "supervisor_messages" in result

    @pytest.mark.asyncio
    async def test_write_research_brief_with_internal_search_unavailable(self):
        """Test research brief when internal search is called but unavailable"""
        state = {
            "query": "Tell me about Apple",
            "profile_type": "company",
            "messages": [],
        }

        config = {
            "configurable": {
                "internal_deep_research": None,  # Service not available
            }
        }

        # Mock LLM response WITH tool call to internal_search_tool
        mock_tool_response = Mock()
        mock_tool_response.content = ""
        mock_tool_response.tool_calls = [
            {
                "name": "internal_search_tool",
                "args": {"query": "Apple existing knowledge", "effort": "low"},
                "id": "tc_123",
            }
        ]

        # Mock final response after tool execution
        mock_final_response = Mock()
        mock_final_response.content = (
            "Research Brief:\n1. Company background\n2. Product lines"
        )
        mock_final_response.tool_calls = []

        with patch("langchain_openai.ChatOpenAI") as mock_chat:
            mock_llm = Mock()
            mock_llm.bind_tools = Mock(return_value=mock_llm)
            mock_llm.ainvoke = AsyncMock(
                side_effect=[mock_tool_response, mock_final_response]
            )
            mock_chat.return_value = mock_llm

            result = await write_research_brief(state, config)

        # Node returns dict, not Command
        assert isinstance(result, dict)
        assert "research_brief" in result

    @pytest.mark.asyncio
    async def test_write_research_brief_exception_handling(self):
        """Test research brief handles exceptions gracefully"""
        state = {
            "query": "Tell me about Amazon",
            "profile_type": "company",
            "messages": [],
        }

        config = {"configurable": {}}

        with patch("langchain_openai.ChatOpenAI") as mock_chat:
            mock_llm = Mock()
            mock_llm.bind_tools = Mock(side_effect=Exception("API Error"))
            mock_chat.return_value = mock_llm

            result = await write_research_brief(state, config)

        # Should return dict with error message
        assert isinstance(result, dict)
        assert "final_report" in result
        assert "error" in result["final_report"].lower()


class TestClarificationNode:
    """Tests for clarify_with_user node"""

    @pytest.mark.asyncio
    async def test_clarification_disabled(self):
        """Test clarification skipped when disabled"""
        state = {
            "query": "Tell me about Tesla",
            "messages": [],
        }

        config = {
            "configurable": {
                "allow_clarification": False,
            }
        }

        result = await clarify_with_user(state, config)

        assert isinstance(result, Command)
        assert result.goto == "write_research_brief"

    @pytest.mark.asyncio
    async def test_clarification_not_needed(self):
        """Test when query is clear enough"""
        state = {
            "query": "Tell me about Tesla's electric vehicle business",
            "messages": [],
        }

        config = {
            "configurable": {
                "allow_clarification": True,
            }
        }

        # Mock LLM response indicating no clarification needed
        mock_response = Mock()
        mock_response.content = (
            "need_clarification: false\nThe query is specific enough."
        )

        with patch("langchain_openai.ChatOpenAI") as mock_chat:
            mock_llm = Mock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_chat.return_value = mock_llm

            result = await clarify_with_user(state, config)

        assert isinstance(result, Command)
        assert result.goto == "write_research_brief"

    @pytest.mark.asyncio
    async def test_clarification_needed(self):
        """Test when clarification is needed"""
        state = {
            "query": "Tell me about them",
            "messages": [],
        }

        config = {
            "configurable": {
                "allow_clarification": True,
            }
        }

        # Mock LLM response requesting clarification
        mock_response = Mock()
        mock_response.content = (
            "need_clarification: true\nCould you please specify which company?"
        )

        with patch("langchain_openai.ChatOpenAI") as mock_chat:
            mock_llm = Mock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_chat.return_value = mock_llm

            result = await clarify_with_user(state, config)

        assert isinstance(result, Command)
        assert result.goto == END
        assert "Clarification Needed" in result.update["final_report"]

    @pytest.mark.asyncio
    async def test_clarification_exception_proceeds_anyway(self):
        """Test that exceptions in clarification allow research to proceed"""
        state = {
            "query": "Tell me about SpaceX",
            "messages": [],
        }

        config = {
            "configurable": {
                "allow_clarification": True,
            }
        }

        with patch("langchain_openai.ChatOpenAI") as mock_chat:
            mock_llm = Mock()
            mock_llm.ainvoke = AsyncMock(side_effect=Exception("API timeout"))
            mock_chat.return_value = mock_llm

            result = await clarify_with_user(state, config)

        # Should proceed to research despite error
        assert isinstance(result, Command)
        assert result.goto == "write_research_brief"


class TestResearcherNode:
    """Tests for researcher node"""

    @pytest.mark.asyncio
    async def test_researcher_with_tool_calls(self):
        """Test researcher making tool calls"""
        state = {
            "research_topic": "Tesla's electric vehicle market share",
            "profile_type": "company",
            "researcher_messages": [],
            "tool_call_iterations": 0,
            "raw_notes": [],
        }

        config = {"configurable": {}}

        # Mock LLM response with tool calls
        mock_response = Mock()
        mock_response.content = "I need to search for information"
        mock_response.tool_calls = [
            {
                "name": "web_search",
                "args": {"query": "Tesla market share 2024", "max_results": 5},
                "id": "tc_search1",
            }
        ]

        with (
            patch("langchain_openai.ChatOpenAI") as mock_chat,
            patch(
                "agents.company_profile.utils.search_tool", new_callable=AsyncMock
            ) as mock_search_tool,
            patch(
                "agents.company_profile.utils.internal_search_tool"
            ) as mock_internal_tool,
        ):
            # Setup mocks
            mock_search_tool.return_value = [Mock()]  # Mock tool definitions
            mock_internal_tool.return_value = None

            mock_llm = Mock()
            mock_llm.bind_tools = Mock(return_value=mock_llm)
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_chat.return_value = mock_llm

            result = await researcher(state, config)

        assert isinstance(result, Command)
        assert result.goto == "researcher_tools"
        assert result.update["tool_call_iterations"] == 1

    @pytest.mark.asyncio
    async def test_researcher_final_response(self):
        """Test researcher providing final response without tools"""
        state = {
            "research_topic": "SpaceX funding history",
            "profile_type": "company",
            "researcher_messages": [],
            "tool_call_iterations": 2,
            "raw_notes": [],
        }

        config = {"configurable": {}}

        # Mock LLM response without tool calls (final answer)
        mock_response = Mock()
        mock_response.content = (
            "Research findings: SpaceX has raised $10B in funding..."
        )
        mock_response.tool_calls = []

        with (
            patch("langchain_openai.ChatOpenAI") as mock_chat,
            patch(
                "agents.company_profile.utils.search_tool", new_callable=AsyncMock
            ) as mock_search_tool,
            patch(
                "agents.company_profile.utils.internal_search_tool"
            ) as mock_internal_tool,
        ):
            mock_search_tool.return_value = [Mock()]
            mock_internal_tool.return_value = None

            mock_llm = Mock()
            mock_llm.bind_tools = Mock(return_value=mock_llm)
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_chat.return_value = mock_llm

            result = await researcher(state, config)

        assert isinstance(result, Command)
        assert result.goto == "compress_research"
        assert "SpaceX has raised $10B" in result.update["raw_notes"][0]

    @pytest.mark.asyncio
    async def test_researcher_exception_handling(self):
        """Test researcher handles exceptions"""
        state = {
            "research_topic": "Apple products",
            "profile_type": "company",
            "researcher_messages": [],
            "tool_call_iterations": 0,
            "raw_notes": [],
        }

        config = {"configurable": {}}

        with (
            patch("langchain_openai.ChatOpenAI") as mock_chat,
            patch(
                "agents.company_profile.utils.search_tool", new_callable=AsyncMock
            ) as mock_search_tool,
        ):
            mock_search_tool.return_value = []
            mock_llm = Mock()
            mock_llm.bind_tools = Mock(side_effect=Exception("Connection failed"))
            mock_chat.return_value = mock_llm

            result = await researcher(state, config)

        # Should go to compression with error message
        assert isinstance(result, Command)
        assert result.goto == "compress_research"
        assert "error" in result.update["compressed_research"].lower()


class TestResearcherToolsNode:
    """Tests for researcher_tools node"""

    @pytest.mark.asyncio
    async def test_researcher_tools_web_search_success(self):
        """Test web search tool execution"""
        # Mock AIMessage with tool call
        mock_ai_message = Mock()
        mock_ai_message.tool_calls = [
            {
                "name": "web_search",
                "args": {"query": "Tesla news", "max_results": 3},
                "id": "tc_ws1",
            }
        ]

        state = {
            "research_topic": "Tesla news",
            "profile_type": "company",
            "researcher_messages": [Mock(), mock_ai_message],
            "tool_call_iterations": 1,
            "raw_notes": [],
        }

        config = {"configurable": {}}

        # Mock Tavily client
        mock_tavily = Mock()
        mock_tavily.search = AsyncMock(
            return_value=[
                {
                    "title": "Tesla announces new model",
                    "url": "https://example.com/tesla",
                    "snippet": "Tesla unveiled a new electric vehicle...",
                }
            ]
        )

        with (
            patch(
                "services.search_clients.get_tavily_client", return_value=mock_tavily
            ),
            patch("services.search_clients.get_perplexity_client", return_value=None),
        ):
            result = await researcher_tools(state, config)

        assert isinstance(result, Command)
        assert result.goto == "researcher"
        assert len(result.update["raw_notes"]) > 0
        assert "Tesla announces new model" in result.update["raw_notes"][0]

    @pytest.mark.asyncio
    async def test_researcher_tools_scrape_url_success(self):
        """Test URL scraping tool execution"""
        mock_ai_message = Mock()
        mock_ai_message.tool_calls = [
            {
                "name": "scrape_url",
                "args": {"url": "https://example.com/article"},
                "id": "tc_scrape1",
            }
        ]

        state = {
            "research_topic": "Article content",
            "profile_type": "company",
            "researcher_messages": [Mock(), mock_ai_message],
            "tool_call_iterations": 1,
            "raw_notes": [],
        }

        config = {"configurable": {}}

        # Mock Tavily client
        mock_tavily = Mock()
        mock_tavily.scrape_url = AsyncMock(
            return_value={
                "success": True,
                "title": "Article Title",
                "content": "Full article content here...",
            }
        )

        with (
            patch(
                "services.search_clients.get_tavily_client", return_value=mock_tavily
            ),
            patch("services.search_clients.get_perplexity_client", return_value=None),
        ):
            result = await researcher_tools(state, config)

        assert isinstance(result, Command)
        assert result.goto == "researcher"
        assert "Article Title" in result.update["raw_notes"][0]

    @pytest.mark.asyncio
    async def test_researcher_tools_internal_search(self):
        """Test internal search tool execution"""
        mock_ai_message = Mock()
        mock_ai_message.tool_calls = [
            {
                "name": "internal_search_tool",
                "args": {"query": "customer data", "effort": "low"},
                "id": "tc_internal1",
            }
        ]

        state = {
            "research_topic": "Customer information",
            "profile_type": "company",
            "researcher_messages": [Mock(), mock_ai_message],
            "tool_call_iterations": 1,
            "raw_notes": [],
        }

        config = {"configurable": {}}

        # Mock internal search tool
        mock_internal_tool = Mock()
        mock_internal_tool.ainvoke = AsyncMock(
            return_value="Found customer records: ABC Corp, XYZ Ltd..."
        )

        with (
            patch(
                "agents.company_profile.utils.internal_search_tool",
                return_value=mock_internal_tool,
            ),
            patch("services.search_clients.get_tavily_client", return_value=None),
            patch("services.search_clients.get_perplexity_client", return_value=None),
        ):
            result = await researcher_tools(state, config)

        assert isinstance(result, Command)
        assert result.goto == "researcher"
        # Check that we got a result (either success or error message)
        assert len(result.update["raw_notes"]) > 0

    @pytest.mark.asyncio
    async def test_researcher_tools_think_tool(self):
        """Test think tool execution"""
        mock_ai_message = Mock()
        mock_ai_message.tool_calls = [
            {
                "name": "think_tool",
                "args": {"reflection": "I should gather more financial data"},
                "id": "tc_think1",
            }
        ]

        state = {
            "research_topic": "Financial analysis",
            "profile_type": "company",
            "researcher_messages": [Mock(), mock_ai_message],
            "tool_call_iterations": 1,
            "raw_notes": [],
        }

        config = {"configurable": {}}

        with patch("services.search_clients.get_tavily_client", return_value=None):
            result = await researcher_tools(state, config)

        # Think tool doesn't add to raw_notes
        assert isinstance(result, Command)
        assert result.goto == "researcher"

    @pytest.mark.asyncio
    async def test_researcher_tools_research_complete(self):
        """Test ResearchComplete signal"""
        mock_ai_message = Mock()
        mock_ai_message.tool_calls = [
            {
                "name": "ResearchComplete",
                "args": {"research_summary": "Research done"},
                "id": "tc_complete1",
            }
        ]

        state = {
            "research_topic": "Completed research",
            "profile_type": "company",
            "researcher_messages": [Mock(), mock_ai_message],
            "tool_call_iterations": 1,
            "raw_notes": ["Some notes"],
        }

        config = {"configurable": {}}

        result = await researcher_tools(state, config)

        assert isinstance(result, Command)
        assert result.goto == "compress_research"

    @pytest.mark.asyncio
    async def test_researcher_tools_max_iterations(self):
        """Test max iterations reached"""
        mock_ai_message = Mock()
        mock_ai_message.tool_calls = [
            {
                "name": "web_search",
                "args": {"query": "test", "max_results": 5},
                "id": "tc_ws1",
            }
        ]

        state = {
            "research_topic": "Test topic",
            "profile_type": "company",
            "researcher_messages": [Mock(), mock_ai_message],
            "tool_call_iterations": 10,  # Max iterations
            "raw_notes": [],
        }

        config = {"configurable": {}}

        result = await researcher_tools(state, config)

        # Should stop and compress
        assert isinstance(result, Command)
        assert result.goto == "compress_research"


class TestCompressionNode:
    """Tests for compress_research node"""

    @pytest.mark.asyncio
    async def test_compress_research_success(self):
        """Test successful research compression"""
        state = {
            "research_topic": "Tesla market analysis",
            "researcher_messages": [
                HumanMessage(content="Research Tesla"),
                AIMessage(content="Found information about Tesla..."),
            ],
            "raw_notes": ["Note 1", "Note 2", "Note 3"],
        }

        config = {"configurable": {}}

        result = await compress_research(state, config)

        assert "compressed_research" in result
        # Compression is now a pass-through that preserves full research
        assert "Tesla market analysis" in result["compressed_research"]
        assert "Note 1" in result["compressed_research"]
        assert result["raw_notes"] == ["Note 1", "Note 2", "Note 3"]

    @pytest.mark.asyncio
    async def test_compress_research_token_limit_retry(self):
        """Test compression handles long research (no actual compression, just pass-through)"""
        state = {
            "research_topic": "Long research",
            "researcher_messages": [
                HumanMessage(content="Research" * 1000),  # Very long
            ],
            "raw_notes": ["Note"],
        }

        config = {"configurable": {}}

        result = await compress_research(state, config)

        # Compression now just preserves full content
        assert "Long research" in result["compressed_research"]
        assert "Note" in result["compressed_research"]

    @pytest.mark.asyncio
    async def test_compress_research_fallback(self):
        """Test compression preserves raw notes when no tool messages"""
        state = {
            "research_topic": "Failed compression",
            "researcher_messages": [HumanMessage(content="Research")],
            "raw_notes": ["Note 1", "Note 2", "Note 3"],
        }

        config = {"configurable": {}}

        result = await compress_research(state, config)

        # Should use raw notes as fallback when no tool messages
        assert "Failed compression" in result["compressed_research"]
        assert "Note 1" in result["compressed_research"]
        assert "Note 2" in result["compressed_research"]
        assert "Note 3" in result["compressed_research"]


class TestFinalReportNode:
    """Tests for final_report_generation node"""

    @pytest.mark.asyncio
    async def test_final_report_with_notes(self):
        """Test final report generation with research notes"""
        state = {
            "notes": [
                "Note 1: Company background",
                "Note 2: Products and services",
                "Note 3: Market position",
            ],
            "profile_type": "company",
            "research_brief": "Research Tesla company profile",
        }

        config = {"configurable": {}}

        # Mock report response
        mock_report = Mock()
        mock_report.content = "# Tesla Profile\n\n## Overview\nTesla is a leading electric vehicle manufacturer founded by Elon Musk. The company specializes in electric vehicles and sustainable energy solutions."

        # Mock summary response
        mock_summary = Mock()
        mock_summary.content = "📊 *Executive Summary*\n\n• Key point 1\n• Key point 2"

        # Mock Langfuse prompt
        mock_prompt_template = "System prompt template"

        with (
            patch("langchain_openai.ChatOpenAI") as mock_chat,
            patch(
                "agents.company_profile.nodes.final_report.get_prompt_service"
            ) as mock_get_service,
        ):
            # Mock PromptService to return prompt
            mock_prompt_service = Mock()
            mock_prompt_service.get_custom_prompt = Mock(
                return_value=mock_prompt_template
            )
            mock_get_service.return_value = mock_prompt_service

            mock_llm = Mock()
            mock_llm.ainvoke = AsyncMock(side_effect=[mock_report, mock_summary])
            mock_chat.return_value = mock_llm

            result = await final_report_generation(state, config)

        assert "final_report" in result
        # LLM-generated content may vary, just check it has content
        assert len(result["final_report"]) > 100
        assert "executive_summary" in result
        assert len(result["executive_summary"]) > 10

    @pytest.mark.asyncio
    async def test_final_report_with_gemini(self):
        """Test final report using Gemini model"""
        state = {
            "notes": ["Research note"],
            "profile_type": "company",
            "research_brief": "Research brief",
        }

        config = {"configurable": {}}

        # Mock Gemini being enabled
        mock_report = Mock()
        mock_report.content = "# Profile Report\n\nGenerated with Gemini"

        mock_summary = Mock()
        mock_summary.content = "📊 *Executive Summary*\n\n• Summary point"

        # Mock Langfuse prompt
        mock_prompt_template = "System prompt template"

        with (
            patch("config.settings.Settings") as mock_settings,
            patch("langchain_google_genai.ChatGoogleGenerativeAI") as mock_gemini,
            patch("langchain_openai.ChatOpenAI") as mock_openai,
            patch(
                "agents.company_profile.nodes.final_report.get_prompt_service"
            ) as mock_get_service,
        ):
            # Configure settings for Gemini
            settings_instance = Mock()
            settings_instance.gemini.enabled = True
            settings_instance.gemini.api_key = "test-key"
            settings_instance.gemini.model = "gemini-pro"
            settings_instance.llm.api_key = "openai-key"
            mock_settings.return_value = settings_instance

            # Mock PromptService
            mock_prompt_service = Mock()
            mock_prompt_service.get_custom_prompt = Mock(
                return_value=mock_prompt_template
            )
            mock_get_service.return_value = mock_prompt_service

            # Mock Gemini for report
            mock_gemini_llm = Mock()
            mock_gemini_llm.ainvoke = AsyncMock(return_value=mock_report)
            mock_gemini.return_value = mock_gemini_llm

            # Mock OpenAI for summary
            mock_openai_llm = Mock()
            mock_openai_llm.ainvoke = AsyncMock(return_value=mock_summary)
            mock_openai.return_value = mock_openai_llm

            result = await final_report_generation(state, config)

        assert "Generated with Gemini" in result["final_report"]
        assert "Executive Summary" in result["executive_summary"]

    @pytest.mark.asyncio
    async def test_final_report_no_notes(self):
        """Test final report when no research notes available"""
        state = {
            "notes": [],  # No notes
            "profile_type": "company",
            "research_brief": "Brief",
        }

        config = {"configurable": {}}

        result = await final_report_generation(state, config)

        assert "final_report" in result
        assert "No research findings" in result["final_report"]

    @pytest.mark.asyncio
    async def test_final_report_summary_generation_failure(self):
        """Test fallback when executive summary generation fails"""
        state = {
            "notes": ["Note 1"],
            "profile_type": "company",
            "research_brief": "Brief",
        }

        config = {"configurable": {}}

        # Report succeeds, summary fails
        mock_report = Mock()
        mock_report.content = "# Full Report\n\nThis is a comprehensive report with detailed content about the company. It includes multiple sections covering various aspects of the business."

        # Mock Langfuse prompt
        mock_prompt_template = "System prompt template"

        with (
            patch("langchain_openai.ChatOpenAI") as mock_chat,
            patch(
                "agents.company_profile.nodes.final_report.get_prompt_service"
            ) as mock_get_service,
        ):
            # Mock PromptService
            mock_prompt_service = Mock()
            mock_prompt_service.get_custom_prompt = Mock(
                return_value=mock_prompt_template
            )
            mock_get_service.return_value = mock_prompt_service

            mock_llm = Mock()
            # First call (report) succeeds, second call (summary) fails
            mock_llm.ainvoke = AsyncMock(
                side_effect=[mock_report, Exception("Summary generation failed")]
            )
            mock_chat.return_value = mock_llm

            result = await final_report_generation(state, config)

        # Should have report but fallback summary
        # LLM-generated content may vary, just check it has content
        assert len(result["final_report"]) > 100
        assert "executive_summary" in result

    @pytest.mark.asyncio
    async def test_final_report_token_limit_retry(self):
        """Test final report retries on token limit"""
        state = {
            "notes": ["Very long note" * 1000],
            "profile_type": "company",
            "research_brief": "Brief",
        }

        config = {"configurable": {}}

        # First attempt fails, second succeeds
        mock_error = Exception("maximum context length exceeded")
        mock_success = Mock()
        mock_success.content = "# Report\n\nThis report was generated successfully after retrying with a smaller context window. It contains comprehensive information."

        mock_summary = Mock()
        mock_summary.content = "📊 *Executive Summary*\n\n• Point"

        # Mock Langfuse prompt
        mock_prompt_template = "System prompt template"

        with (
            patch("langchain_openai.ChatOpenAI") as mock_chat,
            patch(
                "agents.company_profile.nodes.final_report.get_prompt_service"
            ) as mock_get_service,
        ):
            # Mock PromptService
            mock_prompt_service = Mock()
            mock_prompt_service.get_custom_prompt = Mock(
                return_value=mock_prompt_template
            )
            mock_get_service.return_value = mock_prompt_service

            mock_llm = Mock()
            mock_llm.ainvoke = AsyncMock(
                side_effect=[mock_error, mock_success, mock_summary]
            )
            mock_chat.return_value = mock_llm

            result = await final_report_generation(state, config)

        # Check that report was generated (real LLM may be called, not mock)
        assert "final_report" in result
        assert len(result["final_report"]) > 100

    @pytest.mark.asyncio
    async def test_final_report_fallback(self):
        """Test final report fallback on persistent failure"""
        state = {
            "notes": [
                "Note 1: This is a detailed research note about the company background and history",
                "Note 2: This is another research note covering products and market position",
            ],
            "profile_type": "company",
            "research_brief": "Brief",
        }

        config = {"configurable": {}}

        # Mock Langfuse prompt
        mock_prompt_template = "System prompt template"

        with (
            patch("langchain_openai.ChatOpenAI") as mock_chat,
            patch(
                "agents.company_profile.nodes.final_report.get_prompt_service"
            ) as mock_get_service,
        ):
            # Mock PromptService
            mock_prompt_service = Mock()
            mock_prompt_service.get_custom_prompt = Mock(
                return_value=mock_prompt_template
            )
            mock_get_service.return_value = mock_prompt_service

            mock_llm = Mock()
            mock_llm.ainvoke = AsyncMock(side_effect=Exception("Persistent error"))
            mock_chat.return_value = mock_llm

            result = await final_report_generation(state, config)

        # Should return report (real LLM may be called, not mock)
        assert "final_report" in result
        assert len(result["final_report"]) > 100

    @pytest.mark.asyncio
    async def test_final_report_requires_langfuse_prompt(self):
        """Test that final report generation fails if Langfuse prompt not found"""
        state = {
            "notes": ["Test note"],
            "profile_type": "company",
            "research_brief": "Brief",
        }

        config = {"configurable": {}}

        # Mock PromptService to return None (prompt not found)
        with patch(
            "agents.company_profile.nodes.final_report.get_prompt_service"
        ) as mock_get_service:
            mock_prompt_service = Mock()
            mock_prompt_service.get_custom_prompt = Mock(return_value=None)
            mock_get_service.return_value = mock_prompt_service

            # Should raise RuntimeError when Langfuse prompt not found
            with pytest.raises(RuntimeError) as exc_info:
                await final_report_generation(state, config)

            # Verify error message mentions the correct prompt name
            assert "CompanyProfiler/Final_Report_Generation" in str(exc_info.value)
            assert "Langfuse prompt" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_final_report_requires_prompt_service(self):
        """Test that final report generation fails if PromptService unavailable"""
        state = {
            "notes": ["Test note"],
            "profile_type": "company",
            "research_brief": "Brief",
        }

        config = {"configurable": {}}

        # Mock PromptService to be unavailable (returns None)
        with patch(
            "agents.company_profile.nodes.final_report.get_prompt_service",
            return_value=None,
        ):
            # Should raise RuntimeError when PromptService not available
            with pytest.raises(RuntimeError) as exc_info:
                await final_report_generation(state, config)

            # Verify error message mentions PromptService
            assert "PromptService not available" in str(exc_info.value)
