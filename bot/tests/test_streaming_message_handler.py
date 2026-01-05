"""Unit tests for streaming message handler with JSON payloads."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_message_handler_shows_working_message():
    """Test that initial 'working' message is shown on first chunk."""
    from handlers.message_handlers import handle_message
    from services.slack_service import SlackService

    # Mock services
    mock_slack = AsyncMock(spec=SlackService)
    mock_slack.get_thread_history = AsyncMock(return_value=([], False))
    mock_slack.send_message = AsyncMock(return_value={"ts": "123.456"})
    mock_slack.update_message = AsyncMock()
    mock_slack.send_thinking_indicator = AsyncMock(return_value="thinking_ts")
    mock_slack.delete_thinking_indicator = AsyncMock()

    # Mock RAG client to yield JSON chunks
    mock_rag_client = MagicMock()

    async def mock_stream(*args, **kwargs):
        yield json.dumps(
            {"step": "test_node", "phase": "started", "message": "Test Node"}
        )
        yield json.dumps(
            {
                "step": "test_node",
                "phase": "completed",
                "message": "Test Node",
                "duration": "2.5s",
            }
        )

    mock_rag_client.generate_response_stream = mock_stream
    mock_rag_client.fetch_agent_info = AsyncMock(
        return_value=(["^profile\\s"], {"^profile\\s": "profile"})
    )

    with (
        patch("handlers.message_handlers.get_rag_client", return_value=mock_rag_client),
        patch("handlers.message_handlers.get_user_system_prompt", return_value=None),
        patch(
            "handlers.message_handlers.MessageFormatter.format_message",
            new=AsyncMock(side_effect=lambda x: x),
        ),
    ):
        await handle_message(
            text="profile test",
            user_id="U123",
            slack_service=mock_slack,
            channel="C123",
            thread_ts="123.456",
        )

    # Should send initial "working" message
    calls = list(mock_slack.send_message.call_args_list)
    assert len(calls) >= 1
    first_call_text = calls[0][1]["text"]
    assert "working" in first_call_text.lower() or "⏳" in first_call_text


@pytest.mark.asyncio
async def test_message_handler_parses_json_payloads():
    """Test that handler correctly parses JSON status payloads."""
    from handlers.message_handlers import handle_message
    from services.slack_service import SlackService

    mock_slack = AsyncMock(spec=SlackService)
    mock_slack.get_thread_history = AsyncMock(return_value=([], False))
    mock_slack.send_message = AsyncMock(return_value={"ts": "123.456"})
    mock_slack.update_message = AsyncMock()
    mock_slack.send_thinking_indicator = AsyncMock(return_value="thinking_ts")
    mock_slack.delete_thinking_indicator = AsyncMock()

    mock_rag_client = MagicMock()

    async def mock_stream(*args, **kwargs):
        # Yield started
        yield json.dumps({"step": "node1", "phase": "started", "message": "Node 1"})
        # Yield completed
        yield json.dumps(
            {
                "step": "node1",
                "phase": "completed",
                "message": "Node 1",
                "duration": "3.2s",
            }
        )
        # Yield final result (modern format with type: "result")
        yield json.dumps(
            {
                "type": "result",
                "node": "final_report",
                "data": {
                    "message": "# Final Report\n\nReport content...",
                    "attachments": [],
                },
            }
        )

    mock_rag_client.generate_response_stream = mock_stream
    mock_rag_client.fetch_agent_info = AsyncMock(
        return_value=(["^profile\\s"], {"^profile\\s": "profile"})
    )

    with (
        patch("handlers.message_handlers.get_rag_client", return_value=mock_rag_client),
        patch("handlers.message_handlers.get_user_system_prompt", return_value=None),
        patch(
            "handlers.message_handlers.MessageFormatter.format_message",
            new=AsyncMock(side_effect=lambda x: x),
        ),
    ):
        await handle_message(
            text="profile test",
            user_id="U123",
            slack_service=mock_slack,
            channel="C123",
            thread_ts="123.456",
        )

    # Should update message with status progression
    update_calls = mock_slack.update_message.call_args_list
    assert len(update_calls) >= 2

    # Check that final message contains both completed status and content
    final_call_text = update_calls[-1][1]["text"]
    assert "✅" in final_call_text or "Node 1" in final_call_text
    assert "Final Report" in final_call_text


@pytest.mark.asyncio
async def test_message_handler_replaces_started_with_completed():
    """Test that started status is replaced by completed status."""
    from handlers.message_handlers import handle_message
    from services.slack_service import SlackService

    mock_slack = AsyncMock(spec=SlackService)
    mock_slack.get_thread_history = AsyncMock(return_value=([], False))
    mock_slack.send_message = AsyncMock(return_value={"ts": "123.456"})
    mock_slack.update_message = AsyncMock()
    mock_slack.send_thinking_indicator = AsyncMock(return_value="thinking_ts")
    mock_slack.delete_thinking_indicator = AsyncMock()

    mock_rag_client = MagicMock()

    async def mock_stream(*args, **kwargs):
        yield json.dumps({"step": "node1", "phase": "started", "message": "Node 1"})
        yield json.dumps(
            {
                "step": "node1",
                "phase": "completed",
                "message": "Node 1",
                "duration": "2.0s",
            }
        )

    mock_rag_client.generate_response_stream = mock_stream
    mock_rag_client.fetch_agent_info = AsyncMock(
        return_value=(["^profile\\s"], {"^profile\\s": "profile"})
    )

    with (
        patch("handlers.message_handlers.get_rag_client", return_value=mock_rag_client),
        patch("handlers.message_handlers.get_user_system_prompt", return_value=None),
        patch(
            "handlers.message_handlers.MessageFormatter.format_message",
            new=AsyncMock(side_effect=lambda x: x),
        ),
    ):
        await handle_message(
            text="profile test",
            user_id="U123",
            slack_service=mock_slack,
            channel="C123",
            thread_ts="123.456",
        )

    # Final message should show completed status (✅) not started status (⏳)
    final_call_text = mock_slack.update_message.call_args_list[-1][1]["text"]
    assert "✅" in final_call_text
    assert "2.0s" in final_call_text


@pytest.mark.asyncio
async def test_agent_detection_strips_slack_formatting():
    """Test that agent detection strips Slack formatting before pattern matching."""
    from handlers.message_handlers import handle_message
    from services.slack_service import SlackService

    mock_slack = AsyncMock(spec=SlackService)
    mock_slack.get_thread_history = AsyncMock(return_value=([], False))
    mock_slack.send_message = AsyncMock(return_value={"ts": "123.456"})
    mock_slack.update_message = AsyncMock()
    mock_slack.send_thinking_indicator = AsyncMock(return_value="thinking_ts")
    mock_slack.delete_thinking_indicator = AsyncMock()

    mock_rag_client = MagicMock()
    stream_called = False

    async def mock_stream(*args, **kwargs):
        nonlocal stream_called
        stream_called = True
        yield json.dumps(
            {"step": "test", "phase": "completed", "message": "Test", "duration": "1s"}
        )

    mock_rag_client.generate_response_stream = mock_stream
    mock_rag_client.fetch_agent_info = AsyncMock(
        return_value=(["^profile\\s"], {"^profile\\s": "profile"})
    )

    with (
        patch("handlers.message_handlers.get_rag_client", return_value=mock_rag_client),
        patch("handlers.message_handlers.get_user_system_prompt", return_value=None),
        patch(
            "handlers.message_handlers.MessageFormatter.format_message",
            new=AsyncMock(side_effect=lambda x: x),
        ),
    ):
        # Send message with Slack bold formatting
        await handle_message(
            text="*profile* costco",  # Slack bold formatting
            user_id="U123",
            slack_service=mock_slack,
            channel="C123",
            thread_ts="123.456",
        )

    # Should detect as agent query despite Slack formatting
    assert stream_called, "Streaming should be called for agent query"
