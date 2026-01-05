"""Integration tests for end-to-end agent streaming."""

import json

import pytest


@pytest.mark.asyncio
async def test_agent_streaming_flow_with_debug_mode():
    """Test complete streaming flow: agent client → JSON payloads → status updates."""
    from unittest.mock import MagicMock

    from clients.agent_client import AgentClient

    client = AgentClient()

    # Simulate realistic LangGraph debug events
    mock_events = [
        # First node starts
        {"type": "task", "payload": {"name": "clarify_with_user", "input": {"query": "profile costco"}}},
        # First node completes
        {
            "type": "task_result",
            "payload": {"name": "clarify_with_user", "result": {"clarification": "Company profile request"}},
        },
        # Second node starts
        {"type": "task", "payload": {"name": "write_research_brief", "input": {}}},
        # Second node completes with final output
        {
            "type": "task_result",
            "payload": {
                "name": "write_research_brief",
                "result": {
                    "research_brief": "Brief content...",
                    "final_report": "# Company Profile: Costco\n\n## Overview\nCostco is a leading retailer with significant market presence and strong financial performance across multiple markets.",
                },
            },
        },
    ]

    # Mock agent with astream
    mock_agent = MagicMock()

    async def mock_astream(*args, **kwargs):
        # Verify debug mode is used
        assert kwargs.get("stream_mode") == "debug", "Should use debug stream mode"
        for event in mock_events:
            yield event

    mock_agent.astream = mock_astream

    from unittest.mock import patch

    with patch("services.agent_registry.get_agent", return_value=mock_agent):
        # Set up agent in cache
        client._agent_cache["profile"] = {
            "agent_name": "profile",
            "display_name": "Profile Agent",
            "endpoint_url": "http://localhost:8000/api/agents/profile/invoke",
            "is_cloud": False,
        }

        # Stream the agent
        chunks = []
        async for chunk in client.stream("profile", "profile costco", {}):
            chunks.append(chunk)

    # Verify streaming produced expected payloads
    assert len(chunks) >= 4, f"Expected at least 4 chunks, got {len(chunks)}"

    parsed = [json.loads(c.strip()) for c in chunks]

    # Check progression: started → completed → started → completed + content
    phases = [p.get("phase") or p.get("type") for p in parsed]
    assert "started" in phases, "Should have started phases"
    assert "completed" in phases, "Should have completed phases"
    assert "content" in phases, "Should have final content"

    # Verify step names are formatted nicely
    steps = [p.get("message") for p in parsed if "message" in p]
    assert "Clarify With User" in steps, "Should have formatted node name"
    assert "Write Research Brief" in steps, "Should have formatted node name"

    # Verify final content is extracted
    content_chunks = [p for p in parsed if p.get("type") == "content"]
    assert len(content_chunks) == 1, "Should have exactly one final content chunk"
    assert "Costco" in content_chunks[0]["content"], "Should contain final report"
    assert len(content_chunks[0]["content"]) > 100, "Final report should be substantial"


@pytest.mark.asyncio
async def test_streaming_handles_rapid_node_execution():
    """Test that streaming correctly handles nodes that complete quickly."""
    from unittest.mock import MagicMock, patch

    from clients.agent_client import AgentClient

    client = AgentClient()

    # Simulate multiple nodes completing rapidly
    mock_events = [
        {"type": "task", "payload": {"name": "node1", "input": {}}},
        {"type": "task_result", "payload": {"name": "node1", "result": {}}},
        {"type": "task", "payload": {"name": "node2", "input": {}}},
        {"type": "task_result", "payload": {"name": "node2", "result": {}}},
        {"type": "task", "payload": {"name": "node3", "input": {}}},
        {"type": "task_result", "payload": {"name": "node3", "result": {}}},
    ]

    mock_agent = MagicMock()

    async def mock_astream(*args, **kwargs):
        for event in mock_events:
            yield event

    mock_agent.astream = mock_astream

    with patch("services.agent_registry.get_agent", return_value=mock_agent):
        client._agent_cache["test"] = {"agent_name": "test", "is_cloud": False}

        chunks = []
        async for chunk in client.stream("test", "test query", {}):
            chunks.append(chunk)

    # Should yield 6 chunks (3 started + 3 completed)
    assert len(chunks) == 6

    parsed = [json.loads(c.strip()) for c in chunks]

    # Verify order: node1 start, node1 end, node2 start, node2 end, node3 start, node3 end
    expected_sequence = [
        ("node1", "started"),
        ("node1", "completed"),
        ("node2", "started"),
        ("node2", "completed"),
        ("node3", "started"),
        ("node3", "completed"),
    ]

    actual_sequence = [(p["step"], p["phase"]) for p in parsed]
    assert actual_sequence == expected_sequence, f"Expected {expected_sequence}, got {actual_sequence}"

    # Verify all completed chunks have durations
    completed_chunks = [p for p in parsed if p["phase"] == "completed"]
    assert all("duration" in c for c in completed_chunks), "All completed chunks should have duration"


@pytest.mark.asyncio
async def test_streaming_formats_node_names_consistently():
    """Test that node names are consistently formatted for display."""
    from unittest.mock import MagicMock, patch

    from clients.agent_client import AgentClient

    client = AgentClient()

    mock_events = [
        {"type": "task", "payload": {"name": "write_research_brief", "input": {}}},
        {"type": "task_result", "payload": {"name": "write_research_brief", "result": {}}},
        {"type": "task", "payload": {"name": "validate_research_brief", "input": {}}},
        {"type": "task_result", "payload": {"name": "validate_research_brief", "result": {}}},
    ]

    mock_agent = MagicMock()

    async def mock_astream(*args, **kwargs):
        for event in mock_events:
            yield event

    mock_agent.astream = mock_astream

    with patch("services.agent_registry.get_agent", return_value=mock_agent):
        client._agent_cache["test"] = {"agent_name": "test", "is_cloud": False}

        chunks = []
        async for chunk in client.stream("test", "test query", {}):
            chunks.append(chunk)

    parsed = [json.loads(c.strip()) for c in chunks]
    messages = [p["message"] for p in parsed]

    # Verify formatting: snake_case → Title Case
    assert "Write Research Brief" in messages, "Should format write_research_brief"
    assert "Validate Research Brief" in messages, "Should format validate_research_brief"

    # Verify no snake_case in output
    assert all("_" not in msg for msg in messages), "Should not have underscores in formatted names"
