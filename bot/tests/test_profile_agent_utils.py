"""Tests for ProfileAgent utility functions."""

import os
import sys
from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.profile_agent import format_duration
from agents.profiler.utils import (
    compress_message_if_needed,
    create_human_message,
    create_system_message,
    detect_profile_type,
    estimate_tokens,
    extract_focus_area,
    format_research_context,
    is_token_limit_exceeded,
    remove_up_to_last_ai_message,
    select_messages_within_budget,
    think_tool,
)


class TestDetectProfileType:
    """Tests for detect_profile_type function"""

    @pytest.mark.asyncio
    async def test_detect_company_profile(self):
        """Test detecting company profile"""
        from unittest.mock import AsyncMock, patch

        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = Mock(
            content='{"profile_type": "company", "confidence": "high", "reasoning": "Corporate entity"}'
        )

        with (
            patch("langchain_openai.ChatOpenAI", return_value=mock_llm),
            patch("config.settings.Settings"),
        ):
            result = await detect_profile_type("Tell me about Tesla")
            assert result == "company"

    @pytest.mark.asyncio
    async def test_detect_employee_profile(self):
        """Test detecting employee/person profile"""
        from unittest.mock import AsyncMock, patch

        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = Mock(
            content='{"profile_type": "employee", "confidence": "high", "reasoning": "Personal name"}'
        )

        with (
            patch("langchain_openai.ChatOpenAI", return_value=mock_llm),
            patch("config.settings.Settings"),
        ):
            result = await detect_profile_type("profile Travis Frisinger")
            assert result == "employee"

    @pytest.mark.asyncio
    async def test_detect_with_empty_query(self):
        """Test with empty query defaults to company"""
        from unittest.mock import AsyncMock, patch

        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = Mock(
            content='{"profile_type": "company", "confidence": "low", "reasoning": "Empty query"}'
        )

        with (
            patch("langchain_openai.ChatOpenAI", return_value=mock_llm),
            patch("config.settings.Settings"),
        ):
            result = await detect_profile_type("")
            assert result == "company"

    @pytest.mark.asyncio
    async def test_detect_invalid_profile_type_defaults_to_company(self):
        """Test that invalid profile types default to company"""
        from unittest.mock import AsyncMock, patch

        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = Mock(
            content='{"profile_type": "invalid_type", "confidence": "low", "reasoning": "Unknown"}'
        )

        with (
            patch("langchain_openai.ChatOpenAI", return_value=mock_llm),
            patch("config.settings.Settings"),
        ):
            result = await detect_profile_type("something random")
            assert result == "company"

    @pytest.mark.asyncio
    async def test_detect_json_parse_error_defaults_to_company(self):
        """Test that JSON parse errors default to company"""
        from unittest.mock import AsyncMock, patch

        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = Mock(content="Not valid JSON")

        with (
            patch("langchain_openai.ChatOpenAI", return_value=mock_llm),
            patch("config.settings.Settings"),
        ):
            result = await detect_profile_type("some query")
            assert result == "company"

    @pytest.mark.asyncio
    async def test_detect_exception_defaults_to_company(self):
        """Test that exceptions default to company"""
        from unittest.mock import AsyncMock, patch

        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = Exception("LLM error")

        with (
            patch("langchain_openai.ChatOpenAI", return_value=mock_llm),
            patch("config.settings.Settings"),
        ):
            result = await detect_profile_type("some query")
            assert result == "company"


class TestFormatDuration:
    """Tests for format_duration function"""

    def test_format_seconds(self):
        """Test formatting seconds"""
        assert format_duration(5.2) == "5.2s"
        assert format_duration(45.7) == "45.7s"
        assert format_duration(0.5) == "0.5s"

    def test_format_minutes(self):
        """Test formatting minutes"""
        assert format_duration(65.0) == "1m 5s"
        assert format_duration(120.0) == "2m 0s"
        assert format_duration(150.5) == "2m 30s"

    def test_format_hours(self):
        """Test formatting hours"""
        assert format_duration(3661.5) == "1h 1m 1s"  # int truncates to 1s
        assert format_duration(7200.0) == "2h 0m 0s"
        assert format_duration(3725.0) == "1h 2m 5s"

    def test_format_edge_cases(self):
        """Test edge cases"""
        assert format_duration(0) == "0.0s"
        assert format_duration(59.9) == "59.9s"
        assert format_duration(60.0) == "1m 0s"
        assert format_duration(3600.0) == "1h 0m 0s"


class TestFormatResearchContext:
    """Tests for format_research_context function"""

    @pytest.mark.asyncio
    async def test_format_with_notes(self):
        """Test formatting with research notes"""
        research_brief = "Research Tesla's electric vehicles"
        notes = ["Note 1: Market share data", "Note 2: Product lineup"]
        profile_type = "company"

        result = await format_research_context(research_brief, notes, profile_type)

        assert "Profile Research Context" in result
        assert "company" in result
        assert "Research Tesla's electric vehicles" in result
        assert "Note 1: Market share data" in result
        assert "Note 2: Product lineup" in result
        assert "Finding 1" in result
        assert "Finding 2" in result

    @pytest.mark.asyncio
    async def test_format_with_empty_notes(self):
        """Test formatting with no notes"""
        research_brief = "Research brief"
        notes = []
        profile_type = "company"

        result = await format_research_context(research_brief, notes, profile_type)

        assert "Profile Research Context" in result
        assert "0 sections" in result

    @pytest.mark.asyncio
    async def test_format_with_many_notes(self):
        """Test formatting with many notes"""
        research_brief = "Brief"
        notes = [f"Note {i}" for i in range(1, 11)]
        profile_type = "company"

        result = await format_research_context(research_brief, notes, profile_type)

        assert "10 sections" in result
        for i in range(1, 11):
            assert f"Finding {i}" in result


class TestIsTokenLimitExceeded:
    """Tests for is_token_limit_exceeded function"""

    def test_openai_token_limit_patterns(self):
        """Test OpenAI token limit error detection"""
        errors = [
            Exception("maximum context length exceeded"),
            Exception("context_length_exceeded for model gpt-4"),
            Exception("tokens exceed the limit"),
            Exception("Request has too many tokens"),
        ]

        for error in errors:
            assert is_token_limit_exceeded(error, "gpt-4") is True

    def test_anthropic_token_limit_patterns(self):
        """Test Anthropic token limit error detection"""
        errors = [
            Exception("prompt is too long"),
            Exception("maximum context size reached"),
            Exception("context length exceeded"),
        ]

        for error in errors:
            assert is_token_limit_exceeded(error, "claude-3") is True

    def test_non_token_errors(self):
        """Test non-token-limit errors are not detected"""
        errors = [
            Exception("API rate limit exceeded"),
            Exception("Invalid API key"),
            Exception("Network timeout"),
            Exception("Model not found"),
        ]

        for error in errors:
            assert is_token_limit_exceeded(error, "gpt-4") is False

    def test_case_insensitive(self):
        """Test detection is case-insensitive"""
        error = Exception("Maximum Context Length Exceeded")
        assert is_token_limit_exceeded(error, "gpt-4") is True


class TestRemoveUpToLastAiMessage:
    """Tests for remove_up_to_last_ai_message function"""

    def test_remove_up_to_last_ai(self):
        """Test removing messages up to last AI message"""
        messages = [
            SystemMessage(content="System"),
            HumanMessage(content="Human 1"),
            AIMessage(content="AI 1"),
            HumanMessage(content="Human 2"),
            AIMessage(content="AI 2"),
            HumanMessage(content="Human 3"),
        ]

        result = remove_up_to_last_ai_message(messages)

        assert len(result) == 1
        assert result[0].content == "Human 3"

    def test_no_ai_messages(self):
        """Test with no AI messages (removes first half)"""
        messages = [
            HumanMessage(content="Human 1"),
            HumanMessage(content="Human 2"),
            HumanMessage(content="Human 3"),
            HumanMessage(content="Human 4"),
        ]

        result = remove_up_to_last_ai_message(messages)

        assert len(result) == 2
        assert result[0].content == "Human 3"

    def test_only_ai_messages(self):
        """Test with only AI messages"""
        messages = [
            AIMessage(content="AI 1"),
            AIMessage(content="AI 2"),
        ]

        result = remove_up_to_last_ai_message(messages)

        # Should keep nothing after last AI message
        assert len(result) == 0

    def test_single_message(self):
        """Test with single message"""
        messages = [HumanMessage(content="Only message")]

        result = remove_up_to_last_ai_message(messages)

        # With 1 message, midpoint is 0, so returns messages[0:] = full list
        assert len(result) == 1


class TestEstimateTokens:
    """Tests for estimate_tokens function"""

    def test_estimate_short_text(self):
        """Test estimating tokens for short text"""
        text = "Hello world"
        tokens = estimate_tokens(text)
        assert tokens == len(text) // 4

    def test_estimate_long_text(self):
        """Test estimating tokens for long text"""
        text = "a" * 10000
        tokens = estimate_tokens(text)
        assert tokens == 2500  # 10000 / 4

    def test_estimate_empty_text(self):
        """Test estimating tokens for empty text"""
        assert estimate_tokens("") == 0

    def test_estimate_with_spaces(self):
        """Test estimating with spaces"""
        text = "This is a test message with multiple words"
        tokens = estimate_tokens(text)
        assert tokens == len(text) // 4


class TestCompressMessageIfNeeded:
    """Tests for compress_message_if_needed function"""

    def test_no_compression_needed(self):
        """Test message under budget is not compressed"""
        message = HumanMessage(content="Short message")
        result = compress_message_if_needed(message, max_tokens=100)
        assert result == "Short message"

    def test_tool_message_compression(self):
        """Test tool message compression keeps beginning and end"""
        content = "A" * 10000
        message = ToolMessage(content=content, tool_call_id="tc_1")
        result = compress_message_if_needed(message, max_tokens=500)

        assert len(result) < len(content)
        assert "[compressed" in result
        assert result.startswith("A")
        assert result.endswith("A")

    def test_ai_message_compression(self):
        """Test AI message compression"""
        content = "B" * 10000
        message = AIMessage(content=content)
        result = compress_message_if_needed(message, max_tokens=500)

        assert len(result) < len(content)
        assert "[compressed" in result

    def test_compression_with_cache(self):
        """Test compression uses cache"""
        content = "C" * 10000
        message = HumanMessage(content=content)
        cache = {}

        # First compression
        result1 = compress_message_if_needed(
            message, max_tokens=500, compression_cache=cache
        )
        assert len(cache) == 1

        # Second compression should use cache
        result2 = compress_message_if_needed(
            message, max_tokens=500, compression_cache=cache
        )
        assert result1 == result2
        assert len(cache) == 1  # No new cache entries

    def test_string_message_compression(self):
        """Test compressing plain strings"""
        content = "D" * 10000
        result = compress_message_if_needed(content, max_tokens=500)

        assert len(result) < len(content)
        assert "[compressed" in result


class TestSelectMessagesWithinBudget:
    """Tests for select_messages_within_budget function"""

    def test_select_all_messages_within_budget(self):
        """Test all messages fit within budget"""
        messages = [
            HumanMessage(content="Message 1"),
            AIMessage(content="Response 1"),
            HumanMessage(content="Message 2"),
        ]

        result = select_messages_within_budget(messages, max_tokens=10000)

        assert "Message 1" in result
        assert "Response 1" in result
        assert "Message 2" in result

    def test_select_recent_messages_when_exceeding_budget(self):
        """Test only recent messages selected when budget exceeded"""
        messages = [
            HumanMessage(content="A" * 1000),
            AIMessage(content="B" * 1000),
            HumanMessage(content="C" * 1000),
            AIMessage(content="D" * 1000),
        ]

        # Very small budget
        result = select_messages_within_budget(messages, max_tokens=100)

        # Should prioritize recent messages
        assert len(result) > 0

    def test_select_with_compression(self):
        """Test message compression during selection"""
        messages = [
            HumanMessage(content="X" * 10000),
            AIMessage(content="Y" * 10000),
        ]

        cache = {}
        result = select_messages_within_budget(
            messages, max_tokens=5000, compression_cache=cache
        )

        # Messages should be compressed to fit
        assert "[compressed" in result

    def test_select_empty_messages(self):
        """Test with no messages"""
        messages = []
        result = select_messages_within_budget(messages, max_tokens=1000)
        assert result == ""


class TestCreateMessages:
    """Tests for message creation utilities"""

    def test_create_system_message(self):
        """Test creating system message"""
        prompt = "You are a helpful assistant. Task: {task}"
        message = create_system_message(prompt, task="research")

        assert isinstance(message, SystemMessage)
        assert message.content == "You are a helpful assistant. Task: research"

    def test_create_system_message_no_formatting(self):
        """Test creating system message without formatting"""
        prompt = "Simple prompt"
        message = create_system_message(prompt)

        assert isinstance(message, SystemMessage)
        assert message.content == "Simple prompt"

    def test_create_human_message(self):
        """Test creating human message"""
        content = "Hello, AI!"
        message = create_human_message(content)

        assert isinstance(message, HumanMessage)
        assert message.content == "Hello, AI!"


class TestThinkTool:
    """Tests for think_tool"""

    def test_think_tool_execution(self):
        """Test think tool records reflection"""
        reflection = "I should search for more recent data"
        result = think_tool.invoke({"reflection": reflection})

        assert "Reflection recorded" in result
        assert reflection in result

    def test_think_tool_with_long_reflection(self):
        """Test think tool with long reflection"""
        reflection = "A" * 500
        result = think_tool.invoke({"reflection": reflection})

        assert "Reflection recorded" in result

    def test_think_tool_schema(self):
        """Test think tool has proper schema"""
        assert think_tool.name == "think_tool"
        assert "reflection" in str(think_tool.args_schema.model_json_schema())


class TavilyClientMockFactory:
    """Factory for creating Tavily client mocks"""

    @staticmethod
    def create_successful_scraper(content: str = "Default content") -> Mock:
        """Create Tavily client mock that successfully scrapes URLs"""
        from unittest.mock import AsyncMock, Mock

        mock_tavily = Mock()
        mock_tavily.scrape_url = AsyncMock(
            return_value={"success": True, "content": content}
        )
        return mock_tavily

    @staticmethod
    def create_failing_scraper(error: str = "Scraping failed") -> Mock:
        """Create Tavily client mock that fails to scrape"""
        from unittest.mock import AsyncMock, Mock

        mock_tavily = Mock()
        mock_tavily.scrape_url = AsyncMock(side_effect=Exception(error))
        return mock_tavily


class ChatOpenAIMockFactory:
    """Factory for creating ChatOpenAI mocks"""

    @staticmethod
    def create_with_response(response_content: str) -> Mock:
        """Create ChatOpenAI mock with a single response"""
        from unittest.mock import AsyncMock, Mock

        mock_response = Mock()
        mock_response.content = response_content

        mock_llm = Mock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        return mock_llm

    @staticmethod
    def create_with_multiple_responses(responses: list[str]) -> Mock:
        """Create ChatOpenAI mock with multiple sequential responses"""
        from unittest.mock import AsyncMock, Mock

        mock_responses = [Mock(content=content) for content in responses]

        mock_llm = Mock()
        mock_llm.ainvoke = AsyncMock(side_effect=mock_responses)
        return mock_llm


class TestExtractFocusArea:
    """Tests for extract_focus_area function with URL scraping"""

    @pytest.mark.asyncio
    async def test_extract_focus_area_no_url(self):
        """Test focus area extraction without URLs"""
        from unittest.mock import patch

        mock_llm = ChatOpenAIMockFactory.create_with_response(
            '{"focus_area": "AI needs and capabilities", "url_context": ""}'
        )

        with patch("langchain_openai.ChatOpenAI", return_value=mock_llm):
            result = await extract_focus_area("profile tesla's ai needs")

        assert result == "AI needs and capabilities"
        # Should not attempt to scrape URLs
        mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_focus_area_with_url_scraping(self):
        """Test focus area extraction with URL scraping and summarization"""
        from unittest.mock import patch

        # Create mocks using factories
        mock_tavily = TavilyClientMockFactory.create_successful_scraper(
            "Aspenware is a TravelTech platform. We helped them implement AI-driven data enrichment for e-commerce."
        )

        mock_llm = ChatOpenAIMockFactory.create_with_multiple_responses(
            [
                "Aspenware case study: AI-driven enrichment pipeline for TravelTech e-commerce platform.",
                '{"focus_area": "AI-driven enrichment strategies for e-commerce", "url_context": "Aspenware case study context"}',
            ]
        )

        with (
            patch(
                "services.search_clients.get_tavily_client", return_value=mock_tavily
            ),
            patch("langchain_openai.ChatOpenAI", return_value=mock_llm),
        ):
            result = await extract_focus_area(
                "profile Vail Resorts and https://example.com/case-study"
            )

        assert result == "AI-driven enrichment strategies for e-commerce"
        # Should scrape URL
        mock_tavily.scrape_url.assert_called_once_with("https://example.com/case-study")
        # Should call LLM twice (summary + extraction)
        assert mock_llm.ainvoke.call_count == 2
