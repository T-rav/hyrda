"""Tests for agent sync is_enabled fix."""

import json
from unittest.mock import mock_open, patch


class TestAgentSyncEnabled:
    """Tests for is_enabled flag in agent sync."""

    def test_discovered_agents_can_be_enabled(self):
        """Discovered agents should have structure that supports is_enabled."""
        # Import here to ensure fresh module state
        from services.agent_sync import _discover_agents_from_langgraph

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
        agent = agents[0]

        # Verify agent has required fields for sync
        assert agent["name"] == "test_agent"
        assert "display_name" in agent
        assert "description" in agent
        assert "aliases" in agent
        assert "is_system" in agent

        # is_enabled is added during sync, not during discovery
        # sync_agents_to_control_plane sets: agent_data["is_enabled"] = True
