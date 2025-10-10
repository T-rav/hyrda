"""Researcher node for deep research workflow.

Individual researcher that executes specific research tasks using web search and scraping tools.
Includes comprehensive Langfuse tracing for observability.
"""

import logging

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from agents.company_profile import prompts
from agents.company_profile.configuration import ProfileConfiguration
from agents.company_profile.state import ResearcherState
from agents.company_profile.utils import (
    create_system_message,
    get_search_tool,
    think_tool,
)
from services.langfuse_service import get_langfuse_service

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

    logger.info(f"Researcher working on: {research_topic[:50]}...")

    # Start Langfuse span for researcher node
    langfuse_service = get_langfuse_service()
    span = None
    if langfuse_service and langfuse_service.client:
        span = langfuse_service.client.start_span(
            name="deep_research_researcher",
            input={
                "research_topic": research_topic,
                "profile_type": profile_type,
                "tool_call_iterations": tool_call_iterations,
            },
            metadata={
                "node_type": "researcher",
                "iteration": tool_call_iterations,
                "max_iterations": configuration.max_react_tool_calls,
            },
        )

    # Get LLM service and WebCat client from config
    llm_service = config.get("configurable", {}).get("llm_service")
    webcat_client = config.get("configurable", {}).get("webcat_client")

    if not llm_service:
        logger.error("No LLM service provided in config")
        if span:
            span.end(level="ERROR", status_message="No LLM service available")
        return Command(
            goto="compress_research",
            update={
                "compressed_research": "Error: No LLM service available",
                "raw_notes": [],
            },
        )

    # Prepare system prompt
    system_prompt = prompts.research_system_prompt.format(
        research_topic=research_topic,
        profile_type=profile_type,
        max_tool_calls=configuration.max_react_tool_calls,
        tool_call_iterations=tool_call_iterations,
    )

    # Get search tools
    search_tools = await get_search_tool(config, webcat_client)
    all_tools = [*search_tools, think_tool]

    # Prepare messages
    messages = list(state["researcher_messages"])
    if not messages or not any(
        hasattr(msg, "type") and msg.type == "system" for msg in messages
    ):
        messages.insert(0, create_system_message(system_prompt))

    # Call LLM with tools
    try:
        # Trace LLM generation
        if langfuse_service and langfuse_service.client:
            generation = langfuse_service.client.start_generation(
                name="researcher_llm_call",
                input={"messages": messages, "tools_available": len(all_tools)},
                metadata={
                    "research_topic": research_topic,
                    "iteration": tool_call_iterations,
                    "has_tools": bool(search_tools),
                },
            )

        response = await llm_service.get_response(
            messages=messages,
            tools=all_tools if search_tools else None,
        )

        # End LLM generation trace
        if langfuse_service and langfuse_service.client and "generation" in locals():
            generation.end(output={"response": response})

        # Check if response contains tool calls
        if isinstance(response, dict) and "tool_calls" in response:
            # Model wants to use tools
            messages.append(
                {
                    "role": "assistant",
                    "content": response.get("content", ""),
                    "tool_calls": response["tool_calls"],
                }
            )

            if span:
                span.end(
                    output={
                        "decision": "call_tools",
                        "tool_count": len(response["tool_calls"]),
                    }
                )

            return Command(
                goto="researcher_tools",
                update={
                    "researcher_messages": messages,
                    "tool_call_iterations": tool_call_iterations + 1,
                },
            )
        else:
            # Model provided final response, compress and return
            final_content = response if isinstance(response, str) else str(response)
            messages.append({"role": "assistant", "content": final_content})

            if span:
                span.end(
                    output={
                        "decision": "complete",
                        "response_length": len(final_content),
                    }
                )

            return Command(
                goto="compress_research",
                update={
                    "researcher_messages": messages,
                    "raw_notes": [final_content],
                },
            )

    except Exception as e:
        logger.error(f"Researcher error: {e}")
        if span:
            span.end(level="ERROR", status_message=str(e))
        return Command(
            goto="compress_research",
            update={
                "compressed_research": f"Research error: {str(e)}",
                "raw_notes": [],
            },
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

    # Get last message with tool calls
    last_message = messages[-1]
    if not isinstance(last_message, dict) or "tool_calls" not in last_message:
        logger.warning("No tool calls found in last message")
        return Command(goto="compress_research", update={"raw_notes": raw_notes})

    tool_calls = last_message["tool_calls"]

    # Check for ResearchComplete signal
    for tool_call in tool_calls:
        if tool_call.get("function", {}).get("name") == "ResearchComplete":
            logger.info("Research complete signal received")
            return Command(goto="compress_research", update={"raw_notes": raw_notes})

    # Check iteration limit
    if tool_call_iterations >= configuration.max_react_tool_calls:
        logger.info(f"Max iterations ({configuration.max_react_tool_calls}) reached")
        return Command(goto="compress_research", update={"raw_notes": raw_notes})

    # Execute tools
    webcat_client = config.get("configurable", {}).get("webcat_client")
    tool_results = []

    for tool_call in tool_calls:
        tool_name = tool_call.get("function", {}).get("name")
        tool_args = tool_call.get("function", {}).get("arguments", {})
        tool_id = tool_call.get("id", "unknown")

        logger.info(f"Executing tool: {tool_name}")

        if tool_name == "think_tool":
            # Execute reflection tool
            result = think_tool.invoke(tool_args)
            tool_results.append(
                {"role": "tool", "tool_call_id": tool_id, "content": str(result)}
            )

        elif tool_name == "web_search" and webcat_client:
            # Execute web search
            try:
                query = tool_args.get("query", "")
                max_results = tool_args.get("max_results", 5)

                # Trace tool execution
                langfuse_service = get_langfuse_service()
                if langfuse_service:
                    langfuse_service.trace_tool_execution(
                        tool_name="web_search",
                        tool_input={"query": query, "max_results": max_results},
                        tool_output={"status": "executing"},
                        metadata={
                            "context": "deep_research_researcher",
                            "research_topic": state["research_topic"],
                        },
                    )

                search_results = await webcat_client.search(query, max_results)

                # Trace results
                if langfuse_service:
                    langfuse_service.trace_tool_execution(
                        tool_name="web_search",
                        tool_input={"query": query, "max_results": max_results},
                        tool_output=search_results,
                        metadata={
                            "context": "deep_research_researcher",
                            "results_count": len(search_results),
                            "research_topic": state["research_topic"],
                        },
                    )

                # Format results
                result_text = f"Found {len(search_results)} results:\n\n"
                for i, result in enumerate(search_results, 1):
                    title = result.get("title", "No title")
                    url = result.get("url", "")
                    snippet = result.get("snippet", "No description")
                    result_text += f"{i}. **{title}**\n{snippet}\nSource: {url}\n\n"

                tool_results.append(
                    {"role": "tool", "tool_call_id": tool_id, "content": result_text}
                )
                raw_notes.append(result_text)

            except Exception as e:
                logger.error(f"Web search error: {e}")
                tool_results.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "content": f"Search error: {str(e)}",
                    }
                )

        elif tool_name == "scrape_url" and webcat_client:
            # Execute URL scraping
            try:
                url = tool_args.get("url", "")

                # Trace tool execution
                langfuse_service = get_langfuse_service()

                scrape_result = await webcat_client.scrape_url(url)

                if scrape_result.get("success"):
                    content = scrape_result.get("content", "")
                    title = scrape_result.get("title", "")

                    # Trace successful scrape
                    if langfuse_service:
                        langfuse_service.trace_tool_execution(
                            tool_name="scrape_url",
                            tool_input={"url": url},
                            tool_output={
                                "success": True,
                                "title": title,
                                "content_length": len(content),
                            },
                            metadata={
                                "context": "deep_research_researcher",
                                "research_topic": state["research_topic"],
                                "url": url,
                            },
                        )

                    result_text = f"# Scraped: {title}\n\nURL: {url}\n\n{content}\n\n"
                    tool_results.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "content": result_text,
                        }
                    )
                    raw_notes.append(result_text)
                    logger.info(f"Successfully scraped {len(content)} chars from {url}")
                else:
                    error = scrape_result.get("error", "Unknown error")

                    # Trace failed scrape
                    if langfuse_service:
                        langfuse_service.trace_tool_execution(
                            tool_name="scrape_url",
                            tool_input={"url": url},
                            tool_output={"success": False, "error": error},
                            metadata={
                                "context": "deep_research_researcher",
                                "research_topic": state["research_topic"],
                                "url": url,
                            },
                        )

                    tool_results.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "content": f"Scrape failed: {error}",
                        }
                    )
                    logger.warning(f"Scrape failed for {url}: {error}")

            except Exception as e:
                logger.error(f"Scrape URL error: {e}")
                tool_results.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "content": f"Scrape error: {str(e)}",
                    }
                )

        else:
            tool_results.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "content": f"Tool {tool_name} not available",
                }
            )

    # Add tool results to messages
    messages.extend(tool_results)

    # Continue researching
    return Command(
        goto="researcher",
        update={"researcher_messages": messages, "raw_notes": raw_notes},
    )
