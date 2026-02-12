"""Tests for unified_agent_loader.py."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.unified_agent_loader import UnifiedAgentLoader, get_unified_loader


@pytest.fixture
def mock_langgraph_config(tmp_path):
    """Create a mock langgraph.json file."""
    config = {
        "dependencies": [".", "./custom_agents"],
        "graphs": {
            "test_agent": "test_module:build_test_agent",
            "another_agent": {"graph": "another_module:build_another"},
        },
        "env": ".env",
    }
    config_file = tmp_path / "langgraph.json"
    config_file.write_text(json.dumps(config))
    return config_file


def test_unified_loader_initialization(mock_langgraph_config):
    """Test UnifiedAgentLoader initializes with config path."""
    loader = UnifiedAgentLoader(str(mock_langgraph_config))
    assert loader.config_path == Path(mock_langgraph_config)
    assert loader._loaded_agents == {}


def test_discover_agents_missing_config(tmp_path):
    """Test discover_agents when config file doesn't exist."""
    loader = UnifiedAgentLoader(str(tmp_path / "missing.json"))
    agents = loader.discover_agents()
    assert agents == {}


def test_discover_agents_invalid_json(tmp_path):
    """Test discover_agents with invalid JSON."""
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text("{ invalid json }")
    loader = UnifiedAgentLoader(str(invalid_file))
    agents = loader.discover_agents()
    assert agents == {}


def test_discover_agents_no_graphs(tmp_path):
    """Test discover_agents when config has no graphs."""
    config = {"dependencies": ["."], "env": ".env"}
    config_file = tmp_path / "langgraph.json"
    config_file.write_text(json.dumps(config))
    loader = UnifiedAgentLoader(str(config_file))
    agents = loader.discover_agents()
    assert agents == {}


def test_discover_agents_with_string_spec(mock_langgraph_config):
    """Test discover_agents with string graph spec."""
    loader = UnifiedAgentLoader(str(mock_langgraph_config))

    # Mock the module import and builder function
    mock_graph = MagicMock()
    with patch("services.unified_agent_loader.importlib.import_module") as mock_import:
        mock_module = MagicMock()
        mock_module.build_test_agent = MagicMock(return_value=mock_graph)
        mock_import.return_value = mock_module

        agents = loader.discover_agents()

        assert "test_agent" in agents
        assert agents["test_agent"] == mock_graph


def test_discover_agents_with_dict_spec(mock_langgraph_config):
    """Test discover_agents with dict graph spec."""
    loader = UnifiedAgentLoader(str(mock_langgraph_config))

    # Mock the module import and builder function
    mock_graph = MagicMock()
    with patch("services.unified_agent_loader.importlib.import_module") as mock_import:
        mock_module = MagicMock()
        mock_module.build_another = MagicMock(return_value=mock_graph)
        mock_import.return_value = mock_module

        agents = loader.discover_agents()

        assert "another_agent" in agents
        assert agents["another_agent"] == mock_graph


def test_discover_agents_caches_results(mock_langgraph_config):
    """Test that discover_agents caches results."""
    loader = UnifiedAgentLoader(str(mock_langgraph_config))

    mock_graph = MagicMock()
    with patch("services.unified_agent_loader.importlib.import_module") as mock_import:
        mock_module = MagicMock()
        mock_module.build_test_agent = MagicMock(return_value=mock_graph)
        mock_import.return_value = mock_module

        # First call
        agents1 = loader.discover_agents()
        assert len(agents1) > 0

        # Second call should use cache (mock won't be called again)
        mock_import.reset_mock()
        agents2 = loader.discover_agents()

        assert agents1 == agents2
        mock_import.assert_not_called()


def test_load_graph_invalid_spec(mock_langgraph_config):
    """Test _load_graph with invalid spec."""
    loader = UnifiedAgentLoader(str(mock_langgraph_config))

    # Invalid spec (no colon)
    result = loader._load_graph("test", "invalid_spec")
    assert result is None

    # Dict without graph key
    result = loader._load_graph("test", {"foo": "bar"})
    assert result is None


def test_load_graph_module_not_found(mock_langgraph_config):
    """Test _load_graph when module doesn't exist."""
    loader = UnifiedAgentLoader(str(mock_langgraph_config))

    with patch(
        "services.unified_agent_loader.importlib.import_module",
        side_effect=ModuleNotFoundError("Module not found"),
    ):
        result = loader._load_graph("test", "missing_module:build_agent")
        assert result is None


def test_load_graph_function_not_found(mock_langgraph_config):
    """Test _load_graph when builder function doesn't exist."""
    loader = UnifiedAgentLoader(str(mock_langgraph_config))

    with patch("services.unified_agent_loader.importlib.import_module") as mock_import:
        mock_module = MagicMock(spec=[])  # No attributes
        mock_import.return_value = mock_module

        result = loader._load_graph("test", "test_module:missing_function")
        assert result is None


def test_load_graph_builder_raises_exception(mock_langgraph_config):
    """Test _load_graph when builder function raises exception."""
    loader = UnifiedAgentLoader(str(mock_langgraph_config))

    with patch("services.unified_agent_loader.importlib.import_module") as mock_import:
        mock_module = MagicMock()
        mock_module.build_test = MagicMock(side_effect=Exception("Build failed"))
        mock_import.return_value = mock_module

        result = loader._load_graph("test", "test_module:build_test")
        assert result is None


def test_get_unified_loader_singleton():
    """Test that get_unified_loader returns singleton."""
    loader1 = get_unified_loader()
    loader2 = get_unified_loader()
    assert loader1 is loader2
