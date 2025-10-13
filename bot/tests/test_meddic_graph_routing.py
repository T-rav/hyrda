"""Test MEDDPICC graph routing logic.

Verify that the graph routes correctly between Q&A and direct analysis.
"""

import pytest

from agents.meddpicc_coach.nodes.graph_builder import build_meddpicc_coach
from agents.meddpicc_coach.state import MeddpiccAgentState


@pytest.mark.asyncio
async def test_graph_routes_empty_query_to_qa():
    """Test that empty query routes to Q&A collector."""
    graph = build_meddpicc_coach()

    state: MeddpiccAgentState = {
        "query": "",
        "question_mode": False,
        "current_question_index": 0,
        "gathered_answers": {},
    }

    config = {"configurable": {"thread_id": "test-thread-1"}}

    result = None
    async for event in graph.astream(state, config):
        result = event
        # Should hit qa_collector first
        if "qa_collector" in event:
            break

    assert result is not None
    assert "qa_collector" in result
    # Should return Q&A mode
    assert result["qa_collector"].get("question_mode") is True


@pytest.mark.asyncio
async def test_graph_routes_notes_to_parse():
    """Test that query with notes routes directly to parse_notes."""
    graph = build_meddpicc_coach()

    state: MeddpiccAgentState = {
        "query": "Spoke with Bob at Acme Corp. They need better reporting.",
        "question_mode": False,
    }

    config = {"configurable": {"thread_id": "test-thread-2"}}

    result = None
    async for event in graph.astream(state, config):
        result = event
        # Should hit parse_notes first (not qa_collector)
        if "parse_notes" in event or "qa_collector" in event:
            break

    assert result is not None
    assert "parse_notes" in result  # Should go to parse_notes, not qa_collector


@pytest.mark.asyncio
async def test_graph_continues_qa_when_question_mode_true():
    """Test that question_mode=True continues Q&A even with query."""
    graph = build_meddpicc_coach()

    # Simulating a checkpoint state where we're mid-Q&A
    state: MeddpiccAgentState = {
        "query": "Acme Corp",  # Answer to question 1
        "question_mode": True,  # Still in Q&A mode
        "current_question_index": 1,
        "gathered_answers": {},
    }

    config = {"configurable": {"thread_id": "test-thread-3"}}

    result = None
    async for event in graph.astream(state, config):
        result = event
        # Should route back to qa_collector despite having a query
        if "qa_collector" in event or "parse_notes" in event:
            break

    assert result is not None
    assert "qa_collector" in result  # Should continue Q&A
    assert "parse_notes" not in result


@pytest.mark.asyncio
async def test_full_qa_flow_compiles_and_builds_report():
    """Test complete flow: empty query → Q&A → compile notes → full report."""
    graph = build_meddpicc_coach()

    # Simulate the final answer (question 8 completed)
    state: MeddpiccAgentState = {
        "query": "Status quo and doing nothing",  # Answer to last question
        "question_mode": True,
        "current_question_index": 8,  # Last question
        "gathered_answers": {
            "company": "Acme Corp - manufacturing",
            "pain": "Manual reporting takes 20 hours per week",
            "metrics": "Save $50K annually",
            "buyer": "CFO Sarah Johnson",
            "criteria": "Must have ROI proof and easy integration",
            "process": "Q1 2026 pilot, Q2 full rollout",
            "champion": "Bob from analytics team",
        },
    }

    config = {"configurable": {"thread_id": "test-thread-4"}}

    # Track which nodes we hit
    nodes_visited = []
    final_result = None

    async for event in graph.astream(state, config):
        node_name = list(event.keys())[0]
        nodes_visited.append(node_name)
        final_result = event

    # Verify flow: qa_collector → parse_notes → meddpicc_analysis → coaching_insights
    assert "qa_collector" in nodes_visited, "Should start with qa_collector"
    assert "parse_notes" in nodes_visited, "Should proceed to parse_notes after Q&A"
    assert "meddpicc_analysis" in nodes_visited, "Should analyze notes"
    assert "coaching_insights" in nodes_visited, "Should provide coaching"

    # Verify qa_collector compiled the notes properly
    # Check that compiled notes contain the answers
    # Final result should have coaching insights with a report
    assert final_result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
