"""Unit tests for agent client streaming with JSON payloads."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_stream_embedded_agent_with_debug_mode():
    """Test streaming LangGraph agent with debug mode yields JSON payloads."""
    from clients.agent_client import AgentClient

    client = AgentClient()

    # Mock LangGraph debug events
    mock_events = [
        # Node starts
        {
            "type": "task",
            "payload": {"name": "clarify_with_user", "input": {"query": "test"}},
        },
        # Node completes
        {
            "type": "task_result",
            "payload": {
                "name": "clarify_with_user",
                "result": {"clarification": "done"},
            },
        },
        # Another node starts
        {
            "type": "task",
            "payload": {"name": "write_research_brief", "input": {}},
        },
        # Another node completes with final report
        {
            "type": "task_result",
            "payload": {
                "name": "write_research_brief",
                "result": {"final_report": "# Company Profile\n\nDetailed report here..."},
            },
        },
    ]

    # Mock agent instance with astream
    mock_agent = MagicMock()

    async def mock_astream(*args, **kwargs):
        for event in mock_events:
            yield event

    mock_agent.astream = mock_astream

    # Mock get_agent to return our mock
    with patch("services.agent_registry.get_agent", return_value=mock_agent):
        # Mock the agent discovery to return embedded agent
        client._agent_cache["test_agent"] = {
            "agent_name": "test_agent",
            "display_name": "Test Agent",
            "endpoint_url": "http://localhost:8000/api/agents/test_agent/invoke",
            "is_cloud": False,
        }

        # Stream the agent
        chunks = []
        async for chunk in client.stream("test_agent", "test query", {}):
            chunks.append(chunk)

    # Should yield 4 JSON payloads (2 started + 1 completed + 1 content)
    assert len(chunks) == 4

    # Parse JSON payloads
    parsed = [json.loads(c.strip()) for c in chunks]

    # First: clarify_with_user started
    assert parsed[0] == {
        "step": "clarify_with_user",
        "phase": "started",
        "message": "Clarify With User",
    }

    # Second: clarify_with_user completed (duration will vary)
    assert parsed[1]["step"] == "clarify_with_user"
    assert parsed[1]["phase"] == "completed"
    assert parsed[1]["message"] == "Clarify With User"
    assert "duration" in parsed[1]

    # Third: write_research_brief started
    assert parsed[2] == {
        "step": "write_research_brief",
        "phase": "started",
        "message": "Write Research Brief",
    }

    # Fourth: write_research_brief completed
    assert parsed[3]["step"] == "write_research_brief"
    assert parsed[3]["phase"] == "completed"
    assert "duration" in parsed[3]


@pytest.mark.asyncio
async def test_stream_skips_internal_nodes():
    """Test that internal nodes (starting with __) are skipped."""
    from clients.agent_client import AgentClient

    client = AgentClient()

    mock_events = [
        {"type": "task", "payload": {"name": "__start__", "input": {}}},
        {"type": "task", "payload": {"name": "real_node", "input": {}}},
        {"type": "task_result", "payload": {"name": "__start__", "result": {}}},
        {"type": "task_result", "payload": {"name": "real_node", "result": {}}},
    ]

    mock_agent = MagicMock()

    async def mock_astream(*args, **kwargs):
        for event in mock_events:
            yield event

    mock_agent.astream = mock_astream

    with patch("services.agent_registry.get_agent", return_value=mock_agent):
        client._agent_cache["test_agent"] = {
            "agent_name": "test_agent",
            "is_cloud": False,
        }

        chunks = []
        async for chunk in client.stream("test_agent", "test query", {}):
            chunks.append(chunk)

    # Should only yield chunks for "real_node", not "__start__"
    assert len(chunks) == 2
    parsed = [json.loads(c.strip()) for c in chunks]
    assert all(p["step"] == "real_node" for p in parsed)


@pytest.mark.asyncio
async def test_stream_extracts_final_report():
    """Test that final report is extracted from task_result payload."""
    from clients.agent_client import AgentClient

    client = AgentClient()

    mock_events = [
        {
            "type": "task_result",
            "payload": {
                "name": "final_report_generation",
                "result": {"final_report": "# Company Profile\n\nFull report content here with sufficient length for extraction..."},
            },
        },
    ]

    mock_agent = MagicMock()

    async def mock_astream(*args, **kwargs):
        for event in mock_events:
            yield event

    mock_agent.astream = mock_astream

    with patch("services.agent_registry.get_agent", return_value=mock_agent):
        client._agent_cache["test_agent"] = {"agent_name": "test_agent", "is_cloud": False}

        chunks = []
        async for chunk in client.stream("test_agent", "test query", {}):
            chunks.append(chunk)

    # Should yield 2 chunks: completion status + final content
    assert len(chunks) == 2

    parsed = [json.loads(c.strip()) for c in chunks]

    # First: completion status
    assert parsed[0]["phase"] == "completed"

    # Second: final content
    assert parsed[1]["type"] == "content"
    assert "Company Profile" in parsed[1]["content"]
    assert len(parsed[1]["content"]) > 100  # Should be full report
