import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from config.settings import Settings
from handlers.message_handlers import handle_message
from health import HealthChecker
from services.user_prompt_service import UserPromptService


class TestIntegration:
    """Integration tests for the complete system"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_create_app_with_all_services(self):
        """Test app creation with all services enabled"""
        with (
            patch("app.Settings") as mock_settings,
            patch("app.AsyncApp") as mock_app,
            patch("app.LLMService"),
            patch("app.SlackService"),
            patch("app.ConversationCache") as mock_cache,
            patch("app.UserPromptService") as mock_prompt_service,
        ):
            # Mock settings
            settings_instance = MagicMock()
            settings_instance.slack.bot_token = "xoxb-test"
            settings_instance.llm = MagicMock()
            settings_instance.cache.enabled = True
            settings_instance.cache.redis_url = "redis://localhost:6379"
            settings_instance.cache.conversation_ttl = 1800
            settings_instance.database.enabled = True
            settings_instance.database.url = (
                "postgresql+asyncpg://test:test@localhost/test"
            )
            mock_settings.return_value = settings_instance

            # Mock service instances
            mock_app_instance = AsyncMock()
            mock_app_instance.client = AsyncMock()
            mock_app.return_value = mock_app_instance

            mock_cache_instance = AsyncMock()
            mock_cache.return_value = mock_cache_instance

            mock_prompt_service_instance = AsyncMock()
            mock_prompt_service.return_value = mock_prompt_service_instance

            # Create app
            app, slack_service, llm_service, conversation_cache, prompt_service = (
                create_app()
            )

            # Verify all services were created
            assert app is not None
            assert slack_service is not None
            assert llm_service is not None
            assert conversation_cache is not None
            assert prompt_service is not None

            # Verify services were initialized with correct parameters
            mock_cache.assert_called_once_with(
                redis_url="redis://localhost:6379", ttl=1800
            )
            mock_prompt_service.assert_called_once_with(
                "postgresql+asyncpg://test:test@localhost/test"
            )

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_create_app_with_disabled_services(self):
        """Test app creation with services disabled"""
        with (
            patch("app.Settings") as mock_settings,
            patch("app.AsyncApp") as mock_app,
            patch("app.LLMService"),
            patch("app.SlackService"),
        ):
            # Mock settings with services disabled
            settings_instance = MagicMock()
            settings_instance.slack.bot_token = "xoxb-test"
            settings_instance.llm = MagicMock()
            settings_instance.cache.enabled = False
            settings_instance.database.enabled = False
            mock_settings.return_value = settings_instance

            mock_app_instance = AsyncMock()
            mock_app_instance.client = AsyncMock()
            mock_app.return_value = mock_app_instance

            # Create app
            app, slack_service, llm_service, conversation_cache, prompt_service = (
                create_app()
            )

            # Verify disabled services are None
            assert app is not None
            assert slack_service is not None
            assert llm_service is not None
            assert conversation_cache is None
            assert prompt_service is None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_database_initialization_flow(self):
        """Test complete database initialization with migrations"""
        mock_database_url = "postgresql+asyncpg://test:test@localhost/test"

        with (
            patch("services.user_prompt_service.create_async_engine"),
            patch("services.user_prompt_service.async_sessionmaker"),
            patch(
                "services.user_prompt_service.MigrationManager"
            ) as mock_migration_manager,
        ):
            # Mock migration manager
            mock_migration_instance = AsyncMock()
            mock_migration_manager.return_value = mock_migration_instance
            mock_migration_instance.initialize = AsyncMock()
            mock_migration_instance.apply_migrations = AsyncMock()

            # Create and initialize service
            service = UserPromptService(mock_database_url)
            await service.initialize()

            # Verify initialization sequence
            mock_migration_manager.assert_called_once_with(mock_database_url)
            mock_migration_instance.initialize.assert_called_once()
            mock_migration_instance.apply_migrations.assert_called_once()

            # Verify migration manager was stored
            assert service.migration_manager is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_health_checker_with_all_services(self):
        """Test health checker with all services available"""
        with patch("health.Settings"):
            mock_settings_instance = MagicMock()
            mock_settings_instance.llm.api_url = "https://api.openai.com/v1"
            mock_settings_instance.slack.bot_token = "xoxb-test"
            mock_settings_instance.slack.app_token = "xapp-test"
            mock_settings_instance.llm.api_key.get_secret_value.return_value = (
                "test-key"
            )

            mock_conversation_cache = AsyncMock()
            mock_conversation_cache.get_cache_stats.return_value = {
                "total_conversations": 10,
                "cache_hits": 8,
                "cache_misses": 2,
            }

            mock_prompt_service = AsyncMock()
            mock_prompt_service.migration_manager = AsyncMock()
            mock_prompt_service.migration_manager.get_migration_status.return_value = {
                "total_migrations": 1,
                "applied_count": 1,
                "pending_count": 0,
            }

            health_checker = HealthChecker(
                mock_settings_instance,
                conversation_cache=mock_conversation_cache,
                prompt_service=mock_prompt_service,
            )

            # Verify health checker was created with all services
            assert health_checker.settings == mock_settings_instance
            assert health_checker.conversation_cache == mock_conversation_cache
            assert health_checker.prompt_service == mock_prompt_service

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_message_flow_with_prompt_service(self):
        """Test complete message flow with custom user prompt"""

        # Mock services
        mock_slack_service = AsyncMock()
        mock_slack_service.send_thinking_indicator.return_value = "thinking_ts"
        mock_slack_service.delete_thinking_indicator = AsyncMock()
        mock_slack_service.send_message = AsyncMock()
        mock_slack_service.get_thread_history = AsyncMock(return_value=([], True))

        mock_llm_service = AsyncMock()
        mock_llm_service.get_response.return_value = "I'm a Python expert response"

        mock_prompt_service = AsyncMock()
        mock_prompt_service.get_user_prompt.return_value = "You are a Python expert"

        with patch("handlers.message_handlers.MessageFormatter") as mock_formatter:
            mock_formatter.format_message = AsyncMock(
                return_value="I'm a Python expert response"
            )

            # Handle message
            await handle_message(
                text="What is Python?",
                user_id="U12345",
                slack_service=mock_slack_service,
                llm_service=mock_llm_service,
                channel="C12345",
                thread_ts="1234567890.123",
                conversation_cache=None,
                prompt_service=mock_prompt_service,
            )

        # Verify prompt service was consulted
        mock_prompt_service.get_user_prompt.assert_called_once_with("U12345")

        # Verify LLM was called
        mock_llm_service.get_response.assert_called_once()

        # Verify response was sent
        mock_slack_service.send_message.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_prompt_command_integration(self):
        """Test @prompt command integration with database"""

        mock_slack_service = AsyncMock()
        mock_llm_service = AsyncMock()
        mock_prompt_service = AsyncMock()
        mock_prompt_service.set_user_prompt = AsyncMock()

        # Handle @prompt command
        await handle_message(
            text="@prompt You are a helpful SQL expert",
            user_id="U12345",
            slack_service=mock_slack_service,
            llm_service=mock_llm_service,
            channel="C12345",
            thread_ts="1234567890.123",
            conversation_cache=None,
            prompt_service=mock_prompt_service,
        )

        # Verify prompt was saved to database
        mock_prompt_service.set_user_prompt.assert_called_once_with(
            "U12345", "You are a helpful SQL expert"
        )

        # Verify response was sent (not LLM call for @prompt commands)
        mock_slack_service.send_message.assert_called_once()
        mock_llm_service.get_response.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_conversation_cache_integration(self):
        """Test conversation cache integration with message handling"""

        mock_slack_service = AsyncMock()
        mock_llm_service = AsyncMock()
        mock_llm_service.get_response.return_value = "Cached response"

        mock_conversation_cache = AsyncMock()
        mock_conversation_cache.get_conversation.return_value = (
            [{"role": "user", "content": "Previous message"}],
            True,
            "cache",
        )
        mock_conversation_cache.update_conversation = AsyncMock()

        with patch("handlers.message_handlers.MessageFormatter") as mock_formatter:
            mock_formatter.format_message = AsyncMock(return_value="Cached response")

            await handle_message(
                text="Follow up question",
                user_id="U12345",
                slack_service=mock_slack_service,
                llm_service=mock_llm_service,
                channel="C12345",
                thread_ts="1234567890.123",
                conversation_cache=mock_conversation_cache,
                prompt_service=None,
            )

        # Verify cache was consulted
        mock_conversation_cache.get_conversation.assert_called_once_with(
            "C12345", "1234567890.123", mock_slack_service
        )

        # Verify conversation was updated with new messages
        assert (
            mock_conversation_cache.update_conversation.call_count == 2
        )  # User + bot message

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_error_handling_integration(self):
        """Test error handling across integrated components"""

        mock_slack_service = AsyncMock()
        mock_slack_service.send_thinking_indicator.return_value = "thinking_ts"
        mock_slack_service.delete_thinking_indicator = AsyncMock()

        mock_llm_service = AsyncMock()
        mock_llm_service.get_response.side_effect = Exception("LLM API error")

        mock_prompt_service = AsyncMock()
        mock_prompt_service.get_user_prompt.side_effect = Exception("Database error")

        with patch("handlers.message_handlers.handle_error") as mock_handle_error:
            await handle_message(
                text="Test message",
                user_id="U12345",
                slack_service=mock_slack_service,
                llm_service=mock_llm_service,
                channel="C12345",
                prompt_service=mock_prompt_service,
            )

        # Verify error handler was called
        mock_handle_error.assert_called_once()

        # Verify thinking indicator was cleaned up
        mock_slack_service.delete_thinking_indicator.assert_called_once_with(
            "C12345", "thinking_ts"
        )

    def test_settings_validation(self):
        """Test settings validation for required environment variables"""
        with patch.dict(
            os.environ,
            {
                "SLACK_BOT_TOKEN": "xoxb-test",
                "SLACK_APP_TOKEN": "xapp-test",
                "LLM_PROVIDER": "openai",
                "LLM_API_KEY": "test-key",
                "LLM_BASE_URL": "https://api.test.com",
                "DATABASE_URL": "postgresql+asyncpg://test:test@localhost/test",
            },
        ):
            settings = Settings()

            assert settings.slack.bot_token == "xoxb-test"
            assert settings.slack.app_token == "xapp-test"
            assert settings.llm.provider == "openai"
            assert settings.llm.base_url == "https://api.test.com"
            assert (
                settings.database.url == "postgresql+asyncpg://test:test@localhost/test"
            )

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_service_cleanup_on_shutdown(self):
        """Test that all services are properly cleaned up on shutdown"""
        mock_prompt_service = AsyncMock()
        mock_prompt_service.close = AsyncMock()
        mock_prompt_service.migration_manager = AsyncMock()
        mock_prompt_service.migration_manager.close = AsyncMock()

        mock_conversation_cache = AsyncMock()
        mock_conversation_cache.close = AsyncMock()

        mock_llm_service = AsyncMock()
        mock_llm_service.close = AsyncMock()

        mock_health_checker = AsyncMock()
        mock_health_checker.stop_server = AsyncMock()

        # Simulate cleanup (this would normally be in the finally block of run())
        await mock_prompt_service.close()
        await mock_conversation_cache.close()
        await mock_llm_service.close()
        await mock_health_checker.stop_server()

        # Verify all services were cleaned up
        mock_prompt_service.close.assert_called_once()
        mock_conversation_cache.close.assert_called_once()
        mock_llm_service.close.assert_called_once()
        mock_health_checker.stop_server.assert_called_once()
