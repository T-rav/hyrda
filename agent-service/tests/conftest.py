"""Pytest configuration - disable tracing during tests."""

import os
from pathlib import Path

# Load only API keys from .env (needed for evals)
# This must happen BEFORE setting fallback test values
# Only load specific API keys to avoid affecting test defaults
_API_KEYS_TO_LOAD = {
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "LLM_API_KEY",
    "PERPLEXITY_API_KEY",
    "TAVILY_API_KEY",
}


def _load_dotenv():
    """Load API keys from .env file for evals."""
    # Find project root (contains .env)
    current = Path(__file__).resolve().parent
    while current != current.parent:
        env_file = current / ".env"
        if env_file.exists():
            with open(env_file) as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        key = key.strip()
                        # Only load specific API keys
                        if key not in _API_KEYS_TO_LOAD:
                            continue
                        value = value.strip()
                        # Remove surrounding quotes
                        if (value.startswith('"') and value.endswith('"')) or (
                            value.startswith("'") and value.endswith("'")
                        ):
                            value = value[1:-1]
                        # Remove inline comments
                        elif "#" in value:
                            value = value.split("#")[0].strip()
                        # Only set if not already in environment
                        if key and not os.getenv(key):
                            os.environ[key] = value
            break
        current = current.parent


_load_dotenv()

# Set environment variables BEFORE imports (critical for jwt_auth module initialization)
os.environ["OTEL_TRACES_ENABLED"] = "false"
if not os.getenv("AGENT_SERVICE_TOKEN"):
    os.environ["AGENT_SERVICE_TOKEN"] = "fake-test-token-for-testing-only"

# Set CONTROL_PLANE_URL to localhost for integration tests
if not os.getenv("CONTROL_PLANE_URL"):
    os.environ["CONTROL_PLANE_URL"] = "http://localhost:6001"

# Set API keys for tests (required for agent initialization)
if not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = "sk-test-key-for-testing-only"
if not os.getenv("LLM_API_KEY"):
    os.environ["LLM_API_KEY"] = "test-llm-api-key"
if not os.getenv("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = "test-anthropic-api-key"

# Set Slack tokens for tests (required for Settings initialization)
if not os.getenv("SLACK_BOT_TOKEN"):
    os.environ["SLACK_BOT_TOKEN"] = "xoxb-test-token"
if not os.getenv("SLACK_APP_TOKEN"):
    os.environ["SLACK_APP_TOKEN"] = "xapp-test-token"

import sys

# Add project root to Python path to access shared module
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.insert(0, project_root)

from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# =============================================================================
# Agent Mock Builder - Fluent API for creating mock agents
# =============================================================================


class MockAgentBuilder:
    """Builder for creating mock agent classes with fluent API.

    Usage:
        agent = (
            MockAgentBuilder()
            .with_name("research")
            .with_display_name("Research Agent")
            .with_aliases(["researcher"])
            .as_system_agent()
            .build()
        )
    """

    def __init__(self):
        self._name = "test_agent"
        self._display_name = "Test Agent"
        self._description = "A test agent"
        self._aliases: list[str] = []
        self._is_system = False
        self._invoke_response: dict[str, Any] = {"response": "Test response"}

    def with_name(self, name: str) -> "MockAgentBuilder":
        """Set agent name."""
        self._name = name
        return self

    def with_display_name(self, display_name: str) -> "MockAgentBuilder":
        """Set display name."""
        self._display_name = display_name
        return self

    def with_description(self, description: str) -> "MockAgentBuilder":
        """Set description."""
        self._description = description
        return self

    def with_aliases(self, aliases: list[str]) -> "MockAgentBuilder":
        """Set aliases."""
        self._aliases = aliases
        return self

    def as_system_agent(self) -> "MockAgentBuilder":
        """Mark as system agent."""
        self._is_system = True
        return self

    def with_invoke_response(self, response: dict[str, Any]) -> "MockAgentBuilder":
        """Set the response for invoke calls."""
        self._invoke_response = response
        return self

    def build(self) -> MagicMock:
        """Build and return the mock agent class."""
        mock_agent = MagicMock()
        mock_agent.__name__ = f"{self._name.title().replace('_', '')}Agent"
        mock_agent.__agent_metadata__ = {
            "display_name": self._display_name,
            "description": self._description,
            "aliases": self._aliases,
            "is_system": self._is_system,
        }

        # Instance behavior
        mock_instance = MagicMock()
        mock_instance.name = self._name
        mock_instance.invoke = AsyncMock(return_value=self._invoke_response)
        mock_agent.return_value = mock_instance

        return mock_agent


class MockUnifiedLoaderBuilder:
    """Builder for creating mock unified loader with fluent API.

    Usage:
        loader = (
            MockUnifiedLoaderBuilder()
            .with_agent(MockAgentBuilder().with_name("help").build())
            .with_agent(MockAgentBuilder().with_name("research").build())
            .build()
        )
    """

    def __init__(self):
        self._agents: dict[str, Any] = {}

    def with_agent(
        self, agent: MagicMock, name: str | None = None
    ) -> "MockUnifiedLoaderBuilder":
        """Add an agent to the loader."""
        agent_name = name or agent.__agent_metadata__.get(
            "display_name", "test"
        ).lower().replace(" ", "_")
        # Extract base name from metadata if available
        if hasattr(agent, "__agent_metadata__"):
            # Use the first part of display_name as key
            display_name = agent.__agent_metadata__.get("display_name", "")
            if display_name:
                agent_name = display_name.lower().split()[0]
        self._agents[agent_name] = agent
        return self

    def with_agents(self, agents: dict[str, MagicMock]) -> "MockUnifiedLoaderBuilder":
        """Add multiple agents."""
        self._agents.update(agents)
        return self

    def empty(self) -> "MockUnifiedLoaderBuilder":
        """Create an empty loader (no agents)."""
        self._agents = {}
        return self

    def build(self) -> MagicMock:
        """Build and return the mock loader."""
        mock_loader = MagicMock()
        mock_loader.discover_agents.return_value = self._agents
        return mock_loader


# =============================================================================
# Factory Functions - Quick creation of common test fixtures
# =============================================================================


class AgentFixtureFactory:
    """Factory for creating common agent test fixtures."""

    @staticmethod
    def help_agent() -> MagicMock:
        """Create a mock help agent."""
        return (
            MockAgentBuilder()
            .with_name("help")
            .with_display_name("Help Agent")
            .with_description("Helps with questions")
            .with_aliases(["agents"])
            .as_system_agent()
            .build()
        )

    @staticmethod
    def research_agent() -> MagicMock:
        """Create a mock research agent."""
        return (
            MockAgentBuilder()
            .with_name("research")
            .with_display_name("Research Agent")
            .with_description("Conducts research")
            .with_aliases(["researcher"])
            .build()
        )

    @staticmethod
    def profile_agent() -> MagicMock:
        """Create a mock profile agent."""
        return (
            MockAgentBuilder()
            .with_name("profile")
            .with_display_name("Profile Agent")
            .with_description("Creates company profiles")
            .with_aliases(["profiler"])
            .build()
        )

    @staticmethod
    def meddic_agent() -> MagicMock:
        """Create a mock MEDDIC agent."""
        return (
            MockAgentBuilder()
            .with_name("meddic")
            .with_display_name("MEDDIC Agent")
            .with_description("MEDDIC qualification")
            .build()
        )

    @staticmethod
    def standard_loader() -> MagicMock:
        """Create a loader with standard agents (help, profile, meddic)."""
        return (
            MockUnifiedLoaderBuilder()
            .with_agents(
                {
                    "help": AgentFixtureFactory.help_agent(),
                    "profile": AgentFixtureFactory.profile_agent(),
                    "meddic": AgentFixtureFactory.meddic_agent(),
                }
            )
            .build()
        )


# =============================================================================
# Pytest Fixtures
# =============================================================================


@pytest.fixture
def mock_agent_builder():
    """Provide MockAgentBuilder for tests."""
    return MockAgentBuilder


@pytest.fixture
def mock_loader_builder():
    """Provide MockUnifiedLoaderBuilder for tests."""
    return MockUnifiedLoaderBuilder


@pytest.fixture
def agent_factory():
    """Provide AgentFixtureFactory for tests."""
    return AgentFixtureFactory


@pytest.fixture
def standard_mock_loader():
    """Provide a standard mock loader with common agents."""
    return AgentFixtureFactory.standard_loader()


@pytest.fixture
def mock_unified_loader_env(standard_mock_loader):
    """Set up mock unified loader environment for tests.

    This fixture:
    1. Clears agent registry caches
    2. Patches the unified loader
    3. Mocks control plane to return agent metadata with aliases
    4. Yields for test execution
    """
    import services.agent_registry as registry_module

    # Clear all caches
    registry_module._agent_classes = {}
    registry_module._cached_agents = None
    registry_module._cache_timestamp = 0

    # Mock control plane response with agent metadata and aliases
    mock_cp_response = Mock()
    mock_cp_response.status_code = 200
    mock_cp_response.json.return_value = {
        "agents": [
            {
                "name": "help",
                "display_name": "Help Agent",
                "description": "Helps with questions",
                "aliases": ["agents"],
                "is_enabled": True,
                "is_system": True,
            },
            {
                "name": "profile",
                "display_name": "Profile Agent",
                "description": "Creates company profiles",
                "aliases": ["profiler"],
                "is_enabled": True,
                "is_system": False,
            },
            {
                "name": "meddic",
                "display_name": "MEDDIC Agent",
                "description": "MEDDIC qualification",
                "aliases": [],
                "is_enabled": True,
                "is_system": False,
            },
        ]
    }

    with (
        patch(
            "services.unified_agent_loader.get_unified_loader",
            return_value=standard_mock_loader,
        ),
        patch("requests.get", return_value=mock_cp_response),
    ):
        yield standard_mock_loader


@pytest.fixture(autouse=True)
def mock_openai_client(request):
    """Mock OpenAI client for unit tests to avoid actual API calls.

    Skips mocking for eval tests (marked with @pytest.mark.eval) which need
    real API calls.
    """
    # Skip mocking for eval tests
    if request.node.get_closest_marker("eval"):
        yield None
        return

    # Skip mocking for tests in evals directory
    if "evals" in str(request.fspath):
        yield None
        return

    with patch("openai.AsyncOpenAI") as mock_client:
        # Create a mock instance
        mock_instance = Mock()
        mock_instance.chat = Mock()
        mock_instance.chat.completions = Mock()
        mock_instance.chat.completions.create = AsyncMock(
            return_value=Mock(
                choices=[Mock(message=Mock(content="Test response"))],
                usage=Mock(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            )
        )
        mock_client.return_value = mock_instance
        yield mock_client
