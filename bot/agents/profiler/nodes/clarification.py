"""Clarification node for deep research workflow.

Checks if clarification is needed from the user before starting research.
Includes Langfuse tracing for observability.
"""

import logging

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.types import Command

from agents.profiler import prompts
from agents.profiler.configuration import ProfileConfiguration
from agents.profiler.state import ProfileAgentState
from agents.profiler.utils import create_human_message

logger = logging.getLogger(__name__)


async def clarify_with_user(
    state: ProfileAgentState, config: RunnableConfig
) -> Command[str]:
    """Check if clarification is needed before research.

    Also detects URLs in the query and extracts company names from them.

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

    # Check if query contains a URL
    import re

    url_pattern = r"(?:https?://)?(?:www\.)?([a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:\.[a-zA-Z]{2,})?(?:/[\w\-._~:/?#[\]@!$&'()*+,;=]*)?)"
    url_match = re.search(url_pattern, query)

    if url_match:
        url = url_match.group(0)
        logger.info(f"Detected URL in query: {url}")

        # Extract company name from URL
        from agents.profiler.utils import extract_company_from_url

        company_name = await extract_company_from_url(url)

        if company_name:
            logger.info(f"Successfully extracted company name from URL: {company_name}")
            # Replace URL with company name in query
            updated_query = query.replace(url, company_name)
            logger.info(f"Updated query: {updated_query}")

            # Update state with cleaner query
            return Command(goto="write_research_brief", update={"query": updated_query})
        else:
            logger.warning(f"Failed to extract company name from URL: {url}")
            # Continue with original query

    # Check if clarification needed
    try:
        from langchain_openai import ChatOpenAI

        from config.settings import Settings

        settings = Settings()
        llm = ChatOpenAI(
            model=settings.llm.model,
            api_key=settings.llm.api_key,
            temperature=0.0,
        )

        prompt = prompts.clarify_with_user_instructions.format(query=query)
        response = await llm.ainvoke(create_human_message(prompt))

        # Extract content from response
        response_text = (
            response.content if hasattr(response, "content") else str(response)
        )

        # Parse response (simplified - in production use structured output)
        if "need_clarification: false" in response_text.lower():
            logger.info("No clarification needed")
            return Command(goto="write_research_brief", update={})
        else:
            logger.info("Clarification needed, returning question")
            clarification_msg = response_text

            return Command(
                goto=END,
                update={
                    "final_report": f"❓ **Clarification Needed**\n\n{clarification_msg}"
                },
            )

    except Exception as e:
        logger.error(f"Clarification error: {e}, proceeding anyway")
        return Command(goto="write_research_brief", update={})
