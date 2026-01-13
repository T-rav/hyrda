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

    # Mock LLM with JSON response
    mock_llm_response = MagicMock()
    mock_llm_response.content = '{"intent": "continue", "message": "Costco\'s revenue model consists of membership fees and bulk product sales, with membership fees providing recurring revenue."}'

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

    # Verify response with new fields
    assert "Costco's revenue model" in result["message"]
    assert result["attachments"] == []
    assert result["followup_mode"] == True  # Intent was "continue"
    assert len(result["conversation_history"]) == 2  # User + assistant

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


@pytest.mark.asyncio
async def test_intent_detection_exit():
    """Test that answer_question detects exit intent and sets followup_mode=False."""
    state: ProfileAgentState = {
        "query": "thanks, that's all I needed!",
        "final_report": "# Test Report",
        "focus_area": "",
    }

    # Mock LLM with exit intent
    mock_llm_response = MagicMock()
    mock_llm_response.content = '{"intent": "exit", "message": "You\'re welcome! Feel free to ask if you need anything else."}'

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

    # Verify exit intent detected
    assert result["followup_mode"] == False  # Should exit follow-up mode
    assert "welcome" in result["message"].lower()


@pytest.mark.asyncio
async def test_conversation_history_tracking():
    """Test that conversation history is tracked across multiple turns."""
    # Initial state with existing conversation
    state: ProfileAgentState = {
        "query": "what about their AI strategy?",
        "final_report": "# Test Report\n\n## AI Strategy\nFocused on machine learning.",
        "focus_area": "",
        "conversation_history": [
            {"role": "user", "content": "what is their revenue?"},
            {"role": "assistant", "content": "Their revenue is $100M."},
        ],
    }

    # Mock LLM
    mock_llm_response = MagicMock()
    mock_llm_response.content = '{"intent": "continue", "message": "Their AI strategy focuses on machine learning applications."}'

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

    # Verify conversation history updated
    assert len(result["conversation_history"]) == 4  # 2 existing + 2 new
    assert result["conversation_history"][2]["role"] == "user"
    assert result["conversation_history"][2]["content"] == "what about their AI strategy?"
    assert result["conversation_history"][3]["role"] == "assistant"

    # Verify history was included in prompt
    call_args = mock_llm.ainvoke.call_args[0][0]
    system_prompt = str(call_args[0])
    assert "RECENT CONVERSATION" in system_prompt or "what is their revenue" in system_prompt


@pytest.mark.asyncio
async def test_conversation_summarization():
    """Test that conversation history is summarized when it exceeds 20 messages."""
    # Create a long conversation history (22 messages = 11 turns)
    long_history = []
    for i in range(11):
        long_history.append({"role": "user", "content": f"Question {i}"})
        long_history.append({"role": "assistant", "content": f"Answer {i}"})

    state: ProfileAgentState = {
        "query": "one more question",
        "final_report": "# Test Report",
        "focus_area": "",
        "conversation_history": long_history,
    }

    # Mock LLM responses (one for answer, one for summary)
    mock_answer_response = MagicMock()
    mock_answer_response.content = '{"intent": "continue", "message": "Here is the answer."}'

    mock_summary_response = MagicMock()
    mock_summary_response.content = "Summary of questions 0-5: Topics A, B, and C were discussed."

    mock_llm = AsyncMock()
    # First call is for answering, second call is for summarization
    mock_llm.ainvoke = AsyncMock(side_effect=[mock_answer_response, mock_summary_response])

    # Mock Settings
    mock_settings = MagicMock()
    mock_settings.gemini.enabled = False
    mock_settings.llm.model = "gpt-4o"
    mock_settings.llm.api_key = "test-key"

    from unittest.mock import patch

    with patch("config.settings.Settings", return_value=mock_settings):
        with patch("langchain_openai.ChatOpenAI", return_value=mock_llm):
            result = await answer_question(state, config={})

    # Verify summarization occurred
    assert "conversation_summary" in result
    assert "Summary" in result["conversation_summary"]
    # History should be trimmed: 22 original - 12 summarized = 10 kept + 2 new = 12 total
    assert len(result["conversation_history"]) == 12

    # Verify summarization was called
    assert mock_llm.ainvoke.call_count == 2  # Once for answer, once for summary


@pytest.mark.asyncio
async def test_conversation_context_in_prompt():
    """Test that conversation summary and history are included in prompt."""
    state: ProfileAgentState = {
        "query": "follow-up question",
        "final_report": "# Test Report",
        "focus_area": "",
        "conversation_history": [
            {"role": "user", "content": "previous question"},
            {"role": "assistant", "content": "previous answer"},
        ],
        "conversation_summary": "Earlier we discussed topic X and Y.",
    }

    # Mock LLM
    mock_llm_response = MagicMock()
    mock_llm_response.content = '{"intent": "continue", "message": "Answer to follow-up."}'

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

    # Verify both summary and history were included in prompt
    call_args = mock_llm.ainvoke.call_args[0][0]
    system_prompt = str(call_args[0])
    assert "CONVERSATION SUMMARY" in system_prompt
    assert "Earlier we discussed topic X and Y" in system_prompt
    assert "RECENT CONVERSATION" in system_prompt
    assert "previous question" in system_prompt
