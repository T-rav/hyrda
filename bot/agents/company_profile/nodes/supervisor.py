"""Supervisor nodes for deep research workflow.

Supervisor delegates research tasks to researchers and coordinates parallel execution.
Includes Langfuse tracing for observability.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from agents.company_profile import prompts
from agents.company_profile.configuration import ProfileConfiguration
from agents.company_profile.state import (
    ConductResearch,
    ResearchComplete,
    SupervisorState,
)
from agents.company_profile.utils import (
    create_human_message,
    create_system_message,
    think_tool,
)
from services.langfuse_service import get_langfuse_service

logger = logging.getLogger(__name__)


async def supervisor(state: SupervisorState, config: RunnableConfig) -> Command[str]:
    """Supervisor node - delegates research tasks to researchers.

    Args:
        state: Current supervisor state
        config: Runtime configuration

    Returns:
        Command to proceed to supervisor_tools or END
    """
    configuration = ProfileConfiguration.from_runnable_config(config)
    research_iterations = state.get("research_iterations", 0)
    research_brief = state.get("research_brief", "")
    notes = state.get("notes", [])
    profile_type = state.get("profile_type", "company")

    # Validate research_brief exists
    if not research_brief:
        logger.error("research_brief is missing or empty in supervisor state")
        return Command(
            goto=END,
            update={"final_report": "Error: research brief not found in state"},
        )

    logger.info(f"Supervisor iteration {research_iterations}")

    # Start Langfuse span for supervisor
    langfuse_service = get_langfuse_service()
    span = None
    if langfuse_service and langfuse_service.client:
        span = langfuse_service.client.start_span(
            name="deep_research_supervisor",
            input={
                "research_brief": research_brief[:200],
                "profile_type": profile_type,
                "research_iterations": research_iterations,
                "notes_count": len(notes),
            },
            metadata={
                "node_type": "supervisor",
                "iteration": research_iterations,
                "max_iterations": configuration.max_researcher_iterations,
            },
        )

    # Get LLM configuration from config
    from langchain_openai import ChatOpenAI

    from config.settings import Settings

    settings = Settings()

    # Create ChatOpenAI instance with tool binding
    llm = ChatOpenAI(
        model=settings.llm.model,
        api_key=settings.llm.api_key,
        temperature=0.7,
    )

    # Build supervisor prompt
    current_date = datetime.now().strftime("%B %d, %Y")
    system_prompt = prompts.lead_researcher_prompt.format(
        research_brief=research_brief,
        profile_type=profile_type,
        max_concurrent_research=configuration.max_concurrent_research_units,
        max_iterations=configuration.max_researcher_iterations,
        research_iterations=research_iterations,
        notes_count=len(notes),
        current_date=current_date,
    )

    # Prepare messages
    messages = list(state["supervisor_messages"])
    if not messages or not any(
        hasattr(msg, "type") and msg.type == "system" for msg in messages
    ):
        messages.insert(0, create_system_message(system_prompt))

    # Define tools for supervisor
    tools = [ConductResearch, ResearchComplete, think_tool]

    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(tools)

    # Call LLM with tools
    try:
        # Trace LLM generation
        generation = None
        if langfuse_service and langfuse_service.client:
            generation = langfuse_service.client.start_generation(
                name="supervisor_llm_call",
                input={
                    "messages": [str(m)[:100] for m in messages],
                    "tools_available": len(tools),
                },
                metadata={
                    "research_brief": research_brief[:200],
                    "iteration": research_iterations,
                    "notes_count": len(notes),
                },
            )

        # Invoke LLM with tools
        response = await llm_with_tools.ainvoke(messages)

        # End generation trace
        if generation:
            generation.end()

        # Check if response contains tool calls (LangChain AIMessage format)
        if hasattr(response, "tool_calls") and response.tool_calls:
            # Add AI message to history
            messages.append(response)

            if span:
                span.end()

            return Command(
                goto="supervisor_tools",
                update={
                    "supervisor_messages": messages,
                    "research_iterations": research_iterations + 1,
                },
            )
        else:
            # No tool calls, end supervision
            messages.append(response)

            if span:
                span.end()

            return Command(
                goto=END,
                update={"supervisor_messages": messages},
            )

    except Exception as e:
        logger.error(f"Supervisor error: {e}")
        if generation:
            generation.end(level="ERROR", status_message=str(e))
        if span:
            span.end(level="ERROR", status_message=str(e))
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
    from agents.company_profile.nodes.graph_builder import build_researcher_subgraph

    configuration = ProfileConfiguration.from_runnable_config(config)
    messages = state["supervisor_messages"]
    notes = list(state.get("notes", []))
    raw_notes = list(state.get("raw_notes", []))
    research_iterations = state["research_iterations"]
    profile_type = state.get("profile_type", "company")

    # Start Langfuse span for supervisor tools
    langfuse_service = get_langfuse_service()
    span = None
    if langfuse_service and langfuse_service.client:
        span = langfuse_service.client.start_span(
            name="deep_research_supervisor_tools",
            input={
                "research_iterations": research_iterations,
                "notes_count": len(notes),
            },
            metadata={
                "node_type": "supervisor_tools",
                "iteration": research_iterations,
            },
        )

    # Get last message with tool calls (LangChain AIMessage)
    last_message = messages[-1]
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        logger.warning("No tool calls in supervisor message")
        if span:
            span.end()
        return Command(goto=END, update={})

    tool_calls = last_message.tool_calls

    # Check for ResearchComplete
    for tool_call in tool_calls:
        if tool_call.get("name") == "ResearchComplete":
            logger.info("Supervisor signaled research complete")
            if span:
                span.end()
            return Command(goto=END, update={})

    # Check iteration limit
    if research_iterations >= configuration.max_researcher_iterations:
        logger.info(
            f"Max supervisor iterations ({configuration.max_researcher_iterations}) reached"
        )
        if span:
            span.end()
        return Command(goto=END, update={})

    # Process ConductResearch calls (LangChain format)
    conduct_research_calls = [
        tc for tc in tool_calls if tc.get("name") == "ConductResearch"
    ]

    # Limit concurrent research
    conduct_research_calls = conduct_research_calls[
        : configuration.max_concurrent_research_units
    ]

    # Execute think_tool calls synchronously
    from langchain_core.messages import ToolMessage

    tool_results = []
    for tool_call in tool_calls:
        tool_name = tool_call.get("name")
        if tool_name == "think_tool":
            tool_args = tool_call.get("args", {})
            tool_id = tool_call.get("id", "unknown")
            result = think_tool.invoke(tool_args)
            tool_results.append(ToolMessage(content=str(result), tool_call_id=tool_id))

            # Trace think_tool execution
            if langfuse_service:
                langfuse_service.trace_tool_execution(
                    tool_name="think_tool",
                    tool_input=tool_args,
                    tool_output={"result": str(result)},
                    metadata={
                        "context": "deep_research_supervisor",
                        "iteration": research_iterations,
                    },
                )

    # Execute research tasks in parallel
    if conduct_research_calls:
        logger.info(f"Delegating {len(conduct_research_calls)} research tasks")

        # Trace delegation
        if langfuse_service:
            langfuse_service.trace_tool_execution(
                tool_name="ConductResearch",
                tool_input={
                    "task_count": len(conduct_research_calls),
                    "topics": [
                        tc.get("args", {}).get("research_topic", "")[:50]
                        for tc in conduct_research_calls
                    ],
                },
                tool_output={"status": "delegating"},
                metadata={
                    "context": "deep_research_supervisor",
                    "iteration": research_iterations,
                },
            )

        # Build researcher subgraph
        researcher_graph = build_researcher_subgraph()

        # Create tasks for parallel execution
        research_tasks = []
        for tool_call in conduct_research_calls:
            research_topic = tool_call.get("args", {}).get("research_topic", "")
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

        # Trace completion
        if langfuse_service:
            langfuse_service.trace_tool_execution(
                tool_name="ConductResearch",
                tool_input={"task_count": len(conduct_research_calls)},
                tool_output={
                    "status": "completed",
                    "notes_added": len(notes) - len(state.get("notes", [])),
                },
                metadata={
                    "context": "deep_research_supervisor",
                    "iteration": research_iterations,
                },
            )

    # Add tool results to messages
    messages.extend(tool_results)

    if span:
        span.end(
            output={
                "tool_results_count": len(tool_results),
                "notes_count": len(notes),
                "raw_notes_count": len(raw_notes),
            }
        )

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
    # Start Langfuse span for individual researcher execution
    langfuse_service = get_langfuse_service()
    span = None
    if langfuse_service and langfuse_service.client:
        span = langfuse_service.client.start_span(
            name="deep_research_execute_researcher",
            input={
                "research_topic": research_topic,
                "profile_type": profile_type,
            },
            metadata={
                "node_type": "execute_researcher",
                "tool_id": tool_id,
            },
        )

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

        if span:
            span.end(
                output={
                    "success": True,
                    "compressed_length": len(compressed),
                    "raw_notes_count": len(raw),
                }
            )

        from langchain_core.messages import ToolMessage

        return {
            "tool_result": ToolMessage(
                content=compressed or "No research results",
                tool_call_id=tool_id,
            ),
            "compressed_research": compressed,
            "raw_notes": raw,
        }

    except Exception as e:
        logger.error(f"Researcher task error: {e}")
        if span:
            span.end()

        from langchain_core.messages import ToolMessage

        return {
            "tool_result": ToolMessage(
                content=f"Research error: {str(e)}",
                tool_call_id=tool_id,
            ),
            "compressed_research": "",
            "raw_notes": [],
        }
