"""Graph builder for goal executor subgraph.

Builds reusable LangGraph subgraph implementing the OpenClaw-style
plan-execute-check loop for goal-driven execution.

This is designed to be embedded in other agents (like prospect_research)
that provide their specific tools and goal prompts.

Features:
- State persistence via LangGraph's SQLite checkpointer
- Auto-compaction flush before ending (OpenClaw pattern)
- Session summaries embedded in Qdrant for semantic search
- Full session archives in MinIO
"""

import logging
import os

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from ..state import (
    GoalExecutorInputState,
    GoalExecutorOutputState,
    GoalExecutorState,
    GoalStatus,
)
from .checker import check_progress, check_router
from .executor import create_step_executor
from .planner import create_plan

logger = logging.getLogger(__name__)

# SQLite database path for checkpointing
CHECKPOINT_DB_PATH = os.getenv(
    "GOAL_EXECUTOR_CHECKPOINT_DB", "/app/data/goal_executor_checkpoints.db"
)


def get_checkpointer() -> SqliteSaver:
    """Get or create the SQLite checkpointer for state persistence.

    Returns:
        SqliteSaver instance for LangGraph checkpointing
    """
    # Ensure directory exists
    db_dir = os.path.dirname(CHECKPOINT_DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    return SqliteSaver.from_conn_string(CHECKPOINT_DB_PATH)


def build_goal_executor(
    tools: list[BaseTool] | None = None,
    system_prompt: str | None = None,
    use_checkpointer: bool = True,
) -> CompiledStateGraph:
    """Build the goal executor subgraph with SQLite state persistence.

    This is a reusable subgraph that can be embedded in other agents.
    The parent agent provides tools and system prompt for customization.

    State is automatically persisted to SQLite between runs, allowing
    goal bots to resume from where they left off.

    The graph implements a plan-execute-check loop:

    ```
    START → create_plan → execute_step ←→ check_progress → END
                              ↑                    │
                              └────── continue ────┘
    ```

    Flow:
    1. create_plan: Decompose goal into steps with dependencies
    2. execute_step: Execute next ready step using provided tools
    3. check_progress: Evaluate if goal complete/failed/continue
    4. Loop back to execute_step if continuing

    Args:
        tools: List of tools available for step execution
        system_prompt: Custom system prompt for the executor
        use_checkpointer: Whether to enable SQLite state persistence (default: True)

    Returns:
        Compiled goal executor subgraph with checkpointing
    """
    # Create executor with provided tools
    execute_step = create_step_executor(tools=tools, system_prompt=system_prompt)

    # Build main graph
    builder = StateGraph(
        GoalExecutorState,
        input_schema=GoalExecutorInputState,
        output_schema=GoalExecutorOutputState,
    )

    # Add nodes
    builder.add_node("create_plan", create_plan)
    builder.add_node("execute_step", execute_step)
    builder.add_node("check_progress", check_progress)
    builder.add_node("save_state", save_state)

    # Add edges
    builder.add_edge(START, "create_plan")

    # Router after planning: if planning failed, go to end
    def plan_router(state: GoalExecutorState) -> str:
        """Route after planning."""
        status = state.get("status", GoalStatus.PLANNING)
        if status == GoalStatus.FAILED:
            return "save_state"
        return "execute_step"

    builder.add_conditional_edges(
        "create_plan",
        plan_router,
        {
            "execute_step": "execute_step",
            "save_state": "save_state",
        },
    )

    # Execute → Check
    builder.add_edge("execute_step", "check_progress")

    # Check → Execute or End
    builder.add_conditional_edges(
        "check_progress",
        check_router,
        {
            "execute": "execute_step",
            "end": "save_state",
        },
    )

    # Save state → END
    builder.add_edge("save_state", END)

    # Compile with SQLite checkpointer for state persistence
    logger.info("Building goal executor graph")

    if use_checkpointer:
        try:
            checkpointer = get_checkpointer()
            logger.info(f"Using SQLite checkpointer at: {CHECKPOINT_DB_PATH}")
            return builder.compile(checkpointer=checkpointer)
        except Exception as e:
            logger.warning(
                f"Failed to create checkpointer, running without persistence: {e}"
            )
            return builder.compile()
    else:
        return builder.compile()


async def save_state(
    state: GoalExecutorState, config: RunnableConfig | None = None
) -> dict:
    """Save persistent state and auto-compact to vector memory.

    This is the pre-compaction flush (like OpenClaw). Before ending:
    1. Save plan/progress to persistent_state
    2. Compact session to vector memory (LLM summary → embed → Qdrant)
    3. Archive full session to MinIO

    Args:
        state: Current goal executor state
        config: LangGraph config with thread_id

    Returns:
        Updated state with persistent_state populated
    """
    plan = state.get("plan")
    completed_results = state.get("completed_results", {})
    status = state.get("status", GoalStatus.RUNNING)

    # Build persistent state
    persistent_state = state.get("persistent_state", {}) or {}

    if plan:
        # Save plan with current step statuses
        persistent_state["plan"] = {
            "plan_id": plan.plan_id,
            "goal": plan.goal,
            "steps": [
                {
                    "id": s.id,
                    "name": s.name,
                    "prompt": s.prompt,
                    "depends_on": s.depends_on,
                    "status": s.status.value
                    if hasattr(s.status, "value")
                    else s.status,
                    "result": s.result,
                    "error": s.error,
                }
                for s in plan.steps
            ],
            "created_at": plan.created_at,
        }

    persistent_state["completed_results"] = completed_results
    persistent_state["last_status"] = (
        status.value if hasattr(status, "value") else status
    )
    persistent_state["iteration_count"] = state.get("iteration_count", 0)

    # Store run results for learning
    if status == GoalStatus.COMPLETED:
        runs = persistent_state.get("previous_runs", [])
        runs.append(
            {
                "outcome": state.get("final_outcome", ""),
                "steps_completed": len(completed_results),
            }
        )
        persistent_state["previous_runs"] = runs[-5:]  # Keep last 5

    # =========================================================================
    # Auto-compact to vector memory (OpenClaw pre-compaction flush)
    # =========================================================================
    await _auto_compact_session(state, config, persistent_state)

    return {"persistent_state": persistent_state}


async def _auto_compact_session(
    state: GoalExecutorState,
    config: RunnableConfig | None,
    persistent_state: dict,
) -> None:
    """Auto-compact session to vector memory before ending.

    This is the OpenClaw-style pre-compaction flush that:
    1. Gets thread_id from config
    2. Gathers session activity
    3. Compacts to vector memory (LLM summary → embed → Qdrant)

    Args:
        state: Goal executor state
        config: LangGraph config
        persistent_state: Persistent state dict
    """
    try:
        # Get thread_id from config
        thread_id = None
        if config:
            configurable = config.get("configurable", {})
            thread_id = configurable.get("thread_id")

        if not thread_id:
            logger.debug("No thread_id in config, skipping auto-compact")
            return

        # Get bot_id from persistent state or default
        bot_id = persistent_state.get("bot_id", "goal_executor")

        # Build outcome summary
        status = state.get("status", GoalStatus.RUNNING)
        final_outcome = state.get("final_outcome", "")
        error_message = state.get("error_message", "")

        if status == GoalStatus.COMPLETED:
            outcome = final_outcome or "Goal completed successfully"
        elif status == GoalStatus.FAILED:
            outcome = (
                f"Goal failed: {error_message}" if error_message else "Goal failed"
            )
        else:
            outcome = f"Goal ended with status: {status}"

        # Get goal
        goal = state.get("goal", "")

        # Build activities from completed results
        completed_results = state.get("completed_results", {})
        activities = []
        for step_id, result in completed_results.items():
            activities.append(
                {
                    "type": "step_completed",
                    "data": {
                        "step_id": step_id,
                        "result": result[:200] if result else "",
                    },
                }
            )

        # Import and call compact
        from ..services import get_goal_memory

        memory = get_goal_memory(bot_id=bot_id, thread_id=thread_id)

        # Log activities to session memory
        for activity in activities:
            memory.log_activity(
                activity["type"],
                activity["data"],
                persist=False,  # Will persist in compact
            )

        # Compact and archive
        archive_result = await memory.compact_and_archive(
            outcome=outcome,
            goal=goal,
        )

        if archive_result.get("archived"):
            logger.info(
                f"Auto-compacted session {thread_id} → "
                f"memory_id={archive_result.get('memory_id')}"
            )
        else:
            logger.debug(f"Session compact skipped: {archive_result}")

    except Exception as e:
        # Don't fail the run if compaction fails
        logger.warning(f"Auto-compact failed (non-fatal): {e}")


logger.info("Goal executor graph builder loaded")
