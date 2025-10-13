"""Tests for MeddicAgent."""

import os
import sys
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.meddic_agent import MeddicAgent
from tests.agent_test_utils import AgentContextBuilder, SlackServiceMockFactory


class TestMeddicAgent:
    """Tests for MeddicAgent"""

    @pytest.mark.asyncio
    async def test_meddic_agent_run(self):
        """Test MeddicAgent execution"""
        agent = MeddicAgent()
        context = AgentContextBuilder.default()

        result = await agent.run("analyze this deal", context)

        assert "response" in result
        assert "metadata" in result
        assert "MEDDIC" in result["response"]
        assert "analyze this deal" in result["response"]

    @pytest.mark.asyncio
    async def test_meddic_agent_has_alias(self):
        """Test that MeddicAgent has medic alias"""
        assert "medic" in MeddicAgent.aliases

    @pytest.mark.asyncio
    async def test_meddic_agent_invalid_context(self):
        """Test MeddicAgent with invalid context"""
        agent = MeddicAgent()
        context = AgentContextBuilder.invalid_missing_channel()

        result = await agent.run("test query", context)

        assert "response" in result
        assert "error" in result["metadata"]


@pytest.mark.integration
class TestMeddicAgentClarificationLogic:
    """Integration tests for MEDDPICC clarification vs proceed logic.

    These are PROMPT EVALUATION tests that verify the LLM-based decision logic
    for when to proceed with analysis vs when to ask for more information.

    NOTE: These tests require a valid LLM_API_KEY in your .env file and will
    make real API calls to OpenAI. They serve as regression tests for the
    clarification prompt logic.

    Run with: pytest -m integration
    Skip with: pytest -m "not integration"
    """

    @pytest.fixture
    def agent_context(self):
        """Create agent and context with proper mocks"""
        agent = MeddicAgent()

        # Create proper async mock for Slack service
        slack_mock = SlackServiceMockFactory.create_mock()
        slack_mock.send_message = AsyncMock(return_value={"ts": "123.456"})
        slack_mock.update_message = AsyncMock(return_value={"ts": "123.456"})
        slack_mock.send_thinking_indicator = AsyncMock(return_value="thinking_ts")
        slack_mock.delete_thinking_indicator = AsyncMock()
        slack_mock.upload_file = AsyncMock(return_value={"ok": False})

        context = AgentContextBuilder().with_slack_service(slack_mock).build()

        return agent, context

    @pytest.mark.asyncio
    async def test_comprehensive_notes_should_proceed(self, agent_context):
        """Test that comprehensive structured notes proceed to analysis"""
        agent, context = agent_context

        notes = """Sales Call Notes – Jane's Equipment Repair
Date: Oct 13, 2025
Attendees: Jane (Owner/Founder), Marcus (Lead Field Tech)

Context:
Jane's Equipment Repair services and maintains medical diagnostic equipment.
Interested in using AI to streamline daily operations.

Key Pain Points:
- High inbound load: Most work orders come by phone/email, no ticketing system
- Scheduling chaos: Manual texting and spreadsheet updates
- Documentation gap: Service notes in paper forms, not searchable
- Compliance risk: Need better traceability for device history
- Tech time lost: 20-30% spent chasing parts or confirming addresses

What They Want:
- AI agent to log repair requests from emails/calls
- Auto-assign jobs based on location and skill
- Generate status updates for customers automatically
- Centralize repair reports in searchable system
- Keep it HIPAA-compliant

Budget & Timeline:
- No formal budget yet - wants small pilot first to prove ROI
- Ideally live before end of Q1 2026

Next Steps:
- Send follow-up email with proposal
- Book demo next week with Jane + Marcus
- Prepare example of AI intake agent"""

        result = await agent.run(notes, context)

        # Should proceed with analysis, not ask for clarification
        assert "response" in result
        assert "MEDDPICC" in result["response"]
        # Should NOT contain clarification language
        assert "need a bit more context" not in result["response"]
        assert "share more about the call" not in result["response"]

    @pytest.mark.asyncio
    async def test_sample_call_notes_should_proceed(self, agent_context):
        """Test that medium-coverage notes proceed to analysis"""
        agent, context = agent_context

        notes = """Call with Sarah Johnson from Acme Corp today. Really good conversation!

They're struggling with deployment speed - currently takes 2 weeks to push updates.
This is causing them to miss market opportunities. Sarah mentioned the CTO (Mark Chen)
is really frustrated about this. They have about 50 engineers on the team.

Budget-wise, she said they have $200K allocated for DevOps improvements this quarter.
They need to see ROI within 6 months.

They're also looking at our competitor XYZ Solutions. Sounds like XYZ is cheaper but
Sarah's concerned about their support quality. She seems really enthusiastic about
our solution and mentioned she'll be championing it internally.

Timeline is end of Q2 - they want something in place before the summer product launch."""

        result = await agent.run(notes, context)

        # Should proceed with analysis
        assert "response" in result
        assert "MEDDPICC" in result["response"]
        assert "need a bit more context" not in result["response"]

    @pytest.mark.asyncio
    async def test_minimal_with_context_should_proceed(self, agent_context):
        """Test that minimal notes with customer + pain proceed"""
        agent, context = agent_context

        notes = "Quick call with John at TechStartup. They have scaling issues. Looking at solutions. John likes our approach."

        result = await agent.run(notes, context)

        # Should proceed - has customer name + pain point
        assert "response" in result
        assert "MEDDPICC" in result["response"]

    @pytest.mark.asyncio
    async def test_customer_plus_pain_should_proceed(self, agent_context):
        """Test that customer name + pain point is sufficient"""
        agent, context = agent_context

        notes = "meddic bob from jane's bait and tackle wants a custom pos system"

        result = await agent.run(notes, context)

        # Should proceed - has customer + solution need
        assert "response" in result
        assert "MEDDPICC" in result["response"]

    @pytest.mark.asyncio
    async def test_vague_single_sentence_should_clarify(self, agent_context):
        """Test that truly vague input asks for clarification"""
        agent, context = agent_context

        notes = "bob wants software"

        result = await agent.run(notes, context)

        # Should ask for clarification
        assert "response" in result
        assert (
            "need a bit more context" in result["response"]
            or "share more about" in result["response"]
        )

    @pytest.mark.asyncio
    async def test_follow_up_without_context_should_clarify(self, agent_context):
        """Test that vague follow-up without context asks for clarification"""
        agent, context = agent_context

        # This is a follow-up message without the original context
        notes = "they need better reporting in powerbi"

        result = await agent.run(notes, context)

        # Should ask for clarification - too vague without context
        assert "response" in result
        assert (
            "need a bit more context" in result["response"]
            or "share more about" in result["response"]
        )

    @pytest.mark.asyncio
    async def test_very_short_input_should_clarify(self, agent_context):
        """Test that very short input asks for clarification"""
        agent, context = agent_context

        notes = "help with deal"

        result = await agent.run(notes, context)

        # Should ask for clarification
        assert "response" in result
        assert (
            "need a bit more context" in result["response"]
            or "share more about" in result["response"]
        )

    @pytest.mark.asyncio
    async def test_structured_bullets_should_proceed(self, agent_context):
        """Test that structured bullet points proceed"""
        agent, context = agent_context

        notes = """DataCorp Call Notes:
• Pain: Current data pipeline is slow
• Budget: $150K allocated for Q2
• Decision maker: CTO Sarah Park
• Timeline: Need solution by June
• Competition: Looking at StreamZ and DataFast"""

        result = await agent.run(notes, context)

        # Should proceed - structured with multiple elements
        assert "response" in result
        assert "MEDDPICC" in result["response"]
        assert "need a bit more context" not in result["response"]
