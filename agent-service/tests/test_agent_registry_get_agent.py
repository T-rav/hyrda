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
        with (
            patch("services.agent_registry.get_agent_info", return_value=None),
            pytest.raises(ValueError, match="Agent 'nonexistent' not found"),
        ):
            get_agent("nonexistent")

    def test_get_agent_no_implementation(self):
        """Test error when agent has no implementation."""
        # Mock agent info without agent_class
        mock_agent_info = {
            "name": "test_agent",
            # Missing agent_class
        }

        with (
            patch(
                "services.agent_registry.get_agent_info", return_value=mock_agent_info
            ),
            pytest.raises(
                ValueError,
                match="found in control-plane but no implementation available",
            ),
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

        with (
            patch(
                "services.agent_registry.get_agent_info", return_value=mock_agent_info
            ),
            pytest.raises(Exception, match="Initialization failed"),
        ):
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
    def test_get_agent_with_unified_loader(
        self, mock_agent_builder, mock_loader_builder
    ):
        """Test get_agent with unified agent loader integration.

        Uses builder pattern for creating mock fixtures.
        """
        # Build test agent using builder
        test_agent = (
            mock_agent_builder()
            .with_name("test_agent")
            .with_display_name("Test Agent")
            .with_invoke_response({"response": "Echo test", "metadata": {}})
            .build()
        )

        # Build loader using builder
        mock_loader = (
            mock_loader_builder().with_agents({"test_agent": test_agent}).build()
        )

        # Clear cache to force reload
        from services.agent_registry import clear_cache  # noqa: PLC0415

        clear_cache()

        # Also clear the agent_classes cache
        import services.agent_registry as registry_module  # noqa: PLC0415

        registry_module._agent_classes = {}

        # Patch where the loader is imported
        with patch(
            "services.unified_agent_loader.get_unified_loader",
            return_value=mock_loader,
        ):
            # Get agent
            agent = get_agent("test_agent")

            assert agent is not None
            assert hasattr(agent, "invoke")

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
