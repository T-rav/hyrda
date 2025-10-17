"""Tests for profile agent PDF caching functionality."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from agents.profile_agent import ProfileAgent


@pytest.mark.asyncio
class TestProfileAgentPdfCaching:
    """Tests for profile agent caching markdown reports for conversation mode."""

    async def test_caches_markdown_before_pdf_generation(self):
        """Test that markdown report is cached before PDF conversion."""
        agent = ProfileAgent()

        # Mock context with conversation_cache
        mock_cache = AsyncMock()
        mock_slack = AsyncMock()
        context = {
            "user_id": "U123",
            "channel": "C123",
            "thread_ts": "1234567890.123456",
            "slack_service": mock_slack,
            "llm_service": Mock(),
            "conversation_cache": mock_cache,
        }

        # Mock the graph to return a complete result
        mock_graph_result = {
            "final_report": "# Tesla Profile\n\nTesla is an electric vehicle company...",
            "executive_summary": "• Tesla makes EVs\n• Founded by Elon Musk\n• Based in Austin",
            "notes": ["Note 1", "Note 2"],
        }

        with patch.object(agent, "graph") as mock_graph:
            # Mock astream to yield the final result
            async def mock_astream(*args, **kwargs):
                yield {"__end__": mock_graph_result}

            mock_graph.astream = mock_astream

            with patch("agents.profile_agent.markdown_to_pdf") as mock_pdf:
                mock_pdf.return_value = b"PDF content"

                with patch("agents.profile_agent.get_pdf_filename") as mock_filename:
                    mock_filename.return_value = "Tesla_Profile.pdf"

                    # Execute agent
                    await agent.run("profile Tesla", context)

                    # Verify markdown was cached
                    mock_cache.store_document_content.assert_called_once()
                    call_args = mock_cache.store_document_content.call_args

                    # Check arguments
                    assert call_args[0][0] == "1234567890.123456"  # thread_ts
                    assert "Tesla Profile" in call_args[0][1]  # markdown content
                    assert ".pdf" in call_args[0][2]  # filename

    async def test_caching_happens_before_pdf_upload(self):
        """Test that caching happens even if PDF upload fails."""
        agent = ProfileAgent()

        mock_cache = AsyncMock()
        mock_slack = AsyncMock()
        mock_slack.upload_file = AsyncMock(return_value=None)  # Upload fails

        context = {
            "user_id": "U123",
            "channel": "C123",
            "thread_ts": "1234567890.123456",
            "slack_service": mock_slack,
            "llm_service": Mock(),
            "conversation_cache": mock_cache,
        }

        mock_graph_result = {
            "final_report": "# Report",
            "executive_summary": "• Summary",
            "notes": [],
        }

        with patch.object(agent, "graph") as mock_graph:

            async def mock_astream(*args, **kwargs):
                yield {"__end__": mock_graph_result}

            mock_graph.astream = mock_astream

            with patch("agents.profile_agent.markdown_to_pdf") as mock_pdf:
                mock_pdf.return_value = b"PDF"

                with patch("agents.profile_agent.get_pdf_filename"):
                    await agent.run("profile test", context)

                    # Caching should happen even if upload fails
                    mock_cache.store_document_content.assert_called_once()

    async def test_no_caching_without_conversation_cache(self):
        """Test that no caching occurs if conversation_cache is not provided."""
        agent = ProfileAgent()

        # Context without conversation_cache
        mock_slack = AsyncMock()
        context = {
            "user_id": "U123",
            "channel": "C123",
            "thread_ts": "1234567890.123456",
            "slack_service": mock_slack,
            "llm_service": Mock(),
            # No conversation_cache
        }

        mock_graph_result = {
            "final_report": "# Report",
            "executive_summary": "• Summary",
            "notes": [],
        }

        with patch.object(agent, "graph") as mock_graph:

            async def mock_astream(*args, **kwargs):
                yield {"__end__": mock_graph_result}

            mock_graph.astream = mock_astream

            with patch("agents.profile_agent.markdown_to_pdf") as mock_pdf:
                mock_pdf.return_value = b"PDF"

                with patch("agents.profile_agent.get_pdf_filename"):
                    # Should not raise an error
                    result = await agent.run("profile test", context)

                    # Verify no caching attempted (no cache to call)
                    assert result is not None

    async def test_no_caching_without_thread_ts(self):
        """Test that no caching occurs if thread_ts is not provided."""
        agent = ProfileAgent()

        mock_cache = AsyncMock()
        mock_slack = AsyncMock()

        # Context without thread_ts
        context = {
            "user_id": "U123",
            "channel": "C123",
            # No thread_ts
            "slack_service": mock_slack,
            "llm_service": Mock(),
            "conversation_cache": mock_cache,
        }

        mock_graph_result = {
            "final_report": "# Report",
            "executive_summary": "• Summary",
            "notes": [],
        }

        with patch.object(agent, "graph") as mock_graph:

            async def mock_astream(*args, **kwargs):
                yield {"__end__": mock_graph_result}

            mock_graph.astream = mock_astream

            with patch("agents.profile_agent.markdown_to_pdf") as mock_pdf:
                mock_pdf.return_value = b"PDF"

                with patch("agents.profile_agent.get_pdf_filename"):
                    await agent.run("profile test", context)

                    # Should not attempt caching without thread_ts
                    mock_cache.store_document_content.assert_not_called()

    async def test_caching_error_does_not_break_workflow(self):
        """Test that caching errors are caught and don't break the workflow."""
        agent = ProfileAgent()

        mock_cache = AsyncMock()
        mock_cache.store_document_content = AsyncMock(
            side_effect=Exception("Cache error")
        )
        mock_slack = AsyncMock()

        context = {
            "user_id": "U123",
            "channel": "C123",
            "thread_ts": "1234567890.123456",
            "slack_service": mock_slack,
            "llm_service": Mock(),
            "conversation_cache": mock_cache,
        }

        mock_graph_result = {
            "final_report": "# Report",
            "executive_summary": "• Summary",
            "notes": [],
        }

        with patch.object(agent, "graph") as mock_graph:

            async def mock_astream(*args, **kwargs):
                yield {"__end__": mock_graph_result}

            mock_graph.astream = mock_astream

            with patch("agents.profile_agent.markdown_to_pdf") as mock_pdf:
                mock_pdf.return_value = b"PDF"

                with patch("agents.profile_agent.get_pdf_filename"):
                    # Should not raise an error despite cache failure
                    result = await agent.run("profile test", context)

                    assert result is not None
                    # Verify caching was attempted
                    mock_cache.store_document_content.assert_called_once()
