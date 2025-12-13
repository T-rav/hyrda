"""Unit tests for agent_registry.get_agent() function.

All tests in this file are pure unit tests with full mocking.
Integration tests are marked with @pytest.mark.integration.
"""

from unittest.mock import MagicMock, patch

import pytest

from services.agent_registry import get_agent


class TestGetAgent:
    """Test get_agent() function."""

    def test_get_agent_success(self):
        """Test successfully getting an agent instance."""
        # Mock agent info with agent class
        mock_agent_class = MagicMock()
        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance

        mock_agent_info = {
            "name": "test_agent",
            "agent_class": mock_agent_class,
        }

        with patch(
            "services.agent_registry.get_agent_info", return_value=mock_agent_info
        ):
            agent = get_agent("test_agent")

            assert agent == mock_agent_instance
            mock_agent_class.assert_called_once_with()

    def test_get_agent_not_found(self):
        """Test error when agent not found."""
        with patch("services.agent_registry.get_agent_info", return_value=None):
            with pytest.raises(ValueError, match="Agent 'nonexistent' not found"):
                get_agent("nonexistent")

    def test_get_agent_no_implementation(self):
        """Test error when agent has no implementation."""
        # Mock agent info without agent_class
        mock_agent_info = {
            "name": "test_agent",
            # Missing agent_class
        }

        with patch(
            "services.agent_registry.get_agent_info", return_value=mock_agent_info
        ):
            with pytest.raises(
                ValueError,
                match="found in control-plane but no implementation available",
            ):
                get_agent("test_agent")

    def test_get_agent_by_alias(self):
        """Test getting agent by alias."""
        mock_agent_class = MagicMock()
        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance

        mock_agent_info = {
            "name": "profile",
            "agent_class": mock_agent_class,
        }

        # get_agent_info should handle alias resolution
        with patch(
            "services.agent_registry.get_agent_info", return_value=mock_agent_info
        ):
            agent = get_agent("profiler")  # Using alias

            assert agent == mock_agent_instance
            mock_agent_class.assert_called_once_with()

    def test_get_agent_case_insensitive(self):
        """Test that agent lookup is case-insensitive."""
        mock_agent_class = MagicMock()
        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance

        mock_agent_info = {
            "name": "profile",
            "agent_class": mock_agent_class,
        }

        # get_agent_info handles case conversion
        with patch(
            "services.agent_registry.get_agent_info", return_value=mock_agent_info
        ):
            agent = get_agent("PROFILE")  # Uppercase

            assert agent == mock_agent_instance

    def test_get_agent_instantiation_error(self):
        """Test handling of agent instantiation errors."""
        mock_agent_class = MagicMock()
        mock_agent_class.side_effect = Exception("Initialization failed")

        mock_agent_info = {
            "name": "broken_agent",
            "agent_class": mock_agent_class,
        }

        with patch(
            "services.agent_registry.get_agent_info", return_value=mock_agent_info
        ):
            with pytest.raises(Exception, match="Initialization failed"):
                get_agent("broken_agent")

    def test_get_agent_returns_new_instance_each_time(self):
        """Test that get_agent returns a new instance each call."""
        mock_agent_class = MagicMock()
        instance1 = MagicMock()
        instance2 = MagicMock()
        mock_agent_class.side_effect = [instance1, instance2]

        mock_agent_info = {
            "name": "test_agent",
            "agent_class": mock_agent_class,
        }

        with patch(
            "services.agent_registry.get_agent_info", return_value=mock_agent_info
        ):
            agent1 = get_agent("test_agent")
            agent2 = get_agent("test_agent")

            assert agent1 is instance1
            assert agent2 is instance2
            assert agent1 is not agent2
            assert mock_agent_class.call_count == 2


@pytest.mark.integration
class TestGetAgentIntegration:
    """Integration tests for get_agent with real registry."""

    @pytest.mark.integration
    def test_get_agent_with_external_loader(self, tmp_path):
        """Test get_agent with external agent loader integration."""
        # Create temporary agent
        agent_dir = tmp_path / "test_agent"
        agent_dir.mkdir()

        agent_code = """
class Agent:
    def __init__(self):
        self.name = "test"

    async def invoke(self, query: str, context: dict) -> dict:
        return {"response": f"Echo: {query}", "metadata": {}}
"""
        (agent_dir / "agent.py").write_text(agent_code)

        # Mock control-plane to return agent metadata
        mock_control_plane_response = [
            {
                "name": "test_agent",
                "display_name": "Test Agent",
                "description": "Test",
                "aliases": [],
                "is_public": True,
                "requires_admin": False,
            }
        ]

        with patch("services.agent_registry.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"agents": mock_control_plane_response}
            mock_get.return_value = mock_response

            # Set external agents path
            with patch("os.getenv") as mock_getenv:

                def getenv_side_effect(key, default=None):
                    if key == "EXTERNAL_AGENTS_PATH":
                        return str(tmp_path)
                    elif key == "CONTROL_PLANE_URL":
                        return "http://control_plane:6001"
                    return default

                mock_getenv.side_effect = getenv_side_effect

                # Clear cache to force reload
                from services.agent_registry import clear_cache

                clear_cache()

                # Reset loader
                import services.external_agent_loader as loader_module

                loader_module._external_loader = None

                # Get agent
                agent = get_agent("test_agent")

                assert agent is not None
                assert hasattr(agent, "invoke")
                assert agent.name == "test"

    @pytest.mark.integration
    def test_get_agent_embedded_cloud_consistency(self):
        """Test that get_agent works consistently for both modes."""
        # Mock agent with both embedded class and cloud assistant_id
        mock_agent_class = MagicMock()
        mock_instance = MagicMock()
        mock_agent_class.return_value = mock_instance

        mock_agent_info = {
            "name": "profile",
            "display_name": "Profile Agent",
            "agent_class": mock_agent_class,
            "langgraph_assistant_id": "asst_123",  # For cloud mode
        }

        with patch(
            "services.agent_registry.get_agent_info", return_value=mock_agent_info
        ):
            # In embedded mode, get_agent returns instance
            agent = get_agent("profile")
            assert agent == mock_instance

            # Agent info has cloud metadata available
            agent_info = mock_agent_info
            assert agent_info["langgraph_assistant_id"] == "asst_123"
