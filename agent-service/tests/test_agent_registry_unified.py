"""Tests for agent_registry.py with unified loader."""

from unittest.mock import MagicMock, patch

import pytest

from services import agent_registry


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset agent registry globals before each test."""
    agent_registry._agent_classes = {}
    agent_registry._cached_agents = None
    agent_registry._cache_timestamp = 0
    yield
    agent_registry._agent_classes = {}
    agent_registry._cached_agents = None
    agent_registry._cache_timestamp = 0


def test_load_agent_classes_success():
    """Test _load_agent_classes successfully loads agents."""
    mock_agents = {"agent1": MagicMock(), "agent2": MagicMock()}

    with patch("services.unified_agent_loader.get_unified_loader") as mock_get_loader:
        mock_loader = MagicMock()
        mock_loader.discover_agents.return_value = mock_agents
        mock_get_loader.return_value = mock_loader

        result = agent_registry._load_agent_classes()

        assert result == mock_agents
        assert agent_registry._agent_classes == mock_agents


def test_load_agent_classes_returns_cached():
    """Test _load_agent_classes returns cached results."""
    mock_agents = {"agent1": MagicMock()}
    agent_registry._agent_classes = mock_agents

    with patch("services.unified_agent_loader.get_unified_loader") as mock_get_loader:
        result = agent_registry._load_agent_classes()

        assert result == mock_agents
        mock_get_loader.assert_not_called()


def test_load_agent_classes_no_agents_no_cache():
    """Test _load_agent_classes doesn't cache when no agents loaded."""
    with patch("services.unified_agent_loader.get_unified_loader") as mock_get_loader:
        mock_loader = MagicMock()
        mock_loader.discover_agents.return_value = {}
        mock_get_loader.return_value = mock_loader

        result = agent_registry._load_agent_classes()

        assert result == {}
        assert agent_registry._agent_classes == {}  # Not cached


def test_load_agent_classes_exception():
    """Test _load_agent_classes handles exceptions."""
    with patch(
        "services.unified_agent_loader.get_unified_loader",
        side_effect=Exception("Load failed"),
    ):
        result = agent_registry._load_agent_classes()

        assert result == {}
        assert agent_registry._agent_classes == {}


def test_get_agent_registry_empty_not_cached():
    """Test get_agent_registry doesn't cache empty registry."""
    with patch("services.agent_registry._load_agent_classes") as mock_load:
        mock_load.return_value = {}

        result = agent_registry.get_agent_registry(force_refresh=True)

        assert result == {}
        assert agent_registry._cached_agents is None  # Not cached


def test_get_agent_registry_success():
    """Test get_agent_registry successfully builds registry."""
    mock_agents = {
        "agent1": MagicMock(),
        "agent2": MagicMock(),
    }

    with patch("services.agent_registry._load_agent_classes") as mock_load:
        mock_load.return_value = mock_agents

        result = agent_registry.get_agent_registry(force_refresh=True)

        assert len(result) == 2
        assert "agent1" in result
        assert "agent2" in result
        assert result["agent1"]["agent_class"] == mock_agents["agent1"]
        assert agent_registry._cached_agents == result  # Cached


def test_get_agent_registry_returns_cached():
    """Test get_agent_registry returns cached non-empty registry."""
    mock_registry = {
        "agent1": {"name": "agent1", "agent_class": MagicMock()},
    }
    agent_registry._cached_agents = mock_registry
    agent_registry._cache_timestamp = 999999999999  # Far future

    with patch("services.agent_registry._load_agent_classes") as mock_load:
        result = agent_registry.get_agent_registry()

        assert result == mock_registry
        mock_load.assert_not_called()


def test_get_agent_registry_skips_empty_cache():
    """Test get_agent_registry doesn't return empty cache."""
    agent_registry._cached_agents = {}  # Empty cache
    agent_registry._cache_timestamp = 999999999

    mock_agents = {"agent1": MagicMock()}
    with patch("services.agent_registry._load_agent_classes") as mock_load:
        mock_load.return_value = mock_agents

        result = agent_registry.get_agent_registry()

        # Should reload since cache was empty
        mock_load.assert_called_once()
        assert len(result) == 1


def test_get_agent_registry_with_control_plane_metadata():
    """Test get_agent_registry merges control plane metadata."""
    mock_agents = {"agent1": MagicMock()}

    with patch("services.agent_registry._load_agent_classes") as mock_load:
        mock_load.return_value = mock_agents

        # Mock control plane response
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "agents": [
                    {
                        "name": "agent1",
                        "display_name": "Agent One",
                        "description": "Test agent",
                        "aliases": ["a1"],
                        "requires_admin": False,
                        "is_system": False,
                    }
                ]
            }
            mock_get.return_value = mock_response

            result = agent_registry.get_agent_registry(force_refresh=True)

            assert result["agent1"]["display_name"] == "Agent One"
            assert result["agent1"]["description"] == "Test agent"
            assert result["agent1"]["aliases"] == ["a1"]
            assert "a1" in result  # Alias registered


def test_get_agent_registry_control_plane_unavailable():
    """Test get_agent_registry works when control plane unavailable."""
    mock_agents = {"agent1": MagicMock()}

    with patch("services.agent_registry._load_agent_classes") as mock_load:
        mock_load.return_value = mock_agents

        with patch("requests.get", side_effect=Exception("Unavailable")):
            result = agent_registry.get_agent_registry(force_refresh=True)

            # Should still return agents from local registry
            assert len(result) == 1
            assert "agent1" in result


def test_get_agent_registry_merges_is_enabled_from_control_plane():
    """Test that is_enabled from control plane overrides local default."""
    mock_agents = {"agent1": MagicMock()}

    with patch("services.agent_registry._load_agent_classes") as mock_load:
        mock_load.return_value = mock_agents

        # Mock control plane response with is_enabled=False
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "agents": [
                    {
                        "name": "agent1",
                        "display_name": "Agent One",
                        "description": "Test agent",
                        "aliases": [],
                        "is_enabled": False,  # Disabled in control plane
                        "requires_admin": False,
                        "is_system": False,
                    }
                ]
            }
            mock_get.return_value = mock_response

            result = agent_registry.get_agent_registry(force_refresh=True)

            # Verify is_enabled was updated from control plane
            assert result["agent1"]["is_enabled"] is False


def test_list_agents():
    """Test list_agents returns primary agents only."""
    mock_registry = {
        "agent1": {"name": "agent1", "is_primary": True},
        "agent2": {"name": "agent2", "is_primary": True},
        "a1": {"name": "agent1", "is_primary": False},  # alias
    }

    with patch("services.agent_registry.get_agent_registry") as mock_get:
        mock_get.return_value = mock_registry

        result = agent_registry.list_agents()

        assert len(result) == 2
        assert all(a["is_primary"] for a in result)


def test_get_agent_info():
    """Test get_agent_info returns agent by name."""
    mock_registry = {
        "agent1": {"name": "agent1", "display_name": "Agent One"},
    }

    with patch("services.agent_registry.get_agent_registry") as mock_get:
        mock_get.return_value = mock_registry

        result = agent_registry.get_agent_info("agent1")

        assert result == mock_registry["agent1"]


def test_get_agent_info_not_found():
    """Test get_agent_info returns None when agent not found."""
    with patch("services.agent_registry.get_agent_registry") as mock_get:
        mock_get.return_value = {}

        result = agent_registry.get_agent_info("missing")

        assert result is None


def test_get_agent_success():
    """Test get_agent returns agent instance."""
    mock_graph = MagicMock()
    mock_graph.ainvoke = MagicMock()  # LangGraph graph

    mock_registry = {
        "agent1": {"name": "agent1", "agent_class": mock_graph},
    }

    with patch("services.agent_registry.get_agent_registry") as mock_get:
        mock_get.return_value = mock_registry

        result = agent_registry.get_agent("agent1")

        # get_agent wraps the graph, so check it has the right attributes
        assert hasattr(result, "ainvoke") or result == mock_graph


def test_get_agent_not_found():
    """Test get_agent raises ValueError when agent not found."""
    with patch("services.agent_registry.get_agent_registry") as mock_get:
        mock_get.return_value = {}

        with pytest.raises(ValueError, match="not found"):
            agent_registry.get_agent("missing")


def test_get_agent_no_implementation():
    """Test get_agent raises ValueError when no agent_class."""
    mock_registry = {
        "agent1": {"name": "agent1"},  # No agent_class
    }

    with patch("services.agent_registry.get_agent_registry") as mock_get:
        mock_get.return_value = mock_registry

        with pytest.raises(ValueError, match="no implementation available"):
            agent_registry.get_agent("agent1")
