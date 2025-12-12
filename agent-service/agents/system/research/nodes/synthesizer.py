"""Synthesizer node - combines findings into comprehensive report."""

import os
import logging

from config.settings import Settings
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI


from ..state import ResearchAgentState

logger = logging.getLogger(__name__)


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

    # Initialize LLM (Settings() in thread to avoid blocking os.getcwd)
    # Use os.getenv to avoid blocking I/O

    llm = ChatOpenAI(
        model=settings.llm.model,
        api_key=settings.llm.api_key,
        temperature=0.3
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

        # Generate PDF and upload to S3
        pdf_url = None
        try:
            from datetime import datetime

            from utils.pdf_generator import markdown_to_pdf

            from ..services.file_cache import ResearchFileCache

            # Generate PDF from markdown
            pdf_bytes_io = markdown_to_pdf(
                markdown_content=final_report,
                title=f"Research Report: {query[:100]}",
                metadata={
                    "generated_at": datetime.now().isoformat(),
                    "query": query,
                    "task_count": len(completed_tasks),
                },
                style="professional",
            )

            if pdf_bytes_io:
                # Upload to S3/MinIO
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

                # Generate presigned URL (valid for 7 days)
                if cached_file:
                    pdf_url = file_cache.get_presigned_url(
                        cached_file.file_path, expiration=604800
                    )
                    logger.info(f"✅ PDF uploaded to S3: {pdf_url[:100]}...")
                else:
                    logger.warning("File cache returned None")
            else:
                logger.warning("PDF generation returned None")

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
