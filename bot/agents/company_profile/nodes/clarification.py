"""Clarification node for deep research workflow.

Checks if clarification is needed from the user before starting research.
Includes Langfuse tracing for observability.
"""

import logging

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.types import Command

from agents.company_profile import prompts
from agents.company_profile.configuration import ProfileConfiguration
from agents.company_profile.state import ProfileAgentState
from agents.company_profile.utils import create_human_message
from services.langfuse_service import get_langfuse_service

logger = logging.getLogger(__name__)


async def clarify_with_user(
    state: ProfileAgentState, config: RunnableConfig
) -> Command[str]:
    """Check if clarification is needed before research.

    Args:
        state: Current profile agent state
        config: Runtime configuration

    Returns:
        Command to proceed to write_research_brief or END with question
    """
    configuration = ProfileConfiguration.from_runnable_config(config)

    # Start Langfuse span for clarification
    langfuse_service = get_langfuse_service()
    span = None
    if langfuse_service and langfuse_service.client:
        span = langfuse_service.client.start_span(
            name="deep_research_clarify_with_user",
            input={
                "query": state["query"][:200],
                "allow_clarification": configuration.allow_clarification,
            },
            metadata={
                "node_type": "clarification",
            },
        )

    if not configuration.allow_clarification:
        logger.info("Clarification disabled, proceeding to research brief")
        if span:
            span.end(output={"decision": "skip", "reason": "disabled"})
        return Command(goto="write_research_brief", update={})

    query = state["query"]
    llm_service = config.get("configurable", {}).get("llm_service")

    if not llm_service:
        logger.warning("No LLM service, skipping clarification")
        if span:
            span.end(level="WARNING", status_message="No LLM service available")
        return Command(goto="write_research_brief", update={})

    # Check if clarification needed
    try:
        # Trace LLM generation
        generation = None
        if langfuse_service and langfuse_service.client:
            generation = langfuse_service.client.start_generation(
                name="clarification_check_llm_call",
                input={"query": query},
                metadata={
                    "purpose": "check_clarification_needed",
                },
            )

        prompt = prompts.clarify_with_user_instructions.format(query=query)
        response = await llm_service.get_response(
            messages=[create_human_message(prompt)],
        )

        # End generation trace
        if generation:
            generation.end(output={"response": response})

        # Parse response (simplified - in production use structured output)
        if (
            isinstance(response, str)
            and "need_clarification: false" in response.lower()
        ):
            logger.info("No clarification needed")
            if span:
                span.end(output={"decision": "proceed", "clarification_needed": False})
            return Command(goto="write_research_brief", update={})
        else:
            logger.info("Clarification needed, returning question")
            clarification_msg = (
                response
                if isinstance(response, str)
                else "Please provide more details about what you'd like to know."
            )

            if span:
                span.end(
                    output={
                        "decision": "ask_user",
                        "clarification_needed": True,
                        "message_length": len(clarification_msg),
                    }
                )

            return Command(
                goto=END,
                update={
                    "final_report": f"❓ **Clarification Needed**\n\n{clarification_msg}"
                },
            )

    except Exception as e:
        logger.error(f"Clarification error: {e}, proceeding anyway")
        if generation:
            generation.end(level="ERROR", status_message=str(e))
        if span:
            span.end(level="ERROR", status_message=str(e))
        return Command(goto="write_research_brief", update={})
