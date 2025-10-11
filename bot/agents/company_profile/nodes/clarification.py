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

    if not configuration.allow_clarification:
        logger.info("Clarification disabled, proceeding to research brief")
        return Command(goto="write_research_brief", update={})

    query = state["query"]
    llm_service = config.get("configurable", {}).get("llm_service")

    if not llm_service:
        logger.warning("No LLM service, skipping clarification")
        return Command(goto="write_research_brief", update={})

    # Check if clarification needed
    try:
        prompt = prompts.clarify_with_user_instructions.format(query=query)
        response = await llm_service.get_response(
            messages=[create_human_message(prompt)],
        )

        # Parse response (simplified - in production use structured output)
        if (
            isinstance(response, str)
            and "need_clarification: false" in response.lower()
        ):
            logger.info("No clarification needed")
            return Command(goto="write_research_brief", update={})
        else:
            logger.info("Clarification needed, returning question")
            clarification_msg = (
                response
                if isinstance(response, str)
                else "Please provide more details about what you'd like to know."
            )

            return Command(
                goto=END,
                update={
                    "final_report": f"❓ **Clarification Needed**\n\n{clarification_msg}"
                },
            )

    except Exception as e:
        logger.error(f"Clarification error: {e}, proceeding anyway")
        return Command(goto="write_research_brief", update={})
