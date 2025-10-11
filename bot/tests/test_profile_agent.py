"""Tests for ProfileAgent."""

import os
import sys
from unittest.mock import AsyncMock, Mock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.profile_agent import ProfileAgent
from services.llm_service import LLMService
from services.slack_service import SlackService
from tests.agent_test_utils import AgentContextBuilder


class TestProfileAgent:
    """Tests for ProfileAgent"""

    @pytest.mark.asyncio
    async def test_profile_agent_run(self):
        """Test ProfileAgent execution"""
        # Mock LLM service for profile agent's LangGraph execution
        llm_service = Mock(spec=LLMService)
        llm_service.get_response = AsyncMock(
            return_value="Please provide more details about what you'd like to know."
        )

        # Mock Slack service
        slack_service = Mock(spec=SlackService)
        slack_service.send_message = AsyncMock(return_value={"ts": "123.456"})
        slack_service.update_message = AsyncMock()
        slack_service.upload_file = AsyncMock(return_value={"ok": True})

        context = (
            AgentContextBuilder()
            .with_llm_service(llm_service)
            .with_slack_service(slack_service)
            .build()
        )

        # Mock LangChain ChatOpenAI to prevent real API calls
        # Create a bound LLM mock that will be returned by bind_tools
        mock_bound_llm = Mock()

        # Supervisor response with ResearchComplete to short-circuit the workflow
        mock_supervisor_response = Mock()
        mock_supervisor_response.content = "Research complete."
        mock_supervisor_response.tool_calls = [
            {
                "name": "ResearchComplete",
                "args": {"research_summary": "Charlotte investigation complete"},
                "id": "tc_1",
            }
        ]

        mock_bound_llm.ainvoke = AsyncMock(return_value=mock_supervisor_response)

        mock_final_report = Mock()
        mock_final_report.content = "# Employee Profile\n\nCharlotte is an employee with expertise in software development."

        with patch("langchain_openai.ChatOpenAI") as mock_chat:
            # Mock LLM with bind_tools that returns the bound LLM
            mock_llm = Mock()
            mock_llm.bind_tools = Mock(return_value=mock_bound_llm)
            mock_llm.ainvoke = AsyncMock(return_value=mock_final_report)
            mock_chat.return_value = mock_llm

            agent = ProfileAgent()
            result = await agent.run("tell me about Charlotte", context)

        assert "response" in result
        assert "metadata" in result
        # Profile agent now returns empty response when PDF is uploaded successfully
        # The actual content is in the PDF file uploaded to Slack
        assert (
            result["response"] == ""
            or "Profile" in result["response"]
            or "No research findings" in result["response"]
        )
        # Check metadata shows it's from profile agent
        assert result["metadata"]["agent"] == "profile"
        # Verify PDF was uploaded
        slack_service.upload_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_profile_agent_invalid_context(self):
        """Test ProfileAgent with invalid context"""
        agent = ProfileAgent()
        context = AgentContextBuilder.invalid_missing_channel()

        result = await agent.run("test query", context)

        assert "response" in result
        assert "error" in result["metadata"]
