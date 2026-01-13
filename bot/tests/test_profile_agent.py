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


def create_mock_aget_state(state_values):
    """Helper to create mock aget_state function.

    Args:
        state_values: Dict of state values to return

    Returns:
        Async mock function that returns a state snapshot

    """

    async def mock_aget_state(config):
        """Mock aget_state to return final state from checkpointer"""
        from unittest.mock import Mock as StateMock

        state_snapshot = StateMock()
        state_snapshot.values = state_values
        return state_snapshot

    return mock_aget_state


class TestProfileAgent:
    """Tests for ProfileAgent"""

    @pytest.mark.asyncio
    async def test_profile_agent_sets_thread_type(self):
        """Test that ProfileAgent sets thread_type='profile' after generating report"""
        # This test verifies the caching logic directly without running the full graph
        # Import the actual ProfileAgent to test the real caching code
        from unittest.mock import patch

        # Mock conversation cache
        mock_conversation_cache = AsyncMock()
        mock_conversation_cache.store_document_content = AsyncMock()
        mock_conversation_cache.set_thread_type = AsyncMock()

        # Mock Slack service
        slack_service = Mock(spec=SlackService)
        slack_service.upload_file = AsyncMock(
            return_value={"ok": True, "file": {"id": "F123"}}
        )

        # Mock LLM service
        llm_service = Mock(spec=LLMService)

        # Create profile agent
        agent = ProfileAgent()

        # Create minimal context with conversation_cache
        context = {
            "thread_ts": "1234.5678",
            "conversation_cache": mock_conversation_cache,
            "slack_service": slack_service,
            "llm_service": llm_service,
            "channel": "C123",
            "user_id": "U123",
        }

        # Mock the graph execution to return a completed state
        with patch.object(agent, "graph") as mock_graph:
            final_report = "# Company Profile\n\nThis is a test profile."
            mock_state = {
                "final_report": final_report,
                "notes": ["Note 1", "Note 2"],
                "executive_summary": "Executive summary text",
            }

            # Mock both ainvoke and aget_state
            mock_graph.ainvoke = AsyncMock(return_value=mock_state)
            mock_graph.aget_state = create_mock_aget_state(mock_state)

            # Execute agent
            result = await agent.run("Profile Acme Corporation", context)

            # Debug: Print what was called
            print(
                f"store_document_content called: {mock_conversation_cache.store_document_content.called}"
            )
            print(
                f"set_thread_type called: {mock_conversation_cache.set_thread_type.called}"
            )
            print(f"Result metadata: {result.get('metadata', {})}")

            # Verify conversation cache methods were called
            assert mock_conversation_cache.store_document_content.called, (
                "store_document_content was not called"
            )
            assert mock_conversation_cache.set_thread_type.called, (
                "set_thread_type was not called"
            )

            # Verify the thread_type was set to 'profile'
            set_thread_type_calls = (
                mock_conversation_cache.set_thread_type.call_args_list
            )
            assert len(set_thread_type_calls) > 0, "set_thread_type was not called"
            assert set_thread_type_calls[0][0] == ("1234.5678", "profile"), (
                f"Expected set_thread_type('1234.5678', 'profile'), got {set_thread_type_calls[0]}"
            )

            # Verify metadata indicates thread tracking should be cleared
            assert result["metadata"]["clear_thread_tracking"] is True

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

        # Create mock graph that returns proper state
        async def mock_astream(input_state, config):
            """Mock graph astream to return final state"""
            # Yield intermediate events (simulate nodes completing)
            yield {"clarify_with_user": {}}
            yield {"write_research_brief": {}}
            yield {"research_supervisor": {}}
            yield {"quality_control": {}}
            # Final event with complete state
            yield {
                "final_report_generation": {
                    "final_report": "# Employee Profile\n\nCharlotte is an employee with expertise in software development.",
                    "executive_summary": "Charlotte is a software developer with 5 years of experience.",
                    "notes": ["Note 1: Background", "Note 2: Experience"],
                }
            }

        # Mock the profile_researcher graph at module level
        mock_graph = Mock()
        mock_graph.astream = mock_astream
        mock_graph.aget_state = create_mock_aget_state(
            {
                "final_report": "# Employee Profile\n\nCharlotte is an employee with expertise in software development.",
                "executive_summary": "Charlotte is a software developer with 5 years of experience.",
                "notes": ["Note 1: Background", "Note 2: Experience"],
            }
        )

        with patch("agents.profile_agent.profile_researcher", mock_graph):
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
    async def test_profile_agent_executive_summary_formatting(self):
        """Test that executive summary has proper Slack bold formatting for heading"""
        # Mock LLM service
        llm_service = Mock(spec=LLMService)
        llm_service.get_response = AsyncMock(return_value="Mock response")

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

        # Mock executive summary with proper Slack formatting
        executive_summary_content = (
            "📊 *Executive Summary*\n\n"
            "• First key point about the company\n"
            "• Second key point about strategy\n"
            "• Third key point about opportunities\n\n"
            "📎 _Full detailed report attached as PDF_"
        )

        # Create mock graph that returns proper state
        async def mock_astream(input_state, config):
            """Mock graph astream to return final state with executive summary"""
            # Yield intermediate events (simulate nodes completing)
            yield {"clarify_with_user": {}}
            yield {"write_research_brief": {}}
            yield {"research_supervisor": {}}
            yield {"quality_control": {}}
            # Final event with complete state in final_report_generation
            yield {
                "final_report_generation": {
                    "final_report": "# Company Profile\n\nFull report content here.",
                    "executive_summary": executive_summary_content,
                    "notes": ["Note 1", "Note 2"],
                }
            }

        # Mock the profile_researcher graph at module level
        mock_graph = Mock()
        mock_graph.astream = mock_astream
        mock_graph.aget_state = create_mock_aget_state(
            {
                "final_report": "# Company Profile\n\nFull report content here.",
                "executive_summary": executive_summary_content,
                "notes": ["Note 1", "Note 2"],
            }
        )

        # Patch the profile_researcher at module level
        with patch("agents.profile_agent.profile_researcher", mock_graph):
            agent = ProfileAgent()
            await agent.run("tell me about Acme Corp", context)

        # Verify PDF was uploaded with executive summary as initial comment
        slack_service.upload_file.assert_called_once()
        upload_call_kwargs = slack_service.upload_file.call_args.kwargs

        # Check that initial_comment contains the executive summary
        assert "initial_comment" in upload_call_kwargs
        initial_comment = upload_call_kwargs["initial_comment"]

        # Verify bold formatting for "Executive Summary"
        assert "*Executive Summary*" in initial_comment, (
            f"Expected bold Executive Summary in: {initial_comment}"
        )
        # Verify emoji formatting
        assert "📊" in initial_comment, f"Expected 📊 emoji in: {initial_comment}"
        assert "📎" in initial_comment, f"Expected 📎 emoji in: {initial_comment}"
        # Verify it has bullet points
        assert "•" in initial_comment, f"Expected bullet points in: {initial_comment}"

    @pytest.mark.asyncio
    async def test_profile_agent_invalid_context(self):
        """Test ProfileAgent with invalid context"""
        agent = ProfileAgent()
        context = AgentContextBuilder.invalid_missing_channel()

        result = await agent.run("test query", context)

        assert "response" in result
        assert "error" in result["metadata"]

    @pytest.mark.asyncio
    async def test_profile_agent_handles_none_state_from_langgraph(self):
        """Test ProfileAgent handles None state from LangGraph quality control edge case.

        This tests the bug fix for when quality_control passes on first try and
        returns Command(goto="__end__", update={}), which can cause LangGraph to
        wrap the final state as {"__end__": None} or {"quality_control": None}.

        Bug: 'NoneType' object has no attribute 'get'
        Fix: Added defensive null checks in state extraction (commits 53ece28, 191f6c4)
        """
        # Mock LLM service
        llm_service = Mock(spec=LLMService)
        llm_service.get_response = AsyncMock(return_value="Mock response")

        # Mock Slack service
        slack_service = Mock(spec=SlackService)
        slack_service.send_message = AsyncMock(return_value={"ts": "123.456"})
        slack_service.update_message = AsyncMock()
        slack_service.upload_file = AsyncMock(
            return_value=None
        )  # Simulate upload failure

        context = (
            AgentContextBuilder()
            .with_llm_service(llm_service)
            .with_slack_service(slack_service)
            .build()
        )

        # Create mock graph that returns None state (simulates the bug)
        async def mock_astream_with_none(input_state, config):
            """Mock graph astream that returns None state (edge case from quality_control)"""
            # Yield intermediate events
            yield {"clarify_with_user": {}}
            yield {"write_research_brief": {}}
            yield {"research_supervisor": {}}
            # Quality control passes and routes to __end__, returning None state
            yield {"quality_control": None}  # This causes the bug!

        # Mock the profile_researcher graph
        mock_graph = Mock()
        mock_graph.astream = mock_astream_with_none
        mock_graph.aget_state = create_mock_aget_state({})  # Empty state!

        with patch("agents.profile_agent.profile_researcher", mock_graph):
            agent = ProfileAgent()
            result = await agent.run("tell me about Tesla", context)

        # Should NOT crash with 'NoneType' object has no attribute 'get'
        assert "response" in result
        assert "metadata" in result
        # Should return "no report available" error message
        assert "Unable to generate profile report" in result["response"]
        assert result["metadata"]["error"] == "no_report"

    @pytest.mark.asyncio
    async def test_profile_agent_handles_empty_values_from_langgraph(self):
        """Test ProfileAgent handles empty dict values from LangGraph.

        This tests another edge case where LangGraph returns {"__end__": {}}
        (empty dict instead of None).
        """
        # Mock LLM service
        llm_service = Mock(spec=LLMService)
        llm_service.get_response = AsyncMock(return_value="Mock response")

        # Mock Slack service
        slack_service = Mock(spec=SlackService)
        slack_service.send_message = AsyncMock(return_value={"ts": "123.456"})
        slack_service.update_message = AsyncMock()
        slack_service.upload_file = AsyncMock(return_value=None)

        context = (
            AgentContextBuilder()
            .with_llm_service(llm_service)
            .with_slack_service(slack_service)
            .build()
        )

        # Create mock graph that returns empty state dict
        async def mock_astream_with_empty_dict(input_state, config):
            """Mock graph astream that returns empty state dict"""
            yield {"clarify_with_user": {}}
            yield {"write_research_brief": {}}
            yield {"research_supervisor": {}}
            # Quality control returns empty dict
            yield {"quality_control": {}}  # Empty state!

        # Mock the profile_researcher graph
        mock_graph = Mock()
        mock_graph.astream = mock_astream_with_empty_dict
        mock_graph.aget_state = create_mock_aget_state({})  # Empty state!

        with patch("agents.profile_agent.profile_researcher", mock_graph):
            agent = ProfileAgent()
            result = await agent.run("tell me about SpaceX", context)

        # Should handle gracefully
        assert "response" in result
        assert "metadata" in result
        # Should return "no report available" since final_report is empty
        assert "Unable to generate profile report" in result["response"]
        assert result["metadata"]["error"] == "no_report"

    @pytest.mark.asyncio
    async def test_profile_agent_quality_control_passes_with_state(self):
        """Test ProfileAgent when quality_control passes and returns state correctly.

        This tests the FIX where quality_control returns:
          Command(goto="__end__", update=state)

        Instead of the broken:
          Command(goto="__end__", update={})

        When QC passes with state, the final event should contain the full report.
        """
        # Mock LLM service
        llm_service = Mock(spec=LLMService)
        llm_service.get_response = AsyncMock(return_value="Mock response")

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

        # Create mock graph that simulates quality_control passing WITH state
        async def mock_astream_qc_passes_with_state(input_state, config):
            """Mock graph where quality_control passes and returns full state"""
            # Yield intermediate events
            yield {"clarify_with_user": {}}
            yield {"write_research_brief": {}}
            yield {"research_supervisor": {}}
            yield {
                "final_report_generation": {
                    "final_report": "# Tesla Profile\n\nTesla is an electric vehicle company...\n\n## Sources\n1. tesla.com\n2. sec.gov",
                    "executive_summary": "📊 *Executive Summary*\n\n• Tesla leads EV market\n• Strong growth trajectory\n• Innovation focus",
                    "notes": ["Note 1", "Note 2", "Note 3"],
                }
            }
            # Quality control passes and returns the FULL STATE (the fix!)
            yield {
                "quality_control": {
                    "final_report": "# Tesla Profile\n\nTesla is an electric vehicle company...\n\n## Sources\n1. tesla.com\n2. sec.gov",
                    "executive_summary": "📊 *Executive Summary*\n\n• Tesla leads EV market\n• Strong growth trajectory\n• Innovation focus",
                    "notes": ["Note 1", "Note 2", "Note 3"],
                }
            }

        # Mock the profile_researcher graph
        mock_graph = Mock()
        mock_graph.astream = mock_astream_qc_passes_with_state
        mock_graph.aget_state = create_mock_aget_state(
            {
                "final_report": "# Tesla Profile\n\nTesla is an electric vehicle company...\n\n## Sources\n1. tesla.com\n2. sec.gov",
                "executive_summary": "📊 *Executive Summary*\n\n• Tesla leads EV market\n• Strong growth trajectory\n• Innovation focus",
                "notes": ["Note 1", "Note 2", "Note 3"],
            }
        )

        with patch("agents.profile_agent.profile_researcher", mock_graph):
            agent = ProfileAgent()
            result = await agent.run("tell me about Tesla", context)

        # Should succeed with the report!
        assert "response" in result
        assert "metadata" in result
        # PDF uploaded successfully, so response is empty
        assert result["response"] == ""
        # Metadata should show success
        assert result["metadata"]["agent"] == "profile"
        assert result["metadata"]["report_length"] > 0
        assert result["metadata"]["pdf_generated"] is True
        assert result["metadata"]["pdf_uploaded"] is True
        # Verify PDF was uploaded
        slack_service.upload_file.assert_called_once()
