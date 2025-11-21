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
from services.prompt_service import get_prompt_service

logger = logging.getLogger(__name__)


async def final_report_generation(
    state: ProfileAgentState, config: RunnableConfig
) -> dict:
    """Generate final comprehensive profile report.

    Args:
        state: Current profile agent state with all research notes
        config: Runtime configuration

    Returns:
        Dict with final_report and executive_summary
    """
    configuration = ProfileConfiguration.from_runnable_config(config)
    notes = state.get("notes", [])
    profile_type = state.get("profile_type", "company")
    focus_area = state.get("focus_area", "")
    research_brief = state.get("research_brief", "")
    revision_count = state.get("revision_count", 0)
    revision_prompt = state.get("revision_prompt", "")

    if revision_count > 0:
        logger.info(
            f"Generating REVISED report (attempt {revision_count}) from {len(notes)} research notes"
        )
    else:
        logger.info(f"Generating final report from {len(notes)} research notes")

    if not notes:
        logger.warning("No research notes available for final report")
        return {"final_report": "No research findings available to generate report."}

    # Use LangChain with Gemini or OpenAI
    from config.settings import Settings

    settings = Settings()

    # Check if Gemini is enabled for final report generation
    llm = None
    if settings.gemini.enabled and settings.gemini.api_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI

            logger.info(
                f"Using Gemini ({settings.gemini.model}) for final report generation"
            )
            llm = ChatGoogleGenerativeAI(
                model=settings.gemini.model,
                google_api_key=settings.gemini.api_key,
                temperature=0.0,  # CRITICAL: 0.0 to prevent hallucination in relationship status
                max_output_tokens=configuration.final_report_model_max_tokens,
            )
        except ImportError:
            logger.warning(
                "langchain_google_genai not installed - falling back to OpenAI"
            )

    if llm is None:
        from langchain_openai import ChatOpenAI

        logger.info(f"Using OpenAI ({settings.llm.model}) for final report generation")
        llm = ChatOpenAI(
            model=settings.llm.model,
            api_key=settings.llm.api_key,
            temperature=0.0,  # CRITICAL: 0.0 to prevent hallucination in relationship status
            max_completion_tokens=configuration.final_report_model_max_tokens,
        )

    # Format research context (async - uses LLM for source selection)
    notes_text = await format_research_context(research_brief, notes, profile_type)

    # Build final report prompt with focus area
    current_date = datetime.now().strftime("%B %d, %Y")

    # Build focus guidance for final report
    if focus_area:
        focus_guidance = f"""
**🎯 CRITICAL - USER'S SPECIFIC REQUEST**: The user specifically asked about "{focus_area}".

**Report Writing Strategy:**
1. **Front-load the focus**: Sections most relevant to {focus_area} should be LONGEST and MOST DETAILED
2. **Emphasize in Solutions section**: The "Solutions 8th Light Can Offer" section MUST heavily emphasize opportunities related to {focus_area}
3. **Connect throughout**: In EVERY section, look for connections to {focus_area} and make them explicit
4. **Executive Summary priority**: Ensure at least 1-2 of the 3 bullet points relate to {focus_area}
5. **Depth allocation**:
   - Sections directly about {focus_area}: Write 4-5 paragraphs each (maximum depth)
   - Related sections: Write 3-4 paragraphs (good depth)
   - Less relevant sections: Write 2-3 paragraphs (sufficient context)

**Example**: If focus is "AI needs", then:
- "Company Priorities" should extensively cover AI initiatives
- "Size of Teams" should deeply analyze AI/ML team structure
- "Solutions 8th Light Can Offer" should propose AI-specific consulting opportunities
- Other sections should still be comprehensive but briefer"""
    else:
        focus_guidance = ""

    # Get prompt from Langfuse (required - no local fallback)
    # Select prompt based on profile type
    prompt_service = get_prompt_service()
    if not prompt_service:
        raise RuntimeError("PromptService not available - required for profile agent")

    if profile_type == "employee":
        prompt_name = "CompanyProfiler/Final_Report_Generation_Employee"
    else:
        prompt_name = "CompanyProfiler/Final_Report_Generation"

    logger.info(f"Fetching {profile_type} prompt from Langfuse: {prompt_name}")
    prompt_template = prompt_service.get_custom_prompt(
        template_name=prompt_name,
        fallback=None,  # Force error if Langfuse prompt not found
    )

    if not prompt_template:
        logger.error(
            f"Langfuse prompt '{prompt_name}' not found. "
            "Check: (1) Prompt exists in Langfuse, (2) Prompt is published/active, "
            "(3) Langfuse settings are correct (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST)"
        )
        raise RuntimeError(
            f"Langfuse prompt '{prompt_name}' not found. "
            "Profile agent requires Langfuse prompts - local fallbacks are not allowed."
        )

    system_prompt = prompt_template.format(
        profile_type=profile_type,
        focus_area=focus_area if focus_area else "None (general profile)",
        focus_guidance=focus_guidance,
        notes=notes_text,
        current_date=current_date,
    )

    # Try generation with retry on token limits
    max_attempts = 3

    # If this is a revision, add the revision prompt
    if revision_count > 0 and revision_prompt:
        logger.info(f"Using revision prompt: {revision_prompt[:100]}...")
        messages = [
            create_system_message(system_prompt),
            create_human_message(revision_prompt),
        ]
    else:
        messages = [
            create_system_message(system_prompt),
            create_human_message("Generate the comprehensive profile report now."),
        ]

    for attempt in range(max_attempts):
        try:
            # Use LangChain ChatOpenAI
            response = await llm.ainvoke(messages)
            final_report = (
                response.content if hasattr(response, "content") else str(response)
            )
            logger.info(f"Final report generated: {len(final_report)} characters")

            # Generate executive summary for Slack display
            logger.info("Generating executive summary from full report")

            try:
                # Build focus guidance for executive summary
                if focus_area:
                    summary_focus_guidance = f"""
**IMPORTANT**: The user specifically asked about "{focus_area}".
Ensure at least 1-2 of your 3 bullet points directly address {focus_area}."""
                else:
                    summary_focus_guidance = ""

                # Use local prompt for executive summary (not in Langfuse)
                summary_prompt = prompts.executive_summary_prompt.format(
                    full_report=final_report,
                    focus_area=focus_area if focus_area else "None (general profile)",
                    focus_guidance=summary_focus_guidance,
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

                logger.info(
                    f"Executive summary generated: {len(executive_summary)} characters"
                )

                # Add footer encouraging follow-up questions
                executive_summary += (
                    "\n\n---\n\n"
                    "_💬 Ask me follow-up questions about this profile in this thread!_\n"
                    "_Or start your message with `profile [company name]` to profile another company._"
                )

            except Exception as summary_error:
                logger.warning(f"Failed to generate executive summary: {summary_error}")
                # Fallback: use Slack-safe markdown
                executive_summary = (
                    "📊 *Executive Summary*\n\n"
                    "• Full detailed report attached as PDF\n\n"
                    "📎 _Unable to generate summary - see full report_\n\n"
                    "---\n\n"
                    "_💬 Ask me follow-up questions about this profile in this thread!_\n"
                    "_Or start your message with `profile [company name]` to profile another company._"
                )

            return {
                "final_report": final_report,
                "executive_summary": executive_summary,
            }

        except Exception as e:
            if is_token_limit_exceeded(e, configuration.final_report_model):
                logger.warning(f"Token limit on final report attempt {attempt + 1}")
                messages = remove_up_to_last_ai_message(messages)
                continue

            logger.error(f"Final report error: {e}")
            break

    # Fallback: return notes summary
    fallback_report = (
        "# Profile Report (Partial)\n\n"
        "Unable to generate full report. Research findings:\n\n"
        + "\n\n".join(notes[:3])
    )

    return {
        "final_report": fallback_report,
        "executive_summary": "📊 *Executive Summary*\n\n• Partial report generated\n\n📎 _See full report for details_",
    }
