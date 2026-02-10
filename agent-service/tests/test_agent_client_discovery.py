"""Tests for AgentClient agent discovery and is_enabled checking."""

from unittest.mock import patch

import pytest

from clients.agent_client import AgentClient


@pytest.fixture
def agent_client():
    """Create AgentClient instance."""
    return AgentClient()


@pytest.fixture
def mock_enabled_agent():
    """Mock enabled agent from registry."""
    return {
        "name": "test_agent",
        "display_name": "Test Agent",
        "is_enabled": True,
        "aliases": [],
    }


@pytest.fixture
def mock_disabled_agent():
    """Mock disabled agent from registry."""
    return {
        "name": "disabled_agent",
        "display_name": "Disabled Agent",
        "is_enabled": False,
        "aliases": [],
    }


@pytest.mark.asyncio
class TestAgentDiscovery:
    """Test agent discovery and is_enabled validation."""

    async def test_discover_enabled_agent_succeeds(
        self, agent_client, mock_enabled_agent
    ):
        """Test that discovering enabled agent succeeds."""
        with patch("services.agent_registry.list_agents") as mock_list:
            mock_list.return_value = [mock_enabled_agent]

            result = await agent_client.discover_agent("test_agent")

            assert result is not None
            assert result["agent_name"] == "test_agent"
            assert result["is_cloud"] is False

    async def test_discover_disabled_agent_raises_error(
        self, agent_client, mock_disabled_agent
    ):
        """Test that discovering disabled agent raises ValueError."""
        with patch("services.agent_registry.list_agents") as mock_list:
            mock_list.return_value = [mock_disabled_agent]

            with pytest.raises(ValueError, match="is disabled"):
                await agent_client.discover_agent("disabled_agent")

    async def test_discover_nonexistent_agent_raises_error(self, agent_client):
        """Test that discovering nonexistent agent raises ValueError."""
        with patch("services.agent_registry.list_agents") as mock_list:
            mock_list.return_value = []

            with pytest.raises(ValueError, match="not found"):
                await agent_client.discover_agent("nonexistent")

    async def test_disabled_agent_from_control_plane(self, agent_client):
        """Test that agent disabled in control plane cannot be discovered."""
        # Agent exists in registry but is disabled by control plane
        mock_agent = {
            "name": "test_agent",
            "display_name": "Test Agent",
            "is_enabled": False,  # Disabled by control plane
            "aliases": [],
        }

        with patch("services.agent_registry.list_agents") as mock_list:
            mock_list.return_value = [mock_agent]

            with pytest.raises(ValueError) as exc_info:
                await agent_client.discover_agent("test_agent")

            assert "disabled" in str(exc_info.value).lower()

    async def test_agent_with_missing_is_enabled_defaults_to_true(self, agent_client):
        """Test that agents without is_enabled field default to enabled."""
        # Agent without is_enabled field (defaults to True)
        mock_agent = {
            "name": "test_agent",
            "display_name": "Test Agent",
            # is_enabled missing → defaults to True
            "aliases": [],
        }

        with patch("services.agent_registry.list_agents") as mock_list:
            mock_list.return_value = [mock_agent]

            # Should succeed (defaults to enabled)
            result = await agent_client.discover_agent("test_agent")
            assert result is not None
            assert result["agent_name"] == "test_agent"

    async def test_cache_cleared_after_disabled_check(self, agent_client):
        """Test that disabled agents are not cached."""
        mock_agent = {
            "name": "test_agent",
            "display_name": "Test Agent",
            "is_enabled": False,
            "aliases": [],
        }

        with patch("services.agent_registry.list_agents") as mock_list:
            mock_list.return_value = [mock_agent]

            # First attempt should fail
            with pytest.raises(ValueError, match="is disabled"):
                await agent_client.discover_agent("test_agent")

            # Verify not cached
            assert "test_agent" not in agent_client._agent_cache

    async def test_enabled_agent_is_cached(self, agent_client, mock_enabled_agent):
        """Test that enabled agents are cached after discovery."""
        with patch("services.agent_registry.list_agents") as mock_list:
            mock_list.return_value = [mock_enabled_agent]

            # First discovery
            result1 = await agent_client.discover_agent("test_agent")

            # Second discovery should use cache
            result2 = await agent_client.discover_agent("test_agent")

            # Should only call list_agents once (cache hit on second call)
            assert mock_list.call_count == 1
            assert result1 == result2
            assert "test_agent" in agent_client._agent_cache
