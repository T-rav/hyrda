"""Tests for executive summary prioritization in agent streaming."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_agent_client_prioritizes_executive_summary():
    """Test that agent_client yields executive_summary instead of full report."""
    from clients.agent_client import AgentClient

    client = AgentClient()

    # Mock LangGraph debug event with both executive_summary and final_report
    mock_events = [
        {
            "type": "task",
            "payload": {"name": "final_report_generation", "input": {}},
        },
        {
            "type": "task_result",
            "payload": {
                "name": "final_report_generation",
                "result": {
                    "executive_summary": "📊 *Executive Summary*\n\n• Key point 1\n• Key point 2\n• Key point 3\n\n📄 [View Full Report](https://minio/report.md)",
                    "final_report": "# Full 14,000 Character Report\n\n" + "x" * 14000,
                    "report_url": "https://minio/report.md",
                },
            },
        },
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

    # Should yield 3 chunks: started, completed, content
    assert len(chunks) == 3

    parsed = [json.loads(c.strip()) for c in chunks]

    # Third chunk should be content with executive_summary (NOT full report)
    content_chunk = parsed[2]
    assert content_chunk["type"] == "content"
    assert "Executive Summary" in content_chunk["content"]
    assert "Key point 1" in content_chunk["content"]
    assert "[View Full Report]" in content_chunk["content"]

    # Should NOT contain the full 14k report
    assert len(content_chunk["content"]) < 1000  # Summary is concise
    assert "x" * 100 not in content_chunk["content"]  # Not the full report


@pytest.mark.asyncio
async def test_agent_client_falls_back_to_final_report():
    """Test that agent_client falls back to final_report if no executive_summary."""
    from clients.agent_client import AgentClient

    client = AgentClient()

    # Mock event with ONLY final_report (no executive_summary)
    mock_events = [
        {
            "type": "task_result",
            "payload": {
                "name": "some_node",
                "result": {
                    "final_report": "# Full Report Content Here\n\nThis is a comprehensive report with substantial content that exceeds 50 characters.",
                },
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

    # Should fall back to final_report
    assert len(chunks) >= 1
    parsed = [json.loads(c.strip()) for c in chunks]
    content_chunks = [p for p in parsed if p.get("type") == "content"]

    assert len(content_chunks) == 1
    assert "Full Report Content" in content_chunks[0]["content"]


@pytest.mark.asyncio
async def test_agent_client_checks_summary_before_response():
    """Test priority order: executive_summary > response > output > final_report."""
    from clients.agent_client import AgentClient

    client = AgentClient()

    # Mock event with all possible content types
    mock_events = [
        {
            "type": "task_result",
            "payload": {
                "name": "test_node",
                "result": {
                    "executive_summary": "📊 Executive Summary (should be picked first)\n\nThis summary contains the key findings and recommendations with sufficient length.",
                    "response": "Response content that is also sufficiently long to exceed the 50 character minimum threshold",
                    "output": "Output content that is also sufficiently long to exceed the 50 character minimum threshold",
                    "final_report": "Full report content with comprehensive details that exceed the 50 character minimum threshold",
                },
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

    parsed = [json.loads(c.strip()) for c in chunks]
    content_chunks = [p for p in parsed if p.get("type") == "content"]

    # Should pick executive_summary (highest priority)
    assert len(content_chunks) == 1
    assert "should be picked first" in content_chunks[0]["content"]
    assert "Response content" not in content_chunks[0]["content"]


@pytest.mark.asyncio
async def test_final_report_node_returns_summary_with_url():
    """Test that final_report node returns executive_summary with S3 URL."""
    from external_agents.profile.nodes.final_report import final_report_generation
    from external_agents.profile.state import ProfileAgentState

    # Mock state
    state = ProfileAgentState(
        query="profile costco",
        notes=[
            "Research note 1 about Costco...",
            "Research note 2 about technology...",
        ],
        profile_type="company",
    )

    # Mock config
    mock_config = {"configurable": {"final_report_model": "gpt-4o"}}

    # Mock LLM, S3 upload, and PromptService
    with (
        patch("external_agents.profile.nodes.final_report.upload_report_to_s3") as mock_upload,
        patch("external_agents.profile.nodes.final_report.get_prompt_service") as mock_prompt_service,
        patch("langchain_openai.ChatOpenAI") as mock_llm,
    ):
        mock_upload.return_value = "https://minio/profile-reports/costco_report.md"

        # Mock PromptService
        mock_prompt = MagicMock()
        mock_prompt.get_custom_prompt.return_value = MagicMock(
            format=lambda **kwargs: "Generate a company profile report."
        )
        mock_prompt_service.return_value = mock_prompt

        # Mock LLM to return a simple report
        mock_llm_instance = MagicMock()
        mock_llm_instance.ainvoke = AsyncMock(
            return_value=MagicMock(
                content="# Company Profile: Costco\n\nFull report content here with substantial details..."
            )
        )
        mock_llm.return_value = mock_llm_instance

        result = await final_report_generation(state, mock_config)

    # Should return executive_summary with S3 link
    assert "executive_summary" in result
    assert "report_url" in result

    summary = result["executive_summary"]
    # Should contain either a proper summary or the report content with footer
    assert any(x in summary for x in ["Executive Summary", "Key point", "•", "Company Profile", "follow-up questions"])
    assert "[View Full Report](https://minio" in summary
    assert result["report_url"] == "https://minio/profile-reports/costco_report.md"

    # S3 upload should have been called
    mock_upload.assert_called_once()
