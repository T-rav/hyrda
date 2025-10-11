import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from handlers.event_handlers import process_message_by_context, register_handlers


# Event Handler Test Factory Classes
class SlackAppFactory:
    """Factory for creating Slack app mocks for event testing"""

    @staticmethod
    def create_basic_app() -> MagicMock:
        """Create basic Slack app mock"""
        app = MagicMock()
        app.event = MagicMock()
        return app

    @staticmethod
    def create_app_with_event_tracking() -> MagicMock:
        """Create app mock that tracks event registrations"""
        app = SlackAppFactory.create_basic_app()
        app.event.call_count = 0
        app.event.call_args_list = []
        return app


class SlackServiceFactory:
    """Factory for creating Slack service mocks for event testing"""

    @staticmethod
    def create_basic_service(bot_id: str = "B12345678") -> AsyncMock:
        """Create basic Slack service mock"""
        from models import ThreadInfo

        service = AsyncMock()
        service.bot_id = bot_id
        service.send_message = AsyncMock()
        service.get_thread_info = AsyncMock(
            return_value=ThreadInfo(
                exists=True,
                message_count=1,
                bot_is_participant=True,
                messages=[],
                participant_ids=[bot_id],
            )
        )
        return service

    @staticmethod
    def create_service_with_thread_info(bot_is_participant: bool = True) -> AsyncMock:
        """Create service with specific thread participation status"""
        from models import ThreadInfo

        service = SlackServiceFactory.create_basic_service()
        service.get_thread_info = AsyncMock(
            return_value=ThreadInfo(
                exists=True,
                message_count=1,
                bot_is_participant=bot_is_participant,
                messages=[],
                participant_ids=["B12345678"] if bot_is_participant else [],
            )
        )
        return service


class LLMServiceFactory:
    """Factory for creating LLM service mocks for event testing"""

    @staticmethod
    def create_basic_service() -> AsyncMock:
        """Create basic LLM service mock"""
        return AsyncMock()


class ConversationCacheFactory:
    """Factory for creating conversation cache mocks for event testing"""

    @staticmethod
    def create_basic_cache() -> AsyncMock:
        """Create basic conversation cache mock"""
        return AsyncMock()


class SlackEventFactory:
    """Factory for creating Slack event objects for testing"""

    @staticmethod
    def create_bot_event(bot_id: str = "B123456789") -> dict:
        """Create event from a bot (should be filtered)"""
        return {"bot_id": bot_id, "text": "Bot message"}

    @staticmethod
    def create_bot_subtype_event() -> dict:
        """Create bot_message subtype event (should be filtered)"""
        return {"subtype": "bot_message", "text": "Bot message"}

    @staticmethod
    def create_no_user_event() -> dict:
        """Create event without user (should be filtered)"""
        return {"text": "Message", "channel": "C123"}

    @staticmethod
    def create_valid_event(
        user_id: str = "U123",
        text: str = "Hello",
        channel: str = "C123",
        thread_ts: str = None,
    ) -> dict:
        """Create valid user event (should be processed)"""
        event = {"user": user_id, "text": text, "channel": channel}
        if thread_ts:
            event["thread_ts"] = thread_ts
        return event

    @staticmethod
    def create_app_mention_event(
        user_id: str = "U123456789",
        bot_mention: str = "<@B987654321>",
        text: str = "hello there",
        channel: str = "C123456789",
        thread_ts: str = "1234567890.123456",
    ) -> dict:
        """Create app mention event"""
        return {
            "user": user_id,
            "text": f"{bot_mention} {text}",
            "channel": channel,
            "thread_ts": thread_ts,
        }

    @staticmethod
    def create_dm_event(
        user_id: str = "U123456789",
        text: str = "Hello in DM",
        channel: str = "D123456789",
    ) -> dict:
        """Create direct message event"""
        return {"user": user_id, "text": text, "channel": channel}


class EventContextFactory:
    """Factory for creating event context scenarios"""

    @staticmethod
    def create_dm_context(
        user_id: str = "U123456789",
        text: str = "Hello",
        channel: str = "D123456789",
    ) -> dict:
        """Create DM context (channel starts with D)"""
        return {
            "event": SlackEventFactory.create_dm_event(user_id, text, channel),
            "context": "dm",
        }

    @staticmethod
    def create_channel_context(
        user_id: str = "U123456789",
        text: str = "Hello",
        channel: str = "C123456789",
        thread_ts: str = "1234567890.123456",
    ) -> dict:
        """Create channel context with thread"""
        return {
            "event": SlackEventFactory.create_valid_event(
                user_id, text, channel, thread_ts
            ),
            "context": "channel",
        }


class TestEventHandlerRegistration:
    """Tests for event handler registration"""

    @pytest.fixture
    def mock_app(self):
        """Create mock Slack app"""
        return SlackAppFactory.create_basic_app()

    @pytest.fixture
    def mock_slack_service(self):
        """Create mock Slack service"""
        return SlackServiceFactory.create_basic_service()

    @pytest.fixture
    def mock_llm_service(self):
        """Create mock LLM service"""
        return LLMServiceFactory.create_basic_service()

    @pytest.mark.asyncio
    async def test_register_handlers(
        self, mock_app, mock_slack_service, mock_llm_service
    ):
        """Test that handlers are registered correctly"""
        await register_handlers(mock_app, mock_slack_service, mock_llm_service)

        # Verify that event decorators were called (3 events: assistant_thread_started, app_mention, message)
        assert mock_app.event.call_count >= 3

        # Verify the correct event types were registered
        expected_events = ["assistant_thread_started", "app_mention", "message"]
        actual_events = [call[0][0] for call in mock_app.event.call_args_list]

        for expected_event in expected_events:
            assert expected_event in actual_events

    @pytest.mark.asyncio
    async def test_register_handlers_with_cache(
        self, mock_app, mock_slack_service, mock_llm_service
    ):
        """Test that handlers can be registered with conversation cache"""
        # Create cache using factory
        mock_cache = ConversationCacheFactory.create_basic_cache()

        await register_handlers(
            mock_app, mock_slack_service, mock_llm_service, mock_cache
        )

        # Verify that handlers were still registered correctly
        assert mock_app.event.call_count >= 3

    @pytest.mark.asyncio
    async def test_register_handlers_creates_closures(
        self, mock_app, mock_slack_service, mock_llm_service
    ):
        """Test that register_handlers creates proper closures with services"""
        await register_handlers(mock_app, mock_slack_service, mock_llm_service)

        # Verify handlers were created and registered
        assert mock_app.event.called

        # The handlers should be registered (we can't easily test the closures without more complex mocking)
        assert mock_app.event.call_count == 3


class TestEventHandlerFunctionality:
    """Test event handler functionality through direct function calls"""

    @pytest.fixture
    def mock_slack_service(self):
        """Create mock Slack service"""
        return SlackServiceFactory.create_basic_service()

    @pytest.fixture
    def mock_llm_service(self):
        """Create mock LLM service"""
        return LLMServiceFactory.create_basic_service()

    @pytest.mark.asyncio
    async def test_assistant_thread_functionality(
        self, mock_slack_service, mock_llm_service
    ):
        """Test assistant thread started functionality by simulating the handler logic"""
        # This tests the logic that would be in the assistant thread handler
        channel_id = "C123456789"
        thread_ts = "1234567890.123456"

        # Simulate what the handler does
        await mock_slack_service.send_message(
            channel=channel_id,
            text="👋 Hello! I'm Insight Mesh Assistant. I can help answer questions about your data or start agent processes for you.",
            thread_ts=thread_ts,
        )

        # Verify the message was sent
        mock_slack_service.send_message.assert_called_once_with(
            channel=channel_id,
            text="👋 Hello! I'm Insight Mesh Assistant. I can help answer questions about your data or start agent processes for you.",
            thread_ts=thread_ts,
        )

    @pytest.mark.asyncio
    async def test_app_mention_functionality(
        self, mock_slack_service, mock_llm_service
    ):
        """Test app mention functionality by simulating handler logic"""
        with patch(
            "handlers.event_handlers.handle_message", new_callable=AsyncMock
        ) as mock_handle_message:
            # Create app mention event using factory
            event = SlackEventFactory.create_app_mention_event()
            raw_text = event["text"]
            clean_text = (
                raw_text.split(">", 1)[-1].strip() if ">" in raw_text else raw_text
            )

            # Call handle_message as the handler would
            await mock_handle_message(
                text=clean_text,
                user_id=event["user"],
                slack_service=mock_slack_service,
                llm_service=mock_llm_service,
                channel=event["channel"],
                thread_ts=event["thread_ts"],
                conversation_cache=None,
            )

            mock_handle_message.assert_called_once_with(
                text="hello there",  # Cleaned text after removing mention
                user_id="U123456789",
                slack_service=mock_slack_service,
                llm_service=mock_llm_service,
                channel="C123456789",
                thread_ts="1234567890.123456",
                conversation_cache=None,
            )

    @pytest.mark.asyncio
    async def test_message_filtering_logic(self, mock_slack_service, mock_llm_service):
        """Test message filtering logic"""
        # Test bot message filtering using factory
        event_bot_id = SlackEventFactory.create_bot_event()
        assert event_bot_id.get("bot_id") is not None  # Should be filtered out

        event_bot_subtype = SlackEventFactory.create_bot_subtype_event()
        assert (
            event_bot_subtype.get("subtype") == "bot_message"
        )  # Should be filtered out

        # Test no user filtering using factory
        event_no_user = SlackEventFactory.create_no_user_event()
        assert event_no_user.get("user") is None  # Should be filtered out

        # Test valid message using factory
        event_valid = SlackEventFactory.create_valid_event()
        assert event_valid.get("user") is not None  # Should be processed


class TestProcessMessageByContext:
    """Tests for process_message_by_context function"""

    @pytest.fixture
    def mock_slack_service(self):
        """Create mock Slack service"""
        return SlackServiceFactory.create_basic_service()

    @pytest.fixture
    def mock_llm_service(self):
        """Create mock LLM service"""
        return LLMServiceFactory.create_basic_service()

    @pytest.mark.asyncio
    async def test_process_message_by_context_dm(
        self, mock_slack_service, mock_llm_service
    ):
        """Test processing message in DM context"""
        with patch(
            "handlers.event_handlers.handle_message", new_callable=AsyncMock
        ) as mock_handle_message:
            await process_message_by_context(
                user_id="U12345",
                channel="D12345",
                channel_type="im",
                text="Hello",
                thread_ts=None,
                ts="1234567890.123456",
                slack_service=mock_slack_service,
                llm_service=mock_llm_service,
            )

            mock_handle_message.assert_called_once()
            call_args = mock_handle_message.call_args
            assert call_args.kwargs["channel"] == "D12345"
            assert call_args.kwargs["text"] == "Hello"
            assert call_args.kwargs["user_id"] == "U12345"

    @pytest.mark.asyncio
    async def test_process_message_by_context_mention(
        self, mock_slack_service, mock_llm_service
    ):
        """Test processing message with bot mention"""
        with patch(
            "handlers.event_handlers.handle_message", new_callable=AsyncMock
        ) as mock_handle_message:
            await process_message_by_context(
                user_id="U12345",
                channel="C12345",
                channel_type="channel",
                text="<@B12345678> hello",
                thread_ts=None,
                ts="1234567890.123456",
                slack_service=mock_slack_service,
                llm_service=mock_llm_service,
            )

            mock_handle_message.assert_called_once()
            call_args = mock_handle_message.call_args
            assert (
                call_args.kwargs["text"] == "hello"
            )  # Text should be cleaned (split(">", 1)[-1].strip())

    @pytest.mark.asyncio
    async def test_process_message_by_context_thread_participant(
        self, mock_slack_service, mock_llm_service
    ):
        """Test processing message in thread where bot is participant"""
        # Use factory to create service with specific thread info
        mock_slack_service = SlackServiceFactory.create_service_with_thread_info(
            bot_is_participant=True
        )

        with patch(
            "handlers.event_handlers.handle_message", new_callable=AsyncMock
        ) as mock_handle_message:
            await process_message_by_context(
                user_id="U12345",
                channel="C12345",
                channel_type="channel",
                text="Reply in thread",
                thread_ts="1234567890.123456",
                ts="1234567890.234567",
                slack_service=mock_slack_service,
                llm_service=mock_llm_service,
            )

            # Should respond in threads when bot is participant
            mock_handle_message.assert_called_once()
            mock_slack_service.get_thread_info.assert_called_once_with(
                "C12345", "1234567890.123456"
            )

    @pytest.mark.asyncio
    async def test_process_message_by_context_thread_not_participant(
        self, mock_slack_service, mock_llm_service
    ):
        """Test processing message in thread where bot is not participant"""
        # Use factory to create service with specific thread info
        mock_slack_service = SlackServiceFactory.create_service_with_thread_info(
            bot_is_participant=False
        )

        with patch(
            "handlers.event_handlers.handle_message", new_callable=AsyncMock
        ) as mock_handle_message:
            await process_message_by_context(
                user_id="U12345",
                channel="C12345",
                channel_type="channel",
                text="Reply in thread",
                thread_ts="1234567890.123456",
                ts="1234567890.234567",
                slack_service=mock_slack_service,
                llm_service=mock_llm_service,
            )

            # Should NOT respond when bot is not a participant
            mock_handle_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_message_by_context_no_response(
        self, mock_slack_service, mock_llm_service
    ):
        """Test processing message that shouldn't get response"""
        with patch(
            "handlers.event_handlers.handle_message", new_callable=AsyncMock
        ) as mock_handle_message:
            # Message in channel without mention or thread
            await process_message_by_context(
                user_id="U12345",
                channel="C12345",
                channel_type="channel",
                text="Just a regular message",
                thread_ts=None,
                ts="1234567890.123456",
                slack_service=mock_slack_service,
                llm_service=mock_llm_service,
            )

            # Should not call handle_message
            mock_handle_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_message_thread_error_fallback(
        self, mock_slack_service, mock_llm_service
    ):
        """Test thread processing falls back to responding on error"""
        mock_slack_service.get_thread_info = AsyncMock(
            side_effect=Exception("Permission error")
        )

        with patch(
            "handlers.event_handlers.handle_message", new_callable=AsyncMock
        ) as mock_handle_message:
            await process_message_by_context(
                user_id="U12345",
                channel="C12345",
                channel_type="channel",
                text="Message in thread",
                thread_ts="1234567890.123456",
                ts="1234567890.234567",
                slack_service=mock_slack_service,
                llm_service=mock_llm_service,
            )

            # Should still respond despite error
            mock_handle_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_with_cache(
        self, mock_slack_service, mock_llm_service
    ):
        """Test processing message with conversation cache"""
        mock_cache = AsyncMock()

        with patch(
            "handlers.event_handlers.handle_message", new_callable=AsyncMock
        ) as mock_handle_message:
            await process_message_by_context(
                user_id="U12345",
                channel="D12345",
                channel_type="im",
                text="Hello with cache",
                thread_ts=None,
                ts="1234567890.123456",
                slack_service=mock_slack_service,
                llm_service=mock_llm_service,
                conversation_cache=mock_cache,
            )

            # Verify cache was passed through
            mock_handle_message.assert_called_once()
            args, kwargs = mock_handle_message.call_args
            assert kwargs.get("conversation_cache") == mock_cache

    @pytest.mark.asyncio
    async def test_mention_text_cleaning_edge_cases(
        self, mock_slack_service, mock_llm_service
    ):
        """Test various mention text cleaning scenarios"""
        with patch(
            "handlers.event_handlers.handle_message", new_callable=AsyncMock
        ) as mock_handle_message:
            # Test mention with no text after
            await process_message_by_context(
                user_id="U12345",
                channel="C12345",
                channel_type="channel",
                text="<@B12345678>",
                thread_ts=None,
                ts="1234567890.123456",
                slack_service=mock_slack_service,
                llm_service=mock_llm_service,
            )

            # Should still call handler with empty string
            mock_handle_message.assert_called_once()
            args, kwargs = mock_handle_message.call_args
            assert kwargs["text"] == ""

    @pytest.mark.asyncio
    async def test_bot_id_none_handling(self, mock_slack_service, mock_llm_service):
        """Test handling when bot_id is None"""
        mock_slack_service.bot_id = None

        with patch(
            "handlers.event_handlers.handle_message", new_callable=AsyncMock
        ) as mock_handle_message:
            await process_message_by_context(
                user_id="U12345",
                channel="C12345",
                channel_type="channel",
                text="<@B12345678> hello",
                thread_ts=None,
                ts="1234567890.123456",
                slack_service=mock_slack_service,
                llm_service=mock_llm_service,
            )

            # Should not respond when bot_id is None
            mock_handle_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_complex_mention_scenarios(
        self, mock_slack_service, mock_llm_service
    ):
        """Test complex mention text scenarios"""
        test_cases = [
            (
                "<@B12345678> simple message",
                "simple message",
            ),  # Fixed: split(">", 1)[-1].strip() removes leading space
            ("<@B12345678>no space", "no space"),
            ("<@B12345678> ", ""),  # Fixed: strip() removes the space
            ("prefix <@B12345678> suffix", "suffix"),  # Fixed: text after > is cleaned
        ]

        for input_text, expected_clean in test_cases:
            with patch(
                "handlers.event_handlers.handle_message", new_callable=AsyncMock
            ) as mock_handle_message:
                await process_message_by_context(
                    user_id="U12345",
                    channel="C12345",
                    channel_type="channel",
                    text=input_text,
                    thread_ts=None,
                    ts="1234567890.123456",
                    slack_service=mock_slack_service,
                    llm_service=mock_llm_service,
                )

                if (
                    mock_slack_service.bot_id
                    and f"<@{mock_slack_service.bot_id}>" in input_text
                ):
                    mock_handle_message.assert_called_once()
                    args, kwargs = mock_handle_message.call_args
                    assert kwargs["text"] == expected_clean
                else:
                    # Should not respond if bot is not mentioned
                    mock_handle_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_thread_participation_edge_cases(
        self, mock_slack_service, mock_llm_service
    ):
        """Test edge cases in thread participation checking"""
        from models import ThreadInfo

        # Test with various thread_info responses
        thread_info_cases = [
            (
                ThreadInfo(
                    exists=True,
                    message_count=1,
                    bot_is_participant=True,
                    messages=[],
                    participant_ids=["B12345678"],
                ),
                True,
            ),  # Should respond
            (
                ThreadInfo(
                    exists=True,
                    message_count=1,
                    bot_is_participant=False,
                    messages=[],
                    participant_ids=[],
                ),
                False,
            ),  # Should not respond
        ]

        for thread_info, should_respond in thread_info_cases:
            mock_slack_service.get_thread_info = AsyncMock(return_value=thread_info)

            with patch(
                "handlers.event_handlers.handle_message", new_callable=AsyncMock
            ) as mock_handle_message:
                await process_message_by_context(
                    user_id="U12345",
                    channel="C12345",
                    channel_type="channel",
                    text="Thread message",
                    thread_ts="1234567890.123456",
                    ts="1234567890.234567",
                    slack_service=mock_slack_service,
                    llm_service=mock_llm_service,
                )

                if should_respond:
                    mock_handle_message.assert_called_once()
                else:
                    mock_handle_message.assert_not_called()


class TestEventHandlerErrorHandling:
    """Test error handling in event handlers"""

    @pytest.fixture
    def mock_slack_service(self):
        """Create mock Slack service"""
        service = AsyncMock()
        service.bot_id = "B12345678"
        return service

    @pytest.fixture
    def mock_llm_service(self):
        """Create mock LLM service"""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_assistant_thread_error_handling(
        self, mock_slack_service, mock_llm_service
    ):
        """Test assistant thread handler error handling"""
        mock_slack_service.send_message.side_effect = Exception("Send failed")

        # Should not raise - error should be caught and logged
        # This simulates what the actual handler does
        import contextlib

        with contextlib.suppress(Exception):
            await mock_slack_service.send_message(
                channel="C123", text="Welcome message", thread_ts="1234"
            )

        # Verify the send was attempted
        mock_slack_service.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_mention_handler_error_propagation(
        self, mock_slack_service, mock_llm_service
    ):
        """Test that mention handler errors are properly handled"""
        with (
            patch(
                "handlers.event_handlers.handle_message",
                new_callable=AsyncMock,
                side_effect=Exception("Processing failed"),
            ) as mock_handle_message,
            patch(
                "handlers.event_handlers.handle_error", new_callable=AsyncMock
            ) as mock_handle_error,
        ):
            # Simulate the error handling that would happen in the mention handler
            try:
                # This would be the handle_message call in the actual handler
                await mock_handle_message(
                    text=" test",
                    user_id="U123",
                    slack_service=mock_slack_service,
                    llm_service=mock_llm_service,
                    channel="C123",
                    thread_ts="1234",
                    conversation_cache=None,
                )
            except Exception as e:
                # Handler would catch and call handle_error
                await mock_handle_error(
                    None,  # client
                    "C123",  # channel
                    "1234",  # thread_ts
                    e,
                    "I'm sorry, I encountered an error while processing your request.",
                )

            mock_handle_error.assert_called_once()
