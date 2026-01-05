"""Test MEDDPICC Q&A flow.

Verify that the question loop properly collects answers and builds a report.
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock the problematic langgraph.checkpoint.sqlite module before imports
sys.modules["langgraph.checkpoint.sqlite"] = MagicMock()
sys.modules["langgraph.checkpoint.sqlite.aio"] = MagicMock()

from agents.meddic_agent import MeddicAgent  # noqa: E402
from agents.meddpicc_coach.nodes.qa_collector import (  # noqa: E402
    MEDDPICC_QUESTIONS,
    qa_collector,
)
from agents.meddpicc_coach.state import MeddpiccAgentState  # noqa: E402


class AsyncIterator:
    """Helper to create async iterator for mocking."""

    def __init__(self, items):
        self.items = items
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        return item


@pytest.mark.asyncio
async def test_qa_collector_starts_with_no_query():
    """Test that qa_collector starts Q&A mode when no query provided."""
    state: MeddpiccAgentState = {
        "query": "",
        "question_mode": False,
        "current_question_index": 0,
        "gathered_answers": {},
    }

    result = await qa_collector(state, {})

    assert result["question_mode"] is True
    assert result["current_question_index"] == 1
    assert "Question 1/8" in result["final_response"]
    assert "company" in result["final_response"].lower()


@pytest.mark.asyncio
async def test_qa_collector_stores_answers():
    """Test that qa_collector stores answers and progresses."""
    state: MeddpiccAgentState = {
        "query": "Acme Corp",
        "question_mode": True,
        "current_question_index": 1,
        "gathered_answers": {},
    }

    result = await qa_collector(state, {})

    # Should store the answer
    assert result["gathered_answers"]["company"] == "Acme Corp"
    # Should ask next question
    assert result["current_question_index"] == 2
    assert "Question 2/8" in result["final_response"]


@pytest.mark.asyncio
async def test_qa_collector_compiles_notes_after_all_questions():
    """Test that qa_collector compiles notes after all 8 questions."""
    state: MeddpiccAgentState = {
        "query": "Status quo",
        "question_mode": True,
        "current_question_index": 8,  # Last question
        "gathered_answers": {
            "company": "Acme Corp",
            "pain": "Slow reporting",
            "metrics": "Save 10 hours per week",
            "buyer": "CTO Sarah",
            "criteria": "ROI proof",
            "process": "Pilot in Q1",
            "champion": "Bob from analytics",
        },
    }

    result = await qa_collector(state, {})

    # Should exit Q&A mode
    assert result["question_mode"] is False
    assert result["current_question_index"] == 0
    # Should have compiled notes
    assert "Acme Corp" in result["query"]
    assert "Slow reporting" in result["query"]
    assert result["raw_notes"] == result["query"]


@pytest.mark.asyncio
async def test_qa_collector_handles_skip_answers():
    """Test that qa_collector filters out 'skip' answers."""
    state: MeddpiccAgentState = {
        "query": "skip",
        "question_mode": True,
        "current_question_index": 8,
        "gathered_answers": {
            "company": "Acme Corp",
            "pain": "skip",
            "metrics": "idk",
            "buyer": "i don't know",
            "criteria": "skip",
            "process": "skip",
            "champion": "skip",
        },
    }

    result = await qa_collector(state, {})

    # Should compile notes without skipped items
    assert "Acme Corp" in result["query"]
    assert "skip" not in result["query"].lower()


@pytest.mark.asyncio
async def test_meddic_agent_no_notes_starts_qa():
    """Test that MeddicAgent with no notes starts Q&A mode."""
    agent = MeddicAgent()

    mock_slack = AsyncMock()
    mock_slack.send_message = AsyncMock(return_value={"ts": "123"})
    mock_slack.update_message = AsyncMock()
    mock_slack.delete_thinking_indicator = AsyncMock()

    context = {
        "user_id": "U123",
        "channel": "C123",
        "thread_ts": "1234567890.123456",
        "slack_service": mock_slack,
        "llm_service": AsyncMock(),
    }

    # Run the real workflow - should trigger Q&A mode
    result = await agent.run("", context)

    # Should return question (Q&A mode activated)
    assert result["metadata"]["question_mode"] is True
    assert "Question 1/8" in result["response"]
    assert "company" in result["response"].lower()


@pytest.mark.asyncio
async def test_meddic_agent_with_notes_skips_qa():
    """Test that MeddicAgent with notes skips Q&A and goes to analysis."""
    agent = MeddicAgent()

    mock_slack = AsyncMock()
    mock_slack.send_message = AsyncMock(return_value={"ts": "123"})
    mock_slack.update_message = AsyncMock()
    mock_slack.delete_thinking_indicator = AsyncMock()

    context = {
        "user_id": "U123",
        "channel": "C123",
        "thread_ts": "9999999999.999999",  # Different thread to avoid state contamination
        "thinking_ts": "123",
        "slack_service": mock_slack,
        "llm_service": AsyncMock(),
    }

    # Call with actual notes
    query = "Spoke with Bob at Acme Corp. They need better reporting. Budget is $50K."

    # Mock the LLM calls to avoid actual API calls
    with patch("agents.meddpicc_coach.nodes.parse_notes.ChatOpenAI") as mock_parse_llm:
        mock_parse_response = MagicMock()
        mock_parse_response.content = query  # Return cleaned notes
        mock_parse_llm.return_value.ainvoke = AsyncMock(
            return_value=mock_parse_response
        )

        with patch(
            "agents.meddpicc_coach.nodes.meddpicc_analysis.ChatOpenAI"
        ) as mock_analysis_llm:
            mock_analysis_response = MagicMock()
            mock_analysis_response.content = (
                "**M - Metrics:** $50K budget\n**E - Economic Buyer:** Bob"
            )
            mock_analysis_llm.return_value.ainvoke = AsyncMock(
                return_value=mock_analysis_response
            )

            with patch(
                "agents.meddpicc_coach.nodes.coaching_insights.ChatOpenAI"
            ) as mock_coaching_llm:
                mock_coaching_response = MagicMock()
                mock_coaching_response.content = (
                    "Great work! Focus on the Economic Buyer..."
                )
                mock_coaching_llm.return_value.ainvoke = AsyncMock(
                    return_value=mock_coaching_response
                )

                # Run the real workflow
                result = await agent.run(query, context)

    # Should NOT be in question mode
    assert result["metadata"].get("question_mode") is not True
    # Should have analysis in response
    assert "response" in result
    assert len(result["response"]) > 0


def test_meddpicc_questions_count():
    """Test that we have exactly 8 MEDDPICC questions."""
    assert len(MEDDPICC_QUESTIONS) == 8

    # Verify all MEDDPICC elements are covered
    keys = [q[0] for q in MEDDPICC_QUESTIONS]
    assert "company" in keys
    assert "pain" in keys
    assert "metrics" in keys
    assert "buyer" in keys
    assert "criteria" in keys
    assert "process" in keys
    assert "champion" in keys
    assert "competition" in keys


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
