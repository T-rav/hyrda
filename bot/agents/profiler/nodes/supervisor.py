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

from agents.profiler import prompts
from agents.profiler.configuration import ProfileConfiguration
from agents.profiler.state import (
    ConductResearch,
    ResearchComplete,
    SupervisorState,
)
from agents.profiler.utils import (
    create_human_message,
    create_system_message,
    think_tool,
)

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
    focus_area = state.get("focus_area", "")

    # Validate research_brief exists
    if not research_brief:
        logger.error("research_brief is missing or empty in supervisor state")
        return Command(
            goto=END,
            update={"final_report": "Error: research brief not found in state"},
        )

    logger.info(f"Supervisor iteration {research_iterations}")

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

    # Build supervisor prompt with dynamic focus
    current_date = datetime.now().strftime("%B %d, %Y")

    # Build focus guidance for supervisor
    if focus_area:
        focus_guidance = f"""
**CRITICAL - USER'S SPECIFIC FOCUS**: The user specifically asked about "{focus_area}".

**Delegation Strategy:**
- Prioritize delegating questions related to {focus_area} FIRST
- Allocate 60-70% of research iterations to {focus_area}-related questions
- Ensure remaining 30-40% covers essential context from other sections
- When delegating, explicitly mention the focus area to researchers"""
    else:
        focus_guidance = "**Note**: This is a general profile request. Distribute research effort evenly across all sections."

    system_prompt = prompts.lead_researcher_prompt.format(
        research_brief=research_brief,
        profile_type=profile_type,
        focus_area=focus_area if focus_area else "None (general profile)",
        focus_guidance=focus_guidance,
        max_concurrent_research=configuration.max_concurrent_research_units,
        max_iterations=configuration.max_researcher_iterations,
        research_iterations=research_iterations,
        notes_count=len(notes),
        current_date=current_date,
    )

    # Prepare messages
    messages = list(state.get("supervisor_messages", []))
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
        # Invoke LLM with tools
        response = await llm_with_tools.ainvoke(messages)

        # Check if response contains tool calls (LangChain AIMessage format)
        if hasattr(response, "tool_calls") and response.tool_calls:
            # Add AI message to history
            messages.append(response)

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
    from agents.profiler.nodes.graph_builder import build_researcher_subgraph

    configuration = ProfileConfiguration.from_runnable_config(config)
    messages = state.get("supervisor_messages", [])
    notes = list(state.get("notes", []))
    raw_notes = list(state.get("raw_notes", []))
    research_iterations = state.get("research_iterations", 0)
    profile_type = state.get("profile_type", "company")

    # Get last message with tool calls (LangChain AIMessage)
    last_message = messages[-1]
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        logger.warning("No tool calls in supervisor message")
        return Command(goto=END, update={})

    tool_calls = last_message.tool_calls

    # Check for ResearchComplete
    for tool_call in tool_calls:
        if tool_call.get("name") == "ResearchComplete":
            logger.info("Supervisor signaled research complete")
            return Command(goto=END, update={})

    # Check iteration limit
    if research_iterations >= configuration.max_researcher_iterations:
        logger.info(
            f"Max supervisor iterations ({configuration.max_researcher_iterations}) reached"
        )
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

    # Execute research tasks in parallel
    if conduct_research_calls:
        logger.info(f"Delegating {len(conduct_research_calls)} research tasks")

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

    # Add tool results to messages
    messages.extend(tool_results)

    # Trim message history to prevent context overflow (keep system + recent interactions)
    # GPT-4o has 128k token limit, but we need to leave room for system prompt and tools
    # CRITICAL: Every AI message with tool_calls MUST have ALL its tool responses
    if len(messages) > 9:  # system + 4 pairs (AI + tool results)
        system_msg = (
            messages[0]
            if messages
            and hasattr(messages[0], "type")
            and messages[0].type == "system"
            else None
        )

        # Build a map of tool_call_id -> tool response for validation
        tool_responses = {}
        for msg in messages:
            if (
                hasattr(msg, "type")
                and msg.type == "tool"
                and hasattr(msg, "tool_call_id")
            ):
                tool_responses[msg.tool_call_id] = msg

        # Work backwards, keeping complete conversation turns (AI + ALL its tool responses)
        trimmed_messages = []
        i = len(messages) - 1

        while (
            i > 0 and len(trimmed_messages) < 20
        ):  # Increased limit to ensure complete pairs
            msg = messages[i]

            # If this is an AI message with tool_calls, we MUST include ALL its tool responses
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                # Check if ALL tool responses are available
                tool_call_ids = [tc.get("id") for tc in msg.tool_calls]
                missing_responses = [
                    tid for tid in tool_call_ids if tid not in tool_responses
                ]

                if missing_responses:
                    # This AI message is missing some tool responses - skip it entirely
                    logger.warning(
                        f"Skipping AI message in trim: missing tool responses for {missing_responses}"
                    )
                    i -= 1
                    continue

                # Include the AI message
                trimmed_messages.insert(0, msg)

                # Include ALL its tool responses
                for tool_call_id in tool_call_ids:
                    tool_msg = tool_responses[tool_call_id]
                    if tool_msg not in trimmed_messages:
                        trimmed_messages.insert(0, tool_msg)
            else:
                # Not an AI message with tool_calls, safe to include
                trimmed_messages.insert(0, msg)

            i -= 1

        if system_msg:
            messages = [system_msg] + trimmed_messages
            logger.info(
                f"Trimmed supervisor messages: kept system + {len(trimmed_messages)} messages"
            )
        else:
            messages = trimmed_messages
            logger.info(
                f"Trimmed supervisor messages: kept {len(trimmed_messages)} messages"
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

        from langchain_core.messages import ToolMessage

        return {
            "tool_result": ToolMessage(
                content=f"Research error: {str(e)}",
                tool_call_id=tool_id,
            ),
            "compressed_research": "",
            "raw_notes": [],
        }
