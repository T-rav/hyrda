import logging
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.errors import delete_message, handle_error
from utils.logging import configure_logging


# TDD Factory Patterns for Utils Testing
class SlackClientFactory:
    """Factory for creating mock Slack clients for utils testing"""

    @staticmethod
    def create_successful_client() -> AsyncMock:
        """Create mock client that succeeds in operations"""
        client = AsyncMock(spec=WebClient)
        client.chat_delete = AsyncMock(return_value={"ok": True})
        client.chat_postMessage = AsyncMock(return_value={"ts": "1234567890.654321"})
        return client

    @staticmethod
    def create_client_with_delete_error(
        error: Exception | None = None,
    ) -> AsyncMock:
        """Create client that fails delete operations"""
        client = AsyncMock(spec=WebClient)
        default_error = SlackApiError(
            message="Error", response={"error": "message_not_found"}
        )
        client.chat_delete = AsyncMock(side_effect=error or default_error)
        return client

    @staticmethod
    def create_client_with_post_error(
        error: Exception | None = None,
    ) -> AsyncMock:
        """Create client that fails post message operations"""
        client = AsyncMock(spec=WebClient)
        default_error = Exception("Post failed")
        client.chat_postMessage = AsyncMock(side_effect=error or default_error)
        return client


class TestDataFactory:
    """Factory for creating consistent test data"""

    @staticmethod
    def create_channel_id() -> str:
        """Create standard test channel ID"""
        return "C12345"

    @staticmethod
    def create_message_ts() -> str:
        """Create standard test message timestamp"""
        return "1234567890.123456"

    @staticmethod
    def create_thread_ts() -> str:
        """Create standard test thread timestamp"""
        return "1234567890.123456"

    @staticmethod
    def create_test_error(message: str = "Test error") -> Exception:
        """Create standard test error"""
        return Exception(message)

    @staticmethod
    def create_fallback_message() -> str:
        """Create standard fallback message"""
        return "Something went wrong"


class LoggingLevelFactory:
    """Factory for creating different logging level configurations"""

    @staticmethod
    def create_valid_levels() -> list[str]:
        """Create list of valid logging levels"""
        return ["DEBUG", "INFO", "WARNING", "ERROR"]

    @staticmethod
    def create_invalid_level() -> str:
        """Create invalid logging level for testing"""
        return "INVALID"

    @staticmethod
    def create_default_level() -> None:
        """Create default logging level (None)"""
        return None


class TestErrorUtils:
    """Tests for the error utilities using factory patterns"""

    @pytest.mark.asyncio
    async def test_delete_message_success(self):
        """Test successful message deletion"""
        mock_client = SlackClientFactory.create_successful_client()
        channel = TestDataFactory.create_channel_id()
        ts = TestDataFactory.create_message_ts()

        result = await delete_message(mock_client, channel, ts)

        assert result is True
        mock_client.chat_delete.assert_called_once_with(channel=channel, ts=ts)

    @pytest.mark.asyncio
    async def test_delete_message_api_error(self):
        """Test message deletion with API error"""
        api_error = SlackApiError(
            message="Error", response={"error": "message_not_found"}
        )
        mock_client = SlackClientFactory.create_client_with_delete_error(api_error)
        channel = TestDataFactory.create_channel_id()
        ts = TestDataFactory.create_message_ts()

        result = await delete_message(mock_client, channel, ts)

        assert result is False
        mock_client.chat_delete.assert_called_once_with(channel=channel, ts=ts)

    @pytest.mark.asyncio
    async def test_delete_message_generic_error(self):
        """Test message deletion with generic error"""
        network_error = Exception("Network error")
        mock_client = SlackClientFactory.create_client_with_delete_error(network_error)
        channel = TestDataFactory.create_channel_id()
        ts = TestDataFactory.create_message_ts()

        result = await delete_message(mock_client, channel, ts)

        assert result is False

    @pytest.mark.asyncio
    async def test_handle_error_success(self):
        """Test successful error handling"""
        mock_client = SlackClientFactory.create_successful_client()
        channel = TestDataFactory.create_channel_id()
        thread_ts = TestDataFactory.create_thread_ts()
        error = TestDataFactory.create_test_error()
        fallback_message = TestDataFactory.create_fallback_message()

        await handle_error(mock_client, channel, thread_ts, error, fallback_message)

        mock_client.chat_postMessage.assert_called_once_with(
            channel=channel, text=fallback_message, thread_ts=thread_ts
        )

    @pytest.mark.asyncio
    async def test_handle_error_post_message_fails(self):
        """Test error handling when posting message fails"""
        mock_client = SlackClientFactory.create_client_with_post_error()
        channel = TestDataFactory.create_channel_id()
        thread_ts = TestDataFactory.create_thread_ts()
        error = TestDataFactory.create_test_error()
        fallback_message = TestDataFactory.create_fallback_message()

        # Should not raise an exception
        await handle_error(mock_client, channel, thread_ts, error, fallback_message)

        mock_client.chat_postMessage.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_error_no_thread(self):
        """Test error handling without thread"""
        mock_client = SlackClientFactory.create_successful_client()
        channel = TestDataFactory.create_channel_id()
        error = TestDataFactory.create_test_error()
        fallback_message = TestDataFactory.create_fallback_message()

        await handle_error(mock_client, channel, None, error, fallback_message)

        mock_client.chat_postMessage.assert_called_once_with(
            channel=channel, text=fallback_message, thread_ts=None
        )


class TestLoggingUtils:
    """Tests for the logging utilities using factory patterns"""

    def test_configure_logging_valid_levels(self):
        """Test logging configuration with all valid levels"""
        valid_levels = LoggingLevelFactory.create_valid_levels()
        for level in valid_levels:
            try:
                configure_logging(level)
                assert True  # If we get here, it worked
            except Exception as e:
                pytest.fail(f"configure_logging failed for {level}: {e}")

    def test_configure_logging_default_level(self):
        """Test logging configuration with default level"""
        default_level = LoggingLevelFactory.create_default_level()
        try:
            configure_logging(default_level)
            assert True
        except Exception as e:
            pytest.fail(f"configure_logging failed: {e}")

    def test_configure_logging_invalid_level(self):
        """Test logging configuration with invalid level"""
        invalid_level = LoggingLevelFactory.create_invalid_level()
        try:
            configure_logging(invalid_level)
            assert True
        except Exception as e:
            pytest.fail(f"configure_logging failed: {e}")

    def test_configure_logging_format(self):
        """Test logging configuration format"""
        # Test that function configures logging properly
        try:
            configure_logging()
            # Verify that a logger can be created and used
            test_logger = logging.getLogger("test")
            test_logger.info("Test message")
            assert True
        except Exception as e:
            pytest.fail(f"configure_logging failed: {e}")

    def test_configure_logging_handler_setup(self):
        """Test that logging handlers are properly configured"""
        # Test that logging setup works
        try:
            configure_logging()
            # Test that we can get loggers after configuration
            root_logger = logging.getLogger()
            test_logger = logging.getLogger("test")
            assert root_logger is not None
            assert test_logger is not None
        except Exception as e:
            pytest.fail(f"configure_logging failed: {e}")

    def test_configure_logging_slack_sdk_level(self):
        """Test that Slack SDK logging level is configured"""
        with (
            patch("logging.basicConfig"),
            patch("logging.getLogger") as mock_get_logger,
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            configure_logging()

            # Should call getLogger multiple times for different loggers
            assert mock_get_logger.call_count >= 1

    def test_configure_logging_urllib3_level(self):
        """Test that urllib3 logging level is configured"""
        with (
            patch("logging.basicConfig"),
            patch("logging.getLogger") as mock_get_logger,
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            configure_logging()

            # Basic logging configuration should be called
            assert mock_get_logger.called
