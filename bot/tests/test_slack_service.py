import os
import sys
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import SlackSettings
from services.slack_service import SlackService
from tests.utils.builders.thread_history_builder import ThreadHistoryBuilder


class SlackSettingsFactory:
    """Factory for creating Slack service settings with different configurations"""

    @staticmethod
    def create_basic_settings(
        bot_token: str = "xoxb-test-token",
        app_token: str = "xapp-test-token",
        bot_id: str = "B12345678",
    ) -> SlackSettings:
        """Create basic Slack settings"""
        with patch.dict(
            os.environ,
            {
                "SLACK_BOT_TOKEN": bot_token,
                "SLACK_APP_TOKEN": app_token,
                "SLACK_BOT_ID": bot_id,
            },
        ):
            return SlackSettings()

    @staticmethod
    def create_production_settings() -> SlackSettings:
        """Create production-like Slack settings"""
        return SlackSettingsFactory.create_basic_settings(
            bot_token="xoxb-prod-token-12345",
            app_token="xapp-prod-token-67890",
            bot_id="B08RGGA6QKS",
        )

    @staticmethod
    def create_invalid_settings() -> SlackSettings:
        """Create invalid Slack settings for error testing"""
        return SlackSettingsFactory.create_basic_settings(
            bot_token="invalid-token",
            app_token="invalid-app-token",
            bot_id="BINVALID",
        )


class SlackClientFactory:
    """Factory for creating mock Slack clients"""

    @staticmethod
    def create_basic_client() -> AsyncMock:
        """Create basic mock Slack client"""
        return AsyncMock(spec=WebClient)

    @staticmethod
    def create_client_with_success_response(
        response: dict[str, Any] | None = None,
    ) -> AsyncMock:
        """Create mock client that returns successful responses"""
        client = SlackClientFactory.create_basic_client()
        default_response = {"ts": "1234567890.654321"}
        client.chat_postMessage = AsyncMock(return_value=response or default_response)
        return client

    @staticmethod
    def create_client_with_error(
        error: Exception | None = None,
    ) -> AsyncMock:
        """Create mock client that raises errors"""
        client = SlackClientFactory.create_basic_client()
        default_error = SlackApiError(
            message="Error", response={"error": "channel_not_found"}
        )
        client.chat_postMessage.side_effect = error or default_error
        return client

    @staticmethod
    def create_client_with_thread_history(
        messages: list[dict[str, Any]] | None = None,
    ) -> AsyncMock:
        """Create mock client with thread history responses"""
        client = SlackClientFactory.create_basic_client()
        default_messages = [
            {"text": "Hello", "user": "U12345", "ts": "1234567890.123456"},
            {"text": "Hi there!", "user": "B12345678", "ts": "1234567890.234567"},
        ]
        client.conversations_replies = AsyncMock(
            return_value={"messages": messages or default_messages}
        )
        return client

    @staticmethod
    def create_client_with_auth_test(
        user_id: str = "B12345678",
        bot_id: str = "B08RGGA6QKS",
    ) -> AsyncMock:
        """Create mock client with auth test response"""
        client = SlackClientFactory.create_basic_client()
        client.auth_test = AsyncMock(
            return_value={"user_id": user_id, "bot_id": bot_id}
        )
        return client


class SlackServiceFactory:
    """Factory for creating SlackService instances"""

    @staticmethod
    def create_service_with_basic_client(
        settings: SlackSettings | None = None,
        client: AsyncMock | None = None,
    ) -> SlackService:
        """Create SlackService with basic configuration"""
        return SlackService(
            settings or SlackSettingsFactory.create_basic_settings(),
            client or SlackClientFactory.create_basic_client(),
        )

    @staticmethod
    def create_service_with_successful_client(
        response: dict[str, Any] | None = None,
    ) -> SlackService:
        """Create SlackService with client that returns successful responses"""
        return SlackService(
            SlackSettingsFactory.create_basic_settings(),
            SlackClientFactory.create_client_with_success_response(response),
        )

    @staticmethod
    def create_service_with_error_client(
        error: Exception | None = None,
    ) -> SlackService:
        """Create SlackService with client that raises errors"""
        return SlackService(
            SlackSettingsFactory.create_basic_settings(),
            SlackClientFactory.create_client_with_error(error),
        )

    @staticmethod
    def create_service_with_thread_history(
        messages: list[dict[str, Any]] | None = None,
    ) -> SlackService:
        """Create SlackService with mock thread history"""
        return SlackService(
            SlackSettingsFactory.create_basic_settings(),
            SlackClientFactory.create_client_with_thread_history(messages),
        )

    @staticmethod
    def create_service_without_bot_id() -> SlackService:
        """Create SlackService without bot ID set"""
        service = SlackServiceFactory.create_service_with_basic_client()
        service.bot_id = None
        if hasattr(service, "bot_user_id"):
            service.bot_user_id = None
        return service


class TestSlackService:
    """Tests for the SlackService class using factory patterns"""

    def test_init(self):
        """Test SlackService initialization"""
        settings = SlackSettingsFactory.create_basic_settings()
        client = SlackClientFactory.create_basic_client()
        slack_service = SlackService(settings, client)

        assert slack_service.settings == settings
        assert slack_service.client == client
        assert slack_service.bot_id == "B12345678"

    @pytest.mark.asyncio
    async def test_send_message_success(self):
        """Test successful message sending"""
        channel = "C12345"
        text = "Hello, World!"
        thread_ts = "1234567890.123456"
        expected_response = {"ts": "1234567890.654321"}

        slack_service = SlackServiceFactory.create_service_with_successful_client(
            expected_response
        )

        result = await slack_service.send_message(channel, text, thread_ts)

        assert result == expected_response
        slack_service.client.chat_postMessage.assert_called_once_with(
            channel=channel, text=text, thread_ts=thread_ts, blocks=None, mrkdwn=True
        )

    @pytest.mark.asyncio
    async def test_send_message_with_blocks(self):
        """Test message sending with blocks"""
        channel = "C12345"
        text = "Hello, World!"
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Hello"}}]
        expected_response = {"ts": "1234567890.654321"}

        slack_service = SlackServiceFactory.create_service_with_successful_client(
            expected_response
        )

        result = await slack_service.send_message(channel, text, blocks=blocks)

        assert result == expected_response
        slack_service.client.chat_postMessage.assert_called_once_with(
            channel=channel, text=text, thread_ts=None, blocks=blocks, mrkdwn=True
        )

    @pytest.mark.asyncio
    async def test_send_message_error(self):
        """Test message sending with API error"""
        channel = "C12345"
        text = "Hello, World!"
        api_error = SlackApiError(
            message="Error", response={"error": "channel_not_found"}
        )

        slack_service = SlackServiceFactory.create_service_with_error_client(api_error)

        result = await slack_service.send_message(channel, text)

        assert result is None

    @pytest.mark.asyncio
    async def test_send_thinking_indicator_success(self):
        """Test successful thinking indicator"""
        channel = "C12345"
        thread_ts = "1234567890.123456"
        expected_response = {"ts": "1234567890.654321"}

        slack_service = SlackServiceFactory.create_service_with_successful_client(
            expected_response
        )

        result = await slack_service.send_thinking_indicator(channel, thread_ts)

        assert result == "1234567890.654321"
        slack_service.client.chat_postMessage.assert_called_once_with(
            channel=channel, text="⏳ _Thinking..._", thread_ts=thread_ts, mrkdwn=True
        )

    @pytest.mark.asyncio
    async def test_send_thinking_indicator_error(self):
        """Test thinking indicator with error"""
        channel = "C12345"
        network_error = Exception("Network error")

        slack_service = SlackServiceFactory.create_service_with_error_client(
            network_error
        )

        result = await slack_service.send_thinking_indicator(channel)

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_thinking_indicator_success(self):
        """Test successful thinking indicator deletion"""
        channel = "C12345"
        ts = "1234567890.654321"
        slack_service = SlackServiceFactory.create_service_with_basic_client()

        # Mock the delete_message function
        with patch(
            "services.slack_service.delete_message", new_callable=AsyncMock
        ) as mock_delete:
            mock_delete.return_value = True

            result = await slack_service.delete_thinking_indicator(channel, ts)

            assert result is True
            mock_delete.assert_called_once_with(slack_service.client, channel, ts)

    @pytest.mark.asyncio
    async def test_delete_thinking_indicator_no_ts(self):
        """Test thinking indicator deletion with no timestamp"""
        channel = "C12345"
        slack_service = SlackServiceFactory.create_service_with_basic_client()

        result = await slack_service.delete_thinking_indicator(channel, None)

        assert result is False

    @pytest.mark.asyncio
    async def test_get_thread_history_success(self):
        """Test successful thread history retrieval"""
        channel = "C12345"
        thread_ts = "1234567890.123456"

        # Create thread history using builder pattern
        mock_messages = ThreadHistoryBuilder.basic_conversation().build()
        slack_service = SlackServiceFactory.create_service_with_thread_history(
            mock_messages
        )

        messages, success = await slack_service.get_thread_history(channel, thread_ts)

        assert success is True
        assert len(messages) == 3
        assert messages[0] == {"role": "user", "content": "Hello"}
        assert messages[1] == {"role": "assistant", "content": "Hi there!"}
        assert messages[2] == {"role": "user", "content": "How are you?"}

    @pytest.mark.asyncio
    async def test_get_thread_history_with_mentions(self):
        """Test thread history with mentions cleanup"""
        channel = "C12345"
        thread_ts = "1234567890.123456"

        # Create thread history with mentions using builder pattern
        mock_messages = ThreadHistoryBuilder.conversation_with_mentions().build()
        slack_service = SlackServiceFactory.create_service_with_thread_history(
            mock_messages
        )

        messages, success = await slack_service.get_thread_history(channel, thread_ts)

        assert success is True
        assert len(messages) == 2
        assert messages[0] == {"role": "user", "content": "hello"}
        assert messages[1] == {"role": "assistant", "content": "Hi there!"}

    @pytest.mark.asyncio
    async def test_get_thread_history_empty_messages(self):
        """Test thread history with empty messages"""
        channel = "C12345"
        thread_ts = "1234567890.123456"

        # Create thread history with empty messages using builder pattern
        mock_messages = ThreadHistoryBuilder.conversation_with_empty_messages().build()
        # Add whitespace message manually since builder doesn't have this specific case
        mock_messages[1]["text"] = "   "

        slack_service = SlackServiceFactory.create_service_with_thread_history(
            mock_messages
        )

        messages, success = await slack_service.get_thread_history(channel, thread_ts)

        assert success is True
        assert len(messages) == 1
        assert messages[0] == {"role": "user", "content": "Hello"}

    @pytest.mark.asyncio
    async def test_get_thread_history_error(self):
        """Test thread history with API error"""
        channel = "C12345"
        thread_ts = "1234567890.123456"

        slack_service = SlackServiceFactory.create_service_with_basic_client()
        slack_service.client.conversations_replies.side_effect = Exception("API error")

        messages, success = await slack_service.get_thread_history(channel, thread_ts)

        assert success is False
        assert messages == []

    @pytest.mark.asyncio
    async def test_get_thread_history_no_bot_id(self):
        """Test thread history when bot ID is not set"""
        channel = "C12345"
        thread_ts = "1234567890.123456"

        # Create service without bot ID and set up auth test
        slack_service = SlackServiceFactory.create_service_without_bot_id()
        mock_messages = [{"text": "Hello", "user": "U12345", "ts": "1234567890.123456"}]

        slack_service.client.conversations_replies = AsyncMock(
            return_value={"messages": mock_messages}
        )
        slack_service.client.auth_test = AsyncMock(
            return_value={"user_id": "B12345678"}
        )

        messages, success = await slack_service.get_thread_history(channel, thread_ts)

        assert success is True
        assert slack_service.bot_id == "B12345678"
        slack_service.client.auth_test.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_thread_history_none_thread_ts(self):
        """Test thread history with None thread_ts (new conversation)"""
        channel = "C12345"
        thread_ts = None
        slack_service = SlackServiceFactory.create_service_with_basic_client()

        messages, success = await slack_service.get_thread_history(channel, thread_ts)

        assert success is True
        assert messages == []

        # Ensure no API call was made since thread_ts is None
        assert (
            not hasattr(slack_service.client, "conversations_replies")
            or not slack_service.client.conversations_replies.called
        )

    @pytest.mark.asyncio
    async def test_get_thread_info_success(self):
        """Test successful thread info retrieval"""
        channel = "C12345"
        thread_ts = "1234567890.123456"

        # Create thread info messages (simplified, no text needed)
        mock_messages = [
            {"user": "U12345", "ts": "1234567890.123456"},
            {"user": "B12345678", "ts": "1234567890.234567"},
            {"user": "U67890", "ts": "1234567890.345678"},
        ]

        slack_service = SlackServiceFactory.create_service_with_basic_client()
        slack_service.client.conversations_replies = AsyncMock(
            return_value={"messages": mock_messages}
        )

        # Mock auth_test to return both user_id and bot_id
        slack_service.client.auth_test = AsyncMock(
            return_value={"user_id": "B12345678", "bot_id": "B08RGGA6QKS"}
        )

        thread_info = await slack_service.get_thread_info(channel, thread_ts)

        assert thread_info.exists is True
        assert thread_info.message_count == 3
        assert thread_info.bot_is_participant is True
        assert set(thread_info.participant_ids) == {"U12345", "B12345678", "U67890"}
        assert thread_info.error is None

    @pytest.mark.asyncio
    async def test_get_thread_info_bot_not_participant(self):
        """Test thread info when bot is not a participant"""
        channel = "C12345"
        thread_ts = "1234567890.123456"

        mock_messages = [
            {"user": "U12345", "ts": "1234567890.123456"},
            {"user": "U67890", "ts": "1234567890.234567"},
        ]

        slack_service = SlackServiceFactory.create_service_with_basic_client()
        slack_service.client.conversations_replies = AsyncMock(
            return_value={"messages": mock_messages}
        )

        # Mock auth_test to return both user_id and bot_id (neither matches participants)
        slack_service.client.auth_test = AsyncMock(
            return_value={"user_id": "U99999999", "bot_id": "B99999999"}
        )

        thread_info = await slack_service.get_thread_info(channel, thread_ts)

        assert thread_info.exists is True
        assert thread_info.message_count == 2
        assert thread_info.bot_is_participant is False
        assert set(thread_info.participant_ids) == {"U12345", "U67890"}

    @pytest.mark.asyncio
    async def test_get_thread_info_no_bot_id(self):
        """Test thread info when bot ID is not set"""
        channel = "C12345"
        thread_ts = "1234567890.123456"

        # Create service without bot ID
        slack_service = SlackServiceFactory.create_service_without_bot_id()
        mock_messages = [{"user": "U12345", "ts": "1234567890.123456"}]

        slack_service.client.conversations_replies = AsyncMock(
            return_value={"messages": mock_messages}
        )
        slack_service.client.auth_test = AsyncMock(
            return_value={"user_id": "B12345678", "bot_id": "B08RGGA6QKS"}
        )

        await slack_service.get_thread_info(channel, thread_ts)

        # With our new logic, bot_id gets set to the actual bot_id from auth_test (if available)
        assert slack_service.bot_id == "B08RGGA6QKS"
        assert slack_service.bot_user_id == "B12345678"
        slack_service.client.auth_test.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_thread_info_permission_error(self):
        """Test thread info with permission error"""
        channel = "C12345"
        thread_ts = "1234567890.123456"

        error_msg = "missing_scope: needed: 'channels:history'"
        permission_error = Exception(error_msg)
        slack_service = SlackServiceFactory.create_service_with_basic_client()
        slack_service.client.conversations_replies.side_effect = permission_error

        thread_info = await slack_service.get_thread_info(channel, thread_ts)

        assert thread_info.exists is False
        assert "Missing permission scope: channels:history" in thread_info.error

    @pytest.mark.asyncio
    async def test_get_thread_info_generic_error(self):
        """Test thread info with generic error"""
        channel = "C12345"
        thread_ts = "1234567890.123456"

        generic_error = Exception("Generic error")
        slack_service = SlackServiceFactory.create_service_with_basic_client()
        slack_service.client.conversations_replies.side_effect = generic_error

        thread_info = await slack_service.get_thread_info(channel, thread_ts)

        assert thread_info.exists is False
        assert thread_info.error == "Generic error"

    @pytest.mark.asyncio
    async def test_get_thread_info_no_messages(self):
        """Test thread info with no messages"""
        channel = "C12345"
        thread_ts = "1234567890.123456"

        slack_service = SlackServiceFactory.create_service_with_basic_client()
        slack_service.client.conversations_replies.return_value = {}

        thread_info = await slack_service.get_thread_info(channel, thread_ts)

        assert thread_info.exists is False
        assert thread_info.message_count == 0
        assert thread_info.bot_is_participant is False

    @pytest.mark.asyncio
    async def test_upload_file_success(self):
        """Test successful file upload"""
        from io import BytesIO

        channel = "C12345"
        file_content = BytesIO(b"PDF content here")
        filename = "test_report.pdf"
        title = "Test Report"

        expected_response = {
            "ok": True,
            "file": {
                "name": filename,
                "size": 100,
                "id": "F12345",
            },
        }

        slack_service = SlackServiceFactory.create_service_with_basic_client()
        slack_service.client.files_upload_v2 = AsyncMock(return_value=expected_response)

        result = await slack_service.upload_file(
            channel=channel,
            file_content=file_content,
            filename=filename,
            title=title,
        )

        assert result is not None
        assert result["ok"] is True
        assert result["file"]["name"] == filename
        slack_service.client.files_upload_v2.assert_called_once_with(
            channel=channel,
            file=file_content,
            filename=filename,
            title=title,
            initial_comment=None,
            thread_ts=None,
        )

    @pytest.mark.asyncio
    async def test_upload_file_with_thread(self):
        """Test file upload in a thread"""
        from io import BytesIO

        channel = "C12345"
        thread_ts = "1234567890.123456"
        file_content = BytesIO(b"PDF content")
        filename = "report.pdf"
        comment = "Here's the report!"

        expected_response = {
            "ok": True,
            "file": {"name": filename, "size": 50},
        }

        slack_service = SlackServiceFactory.create_service_with_basic_client()
        slack_service.client.files_upload_v2 = AsyncMock(return_value=expected_response)

        result = await slack_service.upload_file(
            channel=channel,
            file_content=file_content,
            filename=filename,
            initial_comment=comment,
            thread_ts=thread_ts,
        )

        assert result is not None
        assert result["ok"] is True
        slack_service.client.files_upload_v2.assert_called_once()
        call_kwargs = slack_service.client.files_upload_v2.call_args.kwargs
        assert call_kwargs["thread_ts"] == thread_ts
        assert call_kwargs["initial_comment"] == comment

    @pytest.mark.asyncio
    async def test_upload_file_with_bytes(self):
        """Test file upload with bytes instead of BytesIO"""
        channel = "C12345"
        file_content = b"Raw bytes content"
        filename = "data.bin"

        expected_response = {
            "ok": True,
            "file": {"name": filename, "size": len(file_content)},
        }

        slack_service = SlackServiceFactory.create_service_with_basic_client()
        slack_service.client.files_upload_v2 = AsyncMock(return_value=expected_response)

        result = await slack_service.upload_file(
            channel=channel,
            file_content=file_content,
            filename=filename,
        )

        assert result is not None
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_upload_file_api_error(self):
        """Test file upload with Slack API error"""
        from io import BytesIO

        channel = "C12345"
        file_content = BytesIO(b"content")
        filename = "test.pdf"

        api_error = SlackApiError(message="Error", response={"error": "invalid_auth"})

        slack_service = SlackServiceFactory.create_service_with_basic_client()
        slack_service.client.files_upload_v2 = AsyncMock(side_effect=api_error)

        result = await slack_service.upload_file(
            channel=channel,
            file_content=file_content,
            filename=filename,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_upload_file_failed_response(self):
        """Test file upload with failed response (ok=false)"""
        from io import BytesIO

        channel = "C12345"
        file_content = BytesIO(b"content")
        filename = "test.pdf"

        failed_response = {
            "ok": False,
            "error": "file_too_large",
        }

        slack_service = SlackServiceFactory.create_service_with_basic_client()
        slack_service.client.files_upload_v2 = AsyncMock(return_value=failed_response)

        result = await slack_service.upload_file(
            channel=channel,
            file_content=file_content,
            filename=filename,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_upload_file_generic_exception(self):
        """Test file upload with generic exception"""
        from io import BytesIO

        channel = "C12345"
        file_content = BytesIO(b"content")
        filename = "test.pdf"

        slack_service = SlackServiceFactory.create_service_with_basic_client()
        slack_service.client.files_upload_v2 = AsyncMock(
            side_effect=Exception("Network error")
        )

        result = await slack_service.upload_file(
            channel=channel,
            file_content=file_content,
            filename=filename,
        )

        assert result is None
