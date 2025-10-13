"""Test MEDDPICC follow-up questions flow.

Verify that the follow-up handler properly detects intent and routes accordingly.
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock the problematic langgraph.checkpoint.sqlite module before imports
sys.modules["langgraph.checkpoint.sqlite"] = MagicMock()
sys.modules["langgraph.checkpoint.sqlite.aio"] = MagicMock()

from agents.meddpicc_coach.nodes.followup_handler import followup_handler  # noqa: E402
from agents.meddpicc_coach.nodes.graph_builder import build_meddpicc_coach  # noqa: E402
from agents.meddpicc_coach.state import MeddpiccAgentState  # noqa: E402


@pytest.mark.asyncio
async def test_followup_handler_stays_for_meddpicc_question():
    """Test that MEDDPICC methodology questions keep follow-up mode active."""
    with patch("agents.meddpicc_coach.nodes.followup_handler.ChatOpenAI") as mock_llm:
        # Mock LLM response for MEDDPICC question (stays in mode)
        mock_response = MagicMock()
        mock_response.content = (
            "Great question! The Economic Buyer is the person who..."
        )
        mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)

        state: MeddpiccAgentState = {
            "query": "What does Economic Buyer mean?",
            "followup_mode": True,
            "original_analysis": "**M - Metrics:** ...",
        }

        result = await followup_handler(state, {})

        assert result["followup_mode"] is True
        assert "Economic Buyer" in result["final_response"]
        assert not result["final_response"].startswith("EXIT_FOLLOWUP_MODE:")


@pytest.mark.asyncio
async def test_followup_handler_stays_for_analysis_modification():
    """Test that requests to modify analysis keep follow-up mode active."""
    with patch("agents.meddpicc_coach.nodes.followup_handler.ChatOpenAI") as mock_llm:
        # Mock LLM response for modification request (stays in mode)
        mock_response = MagicMock()
        mock_response.content = (
            "Got it! Here's your MEDDIC analysis without Paper Process..."
        )
        mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)

        state: MeddpiccAgentState = {
            "query": "I don't use P in my process, drop it",
            "followup_mode": True,
            "original_analysis": "**M - Metrics:**\n**E - Economic Buyer:**\n**P - Paper Process:**...",
        }

        result = await followup_handler(state, {})

        assert result["followup_mode"] is True
        assert not result["final_response"].startswith("EXIT_FOLLOWUP_MODE:")


@pytest.mark.asyncio
async def test_followup_handler_stays_for_sales_coaching():
    """Test that sales coaching requests keep follow-up mode active."""
    with patch("agents.meddpicc_coach.nodes.followup_handler.ChatOpenAI") as mock_llm:
        # Mock LLM response for coaching request (stays in mode)
        mock_response = MagicMock()
        mock_response.content = (
            "To approach this deal, focus on identifying the Economic Buyer first..."
        )
        mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)

        state: MeddpiccAgentState = {
            "query": "use this to help figure out how to sell to target's ai needs",
            "followup_mode": True,
            "original_analysis": "**M - Metrics:** Target mentioned 20% efficiency gains...",
        }

        result = await followup_handler(state, {})

        assert result["followup_mode"] is True
        assert not result["final_response"].startswith("EXIT_FOLLOWUP_MODE:")


@pytest.mark.asyncio
async def test_followup_handler_exits_for_unrelated_question():
    """Test that unrelated questions trigger exit from follow-up mode."""
    with patch("agents.meddpicc_coach.nodes.followup_handler.ChatOpenAI") as mock_llm:
        # Mock LLM response detecting unrelated question (exits mode) - JSON format
        mock_response = MagicMock()
        mock_response.content = '{"intent": "exit", "response": "Got it! I\'ll hand this over to the main bot."}'
        mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)

        state: MeddpiccAgentState = {
            "query": "What's the weather today?",
            "followup_mode": True,
            "original_analysis": "**M - Metrics:** ...",
        }

        result = await followup_handler(state, {})

        assert result["followup_mode"] is False
        assert "hand this over to the main bot" in result["final_response"]


@pytest.mark.asyncio
async def test_followup_handler_exits_with_explicit_exit_command():
    """Test that explicit exit commands trigger exit from follow-up mode."""
    with patch("agents.meddpicc_coach.nodes.followup_handler.ChatOpenAI") as mock_llm:
        # Mock LLM response for exit command (exits mode) - JSON format
        mock_response = MagicMock()
        mock_response.content = '{"intent": "exit", "response": "Got it! I\'ll hand this over to the main bot."}'
        mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)

        state: MeddpiccAgentState = {
            "query": "exit this please and search for target's ai needs",
            "followup_mode": True,
            "original_analysis": "**M - Metrics:** ...",
        }

        result = await followup_handler(state, {})

        assert result["followup_mode"] is False


@pytest.mark.asyncio
async def test_graph_routes_to_followup_handler_when_followup_mode_true():
    """Test that graph routes to follow-up handler when followup_mode is True."""
    graph = build_meddpicc_coach()

    with patch("agents.meddpicc_coach.nodes.followup_handler.ChatOpenAI") as mock_llm:
        # Mock LLM response - JSON format
        mock_response = MagicMock()
        mock_response.content = '{"intent": "meddpicc", "response": "Great question! Here\'s what you need to know..."}'
        mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)

        state: MeddpiccAgentState = {
            "query": "What does Champion mean?",
            "followup_mode": True,
            "original_analysis": "**M - Metrics:** ...",
        }

        config = {"configurable": {"thread_id": "test-followup-1"}}

        result = None
        async for event in graph.astream(state, config):
            result = event
            # Should route to followup_handler, not qa_collector or parse_notes
            if (
                "followup_handler" in event
                or "qa_collector" in event
                or "parse_notes" in event
            ):
                break

        assert result is not None
        assert "followup_handler" in result
        assert "qa_collector" not in result
        assert "parse_notes" not in result


@pytest.mark.asyncio
async def test_full_followup_flow_stay_then_exit():
    """Test complete flow: follow-up question (stay) → exit command (exit)."""
    with patch("agents.meddpicc_coach.nodes.followup_handler.ChatOpenAI") as mock_llm:
        # Test 1: MEDDPICC question (should stay in mode) - JSON format
        mock_response_stay = MagicMock()
        mock_response_stay.content = '{"intent": "meddpicc", "response": "A Champion is an internal advocate..."}'
        mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response_stay)

        state1: MeddpiccAgentState = {
            "query": "What does Champion mean?",
            "followup_mode": True,
            "original_analysis": "**M - Metrics:** Target mentioned...",
        }

        result1 = await followup_handler(state1, {})
        assert result1["followup_mode"] is True
        assert "Champion" in result1["final_response"]

        # Test 2: Exit command (should exit mode) - JSON format
        mock_response_exit = MagicMock()
        mock_response_exit.content = '{"intent": "exit", "response": "Got it! I\'ll hand this over to the main bot."}'
        mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response_exit)

        state2: MeddpiccAgentState = {
            "query": "done",
            "followup_mode": True,
            "original_analysis": "**M - Metrics:** Target mentioned...",
        }

        result2 = await followup_handler(state2, {})
        assert result2["followup_mode"] is False
        assert "hand this over" in result2["final_response"]


@pytest.mark.asyncio
async def test_followup_handler_handles_missing_original_analysis():
    """Test that handler gracefully handles missing original analysis."""
    state: MeddpiccAgentState = {
        "query": "What does Champion mean?",
        "followup_mode": True,
        "original_analysis": "",  # Missing
    }

    result = await followup_handler(state, {})

    assert result["followup_mode"] is False
    assert "don't have the original analysis" in result["final_response"]


@pytest.mark.asyncio
async def test_followup_handler_handles_empty_query():
    """Test that handler gracefully handles empty query."""
    state: MeddpiccAgentState = {
        "query": "",
        "followup_mode": True,
        "original_analysis": "**M - Metrics:** ...",
    }

    result = await followup_handler(state, {})

    assert result["followup_mode"] is True
    assert "ready for your follow-up questions" in result["final_response"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
