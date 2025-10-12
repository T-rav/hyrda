"""Tests for ProfileAgent error handling and edge cases."""

import os
import sys
from unittest.mock import AsyncMock, Mock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.profile_agent import ProfileAgent
from services.llm_service import LLMService
from services.slack_service import SlackService
from tests.agent_test_utils import AgentContextBuilder


class TestProfileAgentErrorHandling:
    """Tests for ProfileAgent error handling"""

    @pytest.mark.asyncio
    async def test_missing_llm_service(self):
        """Test profile agent without LLM service"""
        context = (
            AgentContextBuilder()
            .with_llm_service(None)  # No LLM service
            .with_slack_service(Mock())
            .build()
        )

        agent = ProfileAgent()
        result = await agent.run("Tell me about Tesla", context)

        assert "response" in result
        assert "LLM service not available" in result["response"]
        assert "error" in result["metadata"]

    @pytest.mark.asyncio
    async def test_empty_query(self):
        """Test profile agent with empty query"""
        llm_service = Mock(spec=LLMService)
        slack_service = Mock(spec=SlackService)
        slack_service.send_message = AsyncMock(return_value={"ts": "123.456"})
        slack_service.delete_thinking_indicator = AsyncMock()

        context = (
            AgentContextBuilder()
            .with_llm_service(llm_service)
            .with_slack_service(slack_service)
            .build()
        )

        # Mock graph to handle empty query
        async def mock_astream(input_state, config):
            yield {
                "final_report_generation": {
                    "final_report": "Unable to process empty query",
                    "executive_summary": "",
                    "notes": [],
                }
            }

        mock_graph = Mock()
        mock_graph.astream = mock_astream

        with patch("agents.profile_agent.profile_researcher", mock_graph):
            agent = ProfileAgent()
            result = await agent.run("", context)

        assert "response" in result
        assert "metadata" in result

    @pytest.mark.asyncio
    async def test_very_long_query(self):
        """Test profile agent with very long query"""
        llm_service = Mock(spec=LLMService)
        slack_service = Mock(spec=SlackService)
        slack_service.send_message = AsyncMock(return_value={"ts": "123.456"})
        slack_service.delete_thinking_indicator = AsyncMock()
        slack_service.update_message = AsyncMock()
        slack_service.upload_file = AsyncMock(return_value={"ok": True})

        context = (
            AgentContextBuilder()
            .with_llm_service(llm_service)
            .with_slack_service(slack_service)
            .build()
        )

        # Very long query
        long_query = "Tell me about " + "A" * 10000

        async def mock_astream(input_state, config):
            yield {
                "final_report_generation": {
                    "final_report": "# Profile Report\n\nProcessed long query",
                    "executive_summary": "📊 *Executive Summary*\n\n• Summary",
                    "notes": ["Note"],
                }
            }

        mock_graph = Mock()
        mock_graph.astream = mock_astream

        with patch("agents.profile_agent.profile_researcher", mock_graph):
            agent = ProfileAgent()
            result = await agent.run(long_query, context)

        assert "response" in result
        # Should handle long query gracefully

    @pytest.mark.asyncio
    async def test_graph_execution_exception(self):
        """Test handling graph execution exceptions"""
        llm_service = Mock(spec=LLMService)
        slack_service = Mock(spec=SlackService)
        slack_service.send_message = AsyncMock(return_value={"ts": "123.456"})
        slack_service.delete_thinking_indicator = AsyncMock()

        context = (
            AgentContextBuilder()
            .with_llm_service(llm_service)
            .with_slack_service(slack_service)
            .build()
        )

        # Mock graph that raises exception
        async def mock_astream_error(input_state, config):
            raise Exception("Graph execution failed")
            yield  # Make it a generator

        mock_graph = Mock()
        mock_graph.astream = mock_astream_error

        with patch("agents.profile_agent.profile_researcher", mock_graph):
            agent = ProfileAgent()
            result = await agent.run("Test query", context)

        assert "response" in result
        assert "error" in result["response"].lower()
        assert "metadata" in result
        assert "error" in result["metadata"]

    @pytest.mark.asyncio
    async def test_no_final_report_generated(self):
        """Test when graph produces no final report"""
        llm_service = Mock(spec=LLMService)
        slack_service = Mock(spec=SlackService)
        slack_service.send_message = AsyncMock(return_value={"ts": "123.456"})
        slack_service.delete_thinking_indicator = AsyncMock()
        slack_service.update_message = AsyncMock()

        context = (
            AgentContextBuilder()
            .with_llm_service(llm_service)
            .with_slack_service(slack_service)
            .build()
        )

        # Mock graph that returns empty result
        async def mock_astream(input_state, config):
            yield {
                "final_report_generation": {
                    "final_report": "",  # Empty report
                    "executive_summary": "",
                    "notes": [],
                }
            }

        mock_graph = Mock()
        mock_graph.astream = mock_astream

        with patch("agents.profile_agent.profile_researcher", mock_graph):
            agent = ProfileAgent()
            result = await agent.run("Test", context)

        assert "response" in result
        assert "Unable to generate profile report" in result["response"]
        assert "error" in result["metadata"]

    @pytest.mark.asyncio
    async def test_pdf_generation_failure(self):
        """Test handling PDF generation failure"""
        llm_service = Mock(spec=LLMService)
        slack_service = Mock(spec=SlackService)
        slack_service.send_message = AsyncMock(return_value={"ts": "123.456"})
        slack_service.delete_thinking_indicator = AsyncMock()
        slack_service.update_message = AsyncMock()
        slack_service.upload_file = AsyncMock(return_value={"ok": True})

        context = (
            AgentContextBuilder()
            .with_llm_service(llm_service)
            .with_slack_service(slack_service)
            .build()
        )

        async def mock_astream(input_state, config):
            yield {
                "final_report_generation": {
                    "final_report": "# Report\n\nContent",
                    "executive_summary": "Summary",
                    "notes": ["Note"],
                }
            }

        mock_graph = Mock()
        mock_graph.astream = mock_astream

        # Mock PDF generation to fail
        with (
            patch("agents.profile_agent.profile_researcher", mock_graph),
            patch(
                "agents.profile_agent.markdown_to_pdf",
                side_effect=Exception("PDF generation failed"),
            ),
        ):
            agent = ProfileAgent()
            result = await agent.run("Test", context)

        # Should handle PDF failure gracefully
        assert "response" in result
        assert "error" in result["metadata"]

    @pytest.mark.asyncio
    async def test_slack_upload_failure(self):
        """Test handling Slack file upload failure"""
        llm_service = Mock(spec=LLMService)
        slack_service = Mock(spec=SlackService)
        slack_service.send_message = AsyncMock(return_value={"ts": "123.456"})
        slack_service.delete_thinking_indicator = AsyncMock()
        slack_service.update_message = AsyncMock()
        slack_service.upload_file = AsyncMock(return_value=None)  # Upload fails

        context = (
            AgentContextBuilder()
            .with_llm_service(llm_service)
            .with_slack_service(slack_service)
            .build()
        )

        async def mock_astream(input_state, config):
            yield {
                "final_report_generation": {
                    "final_report": "# Report\n\nContent here",
                    "executive_summary": "📊 *Summary*\n\n• Point",
                    "notes": ["Note"],
                }
            }

        mock_graph = Mock()
        mock_graph.astream = mock_astream

        with patch("agents.profile_agent.profile_researcher", mock_graph):
            agent = ProfileAgent()
            result = await agent.run("Test", context)

        # Should fall back to returning text response
        assert "response" in result
        assert len(result["response"]) > 0  # Should have fallback content
        assert result["metadata"]["pdf_uploaded"] is False

    @pytest.mark.asyncio
    async def test_slack_service_unavailable(self):
        """Test when Slack service is not available"""
        llm_service = Mock(spec=LLMService)

        context = (
            AgentContextBuilder()
            .with_llm_service(llm_service)
            .with_slack_service(None)  # No Slack service
            .build()
        )

        async def mock_astream(input_state, config):
            yield {
                "final_report_generation": {
                    "final_report": "# Report\n\nContent",
                    "executive_summary": "Summary",
                    "notes": ["Note"],
                }
            }

        mock_graph = Mock()
        mock_graph.astream = mock_astream

        with patch("agents.profile_agent.profile_researcher", mock_graph):
            agent = ProfileAgent()
            result = await agent.run("Test", context)

        # Should complete without Slack interactions
        assert "response" in result
        assert "metadata" in result

    @pytest.mark.asyncio
    async def test_entity_name_extraction_failure(self):
        """Test fallback when entity name extraction fails"""
        llm_service = Mock(spec=LLMService)
        slack_service = Mock(spec=SlackService)
        slack_service.send_message = AsyncMock(return_value={"ts": "123.456"})
        slack_service.delete_thinking_indicator = AsyncMock()
        slack_service.update_message = AsyncMock()
        slack_service.upload_file = AsyncMock(return_value={"ok": True})

        context = (
            AgentContextBuilder()
            .with_llm_service(llm_service)
            .with_slack_service(slack_service)
            .build()
        )

        async def mock_astream(input_state, config):
            yield {
                "final_report_generation": {
                    "final_report": "# Report\n\nContent",
                    "executive_summary": "Summary",
                    "notes": ["Note"],
                }
            }

        mock_graph = Mock()
        mock_graph.astream = mock_astream

        # Mock entity extraction to fail
        with (
            patch("agents.profile_agent.profile_researcher", mock_graph),
            patch("langchain_openai.ChatOpenAI") as mock_chat,
        ):
            # Mock LLM for entity extraction to fail
            mock_llm = Mock()
            mock_llm.ainvoke = AsyncMock(
                side_effect=Exception("Entity extraction failed")
            )
            mock_chat.return_value = mock_llm

            agent = ProfileAgent()
            result = await agent.run("Test query", context)

        # Should use generic title as fallback
        assert "response" in result
        # PDF should still be uploaded with generic title
        slack_service.upload_file.assert_called_once()


class TestProfileAgentEdgeCases:
    """Tests for ProfileAgent edge cases"""

    @pytest.mark.asyncio
    async def test_special_characters_in_query(self):
        """Test query with special characters"""
        llm_service = Mock(spec=LLMService)
        slack_service = Mock(spec=SlackService)
        slack_service.send_message = AsyncMock(return_value={"ts": "123.456"})
        slack_service.delete_thinking_indicator = AsyncMock()
        slack_service.update_message = AsyncMock()
        slack_service.upload_file = AsyncMock(return_value={"ok": True})

        context = (
            AgentContextBuilder()
            .with_llm_service(llm_service)
            .with_slack_service(slack_service)
            .build()
        )

        special_query = "Tell me about Tesla™ & SpaceX® <Company> [2024]"

        async def mock_astream(input_state, config):
            yield {
                "final_report_generation": {
                    "final_report": "# Report\n\nContent",
                    "executive_summary": "Summary",
                    "notes": ["Note"],
                }
            }

        mock_graph = Mock()
        mock_graph.astream = mock_astream

        with patch("agents.profile_agent.profile_researcher", mock_graph):
            agent = ProfileAgent()
            result = await agent.run(special_query, context)

        assert "response" in result
        assert "metadata" in result

    @pytest.mark.asyncio
    async def test_unicode_in_query(self):
        """Test query with unicode characters"""
        llm_service = Mock(spec=LLMService)
        slack_service = Mock(spec=SlackService)
        slack_service.send_message = AsyncMock(return_value={"ts": "123.456"})
        slack_service.delete_thinking_indicator = AsyncMock()
        slack_service.update_message = AsyncMock()
        slack_service.upload_file = AsyncMock(return_value={"ok": True})

        context = (
            AgentContextBuilder()
            .with_llm_service(llm_service)
            .with_slack_service(slack_service)
            .build()
        )

        unicode_query = "Tell me about 北京 (Beijing) 🚀"

        async def mock_astream(input_state, config):
            yield {
                "final_report_generation": {
                    "final_report": "# Report\n\nContent",
                    "executive_summary": "Summary",
                    "notes": ["Note"],
                }
            }

        mock_graph = Mock()
        mock_graph.astream = mock_astream

        with patch("agents.profile_agent.profile_researcher", mock_graph):
            agent = ProfileAgent()
            result = await agent.run(unicode_query, context)

        assert "response" in result

    @pytest.mark.asyncio
    async def test_multiple_concurrent_requests(self):
        """Test handling multiple concurrent profile requests"""
        llm_service = Mock(spec=LLMService)
        slack_service = Mock(spec=SlackService)
        slack_service.send_message = AsyncMock(return_value={"ts": "123.456"})
        slack_service.delete_thinking_indicator = AsyncMock()
        slack_service.update_message = AsyncMock()
        slack_service.upload_file = AsyncMock(return_value={"ok": True})

        context = (
            AgentContextBuilder()
            .with_llm_service(llm_service)
            .with_slack_service(slack_service)
            .build()
        )

        async def mock_astream(input_state, config):
            yield {
                "final_report_generation": {
                    "final_report": f"# Report for {input_state['query']}\n\nContent",
                    "executive_summary": "Summary",
                    "notes": ["Note"],
                }
            }

        mock_graph = Mock()
        mock_graph.astream = mock_astream

        with patch("agents.profile_agent.profile_researcher", mock_graph):
            agent = ProfileAgent()

            # Run multiple queries concurrently
            import asyncio

            results = await asyncio.gather(
                agent.run("Tesla", context),
                agent.run("Apple", context),
                agent.run("Google", context),
            )

        # All should complete successfully
        assert len(results) == 3
        for result in results:
            assert "response" in result
            assert "metadata" in result

    @pytest.mark.asyncio
    async def test_very_long_report(self):
        """Test handling very long final report"""
        llm_service = Mock(spec=LLMService)
        slack_service = Mock(spec=SlackService)
        slack_service.send_message = AsyncMock(return_value={"ts": "123.456"})
        slack_service.delete_thinking_indicator = AsyncMock()
        slack_service.update_message = AsyncMock()
        slack_service.upload_file = AsyncMock(return_value={"ok": True})

        context = (
            AgentContextBuilder()
            .with_llm_service(llm_service)
            .with_slack_service(slack_service)
            .build()
        )

        # Generate very long report
        long_report = "# Very Long Report\n\n" + ("Content paragraph. " * 10000)

        async def mock_astream(input_state, config):
            yield {
                "final_report_generation": {
                    "final_report": long_report,
                    "executive_summary": "Summary",
                    "notes": ["Note"],
                }
            }

        mock_graph = Mock()
        mock_graph.astream = mock_astream

        with patch("agents.profile_agent.profile_researcher", mock_graph):
            agent = ProfileAgent()
            result = await agent.run("Test", context)

        # Should handle long report (PDF generation)
        assert "response" in result
        assert result["metadata"]["report_length"] == len(long_report)

    @pytest.mark.asyncio
    async def test_no_research_notes(self):
        """Test when research produces no notes"""
        llm_service = Mock(spec=LLMService)
        slack_service = Mock(spec=SlackService)
        slack_service.send_message = AsyncMock(return_value={"ts": "123.456"})
        slack_service.delete_thinking_indicator = AsyncMock()
        slack_service.update_message = AsyncMock()

        context = (
            AgentContextBuilder()
            .with_llm_service(llm_service)
            .with_slack_service(slack_service)
            .build()
        )

        async def mock_astream(input_state, config):
            yield {
                "final_report_generation": {
                    "final_report": "No data found",
                    "executive_summary": "",
                    "notes": [],  # No notes
                }
            }

        mock_graph = Mock()
        mock_graph.astream = mock_astream

        with patch("agents.profile_agent.profile_researcher", mock_graph):
            agent = ProfileAgent()
            result = await agent.run("Test", context)

        assert "response" in result
        assert result["metadata"]["research_notes"] == 0

    @pytest.mark.asyncio
    async def test_internal_deep_research_unavailable(self):
        """Test when internal deep research service is unavailable"""
        llm_service = Mock(spec=LLMService)
        slack_service = Mock(spec=SlackService)
        slack_service.send_message = AsyncMock(return_value={"ts": "123.456"})
        slack_service.delete_thinking_indicator = AsyncMock()
        slack_service.update_message = AsyncMock()
        slack_service.upload_file = AsyncMock(return_value={"ok": True})

        context = (
            AgentContextBuilder()
            .with_llm_service(llm_service)
            .with_slack_service(slack_service)
            .build()
        )

        async def mock_astream(input_state, config):
            yield {
                "final_report_generation": {
                    "final_report": "# Report\n\nContent",
                    "executive_summary": "Summary",
                    "notes": ["Note"],
                }
            }

        mock_graph = Mock()
        mock_graph.astream = mock_astream

        # Mock internal deep research to return None
        with (
            patch("agents.profile_agent.profile_researcher", mock_graph),
            patch(
                "services.internal_deep_research.get_internal_deep_research_service",
                return_value=None,
            ),
        ):
            agent = ProfileAgent()
            result = await agent.run("Test", context)

        # Should complete successfully without internal search
        assert "response" in result
        assert "metadata" in result
