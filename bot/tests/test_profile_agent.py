"""Tests for ProfileAgent."""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.profile_agent import ProfileAgent
from tests.agent_test_utils import AgentContextBuilder


class TestProfileAgent:
    """Tests for ProfileAgent"""

    @pytest.mark.asyncio
    async def test_profile_agent_run(self):
        """Test ProfileAgent execution"""
        agent = ProfileAgent()
        context = AgentContextBuilder.default()

        result = await agent.run("tell me about Charlotte", context)

        assert "response" in result
        assert "metadata" in result
        assert "Profile Agent" in result["response"]
        assert "Charlotte" in result["response"]

    @pytest.mark.asyncio
    async def test_profile_agent_invalid_context(self):
        """Test ProfileAgent with invalid context"""
        agent = ProfileAgent()
        context = AgentContextBuilder.invalid_missing_channel()

        result = await agent.run("test query", context)

        assert "response" in result
        assert "error" in result["metadata"]
