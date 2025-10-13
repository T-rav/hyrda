"""Integration tests for MEDDPICC Q&A flow.

Tests full user journeys from start to finish:
- Full notes → report
- Empty → Q&A loop (8 questions) → report (multiple iterations)
"""

from unittest.mock import AsyncMock, patch

import pytest

from agents.meddic_agent import MeddicAgent
from agents.meddpicc_coach.nodes.graph_builder import build_meddpicc_coach


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
async def test_full_notes_to_report():
    """Test: User provides full notes upfront → gets report immediately."""
    graph = build_meddpicc_coach()

    full_notes = """
    Company: Acme Corp - 500 person manufacturing company
    Pain: Manual reporting takes 20 hours per week, error-prone
    Metrics: Save $50K annually, reduce reporting time by 80%
    Buyer: CFO Sarah Johnson has final budget approval
    Criteria: Must integrate with existing ERP, ROI proof required
    Process: Q1 2026 pilot, Q2 full rollout if successful
    Champion: Bob from analytics team is pushing for this
    Competition: Evaluating us vs. Tableau and staying with Excel
    """

    state = {"query": full_notes}
    config = {"configurable": {"thread_id": "test-full-notes"}}

    nodes_visited = []
    async for event in graph.astream(state, config):
        node_name = list(event.keys())[0]
        nodes_visited.append(node_name)

    # Should skip Q&A and go straight to analysis
    assert "qa_collector" not in nodes_visited, (
        "Should NOT enter Q&A mode with full notes"
    )
    assert "parse_notes" in nodes_visited
    assert "meddpicc_analysis" in nodes_visited
    assert "coaching_insights" in nodes_visited
    print(f"✅ Full notes → report: {len(nodes_visited)} nodes")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_qa_flow_iteration_1():
    """Test iteration 1: Empty → Answer all 8 questions → Get report."""
    graph = build_meddpicc_coach()
    thread_id = "test-qa-iteration-1"

    # Step 1: Start with empty query
    state = {"query": ""}
    config = {"configurable": {"thread_id": thread_id}}

    result = None
    async for event in graph.astream(state, config):
        result = event
        break  # Get first response

    assert "qa_collector" in result
    assert result["qa_collector"]["question_mode"] is True
    assert "Question 1/8" in result["qa_collector"]["final_response"]
    print("✅ Iteration 1 - Question 1 asked")

    # Step 2-9: Answer each question
    answers = [
        "Acme Corp - manufacturing",
        "Manual reporting takes 20 hours/week",
        "Save $50K annually",
        "CFO Sarah Johnson",
        "Must integrate with ERP",
        "Q1 2026 pilot",
        "Bob from analytics",
        "Evaluating vs Tableau",
    ]

    for i, answer in enumerate(answers, 1):
        state = {"query": answer}
        result = None
        nodes_in_turn = []

        async for event in graph.astream(state, config):
            result = event
            nodes_in_turn.append(list(event.keys())[0])

        if i < 8:
            # Should still be in Q&A mode
            assert "qa_collector" in nodes_in_turn
            print(f"✅ Iteration 1 - Question {i + 1} asked")
        else:
            # Last answer should trigger full analysis
            assert "qa_collector" in nodes_in_turn
            assert "parse_notes" in nodes_in_turn
            assert "meddpicc_analysis" in nodes_in_turn
            assert "coaching_insights" in nodes_in_turn
            print(
                f"✅ Iteration 1 - Complete! Report generated after {len(nodes_in_turn)} nodes"
            )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_qa_flow_iteration_2():
    """Test iteration 2: Empty → Answer all 8 questions → Get report."""
    graph = build_meddpicc_coach()
    thread_id = "test-qa-iteration-2"

    # Start with empty query
    state = {"query": ""}
    config = {"configurable": {"thread_id": thread_id}}

    result = None
    async for event in graph.astream(state, config):
        result = event
        break

    assert "qa_collector" in result
    assert result["qa_collector"]["question_mode"] is True
    print("✅ Iteration 2 - Started Q&A")

    # Answer all 8 questions
    answers = [
        "TechStart Inc - SaaS startup, 50 employees",
        "Customer onboarding takes too long, 40% churn",
        "Reduce churn to 20%, save $200K ARR",
        "CEO Mike Chen",
        "Fast implementation, proven results",
        "Need solution by EOY, urgent",
        "Head of CS Lisa is champion",
        "Considering building in-house",
    ]

    for i, answer in enumerate(answers, 1):
        state = {"query": answer}
        nodes_in_turn = []

        async for event in graph.astream(state, config):
            nodes_in_turn.append(list(event.keys())[0])

        if i < 8:
            assert "qa_collector" in nodes_in_turn
        else:
            # Final answer triggers full pipeline
            assert "coaching_insights" in nodes_in_turn
            print("✅ Iteration 2 - Complete! Report generated")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_qa_flow_iteration_3():
    """Test iteration 3: Empty → Answer all 8 questions → Get report."""
    graph = build_meddpicc_coach()
    thread_id = "test-qa-iteration-3"

    # Start with empty query
    state = {"query": ""}
    config = {"configurable": {"thread_id": thread_id}}

    result = None
    async for event in graph.astream(state, config):
        result = event
        break

    assert "qa_collector" in result
    print("✅ Iteration 3 - Started Q&A")

    # Answer all 8 questions (with some skips)
    answers = [
        "Global Retail Co",
        "Inventory management is broken",
        "skip",  # No metrics provided
        "idk",  # Don't know buyer
        "Need cloud-based solution",
        "ASAP, critical",
        "IT Director Jane is pushing",
        "skip",  # No competition info
    ]

    for i, answer in enumerate(answers, 1):
        state = {"query": answer}
        nodes_in_turn = []

        async for event in graph.astream(state, config):
            nodes_in_turn.append(list(event.keys())[0])

        if i < 8:
            assert "qa_collector" in nodes_in_turn
        else:
            # Even with skips, should generate report
            assert "coaching_insights" in nodes_in_turn
            print("✅ Iteration 3 - Complete! Report generated (with skipped answers)")


@pytest.mark.asyncio
async def test_agent_level_full_notes():
    """Test at agent level: Full notes → report (no Q&A)."""
    agent = MeddicAgent()

    mock_slack = AsyncMock()
    mock_slack.send_message = AsyncMock(return_value={"ts": "123"})
    mock_slack.update_message = AsyncMock()
    mock_slack.delete_thinking_indicator = AsyncMock()

    context = {
        "user_id": "U123",
        "channel": "C123",
        "thread_ts": "1234567890.123456",
        "thinking_ts": "123",
        "slack_service": mock_slack,
        "llm_service": AsyncMock(),
    }

    full_notes = """
    Call with Acme Corp (500 person manufacturing):
    - Pain: Manual reporting takes 20 hours/week
    - Goal: Save $50K annually
    - Decision maker: CFO Sarah Johnson
    - Timeline: Q1 2026 pilot
    """

    with patch.object(agent.graph, "astream") as mock_stream:
        # Mock successful analysis
        mock_stream.return_value = AsyncIterator(
            [
                {"parse_notes": {"raw_notes": full_notes}},
                {"meddpicc_analysis": {"meddpicc_breakdown": "Analysis"}},
                {"coaching_insights": {"final_response": "Full report here"}},
            ]
        )

        result = await agent.run(full_notes, context)

    # Should get full report, not questions
    assert result["metadata"].get("question_mode") is not True
    assert "Full report here" in result["response"]
    print("✅ Agent-level full notes test passed")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_three_complete_qa_conversations():
    """Test 3 complete back-and-forth Q&A conversations in sequence.

    Simulates real user interaction:
    - User sends empty message
    - Bot asks question
    - User answers
    - Bot asks next question
    - ... repeat for all 8 questions
    - Bot generates report

    This happens 3 times with different scenarios.
    """
    graph = build_meddpicc_coach()

    # Define 3 different conversation scenarios
    scenarios = [
        {
            "name": "Acme Corp - Manufacturing",
            "thread_id": "conversation-1",
            "answers": [
                "Acme Corp - 500 person manufacturing company",
                "Manual reporting takes 20 hours per week, lots of errors",
                "Save $50K annually, reduce reporting time by 80%",
                "CFO Sarah Johnson has final budget approval",
                "Must integrate with existing ERP, need ROI proof",
                "Q1 2026 pilot, Q2 full rollout if successful",
                "Bob from analytics team is our champion",
                "Evaluating us vs. Tableau and staying with Excel",
            ],
        },
        {
            "name": "TechStart - SaaS Startup",
            "thread_id": "conversation-2",
            "answers": [
                "TechStart Inc - 50 person SaaS startup",
                "Customer onboarding takes too long, 40% churn rate",
                "Reduce churn to 20%, save $200K in ARR",
                "CEO Mike Chen makes all tech decisions",
                "Fast implementation critical, proven results needed",
                "Need solution by end of year, very urgent",
                "Head of Customer Success Lisa is pushing hard for this",
                "Considering building in-house or hiring more CS reps",
            ],
        },
        {
            "name": "Global Retail - Enterprise",
            "thread_id": "conversation-3",
            "answers": [
                "Global Retail Co - 5000+ employees",
                "Inventory management system is completely broken",
                "skip",  # No metrics
                "idk",  # Don't know decision maker
                "Must be cloud-based and support multiple regions",
                "ASAP - this is causing major issues daily",
                "IT Director Jane is championing the project",
                "skip",  # No competition info
            ],
        },
    ]

    for scenario in scenarios:
        print(f"\n{'=' * 60}")
        print(f"🎯 Starting conversation: {scenario['name']}")
        print(f"{'=' * 60}")

        # Turn 1: User sends empty message to start Q&A
        print("👤 User: -meddic (empty)")
        state = {"query": ""}
        config = {"configurable": {"thread_id": scenario["thread_id"]}}

        result = None
        async for event in graph.astream(state, config):
            result = event
            break  # Get first question

        assert "qa_collector" in result
        assert result["qa_collector"]["question_mode"] is True
        question_num = 1
        print(f"🤖 Bot: Question {question_num}/8")

        # Turns 2-9: Answer each question with back-and-forth
        for i, answer in enumerate(scenario["answers"], 1):
            print(f"👤 User: {answer[:50]}{'...' if len(answer) > 50 else ''}")

            state = {"query": answer}
            nodes_in_turn = []

            async for event in graph.astream(state, config):
                nodes_in_turn.append(list(event.keys())[0])

            if i < 8:
                # Should still be asking questions
                assert "qa_collector" in nodes_in_turn
                print(f"🤖 Bot: Question {i + 1}/8")
            else:
                # Last answer should trigger full analysis
                assert "qa_collector" in nodes_in_turn
                assert "parse_notes" in nodes_in_turn
                assert "meddpicc_analysis" in nodes_in_turn
                assert "coaching_insights" in nodes_in_turn
                print("🤖 Bot: ✅ Full MEDDPICC report generated!")
                print(f"   Pipeline: {' → '.join(nodes_in_turn)}")

        print(f"✅ Conversation complete: {scenario['name']}")

    print(f"\n{'=' * 60}")
    print("🎉 All 3 conversations completed successfully!")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
