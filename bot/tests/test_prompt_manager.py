"""Unit tests for prompt manager module.

Tests user prompt management and context injection functionality.
"""

from unittest.mock import Mock, patch

from handlers.prompt_manager import get_user_system_prompt


class TestPromptManager:
    """Unit tests for prompt manager module"""

    def test_get_user_system_prompt_no_service(self):
        """Test prompt retrieval when PromptService unavailable"""
        with patch("handlers.prompt_manager.get_prompt_service", return_value=None):
            result = get_user_system_prompt()
            assert len(result) > 0
            assert "Insight Mesh" in result or "assistant" in result.lower()

    def test_get_user_system_prompt_with_service(self):
        """Test prompt retrieval with PromptService available"""
        mock_service = Mock()
        mock_service.get_system_prompt.return_value = "Custom system prompt"

        with patch(
            "handlers.prompt_manager.get_prompt_service", return_value=mock_service
        ):
            result = get_user_system_prompt()
            assert result == "Custom system prompt"
            mock_service.get_system_prompt.assert_called_once()

    def test_get_user_system_prompt_with_user_context(self):
        """Test prompt with user context injection"""
        mock_prompt_service = Mock()
        mock_prompt_service.get_system_prompt.return_value = "Base prompt"

        mock_user_service = Mock()
        mock_user_service.get_user_info.return_value = {
            "real_name": "John Doe",
            "display_name": "johnd",
            "email_address": "john@example.com",
        }

        with (
            patch(
                "handlers.prompt_manager.get_prompt_service",
                return_value=mock_prompt_service,
            ),
            patch(
                "services.user_service.get_user_service",
                return_value=mock_user_service,
            ),
        ):
            result = get_user_system_prompt(user_id="U123")

            # Should contain base prompt and user context
            assert "Base prompt" in result
            assert "John Doe" in result
            assert "john@example.com" in result
            assert "Current User Context" in result

    def test_get_user_system_prompt_user_info_error(self):
        """Test prompt when user info retrieval fails"""
        mock_prompt_service = Mock()
        mock_prompt_service.get_system_prompt.return_value = "Base prompt"

        mock_user_service = Mock()
        mock_user_service.get_user_info.side_effect = Exception("Database error")

        with (
            patch(
                "handlers.prompt_manager.get_prompt_service",
                return_value=mock_prompt_service,
            ),
            patch(
                "services.user_service.get_user_service",
                return_value=mock_user_service,
            ),
        ):
            result = get_user_system_prompt(user_id="U123")

            # Should return base prompt without user context on error
            assert result == "Base prompt"

    def test_get_user_system_prompt_no_user_info_found(self):
        """Test prompt when user info not found"""
        mock_prompt_service = Mock()
        mock_prompt_service.get_system_prompt.return_value = "Base prompt"

        mock_user_service = Mock()
        mock_user_service.get_user_info.return_value = None

        with (
            patch(
                "handlers.prompt_manager.get_prompt_service",
                return_value=mock_prompt_service,
            ),
            patch(
                "services.user_service.get_user_service",
                return_value=mock_user_service,
            ),
        ):
            result = get_user_system_prompt(user_id="U123")

            # Should return base prompt without user context
            assert result == "Base prompt"

    def test_get_user_system_prompt_partial_user_info(self):
        """Test prompt with partial user information"""
        mock_prompt_service = Mock()
        mock_prompt_service.get_system_prompt.return_value = "Base prompt"

        mock_user_service = Mock()
        mock_user_service.get_user_info.return_value = {
            "display_name": "johnd",
            # Missing real_name and email_address
        }

        with (
            patch(
                "handlers.prompt_manager.get_prompt_service",
                return_value=mock_prompt_service,
            ),
            patch(
                "services.user_service.get_user_service",
                return_value=mock_user_service,
            ),
        ):
            result = get_user_system_prompt(user_id="U123")

            # Should contain base prompt and available user info
            assert "Base prompt" in result
            assert "johnd" in result
            assert "Current User Context" in result
