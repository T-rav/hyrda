"""Tests for agent registry, router, and agent implementations."""

import os
import sys

import pytest

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.base_agent import BaseAgent
from agents.help_agent import HelpAgent
from agents.meddic_agent import MeddicAgent
from agents.profile_agent import ProfileAgent
from agents.registry import AgentRegistry
from agents.router import CommandRouter


class TestAgentRegistry:
    """Tests for AgentRegistry"""

    def test_registry_initialization(self):
        """Test that registry initializes empty"""
        registry = AgentRegistry()
        assert len(registry.list_agents()) == 0

    def test_register_agent_without_aliases(self):
        """Test registering an agent without aliases"""
        registry = AgentRegistry()

        class TestAgent(BaseAgent):
            name = "test"
            aliases = []

            async def run(self, query, context):
                return {"response": "test"}

        registry.register("test", TestAgent, [])

        assert registry.is_registered("test")
        assert len(registry.list_agents()) == 1

    def test_register_agent_with_aliases(self):
        """Test registering an agent with aliases"""
        registry = AgentRegistry()

        class TestAgent(BaseAgent):
            name = "test"
            aliases = ["t", "tst"]

            async def run(self, query, context):
                return {"response": "test"}

        registry.register("test", TestAgent, ["t", "tst"])

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

        class TestAgent(BaseAgent):
            name = "test"
            aliases = []

            async def run(self, query, context):
                return {"response": "test"}

        registry.register("test", TestAgent, [])

        agent_info = registry.get("test")
        assert agent_info is not None
        assert agent_info["agent_class"] == TestAgent
        assert agent_info["name"] == "test"

    def test_get_agent_by_alias(self):
        """Test getting agent by alias"""
        registry = AgentRegistry()

        class TestAgent(BaseAgent):
            name = "test"
            aliases = ["t"]

            async def run(self, query, context):
                return {"response": "test"}

        registry.register("test", TestAgent, ["t"])

        agent_info = registry.get("t")
        assert agent_info is not None
        assert agent_info["agent_class"] == TestAgent

    def test_get_primary_name_from_alias(self):
        """Test resolving alias to primary name"""
        registry = AgentRegistry()

        class TestAgent(BaseAgent):
            name = "test"
            aliases = ["t"]

            async def run(self, query, context):
                return {"response": "test"}

        registry.register("test", TestAgent, ["t"])

        primary_name = registry.get_primary_name("t")
        assert primary_name == "test"

    def test_get_primary_name_from_primary(self):
        """Test that primary name returns itself"""
        registry = AgentRegistry()

        class TestAgent(BaseAgent):
            name = "test"
            aliases = []

            async def run(self, query, context):
                return {"response": "test"}

        registry.register("test", TestAgent, [])

        primary_name = registry.get_primary_name("test")
        assert primary_name == "test"

    def test_case_insensitive_registration(self):
        """Test that registration is case-insensitive"""
        registry = AgentRegistry()

        class TestAgent(BaseAgent):
            name = "Test"
            aliases = ["T"]

            async def run(self, query, context):
                return {"response": "test"}

        registry.register("Test", TestAgent, ["T"])

        assert registry.is_registered("test")
        assert registry.is_registered("TEST")
        assert registry.is_registered("t")

    def test_list_agents_returns_only_primary(self):
        """Test that list_agents returns only primary agents, not aliases"""
        registry = AgentRegistry()

        class TestAgent1(BaseAgent):
            name = "test1"
            aliases = ["t1", "tst1"]

            async def run(self, query, context):
                return {"response": "test1"}

        class TestAgent2(BaseAgent):
            name = "test2"
            aliases = ["t2"]

            async def run(self, query, context):
                return {"response": "test2"}

        registry.register("test1", TestAgent1, ["t1", "tst1"])
        registry.register("test2", TestAgent2, ["t2"])

        agents = registry.list_agents()
        assert len(agents) == 2
        names = [a["name"] for a in agents]
        assert "test1" in names
        assert "test2" in names
        assert "t1" not in names
        assert "t2" not in names


class TestCommandRouter:
    """Tests for CommandRouter"""

    def test_parse_command_valid(self):
        """Test parsing valid commands"""
        router = CommandRouter(AgentRegistry())

        command, query = router.parse_command("/profile tell me about Charlotte")
        assert command == "profile"
        assert query == "tell me about Charlotte"

    def test_parse_command_no_query(self):
        """Test parsing command without query"""
        router = CommandRouter(AgentRegistry())

        command, query = router.parse_command("/agents")
        assert command == "agents"
        assert query == ""

    def test_parse_command_case_insensitive(self):
        """Test that command parsing is case-insensitive"""
        router = CommandRouter(AgentRegistry())

        command, query = router.parse_command("/PROFILE test")
        assert command == "profile"
        assert query == "test"

    def test_parse_command_invalid(self):
        """Test parsing invalid commands"""
        router = CommandRouter(AgentRegistry())

        command, query = router.parse_command("not a command")
        assert command is None
        assert query == ""

    def test_route_to_registered_agent(self):
        """Test routing to a registered agent"""
        registry = AgentRegistry()

        class TestAgent(BaseAgent):
            name = "test"
            aliases = []

            async def run(self, query, context):
                return {"response": "test"}

        registry.register("test", TestAgent, [])
        router = CommandRouter(registry)

        agent_info, query, primary_name = router.route("/test hello world")

        assert agent_info is not None
        assert agent_info["agent_class"] == TestAgent
        assert query == "hello world"
        assert primary_name == "test"

    def test_route_to_agent_via_alias(self):
        """Test routing to agent via alias"""
        registry = AgentRegistry()

        class TestAgent(BaseAgent):
            name = "test"
            aliases = ["t"]

            async def run(self, query, context):
                return {"response": "test"}

        registry.register("test", TestAgent, ["t"])
        router = CommandRouter(registry)

        agent_info, query, primary_name = router.route("/t hello")

        assert agent_info is not None
        assert agent_info["agent_class"] == TestAgent
        assert query == "hello"
        assert primary_name == "test"  # Resolves to primary name

    def test_route_unregistered_command(self):
        """Test routing unregistered command returns None"""
        registry = AgentRegistry()
        router = CommandRouter(registry)

        agent_info, query, primary_name = router.route("/unknown test")

        assert agent_info is None
        assert query == "test"
        assert primary_name is None

    def test_route_invalid_command(self):
        """Test routing invalid command returns None"""
        registry = AgentRegistry()
        router = CommandRouter(registry)

        agent_info, query, primary_name = router.route("not a command")

        assert agent_info is None
        assert query == ""
        assert primary_name is None

    def test_list_available_commands(self):
        """Test listing available commands"""
        registry = AgentRegistry()

        class TestAgent1(BaseAgent):
            name = "test1"
            aliases = []

            async def run(self, query, context):
                return {"response": "test1"}

        class TestAgent2(BaseAgent):
            name = "test2"
            aliases = []

            async def run(self, query, context):
                return {"response": "test2"}

        registry.register("test1", TestAgent1, [])
        registry.register("test2", TestAgent2, [])
        router = CommandRouter(registry)

        commands = router.list_available_commands()
        assert len(commands) == 2
        assert "test1" in commands
        assert "test2" in commands


class TestBaseAgent:
    """Tests for BaseAgent"""

    def test_agent_requires_name(self):
        """Test that agent must define name"""

        class InvalidAgent(BaseAgent):
            name = ""  # Invalid

            async def run(self, query, context):
                return {"response": "test"}

        with pytest.raises(ValueError, match="must define 'name' attribute"):
            InvalidAgent()

    def test_agent_with_valid_name(self):
        """Test agent with valid name"""

        class ValidAgent(BaseAgent):
            name = "valid"

            async def run(self, query, context):
                return {"response": "test"}

        agent = ValidAgent()
        assert agent.name == "valid"

    def test_validate_context_valid(self):
        """Test context validation with valid context"""

        class TestAgent(BaseAgent):
            name = "test"

            async def run(self, query, context):
                return {"response": "test"}

        agent = TestAgent()
        context = {
            "user_id": "U123",
            "channel": "C123",
            "slack_service": "mock_service",
        }

        assert agent.validate_context(context) is True

    def test_validate_context_missing_fields(self):
        """Test context validation with missing fields"""

        class TestAgent(BaseAgent):
            name = "test"

            async def run(self, query, context):
                return {"response": "test"}

        agent = TestAgent()
        context = {"user_id": "U123"}  # Missing channel and slack_service

        assert agent.validate_context(context) is False

    def test_get_info(self):
        """Test getting agent info"""

        class TestAgent(BaseAgent):
            name = "test"
            aliases = ["t", "tst"]
            description = "Test agent"

            async def run(self, query, context):
                return {"response": "test"}

        agent = TestAgent()
        info = agent.get_info()

        assert info["name"] == "test"
        assert info["aliases"] == ["t", "tst"]
        assert info["description"] == "Test agent"


class TestProfileAgent:
    """Tests for ProfileAgent"""

    @pytest.mark.asyncio
    async def test_profile_agent_run(self):
        """Test ProfileAgent execution"""
        agent = ProfileAgent()
        context = {
            "user_id": "U123",
            "channel": "C123",
            "slack_service": "mock_service",
        }

        result = await agent.run("tell me about Charlotte", context)

        assert "response" in result
        assert "metadata" in result
        assert "Profile Agent" in result["response"]
        assert "Charlotte" in result["response"]

    @pytest.mark.asyncio
    async def test_profile_agent_invalid_context(self):
        """Test ProfileAgent with invalid context"""
        agent = ProfileAgent()
        context = {"user_id": "U123"}  # Missing required fields

        result = await agent.run("test query", context)

        assert "response" in result
        assert "error" in result["metadata"]


class TestMeddicAgent:
    """Tests for MeddicAgent"""

    @pytest.mark.asyncio
    async def test_meddic_agent_run(self):
        """Test MeddicAgent execution"""
        agent = MeddicAgent()
        context = {
            "user_id": "U123",
            "channel": "C123",
            "slack_service": "mock_service",
        }

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
        context = {"user_id": "U123"}  # Missing required fields

        result = await agent.run("test query", context)

        assert "response" in result
        assert "error" in result["metadata"]


class TestHelpAgent:
    """Tests for HelpAgent"""

    @pytest.mark.asyncio
    async def test_help_agent_lists_all_agents(self):
        """Test that HelpAgent lists all registered agents"""
        agent = HelpAgent()
        context = {
            "user_id": "U123",
            "channel": "C123",
            "slack_service": "mock_service",
        }

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
        context = {
            "user_id": "U123",
            "channel": "C123",
            "slack_service": "mock_service",
        }

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
        context = {
            "user_id": "U123",
            "channel": "C123",
            "slack_service": "mock_service",
        }

        result = await agent.run("", context)

        assert "metadata" in result
        assert "agent" in result["metadata"]
        assert result["metadata"]["agent"] == "help"
        assert "agent_count" in result["metadata"]
        assert result["metadata"]["agent_count"] >= 3  # At least 3 agents
