"""Tests for AgentRegistry."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.registry import AgentRegistry
from tests.agent_test_utils import TestAgentFactory


class TestAgentRegistry:
    """Tests for AgentRegistry"""

    def test_registry_initialization(self):
        """Test that registry initializes empty"""
        registry = AgentRegistry()
        assert len(registry.list_agents()) == 0

    def test_register_agent_without_aliases(self):
        """Test registering an agent without aliases"""
        registry = AgentRegistry()
        test_agent = TestAgentFactory.create_simple_agent(name="test", aliases=[])

        registry.register("test", test_agent, [])

        assert registry.is_registered("test")
        assert len(registry.list_agents()) == 1

    def test_register_agent_with_aliases(self):
        """Test registering an agent with aliases"""
        registry = AgentRegistry()
        test_agent = TestAgentFactory.create_agent_with_aliases(
            name="test", aliases=["t", "tst"]
        )

        registry.register("test", test_agent, ["t", "tst"])

        # Primary name is registered
        assert registry.is_registered("test")
        # Aliases are registered
        assert registry.is_registered("t")
        assert registry.is_registered("tst")
        # Only one primary agent in list
        assert len(registry.list_agents()) == 1

    def test_get_agent_by_name(self):
        """Test getting agent by primary name"""
        registry = AgentRegistry()
        test_agent = TestAgentFactory.create_simple_agent(name="test")

        registry.register("test", test_agent, [])

        agent_info = registry.get("test")
        assert agent_info is not None
        assert agent_info["agent_class"] == test_agent
        assert agent_info["name"] == "test"

    def test_get_agent_by_alias(self):
        """Test getting agent by alias"""
        registry = AgentRegistry()
        test_agent = TestAgentFactory.create_agent_with_aliases(
            name="test", aliases=["t"]
        )

        registry.register("test", test_agent, ["t"])

        agent_info = registry.get("t")
        assert agent_info is not None
        assert agent_info["agent_class"] == test_agent

    def test_get_primary_name_from_alias(self):
        """Test resolving alias to primary name"""
        registry = AgentRegistry()
        test_agent = TestAgentFactory.create_agent_with_aliases(
            name="test", aliases=["t"]
        )

        registry.register("test", test_agent, ["t"])

        primary_name = registry.get_primary_name("t")
        assert primary_name == "test"

    def test_get_primary_name_from_primary(self):
        """Test that primary name returns itself"""
        registry = AgentRegistry()
        test_agent = TestAgentFactory.create_simple_agent(name="test")

        registry.register("test", test_agent, [])

        primary_name = registry.get_primary_name("test")
        assert primary_name == "test"

    def test_case_insensitive_registration(self):
        """Test that registration is case-insensitive"""
        registry = AgentRegistry()
        test_agent = TestAgentFactory.create_agent_with_aliases(
            name="Test", aliases=["T"]
        )

        registry.register("Test", test_agent, ["T"])

        assert registry.is_registered("test")
        assert registry.is_registered("TEST")
        assert registry.is_registered("t")

    def test_list_agents_returns_only_primary(self):
        """Test that list_agents returns only primary agents, not aliases"""
        registry = AgentRegistry()
        test_agent1 = TestAgentFactory.create_agent_with_aliases(
            name="test1", aliases=["t1", "tst1"]
        )
        test_agent2 = TestAgentFactory.create_agent_with_aliases(
            name="test2", aliases=["t2"]
        )

        registry.register("test1", test_agent1, ["t1", "tst1"])
        registry.register("test2", test_agent2, ["t2"])

        agents = registry.list_agents()
        assert len(agents) == 2
        names = [a["name"] for a in agents]
        assert "test1" in names
        assert "test2" in names
        assert "t1" not in names
        assert "t2" not in names
