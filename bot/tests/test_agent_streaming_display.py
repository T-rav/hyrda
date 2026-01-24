"""
Tests for agent streaming status display in Slack.

Verifies that agent execution progress:
- Stacks steps without duplicates
- Replaces running steps with completed versions
- Shows final completion status
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest


class MockAgentClient:
    """Mock agent client that yields streaming events."""

    def __init__(self, events):
        self.events = events

    async def stream(self, *args, **kwargs):
        for event in self.events:
            yield event


class TestAgentStreamingDisplay:
    """Test streaming status message display."""

    @pytest.mark.asyncio
    async def test_steps_accumulate_without_duplicates(self):
        """Test that steps stack vertically and duplicates are prevented."""
        # Simulate receiving duplicate 'started' events
        events = [
            {"phase": "started", "step": "research", "message": "Research Company"},
            {
                "phase": "started",
                "step": "research",
                "message": "Research Company",
            },  # Duplicate
            {"phase": "started", "step": "analyze", "message": "Analyze Findings"},
            {
                "phase": "started",
                "step": "analyze",
                "message": "Analyze Findings",
            },  # Duplicate
            {"response": "Done"},
        ]

        slack_service = Mock()
        slack_service.update_message = AsyncMock()

        agent_client = MockAgentClient(events)

        # Import the actual handler
        from handlers import message_handlers

        # Patch dependencies
        with (
            patch.object(
                message_handlers, "get_agent_client", return_value=agent_client
            ),
            patch.object(message_handlers, "SlackService", return_value=slack_service),
        ):
            # Call the internal streaming handler
            await message_handlers._handle_agent_command_streaming(
                primary_name="profile",
                query="microsoft",
                channel="C123",
                thinking_message_ts="123.456",
                context={"thread_id": "test"},
            )

        # Verify update_message was called
        assert slack_service.update_message.call_count > 0

        # Get all status texts that were sent
        status_updates = [
            str(call[0][2]) for call in slack_service.update_message.call_args_list
        ]

        # Verify NO duplicates - "Research Company" should only appear once per update
        for status in status_updates[:-1]:  # Exclude final completion update
            # Count occurrences
            research_count = status.count("Research Company")
            analyze_count = status.count("Analyze Findings")

            # Each should appear at most once
            assert research_count <= 1, f"Duplicate 'Research Company' in: {status}"
            assert analyze_count <= 1, f"Duplicate 'Analyze Findings' in: {status}"

        # Verify final update has both steps
        final_status = status_updates[-1]
        assert "Research Company" in final_status
        assert "Analyze Findings" in final_status

    @pytest.mark.asyncio
    async def test_completed_events_replace_running_steps(self):
        """Test that completed events replace running steps with checkmarks."""
        events = [
            {"phase": "started", "step": "research", "message": "Research Company"},
            {
                "phase": "completed",
                "step": "research",
                "message": "Research Company",
                "duration": "3.5s",
            },
            {"response": "Done"},
        ]

        slack_service = Mock()
        slack_service.update_message = AsyncMock()

        agent_client = MockAgentClient(events)

        from handlers import message_handlers

        with (
            patch.object(
                message_handlers, "get_agent_client", return_value=agent_client
            ),
            patch.object(message_handlers, "SlackService", return_value=slack_service),
        ):
            await message_handlers._handle_agent_command_streaming(
                primary_name="profile",
                query="test",
                channel="C123",
                thinking_message_ts="123.456",
                context={"thread_id": "test"},
            )

        # Get status updates
        status_updates = [
            str(call[0][2]) for call in slack_service.update_message.call_args_list
        ]

        # First update: running step with hourglass
        first_status = status_updates[0]
        assert "⏳" in first_status
        assert "Research Company" in first_status

        # Second update: completed step with checkmark and duration
        second_status = status_updates[1]
        assert "✅" in second_status
        assert "Research Company" in second_status
        assert "3.5s" in second_status

    @pytest.mark.asyncio
    async def test_final_completion_status_shown(self):
        """Test that final completion message is displayed."""
        events = [
            {"phase": "started", "step": "research", "message": "Research"},
            {"response": "Final response text"},
        ]

        slack_service = Mock()
        slack_service.update_message = AsyncMock()

        agent_client = MockAgentClient(events)

        from handlers import message_handlers

        with (
            patch.object(
                message_handlers, "get_agent_client", return_value=agent_client
            ),
            patch.object(message_handlers, "SlackService", return_value=slack_service),
        ):
            await message_handlers._handle_agent_command_streaming(
                primary_name="profile",
                query="test",
                channel="C123",
                thinking_message_ts="123.456",
                context={"thread_id": "test"},
            )

        # Get final status update
        final_status = str(slack_service.update_message.call_args_list[-1][0][2])

        # Should show completed status
        assert "✅" in final_status
        assert "Complete" in final_status

    @pytest.mark.asyncio
    async def test_multiple_steps_stack_vertically(self):
        """Test that multiple steps appear on separate lines."""
        events = [
            {"phase": "started", "step": "step1", "message": "Step One"},
            {"phase": "started", "step": "step2", "message": "Step Two"},
            {"phase": "started", "step": "step3", "message": "Step Three"},
            {"response": "Done"},
        ]

        slack_service = Mock()
        slack_service.update_message = AsyncMock()

        agent_client = MockAgentClient(events)

        from handlers import message_handlers

        with (
            patch.object(
                message_handlers, "get_agent_client", return_value=agent_client
            ),
            patch.object(message_handlers, "SlackService", return_value=slack_service),
        ):
            await message_handlers._handle_agent_command_streaming(
                primary_name="profile",
                query="test",
                channel="C123",
                thinking_message_ts="123.456",
                context={"thread_id": "test"},
            )

        # Get final pre-completion status (second to last update)
        final_steps_status = str(slack_service.update_message.call_args_list[-2][0][2])

        # Verify all three steps are present and on separate lines
        assert "Step One" in final_steps_status
        assert "Step Two" in final_steps_status
        assert "Step Three" in final_steps_status

        # Verify newlines between steps (multiline display)
        lines = final_steps_status.split("\n")
        assert len(lines) >= 3, "Steps should be on separate lines"

    @pytest.mark.asyncio
    async def test_shows_last_10_steps_only(self):
        """Test that only the last 10 steps are displayed."""
        # Create 15 steps
        events = [
            {"phase": "started", "step": f"step{i}", "message": f"Step {i}"}
            for i in range(15)
        ]
        events.append({"response": "Done"})

        slack_service = Mock()
        slack_service.update_message = AsyncMock()

        agent_client = MockAgentClient(events)

        from handlers import message_handlers

        with (
            patch.object(
                message_handlers, "get_agent_client", return_value=agent_client
            ),
            patch.object(message_handlers, "SlackService", return_value=slack_service),
        ):
            await message_handlers._handle_agent_command_streaming(
                primary_name="profile",
                query="test",
                channel="C123",
                thinking_message_ts="123.456",
                context={"thread_id": "test"},
            )

        # Get final steps status (before completion message)
        final_status = str(slack_service.update_message.call_args_list[-2][0][2])

        # Should NOT contain early steps (0-4)
        assert "Step 0" not in final_status
        assert "Step 4" not in final_status

        # Should contain last 10 steps (5-14)
        assert "Step 5" in final_status
        assert "Step 14" in final_status

    @pytest.mark.asyncio
    async def test_preserves_response_and_metadata(self):
        """Test that final response with PDF link is preserved."""
        events = [
            {"phase": "started", "step": "generate", "message": "Generate Report"},
            {
                "response": "Profile complete. View PDF: https://storage.example.com/report.pdf",
                "metadata": {
                    "pdf_url": "https://storage.example.com/report.pdf",
                    "sources": ["example.com"],
                },
            },
        ]

        slack_service = Mock()
        slack_service.update_message = AsyncMock()

        agent_client = MockAgentClient(events)

        from handlers import message_handlers

        with (
            patch.object(
                message_handlers, "get_agent_client", return_value=agent_client
            ),
            patch.object(message_handlers, "SlackService", return_value=slack_service),
        ):
            (
                response,
                metadata,
                _,
            ) = await message_handlers._handle_agent_command_streaming(
                primary_name="profile",
                query="test",
                channel="C123",
                thinking_message_ts="123.456",
                context={"thread_id": "test"},
            )

        # Verify response contains PDF link
        assert "https://storage.example.com/report.pdf" in response

        # Verify metadata preserved
        assert metadata["pdf_url"] == "https://storage.example.com/report.pdf"
        assert "sources" in metadata
