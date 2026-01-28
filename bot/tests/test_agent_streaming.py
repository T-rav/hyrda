"""
Tests for agent streaming event handling.

Verifies that the bot correctly processes and displays streaming events
from agent-service, including node start/complete status updates.
"""

import json
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


# Mock OpenTelemetry before importing
@contextmanager
def mock_create_span(*args, **kwargs):
    """Mock create_span as a proper context manager."""
    yield MagicMock()


def mock_record_exception(*args, **kwargs):
    """Mock record_exception as a no-op."""
    pass


# Apply mocks
_create_span_patcher = patch(
    "shared.utils.otel_http_client.create_span", side_effect=mock_create_span
)
_record_exception_patcher = patch(
    "shared.utils.otel_http_client.record_exception", side_effect=mock_record_exception
)
_create_span_patcher.start()
_record_exception_patcher.start()

from bot.services.agent_client import AgentClient


class TestAgentStreaming:
    """Test agent streaming event parsing and display."""

    @pytest.mark.asyncio
    async def test_stream_parses_node_started_events(self):
        """Test that stream() correctly parses node started events."""
        # Create mock SSE stream with node started event
        mock_response = Mock()
        mock_response.status_code = 200

        started_event = {
            "phase": "started",
            "step": "research",
            "message": "Research Company",
        }

        # Mock SSE data format: "data: {json}\n\n"
        sse_line = f"data: {json.dumps(started_event)}"

        async def mock_aiter_lines():
            yield sse_line

        mock_response.aiter_lines = mock_aiter_lines
        mock_response.raise_for_status = Mock()

        # Mock httpx client with proper async context manager support
        mock_client = AsyncMock()

        # Create mock stream context
        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_context.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = Mock(return_value=mock_stream_context)

        # Mock AsyncClient context manager
        mock_client_context = AsyncMock()
        mock_client_context.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_context.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client_context):
            # Test stream parsing
            client = AgentClient()
            events = []
            async for event in client.stream(
                "profile", "test query", {"thread_id": "test"}
            ):
                events.append(event)

            # Verify event was parsed correctly
            assert len(events) == 1
            assert events[0]["phase"] == "started"
            assert events[0]["step"] == "research"
            assert events[0]["message"] == "Research Company"

    @pytest.mark.asyncio
    async def test_stream_parses_node_completed_events(self):
        """Test that stream() correctly parses node completed events."""
        mock_response = Mock()
        mock_response.status_code = 200

        completed_event = {
            "phase": "completed",
            "step": "research",
            "message": "Research Company",
            "duration": "5.2s",
        }

        sse_line = f"data: {json.dumps(completed_event)}"

        async def mock_aiter_lines():
            yield sse_line

        mock_response.aiter_lines = mock_aiter_lines
        mock_response.raise_for_status = Mock()

        # Mock httpx client with proper async context manager support
        mock_client = AsyncMock()

        # Create mock stream context
        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_context.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = Mock(return_value=mock_stream_context)

        # Mock AsyncClient context manager
        mock_client_context = AsyncMock()
        mock_client_context.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_context.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client_context):
            client = AgentClient()
            events = []
            async for event in client.stream(
                "profile", "test query", {"thread_id": "test"}
            ):
                events.append(event)

            assert len(events) == 1
            assert events[0]["phase"] == "completed"
            assert events[0]["step"] == "research"
            assert events[0]["duration"] == "5.2s"

    @pytest.mark.asyncio
    async def test_stream_parses_final_response_event(self):
        """Test that stream() correctly parses final response events."""
        mock_response = Mock()
        mock_response.status_code = 200

        response_event = {
            "response": "Microsoft is a technology company...",
            "metadata": {"sources": ["example.com"]},
        }

        sse_line = f"data: {json.dumps(response_event)}"

        async def mock_aiter_lines():
            yield sse_line

        mock_response.aiter_lines = mock_aiter_lines
        mock_response.raise_for_status = Mock()

        # Mock httpx client with proper async context manager support
        mock_client = AsyncMock()

        # Create mock stream context
        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_context.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = Mock(return_value=mock_stream_context)

        # Mock AsyncClient context manager
        mock_client_context = AsyncMock()
        mock_client_context.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_context.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client_context):
            client = AgentClient()
            events = []
            async for event in client.stream(
                "profile", "test query", {"thread_id": "test"}
            ):
                events.append(event)

            assert len(events) == 1
            assert "response" in events[0]
            assert "Microsoft" in events[0]["response"]
            assert events[0]["metadata"]["sources"] == ["example.com"]

    @pytest.mark.asyncio
    async def test_stream_handles_multiple_node_executions(self):
        """Test that stream() correctly handles multiple sequential node events."""
        mock_response = Mock()
        mock_response.status_code = 200

        events_sequence = [
            {"phase": "started", "step": "research", "message": "Research Company"},
            {
                "phase": "completed",
                "step": "research",
                "message": "Research Company",
                "duration": "3.5s",
            },
            {"phase": "started", "step": "analyze", "message": "Analyze Findings"},
            {
                "phase": "completed",
                "step": "analyze",
                "message": "Analyze Findings",
                "duration": "2.1s",
            },
            {"response": "Analysis complete", "metadata": {}},
        ]

        async def mock_aiter_lines():
            for event in events_sequence:
                yield f"data: {json.dumps(event)}"

        mock_response.aiter_lines = mock_aiter_lines
        mock_response.raise_for_status = Mock()

        # Mock httpx client with proper async context manager support
        mock_client = AsyncMock()

        # Create mock stream context
        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_context.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = Mock(return_value=mock_stream_context)

        # Mock AsyncClient context manager
        mock_client_context = AsyncMock()
        mock_client_context.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_context.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client_context):
            client = AgentClient()
            events = []
            async for event in client.stream(
                "profile", "test query", {"thread_id": "test"}
            ):
                events.append(event)

            # Verify all events were received in order
            assert len(events) == 5
            assert events[0]["phase"] == "started"
            assert events[0]["step"] == "research"
            assert events[1]["phase"] == "completed"
            assert events[1]["duration"] == "3.5s"
            assert events[2]["step"] == "analyze"
            assert events[4].get("response") == "Analysis complete"

    @pytest.mark.asyncio
    async def test_stream_skips_malformed_sse_data(self):
        """Test that stream() gracefully skips malformed SSE events."""
        mock_response = Mock()
        mock_response.status_code = 200

        async def mock_aiter_lines():
            yield "data: {invalid json"  # Malformed JSON
            yield f"data: {json.dumps({'phase': 'started', 'step': 'test', 'message': 'Test'})}"  # Valid
            yield "not a data line"  # Invalid SSE format
            yield f"data: {json.dumps({'response': 'Done'})}"  # Valid

        mock_response.aiter_lines = mock_aiter_lines
        mock_response.raise_for_status = Mock()

        # Mock httpx client with proper async context manager support
        mock_client = AsyncMock()

        # Create mock stream context
        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_context.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = Mock(return_value=mock_stream_context)

        # Mock AsyncClient context manager
        mock_client_context = AsyncMock()
        mock_client_context.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_context.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client_context):
            client = AgentClient()
            events = []
            async for event in client.stream(
                "profile", "test query", {"thread_id": "test"}
            ):
                events.append(event)

            # Should only get the 2 valid events
            assert len(events) == 2
            assert events[0]["phase"] == "started"
            assert events[1].get("response") == "Done"
