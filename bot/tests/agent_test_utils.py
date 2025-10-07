"""Test utilities for agent testing.

Provides factories and builders for creating test data following the
established pattern in test_message_handlers.py
"""

from typing import Any
from unittest.mock import Mock

from agents.base_agent import BaseAgent


class AgentContextBuilder:
    """Builder for creating agent context dictionaries"""

    def __init__(self):
        self._user_id = "U123"
        self._channel = "C123"
        self._thread_ts = None
        self._slack_service = "mock_slack_service"
        self._llm_service = None
        self._additional_fields = {}

    def with_user_id(self, user_id: str) -> "AgentContextBuilder":
        self._user_id = user_id
        return self

    def with_channel(self, channel: str) -> "AgentContextBuilder":
        self._channel = channel
        return self

    def with_thread_ts(self, thread_ts: str) -> "AgentContextBuilder":
        self._thread_ts = thread_ts
        return self

    def with_slack_service(self, slack_service: Any) -> "AgentContextBuilder":
        self._slack_service = slack_service
        return self

    def with_llm_service(self, llm_service: Any) -> "AgentContextBuilder":
        self._llm_service = llm_service
        return self

    def with_field(self, key: str, value: Any) -> "AgentContextBuilder":
        self._additional_fields[key] = value
        return self

    def build(self) -> dict[str, Any]:
        """Build the context dictionary"""
        context = {
            "user_id": self._user_id,
            "channel": self._channel,
            "slack_service": self._slack_service,
            **self._additional_fields,
        }

        if self._thread_ts:
            context["thread_ts"] = self._thread_ts

        if self._llm_service:
            context["llm_service"] = self._llm_service

        return context

    @classmethod
    def default(cls) -> dict[str, Any]:
        """Create default context"""
        return cls().build()

    @classmethod
    def with_thread(cls, thread_ts: str = "1234.5678") -> dict[str, Any]:
        """Create context with thread"""
        return cls().with_thread_ts(thread_ts).build()

    @classmethod
    def invalid_missing_channel(cls) -> dict[str, Any]:
        """Create invalid context missing channel"""
        return {"user_id": "U123", "slack_service": "mock"}

    @classmethod
    def invalid_missing_slack_service(cls) -> dict[str, Any]:
        """Create invalid context missing slack_service"""
        return {"user_id": "U123", "channel": "C123"}


class TestAgentFactory:
    """Factory for creating test agent classes"""

    @staticmethod
    def create_simple_agent(
        name: str = "test",
        aliases: list[str] = None,
        description: str = "Test agent",
    ) -> type[BaseAgent]:
        """Create a simple test agent class"""

        # Create concrete implementation with run method
        class SimpleTestAgent(BaseAgent):
            async def run(self, query: str, context: dict[str, Any]) -> dict[str, Any]:
                return {"response": f"Test response for: {query}", "metadata": {}}

        SimpleTestAgent.name = name
        SimpleTestAgent.aliases = aliases or []
        SimpleTestAgent.description = description

        return SimpleTestAgent

    @staticmethod
    def create_agent_with_aliases(
        name: str = "test",
        aliases: list[str] = None,
    ) -> type[BaseAgent]:
        """Create test agent with aliases"""
        return TestAgentFactory.create_simple_agent(
            name=name,
            aliases=aliases or ["t", "tst"],
            description=f"Test agent {name}",
        )


class SlackServiceMockFactory:
    """Factory for creating Slack service mocks for agent tests"""

    @staticmethod
    def create_mock() -> Mock:
        """Create basic Slack service mock"""
        service = Mock()
        service.settings = Mock()
        service.settings.bot_token = "test-token"
        service.send_message = Mock()
        service.send_thinking_indicator = Mock(return_value="thinking_ts")
        service.delete_thinking_indicator = Mock()
        return service


class AgentRegistryMockFactory:
    """Factory for creating AgentRegistry mocks"""

    @staticmethod
    def create_empty() -> Mock:
        """Create empty registry mock"""
        from agents.registry import AgentRegistry

        return AgentRegistry()

    @staticmethod
    def create_with_agents(agent_count: int = 2) -> Mock:
        """Create registry with test agents"""
        from agents.registry import AgentRegistry

        registry = AgentRegistry()

        for i in range(agent_count):
            agent_class = TestAgentFactory.create_simple_agent(
                name=f"test{i}", aliases=[f"t{i}"], description=f"Test agent {i}"
            )
            registry.register(f"test{i}", agent_class, [f"t{i}"])

        return registry
