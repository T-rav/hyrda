"""Tests for HelpAgent."""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.help_agent import HelpAgent

from tests.agent_test_utils import AgentContextBuilder


class TestHelpAgent:
    """Tests for HelpAgent"""

    @pytest.mark.asyncio
    async def test_help_agent_lists_all_agents(self):
        """Test that HelpAgent lists all registered agents"""
        agent = HelpAgent()
        context = AgentContextBuilder.default()

        result = await agent.run("", context)

        assert "response" in result
        assert "metadata" in result
        response = result["response"]

        # Should list all agents
        assert "profile" in response.lower()
        assert "meddic" in response.lower()
        assert "agents" in response.lower()

        # Should show aliases
        assert "medic" in response.lower()
        assert "help" in response.lower()

    @pytest.mark.asyncio
    async def test_help_agent_shows_usage(self):
        """Test that HelpAgent shows usage examples"""
        agent = HelpAgent()
        context = AgentContextBuilder.default()

        result = await agent.run("", context)

        response = result["response"]
        assert "Usage:" in response or "usage" in response.lower()
        assert "Example:" in response or "example" in response.lower()

    @pytest.mark.asyncio
    async def test_help_agent_has_aliases(self):
        """Test that HelpAgent has help alias"""
        assert "help" in HelpAgent.aliases

    @pytest.mark.asyncio
    async def test_help_agent_metadata(self):
        """Test that HelpAgent returns metadata"""
        agent = HelpAgent()
        context = AgentContextBuilder.default()

        result = await agent.run("", context)

        assert "metadata" in result
        assert "agent" in result["metadata"]
        assert result["metadata"]["agent"] == "help"
        assert "agent_count" in result["metadata"]
        assert result["metadata"]["agent_count"] >= 3  # At least 3 agents
