"""Tests for services/agent_registry.py"""

from unittest.mock import Mock, patch

import pytest

from services import agent_registry


@pytest.fixture(autouse=True)
def clear_registry_cache():
    """Clear agent registry cache before each test."""
    agent_registry.clear_cache()
    yield
    agent_registry.clear_cache()


@pytest.fixture
def mock_agents_response():
    """Mock response from control-plane /api/agents endpoint."""
    return {
        "agents": [
            {
                "name": "profile",
                "description": "Company profile agent",
                "aliases": ["company", "profile-agent"],
                "is_enabled": True,
                "is_slack_visible": True,
                "is_system": False,
            },
            {
                "name": "meddic",
                "description": "MEDDPICC qualification agent",
                "aliases": ["meddpicc", "qual"],
                "is_enabled": True,
                "is_slack_visible": True,
                "is_system": False,
            },
            {
                "name": "internal",
                "description": "Internal system agent",
                "aliases": [],
                "is_enabled": False,
                "is_slack_visible": True,
                "is_system": True,  # System agents are always enabled
            },
            {
                "name": "disabled-agent",
                "description": "Disabled agent",
                "aliases": ["disabled"],
                "is_enabled": False,
                "is_slack_visible": True,
                "is_system": False,
            },
            {
                "name": "api-only",
                "description": "API only agent",
                "aliases": [],
                "is_enabled": True,
                "is_slack_visible": False,  # Not visible in Slack
                "is_system": False,
            },
        ]
    }


class TestGetAgentRegistry:
    @patch("config.settings.Settings")
    @patch("requests.get")
    def test_get_agent_registry_success(
        self, mock_get, mock_settings, mock_agents_response
    ):
        """Test successful agent registry fetch."""
        mock_settings.return_value.control_plane_url = "http://control:6001"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_agents_response
        mock_get.return_value = mock_response

        registry = agent_registry.get_agent_registry()

        # Should have 3 enabled+visible agents: profile, meddic, internal (system)
        # profile has 3 entries (primary + 2 aliases)
        # meddic has 3 entries (primary + 2 aliases)
        # internal has 1 entry (no aliases)
        assert len(registry) == 7  # 3+3+1

        # Check profile agent (primary)
        assert "profile" in registry
        assert registry["profile"]["name"] == "profile"
        assert registry["profile"]["is_primary"] is True
        assert "company" in registry["profile"]["aliases"]

        # Check profile alias
        assert "company" in registry
        assert registry["company"]["name"] == "profile"
        assert registry["company"]["is_primary"] is False

        # Check system agent included despite is_enabled=False
        assert "internal" in registry

        # Disabled non-system agent should NOT be in registry
        assert "disabled-agent" not in registry

        # API-only agent should NOT be in registry (not slack_visible)
        assert "api-only" not in registry

    @patch("config.settings.Settings")
    @patch("requests.get")
    def test_get_agent_registry_caching(
        self, mock_get, mock_settings, mock_agents_response
    ):
        """Test agent registry caching with TTL."""
        mock_settings.return_value.control_plane_url = "http://control:6001"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_agents_response
        mock_get.return_value = mock_response

        # First call - should hit API
        registry1 = agent_registry.get_agent_registry()
        assert mock_get.call_count == 1

        # Second call immediately - should use cache
        registry2 = agent_registry.get_agent_registry()
        assert mock_get.call_count == 1  # No additional call
        assert registry1 == registry2

        # Force refresh
        registry3 = agent_registry.get_agent_registry(force_refresh=True)
        assert mock_get.call_count == 2  # Additional call made
        assert registry1 == registry3

    @patch("config.settings.Settings")
    @patch("requests.get")
    def test_get_agent_registry_http_error(self, mock_get, mock_settings):
        mock_settings.return_value.control_plane_url = "http://control:6001"
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        registry = agent_registry.get_agent_registry()

        # Should return empty dict on error
        assert registry == {}

    @patch("config.settings.Settings")
    @patch("requests.get")
    def test_get_agent_registry_exception(self, mock_get, mock_settings):
        mock_settings.return_value.control_plane_url = "http://control:6001"
        mock_get.side_effect = Exception("Connection error")

        registry = agent_registry.get_agent_registry()

        # Should return empty dict on exception
        assert registry == {}

    @patch("config.settings.Settings")
    @patch("requests.get")
    def test_get_agent_registry_returns_stale_cache_on_error(
        self, mock_get, mock_settings, mock_agents_response
    ):
        """Test that stale cache is returned when API fails."""
        mock_settings.return_value.control_plane_url = "http://control:6001"

        # First call succeeds
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_agents_response
        mock_get.return_value = mock_response
        registry1 = agent_registry.get_agent_registry()
        assert len(registry1) > 0

        # Clear cache timestamp to simulate expired cache
        agent_registry._cache_timestamp = 0

        # Second call fails
        mock_response.status_code = 500
        registry2 = agent_registry.get_agent_registry()

        # Should return stale cache instead of empty dict
        assert registry2 == registry1
        assert len(registry2) > 0


class TestGetAgentInfo:
    @patch("config.settings.Settings")
    @patch("requests.get")
    def test_get_agent_info_by_name(
        self, mock_get, mock_settings, mock_agents_response
    ):
        """Test getting agent info by primary name."""
        mock_settings.return_value.control_plane_url = "http://control:6001"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_agents_response
        mock_get.return_value = mock_response

        agent_info = agent_registry.get_agent_info("profile")

        assert agent_info is not None
        assert agent_info["name"] == "profile"
        assert agent_info["is_primary"] is True

    @patch("config.settings.Settings")
    @patch("requests.get")
    def test_get_agent_info_by_alias(
        self, mock_get, mock_settings, mock_agents_response
    ):
        """Test getting agent info by alias."""
        mock_settings.return_value.control_plane_url = "http://control:6001"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_agents_response
        mock_get.return_value = mock_response

        agent_info = agent_registry.get_agent_info("company")

        assert agent_info is not None
        assert agent_info["name"] == "profile"  # Points to primary
        assert agent_info["is_primary"] is False

    @patch("config.settings.Settings")
    @patch("requests.get")
    def test_get_agent_info_case_insensitive(
        self, mock_get, mock_settings, mock_agents_response
    ):
        """Test that agent lookup is case insensitive."""
        mock_settings.return_value.control_plane_url = "http://control:6001"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_agents_response
        mock_get.return_value = mock_response

        agent_info = agent_registry.get_agent_info("PROFILE")

        assert agent_info is not None
        assert agent_info["name"] == "profile"

    @patch("config.settings.Settings")
    @patch("requests.get")
    def test_get_agent_info_not_found(
        self, mock_get, mock_settings, mock_agents_response
    ):
        """Test getting info for non-existent agent."""
        mock_settings.return_value.control_plane_url = "http://control:6001"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_agents_response
        mock_get.return_value = mock_response

        agent_info = agent_registry.get_agent_info("nonexistent")

        assert agent_info is None


class TestGetPrimaryName:
    @patch("config.settings.Settings")
    @patch("requests.get")
    def test_get_primary_name_from_alias(
        self, mock_get, mock_settings, mock_agents_response
    ):
        """Test resolving primary name from alias."""
        mock_settings.return_value.control_plane_url = "http://control:6001"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_agents_response
        mock_get.return_value = mock_response

        primary = agent_registry.get_primary_name("company")

        assert primary == "profile"

    @patch("config.settings.Settings")
    @patch("requests.get")
    def test_get_primary_name_already_primary(
        self, mock_get, mock_settings, mock_agents_response
    ):
        """Test getting primary name when already primary."""
        mock_settings.return_value.control_plane_url = "http://control:6001"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_agents_response
        mock_get.return_value = mock_response

        primary = agent_registry.get_primary_name("profile")

        assert primary == "profile"

    @patch("config.settings.Settings")
    @patch("requests.get")
    def test_get_primary_name_not_found(
        self, mock_get, mock_settings, mock_agents_response
    ):
        """Test getting primary name for non-existent agent."""
        mock_settings.return_value.control_plane_url = "http://control:6001"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_agents_response
        mock_get.return_value = mock_response

        primary = agent_registry.get_primary_name("nonexistent")

        # Should return lowercased input when not found
        assert primary == "nonexistent"


class TestCheckAgentAvailability:
    @patch("config.settings.Settings")
    @patch("requests.get")
    def test_check_agent_availability_enabled(
        self, mock_get, mock_settings, mock_agents_response
    ):
        """Test availability check for enabled agent."""
        mock_settings.return_value.control_plane_url = "http://control:6001"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_agents_response
        mock_get.return_value = mock_response

        result = agent_registry.check_agent_availability("profile")

        assert result is not None
        assert result["exists"] is True
        assert result["is_enabled"] is True
        assert result["is_slack_visible"] is True
        assert "available" in result["reason"].lower()

    @patch("config.settings.Settings")
    @patch("requests.get")
    def test_check_agent_availability_disabled(
        self, mock_get, mock_settings, mock_agents_response
    ):
        """Test availability check for disabled agent."""
        mock_settings.return_value.control_plane_url = "http://control:6001"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_agents_response
        mock_get.return_value = mock_response

        result = agent_registry.check_agent_availability("disabled-agent")

        assert result is not None
        assert result["exists"] is True
        assert result["is_enabled"] is False
        assert "disabled by an administrator" in result["reason"]

    @patch("config.settings.Settings")
    @patch("requests.get")
    def test_check_agent_availability_not_slack_visible(
        self, mock_get, mock_settings, mock_agents_response
    ):
        """Test availability check for API-only agent."""
        mock_settings.return_value.control_plane_url = "http://control:6001"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_agents_response
        mock_get.return_value = mock_response

        result = agent_registry.check_agent_availability("api-only")

        assert result is not None
        assert result["exists"] is True
        assert result["is_slack_visible"] is False
        assert "not available in Slack" in result["reason"]

    @patch("config.settings.Settings")
    @patch("requests.get")
    def test_check_agent_availability_system_agent(
        self, mock_get, mock_settings, mock_agents_response
    ):
        """Test availability check for system agent (always enabled)."""
        mock_settings.return_value.control_plane_url = "http://control:6001"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_agents_response
        mock_get.return_value = mock_response

        result = agent_registry.check_agent_availability("internal")

        assert result is not None
        assert result["exists"] is True
        assert result["is_enabled"] is True  # System agents always enabled

    @patch("config.settings.Settings")
    @patch("requests.get")
    def test_check_agent_availability_not_found(
        self, mock_get, mock_settings, mock_agents_response
    ):
        """Test availability check for non-existent agent."""
        mock_settings.return_value.control_plane_url = "http://control:6001"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_agents_response
        mock_get.return_value = mock_response

        result = agent_registry.check_agent_availability("nonexistent")

        assert result is None

    @patch("config.settings.Settings")
    @patch("requests.get")
    def test_check_agent_availability_http_error(self, mock_get, mock_settings):
        mock_settings.return_value.control_plane_url = "http://control:6001"
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        result = agent_registry.check_agent_availability("profile")

        assert result is None

    @patch("config.settings.Settings")
    @patch("requests.get")
    def test_check_agent_availability_exception(self, mock_get, mock_settings):
        mock_settings.return_value.control_plane_url = "http://control:6001"
        mock_get.side_effect = Exception("Connection error")

        result = agent_registry.check_agent_availability("profile")

        assert result is None


class TestRouteCommand:
    @patch("config.settings.Settings")
    @patch("requests.get")
    def test_route_command_with_dash(
        self, mock_get, mock_settings, mock_agents_response
    ):
        """Test routing command with dash prefix."""
        mock_settings.return_value.control_plane_url = "http://control:6001"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_agents_response
        mock_get.return_value = mock_response

        agent_info, query, primary_name = agent_registry.route_command(
            "-profile tell me about AllCampus"
        )

        assert agent_info is not None
        assert agent_info["name"] == "profile"
        assert query == "tell me about AllCampus"
        assert primary_name == "profile"

    @patch("config.settings.Settings")
    @patch("requests.get")
    def test_route_command_without_dash(
        self, mock_get, mock_settings, mock_agents_response
    ):
        """Test routing command without dash prefix."""
        mock_settings.return_value.control_plane_url = "http://control:6001"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_agents_response
        mock_get.return_value = mock_response

        agent_info, query, primary_name = agent_registry.route_command(
            "meddic analyze this deal"
        )

        assert agent_info is not None
        assert agent_info["name"] == "meddic"
        assert query == "analyze this deal"
        assert primary_name == "meddic"

    @patch("config.settings.Settings")
    @patch("requests.get")
    def test_route_command_with_alias(
        self, mock_get, mock_settings, mock_agents_response
    ):
        """Test routing command using agent alias."""
        mock_settings.return_value.control_plane_url = "http://control:6001"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_agents_response
        mock_get.return_value = mock_response

        agent_info, query, primary_name = agent_registry.route_command(
            "company research Microsoft"
        )

        assert agent_info is not None
        assert agent_info["name"] == "profile"  # Resolves to primary
        assert query == "research Microsoft"
        assert primary_name == "profile"

    @patch("config.settings.Settings")
    @patch("requests.get")
    def test_route_command_case_insensitive(
        self, mock_get, mock_settings, mock_agents_response
    ):
        """Test routing command is case insensitive."""
        mock_settings.return_value.control_plane_url = "http://control:6001"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_agents_response
        mock_get.return_value = mock_response

        agent_info, query, primary_name = agent_registry.route_command(
            "PROFILE tell me about AllCampus"
        )

        assert agent_info is not None
        assert agent_info["name"] == "profile"
        assert primary_name == "profile"

    @patch("config.settings.Settings")
    @patch("requests.get")
    def test_route_command_not_found(
        self, mock_get, mock_settings, mock_agents_response
    ):
        """Test routing with non-existent agent."""
        mock_settings.return_value.control_plane_url = "http://control:6001"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_agents_response
        mock_get.return_value = mock_response

        agent_info, query, primary_name = agent_registry.route_command(
            "nonexistent do something"
        )

        assert agent_info is None
        assert query == "do something"
        assert primary_name is None

    @patch("config.settings.Settings")
    @patch("requests.get")
    def test_route_command_empty_query(
        self, mock_get, mock_settings, mock_agents_response
    ):
        """Test routing command with no query text."""
        mock_settings.return_value.control_plane_url = "http://control:6001"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_agents_response
        mock_get.return_value = mock_response

        agent_info, query, primary_name = agent_registry.route_command("profile")

        assert agent_info is not None
        assert query == ""  # Empty query is valid
        assert primary_name == "profile"

    def test_route_command_invalid_format(self):
        agent_info, query, primary_name = agent_registry.route_command("")

        assert agent_info is None
        assert query == ""
        assert primary_name is None


class TestClearCache:
    @patch("config.settings.Settings")
    @patch("requests.get")
    def test_clear_cache(self, mock_get, mock_settings, mock_agents_response):
        mock_settings.return_value.control_plane_url = "http://control:6001"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_agents_response
        mock_get.return_value = mock_response

        # Populate cache
        agent_registry.get_agent_registry()
        assert agent_registry._cached_agents is not None
        assert agent_registry._cache_timestamp > 0

        # Clear cache
        agent_registry.clear_cache()
        assert agent_registry._cached_agents is None
        assert agent_registry._cache_timestamp == 0

        # Next call should hit API again
        agent_registry.get_agent_registry()
        assert mock_get.call_count == 2  # Called twice (initial + after clear)
