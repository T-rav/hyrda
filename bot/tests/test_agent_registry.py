"""Tests for AgentRegistry (declarative HTTP-based architecture)."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.registry import AgentRegistry


class TestAgentRegistry:
    """Tests for declarative AgentRegistry"""

    def test_registry_initialization(self):
        """Test that registry initializes with pre-registered agents"""
        registry = AgentRegistry()
        agents = registry.list_agents()
        # Registry now has agents pre-registered (research, profile, meddic, help)
        assert len(agents) >= 4
        agent_names = {a["name"] for a in agents}
        assert "research" in agent_names
        assert "profile" in agent_names
        assert "meddic" in agent_names
        assert "help" in agent_names

    def test_list_agents_returns_all(self):
        """Test that list_agents returns all pre-registered agents"""
        registry = AgentRegistry()
        agents = registry.list_agents()
        assert isinstance(agents, list)
        assert len(agents) >= 4
        for agent in agents:
            assert "name" in agent
            assert "display_name" in agent
            assert "description" in agent
            assert "aliases" in agent

    def test_get_agent_by_name(self):
        """Test getting agent by name"""
        registry = AgentRegistry()

        research_agent = registry.get_agent("research")
        assert research_agent is not None
        assert research_agent["name"] == "research"
        assert research_agent["display_name"] == "Research Agent"
        assert "research" in research_agent["aliases"]

    def test_get_agent_nonexistent(self):
        """Test getting nonexistent agent returns None"""
        registry = AgentRegistry()

        agent = registry.get_agent("nonexistent")
        assert agent is None

    def test_research_agent_metadata(self):
        """Test research agent has correct metadata"""
        registry = AgentRegistry()

        agent = registry.get_agent("research")
        assert agent is not None
        assert agent["name"] == "research"
        assert agent["display_name"] == "Research Agent"
        assert agent["description"] == "Deep research on any topic"
        assert isinstance(agent["aliases"], list)
        assert "research" in agent["aliases"]

    def test_profile_agent_metadata(self):
        """Test profile agent has correct metadata"""
        registry = AgentRegistry()

        agent = registry.get_agent("profile")
        assert agent is not None
        assert agent["name"] == "profile"
        assert agent["display_name"] == "Company Profile Agent"
        assert agent["description"] == "Generate company profiles"
        assert "profile" in agent["aliases"]

    def test_meddic_agent_metadata(self):
        """Test meddic agent has correct metadata"""
        registry = AgentRegistry()

        agent = registry.get_agent("meddic")
        assert agent is not None
        assert agent["name"] == "meddic"
        assert agent["display_name"] == "MEDDIC Coach"
        assert agent["description"] == "Deal coaching and analysis"
        assert "meddic" in agent["aliases"]

    def test_help_agent_metadata(self):
        """Test help agent has correct metadata"""
        registry = AgentRegistry()

        agent = registry.get_agent("help")
        assert agent is not None
        assert agent["name"] == "help"
        assert agent["display_name"] == "Help Agent"
        assert agent["description"] == "List available agents and help"
        assert "help" in agent["aliases"]
