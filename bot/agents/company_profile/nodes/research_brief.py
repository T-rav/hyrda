"""Research brief generation node for deep research workflow.

Generates a structured research brief from user query to guide the research process.
Includes Langfuse tracing for observability.
"""

import logging
from datetime import datetime

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.types import Command

from agents.company_profile import prompts
from agents.company_profile.state import ProfileAgentState
from agents.company_profile.utils import (
    create_human_message,
    detect_profile_type,
    internal_search_tool,
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

    # Generate research brief using LangChain ChatOpenAI with tool calling
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

        # Bind internal_search_tool to allow searching existing knowledge
        llm_with_tools = llm.bind_tools([internal_search_tool])

        # Trace LLM generation
        if langfuse_service and langfuse_service.client:
            generation = langfuse_service.client.start_generation(
                name="research_brief_llm_call",
                input={"query": query, "profile_type": profile_type},
                metadata={
                    "purpose": "generate_research_brief",
                    "tools_available": ["internal_search_tool"],
                },
            )

        current_date = datetime.now().strftime("%B %d, %Y")
        prompt = prompts.transform_messages_into_research_topic_prompt.format(
            query=query, profile_type=profile_type, current_date=current_date
        )
        messages = [create_human_message(prompt)]

        # Execute LLM with potential tool calls
        response = await llm_with_tools.ainvoke(messages)

        # Handle tool calls if present
        if hasattr(response, "tool_calls") and response.tool_calls:
            logger.info(
                f"Research brief requested {len(response.tool_calls)} tool calls"
            )

            # Add AI message to conversation
            messages.append(response)

            # Execute tool calls
            for tool_call in response.tool_calls:
                tool_name = tool_call.get("name", "")
                tool_args = tool_call.get("args", {})
                tool_id = tool_call.get("id", "")

                if tool_name == "internal_search_tool":
                    # Execute internal search
                    query_text = tool_args.get("query", "")
                    effort = tool_args.get("effort", "low")  # Default to low effort

                    logger.info(
                        f"Research brief executing internal search: {query_text}"
                    )

                    # Get internal deep research service from config
                    internal_deep_research = config.get("configurable", {}).get(
                        "internal_deep_research"
                    )

                    if not internal_deep_research:
                        tool_result = ToolMessage(
                            content="Internal search service not available",
                            tool_call_id=tool_id,
                        )
                        logger.warning(
                            "Internal deep research service not available for research brief"
                        )
                    else:
                        # Execute search
                        research_result = await internal_deep_research.deep_research(
                            query=query_text,
                            effort=effort,
                            conversation_history=[],
                            user_id=None,
                        )

                        if research_result.get("success"):
                            summary = research_result.get("summary", "")
                            tool_result = ToolMessage(
                                content=f"Internal search results:\n\n{summary}",
                                tool_call_id=tool_id,
                            )
                        else:
                            error = research_result.get("error", "Unknown error")
                            tool_result = ToolMessage(
                                content=f"Internal search failed: {error}",
                                tool_call_id=tool_id,
                            )

                    messages.append(tool_result)

            # Get final response after tool execution
            response = await llm.ainvoke(messages)

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
