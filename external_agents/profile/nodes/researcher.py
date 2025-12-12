"""Researcher node for deep research workflow.

Individual researcher that executes specific research tasks using web search and scraping tools.
Includes comprehensive Langfuse tracing for observability.

REFACTORED VERSION: Giant researcher_tools function broken into focused helper functions.
"""

import logging
from datetime import datetime

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.types import Command

from .. import prompts
from ..configuration import ProfileConfiguration
from ..state import ResearcherState
from ..utils import (
    create_system_message,
    internal_search_tool,
    search_tool,
    sec_query_tool,
    think_tool,
)
from config.settings import Settings
from .services.search_clients import get_perplexity_client, get_tavily_client

logger = logging.getLogger(__name__)


async def researcher(state: ResearcherState, config: RunnableConfig) -> Command[str]:
    """Individual researcher node - executes specific research task.

    Args:
        state: Current researcher state
        config: Runtime configuration

    Returns:
        Command to proceed to researcher_tools or compress_research
    """
    configuration = ProfileConfiguration.from_runnable_config(config)
    tool_call_iterations = state.get("tool_call_iterations", 0)
    research_topic = state["research_topic"]
    profile_type = state.get("profile_type", "company")
    focus_area = state.get("focus_area", "")

    if focus_area:
        logger.info(
            f"Researcher working on: {research_topic[:50]}... (Focus: {focus_area})"
        )
    else:
        logger.info(f"Researcher working on: {research_topic[:50]}...")

    # Use LangChain ChatOpenAI directly
    settings = Settings()
    llm = ChatOpenAI(
        model=settings.llm.model,
        api_key=settings.llm.api_key,
        temperature=0.7,
    )

    # Prepare system prompt with focus area
    current_date = datetime.now().strftime("%B %d, %Y")

    # Build focus guidance for researcher
    if focus_area:
        focus_guidance = f"""
**PRIORITY RESEARCH FOCUS**: The user specifically wants information about "{focus_area}".

**Your Research Strategy:**
- While investigating your assigned questions, ALWAYS consider how they relate to {focus_area}
- If you find information directly relevant to {focus_area}, dig deeper with additional searches
- Connect your findings back to {focus_area} in your notes
- Prioritize sources and angles that reveal insights about {focus_area}"""
    else:
        focus_guidance = ""

    system_prompt = prompts.research_system_prompt.format(
        research_topic=research_topic,
        profile_type=profile_type,
        focus_area=focus_area if focus_area else "None (general profile)",
        focus_guidance=focus_guidance,
        max_tool_calls=configuration.max_react_tool_calls,
        tool_call_iterations=tool_call_iterations,
        current_date=current_date,
    )

    # Get search tools
    search_tools = await search_tool(
        config,
        perplexity_enabled=settings.search.perplexity_enabled,
    )

    # Get internal search tool
    internal_search = internal_search_tool()

    # Get SEC query tool
    sec_query = sec_query_tool()

    # Build tool list
    all_tools = [*search_tools, think_tool]
    if internal_search:
        all_tools.append(internal_search)
    if sec_query:
        all_tools.append(sec_query)

    # Prepare messages
    messages = list(state["researcher_messages"])
    if not messages or not any(
        hasattr(msg, "type") and msg.type == "system" for msg in messages
    ):
        messages.insert(0, create_system_message(system_prompt))

    # Call LLM with tools
    try:
        if all_tools:
            llm_with_tools = llm.bind_tools(all_tools)
            response = await llm_with_tools.ainvoke(messages)
        else:
            response = await llm.ainvoke(messages)

        # Check if response contains tool calls
        if hasattr(response, "tool_calls") and response.tool_calls:
            messages.append(response)

            return Command(
                goto="researcher_tools",
                update={
                    "researcher_messages": messages,
                    "tool_call_iterations": tool_call_iterations + 1,
                },
            )
        else:
            final_content = (
                response.content if hasattr(response, "content") else str(response)
            )
            messages.append(response)

            return Command(
                goto="compress_research",
                update={
                    "researcher_messages": messages,
                    "raw_notes": [final_content],
                },
            )

    except Exception as e:
        logger.error(f"Researcher error: {e}")
        return Command(
            goto="compress_research",
            update={
                "compressed_research": f"Research error: {str(e)}",
                "raw_notes": [],
            },
        )


# Helper functions for tool execution


def _execute_think_tool(tool_args: dict, tool_id: str) -> ToolMessage:
    """Execute think/reflection tool.

    Args:
        tool_args: Tool arguments
        tool_id: Tool call ID

    Returns:
        ToolMessage with result
    """
    result = think_tool.invoke(tool_args)
    return ToolMessage(content=str(result), tool_call_id=tool_id)


async def _execute_sec_query(
    tool_args: dict, tool_id: str
) -> tuple[ToolMessage, str | None]:
    """Execute SEC query tool.

    Args:
        tool_args: Tool arguments
        tool_id: Tool call ID

    Returns:
        Tuple of (ToolMessage, optional note to append)
    """
    try:
        sec_query = sec_query_tool()

        if not sec_query:
            return (
                ToolMessage(
                    content="SEC query tool not available",
                    tool_call_id=tool_id,
                ),
                None,
            )

        result = await sec_query.ainvoke(tool_args)
        logger.info("SEC query completed")
        return ToolMessage(content=result, tool_call_id=tool_id), result

    except Exception as e:
        logger.error(f"SEC query error: {e}")
        return (
            ToolMessage(
                content=f"SEC query error: {str(e)}",
                tool_call_id=tool_id,
            ),
            None,
        )


async def _execute_internal_search(
    tool_args: dict, tool_id: str, state: ResearcherState
) -> tuple[ToolMessage, str | None]:
    """Execute internal knowledge base search.

    Args:
        tool_args: Tool arguments
        tool_id: Tool call ID
        state: Researcher state

    Returns:
        Tuple of (ToolMessage, optional note to append)
    """
    try:
        internal_search = internal_search_tool()

        if not internal_search:
            logger.info(
                "Internal search tool not available - vector DB may be disabled"
            )
            return (
                ToolMessage(
                    content="Internal search service not available (vector database not configured)",
                    tool_call_id=tool_id,
                ),
                None,
            )

        # Add profile_type from state to tool args
        tool_args_with_profile = {
            **tool_args,
            "profile_type": state.get("profile_type", "company"),
        }

        result_text = await internal_search.ainvoke(tool_args_with_profile)
        logger.info("Internal search completed")
        return ToolMessage(content=result_text, tool_call_id=tool_id), result_text

    except Exception as e:
        logger.error(f"Internal search error: {e}")
        return (
            ToolMessage(
                content=f"Internal search error: {str(e)}",
                tool_call_id=tool_id,
            ),
            None,
        )


async def _execute_web_search(
    tool_args: dict, tool_id: str, tavily_client
) -> tuple[ToolMessage, str | None]:
    """Execute web search via Tavily.

    Args:
        tool_args: Tool arguments
        tool_id: Tool call ID
        tavily_client: Tavily client instance

    Returns:
        Tuple of (ToolMessage, optional note to append)
    """
    try:
        query = tool_args.get("query", "")
        max_results = tool_args.get("max_results", 10)

        search_results = await tavily_client.search(query, max_results)

        # Format results
        result_text = f"Found {len(search_results)} results:\n\n"
        for i, result in enumerate(search_results, 1):
            title = result.get("title", "No title")
            url = result.get("url", "")
            snippet = result.get("snippet", "No description")
            result_text += f"{i}. **{title}**\n{snippet}\nSource: {url}\n\n"

        return ToolMessage(content=result_text, tool_call_id=tool_id), result_text

    except Exception as e:
        logger.error(f"Web search error: {e}")
        return (
            ToolMessage(content=f"Search error: {str(e)}", tool_call_id=tool_id),
            None,
        )


async def _execute_scrape_url(
    tool_args: dict, tool_id: str, tavily_client
) -> tuple[ToolMessage, str | None]:
    """Execute URL scraping via Tavily.

    Args:
        tool_args: Tool arguments
        tool_id: Tool call ID
        tavily_client: Tavily client instance

    Returns:
        Tuple of (ToolMessage, optional note to append)
    """
    try:
        url = tool_args.get("url", "")

        scrape_result = await tavily_client.scrape_url(url)

        if scrape_result.get("success"):
            content = scrape_result.get("content", "")
            title = scrape_result.get("title", "")

            result_text = f"# Scraped: {title}\n\nURL: {url}\n\n{content}\n\n"
            logger.info(f"Successfully scraped {len(content)} chars from {url}")
            return ToolMessage(content=result_text, tool_call_id=tool_id), result_text
        else:
            error = scrape_result.get("error", "Unknown error")
            logger.warning(f"Scrape failed for {url}: {error}")
            return (
                ToolMessage(content=f"Scrape failed: {error}", tool_call_id=tool_id),
                None,
            )

    except Exception as e:
        logger.error(f"Scrape URL error: {e}")
        return (
            ToolMessage(content=f"Scrape error: {str(e)}", tool_call_id=tool_id),
            None,
        )


async def _execute_deep_research(
    tool_args: dict, tool_id: str, perplexity_client
) -> tuple[ToolMessage, str | None]:
    """Execute deep research via Perplexity.

    Args:
        tool_args: Tool arguments
        tool_id: Tool call ID
        perplexity_client: Perplexity client instance

    Returns:
        Tuple of (ToolMessage, optional note to append)
    """
    try:
        query = tool_args.get("query", "")

        logger.info(f"Starting deep_research: {query[:100]}...")
        research_result = await perplexity_client.deep_research(query)

        logger.info(
            f"Deep research result type: {type(research_result)}, "
            f"keys: {list(research_result.keys()) if isinstance(research_result, dict) else 'NOT A DICT'}"
        )

        if research_result.get("success") or research_result.get("answer"):
            answer = research_result.get("answer", "")
            sources = research_result.get("sources", [])

            logger.info(
                f"Sources type: {type(sources)}, "
                f"count: {len(sources) if isinstance(sources, list) else 'NOT A LIST'}, "
                f"first source type: {type(sources[0]) if sources else 'EMPTY'}"
            )

            # Format answer with sources
            result_text = f"# Deep Research Results\n\n{answer}\n\n"
            if sources:
                result_text += "### Sources\n"
                for idx, source in enumerate(sources[:10], 1):
                    if isinstance(source, str):
                        result_text += f"{idx}. {source} - Deep Research Results\n"
                    elif isinstance(source, dict):
                        url = source.get("url", "")
                        title = source.get("title", "Untitled")
                        result_text += (
                            f"{idx}. {url} - Deep Research Results: {title}\n"
                        )
                    else:
                        logger.warning(f"Unexpected source type: {type(source)}")
                        result_text += f"{idx}. {str(source)} - Deep Research Results\n"

            logger.info(
                f"Deep research completed: {len(answer)} chars, {len(sources)} sources"
            )
            return ToolMessage(content=result_text, tool_call_id=tool_id), result_text
        else:
            error = research_result.get("error", "Unknown error")
            logger.warning(f"Deep research failed for {query[:100]}: {error}")
            return (
                ToolMessage(
                    content=f"Deep research failed: {error}",
                    tool_call_id=tool_id,
                ),
                None,
            )

    except Exception as e:
        logger.error(f"Deep research error: {e}")
        return (
            ToolMessage(content=f"Deep research error: {str(e)}", tool_call_id=tool_id),
            None,
        )


async def researcher_tools(
    state: ResearcherState, config: RunnableConfig
) -> Command[str]:
    """Execute tools called by researcher.

    Args:
        state: Current researcher state
        config: Runtime configuration

    Returns:
        Command to return to researcher or proceed to compression
    """
    configuration = ProfileConfiguration.from_runnable_config(config)
    messages = state["researcher_messages"]
    tool_call_iterations = state["tool_call_iterations"]
    raw_notes = list(state.get("raw_notes", []))

    # Validate tool calls
    last_message = messages[-1]
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        logger.warning("No tool calls found in last message")
        return Command(goto="compress_research", update={"raw_notes": raw_notes})

    tool_calls = last_message.tool_calls

    # Check for completion signal
    for tool_call in tool_calls:
        if tool_call.get("name") == "ResearchComplete":
            logger.info("Research complete signal received")
            return Command(goto="compress_research", update={"raw_notes": raw_notes})

    # Check iteration limit
    if tool_call_iterations >= configuration.max_react_tool_calls:
        logger.info(f"Max iterations ({configuration.max_react_tool_calls}) reached")
        return Command(goto="compress_research", update={"raw_notes": raw_notes})

    # Initialize search clients
    tavily_client = get_tavily_client()
    perplexity_client = get_perplexity_client()
    tool_results = []

    # Execute each tool call
    for tool_call in tool_calls:
        tool_name = tool_call.get("name")
        tool_args = tool_call.get("args", {})
        tool_id = tool_call.get("id", "unknown")

        logger.info(f"Executing tool: {tool_name}")

        # Dispatch to appropriate handler
        if tool_name == "think_tool":
            result = _execute_think_tool(tool_args, tool_id)
            tool_results.append(result)

        elif tool_name == "sec_query":
            result, note = await _execute_sec_query(tool_args, tool_id)
            tool_results.append(result)
            if note:
                raw_notes.append(note)

        elif tool_name == "internal_search_tool":
            result, note = await _execute_internal_search(tool_args, tool_id, state)
            tool_results.append(result)
            if note:
                raw_notes.append(note)

        elif tool_name == "web_search" and tavily_client:
            result, note = await _execute_web_search(tool_args, tool_id, tavily_client)
            tool_results.append(result)
            if note:
                raw_notes.append(note)

        elif tool_name == "scrape_url" and tavily_client:
            result, note = await _execute_scrape_url(tool_args, tool_id, tavily_client)
            tool_results.append(result)
            if note:
                raw_notes.append(note)

        elif tool_name == "deep_research" and perplexity_client:
            result, note = await _execute_deep_research(
                tool_args, tool_id, perplexity_client
            )
            tool_results.append(result)
            if note:
                raw_notes.append(note)

        else:
            tool_results.append(
                ToolMessage(
                    content=f"Tool {tool_name} not available", tool_call_id=tool_id
                )
            )

    # Add tool results to messages
    messages.extend(tool_results)

    # Continue researching
    return Command(
        goto="researcher",
        update={"researcher_messages": messages, "raw_notes": raw_notes},
    )
