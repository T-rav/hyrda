"""Unit tests for answer_question node."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from ..nodes.answer_question import answer_question
from ..state import ProfileAgentState


@pytest.mark.asyncio
async def test_answer_question_with_report():
    """Test that answer_question uses final_report to answer question."""
    # Mock state with existing report
    state: ProfileAgentState = {
        "query": "what is their revenue model?",
        "final_report": """# Costco - Company Profile

## Revenue Model
Costco generates revenue through membership fees and product sales.
Their membership model creates recurring revenue streams.

## Business Strategy
Focus on bulk sales and warehouse format.""",
        "focus_area": "",
    }

    # Mock LLM
    mock_llm_response = MagicMock()
    mock_llm_response.content = "Costco's revenue model consists of membership fees and bulk product sales, with membership fees providing recurring revenue."

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

    # Mock Settings to avoid env var requirements
    mock_settings = MagicMock()
    mock_settings.gemini.enabled = False
    mock_settings.llm.model = "gpt-4o"
    mock_settings.llm.api_key = "test-key"

    # Mock LLM initialization
    from unittest.mock import patch

    with patch("config.settings.Settings", return_value=mock_settings):
        with patch("langchain_openai.ChatOpenAI", return_value=mock_llm):
            result = await answer_question(state, config={})

    # Verify response
    assert result["message"] == mock_llm_response.content
    assert result["attachments"] == []

    # Verify LLM was called with report context
    call_args = mock_llm.ainvoke.call_args[0][0]
    assert len(call_args) == 2  # system + user message
    assert "Costco - Company Profile" in str(call_args[0])  # Report in system message
    assert "what is their revenue model" in str(call_args[1])  # Question in user message


@pytest.mark.asyncio
async def test_answer_question_without_report():
    """Test that answer_question returns error when no report exists."""
    # Mock state without report
    state: ProfileAgentState = {
        "query": "what is their revenue model?",
        "final_report": "",  # No report
        "focus_area": "",
    }

    result = await answer_question(state, config={})

    # Verify error response
    assert "don't have a profile report" in result["message"]
    assert "❌" in result["message"]


@pytest.mark.asyncio
async def test_answer_question_with_focus_area():
    """Test that answer_question includes focus_area in prompt."""
    state: ProfileAgentState = {
        "query": "tell me more about their AI strategy",
        "final_report": """# Company Profile

## Technology
Uses AI for inventory management and customer analytics.""",
        "focus_area": "AI capabilities",
    }

    # Mock LLM
    mock_llm_response = MagicMock()
    mock_llm_response.content = "The company uses AI for inventory and customer analytics."

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

    # Mock Settings
    mock_settings = MagicMock()
    mock_settings.gemini.enabled = False
    mock_settings.llm.model = "gpt-4o"
    mock_settings.llm.api_key = "test-key"

    from unittest.mock import patch

    with patch("config.settings.Settings", return_value=mock_settings):
        with patch("langchain_openai.ChatOpenAI", return_value=mock_llm):
            result = await answer_question(state, config={})

    # Verify focus_area was included in prompt
    call_args = mock_llm.ainvoke.call_args[0][0]
    assert "AI capabilities" in str(call_args[0])


@pytest.mark.asyncio
async def test_answer_question_handles_llm_error():
    """Test that answer_question handles LLM errors gracefully."""
    state: ProfileAgentState = {
        "query": "test question",
        "final_report": "# Test Report",
        "focus_area": "",
    }

    # Mock LLM that raises error
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(side_effect=Exception("API timeout"))

    # Mock Settings
    mock_settings = MagicMock()
    mock_settings.gemini.enabled = False
    mock_settings.llm.model = "gpt-4o"
    mock_settings.llm.api_key = "test-key"

    from unittest.mock import patch

    with patch("config.settings.Settings", return_value=mock_settings):
        with patch("langchain_openai.ChatOpenAI", return_value=mock_llm):
            result = await answer_question(state, config={})

    # Verify error message returned
    assert "❌" in result["message"]
    assert "Failed to answer question" in result["message"]


@pytest.mark.asyncio
async def test_answer_question_uses_gemini_if_available():
    """Test that answer_question prefers Gemini if configured."""
    state: ProfileAgentState = {
        "query": "test question",
        "final_report": "# Test Report",
        "focus_area": "",
    }

    # Mock successful Gemini response
    mock_gemini_response = MagicMock()
    mock_gemini_response.content = "Answer from Gemini"

    mock_gemini = AsyncMock()
    mock_gemini.ainvoke = AsyncMock(return_value=mock_gemini_response)

    from unittest.mock import patch

    # Mock settings to enable Gemini
    mock_settings = MagicMock()
    mock_settings.gemini.enabled = True
    mock_settings.gemini.api_key = "test-key"
    mock_settings.gemini.model = "gemini-2.0-flash"

    with patch("config.settings.Settings", return_value=mock_settings):
        with patch(
            "langchain_google_genai.ChatGoogleGenerativeAI",
            return_value=mock_gemini,
        ):
            result = await answer_question(state, config={})

    # Verify Gemini was used
    assert result["message"] == "Answer from Gemini"
    assert mock_gemini.ainvoke.called
