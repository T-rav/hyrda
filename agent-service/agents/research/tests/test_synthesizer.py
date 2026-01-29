"""Tests for synthesizer node with PDF generation."""

from io import BytesIO
from unittest.mock import AsyncMock, Mock, patch

import pytest
from langchain_core.messages import AIMessage

from ..nodes.synthesizer import synthesize_findings
from ..state import CachedFile


@pytest.fixture
def mock_state():
    """Mock research agent state."""
    return {
        "query": "Test research query",
        "research_plan": "Test plan",
        "completed_tasks": [
            {
                "task_id": "task_1",
                "description": "Research task 1",
                "priority": "high",
                "findings": "Finding 1: Important data",
            },
            {
                "task_id": "task_2",
                "description": "Research task 2",
                "priority": "medium",
                "findings": "Finding 2: More data",
            },
        ],
        "report_structure": "# Report\n## Section 1\n## Section 2",
    }


class TestSynthesizerPDFGeneration:
    """Test PDF generation in synthesizer node."""

    @pytest.mark.skip(
        reason="Requires full environment (SLACK_BOT_TOKEN, LLM_API_KEY, S3)"
    )
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_synthesize_with_pdf_success(self, mock_state):
        """Test successful PDF generation and S3 upload - requires full stack."""
        mock_pdf_bytes = BytesIO(b"%PDF-1.4 test pdf content")
        mock_cached_file = CachedFile(
            file_id="test123",
            file_type="pdf",
            file_path="s3://research-pdfs/test_report.pdf",
            metadata={"query": "Test query"},
            cached_at="2024-01-01T00:00:00",
            size_bytes=1024,
        )
        mock_presigned_url = (
            "http://minio:9000/research-pdfs/test_report.pdf?signature=abc123"
        )

        # Mock LLM
        mock_llm = AsyncMock()
        report_response = Mock()
        report_response.content = "# Test Report\n\nContent here"
        summary_response = Mock()
        summary_response.content = "• Finding 1\n• Finding 2"
        mock_llm.ainvoke.side_effect = [report_response, summary_response]

        # Mock Settings
        mock_settings = Mock()
        mock_settings.llm.model = "gpt-4"
        mock_settings.llm.api_key = "test-key"

        # Mock PDF generator
        def mock_markdown_to_pdf(*args, **kwargs):
            return mock_pdf_bytes

        # Mock file cache
        mock_cache = Mock()
        mock_cache.cache_file.return_value = mock_cached_file
        mock_cache.get_presigned_url.return_value = mock_presigned_url

        with (
            patch("langchain_openai.ChatOpenAI", return_value=mock_llm),
            patch(
                "config.settings.Settings",
                return_value=mock_settings,
            ),
            patch(
                "utils.pdf_generator.markdown_to_pdf",
                side_effect=mock_markdown_to_pdf,
            ),
            patch(
                "agents.system.research.services.file_cache.ResearchFileCache",
                return_value=mock_cache,
            ),
        ):
            result = await synthesize_findings(mock_state)

            # Verify basic structure
            assert "final_report" in result
            assert "executive_summary" in result
            assert "pdf_url" in result
            assert "messages" in result

            # Verify PDF URL is set
            assert result["pdf_url"] == mock_presigned_url

            # Verify PDF was generated
            assert mock_cache.cache_file.called
            assert mock_cache.get_presigned_url.called

    @pytest.mark.skip(
        reason="Requires full environment (SLACK_BOT_TOKEN, LLM_API_KEY, S3)"
    )
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_synthesize_pdf_generation_fails_gracefully(self, mock_state):
        """Test that synthesizer continues if PDF generation fails - requires full stack."""
        mock_llm = AsyncMock()
        report_response = Mock()
        report_response.content = "# Test Report"
        summary_response = Mock()
        summary_response.content = "• Finding 1"
        mock_llm.ainvoke.side_effect = [report_response, summary_response]

        mock_settings = Mock()
        mock_settings.llm.model = "gpt-4"
        mock_settings.llm.api_key = "test-key"

        with (
            patch("langchain_openai.ChatOpenAI", return_value=mock_llm),
            patch(
                "config.settings.Settings",
                return_value=mock_settings,
            ),
            patch(
                "utils.pdf_generator.markdown_to_pdf",
                side_effect=Exception("PDF error"),
            ),
        ):
            result = await synthesize_findings(mock_state)

            # Verify continues without PDF
            assert "final_report" in result
            assert "executive_summary" in result
            assert "pdf_url" in result
            assert result["pdf_url"] == ""  # Empty when PDF fails

    @pytest.mark.asyncio
    async def test_synthesize_no_completed_tasks(self):
        """Test synthesizer with no completed tasks."""
        state = {
            "query": "Test query",
            "completed_tasks": [],
        }

        result = await synthesize_findings(state)

        assert result["final_report"] == "No research completed yet."
        assert result["executive_summary"] == "Research in progress."
        assert isinstance(result["messages"][0], AIMessage)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
