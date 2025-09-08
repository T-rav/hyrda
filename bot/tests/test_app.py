import os
import sys
from unittest.mock import MagicMock, patch

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, main


class TestApp:
    """Tests for the main app functionality - simplified to avoid async hanging"""

    def test_create_app(self):
        """Test app creation returns expected components"""
        with (
            patch.dict(
                os.environ,
                {
                    "SLACK_BOT_TOKEN": "xoxb-test-token",
                    "SLACK_APP_TOKEN": "xapp-test-token",
                    "LLM_PROVIDER": "openai",
                    "LLM_API_KEY": "test-api-key",
                    "LLM_MODEL": "gpt-4o-mini",
                    "DATABASE_URL": "postgresql://test:test@localhost:5432/test_db",
                    "VECTOR_ENABLED": "false",
                },
            ),
            patch("app.AsyncApp") as mock_app_class,
            patch("app.LLMService") as mock_llm_service_class,
            patch("app.SlackService") as mock_slack_service_class,
            patch("app.ConversationCache"),
        ):
            # Mock AsyncApp
            mock_app = MagicMock()
            mock_app_class.return_value = mock_app

            # Mock services
            mock_llm_service = MagicMock()
            mock_slack_service = MagicMock()
            mock_llm_service_class.return_value = mock_llm_service
            mock_slack_service_class.return_value = mock_slack_service

            result = create_app()

            # Should return 4 components (no prompt service anymore)
            assert len(result) == 4
            app, slack_service, llm_service, conversation_cache = result

            # Verify basic creation
            assert app == mock_app
            assert slack_service == mock_slack_service
            assert llm_service == mock_llm_service

    def test_main_function_exists(self):
        """Test that main function calls asyncio.run"""
        with patch("app.asyncio.run") as mock_asyncio_run:
            main()
            # Should call asyncio.run with a coroutine
            mock_asyncio_run.assert_called_once()
