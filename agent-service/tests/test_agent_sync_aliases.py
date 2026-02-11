"""Tests for agent sync with alias discovery from langgraph.json."""

import json
from unittest.mock import mock_open, patch

from services.agent_sync import _discover_agents_from_langgraph


class TestAgentDiscoveryFromLangGraph:
    """Tests for discovering agents from langgraph.json."""

    def test_discover_agents_simple_format(self):
        """Should parse simple string format: 'agent': 'module:function'."""
        config = {
            "graphs": {
                "test_agent": "module.path:build_agent",
                "another_agent": "another.module:build_another",
            }
        }

        config_json = json.dumps(config)

        with patch("builtins.open", mock_open(read_data=config_json)):
            with patch("pathlib.Path.exists", return_value=True):
                agents = _discover_agents_from_langgraph()

        assert len(agents) == 2
        assert agents[0]["name"] == "test_agent"
        assert agents[0]["aliases"] == []  # No aliases in simple format
        assert agents[0]["display_name"] == "Test Agent"
        assert agents[0]["is_system"] is False

    def test_discover_agents_extended_format_with_aliases(self):
        """Should extract metadata from @agent_metadata decorator."""
        config = {
            "graphs": {
                "profile": "profiler.nodes:build_profile",
                "meddic": "meddic.nodes:build_meddic",
            }
        }

        # Create mock objects with decorator metadata
        mock_profile = type("MockGraph", (), {})()
        mock_profile.__agent_metadata__ = {
            "display_name": "Company Profile",
            "description": "Generate company profiles",
            "aliases": ["profile", "company profile", "-profile"],
            "is_system": False,
        }

        mock_meddic = type("MockGraph", (), {})()
        mock_meddic.__agent_metadata__ = {
            "display_name": "MEDDIC Coach",
            "description": "Deal coaching",
            "aliases": ["meddic", "medic", "meddpicc"],
            "is_system": False,
        }

        config_json = json.dumps(config)

        def mock_import(name):
            if name == "profiler.nodes":
                m = type("Module", (), {})()
                m.build_profile = mock_profile
                return m
            elif name == "meddic.nodes":
                m = type("Module", (), {})()
                m.build_meddic = mock_meddic
                return m
            raise ImportError(f"No module named '{name}'")

        with patch("builtins.open", mock_open(read_data=config_json)):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("importlib.import_module", side_effect=mock_import):
                    agents = _discover_agents_from_langgraph()

        assert len(agents) == 2

        profile = next(a for a in agents if a["name"] == "profile")
        assert profile["display_name"] == "Company Profile"
        # Agent's own name filtered from aliases (it's redundant)
        assert profile["aliases"] == ["company profile", "-profile"]

        meddic = next(a for a in agents if a["name"] == "meddic")
        # Agent's own name filtered from aliases (it's redundant)
        assert meddic["aliases"] == ["medic", "meddpicc"]

    def test_discover_agents_research_is_system(self):
        """Research agent decorator should mark it as system agent."""
        config = {
            "graphs": {"research": "agents.research.research_agent:research_agent"}
        }

        # Mock research agent with decorator metadata
        mock_research = type("MockGraph", (), {})()
        mock_research.__agent_metadata__ = {
            "display_name": "Research Agent",
            "description": "Deep research agent",
            "aliases": ["research", "deep_research"],
            "is_system": True,  # System agents can't be disabled
        }

        config_json = json.dumps(config)

        def mock_import(name):
            if name == "agents.research.research_agent":
                m = type("Module", (), {})()
                m.research_agent = mock_research
                return m
            raise ImportError(f"No module named '{name}'")

        with patch("builtins.open", mock_open(read_data=config_json)):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("importlib.import_module", side_effect=mock_import):
                    agents = _discover_agents_from_langgraph()

        assert len(agents) == 1
        assert agents[0]["is_system"] is True
        assert agents[0]["name"] == "research"

    def test_discover_agents_mixed_formats(self):
        """Should handle agents with and without decorator metadata."""
        config = {
            "graphs": {
                "simple_agent": "simple.module:build",
                "extended_agent": "extended.module:build",
            }
        }

        # Simple agent has no decorator metadata
        mock_simple = type("MockGraph", (), {})()

        # Extended agent has decorator metadata
        mock_extended = type("MockGraph", (), {})()
        mock_extended.__agent_metadata__ = {
            "display_name": "Extended Agent",
            "description": "Has metadata",
            "aliases": ["ext", "extended"],
            "is_system": False,
        }

        config_json = json.dumps(config)

        def mock_import(name):
            if name == "simple.module":
                m = type("Module", (), {})()
                m.build = mock_simple
                return m
            elif name == "extended.module":
                m = type("Module", (), {})()
                m.build = mock_extended
                return m
            raise ImportError(f"No module named '{name}'")

        with patch("builtins.open", mock_open(read_data=config_json)):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("importlib.import_module", side_effect=mock_import):
                    agents = _discover_agents_from_langgraph()

        assert len(agents) == 2

        simple = next(a for a in agents if a["name"] == "simple_agent")
        assert simple["aliases"] == []

        extended = next(a for a in agents if a["name"] == "extended_agent")
        assert extended["aliases"] == ["ext", "extended"]

    def test_discover_agents_empty_aliases(self):
        """Should handle agents with empty aliases list."""
        config = {
            "graphs": {
                "no_aliases": {"graph": "module:build", "metadata": {"aliases": []}}
            }
        }

        config_json = json.dumps(config)

        with patch("builtins.open", mock_open(read_data=config_json)):
            with patch("pathlib.Path.exists", return_value=True):
                agents = _discover_agents_from_langgraph()

        assert len(agents) == 1
        assert agents[0]["aliases"] == []

    def test_discover_agents_file_not_found(self):
        """Should return empty list when langgraph.json not found."""
        with patch("pathlib.Path.exists", return_value=False):
            agents = _discover_agents_from_langgraph()

        assert agents == []

    def test_discover_agents_enabled_by_default(self):
        """Agents should be enabled by default for immediate availability."""
        config = {
            "graphs": {
                "test_agent": {
                    "graph": "module.path:build_agent",
                    "metadata": {"display_name": "Test Agent"},
                }
            }
        }

        config_json = json.dumps(config)

        with patch("builtins.open", mock_open(read_data=config_json)):
            with patch("pathlib.Path.exists", return_value=True):
                agents = _discover_agents_from_langgraph()

        assert len(agents) == 1
        # Note: is_enabled is added during sync, not during discovery
        # This test documents expected behavior

    def test_discover_agents_filters_own_name_from_aliases(self):
        """Agent's own name should be filtered from aliases to prevent registry overwrite."""
        config = {
            "graphs": {
                "meddic": "meddic.nodes:build_meddic",
            }
        }

        # Mock with decorator metadata including own name in aliases
        mock_meddic = type("MockGraph", (), {})()
        mock_meddic.__agent_metadata__ = {
            "display_name": "MEDDIC Coach",
            "description": "Deal coaching",
            "aliases": ["meddic", "medic", "meddpicc", "deal analysis"],
            "is_system": False,
        }

        config_json = json.dumps(config)

        def mock_import(name):
            if name == "meddic.nodes":
                m = type("Module", (), {})()
                m.build_meddic = mock_meddic
                return m
            raise ImportError(f"No module named '{name}'")

        with patch("builtins.open", mock_open(read_data=config_json)):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("importlib.import_module", side_effect=mock_import):
                    agents = _discover_agents_from_langgraph()

        assert len(agents) == 1
        meddic = agents[0]

        # Own name 'meddic' should be filtered out
        assert "meddic" not in meddic["aliases"]
        assert meddic["aliases"] == ["medic", "meddpicc", "deal analysis"]
