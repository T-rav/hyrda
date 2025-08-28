import sys
import os
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from handlers.message_handlers import handle_message, prepare_llm_messages, handle_agent_action, SYSTEM_MESSAGE
from services.llm_service import LLMService
from services.slack_service import SlackService
from config.settings import LLMSettings, SlackSettings


class TestMessageHandlers:
    """Tests for message handler functions"""

    @pytest.fixture
    def mock_llm_service(self):
        """Create mock LLM service"""
        return AsyncMock(spec=LLMService)

    @pytest.fixture
    def mock_slack_service(self):
        """Create mock Slack service"""
        return AsyncMock(spec=SlackService)

    @pytest.mark.asyncio
    async def test_handle_message_success(self, mock_slack_service, mock_llm_service):
        """Test successful message handling"""
        text = "Hello, how are you?"
        user_id = "U12345"
        channel = "C12345"
        thread_ts = "1234567890.123456"
        
        # Mock services with AsyncMock
        mock_slack_service.send_thinking_indicator = AsyncMock(return_value="thinking_ts")
        mock_slack_service.get_thread_history = AsyncMock(return_value=([], True))
        mock_slack_service.delete_thinking_indicator = AsyncMock()
        mock_slack_service.send_message = AsyncMock()
        mock_llm_service.get_response = AsyncMock(return_value="I'm doing well, thank you!")
        
        # Mock MessageFormatter
        with patch('handlers.message_handlers.MessageFormatter') as mock_formatter:
            mock_formatter.format_message = AsyncMock(return_value="I'm doing well, thank you!")
            
            await handle_message(text, user_id, mock_slack_service, mock_llm_service, channel, thread_ts)
        
        # Verify calls
        mock_slack_service.send_thinking_indicator.assert_called_once_with(channel, thread_ts)
        mock_slack_service.get_thread_history.assert_called_once_with(channel, thread_ts)
        mock_llm_service.get_response.assert_called_once()
        mock_slack_service.delete_thinking_indicator.assert_called_once_with(channel, "thinking_ts")
        mock_slack_service.send_message.assert_called_once_with(
            channel=channel,
            text="I'm doing well, thank you!",
            thread_ts=thread_ts
        )

    @pytest.mark.asyncio
    async def test_handle_message_no_thread(self, mock_slack_service, mock_llm_service):
        """Test message handling without thread"""
        text = "Hello"
        user_id = "U12345"
        channel = "C12345"
        
        mock_slack_service.send_thinking_indicator = AsyncMock(return_value="thinking_ts")
        mock_slack_service.get_thread_history = AsyncMock(return_value=([], True))
        mock_slack_service.delete_thinking_indicator = AsyncMock()
        mock_slack_service.send_message = AsyncMock()
        mock_llm_service.get_response = AsyncMock(return_value="Hello!")
        
        with patch('handlers.message_handlers.MessageFormatter') as mock_formatter:
            mock_formatter.format_message = AsyncMock(return_value="Hello!")
            
            await handle_message(text, user_id, mock_slack_service, mock_llm_service, channel)
        
        # Thread history should not be called when no thread_ts
        mock_slack_service.get_thread_history.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_message_with_thread_history(self, mock_slack_service, mock_llm_service):
        """Test message handling with thread history"""
        text = "What did I ask before?"
        user_id = "U12345"
        channel = "C12345"
        thread_ts = "1234567890.123456"
        
        thread_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        
        mock_slack_service.send_thinking_indicator = AsyncMock(return_value="thinking_ts")
        mock_slack_service.get_thread_history = AsyncMock(return_value=(thread_history, True))
        mock_slack_service.delete_thinking_indicator = AsyncMock()
        mock_slack_service.send_message = AsyncMock()
        mock_llm_service.get_response = AsyncMock(return_value="You asked 'Hello'")
        
        with patch('handlers.message_handlers.MessageFormatter') as mock_formatter:
            mock_formatter.format_message = AsyncMock(return_value="You asked 'Hello'")
            
            await handle_message(text, user_id, mock_slack_service, mock_llm_service, channel, thread_ts)
        
        # Verify LLM was called with thread history
        call_args = mock_llm_service.get_response.call_args
        messages = call_args[1]['messages']
        
        # Should have system message + thread history + current message
        assert len(messages) >= 4
        assert messages[0]['role'] == 'system'
        assert messages[1] == {"role": "user", "content": "Hello"}
        assert messages[2] == {"role": "assistant", "content": "Hi there!"}

    @pytest.mark.asyncio
    async def test_handle_message_llm_error(self, mock_slack_service, mock_llm_service):
        """Test message handling when LLM returns None"""
        text = "Hello"
        user_id = "U12345"
        channel = "C12345"
        thread_ts = "1234567890.123456"
        
        mock_slack_service.send_thinking_indicator = AsyncMock(return_value="thinking_ts")
        mock_slack_service.get_thread_history = AsyncMock(return_value=([], True))
        mock_slack_service.delete_thinking_indicator = AsyncMock()
        mock_slack_service.send_message = AsyncMock()
        mock_llm_service.get_response = AsyncMock(return_value=None)
        
        await handle_message(text, user_id, mock_slack_service, mock_llm_service, channel, thread_ts)
        
        # Should send error message
        mock_slack_service.send_message.assert_called_once_with(
            channel=channel,
            text="I'm sorry, I encountered an error while generating a response.",
            thread_ts=thread_ts
        )

    @pytest.mark.asyncio
    async def test_handle_message_exception(self, mock_slack_service, mock_llm_service):
        """Test message handling with exception"""
        text = "Hello"
        user_id = "U12345"
        channel = "C12345"
        thread_ts = "1234567890.123456"
        
        mock_slack_service.send_thinking_indicator = AsyncMock(return_value="thinking_ts")
        mock_slack_service.get_thread_history = AsyncMock(side_effect=Exception("API error"))
        mock_slack_service.delete_thinking_indicator = AsyncMock()
        mock_slack_service.client = MagicMock()  # Add client attribute
        
        with patch('handlers.message_handlers.handle_error') as mock_handle_error:
            mock_handle_error = AsyncMock()
            await handle_message(text, user_id, mock_slack_service, mock_llm_service, channel, thread_ts)
            
            # Should delete thinking indicator
            mock_slack_service.delete_thinking_indicator.assert_called_once_with(channel, "thinking_ts")

    @pytest.mark.asyncio
    async def test_prepare_llm_messages_no_thread(self):
        """Test preparing LLM messages without thread history"""
        text = "Hello"
        thread_messages = []
        
        messages = await prepare_llm_messages(text, thread_messages)
        
        assert len(messages) == 2
        assert messages[0] == {"role": "system", "content": SYSTEM_MESSAGE}
        assert messages[1] == {"role": "user", "content": text}

    @pytest.mark.asyncio
    async def test_prepare_llm_messages_with_thread(self):
        """Test preparing LLM messages with thread history"""
        text = "What did I say?"
        thread_messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        
        messages = await prepare_llm_messages(text, thread_messages)
        
        assert len(messages) == 4
        assert messages[0] == {"role": "system", "content": SYSTEM_MESSAGE}
        assert messages[1] == {"role": "user", "content": "Hello"}
        assert messages[2] == {"role": "assistant", "content": "Hi there!"}
        assert messages[3] == {"role": "user", "content": text}

    @pytest.mark.asyncio
    async def test_prepare_llm_messages_duplicate_last_message(self):
        """Test preparing LLM messages when current text is duplicate of last message"""
        text = "Hello again"
        thread_messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "Hello again"}
        ]
        
        messages = await prepare_llm_messages(text, thread_messages)
        
        # Should not add duplicate message
        assert len(messages) == 4
        assert messages[0] == {"role": "system", "content": SYSTEM_MESSAGE}
        assert messages[-1] == {"role": "user", "content": "Hello again"}

    @pytest.mark.asyncio
    async def test_prepare_llm_messages_empty_text(self):
        """Test preparing LLM messages with empty text"""
        text = ""
        thread_messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        
        messages = await prepare_llm_messages(text, thread_messages)
        
        # Should only have system message and thread history
        assert len(messages) == 3
        assert messages[0] == {"role": "system", "content": SYSTEM_MESSAGE}
        assert messages[1] == {"role": "user", "content": "Hello"}
        assert messages[2] == {"role": "assistant", "content": "Hi there!"}

    @pytest.mark.asyncio
    async def test_handle_agent_action_success(self, mock_slack_service):
        """Test successful agent action handling"""
        action_id = "test_action"
        user_id = "U12345"
        channel = "C12345"
        thread_ts = "1234567890.123456"
        
        mock_slack_service.send_thinking_indicator = AsyncMock(return_value="thinking_ts")
        mock_slack_service.delete_thinking_indicator = AsyncMock()
        mock_slack_service.send_message = AsyncMock()
        
        # Mock agent process functions
        with patch('handlers.message_handlers.run_agent_process') as mock_run_agent, \
             patch('handlers.message_handlers.get_agent_blocks') as mock_get_blocks:
            
            mock_run_agent.return_value = {
                "success": True,
                "name": "Test Agent",
                "result": "Process completed"
            }
            mock_get_blocks.return_value = [{"type": "section", "text": {"type": "mrkdwn", "text": "Success!"}}]
            
            await handle_agent_action(action_id, user_id, mock_slack_service, channel, thread_ts)
        
        # Verify calls
        mock_slack_service.send_thinking_indicator.assert_called_once_with(channel, thread_ts)
        mock_run_agent.assert_called_once_with(action_id)
        mock_get_blocks.assert_called_once()
        mock_slack_service.delete_thinking_indicator.assert_called_once_with(channel, "thinking_ts")
        
        # Verify message sent
        call_args = mock_slack_service.send_message.call_args
        assert call_args[1]['channel'] == channel
        assert call_args[1]['thread_ts'] == thread_ts
        assert "Test Agent started successfully" in call_args[1]['text']

    @pytest.mark.asyncio
    async def test_handle_agent_action_failure(self, mock_slack_service):
        """Test agent action handling with failure"""
        action_id = "test_action"
        user_id = "U12345"
        channel = "C12345"
        thread_ts = "1234567890.123456"
        
        mock_slack_service.send_thinking_indicator = AsyncMock(return_value="thinking_ts")
        mock_slack_service.delete_thinking_indicator = AsyncMock()
        mock_slack_service.send_message = AsyncMock()
        
        with patch('handlers.message_handlers.run_agent_process') as mock_run_agent, \
             patch('handlers.message_handlers.get_agent_blocks') as mock_get_blocks:
            
            mock_run_agent.return_value = {
                "success": False,
                "error": "Process failed",
                "name": "Test Agent"
            }
            mock_get_blocks.return_value = [{"type": "section", "text": {"type": "mrkdwn", "text": "Failed!"}}]
            
            await handle_agent_action(action_id, user_id, mock_slack_service, channel, thread_ts)
        
        # Verify failure message
        call_args = mock_slack_service.send_message.call_args
        assert "Failed to start agent process: Process failed" in call_args[1]['text']

    @pytest.mark.asyncio
    async def test_handle_agent_action_unknown_error(self, mock_slack_service):
        """Test agent action handling with unknown error"""
        action_id = "test_action"
        user_id = "U12345"
        channel = "C12345"
        thread_ts = "1234567890.123456"
        
        mock_slack_service.send_thinking_indicator = AsyncMock(return_value="thinking_ts")
        mock_slack_service.delete_thinking_indicator = AsyncMock()
        mock_slack_service.send_message = AsyncMock()
        
        with patch('handlers.message_handlers.run_agent_process') as mock_run_agent, \
             patch('handlers.message_handlers.get_agent_blocks') as mock_get_blocks:
            
            mock_run_agent.return_value = {
                "success": False,
                "name": "Test Agent"
            }
            mock_get_blocks.return_value = []
            
            await handle_agent_action(action_id, user_id, mock_slack_service, channel, thread_ts)
        
        # Verify unknown error message
        call_args = mock_slack_service.send_message.call_args
        assert "Failed to start agent process: Unknown error" in call_args[1]['text']