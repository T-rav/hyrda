"""LangGraph workflow for company profile deep research.

Implements a hierarchical research system with supervisor and researcher subgraphs.
"""

import asyncio
import logging
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from agents.company_profile import prompts
from agents.company_profile.configuration import ProfileConfiguration
from agents.company_profile.state import (
    ConductResearch,
    ProfileAgentInputState,
    ProfileAgentState,
    ResearchComplete,
    ResearcherOutputState,
    ResearcherState,
    SupervisorState,
)
from agents.company_profile.utils import (
    create_human_message,
    create_system_message,
    detect_profile_type,
    format_research_context,
    get_search_tool,
    is_token_limit_exceeded,
    remove_up_to_last_ai_message,
    think_tool,
)

logger = logging.getLogger(__name__)


# ============================================================================
# RESEARCHER SUBGRAPH NODES
# ============================================================================


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

    # Get LLM service and WebCat client from config
    llm_service = config.get("configurable", {}).get("llm_service")
    webcat_client = config.get("configurable", {}).get("webcat_client")

    if not llm_service:
        logger.error("No LLM service provided in config")
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
        response = await llm_service.get_response(
            messages=messages,
            tools=all_tools if search_tools else None,
        )

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
                search_results = await webcat_client.search(query, max_results)

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
                scrape_result = await webcat_client.scrape_url(url)

                if scrape_result.get("success"):
                    content = scrape_result.get("content", "")
                    title = scrape_result.get("title", "")
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


async def compress_research(state: ResearcherState, config: RunnableConfig) -> dict:
    """Compress and synthesize research findings.

    Args:
        state: Current researcher state
        config: Runtime configuration

    Returns:
        Dict with compressed_research and raw_notes
    """
    configuration = ProfileConfiguration.from_runnable_config(config)
    research_topic = state["research_topic"]
    messages = state["researcher_messages"]
    raw_notes = state.get("raw_notes", [])

    logger.info(f"Compressing research for: {research_topic[:50]}...")

    # Get LLM service
    llm_service = config.get("configurable", {}).get("llm_service")
    if not llm_service:
        return {
            "compressed_research": "Error: No LLM service for compression",
            "raw_notes": raw_notes,
        }

    # Build compression prompt
    system_prompt = prompts.compress_research_system_prompt.format(
        research_topic=research_topic
    )

    # Create compression messages
    compression_messages = [
        create_system_message(system_prompt),
        create_human_message("\n\n".join([str(msg) for msg in messages[-5:]])),
    ]

    # Try compression with retry on token limits
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            response = await llm_service.get_response(
                messages=compression_messages,
                max_tokens=configuration.compression_model_max_tokens,
            )

            compressed = response if isinstance(response, str) else str(response)
            logger.info(f"Research compressed to {len(compressed)} characters")

            return {"compressed_research": compressed, "raw_notes": raw_notes}

        except Exception as e:
            if is_token_limit_exceeded(e, configuration.compression_model):
                logger.warning(f"Token limit on compression attempt {attempt + 1}")
                compression_messages = remove_up_to_last_ai_message(
                    compression_messages
                )
                continue
            logger.error(f"Compression error: {e}")
            break

    # Fallback: return raw notes
    return {
        "compressed_research": "Compression failed. Raw notes: "
        + "\n".join(raw_notes[:3]),
        "raw_notes": raw_notes,
    }


# ============================================================================
# SUPERVISOR SUBGRAPH NODES
# ============================================================================


async def supervisor(state: SupervisorState, config: RunnableConfig) -> Command[str]:
    """Supervisor node - delegates research tasks to researchers.

    Args:
        state: Current supervisor state
        config: Runtime configuration

    Returns:
        Command to proceed to supervisor_tools
    """
    configuration = ProfileConfiguration.from_runnable_config(config)
    research_iterations = state.get("research_iterations", 0)
    research_brief = state["research_brief"]
    notes = state.get("notes", [])
    profile_type = state.get("profile_type", "company")

    logger.info(f"Supervisor iteration {research_iterations}")

    # Get LLM service
    llm_service = config.get("configurable", {}).get("llm_service")
    if not llm_service:
        logger.error("No LLM service in supervisor")
        return Command(goto=END, update={})

    # Build supervisor prompt
    system_prompt = prompts.lead_researcher_prompt.format(
        research_brief=research_brief,
        profile_type=profile_type,
        max_concurrent_research=configuration.max_concurrent_research_units,
        max_iterations=configuration.max_researcher_iterations,
        research_iterations=research_iterations,
        notes_count=len(notes),
    )

    # Prepare messages
    messages = list(state["supervisor_messages"])
    if not messages or not any(
        hasattr(msg, "type") and msg.type == "system" for msg in messages
    ):
        messages.insert(0, create_system_message(system_prompt))

    # Define tools for supervisor
    tools = [ConductResearch, ResearchComplete, think_tool]

    # Call LLM with tools
    try:
        response = await llm_service.get_response(
            messages=messages,
            tools=tools,
        )

        # Check if response contains tool calls
        if isinstance(response, dict) and "tool_calls" in response:
            messages.append(
                {
                    "role": "assistant",
                    "content": response.get("content", ""),
                    "tool_calls": response["tool_calls"],
                }
            )

            return Command(
                goto="supervisor_tools",
                update={
                    "supervisor_messages": messages,
                    "research_iterations": research_iterations + 1,
                },
            )
        else:
            # No tool calls, end supervision
            final_content = response if isinstance(response, str) else str(response)
            messages.append({"role": "assistant", "content": final_content})

            return Command(
                goto=END,
                update={"supervisor_messages": messages},
            )

    except Exception as e:
        logger.error(f"Supervisor error: {e}")
        return Command(goto=END, update={})


async def supervisor_tools(
    state: SupervisorState, config: RunnableConfig
) -> Command[str]:
    """Execute supervisor tools - primarily ConductResearch delegation.

    Args:
        state: Current supervisor state
        config: Runtime configuration

    Returns:
        Command to return to supervisor or END
    """
    configuration = ProfileConfiguration.from_runnable_config(config)
    messages = state["supervisor_messages"]
    notes = list(state.get("notes", []))
    raw_notes = list(state.get("raw_notes", []))
    research_iterations = state["research_iterations"]
    profile_type = state.get("profile_type", "company")

    # Get last message with tool calls
    last_message = messages[-1]
    if not isinstance(last_message, dict) or "tool_calls" not in last_message:
        logger.warning("No tool calls in supervisor message")
        return Command(goto=END, update={})

    tool_calls = last_message["tool_calls"]

    # Check for ResearchComplete
    for tool_call in tool_calls:
        if tool_call.get("function", {}).get("name") == "ResearchComplete":
            logger.info("Supervisor signaled research complete")
            return Command(goto=END, update={})

    # Check iteration limit
    if research_iterations >= configuration.max_researcher_iterations:
        logger.info(
            f"Max supervisor iterations ({configuration.max_researcher_iterations}) reached"
        )
        return Command(goto=END, update={})

    # Process ConductResearch calls
    conduct_research_calls = [
        tc
        for tc in tool_calls
        if tc.get("function", {}).get("name") == "ConductResearch"
    ]

    # Limit concurrent research
    conduct_research_calls = conduct_research_calls[
        : configuration.max_concurrent_research_units
    ]

    # Execute think_tool calls synchronously
    tool_results = []
    for tool_call in tool_calls:
        tool_name = tool_call.get("function", {}).get("name")
        if tool_name == "think_tool":
            tool_args = tool_call.get("function", {}).get("arguments", {})
            tool_id = tool_call.get("id", "unknown")
            result = think_tool.invoke(tool_args)
            tool_results.append(
                {"role": "tool", "tool_call_id": tool_id, "content": str(result)}
            )

    # Execute research tasks in parallel
    if conduct_research_calls:
        logger.info(f"Delegating {len(conduct_research_calls)} research tasks")

        # Build researcher subgraph
        researcher_graph = build_researcher_subgraph()

        # Create tasks for parallel execution
        research_tasks = []
        for tool_call in conduct_research_calls:
            research_topic = (
                tool_call.get("function", {})
                .get("arguments", {})
                .get("research_topic", "")
            )
            tool_id = tool_call.get("id", "unknown")

            task = execute_researcher(
                researcher_graph,
                research_topic,
                profile_type,
                tool_id,
                config,
            )
            research_tasks.append(task)

        # Execute in parallel
        research_results = await asyncio.gather(*research_tasks)

        # Process results
        for result in research_results:
            tool_results.append(result["tool_result"])
            if result["compressed_research"]:
                notes.append(result["compressed_research"])
            if result["raw_notes"]:
                raw_notes.extend(result["raw_notes"])

    # Add tool results to messages
    messages.extend(tool_results)

    # Continue supervision
    return Command(
        goto="supervisor",
        update={
            "supervisor_messages": messages,
            "notes": notes,
            "raw_notes": raw_notes,
        },
    )


async def execute_researcher(
    researcher_graph: CompiledStateGraph,
    research_topic: str,
    profile_type: str,
    tool_id: str,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Execute a single researcher task.

    Args:
        researcher_graph: Compiled researcher subgraph
        research_topic: Topic to research
        profile_type: Type of profile
        tool_id: Tool call ID for result mapping
        config: Runtime configuration

    Returns:
        Dict with tool_result, compressed_research, and raw_notes
    """
    try:
        result = await researcher_graph.ainvoke(
            {
                "researcher_messages": [create_human_message(research_topic)],
                "research_topic": research_topic,
                "tool_call_iterations": 0,
                "compressed_research": "",
                "raw_notes": [],
                "profile_type": profile_type,
            },
            config,
        )

        compressed = result.get("compressed_research", "")
        raw = result.get("raw_notes", [])

        return {
            "tool_result": {
                "role": "tool",
                "tool_call_id": tool_id,
                "content": compressed or "No research results",
            },
            "compressed_research": compressed,
            "raw_notes": raw,
        }

    except Exception as e:
        logger.error(f"Researcher task error: {e}")
        return {
            "tool_result": {
                "role": "tool",
                "tool_call_id": tool_id,
                "content": f"Research error: {str(e)}",
            },
            "compressed_research": "",
            "raw_notes": [],
        }


# ============================================================================
# MAIN GRAPH NODES
# ============================================================================


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

    llm_service = config.get("configurable", {}).get("llm_service")
    if not llm_service:
        logger.error("No LLM service for research brief")
        return Command(
            goto=END, update={"final_report": "Error: No LLM service available"}
        )

    # Generate research brief
    try:
        prompt = prompts.transform_messages_into_research_topic_prompt.format(
            query=query, profile_type=profile_type
        )
        response = await llm_service.get_response(
            messages=[create_human_message(prompt)],
        )

        research_brief = response if isinstance(response, str) else str(response)
        logger.info(f"Research brief generated: {len(research_brief)} characters")

        # Initialize supervisor messages
        supervisor_init_msg = create_human_message(research_brief)

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
        return Command(
            goto=END,
            update={"final_report": f"Error generating research plan: {str(e)}"},
        )


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

    if not notes:
        return {"final_report": "No research findings available to generate report."}

    # Get LLM service
    llm_service = config.get("configurable", {}).get("llm_service")
    if not llm_service:
        return {"final_report": "Error: No LLM service for final report"}

    # Format research context
    notes_text = format_research_context(research_brief, notes, profile_type)

    # Build final report prompt
    system_prompt = prompts.final_report_generation_prompt.format(
        profile_type=profile_type, notes=notes_text
    )

    # Try generation with retry on token limits
    max_attempts = 3
    messages = [
        create_system_message(system_prompt),
        create_human_message("Generate the comprehensive profile report now."),
    ]

    for attempt in range(max_attempts):
        try:
            response = await llm_service.get_response(
                messages=messages,
                max_tokens=configuration.final_report_model_max_tokens,
            )

            final_report = response if isinstance(response, str) else str(response)
            logger.info(f"Final report generated: {len(final_report)} characters")

            return {"final_report": final_report}

        except Exception as e:
            if is_token_limit_exceeded(e, configuration.final_report_model):
                logger.warning(f"Token limit on final report attempt {attempt + 1}")
                messages = remove_up_to_last_ai_message(messages)
                continue
            logger.error(f"Final report error: {e}")
            break

    # Fallback: return notes summary
    return {
        "final_report": "# Profile Report (Partial)\n\nUnable to generate full report. Research findings:\n\n"
        + "\n\n".join(notes[:3])
    }


# ============================================================================
# GRAPH BUILDERS
# ============================================================================


def build_researcher_subgraph() -> CompiledStateGraph:
    """Build and compile the researcher subgraph.

    Returns:
        Compiled researcher subgraph
    """
    researcher_builder = StateGraph(ResearcherState, output=ResearcherOutputState)

    # Add nodes
    researcher_builder.add_node("researcher", researcher)
    researcher_builder.add_node("researcher_tools", researcher_tools)
    researcher_builder.add_node("compress_research", compress_research)

    # Add edges
    researcher_builder.add_edge(START, "researcher")
    researcher_builder.add_edge("compress_research", END)

    # Compile and return
    return researcher_builder.compile()


def build_supervisor_subgraph() -> CompiledStateGraph:
    """Build and compile the supervisor subgraph.

    Returns:
        Compiled supervisor subgraph
    """
    supervisor_builder = StateGraph(SupervisorState)

    # Add nodes
    supervisor_builder.add_node("supervisor", supervisor)
    supervisor_builder.add_node("supervisor_tools", supervisor_tools)

    # Add edges
    supervisor_builder.add_edge(START, "supervisor")

    # Compile and return
    return supervisor_builder.compile()


def build_profile_researcher() -> CompiledStateGraph:
    """Build and compile the main profile researcher graph.

    Returns:
        Compiled profile researcher graph
    """
    # Build subgraphs
    supervisor_subgraph = build_supervisor_subgraph()

    # Build main graph
    profile_builder = StateGraph(ProfileAgentState, input=ProfileAgentInputState)

    # Add nodes
    profile_builder.add_node("clarify_with_user", clarify_with_user)
    profile_builder.add_node("write_research_brief", write_research_brief)
    profile_builder.add_node("research_supervisor", supervisor_subgraph)
    profile_builder.add_node("final_report_generation", final_report_generation)

    # Add edges
    profile_builder.add_edge(START, "clarify_with_user")
    profile_builder.add_edge("research_supervisor", "final_report_generation")
    profile_builder.add_edge("final_report_generation", END)

    # Compile and return
    return profile_builder.compile()


# Create the main graph instance
profile_researcher = build_profile_researcher()

logger.info("Profile researcher graph compiled successfully")
