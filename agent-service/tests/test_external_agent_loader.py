"""Unit tests for ExternalAgentLoader (external agent loading system).

All tests are pure unit tests using mocking and temporary directories.
No integration with real external agents or databases.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.external_agent_loader import (
    ExternalAgentLoader,
    get_external_loader,
    reload_external_agent,
)


@pytest.fixture
def temp_agents_dir(tmp_path):
    """Create temporary agents directory for testing."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    return agents_dir


@pytest.fixture
def simple_agent_code():
    """Simple agent code for testing."""
    return '''
class Agent:
    """Test agent."""
    def __init__(self):
        self.name = "test"

    async def invoke(self, query: str, context: dict) -> dict:
        return {"response": f"Echo: {query}", "metadata": {}}
'''


class TestExternalAgentLoaderInitialization:
    """Test ExternalAgentLoader initialization."""

    def test_initialization_with_path(self):
        """Test initialization with explicit path."""
        loader = ExternalAgentLoader("/custom/path")
        assert loader.external_path == "/custom/path"

    def test_initialization_from_env(self):
        """Test initialization from environment variable."""
        with patch.dict(os.environ, {"EXTERNAL_AGENTS_PATH": "/env/path"}):
            loader = ExternalAgentLoader()
            assert loader.external_path == "/env/path"

    def test_initialization_no_path(self):
        """Test initialization without path."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("EXTERNAL_AGENTS_PATH", None)
            loader = ExternalAgentLoader()
            assert loader.external_path is None


class TestAgentDiscovery:
    """Test agent discovery functionality."""

    def test_discover_agents_no_path(self):
        """Test discovery with no external path configured."""
        loader = ExternalAgentLoader(external_agents_path=None)
        agents = loader.discover_agents()
        assert agents == {}

    def test_discover_agents_missing_directory(self):
        """Test discovery when directory doesn't exist."""
        loader = ExternalAgentLoader("/nonexistent/path")
        agents = loader.discover_agents()
        assert agents == {}

    def test_discover_single_agent(self, temp_agents_dir, simple_agent_code):
        """Test discovering a single valid agent."""
        # Create agent directory and file
        agent_dir = temp_agents_dir / "test_agent"
        agent_dir.mkdir()
        agent_file = agent_dir / "agent.py"
        agent_file.write_text(simple_agent_code)

        loader = ExternalAgentLoader(str(temp_agents_dir))
        agents = loader.discover_agents()

        assert "test_agent" in agents
        assert agents["test_agent"].__name__ == "Agent"

    def test_discover_multiple_agents(self, temp_agents_dir, simple_agent_code):
        """Test discovering multiple agents."""
        # Create two agents
        for agent_name in ["agent1", "agent2"]:
            agent_dir = temp_agents_dir / agent_name
            agent_dir.mkdir()
            agent_file = agent_dir / "agent.py"
            agent_file.write_text(simple_agent_code)

        loader = ExternalAgentLoader(str(temp_agents_dir))
        agents = loader.discover_agents()

        assert len(agents) == 2
        assert "agent1" in agents
        assert "agent2" in agents

    def test_skip_directory_without_agent_py(self, temp_agents_dir):
        """Test skipping directories without agent.py."""
        # Create directory without agent.py
        invalid_dir = temp_agents_dir / "invalid_agent"
        invalid_dir.mkdir()
        (invalid_dir / "other.py").write_text("# Not agent.py")

        loader = ExternalAgentLoader(str(temp_agents_dir))
        agents = loader.discover_agents()

        assert "invalid_agent" not in agents

    def test_skip_underscore_directories(self, temp_agents_dir, simple_agent_code):
        """Test skipping directories starting with underscore."""
        # Create _private directory
        private_dir = temp_agents_dir / "_private"
        private_dir.mkdir()
        (private_dir / "agent.py").write_text(simple_agent_code)

        loader = ExternalAgentLoader(str(temp_agents_dir))
        agents = loader.discover_agents()

        assert "_private" not in agents

    def test_handle_invalid_agent_code(self, temp_agents_dir):
        """Test handling of invalid Python code in agent.py."""
        agent_dir = temp_agents_dir / "broken_agent"
        agent_dir.mkdir()
        agent_file = agent_dir / "agent.py"
        agent_file.write_text("this is not valid python {{{")

        loader = ExternalAgentLoader(str(temp_agents_dir))
        agents = loader.discover_agents()

        # Should skip broken agent and continue
        assert "broken_agent" not in agents

    def test_handle_missing_agent_class(self, temp_agents_dir):
        """Test handling of agent.py without Agent class."""
        agent_dir = temp_agents_dir / "no_class_agent"
        agent_dir.mkdir()
        agent_file = agent_dir / "agent.py"
        agent_file.write_text("# Valid Python but no Agent class\nclass Other: pass")

        loader = ExternalAgentLoader(str(temp_agents_dir))
        agents = loader.discover_agents()

        assert "no_class_agent" not in agents


class TestAgentLoading:
    """Test agent loading and module management."""

    def test_load_agent_with_relative_imports(self, temp_agents_dir):
        """Test loading agent with relative imports."""
        agent_dir = temp_agents_dir / "complex_agent"
        agent_dir.mkdir()

        # Create helper module
        (agent_dir / "helper.py").write_text("def helper(): return 'helped'")

        # Create agent that imports helper
        agent_code = '''
from helper import helper

class Agent:
    def __init__(self):
        self.name = helper()

    async def invoke(self, query: str, context: dict) -> dict:
        return {"response": self.name, "metadata": {}}
'''
        (agent_dir / "agent.py").write_text(agent_code)

        loader = ExternalAgentLoader(str(temp_agents_dir))
        agents = loader.discover_agents()

        assert "complex_agent" in agents
        # Agent should load successfully with helper imported

    def test_get_agent_class(self, temp_agents_dir, simple_agent_code):
        """Test getting agent class by name."""
        agent_dir = temp_agents_dir / "test_agent"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text(simple_agent_code)

        loader = ExternalAgentLoader(str(temp_agents_dir))
        loader.discover_agents()

        agent_class = loader.get_agent_class("test_agent")
        assert agent_class is not None
        assert agent_class.__name__ == "Agent"

    def test_get_nonexistent_agent_class(self, temp_agents_dir):
        """Test getting non-existent agent class."""
        loader = ExternalAgentLoader(str(temp_agents_dir))
        loader.discover_agents()

        agent_class = loader.get_agent_class("nonexistent")
        assert agent_class is None

    def test_list_external_agents(self, temp_agents_dir, simple_agent_code):
        """Test listing all loaded agent names."""
        # Create two agents
        for agent_name in ["agent1", "agent2"]:
            agent_dir = temp_agents_dir / agent_name
            agent_dir.mkdir()
            (agent_dir / "agent.py").write_text(simple_agent_code)

        loader = ExternalAgentLoader(str(temp_agents_dir))
        loader.discover_agents()

        agent_names = loader.list_external_agents()
        assert sorted(agent_names) == ["agent1", "agent2"]


class TestAgentReload:
    """Test agent hot-reload functionality."""

    def test_reload_agent_success(self, temp_agents_dir, simple_agent_code):
        """Test successfully reloading an agent."""
        agent_dir = temp_agents_dir / "test_agent"
        agent_dir.mkdir()
        agent_file = agent_dir / "agent.py"
        agent_file.write_text(simple_agent_code)

        loader = ExternalAgentLoader(str(temp_agents_dir))
        loader.discover_agents()

        # Modify agent code
        modified_code = simple_agent_code.replace('"test"', '"modified"')
        agent_file.write_text(modified_code)

        # Reload
        reloaded_class = loader.reload_agent("test_agent")
        assert reloaded_class is not None

    def test_reload_nonexistent_agent(self, temp_agents_dir):
        """Test reloading non-existent agent."""
        loader = ExternalAgentLoader(str(temp_agents_dir))
        loader.discover_agents()

        result = loader.reload_agent("nonexistent")
        assert result is None

    def test_reload_without_path(self):
        """Test reload fails gracefully without external path."""
        loader = ExternalAgentLoader(external_agents_path=None)
        result = loader.reload_agent("any_agent")
        assert result is None

    def test_reload_removes_from_cache(self, temp_agents_dir, simple_agent_code):
        """Test that reload removes agent from cache."""
        agent_dir = temp_agents_dir / "test_agent"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text(simple_agent_code)

        loader = ExternalAgentLoader(str(temp_agents_dir))
        loader.discover_agents()

        # Verify in cache
        assert "test_agent" in loader._loaded_agents

        # Reload
        loader.reload_agent("test_agent")

        # Should still be in cache after reload
        assert "test_agent" in loader._loaded_agents


class TestGlobalLoader:
    """Test global loader singleton."""

    def test_get_external_loader_singleton(self):
        """Test that get_external_loader returns same instance."""
        # Reset global
        import services.external_agent_loader as loader_module

        loader_module._external_loader = None

        loader1 = get_external_loader()
        loader2 = get_external_loader()

        assert loader1 is loader2

    def test_reload_external_agent_function(self, temp_agents_dir, simple_agent_code):
        """Test global reload_external_agent function."""
        # Create agent
        agent_dir = temp_agents_dir / "test_agent"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text(simple_agent_code)

        # Reset global and set path
        import services.external_agent_loader as loader_module

        loader_module._external_loader = ExternalAgentLoader(str(temp_agents_dir))
        get_external_loader().discover_agents()

        # Reload via function
        result = reload_external_agent("test_agent")
        assert result is True

    def test_reload_external_agent_failure(self):
        """Test global reload function with non-existent agent."""
        import services.external_agent_loader as loader_module

        loader_module._external_loader = ExternalAgentLoader()

        result = reload_external_agent("nonexistent")
        assert result is False


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_agent_file(self, temp_agents_dir):
        """Test handling of empty agent.py file."""
        agent_dir = temp_agents_dir / "empty_agent"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text("")

        loader = ExternalAgentLoader(str(temp_agents_dir))
        agents = loader.discover_agents()

        assert "empty_agent" not in agents

    def test_agent_with_syntax_errors(self, temp_agents_dir):
        """Test handling of agent with syntax errors."""
        agent_dir = temp_agents_dir / "syntax_error_agent"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text("class Agent:\n    def __init__(self")  # Missing closing

        loader = ExternalAgentLoader(str(temp_agents_dir))
        agents = loader.discover_agents()

        assert "syntax_error_agent" not in agents

    def test_agent_with_import_errors(self, temp_agents_dir):
        """Test handling of agent with import errors."""
        agent_dir = temp_agents_dir / "import_error_agent"
        agent_dir.mkdir()
        agent_code = '''
import nonexistent_module

class Agent:
    pass
'''
        (agent_dir / "agent.py").write_text(agent_code)

        loader = ExternalAgentLoader(str(temp_agents_dir))
        agents = loader.discover_agents()

        # Should fail to load
        assert "import_error_agent" not in agents

    def test_discover_agents_caches_results(self, temp_agents_dir, simple_agent_code):
        """Test that multiple discoveries don't reload agents unnecessarily."""
        agent_dir = temp_agents_dir / "test_agent"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text(simple_agent_code)

        loader = ExternalAgentLoader(str(temp_agents_dir))

        # First discovery
        agents1 = loader.discover_agents()

        # Second discovery - should return same classes
        agents2 = loader.discover_agents()

        assert agents1["test_agent"] is agents2["test_agent"]
