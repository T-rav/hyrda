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


async def final_report_generation(
    state: ProfileAgentState, config: RunnableConfig
) -> dict:
    """Generate final comprehensive profile report.

    Args:
        state: Current profile agent state with all research notes
        config: Runtime configuration

    Returns:
        Dict with final_report
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

    # Try generation with retry on token limits
    max_attempts = 3
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

                logger.info(
                    f"Executive summary generated: {len(executive_summary)} characters"
                )

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

    return {"final_report": fallback_report}
