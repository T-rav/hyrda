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
from services.langfuse_service import get_langfuse_service

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

    # Start Langfuse span for final report generation
    langfuse_service = get_langfuse_service()
    span = None
    if langfuse_service and langfuse_service.client:
        span = langfuse_service.client.start_span(
            name="deep_research_final_report_generation",
            input={
                "notes_count": len(notes),
                "profile_type": profile_type,
                "research_brief": research_brief[:200],
            },
            metadata={
                "node_type": "final_report",
                "max_tokens": configuration.final_report_model_max_tokens,
            },
        )

    if not notes:
        logger.warning("No research notes available for final report")
        if span:
            span.end(
                level="WARNING",
                output={"success": False, "reason": "no_notes"},
            )
        return {"final_report": "No research findings available to generate report."}

    # Use LangChain ChatOpenAI directly
    from langchain_openai import ChatOpenAI

    from config.settings import Settings

    settings = Settings()
    llm = ChatOpenAI(
        model=settings.llm.model,
        api_key=settings.llm.api_key,
        temperature=0.7,
        max_tokens=configuration.final_report_model_max_tokens,
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
            # Trace LLM generation
            generation = None
            if langfuse_service and langfuse_service.client:
                generation = langfuse_service.client.start_generation(
                    name="final_report_llm_call",
                    input={
                        "messages": messages,
                        "attempt": attempt + 1,
                        "notes_count": len(notes),
                    },
                    metadata={
                        "profile_type": profile_type,
                        "max_tokens": configuration.final_report_model_max_tokens,
                    },
                )

            # Use LangChain ChatOpenAI
            response = await llm.ainvoke(messages)
            final_report = (
                response.content if hasattr(response, "content") else str(response)
            )
            logger.info(f"Final report generated: {len(final_report)} characters")

            # End generation trace
            if generation:
                generation.end(
                    output={
                        "report_length": len(final_report),
                        "attempt": attempt + 1,
                    }
                )

            # Generate executive summary for Slack display
            logger.info("Generating executive summary from full report")
            summary_generation = None
            if langfuse_service and langfuse_service.client:
                summary_generation = langfuse_service.client.start_generation(
                    name="executive_summary_generation",
                    input={
                        "full_report_length": len(final_report),
                        "profile_type": profile_type,
                    },
                    metadata={"node_type": "executive_summary"},
                )

            try:
                summary_prompt = prompts.executive_summary_prompt.format(
                    full_report=final_report
                )
                # Use LangChain ChatOpenAI with lower max_tokens for summary
                summary_llm = ChatOpenAI(
                    model=settings.llm.model,
                    api_key=settings.llm.api_key,
                    temperature=0.7,
                    max_tokens=500,
                )
                summary_response = await summary_llm.ainvoke(
                    [create_human_message(summary_prompt)]
                )
                executive_summary = (
                    summary_response.content
                    if hasattr(summary_response, "content")
                    else str(summary_response)
                )
                logger.info(
                    f"Executive summary generated: {len(executive_summary)} characters"
                )

                if summary_generation:
                    summary_generation.end(
                        output={"summary_length": len(executive_summary)}
                    )

            except Exception as summary_error:
                logger.warning(f"Failed to generate executive summary: {summary_error}")
                # Fallback: use first paragraph of report
                executive_summary = (
                    "📊 **Executive Summary**\n\n"
                    "• Full detailed report attached as PDF\n\n"
                    "📎 _Unable to generate summary - see full report_"
                )
                if summary_generation:
                    summary_generation.end(
                        level="WARNING", status_message=str(summary_error)
                    )

            # End span
            if span:
                span.end(
                    output={
                        "success": True,
                        "report_length": len(final_report),
                        "summary_length": len(executive_summary),
                        "attempts": attempt + 1,
                    }
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
            if generation:
                generation.end(level="ERROR", status_message=str(e))
            if span:
                span.end(level="ERROR", status_message=str(e))
            break

    # Fallback: return notes summary
    fallback_report = (
        "# Profile Report (Partial)\n\n"
        "Unable to generate full report. Research findings:\n\n"
        + "\n\n".join(notes[:3])
    )

    if span:
        span.end(
            output={
                "success": False,
                "fallback": True,
                "notes_included": min(3, len(notes)),
            }
        )

    return {"final_report": fallback_report}
