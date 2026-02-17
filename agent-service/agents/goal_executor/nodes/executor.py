"""Executor node for running plan steps.

Executes individual steps using LLM with tool access.
Provides a factory function to create executors with custom tools.
Includes context pruning to manage token limits during long executions.
"""

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool, tool

from ..state import GoalExecutorState, StepStatus

logger = logging.getLogger(__name__)


# =============================================================================
# Context Pruning Configuration
# =============================================================================

# Pruning thresholds (in characters, ~4 chars per token)
SOFT_TRIM_THRESHOLD = 50_000  # ~12.5k tokens - soft trim
HARD_CLEAR_THRESHOLD = 100_000  # ~25k tokens - hard clear
MIN_PRUNABLE_CHARS = 10_000  # Don't prune small results

# How much to keep when soft-trimming (head + tail)
SOFT_TRIM_KEEP_RATIO = 0.2  # Keep 20% from head and 20% from tail

# Protect recent tool results from pruning
KEEP_LAST_TOOL_RESULTS = 3

# Placeholder for cleared content
HARD_CLEAR_PLACEHOLDER = "[Tool result cleared - content exceeded size limit]"


def _soft_trim_content(content: str, threshold: int = SOFT_TRIM_THRESHOLD) -> str:
    """Soft-trim content by keeping head and tail.

    Removes the middle portion of large content while preserving
    the beginning and end for context.

    Args:
        content: The content to trim
        threshold: Size threshold for trimming

    Returns:
        Trimmed content with middle replaced by ellipsis
    """
    if len(content) <= threshold:
        return content

    keep_chars = int(threshold * SOFT_TRIM_KEEP_RATIO)
    head = content[:keep_chars]
    tail = content[-keep_chars:]
    removed_chars = len(content) - (keep_chars * 2)

    return f"{head}\n\n... [{removed_chars:,} characters trimmed] ...\n\n{tail}"


def _hard_clear_content(content: str) -> str:
    """Hard-clear content by replacing with placeholder.

    Args:
        content: The content to clear

    Returns:
        Placeholder string with original size info
    """
    return f"{HARD_CLEAR_PLACEHOLDER} (original: {len(content):,} chars)"


def _is_image_content(content: str) -> bool:
    """Check if content appears to be image/binary data.

    Args:
        content: The content to check

    Returns:
        True if content looks like image/binary data
    """
    # Check for common image data patterns
    if content.startswith(("data:image/", "iVBOR", "/9j/", "R0lGOD")):
        return True

    # Check for base64-like content characteristics:
    # - High alphanumeric ratio (>95%)
    # - Mixed case (base64 uses both upper and lower)
    # - Contains digits (base64 uses 0-9)
    # - Low character diversity in longer strings suggests NOT base64
    if len(content) > 1000:
        sample = content[:1000]
        alnum_ratio = sum(c.isalnum() for c in sample) / len(sample)
        if alnum_ratio > 0.95:
            # Additional checks to distinguish base64 from repetitive text
            has_upper = any(c.isupper() for c in sample)
            has_lower = any(c.islower() for c in sample)
            has_digit = any(c.isdigit() for c in sample)
            unique_chars = len(set(sample))

            # Base64 typically has mixed case, digits, and high character diversity
            # Repetitive text (like "AAAA...") has very low diversity
            if has_upper and has_lower and has_digit and unique_chars > 20:
                return True

    return False


def prune_tool_results(
    messages: list[BaseMessage],
    soft_threshold: int = SOFT_TRIM_THRESHOLD,
    hard_threshold: int = HARD_CLEAR_THRESHOLD,
    keep_last: int = KEEP_LAST_TOOL_RESULTS,
) -> list[BaseMessage]:
    """Prune tool results to manage context window size.

    Applies soft-trim or hard-clear to large tool results while
    protecting recent results and image content.

    Strategy:
    - Results < soft_threshold: Keep as-is
    - Results between soft and hard threshold: Soft-trim (keep head + tail)
    - Results > hard_threshold: Hard-clear (replace with placeholder)
    - Last N tool results: Never prune
    - Image content: Never prune

    Args:
        messages: List of messages to prune
        soft_threshold: Character count for soft trimming
        hard_threshold: Character count for hard clearing
        keep_last: Number of recent tool results to protect

    Returns:
        Pruned message list (modified in place for efficiency)
    """
    # Find all tool message indices
    tool_indices = [i for i, msg in enumerate(messages) if isinstance(msg, ToolMessage)]

    if not tool_indices:
        return messages

    # Protect the last N tool results
    protected_indices = set(tool_indices[-keep_last:]) if keep_last > 0 else set()

    pruned_count = 0
    trimmed_count = 0

    for idx in tool_indices:
        if idx in protected_indices:
            continue

        msg = messages[idx]
        # Type narrowing: we know this is a ToolMessage from the indices filter
        if not isinstance(msg, ToolMessage):
            continue

        content = msg.content if isinstance(msg.content, str) else str(msg.content)

        # Skip small results
        if len(content) < MIN_PRUNABLE_CHARS:
            continue

        # Skip image content
        if _is_image_content(content):
            continue

        # Apply pruning
        if len(content) > hard_threshold:
            # Hard clear
            messages[idx] = ToolMessage(
                content=_hard_clear_content(content),
                tool_call_id=msg.tool_call_id,
            )
            pruned_count += 1
        elif len(content) > soft_threshold:
            # Soft trim
            messages[idx] = ToolMessage(
                content=_soft_trim_content(content, soft_threshold),
                tool_call_id=msg.tool_call_id,
            )
            trimmed_count += 1

    if pruned_count or trimmed_count:
        logger.debug(
            f"Context pruning: {pruned_count} hard-cleared, {trimmed_count} soft-trimmed"
        )

    return messages


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

        # Create LLM with tools (Claude Opus 4.5)
        llm = ChatAnthropic(model="claude-opus-4-5-20251101", temperature=0.3)
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

                # Prune old tool results before next LLM call
                messages = prune_tool_results(messages)

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
                        # Prune before each subsequent LLM call
                        messages = prune_tool_results(messages)
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
