"""Unit tests for MeddicAgent helper methods.

Tests the refactored helper methods extracted from the giant run() method.
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock

# Set required environment variables for tests
os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-test-token")
os.environ.setdefault("SLACK_APP_TOKEN", "xapp-test-token")
os.environ.setdefault("LLM_API_KEY", "test-api-key")

from agents.meddic_agent import MeddicAgent


class TestMeddicAgentHelpers:
    """Test suite for MeddicAgent helper methods."""

    @pytest.fixture
    def agent(self):
        """Create MeddicAgent instance."""
        return MeddicAgent()

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        return {
            "user_id": "U123",
            "channel": "C123",
            "thread_ts": "1234.56",
            "thinking_ts": "1234.57",
            "slack_service": AsyncMock(),
        }

    # Tests for _get_services_from_context
    def test_get_services_from_context(self, agent, mock_context):
        """Test service extraction from context."""
        # Act
        slack_service, channel, thread_ts = agent._get_services_from_context(
            mock_context
        )

        # Assert
        assert slack_service == mock_context["slack_service"]
        assert channel == "C123"
        assert thread_ts == "1234.56"

    # Tests for _setup_progress_message
    @pytest.mark.asyncio
    async def test_setup_progress_message_success(self, agent):
        """Test progress message setup."""
        # Arrange
        mock_slack = AsyncMock()
        mock_slack.send_message.return_value = {"ts": "1234.58"}

        # Act
        result = await agent._setup_progress_message(
            mock_slack, "C123", "1234.56", "1234.57"
        )

        # Assert
        assert result == "1234.58"
        mock_slack.delete_thinking_indicator.assert_called_once()

    @pytest.mark.asyncio
    async def test_setup_progress_message_no_service(self, agent):
        """Test progress message without Slack service."""
        # Act
        result = await agent._setup_progress_message(None, "C123", None, None)

        # Assert
        assert result is None

    # Tests for _generate_thread_id
    def test_generate_thread_id_with_thread_ts(self, agent):
        """Test thread ID generation with existing thread_ts."""
        # Act
        thread_id = agent._generate_thread_id("1234.56", "U123")

        # Assert
        assert thread_id == "1234.56"

    def test_generate_thread_id_without_thread_ts(self, agent):
        """Test thread ID generation without thread_ts."""
        # Act
        thread_id = agent._generate_thread_id(None, "U123")

        # Assert
        assert thread_id.startswith("meddic_U123_")

    # Tests for _get_node_messages
    def test_get_node_messages(self, agent):
        """Test node messages configuration."""
        # Act
        messages = agent._get_node_messages()

        # Assert
        assert "parse_notes" in messages
        assert "meddpicc_analysis" in messages
        assert "coaching_insights" in messages
        assert "followup_handler" in messages

    # Tests for _get_node_order
    def test_get_node_order(self, agent):
        """Test node execution order."""
        # Act
        order = agent._get_node_order()

        # Assert
        assert len(order) == 3
        assert order[0] == "parse_notes"
        assert order[-1] == "coaching_insights"

    # Tests for _extract_final_result
    def test_extract_final_result_dict(self, agent):
        """Test final result extraction from dict."""
        # Arrange
        result = {"node_name": {"final_response": "Analysis complete"}}

        # Act
        extracted = agent._extract_final_result(result)

        # Assert
        assert isinstance(extracted, dict)
        assert "final_response" in extracted

    def test_extract_final_result_invalid(self, agent):
        """Test final result extraction with invalid type."""
        # Act
        extracted = agent._extract_final_result("invalid")

        # Assert
        assert extracted == {}

    # Tests for _handle_question_mode
    def test_handle_question_mode_active(self, agent):
        """Test Q&A mode handling."""
        # Arrange
        result = {"question_mode": True, "final_response": "What's the budget?"}

        # Act
        response = agent._handle_question_mode(result)

        # Assert
        assert response is not None
        assert response["response"] == "What's the budget?"
        assert response["metadata"]["question_mode"] is True

    def test_handle_question_mode_inactive(self, agent):
        """Test Q&A mode when not active."""
        # Arrange
        result = {"question_mode": False, "final_response": "Analysis"}

        # Act
        response = agent._handle_question_mode(result)

        # Assert
        assert response is None

    # Tests for _handle_clarification_needed
    def test_handle_clarification_needed_present(self, agent):
        """Test clarification handling when needed."""
        # Arrange
        result = {"clarification_message": "Please provide more details"}

        # Act
        response = agent._handle_clarification_needed(result)

        # Assert
        assert response is not None
        assert "MEDDPICC" in response["response"]
        assert response["metadata"]["needs_clarification"] is True

    def test_handle_clarification_needed_absent(self, agent):
        """Test clarification handling when not needed."""
        # Arrange
        result = {"final_response": "Analysis complete"}

        # Act
        response = agent._handle_clarification_needed(result)

        # Assert
        assert response is None

    # Tests for _format_final_response
    def test_format_final_response_with_followup(self, agent, mock_context):
        """Test final response formatting with followup mode."""
        # Arrange
        result = {
            "final_response": "**MEDDPICC Analysis**\nMetrics: 20% cost savings",
            "sources": [],
            "followup_mode": True,
        }

        # Act
        response = agent._format_final_response(result, "query", "thread123", mock_context)

        # Assert
        assert response["response"].endswith(
            "_💬 Ask me follow-up questions or type 'done' to exit._"
        )
        assert "clear_thread_tracking" not in response["metadata"]

    def test_format_final_response_exiting_followup(self, agent, mock_context):
        """Test final response formatting when exiting followup."""
        # Arrange
        result = {
            "final_response": "Analysis complete",
            "sources": [],
            "followup_mode": False,
        }

        # Act
        response = agent._format_final_response(result, "query", "thread123", mock_context)

        # Assert
        assert response["response"].endswith("_✅ Feel free to ask me anything!_")
        assert response["metadata"]["clear_thread_tracking"] is True

    def test_format_final_response_no_response(self, agent, mock_context):
        """Test final response with missing content."""
        # Arrange
        result = {"sources": []}

        # Act
        response = agent._format_final_response(result, "query", "thread123", mock_context)

        # Assert
        assert "Unable to generate" in response["response"]
        assert "error" in response["metadata"]
