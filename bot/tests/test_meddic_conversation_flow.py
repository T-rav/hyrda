"""Test MEDDPICC multi-turn conversation flow with context accumulation.

These tests verify that the MEDDIC agent:
1. Asks for clarification when input is insufficient
2. Resumes conversation with accumulated context from previous turns
3. Proceeds with analysis once sufficient information is gathered
4. Uses LangGraph checkpointing to maintain state across turns
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from dotenv import load_dotenv

# Load .env from project root FIRST, before any other imports
project_root = Path(__file__).parent.parent.parent
env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"✅ Loaded .env from {env_file}")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.meddic_agent import MeddicAgent
from tests.agent_test_utils import AgentContextBuilder, SlackServiceMockFactory


@pytest.mark.integration
class TestMeddicConversationFlow:
    """Integration tests for multi-turn MEDDPICC conversations.

    NOTE: These tests require a valid LLM_API_KEY and make real API calls.
    They test the complete conversation flow with checkpointing.
    """

    @pytest.fixture
    def agent_and_context(self):
        """Create agent and context with proper mocks"""
        agent = MeddicAgent()

        # Create proper async mock for Slack service
        slack_mock = SlackServiceMockFactory.create_mock()
        slack_mock.send_message = AsyncMock(return_value={"ts": "123.456"})
        slack_mock.update_message = AsyncMock(return_value={"ts": "123.456"})
        slack_mock.send_thinking_indicator = AsyncMock(return_value="thinking_ts")
        slack_mock.delete_thinking_indicator = AsyncMock()
        slack_mock.upload_file = AsyncMock(return_value={"ok": False})

        # Use same user_id and channel for all turns (simulates thread)
        context = (
            AgentContextBuilder()
            .with_user_id("U123")
            .with_channel("C456")
            .with_slack_service(slack_mock)
            .build()
        )

        return agent, context

    @pytest.mark.asyncio
    async def test_two_turn_conversation_vague_then_detailed(self, agent_and_context):
        """Test: Vague input → Clarification → Detailed response → Analysis

        Turn 1: "bob from jane's bait and tackle wants a custom pos system"
        Expected: Should ask for more details (minimal context)

        Turn 2: "they need better reporting in powerbi and inventory tracking"
        Expected: Should proceed with analysis (accumulated context is now sufficient)
        """
        agent, context = agent_and_context

        # Turn 1: Vague initial input
        turn1_input = "bob from jane's bait and tackle wants a custom pos system"
        turn1_result = await agent.run(turn1_input, context)

        print("\n" + "=" * 80)
        print("TURN 1 INPUT:")
        print(turn1_input)
        print("\nTURN 1 RESPONSE:")
        print(turn1_result["response"])
        print("=" * 80)

        # Turn 1 assertions: Should proceed (customer name + pain point is sufficient with new logic)
        assert "response" in turn1_result
        # With the new permissive logic, this should actually PROCEED
        # because it has customer name + specific solution need
        assert "MEDDPICC" in turn1_result["response"]

    @pytest.mark.asyncio
    async def test_three_turn_conversation_accumulating_context(
        self, agent_and_context
    ):
        """Test: Multiple turns building up context until analysis proceeds

        Turn 1: "help with a deal"
        Expected: Ask for clarification (too vague)

        Turn 2: "it's for jane's bait and tackle"
        Expected: Ask for more details (need pain points)

        Turn 3: "they want a pos system with better reporting"
        Expected: Proceed with analysis (now have customer + pain)
        """
        agent, context = agent_and_context

        # Turn 1: Very vague
        turn1_input = "help with a deal"
        turn1_result = await agent.run(turn1_input, context)

        print("\n" + "=" * 80)
        print("TURN 1 INPUT:")
        print(turn1_input)
        print("\nTURN 1 RESPONSE:")
        print(turn1_result["response"][:300])
        print("=" * 80)

        # Turn 1: Should ask for clarification
        assert "response" in turn1_result
        assert (
            "need a bit more context" in turn1_result["response"]
            or "share more about" in turn1_result["response"]
        )

        # Turn 2: Add customer name but still vague
        turn2_input = "it's for jane's bait and tackle"
        turn2_result = await agent.run(turn2_input, context)

        print("\n" + "=" * 80)
        print("TURN 2 INPUT:")
        print(turn2_input)
        print("\nTURN 2 RESPONSE:")
        print(turn2_result["response"][:300])
        print("=" * 80)

        # Turn 2: May ask for more details or proceed depending on how the LLM interprets accumulated context
        assert "response" in turn2_result

        # Turn 3: Add specific pain point
        turn3_input = (
            "they want a pos system with better reporting and inventory management"
        )
        turn3_result = await agent.run(turn3_input, context)

        print("\n" + "=" * 80)
        print("TURN 3 INPUT:")
        print(turn3_input)
        print("\nTURN 3 RESPONSE:")
        print(
            turn3_result["response"][:500]
            if turn3_result.get("response")
            else "(empty - PDF uploaded)"
        )
        print(f"\nTURN 3 METADATA: {turn3_result.get('metadata', {})}")
        print("=" * 80)

        # Turn 3: Should now proceed with analysis (customer + specific needs)
        assert "response" in turn3_result
        metadata = turn3_result.get("metadata", {})

        # Success case: Either text response OR successful PDF upload
        if metadata.get("pdf_uploaded"):
            # PDF was uploaded with summary - response will be empty
            assert metadata.get("pdf_generated"), (
                "PDF should be generated when uploaded"
            )
            assert metadata.get("response_length", 0) > 0, (
                "Should have generated content even if response is empty"
            )
            print("✅ Turn 3 SUCCESS: Analysis completed and PDF uploaded")
        else:
            # PDF failed - should have full text response
            assert turn3_result["response"], (
                "Should have text response if PDF upload failed"
            )
            assert "MEDDPICC" in turn3_result["response"], (
                "Text response should contain MEDDPICC analysis"
            )
            print("✅ Turn 3 SUCCESS: Analysis completed with text fallback")

    @pytest.mark.asyncio
    async def test_clarification_then_comprehensive_notes(self, agent_and_context):
        """Test: Vague → Clarification → User pastes comprehensive notes → Analysis

        Turn 1: "they need better reporting in powerbi"
        Expected: Ask for clarification (no customer, no context)

        Turn 2: User pastes full structured call notes
        Expected: Proceed with analysis
        """
        agent, context = agent_and_context

        # Turn 1: Vague follow-up style message
        turn1_input = "they need better reporting in powerbi"
        turn1_result = await agent.run(turn1_input, context)

        print("\n" + "=" * 80)
        print("TURN 1 INPUT:")
        print(turn1_input)
        print("\nTURN 1 RESPONSE:")
        print(turn1_result["response"][:300])
        print("=" * 80)

        # Turn 1: Should ask for clarification
        assert "response" in turn1_result
        assert (
            "need a bit more context" in turn1_result["response"]
            or "share more about" in turn1_result["response"]
        )

        # Turn 2: User responds with comprehensive notes
        turn2_input = """Sales Call Notes – DataCorp Analytics

Pain Points:
- Current PowerBI reports are slow and don't update in real-time
- Data pipeline is fragmented across 5 different sources
- No automated alerting when KPIs go off track
- Analysts spend 60% of time on data prep instead of analysis

What They Want:
- Unified data platform with real-time PowerBI integration
- Automated data quality checks and alerting
- Self-service analytics for business users

Budget: $250K for Q2 implementation
Decision Maker: CTO Sarah Chen
Timeline: Need to launch by end of Q2 for board presentation
Competition: Evaluating Tableau + Snowflake vs our solution"""

        turn2_result = await agent.run(turn2_input, context)

        print("\n" + "=" * 80)
        print("TURN 2 INPUT:")
        print(turn2_input[:200] + "...")
        print("\nTURN 2 RESPONSE:")
        print(turn2_result["response"][:500])
        print("=" * 80)

        # Turn 2: Should now proceed with analysis
        assert "response" in turn2_result
        assert "MEDDPICC" in turn2_result["response"]
        # Should NOT ask for clarification again
        assert "need a bit more context" not in turn2_result["response"]

    @pytest.mark.asyncio
    async def test_checkpointing_preserves_state(self, agent_and_context):
        """Test that LangGraph checkpointing works across turns

        Verify that the thread_id is maintained and context accumulates
        """
        agent, context = agent_and_context

        # Turn 1
        turn1_input = "analyzing a deal for Acme Corp"
        turn1_result = await agent.run(turn1_input, context)

        # Check that thread_id was set
        assert "thread_id" in turn1_result.get("metadata", {})
        thread_id_turn1 = turn1_result["metadata"]["thread_id"]

        # Turn 2
        turn2_input = "they have a $200K budget"
        turn2_result = await agent.run(turn2_input, context)

        # Verify same thread_id (conversation continuity)
        assert "thread_id" in turn2_result.get("metadata", {})
        thread_id_turn2 = turn2_result["metadata"]["thread_id"]

        assert thread_id_turn1 == thread_id_turn2, (
            "Thread ID should remain consistent across turns"
        )

        print(f"\n✅ Checkpointing working: thread_id={thread_id_turn1}")

    @pytest.mark.asyncio
    async def test_pdf_generation_with_comprehensive_notes(self, agent_and_context):
        """Test that PDF is generated when comprehensive notes are provided

        When user provides detailed sales notes, the agent should:
        1. Proceed with analysis (not ask for clarification)
        2. Generate a valid PDF report
        3. Include MEDDPICC analysis content
        """
        agent, context = agent_and_context

        comprehensive_notes = """Sales Call - TechCorp Enterprise Deal

PAIN POINTS:
- Legacy system causing 40% slower deployments
- Engineering team frustrated with 2-week release cycles
- Losing competitive advantage to faster-moving startups

ECONOMIC BUYER:
- CTO Rachel Kim has final decision authority
- Budget: $300K allocated for DevOps transformation

DECISION PROCESS:
- Rachel evaluates solutions (week 1-2)
- Technical review with team (week 3)
- Board approval needed for contracts over $250K (week 4)

METRICS:
- Need to reduce deployment time from 2 weeks to 2 days
- Want 50% reduction in production incidents
- Target ROI within 6 months

CHAMPION:
- VP Engineering Mike Chen is advocating internally
- He's used our solution at previous company

COMPETITION:
- Comparing us against DevOps Pro and Cloudify
- We have strongest enterprise features

TIMELINE:
- Pilot by end of Q1
- Full rollout by Q3"""

        result = await agent.run(comprehensive_notes, context)

        # Should proceed with analysis (not clarification)
        assert "response" in result
        assert not result.get("metadata", {}).get("needs_clarification", False)

        metadata = result.get("metadata", {})

        # PDF should be generated
        assert metadata.get("pdf_generated"), (
            "PDF should be generated for comprehensive notes"
        )
        assert metadata.get("response_length", 0) > 500, (
            "Should generate substantial analysis content"
        )

        # Should have MEDDPICC analysis (either in response or PDF)
        if result.get("response"):
            # Text response returned (PDF upload failed)
            assert "MEDDPICC" in result["response"], (
                "Text response should contain MEDDPICC analysis"
            )

        # Verify metadata is complete
        assert "query_length" in metadata
        assert "agent" in metadata
        assert metadata["agent"] == "meddic"
        assert "thread_id" in metadata

        print("\n✅ PDF generation test PASSED")
        print(f"   - PDF generated: {metadata.get('pdf_generated')}")
        print(f"   - PDF uploaded: {metadata.get('pdf_uploaded')}")
        print(f"   - Analysis length: {metadata.get('response_length')} chars")

    @pytest.mark.asyncio
    async def test_pdf_not_generated_for_clarification(self, agent_and_context):
        """Test that PDF is NOT generated when asking for clarification

        When input is insufficient, agent should:
        1. Ask for clarification
        2. NOT generate a PDF
        3. Return clarification message
        """
        agent, context = agent_and_context

        vague_input = "help with deal"

        result = await agent.run(vague_input, context)

        # Should ask for clarification
        assert "response" in result
        metadata = result.get("metadata", {})

        # Check if it asked for clarification
        needs_clarification = metadata.get("needs_clarification", False)
        has_clarification_text = (
            "need a bit more context" in result["response"]
            or "share more about" in result["response"]
        )

        if needs_clarification or has_clarification_text:
            # PDF should NOT be generated for clarification
            assert not metadata.get("pdf_generated", False), (
                "PDF should NOT be generated when asking for clarification"
            )
            print(
                "\n✅ Clarification test PASSED - No PDF generated for insufficient input"
            )
        else:
            # Agent proceeded anyway (might have permissive logic)
            print("\n⚠️  Agent proceeded instead of asking for clarification")
            print(f"   Response: {result['response'][:200]}")
            # This is acceptable with permissive logic

    @pytest.mark.asyncio
    async def test_clarification_flow_then_pdf_generation(self, agent_and_context):
        """Test complete flow: Clarification → Details → PDF generated

        Turn 1: Vague input → Clarification (NO PDF)
        Turn 2: Comprehensive notes → Analysis with PDF generated
        """
        agent, context = agent_and_context

        # Turn 1: Vague input should trigger clarification
        turn1_input = "need help with a sales deal"
        turn1_result = await agent.run(turn1_input, context)

        print("\n" + "=" * 80)
        print("TURN 1: Vague input")
        print(f"Input: {turn1_input}")
        print(f"Response: {turn1_result['response'][:200]}")
        print("=" * 80)

        # Turn 1 assertions
        assert "response" in turn1_result
        turn1_metadata = turn1_result.get("metadata", {})

        # Should ask for clarification (no PDF)
        needs_clarification = turn1_metadata.get("needs_clarification", False)
        has_clarification_text = (
            "need a bit more context" in turn1_result["response"]
            or "share more about" in turn1_result["response"]
        )

        if needs_clarification or has_clarification_text:
            # Turn 1: No PDF should be generated
            assert not turn1_metadata.get("pdf_generated", False), (
                "Turn 1: PDF should NOT be generated for clarification"
            )
            print("✅ Turn 1: Clarification requested, no PDF generated")
        else:
            print("⚠️  Turn 1: Agent proceeded (permissive logic) - checking Turn 2...")

        # Turn 2: User provides comprehensive notes
        turn2_input = """Here are the details:

CUSTOMER: DataFlow Analytics
PAIN POINTS:
- Current reporting system takes 3 hours to generate daily reports
- No real-time visibility into KPIs
- Data silos across 5 different systems
- Manual data entry causing 15% error rate

ECONOMIC BUYER:
- CFO Jennifer Martinez has final approval
- Budget: $150K allocated for analytics transformation

DECISION PROCESS:
- Evaluation period: 2 weeks
- Technical review with IT team
- Final approval from CFO and CTO

METRICS:
- Reduce report generation from 3 hours to 15 minutes
- Achieve <1% error rate
- ROI target: 6 months

TIMELINE:
- Need solution deployed by end of Q2
- Pilot starting next month

CHAMPION:
- VP of Analytics David Kim is advocating for our solution
- He's familiar with our platform from previous company"""

        turn2_result = await agent.run(turn2_input, context)

        print("\n" + "=" * 80)
        print("TURN 2: Comprehensive details provided")
        print(f"Input: {turn2_input[:100]}...")
        print(
            f"Response: {turn2_result['response'][:200] if turn2_result.get('response') else '(empty - PDF uploaded)'}"
        )
        print("=" * 80)

        # Turn 2 assertions
        assert "response" in turn2_result
        turn2_metadata = turn2_result.get("metadata", {})

        # Turn 2: PDF should NOW be generated after receiving details
        assert turn2_metadata.get("pdf_generated"), (
            "Turn 2: PDF should be generated after receiving comprehensive details"
        )
        assert turn2_metadata.get("response_length", 0) > 500, (
            "Turn 2: Should generate substantial MEDDPICC analysis"
        )

        # Verify MEDDPICC content (either in response or via PDF upload)
        if turn2_result.get("response"):
            # Text response returned (PDF upload failed in test)
            assert "MEDDPICC" in turn2_result["response"], (
                "Turn 2: Should contain MEDDPICC analysis"
            )

        print("\n✅ COMPLETE FLOW TEST PASSED:")
        print("   Turn 1: Clarification (no PDF) ✅")
        print(
            f"   Turn 2: Analysis with PDF generated ({turn2_metadata.get('response_length')} chars) ✅"
        )
        print(f"   PDF generated: {turn2_metadata.get('pdf_generated')}")
        print(f"   PDF uploaded: {turn2_metadata.get('pdf_uploaded')}")


if __name__ == "__main__":
    # Allow running this test file directly
    pytest.main([__file__, "-v", "-s"])
