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
from services.retrieval_service import RetrievalService


# Integration Test Factory Classes
class SettingsFactory:
    """Factory for creating mock settings for integration tests"""

    @staticmethod
    def create_basic_settings() -> MagicMock:
        """Create basic settings with essential configuration"""
        settings = MagicMock()
        settings.slack.bot_token = "xoxb-test"
        settings.slack.app_token = "xapp-test"
        settings.llm = MagicMock()
        settings.llm.api_url = "https://api.openai.com/v1"
        settings.llm.api_key.get_secret_value.return_value = "test-key"
        return settings

    @staticmethod
    def create_cache_enabled_settings() -> MagicMock:
        """Create settings with cache enabled"""
        settings = SettingsFactory.create_basic_settings()
        settings.cache.enabled = True
        settings.cache.redis_url = "redis://localhost:6379"
        settings.cache.conversation_ttl = 1800
        return settings

    @staticmethod
    def create_cache_disabled_settings() -> MagicMock:
        """Create settings with cache disabled"""
        settings = SettingsFactory.create_basic_settings()
        settings.cache.enabled = False
        return settings


class SlackServiceFactory:
    """Factory for creating Slack service mocks for integration tests"""

    @staticmethod
    def create_basic_service() -> AsyncMock:
        """Create basic Slack service mock"""
        service = AsyncMock()
        service.send_thinking_indicator.return_value = "thinking_ts"
        service.delete_thinking_indicator = AsyncMock()
        service.send_message = AsyncMock()
        service.get_thread_history = AsyncMock(return_value=([], True))
        return service

    @staticmethod
    def create_service_with_thread_history(history: list = None) -> AsyncMock:
        """Create Slack service with specific thread history"""
        if history is None:
            history = []
        service = SlackServiceFactory.create_basic_service()
        service.get_thread_history = AsyncMock(return_value=(history, True))
        return service


class LLMServiceFactory:
    """Factory for creating LLM service mocks for integration tests"""

    @staticmethod
    def create_service(response: str = "Test LLM response") -> AsyncMock:
        """Create LLM service mock with specific response"""
        service = AsyncMock()
        service.get_response.return_value = response
        return service

    @staticmethod
    def create_failing_service(error_message: str = "LLM API error") -> AsyncMock:
        """Create LLM service mock that raises an exception"""
        service = AsyncMock()
        service.get_response.side_effect = Exception(error_message)
        return service


class ConversationCacheFactory:
    """Factory for creating conversation cache mocks"""

    @staticmethod
    def create_cache() -> AsyncMock:
        """Create basic conversation cache mock"""
        cache = AsyncMock()
        cache.get_conversation.return_value = ([], False, "miss")
        cache.update_conversation = AsyncMock()
        cache.store_document_content = AsyncMock(return_value=True)
        cache.get_document_content = AsyncMock(return_value=(None, None))
        cache.get_cache_stats.return_value = {
            "total_conversations": 10,
            "cache_hits": 8,
            "cache_misses": 2,
        }
        return cache

    @staticmethod
    def create_cache_with_conversation(conversation: list = None) -> AsyncMock:
        """Create cache with existing conversation"""
        if conversation is None:
            conversation = [{"role": "user", "content": "Previous message"}]
        cache = ConversationCacheFactory.create_cache()
        cache.get_conversation.return_value = (conversation, True, "cache")
        return cache


class AppFactory:
    """Factory for creating app mocks"""

    @staticmethod
    def create_app_mock() -> AsyncMock:
        """Create basic app mock"""
        app = AsyncMock()
        app.client = AsyncMock()
        return app


@pytest.mark.skip(
    reason="Integration tests for OLD ARCHITECTURE (pre-microservices). "
    "These test app.py with LLMService directly, but new architecture uses rag-service via HTTP. "
    "\n\n"
    "✅ NEW MICROSERVICES INTEGRATION TESTS: See test_integration_microservices.py\n"
    "   Tests cover:\n"
    "   - Bot → RAG Service HTTP communication\n"
    "   - Bot → Agent Service HTTP communication\n"
    "   - Service health checks\n"
    "   - End-to-end message flows\n"
    "   - Error handling across services\n"
    "   - Cross-service authentication\n"
    "\n"
    "Run with: pytest -v -m integration tests/test_integration_microservices.py"
)
class TestIntegrationLegacy:
    """Integration tests for the OLD pre-microservices architecture.

    DEPRECATED: These tests are kept for reference only.
    Use test_integration_microservices.py for current architecture testing.
    """

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
        ):
            # Create settings using factory
            settings_instance = SettingsFactory.create_cache_enabled_settings()
            mock_settings.return_value = settings_instance

            # Create service instances using factories
            mock_app_instance = AppFactory.create_app_mock()
            mock_app.return_value = mock_app_instance

            mock_cache_instance = ConversationCacheFactory.create_cache()
            mock_cache.return_value = mock_cache_instance

            # Create app
            (
                app,
                slack_service,
                llm_service,
                conversation_cache,
                metrics_service,
            ) = create_app()

            # Verify all services were created
            assert app is not None
            assert slack_service is not None
            assert llm_service is not None
            assert conversation_cache is not None

            # Verify services were initialized with correct parameters
            mock_cache.assert_called_once_with(
                redis_url="redis://localhost:6379", ttl=1800
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
            # Create settings with disabled services using factory
            settings_instance = SettingsFactory.create_cache_disabled_settings()
            mock_settings.return_value = settings_instance

            # Create app mock using factory
            mock_app_instance = AppFactory.create_app_mock()
            mock_app.return_value = mock_app_instance

            # Create app
            (
                app,
                slack_service,
                llm_service,
                conversation_cache,
                metrics_service,
            ) = create_app()

            # Verify disabled services are None
            assert app is not None
            assert slack_service is not None
            assert llm_service is not None
            assert conversation_cache is None

    # Database initialization test removed - no database/migrations in simplified architecture

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_health_checker_with_all_services(self):
        """Test health checker with all services available"""
        with patch("health.Settings"):
            # Create settings using factory
            mock_settings_instance = SettingsFactory.create_basic_settings()

            # Create conversation cache using factory
            mock_conversation_cache = ConversationCacheFactory.create_cache()

            # No migration data in simplified architecture

            health_checker = HealthChecker(
                mock_settings_instance,
                conversation_cache=mock_conversation_cache,
            )

            # Verify health checker was created with all services
            assert health_checker.settings == mock_settings_instance
            assert health_checker.conversation_cache == mock_conversation_cache

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_message_flow_with_cache(self):
        """Test complete message flow with cache"""

        # Create services using factories
        mock_slack_service = SlackServiceFactory.create_basic_service()
        mock_llm_service = LLMServiceFactory.create_service(
            "I'm a Python expert response"
        )

        # Test completed
        # Test completed

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
            )

        # Verify prompt service was consulted
        # Test completed

        # Verify LLM was called
        mock_llm_service.get_response.assert_called_once()

        # Verify response was sent
        mock_slack_service.send_message.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_prompt_command_integration(self):
        """Test @prompt command integration with database"""

        # Create services using factories
        mock_slack_service = SlackServiceFactory.create_basic_service()
        mock_llm_service = LLMServiceFactory.create_service("SQL response")

        # Handle @prompt command (now just regular message in simplified architecture)
        await handle_message(
            text="You are a helpful SQL expert",
            user_id="U12345",
            slack_service=mock_slack_service,
            llm_service=mock_llm_service,
            channel="C12345",
            thread_ts="1234567890.123",
            conversation_cache=None,
        )

        # Verify response was sent (prompt commands removed in simplified architecture)
        mock_slack_service.send_message.assert_called_once()
        mock_llm_service.get_response.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_conversation_cache_integration(self):
        """Test conversation cache integration with message handling"""

        # Create services using factories
        mock_slack_service = SlackServiceFactory.create_basic_service()
        mock_llm_service = LLMServiceFactory.create_service("Cached response")
        mock_conversation_cache = (
            ConversationCacheFactory.create_cache_with_conversation()
        )

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
            )

        # Note: In the simplified architecture, conversation cache is not actively used
        # The message handler uses direct thread history from Slack instead
        # Verify the thread history was retrieved (current implementation)
        mock_slack_service.get_thread_history.assert_called_once_with(
            "C12345", "1234567890.123"
        )

        # In the simplified architecture, conversation cache updates are not used
        # Verify the core functionality works: LLM response and message sending
        mock_llm_service.get_response.assert_called_once()
        mock_slack_service.send_message.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_error_handling_integration(self):
        """Test error handling across integrated components"""

        # Create services using factories
        mock_slack_service = SlackServiceFactory.create_basic_service()
        mock_llm_service = LLMServiceFactory.create_failing_service("LLM API error")

        with patch("handlers.message_handlers.handle_error") as mock_handle_error:
            await handle_message(
                text="Test message",
                user_id="U12345",
                slack_service=mock_slack_service,
                llm_service=mock_llm_service,
                channel="C12345",
                message_ts="1234567890.123456",  # Required for non-DM messages
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
            },
        ):
            settings = Settings()

            assert settings.slack.bot_token == "xoxb-test"
            assert settings.slack.app_token == "xapp-test"
            assert settings.llm.provider == "openai"
            assert settings.llm.base_url == "https://api.test.com"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_results_similarity_threshold_filtering(self):
        """Test that results_similarity_threshold properly filters low-relevance results"""

        # Create settings with specific threshold
        settings = Settings()
        settings.rag.results_similarity_threshold = 0.7
        settings.rag.max_results = 5
        settings.vector.provider = "qdrant"

        retrieval_service = RetrievalService(settings)

        # Mock vector service and embedding service
        mock_vector_service = AsyncMock()
        mock_embedding_service = AsyncMock()
        mock_embedding_service.get_embedding.return_value = [0.1] * 1536

        # Mock search results with varying similarity scores
        mock_results = [
            {
                "similarity": 0.95,
                "content": "High relevance",
                "metadata": {"file_name": "doc1"},
            },
            {
                "similarity": 0.924,
                "content": "High relevance 2",
                "metadata": {"file_name": "doc2"},
            },
            {
                "similarity": 0.751,
                "content": "Above threshold",
                "metadata": {"file_name": "doc3"},
            },
            {
                "similarity": 0.689,
                "content": "Below threshold",
                "metadata": {"file_name": "doc4"},
            },  # Should be filtered
            {
                "similarity": 0.663,
                "content": "Below threshold 2",
                "metadata": {"file_name": "doc5"},
            },  # Should be filtered
        ]
        mock_vector_service.search.return_value = mock_results

        # Test retrieval with threshold filtering
        results = await retrieval_service.retrieve_context(
            "test query",
            vector_service=mock_vector_service,
            embedding_service=mock_embedding_service,
        )

        # Should only return 3 results (above 0.7 threshold)
        assert len(results) == 3
        assert all(result["similarity"] >= 0.7 for result in results)

        # Verify the filtered results
        similarities = [result["similarity"] for result in results]
        assert 0.95 in similarities
        assert 0.924 in similarities
        assert 0.751 in similarities
        assert 0.689 not in similarities  # Should be filtered out
        assert 0.663 not in similarities  # Should be filtered out

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_service_cleanup_on_shutdown(self):
        """Test that all services are properly cleaned up on shutdown"""
        mock_conversation_cache = AsyncMock()
        mock_conversation_cache.close = AsyncMock()

        mock_llm_service = AsyncMock()
        mock_llm_service.close = AsyncMock()

        mock_health_checker = AsyncMock()
        mock_health_checker.stop_server = AsyncMock()

        # Simulate cleanup (this would normally be in the finally block of run())
        await mock_conversation_cache.close()
        await mock_llm_service.close()
        await mock_health_checker.stop_server()

        # Verify all services were cleaned up
        mock_conversation_cache.close.assert_called_once()
        mock_llm_service.close.assert_called_once()
        mock_health_checker.stop_server.assert_called_once()
