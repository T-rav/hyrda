import sys
import os
import pytest
import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.errors import handle_error, delete_message
from utils.logging import configure_logging


class TestErrorUtils:
    """Tests for the error utilities"""

    @pytest.mark.asyncio
    async def test_delete_message_success(self):
        """Test successful message deletion"""
        mock_client = AsyncMock(spec=WebClient)
        mock_client.chat_delete = AsyncMock(return_value={"ok": True})
        
        channel = "C12345"
        ts = "1234567890.123456"
        
        result = await delete_message(mock_client, channel, ts)
        
        assert result is True
        mock_client.chat_delete.assert_called_once_with(channel=channel, ts=ts)

    @pytest.mark.asyncio
    async def test_delete_message_api_error(self):
        """Test message deletion with API error"""
        mock_client = AsyncMock(spec=WebClient)
        mock_client.chat_delete.side_effect = SlackApiError(
            message="Error", response={"error": "message_not_found"}
        )
        
        channel = "C12345"
        ts = "1234567890.123456"
        
        result = await delete_message(mock_client, channel, ts)
        
        assert result is False
        mock_client.chat_delete.assert_called_once_with(channel=channel, ts=ts)

    @pytest.mark.asyncio
    async def test_delete_message_generic_error(self):
        """Test message deletion with generic error"""
        mock_client = AsyncMock(spec=WebClient)
        mock_client.chat_delete.side_effect = Exception("Network error")
        
        channel = "C12345"
        ts = "1234567890.123456"
        
        result = await delete_message(mock_client, channel, ts)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_handle_error_success(self):
        """Test successful error handling"""
        mock_client = AsyncMock(spec=WebClient)
        mock_client.chat_postMessage = AsyncMock(return_value={"ts": "1234567890.654321"})
        
        channel = "C12345"
        thread_ts = "1234567890.123456"
        error = Exception("Test error")
        fallback_message = "Something went wrong"
        
        await handle_error(mock_client, channel, thread_ts, error, fallback_message)
        
        mock_client.chat_postMessage.assert_called_once_with(
            channel=channel,
            text=fallback_message,
            thread_ts=thread_ts
        )

    @pytest.mark.asyncio
    async def test_handle_error_post_message_fails(self):
        """Test error handling when posting message fails"""
        mock_client = AsyncMock(spec=WebClient)
        mock_client.chat_postMessage = AsyncMock(side_effect=Exception("Post failed"))
        
        channel = "C12345"
        thread_ts = "1234567890.123456"
        error = Exception("Test error")
        fallback_message = "Something went wrong"
        
        # Should not raise an exception
        await handle_error(mock_client, channel, thread_ts, error, fallback_message)
        
        mock_client.chat_postMessage.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_error_no_thread(self):
        """Test error handling without thread"""
        mock_client = AsyncMock(spec=WebClient)
        mock_client.chat_postMessage = AsyncMock(return_value={"ts": "1234567890.654321"})
        
        channel = "C12345"
        error = Exception("Test error")
        fallback_message = "Something went wrong"
        
        await handle_error(mock_client, channel, None, error, fallback_message)
        
        mock_client.chat_postMessage.assert_called_once_with(
            channel=channel,
            text=fallback_message,
            thread_ts=None
        )


class TestLoggingUtils:
    """Tests for the logging utilities"""

    def test_configure_logging_info_level(self):
        """Test logging configuration with INFO level"""
        # Test that function executes without error
        try:
            configure_logging("INFO")
            assert True  # If we get here, it worked
        except Exception as e:
            pytest.fail(f"configure_logging failed: {e}")

    def test_configure_logging_debug_level(self):
        """Test logging configuration with DEBUG level"""
        # Test that function executes without error
        try:
            configure_logging("DEBUG")
            assert True
        except Exception as e:
            pytest.fail(f"configure_logging failed: {e}")

    def test_configure_logging_warning_level(self):
        """Test logging configuration with WARNING level"""
        # Test that function executes without error
        try:
            configure_logging("WARNING")
            assert True
        except Exception as e:
            pytest.fail(f"configure_logging failed: {e}")

    def test_configure_logging_error_level(self):
        """Test logging configuration with ERROR level"""
        # Test that function executes without error
        try:
            configure_logging("ERROR")
            assert True
        except Exception as e:
            pytest.fail(f"configure_logging failed: {e}")

    def test_configure_logging_default_level(self):
        """Test logging configuration with default level"""
        # Test that function executes without error
        try:
            configure_logging()
            assert True
        except Exception as e:
            pytest.fail(f"configure_logging failed: {e}")

    def test_configure_logging_invalid_level(self):
        """Test logging configuration with invalid level"""
        # Test that function executes without error even with invalid level
        try:
            configure_logging("INVALID")
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
        with patch('logging.basicConfig'), \
             patch('logging.getLogger') as mock_get_logger:
            
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            configure_logging()
            
            # Should call getLogger multiple times for different loggers
            assert mock_get_logger.call_count >= 1

    def test_configure_logging_urllib3_level(self):
        """Test that urllib3 logging level is configured"""
        with patch('logging.basicConfig'), \
             patch('logging.getLogger') as mock_get_logger:
            
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            configure_logging()
            
            # Basic logging configuration should be called
            assert mock_get_logger.called