"""Tests for services.agent_registry module.

Tests the dynamic agent registry that fetches from control plane API
and merges with local agent classes.
"""

import os
import sys
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services import agent_registry
from tests.agent_test_utils import TestAgentFactory


class TestServicesAgentRegistry:
    """Tests for services.agent_registry module."""

    def test_get_function_exists(self):
        """Test that get() function exists and is callable."""
        assert hasattr(agent_registry, "get")
        assert callable(agent_registry.get)

    def test_get_agent_info_function_exists(self):
        """Test that get_agent_info() function exists."""
        assert hasattr(agent_registry, "get_agent_info")
        assert callable(agent_registry.get_agent_info)

    def test_get_calls_get_agent_info(self):
        """Test that get() calls get_agent_info()."""
        with patch("services.agent_registry.get_agent_info") as mock_get_info:
            mock_get_info.return_value = {"name": "test", "agent_class": Mock()}
            result = agent_registry.get("test")
            mock_get_info.assert_called_once_with("test")
            assert result == mock_get_info.return_value

    @patch("services.agent_registry.get_agent_registry")
    def test_get_agent_info_returns_none_for_missing_agent(self, mock_get_registry):
        """Test that get_agent_info returns None for missing agent."""
        mock_get_registry.return_value = {}
        result = agent_registry.get_agent_info("nonexistent")
        assert result is None

    @patch("services.agent_registry.get_agent_registry")
    def test_get_agent_info_returns_agent_info(self, mock_get_registry):
        """Test that get_agent_info returns agent info dict."""
        test_agent_class = TestAgentFactory.create_simple_agent(name="test")
        mock_get_registry.return_value = {
            "test": {
                "name": "test",
                "agent_class": test_agent_class,
                "aliases": [],
                "is_primary": True,
            }
        }
        result = agent_registry.get_agent_info("test")
        assert result is not None
        assert result["name"] == "test"
        assert result["agent_class"] == test_agent_class

    @patch("services.agent_registry.get_agent_registry")
    def test_get_agent_info_case_insensitive(self, mock_get_registry):
        """Test that get_agent_info is case-insensitive."""
        test_agent_class = TestAgentFactory.create_simple_agent(name="test")
        mock_get_registry.return_value = {
            "test": {
                "name": "test",
                "agent_class": test_agent_class,
                "aliases": [],
                "is_primary": True,
            }
        }
        result = agent_registry.get_agent_info("TEST")
        assert result is not None
        assert result["name"] == "test"

    @patch("services.agent_registry.get_agent_registry")
    def test_get_primary_name_returns_primary_for_primary(self, mock_get_registry):
        """Test that get_primary_name returns name for primary agent."""
        mock_get_registry.return_value = {
            "test": {
                "name": "test",
                "is_primary": True,
            }
        }
        result = agent_registry.get_primary_name("test")
        assert result == "test"

    @patch("services.agent_registry.get_agent_registry")
    def test_get_primary_name_returns_primary_for_alias(self, mock_get_registry):
        """Test that get_primary_name resolves alias to primary name."""
        mock_get_registry.return_value = {
            "test": {
                "name": "test",
                "is_primary": True,
            },
            "alias": {
                "name": "test",
                "is_primary": False,
            },
        }
        result = agent_registry.get_primary_name("alias")
        assert result == "test"

    @patch("services.agent_registry.get_agent_registry")
    def test_get_primary_name_returns_none_for_missing(self, mock_get_registry):
        """Test that get_primary_name returns None for missing agent."""
        mock_get_registry.return_value = {}
        result = agent_registry.get_primary_name("nonexistent")
        assert result is None

    @patch("services.agent_registry.get_agent_registry")
    def test_list_agents_returns_only_primary(self, mock_get_registry):
        """Test that list_agents returns only primary agents."""
        test_agent_class = TestAgentFactory.create_simple_agent(name="test")
        mock_get_registry.return_value = {
            "test": {
                "name": "test",
                "agent_class": test_agent_class,
                "aliases": ["alias"],
                "is_primary": True,
            },
            "alias": {
                "name": "test",
                "agent_class": test_agent_class,
                "is_primary": False,
            },
        }
        result = agent_registry.list_agents()
        assert len(result) == 1
        assert result[0]["name"] == "test"
        assert result[0]["agent_class"] == test_agent_class

    @patch("services.agent_registry.get_agent_registry")
    def test_list_agents_includes_agent_class(self, mock_get_registry):
        """Test that list_agents includes agent_class in results."""
        test_agent_class = TestAgentFactory.create_simple_agent(name="test")
        mock_get_registry.return_value = {
            "test": {
                "name": "test",
                "agent_class": test_agent_class,
                "aliases": [],
                "is_primary": True,
            }
        }
        result = agent_registry.list_agents()
        assert len(result) == 1
        assert "agent_class" in result[0]
        assert result[0]["agent_class"] == test_agent_class

    @patch("services.agent_registry._load_agent_classes")
    @patch("requests.get")
    @patch.dict(os.environ, {"CONTROL_PLANE_URL": "http://test:6001"})
    def test_get_agent_registry_includes_agent_class(
        self, mock_requests_get, mock_load_classes
    ):
        """Test that get_agent_registry includes agent_class in registry."""
        test_agent_class = TestAgentFactory.create_simple_agent(name="test")
        mock_load_classes.return_value = {"test": test_agent_class}

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "agents": [
                {
                    "name": "test",
                    "display_name": "Test Agent",
                    "description": "Test description",
                    "aliases": [],
                    "is_enabled": True,
                    "is_public": True,
                    "requires_admin": False,
                    "is_system": False,
                }
            ]
        }
        mock_requests_get.return_value = mock_response

        # Clear cache to force refresh
        agent_registry.clear_cache()

        registry = agent_registry.get_agent_registry(force_refresh=True)

        assert "test" in registry
        assert "agent_class" in registry["test"]
        assert registry["test"]["agent_class"] == test_agent_class

    @patch("services.agent_registry._load_agent_classes")
    @patch("requests.get")
    @patch.dict(os.environ, {"CONTROL_PLANE_URL": "http://test:6001"})
    def test_get_agent_registry_includes_agent_class_for_aliases(
        self, mock_requests_get, mock_load_classes
    ):
        """Test that get_agent_registry includes agent_class for aliases."""
        test_agent_class = TestAgentFactory.create_simple_agent(name="test")
        mock_load_classes.return_value = {"test": test_agent_class}

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "agents": [
                {
                    "name": "test",
                    "display_name": "Test Agent",
                    "description": "Test description",
                    "aliases": ["alias"],
                    "is_enabled": True,
                    "is_public": True,
                    "requires_admin": False,
                    "is_system": False,
                }
            ]
        }
        mock_requests_get.return_value = mock_response

        # Clear cache to force refresh
        agent_registry.clear_cache()

        registry = agent_registry.get_agent_registry(force_refresh=True)

        assert "test" in registry
        assert "alias" in registry
        assert "agent_class" in registry["test"]
        assert "agent_class" in registry["alias"]
        assert registry["test"]["agent_class"] == test_agent_class
        assert registry["alias"]["agent_class"] == test_agent_class

    @patch("services.agent_registry._load_agent_classes")
    @patch("requests.get")
    @patch.dict(os.environ, {"CONTROL_PLANE_URL": "http://test:6001"})
    def test_get_agent_registry_handles_missing_agent_class(
        self, mock_requests_get, mock_load_classes
    ):
        """Test that get_agent_registry handles missing agent_class gracefully."""
        # No agent class available
        mock_load_classes.return_value = {}

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "agents": [
                {
                    "name": "test",
                    "display_name": "Test Agent",
                    "description": "Test description",
                    "aliases": [],
                    "is_enabled": True,
                    "is_public": True,
                    "requires_admin": False,
                    "is_system": False,
                }
            ]
        }
        mock_requests_get.return_value = mock_response

        # Clear cache to force refresh
        agent_registry.clear_cache()

        registry = agent_registry.get_agent_registry(force_refresh=True)

        assert "test" in registry
        # agent_class should not be present if not available
        assert "agent_class" not in registry["test"]

    @patch.dict("sys.modules")
    @pytest.mark.integration
    def test_load_agent_classes_loads_from_local_registry(self):
        """Test that _load_agent_classes loads from local registry.

        INTEGRATION TEST: Loads actual agents from filesystem.
        """
        # This test verifies the function can load from system loader
        test_agent_class = TestAgentFactory.create_simple_agent(name="test")

        # Mock the system loader to return our test agent
        mock_system_loader = Mock()
        mock_system_loader.discover_agents.return_value = {"test": test_agent_class}

        # Clear the cache to force reload
        agent_registry._agent_classes = {}

        with patch("services.system_agent_loader.get_system_loader", return_value=mock_system_loader):
            # Disable external agents to test only system loader
            with patch.dict(os.environ, {"LOAD_EXTERNAL_AGENTS": "false"}):
                classes = agent_registry._load_agent_classes()

        assert "test" in classes
        assert classes["test"] == test_agent_class

    def test_clear_cache_clears_cached_data(self):
        """Test that clear_cache clears cached registry."""
        # Set some cached data
        agent_registry._cached_agents = {"test": {"name": "test"}}
        agent_registry._cache_timestamp = 12345.0

        agent_registry.clear_cache()

        assert agent_registry._cached_agents is None
        assert agent_registry._cache_timestamp == 0

    @pytest.mark.integration
    @patch("services.system_agent_loader.get_system_loader")
    @patch("services.external_agent_loader.get_external_loader")
    def test_external_cannot_override_system_agent(
        self, mock_external_loader, mock_system_loader
    ):
        """Test that external agents cannot override system agents.

        INTEGRATION TEST: Tests agent loader behavior.
        """
        # Mock system agent
        system_agent_class = Mock()
        system_agent_class.__name__ = "SystemResearchAgent"
        mock_system_loader.return_value.discover_agents.return_value = {
            "research": system_agent_class
        }

        # Mock external agent with SAME name (conflict)
        external_agent_class = Mock()
        external_agent_class.__name__ = "ExternalResearchAgent"
        mock_external_loader.return_value.discover_agents.return_value = {
            "research": external_agent_class
        }

        # Clear cache to force reload
        agent_registry._agent_classes = {}

        # Load agents
        with patch.dict(os.environ, {"LOAD_EXTERNAL_AGENTS": "true"}):
            classes = agent_registry._load_agent_classes()

        # Verify system agent wins, external rejected
        assert "research" in classes
        assert classes["research"] == system_agent_class  # System wins!
        assert classes["research"] != external_agent_class  # External rejected

    @pytest.mark.integration
    @patch("services.system_agent_loader.get_system_loader")
    @patch("services.external_agent_loader.get_external_loader")
    def test_external_loads_when_no_conflict(
        self, mock_external_loader, mock_system_loader
    ):
        """Test that external agents load normally when no conflict.

        INTEGRATION TEST: Tests agent loader behavior.
        """
        # Mock system agent
        system_agent_class = Mock()
        system_agent_class.__name__ = "ResearchAgent"
        mock_system_loader.return_value.discover_agents.return_value = {
            "research": system_agent_class
        }

        # Mock external agent with DIFFERENT name (no conflict)
        external_agent_class = Mock()
        external_agent_class.__name__ = "ProfileAgent"
        mock_external_loader.return_value.discover_agents.return_value = {
            "profile": external_agent_class
        }

        # Clear cache to force reload
        agent_registry._agent_classes = {}

        # Load agents
        with patch.dict(os.environ, {"LOAD_EXTERNAL_AGENTS": "true"}):
            classes = agent_registry._load_agent_classes()

        # Verify both loaded
        assert "research" in classes
        assert "profile" in classes
        assert classes["research"] == system_agent_class
        assert classes["profile"] == external_agent_class
