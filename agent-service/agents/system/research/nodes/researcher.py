"""Researcher node - executes research tasks with tools."""

import logging
from typing import Any

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI

from config.settings import Settings

from ..state import ResearcherState
from ..tools import (
    EnhancedWebSearchTool,
    InternalSearchTool,
    SECQueryTool,
)

logger = logging.getLogger(__name__)

# Initialize tools at module level to avoid blocking I/O in async context
# Tool __init__ methods do network calls (Qdrant, Redis) which are blocking
_RESEARCH_TOOLS = [
    InternalSearchTool(),  # Qdrant client initialization (blocking)
    SECQueryTool(),  # Redis client initialization (blocking)
    EnhancedWebSearchTool(),  # Tavily client initialization (blocking)
]


async def researcher(state: ResearcherState) -> dict[str, Any]:
    """Execute research task with tool calling.

    Args:
        state: Researcher state with current task

    Returns:
        Updated state with tool calls or findings
    """
    current_task = state["current_task"]
    researcher_messages = state.get("researcher_messages", [])
    tool_call_iterations = state.get("tool_call_iterations", 0)

    logger.info(f"Researcher working on: {current_task.description[:60]}...")

    # Initialize LLM
    settings = Settings()
    llm = ChatOpenAI(
        model=settings.llm.model,
        api_key=settings.llm.api_key,
        temperature=0.2
    )

    # Use pre-instantiated tools (initialized at module level to avoid blocking I/O)
    llm_with_tools = llm.bind_tools(_RESEARCH_TOOLS)

    # Create research prompt with internal-first priority
    if not researcher_messages:
        system_prompt = f"""You are an expert researcher. Your task:

**Task:** {current_task.description}
**Priority:** {current_task.priority}

🎯 **CRITICAL: Always check internal knowledge base FIRST**

**Tool Priority (use in this order):**

1. **internal_search** - ALWAYS START HERE
   - Check for existing relationships (companies, people, past work)
   - Search internal knowledge base for relevant context
   - If found, include in your research

2. **sec_query** / **sec_research** - For company research
   - SEC 10-K (annual reports), 8-K (material events)
   - Financial data, risk factors, strategic priorities
   - Executive changes, acquisitions, partnerships

3. **web_search** - For current information
   - Recent news, trends, market data
   - Use when internal data is outdated or missing

**Important:**
- If internal data mentions companies/people, always check internal_search for relationships
- Combine internal and external sources for comprehensive view
- Cite sources clearly (internal vs SEC vs web)

Be thorough and gather multiple perspectives. When you have comprehensive findings, summarize them clearly with proper attribution.
"""
        researcher_messages = [HumanMessage(content=system_prompt)]

    try:
        # Invoke LLM with tools
        response = await llm_with_tools.ainvoke(researcher_messages)

        # Add response to messages
        researcher_messages.append(response)

        # Check if tool calls exist
        if hasattr(response, "tool_calls") and response.tool_calls:
            logger.info(f"Researcher making {len(response.tool_calls)} tool calls")
            return {
                "researcher_messages": researcher_messages,
                "tool_call_iterations": tool_call_iterations + 1,
            }
        else:
            # No more tool calls, extract findings
            findings = response.content
            logger.info(f"Research complete: {findings[:100]}...")
            return {
                "findings": findings,
                "researcher_messages": researcher_messages,
                "raw_data": [findings],
            }

    except Exception as e:
        logger.error(f"Error in researcher: {e}")
        return {
            "findings": f"Error during research: {str(e)}",
            "researcher_messages": researcher_messages,
        }


async def researcher_tools(state: ResearcherState) -> dict[str, Any]:
    """Execute tool calls from researcher.

    Args:
        state: Researcher state with pending tool calls

    Returns:
        Updated state with tool results
    """
    researcher_messages = state["researcher_messages"]
    last_message = researcher_messages[-1]

    # Extract tool calls
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {"researcher_messages": researcher_messages}

    # Execute each tool call
    tool_messages = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]

        logger.info(f"Executing tool: {tool_name}")

        try:
            # Execute tool (would actually call the tool here)
            # For now, return placeholder
            result = f"Tool {tool_name} executed successfully"

            tool_messages.append(
                ToolMessage(
                    content=result,
                    tool_call_id=tool_call["id"],
                )
            )
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}")
            tool_messages.append(
                ToolMessage(
                    content=f"Error: {str(e)}",
                    tool_call_id=tool_call["id"],
                )
            )

    # Add tool results to messages
    researcher_messages.extend(tool_messages)

    return {"researcher_messages": researcher_messages}
