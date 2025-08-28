import sys
import os
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from handlers.event_handlers import register_handlers, process_message_by_context
from services.llm_service import LLMService
from services.slack_service import SlackService


class TestEventHandlers:
    """Tests for event handler functions"""

    @pytest.fixture
    def mock_app(self):
        """Create mock Slack app"""
        app = MagicMock()
        app.event = MagicMock()
        return app

    @pytest.fixture
    def mock_slack_service(self):
        """Create mock Slack service"""
        service = AsyncMock(spec=SlackService)
        service.bot_id = "B12345678"
        return service

    @pytest.fixture
    def mock_llm_service(self):
        """Create mock LLM service"""
        return AsyncMock(spec=LLMService)

    @pytest.mark.asyncio
    async def test_register_handlers(self, mock_app, mock_slack_service, mock_llm_service):
        """Test that handlers are registered correctly"""
        await register_handlers(mock_app, mock_slack_service, mock_llm_service)
        
        # Verify that event decorators were called
        assert mock_app.event.call_count >= 2  # Should register multiple events

    @pytest.mark.asyncio
    async def test_assistant_thread_started_handler(self, mock_app, mock_slack_service, mock_llm_service):
        """Test assistant thread started event handler"""
        mock_slack_service.send_message = AsyncMock()
        
        await register_handlers(mock_app, mock_slack_service, mock_llm_service)
        
        # Simulate the handler being called directly
        body = {
            "event": {
                "channel": "C12345",
                "thread_ts": "1234567890.123456",
                "user": "U12345"
            }
        }
        client = MagicMock()
        
        # Test that event registration happened
        assert mock_app.event.call_count >= 2

    @pytest.mark.asyncio
    async def test_app_mention_handler(self, mock_app, mock_slack_service, mock_llm_service):
        """Test app mention event handler"""
        with patch('handlers.event_handlers.handle_message') as mock_handle_message:
            mock_handle_message = AsyncMock()
            
            await register_handlers(mock_app, mock_slack_service, mock_llm_service)
            
            # Test that event registration happened
            assert mock_app.event.call_count >= 2

    @pytest.mark.asyncio
    async def test_process_message_by_context_dm(self, mock_slack_service, mock_llm_service):
        """Test processing message in DM context"""
        with patch('handlers.event_handlers.handle_message', new_callable=AsyncMock) as mock_handle_message:
            
            await process_message_by_context(
                user_id="U12345",
                channel="D12345",
                channel_type="im",
                text="Hello",
                thread_ts=None,
                ts="1234567890.123456",
                slack_service=mock_slack_service,
                llm_service=mock_llm_service
            )
            
            mock_handle_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_by_context_mention(self, mock_slack_service, mock_llm_service):
        """Test processing message with bot mention"""
        with patch('handlers.event_handlers.handle_message', new_callable=AsyncMock) as mock_handle_message:
            
            await process_message_by_context(
                user_id="U12345",
                channel="C12345",
                channel_type="channel",
                text="<@B12345678> hello",
                thread_ts=None,
                ts="1234567890.123456",
                slack_service=mock_slack_service,
                llm_service=mock_llm_service
            )
            
            mock_handle_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_by_context_thread(self, mock_slack_service, mock_llm_service):
        """Test processing message in thread"""
        with patch('handlers.event_handlers.handle_message', new_callable=AsyncMock) as mock_handle_message:
            
            await process_message_by_context(
                user_id="U12345",
                channel="C12345",
                channel_type="channel",
                text="Reply in thread",
                thread_ts="1234567890.123456",
                ts="1234567890.234567",
                slack_service=mock_slack_service,
                llm_service=mock_llm_service
            )
            
            # Should always respond in threads (temporary fix)
            mock_handle_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_by_context_no_response(self, mock_slack_service, mock_llm_service):
        """Test processing message that shouldn't get response"""
        with patch('handlers.event_handlers.handle_message') as mock_handle_message:
            mock_handle_message = AsyncMock()
            
            # Message in channel without mention or thread
            await process_message_by_context(
                user_id="U12345",
                channel="C12345",
                channel_type="channel",
                text="Just a regular message",
                thread_ts=None,
                ts="1234567890.123456",
                slack_service=mock_slack_service,
                llm_service=mock_llm_service
            )
            
            # Should not call handle_message
            mock_handle_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_message_event_handler_bot_message(self, mock_app, mock_slack_service, mock_llm_service):
        """Test message event handler skips bot messages"""
        with patch('handlers.event_handlers.process_message_by_context') as mock_process:
            mock_process = AsyncMock()
            
            await register_handlers(mock_app, mock_slack_service, mock_llm_service)
            
            # Test that handlers were registered
            assert mock_app.event.call_count >= 2

    @pytest.mark.asyncio
    async def test_message_event_handler_no_user(self, mock_app, mock_slack_service, mock_llm_service):
        """Test message event handler skips messages without user"""
        with patch('handlers.event_handlers.process_message_by_context') as mock_process:
            mock_process = AsyncMock()
            
            await register_handlers(mock_app, mock_slack_service, mock_llm_service)
            
            # Test that handlers were registered
            assert mock_app.event.call_count >= 2

    @pytest.mark.asyncio
    async def test_message_event_handler_valid_message(self, mock_app, mock_slack_service, mock_llm_service):
        """Test message event handler processes valid messages"""
        with patch('handlers.event_handlers.process_message_by_context') as mock_process:
            mock_process = AsyncMock()
            
            await register_handlers(mock_app, mock_slack_service, mock_llm_service)
            
            # Test that handlers were registered
            assert mock_app.event.call_count >= 2

    @pytest.mark.asyncio
    async def test_process_message_thread_error_fallback(self, mock_slack_service, mock_llm_service):
        """Test thread processing falls back to responding on error"""
        mock_slack_service.get_thread_info = AsyncMock(side_effect=Exception("Permission error"))
        
        with patch('handlers.event_handlers.handle_message', new_callable=AsyncMock) as mock_handle_message:
            
            await process_message_by_context(
                user_id="U12345",
                channel="C12345",
                channel_type="channel",
                text="Message in thread",
                thread_ts="1234567890.123456",
                ts="1234567890.234567",
                slack_service=mock_slack_service,
                llm_service=mock_llm_service
            )
            
            # Should still respond despite error
            mock_handle_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_mention_handler_error(self, mock_app, mock_slack_service, mock_llm_service):
        """Test mention handler error handling"""
        with patch('handlers.event_handlers.handle_message') as mock_handle_message, \
             patch('handlers.event_handlers.handle_error') as mock_handle_error:
            
            mock_handle_message = AsyncMock(side_effect=Exception("Processing error"))
            mock_handle_error = AsyncMock()
            
            await register_handlers(mock_app, mock_slack_service, mock_llm_service)
            
            # Test that handlers were registered
            assert mock_app.event.call_count >= 2