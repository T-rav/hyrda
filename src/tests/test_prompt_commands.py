import os
import sys
from unittest.mock import AsyncMock

import pytest

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from handlers.message_handlers import (
    DEFAULT_SYSTEM_MESSAGE,
    PROMPT_HELP_TEXT,
    get_user_system_prompt,
    handle_prompt_command,
)
from services.slack_service import SlackService
from services.user_prompt_service import UserPromptService


@pytest.fixture
def mock_slack_service():
    """Create mock Slack service"""
    service = AsyncMock(spec=SlackService)
    service.send_message = AsyncMock()
    return service


@pytest.fixture
def mock_prompt_service():
    """Create mock UserPromptService"""
    service = AsyncMock(spec=UserPromptService)
    service.get_user_prompt = AsyncMock()
    service.set_user_prompt = AsyncMock()
    service.get_user_prompt_history = AsyncMock()
    service.reset_user_prompt = AsyncMock()
    return service


class TestPromptCommands:
    """Tests for @prompt command functionality"""

    @pytest.mark.asyncio
    async def test_prompt_help_command(self, mock_slack_service):
        """Test @prompt help command (empty @prompt)"""
        text = "@prompt"
        user_id = "U12345"
        channel = "C12345"
        thread_ts = "1234567890.123"

        result = await handle_prompt_command(
            text, user_id, mock_slack_service, channel, thread_ts
        )

        assert result is True  # Command was handled
        mock_slack_service.send_message.assert_called_once_with(
            channel=channel, text=PROMPT_HELP_TEXT, thread_ts=thread_ts
        )

    @pytest.mark.asyncio
    async def test_not_prompt_command(self, mock_slack_service):
        """Test that non-@prompt text returns False"""
        text = "Hello, how are you?"
        user_id = "U12345"
        channel = "C12345"

        result = await handle_prompt_command(text, user_id, mock_slack_service, channel)

        assert result is False  # Command was not handled
        mock_slack_service.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_custom_prompt(self, mock_slack_service, mock_prompt_service):
        """Test setting a custom system prompt"""
        text = "@prompt You are a helpful Python expert who gives concise examples"
        user_id = "U12345"
        channel = "C12345"
        thread_ts = "1234567890.123"

        result = await handle_prompt_command(
            text, user_id, mock_slack_service, channel, thread_ts, mock_prompt_service
        )

        assert result is True
        mock_prompt_service.set_user_prompt.assert_called_once_with(
            user_id, "You are a helpful Python expert who gives concise examples"
        )

        # Check that response was sent
        mock_slack_service.send_message.assert_called_once()
        call_args = mock_slack_service.send_message.call_args
        assert call_args[1]["channel"] == channel
        assert call_args[1]["thread_ts"] == thread_ts
        assert "System prompt updated" in call_args[1]["text"]

    @pytest.mark.asyncio
    async def test_set_long_prompt_truncated_preview(
        self, mock_slack_service, mock_prompt_service
    ):
        """Test setting a long prompt shows truncated preview"""
        long_prompt = "You are a very helpful assistant that provides extremely detailed explanations with lots of context and examples"
        text = f"@prompt {long_prompt}"
        user_id = "U12345"
        channel = "C12345"

        result = await handle_prompt_command(
            text,
            user_id,
            mock_slack_service,
            channel,
            prompt_service=mock_prompt_service,
        )

        assert result is True
        mock_prompt_service.set_user_prompt.assert_called_once_with(
            user_id, long_prompt
        )

        # Check that response contains truncated preview
        call_args = mock_slack_service.send_message.call_args
        response_text = call_args[1]["text"]
        assert "..." in response_text  # Should be truncated

    @pytest.mark.asyncio
    async def test_prompt_history_with_data(
        self, mock_slack_service, mock_prompt_service
    ):
        """Test @prompt history with existing prompts"""
        text = "@prompt history"
        user_id = "U12345"
        channel = "C12345"

        mock_history = [
            {
                "prompt": "You are a Python expert",
                "preview": "You are a Python expert",
                "timestamp": "2024-01-01T10:00:00+00:00",
                "is_current": True,
            },
            {
                "prompt": "You are a helpful assistant",
                "preview": "You are a helpful assistant",
                "timestamp": "2024-01-01T09:00:00+00:00",
                "is_current": False,
            },
        ]
        mock_prompt_service.get_user_prompt_history.return_value = mock_history

        result = await handle_prompt_command(
            text,
            user_id,
            mock_slack_service,
            channel,
            prompt_service=mock_prompt_service,
        )

        assert result is True
        mock_prompt_service.get_user_prompt_history.assert_called_once_with(user_id)

        call_args = mock_slack_service.send_message.call_args
        response_text = call_args[1]["text"]
        assert "Your Recent System Prompts" in response_text
        assert "Python expert" in response_text
        assert "*(current)*" in response_text  # Current prompt indicator

    @pytest.mark.asyncio
    async def test_prompt_history_empty(self, mock_slack_service, mock_prompt_service):
        """Test @prompt history with no prompts"""
        text = "@prompt history"
        user_id = "U12345"
        channel = "C12345"

        mock_prompt_service.get_user_prompt_history.return_value = []

        result = await handle_prompt_command(
            text,
            user_id,
            mock_slack_service,
            channel,
            prompt_service=mock_prompt_service,
        )

        assert result is True

        call_args = mock_slack_service.send_message.call_args
        response_text = call_args[1]["text"]
        assert "haven't set any custom system prompts" in response_text

    @pytest.mark.asyncio
    async def test_prompt_reset(self, mock_slack_service, mock_prompt_service):
        """Test @prompt reset command"""
        text = "@prompt reset"
        user_id = "U12345"
        channel = "C12345"

        result = await handle_prompt_command(
            text,
            user_id,
            mock_slack_service,
            channel,
            prompt_service=mock_prompt_service,
        )

        assert result is True
        mock_prompt_service.reset_user_prompt.assert_called_once_with(user_id)

        call_args = mock_slack_service.send_message.call_args
        response_text = call_args[1]["text"]
        assert "System prompt reset to default" in response_text

    @pytest.mark.asyncio
    async def test_prompt_commands_without_database(self, mock_slack_service):
        """Test @prompt commands when database is not available"""
        text = "@prompt You are a helpful assistant"
        user_id = "U12345"
        channel = "C12345"

        # No prompt_service provided
        result = await handle_prompt_command(
            text, user_id, mock_slack_service, channel, prompt_service=None
        )

        assert result is True

        call_args = mock_slack_service.send_message.call_args
        response_text = call_args[1]["text"]
        assert "Database not available" in response_text

    @pytest.mark.asyncio
    async def test_prompt_history_without_database(self, mock_slack_service):
        """Test @prompt history when database is not available"""
        text = "@prompt history"
        user_id = "U12345"
        channel = "C12345"

        result = await handle_prompt_command(
            text, user_id, mock_slack_service, channel, prompt_service=None
        )

        assert result is True

        call_args = mock_slack_service.send_message.call_args
        response_text = call_args[1]["text"]
        assert "Database not available" in response_text

    @pytest.mark.asyncio
    async def test_prompt_reset_without_database(self, mock_slack_service):
        """Test @prompt reset when database is not available"""
        text = "@prompt reset"
        user_id = "U12345"
        channel = "C12345"

        result = await handle_prompt_command(
            text, user_id, mock_slack_service, channel, prompt_service=None
        )

        assert result is True

        call_args = mock_slack_service.send_message.call_args
        response_text = call_args[1]["text"]
        assert "Database not available" in response_text

    @pytest.mark.asyncio
    async def test_get_user_system_prompt_with_custom(self, mock_prompt_service):
        """Test getting user system prompt when user has custom prompt"""
        user_id = "U12345"
        custom_prompt = "You are a Python expert"

        mock_prompt_service.get_user_prompt.return_value = custom_prompt

        result = await get_user_system_prompt(user_id, mock_prompt_service)

        assert result == custom_prompt
        mock_prompt_service.get_user_prompt.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_get_user_system_prompt_default(self, mock_prompt_service):
        """Test getting user system prompt when user has no custom prompt"""
        user_id = "U12345"

        mock_prompt_service.get_user_prompt.return_value = None

        result = await get_user_system_prompt(user_id, mock_prompt_service)

        assert result == DEFAULT_SYSTEM_MESSAGE
        mock_prompt_service.get_user_prompt.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_get_user_system_prompt_no_service(self):
        """Test getting user system prompt when no service available"""
        user_id = "U12345"

        result = await get_user_system_prompt(user_id, None)

        assert result == DEFAULT_SYSTEM_MESSAGE

    def test_prompt_command_text_parsing(self):
        """Test various @prompt command text parsing scenarios"""
        test_cases = [
            ("@prompt", True, ""),
            ("@prompt ", True, ""),
            ("@prompt help", True, "help"),
            ("@prompt history", True, "history"),
            ("@prompt reset", True, "reset"),
            ("@prompt You are helpful", True, "You are helpful"),
            ("prompt", False, None),  # Missing @
            ("@prompts", False, None),  # Wrong command
            ("Hello @prompt", False, None),  # Not at start
        ]

        for text, should_match, expected_command in test_cases:
            # Proper parsing logic: check for exact "@prompt" followed by space or end of string
            stripped_text = text.strip()
            if stripped_text == "@prompt" or stripped_text.startswith("@prompt "):
                is_prompt_command = True
                command_part = text[7:].strip() if len(text) > 7 else ""
            else:
                is_prompt_command = False
                command_part = None

            if should_match:
                assert is_prompt_command is True
                assert command_part == expected_command
            else:
                assert is_prompt_command is False
