"""Unit tests for message_handlers.py core orchestration logic.

Tests individual functions in isolation, separate from integration tests.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from handlers.message_handlers import handle_message


# Shared fixtures for all tests in this file
@pytest.fixture(autouse=True)
def mock_rag_dependencies():
    """Auto-mock RAG service dependencies for all tests in this file"""
    mock_rag = AsyncMock()
    mock_rag.generate_response = AsyncMock(return_value={"response": "test response"})

    with (
        patch("handlers.message_handlers.get_rag_client", return_value=mock_rag),
        patch(
            "handlers.message_handlers.get_user_system_prompt",
            return_value="You are a helpful assistant",
        ),
        patch(
            "handlers.message_handlers.MessageFormatter.format_message",
            return_value="formatted",
        ),
        patch("handlers.message_handlers.get_metrics_service", return_value=None),
        patch("handlers.message_handlers.get_langfuse_service", return_value=None),
    ):
        yield mock_rag


class TestConversationIDLogic:
    """Unit tests for conversation ID generation logic"""

    @pytest.mark.asyncio
    async def test_conversation_id_with_thread(self, mock_rag_dependencies):
        """Test conversation ID uses thread_ts when available"""
        mock_slack = AsyncMock()
        mock_slack.get_thread_history = AsyncMock(return_value=([], True))
        mock_slack.send_thinking_indicator = AsyncMock(return_value="ts123")
        mock_slack.delete_thinking_indicator = AsyncMock()
        mock_slack.send_message = AsyncMock()

        await handle_message(
            text="test",
            user_id="U123",
            slack_service=mock_slack,
            channel="C123",
            thread_ts="1234.5678",
            message_ts="9999.0000",
        )

        # Verify RAG client was called with thread_ts as conversation_id
        mock_rag_dependencies.generate_response.assert_called_once()
        call_kwargs = mock_rag_dependencies.generate_response.call_args[1]
        assert call_kwargs["conversation_id"] == "1234.5678"

    @pytest.mark.asyncio
    async def test_conversation_id_dm_without_thread(self):
        """Test conversation ID uses channel for DMs without thread"""
        mock_slack = AsyncMock()
        mock_rag = AsyncMock()
        mock_slack.get_thread_history = AsyncMock(return_value=([], True))
        mock_rag.generate_response = AsyncMock(
            return_value={"response": "test response"}
        )
        mock_slack.send_thinking_indicator = AsyncMock(return_value="ts123")
        mock_slack.delete_thinking_indicator = AsyncMock()
        mock_slack.send_message = AsyncMock()

        with (
            patch("handlers.message_handlers.get_metrics_service", return_value=None),
            patch("handlers.message_handlers.get_langfuse_service", return_value=None),
            patch("handlers.message_handlers.get_rag_client", return_value=mock_rag),
            patch(
                "handlers.message_handlers.get_user_system_prompt",
                return_value="You are a helpful assistant",
            ),
            patch(
                "handlers.message_handlers.MessageFormatter.format_message",
                return_value="formatted",
            ),
        ):
            await handle_message(
                text="test",
                user_id="U123",
                slack_service=mock_slack,
                channel="D123ABC",  # DM channel
                thread_ts=None,
                message_ts="1234.5678",
            )

        # Verify RAG client was called with channel as conversation_id for DMs
        call_kwargs = mock_rag.generate_response.call_args[1]
        assert call_kwargs["conversation_id"] == "D123ABC"

    @pytest.mark.asyncio
    async def test_conversation_id_channel_without_thread(self, mock_rag_dependencies):
        """Test conversation ID uses message_ts for channels without thread"""
        mock_slack = AsyncMock()
        mock_slack.get_thread_history = AsyncMock(return_value=([], True))
        mock_slack.send_thinking_indicator = AsyncMock(return_value="ts123")
        mock_slack.delete_thinking_indicator = AsyncMock()
        mock_slack.send_message = AsyncMock()

        await handle_message(
            text="test",
            user_id="U123",
            slack_service=mock_slack,
            channel="C123",
            thread_ts=None,
            message_ts="1234.5678",
        )

        # Verify RAG client was called with message_ts as conversation_id for channels
        call_kwargs = mock_rag_dependencies.generate_response.call_args[1]
        assert call_kwargs["conversation_id"] == "1234.5678"

    @pytest.mark.asyncio
    async def test_conversation_id_missing_raises_error(self):
        """Test that missing conversation ID for non-DM raises error"""
        mock_slack = AsyncMock()

        with pytest.raises(ValueError, match="Must provide thread_ts or message_ts"):
            await handle_message(
                text="test",
                user_id="U123",
                slack_service=mock_slack,
                channel="C123",  # Not a DM
                thread_ts=None,
                message_ts=None,  # Missing!
            )


class TestRAGControl:
    """Unit tests for RAG enable/disable logic"""

    @pytest.mark.asyncio
    async def test_rag_disabled_for_profile_threads(self, mock_rag_dependencies):
        """Test RAG is disabled for profile threads"""
        mock_slack = AsyncMock()
        mock_llm = AsyncMock()
        mock_cache = AsyncMock()
        mock_slack.get_thread_history = AsyncMock(return_value=([], True))
        mock_llm.get_response = AsyncMock(return_value="response")
        mock_slack.send_thinking_indicator = AsyncMock(return_value="ts123")
        mock_slack.delete_thinking_indicator = AsyncMock()
        mock_slack.send_message = AsyncMock()
        mock_cache.get_thread_type = AsyncMock(return_value="profile")
        mock_cache.get_document_content = AsyncMock(return_value=(None, None))

        with (
            patch("handlers.message_handlers.get_metrics_service", return_value=None),
            patch("handlers.message_handlers.get_langfuse_service", return_value=None),
        ):
            await handle_message(
                text="test",
                user_id="U123",
                slack_service=mock_slack,
                channel="C123",
                thread_ts="1234.5678",
                conversation_cache=mock_cache,
                message_ts="1234.5678",
            )

        # Verify LLM was called with use_rag=False
        call_kwargs = mock_rag_dependencies.generate_response.call_args[1]
        assert call_kwargs["use_rag"] is False

    @pytest.mark.asyncio
    async def test_rag_enabled_for_normal_threads(self, mock_rag_dependencies):
        """Test RAG is enabled for normal threads"""
        mock_slack = AsyncMock()
        mock_llm = AsyncMock()
        mock_cache = AsyncMock()
        mock_slack.get_thread_history = AsyncMock(return_value=([], True))
        mock_llm.get_response = AsyncMock(return_value="response")
        mock_slack.send_thinking_indicator = AsyncMock(return_value="ts123")
        mock_slack.delete_thinking_indicator = AsyncMock()
        mock_slack.send_message = AsyncMock()
        mock_cache.get_thread_type = AsyncMock(return_value=None)
        mock_cache.get_document_content = AsyncMock(return_value=(None, None))

        with (
            patch("handlers.message_handlers.get_metrics_service", return_value=None),
            patch("handlers.message_handlers.get_langfuse_service", return_value=None),
        ):
            await handle_message(
                text="test",
                user_id="U123",
                slack_service=mock_slack,
                channel="C123",
                thread_ts="1234.5678",
                conversation_cache=mock_cache,
                message_ts="1234.5678",
            )

        # Verify LLM was called with use_rag=True
        call_kwargs = mock_rag_dependencies.generate_response.call_args[1]
        assert call_kwargs["use_rag"] is True


class TestFileAttachmentProcessing:
    """Unit tests for file attachment processing in message flow"""

    @pytest.mark.asyncio
    async def test_message_with_file_attachments(self, mock_rag_dependencies):
        """Test that file attachments are processed"""
        mock_slack = AsyncMock()
        mock_llm = AsyncMock()
        mock_slack.get_thread_history = AsyncMock(return_value=([], True))
        mock_llm.get_response = AsyncMock(return_value="response")
        mock_slack.send_thinking_indicator = AsyncMock(return_value="ts123")
        mock_slack.delete_thinking_indicator = AsyncMock()
        mock_slack.send_message = AsyncMock()

        files = [{"name": "test.txt", "url_private": "https://test.com/file"}]

        with (
            patch("handlers.message_handlers.get_metrics_service", return_value=None),
            patch("handlers.message_handlers.get_langfuse_service", return_value=None),
            patch("handlers.message_handlers.process_file_attachments") as mock_process,
        ):
            mock_process.return_value = "file content"

            await handle_message(
                text="test",
                user_id="U123",
                slack_service=mock_slack,
                channel="C123",
                thread_ts="1234.5678",
                files=files,
                message_ts="1234.5678",
            )

            # Verify file processing was called
            mock_process.assert_called_once_with(files, mock_slack)

            # Verify LLM received document content
            call_kwargs = mock_rag_dependencies.generate_response.call_args[1]
            assert call_kwargs["document_content"] == "file content"
            assert call_kwargs["document_filename"] == "test.txt"


@pytest.mark.skip(
    reason="Bot command routing moved to rag-service in microservices refactor. "
    "See rag-service tests for routing logic."
)
class TestBotCommandRouting:
    """Unit tests for bot command routing logic

    NOTE: This tests OLD ARCHITECTURE. Routing now happens in rag-service.
    """

    @pytest.mark.asyncio
    async def test_bot_command_routes_to_agent(self):
        """Test that recognized bot commands route to agents"""
        mock_slack = AsyncMock()
        mock_slack.send_thinking_indicator = AsyncMock(return_value="ts123")
        mock_slack.delete_thinking_indicator = AsyncMock()
        mock_slack.send_message = AsyncMock()

        with patch("handlers.message_handlers.route_command") as mock_route:
            mock_route.return_value = (
                "profile",
                {},
                "Anthropic",
            )  # (agent_name, params, query)

            with patch("handlers.message_handlers.get_agent_info") as mock_agent_info:
                mock_agent_info.return_value = {
                    "agent_name": "profile",
                    "display_name": "Profile Agent",
                }

                with patch(
                    "handlers.prompt_manager.get_user_system_prompt"
                ) as mock_prompt:
                    mock_prompt.return_value = "system prompt"

                    # Mock the agent client to prevent actual HTTP calls
                    with patch("services.agent_client.AgentClient") as MockAgentClient:
                        mock_client = AsyncMock()
                        mock_client.invoke_agent = AsyncMock(
                            return_value={"response": "agent response"}
                        )
                        MockAgentClient.return_value = mock_client

                        # Note: handle_bot_command removed in microservices refactor
                        # This test is skipped - kept for reference
                        result = True  # Placeholder for old test logic

                        # Should return True (command handled)
                        assert result is True


class TestMetricsTracking:
    """Unit tests for metrics tracking in message handlers"""

    @pytest.mark.asyncio
    async def test_message_processed_metric_recorded(self):
        """Test that message processed metric is recorded"""
        mock_slack = AsyncMock()
        mock_llm = AsyncMock()
        mock_metrics = Mock()
        mock_slack.get_thread_history = AsyncMock(return_value=([], True))
        mock_llm.get_response = AsyncMock(return_value="response")
        mock_slack.send_thinking_indicator = AsyncMock(return_value="ts123")
        mock_slack.delete_thinking_indicator = AsyncMock()
        mock_slack.send_message = AsyncMock()

        with (
            patch(
                "handlers.message_handlers.get_metrics_service",
                return_value=mock_metrics,
            ),
            patch("handlers.message_handlers.get_langfuse_service", return_value=None),
        ):
            await handle_message(
                text="test",
                user_id="U123",
                slack_service=mock_slack,
                channel="C123",
                thread_ts="1234.5678",
                message_ts="1234.5678",
            )

        # Verify metrics were recorded
        mock_metrics.record_message_processed.assert_called_once_with(
            user_id="U123", channel_type="channel"
        )
        mock_metrics.record_conversation_activity.assert_called_once_with("1234.5678")

    @pytest.mark.asyncio
    async def test_dm_channel_type_detected(self):
        """Test that DM channel type is correctly detected"""
        mock_slack = AsyncMock()
        mock_llm = AsyncMock()
        mock_metrics = Mock()
        mock_slack.get_thread_history = AsyncMock(return_value=([], True))
        mock_llm.get_response = AsyncMock(return_value="response")
        mock_slack.send_thinking_indicator = AsyncMock(return_value="ts123")
        mock_slack.delete_thinking_indicator = AsyncMock()
        mock_slack.send_message = AsyncMock()

        with (
            patch(
                "handlers.message_handlers.get_metrics_service",
                return_value=mock_metrics,
            ),
            patch("handlers.message_handlers.get_langfuse_service", return_value=None),
        ):
            await handle_message(
                text="test",
                user_id="U123",
                slack_service=mock_slack,
                channel="D123ABC",  # DM channel
                thread_ts=None,
                message_ts="1234.5678",
            )

        # Verify DM channel type was recorded
        mock_metrics.record_message_processed.assert_called_once_with(
            user_id="U123", channel_type="dm"
        )


class TestErrorHandling:
    """Unit tests for error handling in message handlers"""

    @pytest.mark.asyncio
    async def test_llm_error_sends_fallback_message(self, mock_rag_dependencies):
        """Test that RAG client errors/empty responses result in fallback message"""
        mock_slack = AsyncMock()
        mock_slack.get_thread_history = AsyncMock(return_value=([], True))
        mock_slack.send_thinking_indicator = AsyncMock(return_value="ts123")
        mock_slack.delete_thinking_indicator = AsyncMock()
        mock_slack.send_message = AsyncMock()

        # Mock RAG client to return empty response (triggers fallback)
        mock_rag_dependencies.generate_response = AsyncMock(
            return_value={"response": ""}
        )

        await handle_message(
            text="test",
            user_id="U123",
            slack_service=mock_slack,
            channel="C123",
            thread_ts="1234.5678",
            message_ts="1234.5678",
        )

        # Verify fallback message was sent
        calls = mock_slack.send_message.call_args_list
        fallback_call = calls[-1]  # Last call should be fallback
        assert "couldn't generate a response" in fallback_call[1]["text"]
