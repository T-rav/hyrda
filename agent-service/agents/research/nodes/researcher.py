"""Researcher node - executes research tasks with tools."""

import logging
from typing import Any

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI

from config.settings import Settings

from ..state import ResearcherState
from ..tools import (
    EnhancedWebSearchTool,
    InternalSearchToolHTTP,  # HTTP-based retrieval via rag-service
    SECQueryTool,
)

logger = logging.getLogger(__name__)

# Initialize tools at module level to avoid blocking I/O in async context
# Tool __init__ methods do network calls (Redis, Tavily) which are blocking
_RESEARCH_TOOLS = [
    InternalSearchToolHTTP(),  # HTTP-based internal search via rag-service
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
        model=settings.llm.model, api_key=settings.llm.api_key, temperature=0.2
    )

    # Use pre-instantiated tools (initialized at module level to avoid blocking I/O)
    llm_with_tools = llm.bind_tools(_RESEARCH_TOOLS)

    # Create research prompt with internal-first priority
    if not researcher_messages:
        system_prompt = f"""You are an expert researcher. Your task:

**Task:** {current_task.description}
**Priority:** {current_task.priority}

🎯 **CRITICAL: Always check internal knowledge base FIRST**

**Research Workflow:**

1. **internal_search_tool** - ALWAYS START HERE
   - Search our internal knowledge base for existing information
   - Check for relevant documents, policies, past work, and historical context
   - Returns raw document chunks that you need to analyze and synthesize
   - **IMPORTANT**: The tool returns formatted document excerpts, NOT synthesized answers
   - Your job: Read the chunks, extract key information, and synthesize into coherent findings
   - Parameters:
     * `max_chunks`: Number of chunks to retrieve (1-20, default: 10)
     * `similarity_threshold`: Minimum relevance score (0.0-1.0, default: 0.7)

2. **sec_query** - For public company financial data (if relevant)
   - SEC filings: 10-K (annual reports), 8-K (material events), 10-Q (quarterly)
   - Use only when researching public companies
   - Provides authoritative financial and business information

3. **web_search** - For current external information
   - Recent news, trends, and developments
   - Industry analysis and expert opinions
   - Use when internal data is insufficient or outdated
   - **Search types:** "standard" (quick results) or "deep" (comprehensive analysis)

**How to Handle Tool Results:**

When internal_search_tool returns results:
- It provides document chunks with "Relationship status", source documents, and relevance scores
- You must READ and SYNTHESIZE these chunks yourself
- Extract key facts, identify patterns, and create coherent narrative
- Cite which documents your findings came from

**Research Best Practices:**

- **Start internal:** Always check internal knowledge base before going external
- **Synthesize chunks:** Read all document excerpts and combine insights into clear findings
- **Cross-reference:** When internal sources mention related topics/entities, search for those too
- **Combine sources:** Synthesize internal and external information for complete picture
- **Cite clearly:** Distinguish between internal sources, SEC filings, and web sources
- **Be thorough:** Gather multiple perspectives and verify information across sources

When you have comprehensive findings, summarize them clearly with proper source attribution.
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
