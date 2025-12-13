"""Synthesizer node - combines findings into comprehensive report."""

import asyncio
import logging
from datetime import datetime
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI

from config.settings import Settings

from ..state import ResearchAgentState

logger = logging.getLogger(__name__)


def _generate_and_upload_pdf(
    final_report: str, query: str, task_count: int
) -> str | None:
    """Generate PDF and upload to S3 (blocking I/O, run in thread).

    Args:
        final_report: Markdown content
        query: Research query
        task_count: Number of completed tasks

    Returns:
        Presigned URL or None if failed
    """
    try:
        from utils.pdf_generator import markdown_to_pdf

        from ..services.file_cache import ResearchFileCache

        # Generate PDF from markdown (blocking file I/O)
        pdf_bytes_io = markdown_to_pdf(
            markdown_content=final_report,
            title=f"Research Report: {query[:100]}",
            metadata={
                "generated_at": datetime.now().isoformat(),
                "query": query,
                "task_count": task_count,
            },
            style="professional",
        )

        if not pdf_bytes_io:
            logger.warning("PDF generation returned None")
            return None

        # Upload to S3/MinIO (blocking network I/O)
        file_cache = ResearchFileCache()
        cached_file = file_cache.cache_file(
            file_type="pdf",
            content=pdf_bytes_io.getvalue(),
            metadata={
                "query": query,
                "title": f"Research Report: {query[:100]}",
                "generated_at": datetime.now().isoformat(),
                "report_length": len(final_report),
            },
        )

        if not cached_file:
            logger.warning("File cache returned None")
            return None

        # Generate presigned URL (valid for 7 days)
        pdf_url = file_cache.get_presigned_url(cached_file.file_path, expiration=604800)
        return pdf_url

    except Exception as e:
        logger.error(f"PDF generation/upload failed: {e}")
        return None


async def synthesize_findings(state: ResearchAgentState) -> dict[str, Any]:
    """Synthesize research findings into comprehensive report.

    Takes completed research tasks and creates a structured report following
    the LLM-generated report structure outline.

    Args:
        state: Research agent state with completed tasks

    Returns:
        Updated state with final_report and executive_summary
    """
    query = state["query"]
    research_plan = state.get("research_plan", "")
    completed_tasks = state.get("completed_tasks", [])
    report_structure = state.get("report_structure", "")

    logger.info(f"Synthesizing findings from {len(completed_tasks)} completed tasks")

    if not completed_tasks:
        return {
            "final_report": "No research completed yet.",
            "executive_summary": "Research in progress.",
            "messages": [AIMessage(content="⚠️ No completed tasks to synthesize")],
        }

    # Initialize LLM
    settings = Settings()
    llm = ChatOpenAI(
        model=settings.llm.model, api_key=settings.llm.api_key, temperature=0.3
    )

    # Compile all findings
    findings_text = []
    for task in completed_tasks:
        findings_text.append(
            f"\n## {task.description}\n**Priority:** {task.priority}\n\n{task.findings}\n"
        )

    all_findings = "\n".join(findings_text)

    # Create synthesis prompt
    synthesis_prompt = f"""You are a world-class research analyst. Synthesize the following research findings into a comprehensive, publication-quality report.

**Original Query:** {query}

**Research Strategy:**
{research_plan}

**Report Structure to Follow:**
{report_structure}

**Research Findings:**
{all_findings}

Create a comprehensive report that:
1. Follows the report structure outline
2. Integrates findings across all research tasks
3. Provides deep analysis and insights
4. Includes specific examples and data points
5. Draws clear conclusions

Format in markdown with proper headings, bullet points, and emphasis.
Report should be 1500-3000 words.
"""

    try:
        # Generate report
        response = await llm.ainvoke([HumanMessage(content=synthesis_prompt)])
        final_report = response.content

        # Generate executive summary (3-5 bullets)
        summary_prompt = f"""Create a concise executive summary (3-5 bullet points) of this research report:

{final_report[:2000]}

Format as markdown bullet list with key takeaways."""

        summary_response = await llm.ainvoke([HumanMessage(content=summary_prompt)])
        executive_summary = summary_response.content

        logger.info(f"Report synthesized: {len(final_report)} characters")

        # Generate PDF and upload to S3 (in thread to avoid blocking I/O)
        pdf_url = None
        try:
            # Run PDF generation in separate thread (blocking file I/O)
            pdf_url = await asyncio.to_thread(
                _generate_and_upload_pdf, final_report, query, len(completed_tasks)
            )
            if pdf_url:
                logger.info(f"✅ PDF uploaded to S3: {pdf_url[:100]}...")
        except Exception as pdf_error:
            logger.error(f"Failed to generate/upload PDF: {pdf_error}")
            # Continue without PDF - don't fail the whole synthesis

        return {
            "final_report": final_report,
            "executive_summary": executive_summary,
            "pdf_url": pdf_url or "",
            "messages": [
                AIMessage(
                    content=f"✅ Research report completed ({len(final_report)} characters)"
                    + (f"\n📎 PDF: {pdf_url}" if pdf_url else "")
                )
            ],
        }

    except Exception as e:
        logger.error(f"Error synthesizing findings: {e}")
        return {
            "final_report": f"Error synthesizing report: {str(e)}",
            "executive_summary": "Error creating summary",
            "messages": [AIMessage(content=f"❌ Error synthesizing: {str(e)}")],
        }
