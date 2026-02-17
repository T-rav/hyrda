"""Executor node for running plan steps.

Executes individual steps using LLM with tool access.
Provides a factory function to create executors with custom tools.
"""

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langchain_openai import ChatOpenAI

from ..state import GoalExecutorState, StepStatus

logger = logging.getLogger(__name__)


# Default tools available to step execution
@tool
def web_search(query: str) -> str:
    """Search the web for information.

    Args:
        query: Search query string

    Returns:
        Search results as text
    """
    # TODO: Integrate with actual web search (Tavily/Perplexity)
    return f"[Web search results for: {query}] - Placeholder results. Integrate with Tavily/Perplexity for real search."


@tool
def knowledge_search(query: str) -> str:
    """Search the internal knowledge base (RAG).

    Args:
        query: Search query string

    Returns:
        Relevant knowledge base results
    """
    # TODO: Integrate with RAG service
    return f"[Knowledge base results for: {query}] - Placeholder results. Integrate with RAG service."


@tool
def take_note(note: str) -> str:
    """Record a note or finding for later reference.

    Args:
        note: The note content to record

    Returns:
        Confirmation message
    """
    return f"Note recorded: {note}"


@tool
def request_human_input(question: str) -> str:
    """Request input from a human operator.

    Args:
        question: The question to ask the human

    Returns:
        Status message (actual human input would be handled asynchronously)
    """
    return f"[Human input requested: {question}] - In production, this would pause for human response."


# Default tool list
DEFAULT_EXECUTOR_TOOLS: list[BaseTool] = [
    web_search,  # type: ignore[list-item]
    knowledge_search,  # type: ignore[list-item]
    take_note,  # type: ignore[list-item]
    request_human_input,  # type: ignore[list-item]
]

DEFAULT_EXECUTOR_SYSTEM_PROMPT = """You are an executor agent working on a specific step of a larger goal.

Your task is to complete the assigned step by gathering information and taking actions.
You have access to tools for web search, knowledge base search, note-taking, and requesting human input.

EXECUTION GUIDELINES:
1. Focus ONLY on your assigned step
2. Use tools to gather necessary information
3. Be thorough but efficient
4. When you have enough information, provide a clear result
5. If you cannot complete the step, explain why

When finished, respond with your findings/results in a clear, structured format.
Include relevant facts, data, or decisions made during execution."""


def create_step_executor(
    tools: list[BaseTool] | None = None,
    system_prompt: str | None = None,
) -> Callable[[GoalExecutorState], Awaitable[dict[str, Any]]]:
    """Create a step executor with custom tools and system prompt.

    This factory function creates an execute_step function configured
    with the provided tools and prompt. Use this to customize the
    goal executor for different agents.

    Args:
        tools: List of tools for step execution. Defaults to standard tools.
        system_prompt: Custom system prompt. Defaults to standard prompt.

    Returns:
        Async function that executes steps in the goal plan
    """
    executor_tools = tools or DEFAULT_EXECUTOR_TOOLS
    executor_prompt = system_prompt or DEFAULT_EXECUTOR_SYSTEM_PROMPT

    # Build tool map for execution
    tool_map = {t.name: t for t in executor_tools}

    async def _execute_tool_call(tool_call: dict) -> str:
        """Execute a single tool call."""
        tool_name = tool_call.get("name", "")
        tool_args = tool_call.get("args", {})

        if tool_name in tool_map:
            try:
                result = tool_map[tool_name].invoke(tool_args)
                return str(result)
            except Exception as e:
                return f"Tool error: {e}"

        return f"Unknown tool: {tool_name}"

    async def execute_step(state: GoalExecutorState) -> dict:
        """Execute the current step in the plan.

        Finds the next ready step (all dependencies complete) and executes it
        using LLM with configured tools.

        Args:
            state: Current goal executor state

        Returns:
            Updated state with step results
        """
        plan = state.get("plan")
        if not plan:
            return {"error_message": "No plan available for execution"}

        completed_results = state.get("completed_results", {})

        # Find next ready step (pending with all deps completed)
        ready_step = None
        for step in plan.steps:
            if step.status != StepStatus.PENDING:
                continue
            # Check dependencies
            deps_met = all(
                any(
                    s.status == StepStatus.SUCCEEDED and s.id == dep for s in plan.steps
                )
                for dep in step.depends_on
            )
            if deps_met:
                ready_step = step
                break

        if not ready_step:
            # No ready steps - check if we're done or stuck
            pending = [s for s in plan.steps if s.status == StepStatus.PENDING]
            if pending:
                # We have pending steps but can't execute them (blocked by failed deps)
                return {
                    "error_message": f"Stuck: {len(pending)} pending steps with unmet dependencies",
                }
            return {}  # All done

        logger.info(f"Executing step: {ready_step.id} - {ready_step.name}")

        # Mark step as running
        ready_step.status = StepStatus.RUNNING
        ready_step.started_at = datetime.now(UTC).isoformat()
        ready_step.attempts += 1

        # Build context from completed steps
        context_parts = []
        for dep_id in ready_step.depends_on:
            if dep_id in completed_results:
                dep_step = next((s for s in plan.steps if s.id == dep_id), None)
                if dep_step:
                    context_parts.append(
                        f"[{dep_step.name}]: {completed_results[dep_id]}"
                    )

        context = "\n".join(context_parts) if context_parts else "No previous context."

        # Create LLM with tools
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
        llm_with_tools = llm.bind_tools(executor_tools)

        messages = [
            SystemMessage(content=executor_prompt),
            HumanMessage(
                content=f"""Overall Goal: {plan.goal}

Your Step: {ready_step.name}
Task: {ready_step.prompt}

Context from previous steps:
{context}

Execute this step and provide your findings."""
            ),
        ]

        try:
            # Execute with potential tool calls
            response = await llm_with_tools.ainvoke(messages)

            # Check for tool calls
            tool_calls = getattr(response, "tool_calls", None)
            if tool_calls:
                # Execute tools
                tool_messages = []

                for tool_call in tool_calls:
                    tool_result = await _execute_tool_call(tool_call)
                    tool_messages.append(
                        ToolMessage(
                            content=tool_result,
                            tool_call_id=tool_call["id"],
                        )
                    )

                # Continue execution with tool results
                messages.append(response)
                messages.extend(tool_messages)

                # Get final response
                final_response = await llm_with_tools.ainvoke(messages)

                # Handle potential additional tool calls (up to 5 iterations)
                for _ in range(4):
                    additional_calls = getattr(final_response, "tool_calls", None)
                    if additional_calls:
                        for tc in additional_calls:
                            tr = await _execute_tool_call(tc)
                            messages.append(final_response)
                            messages.append(
                                ToolMessage(content=tr, tool_call_id=tc["id"])
                            )
                        final_response = await llm_with_tools.ainvoke(messages)
                    else:
                        break

                result = (
                    final_response.content
                    if hasattr(final_response, "content")
                    else str(final_response)
                )
            else:
                result = (
                    response.content if hasattr(response, "content") else str(response)
                )

            # Mark step as succeeded
            ready_step.status = StepStatus.SUCCEEDED
            ready_step.completed_at = datetime.now(UTC).isoformat()
            ready_step.result = result

            # Update completed results
            completed_results[ready_step.id] = result

            logger.info(f"Step {ready_step.id} completed successfully")

            return {
                "plan": plan,
                "completed_results": completed_results,
                "current_step_id": ready_step.id,
                "messages": [
                    AIMessage(content=f"Completed {ready_step.name}: {result[:500]}...")
                ],
            }

        except Exception as e:
            logger.error(f"Step {ready_step.id} failed: {e}", exc_info=True)

            ready_step.status = StepStatus.FAILED
            ready_step.completed_at = datetime.now(UTC).isoformat()
            ready_step.error = str(e)

            return {
                "plan": plan,
                "current_step_id": ready_step.id,
                "messages": [AIMessage(content=f"Step {ready_step.name} failed: {e}")],
            }

    return execute_step


# Default executor for backward compatibility
execute_step = create_step_executor()


def step_tools(_state: GoalExecutorState) -> dict:
    """Execute tools for current step.

    This node handles tool execution within the step subgraph.
    Currently integrated into execute_step, but available for more
    complex tool orchestration.

    Args:
        _state: Current state (unused)

    Returns:
        Updated state with tool results
    """
    # Tool execution is handled inline in execute_step
    # This function can be expanded for async tool orchestration
    return {}
