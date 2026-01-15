"""Tests for agent sync with alias discovery from langgraph.json."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config, f)
            temp_path = Path(f.name)

        try:
            with patch('services.agent_sync.Path') as mock_path:
                mock_path.return_value.parent.parent = temp_path.parent
                mock_path.return_value.exists.return_value = True

                # Mock open to return our temp file
                with patch('builtins.open', lambda *args, **kwargs: open(temp_path, *args, **kwargs)):
                    agents = _discover_agents_from_langgraph()

                assert len(agents) == 2
                assert agents[0]["name"] == "test_agent"
                assert agents[0]["aliases"] == []  # No aliases in simple format
                assert agents[0]["display_name"] == "Test Agent"
        finally:
            temp_path.unlink()

    def test_discover_agents_extended_format_with_aliases(self):
        """Should parse extended format with metadata including aliases."""
        config = {
            "graphs": {
                "profile": {
                    "graph": "profiler.nodes:build_profile",
                    "metadata": {
                        "display_name": "Company Profile",
                        "description": "Generate company profiles",
                        "aliases": ["profile", "company profile", "-profile"]
                    }
                },
                "meddic": {
                    "graph": "meddic.nodes:build_meddic",
                    "metadata": {
                        "display_name": "MEDDIC Coach",
                        "description": "Deal coaching",
                        "aliases": ["meddic", "medic", "meddpicc"]
                    }
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config, f)
            temp_path = Path(f.name)

        try:
            with patch('services.agent_sync.Path') as mock_path:
                mock_path.return_value.parent.parent = temp_path.parent
                mock_path.return_value.exists.return_value = True

                with patch('builtins.open', lambda *args, **kwargs: open(temp_path, *args, **kwargs)):
                    agents = _discover_agents_from_langgraph()

                assert len(agents) == 2

                profile = next(a for a in agents if a["name"] == "profile")
                assert profile["display_name"] == "Company Profile"
                assert profile["aliases"] == ["profile", "company profile", "-profile"]

                meddic = next(a for a in agents if a["name"] == "meddic")
                assert meddic["aliases"] == ["meddic", "medic", "meddpicc"]
        finally:
            temp_path.unlink()

    def test_discover_agents_help_is_system(self):
        """Help agent should always be marked as system agent."""
        config = {
            "graphs": {
                "help": {
                    "graph": "help.agent:build_help",
                    "metadata": {
                        "display_name": "Help Agent",
                        "aliases": ["help", "agents"]
                    }
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config, f)
            temp_path = Path(f.name)

        try:
            with patch('services.agent_sync.Path') as mock_path:
                mock_path.return_value.parent.parent = temp_path.parent
                mock_path.return_value.exists.return_value = True

                with patch('builtins.open', lambda *args, **kwargs: open(temp_path, *args, **kwargs)):
                    agents = _discover_agents_from_langgraph()

                assert len(agents) == 1
                assert agents[0]["is_system"] is True

        finally:
            temp_path.unlink()

    def test_discover_agents_mixed_formats(self):
        """Should handle mixed simple and extended formats."""
        config = {
            "graphs": {
                "simple_agent": "simple.module:build",
                "extended_agent": {
                    "graph": "extended.module:build",
                    "metadata": {
                        "aliases": ["ext", "extended"]
                    }
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config, f)
            temp_path = Path(f.name)

        try:
            with patch('services.agent_sync.Path') as mock_path:
                mock_path.return_value.parent.parent = temp_path.parent
                mock_path.return_value.exists.return_value = True

                with patch('builtins.open', lambda *args, **kwargs: open(temp_path, *args, **kwargs)):
                    agents = _discover_agents_from_langgraph()

                assert len(agents) == 2

                simple = next(a for a in agents if a["name"] == "simple_agent")
                assert simple["aliases"] == []

                extended = next(a for a in agents if a["name"] == "extended_agent")
                assert extended["aliases"] == ["ext", "extended"]
        finally:
            temp_path.unlink()

    def test_discover_agents_empty_aliases(self):
        """Should handle agents with empty aliases list."""
        config = {
            "graphs": {
                "no_aliases": {
                    "graph": "module:build",
                    "metadata": {
                        "aliases": []
                    }
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config, f)
            temp_path = Path(f.name)

        try:
            with patch('services.agent_sync.Path') as mock_path:
                mock_path.return_value.parent.parent = temp_path.parent
                mock_path.return_value.exists.return_value = True

                with patch('builtins.open', lambda *args, **kwargs: open(temp_path, *args, **kwargs)):
                    agents = _discover_agents_from_langgraph()

                assert len(agents) == 1
                assert agents[0]["aliases"] == []
        finally:
            temp_path.unlink()
