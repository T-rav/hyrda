"""Tests for ProfileAgent."""

import os
import sys
from unittest.mock import AsyncMock, Mock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.profile_agent import ProfileAgent
from services.llm_service import LLMService
from services.slack_service import SlackService
from tests.agent_test_utils import AgentContextBuilder


class TestProfileAgent:
    """Tests for ProfileAgent"""

    @pytest.mark.asyncio
    async def test_profile_agent_run(self):
        """Test ProfileAgent execution"""
        # Mock LLM service for profile agent's LangGraph execution
        llm_service = Mock(spec=LLMService)
        llm_service.get_response = AsyncMock(
            return_value="Please provide more details about what you'd like to know."
        )

        # Mock Slack service
        slack_service = Mock(spec=SlackService)
        slack_service.send_message = AsyncMock()

        context = (
            AgentContextBuilder()
            .with_llm_service(llm_service)
            .with_slack_service(slack_service)
            .build()
        )

        agent = ProfileAgent()
        result = await agent.run("tell me about Charlotte", context)

        assert "response" in result
        assert "metadata" in result
        # Response should contain profile header (e.g., "# Employee Profile" or similar)
        assert "Profile" in result["response"]
        # Check metadata shows it's from profile agent
        assert result["metadata"]["agent"] == "profile"

    @pytest.mark.asyncio
    async def test_profile_agent_invalid_context(self):
        """Test ProfileAgent with invalid context"""
        agent = ProfileAgent()
        context = AgentContextBuilder.invalid_missing_channel()

        result = await agent.run("test query", context)

        assert "response" in result
        assert "error" in result["metadata"]
