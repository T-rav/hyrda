"""Tests for CommandRouter."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.router import CommandRouter
from tests.agent_test_utils import AgentRegistryMockFactory, TestAgentFactory


class TestCommandRouter:
    """Tests for CommandRouter"""

    def test_parse_command_valid(self):
        """Test parsing valid commands"""
        registry = AgentRegistryMockFactory.create_empty()
        router = CommandRouter(registry)

        command, query = router.parse_command("-profile tell me about Charlotte")
        assert command == "profile"
        assert query == "tell me about Charlotte"

    def test_parse_command_no_query(self):
        """Test parsing command without query"""
        registry = AgentRegistryMockFactory.create_empty()
        router = CommandRouter(registry)

        command, query = router.parse_command("-agents")
        assert command == "agents"
        assert query == ""

    def test_parse_command_case_insensitive(self):
        """Test that command parsing is case-insensitive"""
        registry = AgentRegistryMockFactory.create_empty()
        router = CommandRouter(registry)

        command, query = router.parse_command("-PROFILE test")
        assert command == "profile"
        assert query == "test"

    def test_parse_command_invalid(self):
        """Test parsing invalid commands"""
        registry = AgentRegistryMockFactory.create_empty()
        router = CommandRouter(registry)

        command, query = router.parse_command("not a command")
        assert command is None
        assert query == ""

    def test_route_to_registered_agent(self):
        """Test routing to a registered agent"""
        registry = AgentRegistryMockFactory.create_empty()
        test_agent = TestAgentFactory.create_simple_agent(name="test")
        registry.register("test", test_agent, [])

        router = CommandRouter(registry)
        agent_info, query, primary_name = router.route("-test hello world")

        assert agent_info is not None
        assert agent_info["agent_class"] == test_agent
        assert query == "hello world"
        assert primary_name == "test"

    def test_route_to_agent_via_alias(self):
        """Test routing to agent via alias"""
        registry = AgentRegistryMockFactory.create_empty()
        test_agent = TestAgentFactory.create_agent_with_aliases(
            name="test", aliases=["t"]
        )
        registry.register("test", test_agent, ["t"])

        router = CommandRouter(registry)
        agent_info, query, primary_name = router.route("-t hello")

        assert agent_info is not None
        assert agent_info["agent_class"] == test_agent
        assert query == "hello"
        assert primary_name == "test"  # Resolves to primary name

    def test_route_unregistered_command(self):
        """Test routing unregistered command returns None"""
        registry = AgentRegistryMockFactory.create_empty()
        router = CommandRouter(registry)

        agent_info, query, primary_name = router.route("-unknown test")

        assert agent_info is None
        assert query == "test"
        assert primary_name is None

    def test_route_invalid_command(self):
        """Test routing invalid command returns None"""
        registry = AgentRegistryMockFactory.create_empty()
        router = CommandRouter(registry)

        agent_info, query, primary_name = router.route("not a command")

        assert agent_info is None
        assert query == ""
        assert primary_name is None

    def test_list_available_commands(self):
        """Test listing available commands"""
        registry = AgentRegistryMockFactory.create_with_agents(agent_count=2)
        router = CommandRouter(registry)

        commands = router.list_available_commands()
        assert len(commands) == 2
        assert "test0" in commands
        assert "test1" in commands
