"""Real integration tests for MEDDPICC follow-up flow.

These tests use REAL LLM calls (not mocked) to test the complete workflow.
Requires OPENAI_API_KEY environment variable.
"""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from agents.meddpicc_coach.nodes.graph_builder import build_meddpicc_coach

# Load .env file from project root
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✓ Loaded .env from: {env_path}")
else:
    print(f"⚠ .env not found at: {env_path}")

# Check for API key (try both OPENAI_API_KEY and LLM_API_KEY)
api_key = os.getenv("LLM_API_KEY")
print(f"API Key present: {bool(api_key)}")
if api_key:
    print(f"API Key starts with: {api_key[:10]}...")

# Skip all tests if no API key
pytestmark = pytest.mark.skipif(
    not api_key,
    reason="OPENAI_API_KEY or LLM_API_KEY not set - skipping real integration tests",
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_analysis_then_followup_stay():
    """Real integration: Full analysis → Follow-up MEDDPICC question → Stay in mode."""
    graph = build_meddpicc_coach()

    # Step 1: Get initial analysis
    initial_notes = """
    Call with Sarah at Acme Corp. They're a 500-person manufacturing company.
    Their main pain is manual reporting - takes their team 20 hours per week.
    They want to save time and reduce errors. Budget is around $50K.
    Sarah (CFO) has final approval. They need ROI proof and ERP integration.
    Timeline is Q1 2026 for pilot. Bob from analytics is really excited about this.
    They're also looking at Tableau as an alternative.
    """

    thread_id = "real-followup-test-1"  # Same thread for state persistence
    state1 = {"query": initial_notes}
    config1 = {"configurable": {"thread_id": thread_id}}

    final_result1 = None
    async for event in graph.astream(state1, config1):
        final_result1 = event

    # Should have completed analysis and enabled follow-up mode
    last_state1 = list(final_result1.values())[0]
    assert last_state1.get("followup_mode") is True, "Follow-up mode should be enabled"
    assert last_state1.get("original_analysis"), "Should have original analysis stored"
    assert "Economic Buyer" in last_state1.get(
        "original_analysis", ""
    ) or "Metrics" in last_state1.get("original_analysis", ""), (
        "Analysis should contain MEDDPICC elements"
    )

    print("✅ Initial analysis complete with follow-up mode enabled")
    print(f"   Analysis length: {len(last_state1.get('original_analysis', ''))} chars")

    # Step 2: Ask a MEDDPICC methodology question (should stay in mode)
    # Use SAME thread_id so state persists via checkpointer
    state2 = {
        "query": "What does Economic Buyer mean in MEDDPICC?",
    }
    config2 = {"configurable": {"thread_id": thread_id}}

    final_result2 = None
    async for event in graph.astream(state2, config2):
        final_result2 = event

    last_state2 = list(final_result2.values())[0]
    response2 = last_state2.get("final_response", "")

    # Should stay in follow-up mode and explain Economic Buyer
    assert last_state2.get("followup_mode") is True, "Should stay in follow-up mode"
    assert not response2.startswith("EXIT_FOLLOWUP_MODE:"), (
        "Should not exit for MEDDPICC question"
    )
    assert "economic buyer" in response2.lower() or "budget" in response2.lower(), (
        "Response should explain Economic Buyer concept"
    )

    print("✅ Follow-up MEDDPICC question answered, stayed in mode")
    print(f"   Response preview: {response2[:100]}...")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_analysis_then_followup_exit():
    """Real integration: Full analysis → Unrelated question → Exit mode."""
    graph = build_meddpicc_coach()

    # Step 1: Get initial analysis
    initial_notes = """
    Quick call with John at TechStartup. They have scaling issues with their infrastructure.
    Looking to improve deployment speed. Budget discussion next week.
    """

    thread_id = "real-followup-exit-test-1"  # Same thread for state persistence
    state1 = {"query": initial_notes}
    config1 = {"configurable": {"thread_id": thread_id}}

    final_result1 = None
    async for event in graph.astream(state1, config1):
        final_result1 = event

    last_state1 = list(final_result1.values())[0]
    assert last_state1.get("followup_mode") is True
    assert last_state1.get("original_analysis")

    print("✅ Initial analysis complete")

    # Step 2: Ask unrelated question (should exit)
    # Use SAME thread_id so state persists
    state2 = {
        "query": "What's the weather like today?",
    }
    config2 = {"configurable": {"thread_id": thread_id}}

    final_result2 = None
    async for event in graph.astream(state2, config2):
        final_result2 = event

    last_state2 = list(final_result2.values())[0]
    response2 = last_state2.get("final_response", "")

    # Should exit follow-up mode for unrelated question
    assert last_state2.get("followup_mode") is False, "Should exit follow-up mode"
    assert (
        "EXIT_FOLLOWUP_MODE:" in response2 or "hand this over" in response2.lower()
    ), "Should signal exit for unrelated question"

    print("✅ Unrelated question triggered exit from follow-up mode")
    print(f"   Exit response: {response2[:150]}...")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_followup_modify_analysis():
    """Real integration: Analysis → Request to modify (drop P) → Modified analysis."""
    graph = build_meddpicc_coach()

    # Step 1: Get initial analysis
    initial_notes = """
    Call with David at Enterprise Co. 1000 employees, need better analytics.
    Pain: Current system too slow. Metrics: Want 50% faster queries.
    David is VP Engineering, can approve up to $100K. Timeline is Q2 2025.
    """

    thread_id = "real-modify-test-1"  # Same thread for state persistence
    state1 = {"query": initial_notes}
    config1 = {"configurable": {"thread_id": thread_id}}

    final_result1 = None
    async for event in graph.astream(state1, config1):
        final_result1 = event

    last_state1 = list(final_result1.values())[0]
    assert last_state1.get("followup_mode") is True

    print("✅ Initial analysis complete")

    # Step 2: Request to drop Paper Process
    # Use SAME thread_id so state persists
    state2 = {
        "query": "I don't use P (Paper Process) in my sales process, please drop it from the analysis",
    }
    config2 = {"configurable": {"thread_id": thread_id}}

    final_result2 = None
    async for event in graph.astream(state2, config2):
        final_result2 = event

    last_state2 = list(final_result2.values())[0]
    response2 = last_state2.get("final_response", "")

    # Should stay in follow-up mode and provide modified analysis
    assert last_state2.get("followup_mode") is True, "Should stay in follow-up mode"
    assert not response2.startswith("EXIT_FOLLOWUP_MODE:"), "Should not exit"
    # Response should acknowledge the modification
    assert (
        "adjust" in response2.lower()
        or "without" in response2.lower()
        or "drop" in response2.lower()
    ), "Should acknowledge dropping Paper Process"

    print("✅ Successfully modified analysis (dropped P)")
    print(f"   Modified response preview: {response2[:200]}...")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_followup_sales_coaching():
    """Real integration: Analysis → Sales coaching question → Coaching response."""
    graph = build_meddpicc_coach()

    # Step 1: Get initial analysis
    initial_notes = """
    First call with Maria at RetailCorp. They mentioned inventory management issues
    but didn't share specifics. Budget wasn't discussed. Need to follow up.
    """

    thread_id = "real-coaching-test-1"  # Same thread for state persistence
    state1 = {"query": initial_notes}
    config1 = {"configurable": {"thread_id": thread_id}}

    final_result1 = None
    async for event in graph.astream(state1, config1):
        final_result1 = event

    last_state1 = list(final_result1.values())[0]
    assert last_state1.get("followup_mode") is True

    print("✅ Initial analysis complete (minimal info)")

    # Step 2: Ask for sales coaching using the analysis
    # Use SAME thread_id so state persists
    state2 = {
        "query": "How should I approach the next call to uncover the Economic Buyer?",
    }
    config2 = {"configurable": {"thread_id": thread_id}}

    final_result2 = None
    async for event in graph.astream(state2, config2):
        final_result2 = event

    last_state2 = list(final_result2.values())[0]
    response2 = last_state2.get("final_response", "")

    # Should stay in follow-up mode and provide coaching
    assert last_state2.get("followup_mode") is True, "Should stay in follow-up mode"
    assert not response2.startswith("EXIT_FOLLOWUP_MODE:"), "Should not exit"
    # Response should contain coaching about Economic Buyer
    assert (
        "economic buyer" in response2.lower() or "decision maker" in response2.lower()
    ), "Should provide Economic Buyer coaching"

    print("✅ Provided sales coaching in follow-up mode")
    print(f"   Coaching preview: {response2[:200]}...")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-m", "integration"])
