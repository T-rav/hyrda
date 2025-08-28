import sys
import os
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.slack_service import SlackService
from config.settings import SlackSettings


class TestSlackService:
    """Tests for the SlackService class"""

    @pytest.fixture
    def slack_settings(self):
        """Create Slack settings for testing"""
        with patch.dict(os.environ, {
            "SLACK_BOT_TOKEN": "xoxb-test-token",
            "SLACK_APP_TOKEN": "xapp-test-token",
            "SLACK_BOT_ID": "B12345678"
        }):
            return SlackSettings()

    @pytest.fixture
    def mock_client(self):
        """Create mock Slack client"""
        return AsyncMock(spec=WebClient)

    @pytest.fixture
    def slack_service(self, slack_settings, mock_client):
        """Create SlackService instance for testing"""
        return SlackService(slack_settings, mock_client)

    @pytest.mark.asyncio
    async def test_init(self, slack_service, slack_settings, mock_client):
        """Test SlackService initialization"""
        assert slack_service.settings == slack_settings
        assert slack_service.client == mock_client
        assert slack_service.bot_id == "B12345678"

    @pytest.mark.asyncio
    async def test_send_message_success(self, slack_service):
        """Test successful message sending"""
        channel = "C12345"
        text = "Hello, World!"
        thread_ts = "1234567890.123456"
        
        # Mock successful response
        slack_service.client.chat_postMessage = AsyncMock(return_value={"ts": "1234567890.654321"})
        
        result = await slack_service.send_message(channel, text, thread_ts)
        
        assert result == "1234567890.654321"
        slack_service.client.chat_postMessage.assert_called_once_with(
            channel=channel,
            text=text,
            thread_ts=thread_ts,
            blocks=None,
            mrkdwn=True
        )

    @pytest.mark.asyncio
    async def test_send_message_with_blocks(self, slack_service):
        """Test message sending with blocks"""
        channel = "C12345"
        text = "Hello, World!"
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Hello"}}]
        
        slack_service.client.chat_postMessage = AsyncMock(return_value={"ts": "1234567890.654321"})
        
        result = await slack_service.send_message(channel, text, blocks=blocks)
        
        assert result == "1234567890.654321"
        slack_service.client.chat_postMessage.assert_called_once_with(
            channel=channel,
            text=text,
            thread_ts=None,
            blocks=blocks,
            mrkdwn=True
        )

    @pytest.mark.asyncio
    async def test_send_message_error(self, slack_service):
        """Test message sending with API error"""
        channel = "C12345"
        text = "Hello, World!"
        
        # Mock API error
        slack_service.client.chat_postMessage.side_effect = SlackApiError(
            message="Error", response={"error": "channel_not_found"}
        )
        
        result = await slack_service.send_message(channel, text)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_send_thinking_indicator_success(self, slack_service):
        """Test successful thinking indicator"""
        channel = "C12345"
        thread_ts = "1234567890.123456"
        
        slack_service.client.chat_postMessage = AsyncMock(return_value={"ts": "1234567890.654321"})
        
        result = await slack_service.send_thinking_indicator(channel, thread_ts)
        
        assert result == "1234567890.654321"
        slack_service.client.chat_postMessage.assert_called_once_with(
            channel=channel,
            text="⏳ _Thinking..._",
            thread_ts=thread_ts,
            mrkdwn=True
        )

    @pytest.mark.asyncio
    async def test_send_thinking_indicator_error(self, slack_service):
        """Test thinking indicator with error"""
        channel = "C12345"
        
        slack_service.client.chat_postMessage.side_effect = Exception("Network error")
        
        result = await slack_service.send_thinking_indicator(channel)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_thinking_indicator_success(self, slack_service):
        """Test successful thinking indicator deletion"""
        channel = "C12345"
        ts = "1234567890.654321"
        
        # Mock the delete_message function
        with patch('services.slack_service.delete_message', new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = True
            
            result = await slack_service.delete_thinking_indicator(channel, ts)
            
            assert result is True
            mock_delete.assert_called_once_with(slack_service.client, channel, ts)

    @pytest.mark.asyncio
    async def test_delete_thinking_indicator_no_ts(self, slack_service):
        """Test thinking indicator deletion with no timestamp"""
        channel = "C12345"
        
        result = await slack_service.delete_thinking_indicator(channel, None)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_get_thread_history_success(self, slack_service):
        """Test successful thread history retrieval"""
        channel = "C12345"
        thread_ts = "1234567890.123456"
        
        # Mock API response
        mock_messages = [
            {"text": "Hello", "user": "U12345", "ts": "1234567890.123456"},
            {"text": "Hi there!", "user": "B12345678", "ts": "1234567890.234567"},
            {"text": "How are you?", "user": "U12345", "ts": "1234567890.345678"}
        ]
        
        slack_service.client.conversations_replies = AsyncMock(return_value={
            "messages": mock_messages
        })
        
        messages, success = await slack_service.get_thread_history(channel, thread_ts)
        
        assert success is True
        assert len(messages) == 3
        assert messages[0] == {"role": "user", "content": "Hello"}
        assert messages[1] == {"role": "assistant", "content": "Hi there!"}
        assert messages[2] == {"role": "user", "content": "How are you?"}

    @pytest.mark.asyncio
    async def test_get_thread_history_with_mentions(self, slack_service):
        """Test thread history with mentions cleanup"""
        channel = "C12345"
        thread_ts = "1234567890.123456"
        
        mock_messages = [
            {"text": "<@B12345678> hello", "user": "U12345", "ts": "1234567890.123456"},
            {"text": "Hi there!", "user": "B12345678", "ts": "1234567890.234567"}
        ]
        
        slack_service.client.conversations_replies = AsyncMock(return_value={
            "messages": mock_messages
        })
        
        messages, success = await slack_service.get_thread_history(channel, thread_ts)
        
        assert success is True
        assert len(messages) == 2
        assert messages[0] == {"role": "user", "content": "hello"}
        assert messages[1] == {"role": "assistant", "content": "Hi there!"}

    @pytest.mark.asyncio
    async def test_get_thread_history_empty_messages(self, slack_service):
        """Test thread history with empty messages"""
        channel = "C12345"
        thread_ts = "1234567890.123456"
        
        mock_messages = [
            {"text": "", "user": "U12345", "ts": "1234567890.123456"},
            {"text": "   ", "user": "U12345", "ts": "1234567890.234567"},
            {"text": "Hello", "user": "U12345", "ts": "1234567890.345678"}
        ]
        
        slack_service.client.conversations_replies = AsyncMock(return_value={
            "messages": mock_messages
        })
        
        messages, success = await slack_service.get_thread_history(channel, thread_ts)
        
        assert success is True
        assert len(messages) == 1
        assert messages[0] == {"role": "user", "content": "Hello"}

    @pytest.mark.asyncio
    async def test_get_thread_history_error(self, slack_service):
        """Test thread history with API error"""
        channel = "C12345"
        thread_ts = "1234567890.123456"
        
        slack_service.client.conversations_replies.side_effect = Exception("API error")
        
        messages, success = await slack_service.get_thread_history(channel, thread_ts)
        
        assert success is False
        assert messages == []

    @pytest.mark.asyncio
    async def test_get_thread_history_no_bot_id(self, slack_service):
        """Test thread history when bot ID is not set"""
        slack_service.bot_id = None
        channel = "C12345"
        thread_ts = "1234567890.123456"
        
        mock_messages = [
            {"text": "Hello", "user": "U12345", "ts": "1234567890.123456"}
        ]
        
        slack_service.client.conversations_replies = AsyncMock(return_value={
            "messages": mock_messages
        })
        slack_service.client.auth_test = AsyncMock(return_value={"user_id": "B12345678"})
        
        messages, success = await slack_service.get_thread_history(channel, thread_ts)
        
        assert success is True
        assert slack_service.bot_id == "B12345678"
        slack_service.client.auth_test.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_thread_info_success(self, slack_service):
        """Test successful thread info retrieval"""
        channel = "C12345"
        thread_ts = "1234567890.123456"
        
        mock_messages = [
            {"user": "U12345", "ts": "1234567890.123456"},
            {"user": "B12345678", "ts": "1234567890.234567"},
            {"user": "U67890", "ts": "1234567890.345678"}
        ]
        
        slack_service.client.conversations_replies = AsyncMock(return_value={
            "messages": mock_messages
        })
        
        thread_info = await slack_service.get_thread_info(channel, thread_ts)
        
        assert thread_info["exists"] is True
        assert thread_info["message_count"] == 3
        assert thread_info["bot_is_participant"] is True
        assert set(thread_info["participant_ids"]) == {"U12345", "B12345678", "U67890"}
        assert thread_info["error"] is None

    @pytest.mark.asyncio
    async def test_get_thread_info_bot_not_participant(self, slack_service):
        """Test thread info when bot is not a participant"""
        channel = "C12345"
        thread_ts = "1234567890.123456"
        
        mock_messages = [
            {"user": "U12345", "ts": "1234567890.123456"},
            {"user": "U67890", "ts": "1234567890.234567"}
        ]
        
        slack_service.client.conversations_replies = AsyncMock(return_value={
            "messages": mock_messages
        })
        
        thread_info = await slack_service.get_thread_info(channel, thread_ts)
        
        assert thread_info["exists"] is True
        assert thread_info["message_count"] == 2
        assert thread_info["bot_is_participant"] is False
        assert set(thread_info["participant_ids"]) == {"U12345", "U67890"}

    @pytest.mark.asyncio
    async def test_get_thread_info_no_bot_id(self, slack_service):
        """Test thread info when bot ID is not set"""
        slack_service.bot_id = None
        channel = "C12345"
        thread_ts = "1234567890.123456"
        
        mock_messages = [
            {"user": "U12345", "ts": "1234567890.123456"}
        ]
        
        slack_service.client.conversations_replies = AsyncMock(return_value={
            "messages": mock_messages
        })
        slack_service.client.auth_test = AsyncMock(return_value={"user_id": "B12345678"})
        
        thread_info = await slack_service.get_thread_info(channel, thread_ts)
        
        assert slack_service.bot_id == "B12345678"
        slack_service.client.auth_test.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_thread_info_permission_error(self, slack_service):
        """Test thread info with permission error"""
        channel = "C12345"
        thread_ts = "1234567890.123456"
        
        error_msg = "missing_scope: needed: 'channels:history'"
        slack_service.client.conversations_replies.side_effect = Exception(error_msg)
        
        thread_info = await slack_service.get_thread_info(channel, thread_ts)
        
        assert thread_info["exists"] is False
        assert "Missing permission scope: channels:history" in thread_info["error"]

    @pytest.mark.asyncio
    async def test_get_thread_info_generic_error(self, slack_service):
        """Test thread info with generic error"""
        channel = "C12345"
        thread_ts = "1234567890.123456"
        
        slack_service.client.conversations_replies.side_effect = Exception("Generic error")
        
        thread_info = await slack_service.get_thread_info(channel, thread_ts)
        
        assert thread_info["exists"] is False
        assert thread_info["error"] == "Generic error"

    @pytest.mark.asyncio
    async def test_get_thread_info_no_messages(self, slack_service):
        """Test thread info with no messages"""
        channel = "C12345"
        thread_ts = "1234567890.123456"
        
        slack_service.client.conversations_replies.return_value = {}
        
        thread_info = await slack_service.get_thread_info(channel, thread_ts)
        
        assert thread_info["exists"] is False
        assert thread_info["message_count"] == 0
        assert thread_info["bot_is_participant"] is False