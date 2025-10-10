"""Research brief generation node for deep research workflow.

Generates a structured research brief from user query to guide the research process.
Includes Langfuse tracing for observability.
"""

import logging
from datetime import datetime

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.types import Command

from agents.company_profile import prompts
from agents.company_profile.state import ProfileAgentState
from agents.company_profile.utils import (
    create_human_message,
    detect_profile_type,
)
from services.langfuse_service import get_langfuse_service

logger = logging.getLogger(__name__)


async def write_research_brief(
    state: ProfileAgentState, config: RunnableConfig
) -> Command[str]:
    """Generate research brief from user query.

    Args:
        state: Current profile agent state
        config: Runtime configuration

    Returns:
        Command to proceed to research_supervisor
    """
    query = state["query"]
    profile_type = state.get("profile_type", detect_profile_type(query))

    logger.info(f"Writing research brief for {profile_type} profile")

    # Start Langfuse span for research brief generation
    langfuse_service = get_langfuse_service()
    span = None
    if langfuse_service and langfuse_service.client:
        span = langfuse_service.client.start_span(
            name="deep_research_write_research_brief",
            input={
                "query": query[:200],
                "profile_type": profile_type,
            },
            metadata={
                "node_type": "research_brief",
            },
        )

    # Generate research brief using LangChain ChatOpenAI
    generation = None
    try:
        from langchain_openai import ChatOpenAI

        from config.settings import Settings

        settings = Settings()
        llm = ChatOpenAI(
            model=settings.llm.model,
            api_key=settings.llm.api_key,
            temperature=0.7,
        )

        # Trace LLM generation
        if langfuse_service and langfuse_service.client:
            generation = langfuse_service.client.start_generation(
                name="research_brief_llm_call",
                input={"query": query, "profile_type": profile_type},
                metadata={
                    "purpose": "generate_research_brief",
                },
            )

        current_date = datetime.now().strftime("%B %d, %Y")
        prompt = prompts.transform_messages_into_research_topic_prompt.format(
            query=query, profile_type=profile_type, current_date=current_date
        )
        response = await llm.ainvoke([create_human_message(prompt)])

        research_brief = (
            response.content if hasattr(response, "content") else str(response)
        )
        logger.info(f"Research brief generated: {len(research_brief)} characters")

        # End generation trace
        if generation:
            generation.end(
                output={
                    "research_brief_length": len(research_brief),
                    "profile_type": profile_type,
                }
            )

        # Initialize supervisor messages
        supervisor_init_msg = create_human_message(research_brief)

        if span:
            span.end(
                output={
                    "success": True,
                    "research_brief_length": len(research_brief),
                    "profile_type": profile_type,
                }
            )

        return Command(
            goto="research_supervisor",
            update={
                "research_brief": research_brief,
                "profile_type": profile_type,
                "supervisor_messages": [supervisor_init_msg],
            },
        )

    except Exception as e:
        logger.error(f"Research brief error: {e}")
        if generation:
            generation.end(level="ERROR", status_message=str(e))
        if span:
            span.end(level="ERROR", status_message=str(e))

        return Command(
            goto=END,
            update={"final_report": f"Error generating research plan: {str(e)}"},
        )
