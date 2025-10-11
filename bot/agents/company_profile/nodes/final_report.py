"""Final report generation node for deep research workflow.

Generates comprehensive profile reports from accumulated research notes.
Includes Langfuse tracing for observability.
"""

import logging
from datetime import datetime

from langchain_core.runnables import RunnableConfig

from agents.company_profile import prompts
from agents.company_profile.configuration import ProfileConfiguration
from agents.company_profile.state import ProfileAgentState
from agents.company_profile.utils import (
    create_human_message,
    create_system_message,
    format_research_context,
    is_token_limit_exceeded,
    remove_up_to_last_ai_message,
)

logger = logging.getLogger(__name__)


def extract_citations_from_report(report: str) -> list[int]:
    """Extract all citation numbers [1], [2], etc. from report.

    Args:
        report: Markdown report text

    Returns:
        Sorted list of unique citation numbers found
    """
    import re

    # Find all [N] citations in the report
    citations = re.findall(r"\[(\d+)\]", report)
    # Convert to integers, deduplicate, and sort
    return sorted({int(c) for c in citations})


def count_sources_in_section(report: str) -> int:
    """Count number of source entries in ## Sources section.

    Args:
        report: Markdown report text

    Returns:
        Number of sources listed (0 if section missing)
    """
    import re

    # Find ## Sources section
    sources_match = re.search(r"## Sources\s*\n(.*)", report, re.DOTALL)
    if not sources_match:
        return 0

    sources_section = sources_match.group(1)

    # Count numbered entries (1. ... 2. ... 3. ...)
    # Match lines starting with digits followed by period
    source_entries = re.findall(r"^\d+\.\s+", sources_section, re.MULTILINE)

    return len(source_entries)


async def validate_report_quality(report: str, llm_api_key: str) -> dict:
    """Validate report quality using LLM judge.

    Args:
        report: Generated report to validate
        llm_api_key: API key for judge LLM

    Returns:
        Dict with validation results: {passes_quality, issues, revision_instructions}
    """
    from langchain_openai import ChatOpenAI

    # Quality validation prompt
    judge_prompt = """You are a quality control judge evaluating a company profile report.

<Report to Evaluate>
{report}
</Report to Evaluate>

<Quality Criteria - ALL MUST PASS>
1. **Sources Section Present**: Report MUST end with "## Sources" section
2. **All Citations Listed**: Every citation [1], [2], [3]... MUST have corresponding entry in Sources
3. **No Gaps in Numbering**: Sources numbered sequentially (1, 2, 3...) with NO gaps
4. **External Sources Only**: No "Internal research" or meta-references in Sources

<Your Task>
Evaluate and return ONLY this JSON:
{{
  "passes_quality": true/false,
  "issues": ["issue 1", "issue 2"],
  "highest_citation": 15,
  "sources_count": 10,
  "missing_sources": [11, 12, 13, 14, 15],
  "revision_instructions": "Specific fix instructions if fails"
}}

Examples:
- PASS: Uses [1-12], lists 1-12 → {{"passes_quality": true, "issues": []}}
- FAIL: Uses [1-18], lists 1-10 → {{"passes_quality": false, "issues": ["Missing sources 11-18"], "revision_instructions": "Add sources 11-18 with URLs"}}
"""

    try:
        import json
        import re

        judge_llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=llm_api_key,
            temperature=0.0,
            max_completion_tokens=500,
        )

        response = await judge_llm.ainvoke(judge_prompt.format(report=report))
        response_text = response.content.strip()

        # Extract JSON from markdown code blocks if present
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", response_text, re.DOTALL)
        if json_match:
            json_text = json_match.group(1)
        else:
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            json_text = json_match.group(0) if json_match else response_text

        return json.loads(json_text)

    except Exception as e:
        logger.warning(f"Quality validation error: {e}")
        # On error, assume pass to not block workflow
        return {"passes_quality": True, "issues": [], "revision_instructions": ""}


async def final_report_generation(
    state: ProfileAgentState, config: RunnableConfig
) -> dict:
    """Generate final comprehensive profile report with quality validation.

    Implements up to 5 revision cycles using LLM-as-a-judge to ensure
    all citations have corresponding source entries.

    Args:
        state: Current profile agent state with all research notes
        config: Runtime configuration

    Returns:
        Dict with final_report and executive_summary
    """
    configuration = ProfileConfiguration.from_runnable_config(config)
    notes = state.get("notes", [])
    profile_type = state.get("profile_type", "company")
    research_brief = state.get("research_brief", "")

    logger.info(f"Generating final report from {len(notes)} research notes")

    if not notes:
        logger.warning("No research notes available for final report")
        return {"final_report": "No research findings available to generate report."}

    # Use LangChain with Gemini or OpenAI
    from config.settings import Settings

    settings = Settings()

    # Check if Gemini is enabled for final report generation
    if settings.gemini.enabled and settings.gemini.api_key:
        from langchain_google_genai import ChatGoogleGenerativeAI

        logger.info(
            f"Using Gemini ({settings.gemini.model}) for final report generation"
        )
        llm = ChatGoogleGenerativeAI(
            model=settings.gemini.model,
            google_api_key=settings.gemini.api_key,
            temperature=0.7,
            max_output_tokens=configuration.final_report_model_max_tokens,
        )
    else:
        from langchain_openai import ChatOpenAI

        logger.info(f"Using OpenAI ({settings.llm.model}) for final report generation")
        llm = ChatOpenAI(
            model=settings.llm.model,
            api_key=settings.llm.api_key,
            temperature=0.7,
            max_completion_tokens=configuration.final_report_model_max_tokens,
        )

    # Format research context
    notes_text = format_research_context(research_brief, notes, profile_type)

    # Build final report prompt
    current_date = datetime.now().strftime("%B %d, %Y")
    system_prompt = prompts.final_report_generation_prompt.format(
        profile_type=profile_type, notes=notes_text, current_date=current_date
    )

    # Quality-controlled generation with up to 5 revision cycles
    max_quality_attempts = 5
    final_report = None

    for quality_attempt in range(max_quality_attempts):
        logger.info(
            f"Report generation attempt {quality_attempt + 1}/{max_quality_attempts}"
        )

        # Build messages for this attempt
        if quality_attempt == 0:
            # First attempt - normal generation
            messages = [
                create_system_message(system_prompt),
                create_human_message("Generate the comprehensive profile report now."),
            ]
        else:
            # Revision attempt - use feedback from quality check
            revision_instructions = getattr(
                final_report_generation, "_last_revision_instructions", ""
            )
            revision_prompt = f"""Your previous report did not pass quality control. Please revise it to fix these issues:

{revision_instructions}

**CRITICAL:** Make sure to:
- Include the complete ## Sources section at the end
- List ALL sources corresponding to EVERY citation [1], [2], [3]... used in the report
- Number sources sequentially with NO gaps (1, 2, 3, 4, 5...)
- Include full URL and description for each source

Generate the complete revised report now.
"""
            messages = [
                create_system_message(system_prompt),
                create_human_message(revision_prompt),
            ]

        # Try generation with token limit retry
        max_token_attempts = 3
        for token_attempt in range(max_token_attempts):
            try:
                response = await llm.ainvoke(messages)
                final_report = (
                    response.content if hasattr(response, "content") else str(response)
                )
                logger.info(
                    f"Report generated: {len(final_report)} characters (quality attempt {quality_attempt + 1}, token attempt {token_attempt + 1})"
                )
                break  # Success, exit token retry loop

            except Exception as e:
                if is_token_limit_exceeded(e, configuration.final_report_model):
                    logger.warning(
                        f"Token limit on generation attempt {token_attempt + 1}"
                    )
                    messages = remove_up_to_last_ai_message(messages)
                    continue
                logger.error(f"Report generation error: {e}")
                break

        # If generation failed completely, use fallback
        if not final_report:
            logger.error("Failed to generate report, using fallback")
            final_report = (
                "# Profile Report (Partial)\n\n"
                "Unable to generate full report. Research findings:\n\n"
                + "\n\n".join(notes[:3])
            )
            break  # Exit quality loop

        # Validate report quality
        logger.info("Validating report quality with LLM judge...")
        citations = extract_citations_from_report(final_report)
        sources_count = count_sources_in_section(final_report)
        logger.info(
            f"Report stats: {len(citations)} citations (highest: {max(citations) if citations else 0}), "
            f"{sources_count} source entries"
        )

        validation = await validate_report_quality(final_report, settings.llm.api_key)
        passes_quality = validation.get("passes_quality", True)
        issues = validation.get("issues", [])
        revision_instructions_text = validation.get("revision_instructions", "")

        if passes_quality:
            logger.info(
                f"✅ Report PASSED quality control on attempt {quality_attempt + 1}"
            )
            break  # Success, exit quality loop

        # Report failed quality check
        logger.warning(
            f"❌ Report FAILED quality control (attempt {quality_attempt + 1}): {len(issues)} issues"
        )
        for issue in issues:
            logger.warning(f"  - {issue}")

        # Check if we've exhausted quality attempts
        if quality_attempt + 1 >= max_quality_attempts:
            logger.error(
                f"❌ Max quality attempts ({max_quality_attempts}) exceeded, proceeding with imperfect report"
            )
            # Add warning to report
            warning_text = (
                "\n\n---\n\n"
                f"⚠️ **Quality Control Warning**: This report did not pass all quality checks after {max_quality_attempts} attempts. "
                f"Known issues: {', '.join(issues)}\n\n"
            )
            final_report = str(final_report) + warning_text
            break

        # Store revision instructions for next attempt
        final_report_generation._last_revision_instructions = "\n".join(
            f"{i + 1}. {issue}\n\n{revision_instructions_text}"
            for i, issue in enumerate(issues)
        )
        logger.info(
            f"🔄 Will retry with revision instructions: {revision_instructions_text[:100]}..."
        )

    # Generate executive summary for Slack display
    logger.info("Generating executive summary from full report")

    try:
        summary_prompt = prompts.executive_summary_prompt.format(
            full_report=final_report
        )
        # Always use GPT-4o for executive summary (more reliable than Gemini)
        from langchain_openai import ChatOpenAI

        logger.info("Using GPT-4o for executive summary generation")
        summary_llm = ChatOpenAI(
            model="gpt-4o",
            api_key=settings.llm.api_key,
            temperature=0.7,
            max_completion_tokens=500,
        )
        summary_response = await summary_llm.ainvoke(
            [create_human_message(summary_prompt)]
        )
        executive_summary = (
            summary_response.content
            if hasattr(summary_response, "content")
            else str(summary_response)
        )

        # Validate that summary is not empty
        if not executive_summary or len(executive_summary.strip()) == 0:
            raise ValueError("LLM returned empty executive summary")

        logger.info(f"Executive summary generated: {len(executive_summary)} characters")

    except Exception as summary_error:
        logger.warning(f"Failed to generate executive summary: {summary_error}")
        # Fallback: use Slack-safe markdown
        executive_summary = (
            "📊 *Executive Summary*\n\n"
            "• Full detailed report attached as PDF\n\n"
            "📎 _Unable to generate summary - see full report_"
        )

    return {
        "final_report": final_report,
        "executive_summary": executive_summary,
    }
