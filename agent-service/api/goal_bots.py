"""Goal bot execution API endpoints."""

import asyncio
import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from dependencies.auth import require_service_auth

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/goal-bots",
    tags=["goal-bots"],
)


class ExecuteGoalBotRequest(BaseModel):
    """Request to execute a goal bot."""

    run_id: str = Field(..., description="The run ID from control plane")
    bot: dict[str, Any] = Field(..., description="Goal bot configuration")


class ExecuteGoalBotResponse(BaseModel):
    """Response from goal bot execution trigger."""

    success: bool
    message: str
    run_id: str
    bot_id: str


# Background task storage (in production, use Redis or similar)
_running_tasks: dict[str, asyncio.Task] = {}


async def _execute_goal_bot_background(
    bot_id: str,
    run_id: str,
    bot: dict[str, Any],
    control_plane_url: str,
    service_api_key: str,
) -> None:
    """Execute a goal bot in the background.

    This function:
    1. Invokes the agent associated with the goal bot
    2. Reports progress/milestones back to control plane
    3. Updates run status on completion/failure
    """
    from services import agent_registry

    agent_name = bot.get("agent_name", bot.get("name"))
    max_iterations = bot.get("max_iterations", 10)

    logger.info(f"Starting goal bot execution: {bot.get('name')} (run_id={run_id})")

    headers = {}
    if service_api_key:
        headers["X-Service-API-Key"] = service_api_key

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            # Log start milestone
            await _log_milestone(
                client,
                control_plane_url,
                headers,
                run_id,
                "plan_created",
                "Starting goal bot execution",
                {"agent_name": agent_name, "max_iterations": max_iterations},
            )

            # Get the agent graph
            registry = agent_registry.get_agent_registry()
            agent_info = registry.get(agent_name)

            if not agent_info:
                raise ValueError(f"Agent '{agent_name}' not found in registry")

            # Get the compiled graph
            graph_func = agent_info.get("graph_func")
            if not graph_func:
                raise ValueError(f"Agent '{agent_name}' has no graph function")

            # Build the graph
            graph = graph_func()

            # Get goal prompt from bot config (or use description as fallback)
            goal_prompt = bot.get("goal_prompt") or bot.get(
                "description", "Execute goal"
            )

            # Execute the agent with the goal prompt
            await _log_milestone(
                client,
                control_plane_url,
                headers,
                run_id,
                "action_taken",
                "Executing agent",
                {"goal_prompt": goal_prompt[:200]},
            )

            # Invoke the graph
            result = await graph.ainvoke(
                {"messages": [{"role": "user", "content": goal_prompt}]},
                config={"recursion_limit": max_iterations * 2},
            )

            # Extract response
            final_response = ""
            if "messages" in result and result["messages"]:
                last_message = result["messages"][-1]
                if hasattr(last_message, "content"):
                    final_response = last_message.content
                elif isinstance(last_message, dict):
                    final_response = last_message.get("content", str(result))
            else:
                final_response = str(result)

            # Log completion milestone
            await _log_milestone(
                client,
                control_plane_url,
                headers,
                run_id,
                "goal_achieved",
                "Goal bot completed successfully",
                {"response_length": len(final_response)},
            )

            # Update run status to completed
            await client.put(
                f"{control_plane_url}/api/goal-bots/runs/{run_id}",
                headers=headers,
                json={
                    "status": "completed",
                    "final_outcome": final_response[:5000],  # Truncate if too long
                },
            )

            logger.info(f"Goal bot completed: {bot.get('name')} (run_id={run_id})")

        except Exception as e:
            error_msg = str(e)
            logger.error(
                f"Goal bot execution failed: {bot.get('name')} "
                f"(run_id={run_id}): {error_msg}",
                exc_info=True,
            )

            # Log error milestone
            try:
                await _log_milestone(
                    client,
                    control_plane_url,
                    headers,
                    run_id,
                    "error",
                    f"Execution failed: {error_msg[:200]}",
                    {"error": error_msg},
                )

                # Update run status to failed
                await client.put(
                    f"{control_plane_url}/api/goal-bots/runs/{run_id}",
                    headers=headers,
                    json={
                        "status": "failed",
                        "error_message": error_msg[:1000],
                    },
                )
            except Exception as report_error:
                logger.error(f"Failed to report error to control plane: {report_error}")

        finally:
            # Clean up task reference
            if run_id in _running_tasks:
                del _running_tasks[run_id]


async def _log_milestone(
    client: httpx.AsyncClient,
    control_plane_url: str,
    headers: dict[str, str],
    run_id: str,
    milestone_type: str,
    milestone_name: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Log a milestone to the control plane."""
    try:
        await client.post(
            f"{control_plane_url}/api/goal-bots/runs/{run_id}/logs",
            headers=headers,
            json={
                "milestone_type": milestone_type,
                "milestone_name": milestone_name,
                "details": details or {},
            },
        )
    except Exception as e:
        logger.warning(f"Failed to log milestone: {e}")


@router.post(
    "/{bot_id}/execute",
    response_model=ExecuteGoalBotResponse,
    dependencies=[Depends(require_service_auth)],
)
async def execute_goal_bot(
    bot_id: str,
    request: ExecuteGoalBotRequest,
    http_request: Request,
) -> ExecuteGoalBotResponse:
    """Execute a goal bot (called by tasks service scheduler).

    This endpoint triggers asynchronous execution of a goal bot.
    The actual execution happens in the background.

    Args:
        bot_id: The goal bot ID
        request: Execution request with run_id and bot config

    Returns:
        Acknowledgment that execution was started
    """
    run_id = request.run_id
    bot = request.bot

    # Check if already running
    if run_id in _running_tasks:
        return ExecuteGoalBotResponse(
            success=False,
            message="Run is already in progress",
            run_id=run_id,
            bot_id=bot_id,
        )

    # Get configuration
    control_plane_url = os.getenv("CONTROL_PLANE_URL", "http://control-plane:6001")
    service_api_key = os.getenv("SERVICE_API_KEY", "")

    # Start background task
    task = asyncio.create_task(
        _execute_goal_bot_background(
            bot_id=bot_id,
            run_id=run_id,
            bot=bot,
            control_plane_url=control_plane_url,
            service_api_key=service_api_key,
        )
    )
    _running_tasks[run_id] = task

    logger.info(f"Started goal bot execution: {bot.get('name')} (run_id={run_id})")

    return ExecuteGoalBotResponse(
        success=True,
        message=f"Goal bot execution started for '{bot.get('name')}'",
        run_id=run_id,
        bot_id=bot_id,
    )


@router.get("/{bot_id}/status/{run_id}", dependencies=[Depends(require_service_auth)])
async def get_execution_status(bot_id: str, run_id: str) -> dict[str, Any]:
    """Get the status of a goal bot execution.

    Args:
        bot_id: The goal bot ID
        run_id: The run ID

    Returns:
        Execution status information
    """
    if run_id in _running_tasks:
        task = _running_tasks[run_id]
        return {
            "bot_id": bot_id,
            "run_id": run_id,
            "status": "running" if not task.done() else "completed",
            "in_memory": True,
        }

    return {
        "bot_id": bot_id,
        "run_id": run_id,
        "status": "unknown",
        "in_memory": False,
        "message": "Run not found in memory. Check control plane for status.",
    }


@router.post("/{bot_id}/cancel/{run_id}", dependencies=[Depends(require_service_auth)])
async def cancel_execution(bot_id: str, run_id: str) -> dict[str, Any]:
    """Cancel a running goal bot execution.

    Args:
        bot_id: The goal bot ID
        run_id: The run ID

    Returns:
        Cancellation result
    """
    if run_id not in _running_tasks:
        raise HTTPException(
            status_code=404,
            detail=f"Run {run_id} not found in running tasks",
        )

    task = _running_tasks[run_id]
    if task.done():
        del _running_tasks[run_id]
        return {
            "success": False,
            "message": "Task already completed",
            "run_id": run_id,
        }

    task.cancel()
    del _running_tasks[run_id]

    # Update control plane
    control_plane_url = os.getenv("CONTROL_PLANE_URL", "http://control-plane:6001")
    service_api_key = os.getenv("SERVICE_API_KEY", "")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {}
            if service_api_key:
                headers["X-Service-API-Key"] = service_api_key

            await client.put(
                f"{control_plane_url}/api/goal-bots/runs/{run_id}",
                headers=headers,
                json={"status": "cancelled"},
            )
    except Exception as e:
        logger.warning(f"Failed to update control plane on cancellation: {e}")

    return {
        "success": True,
        "message": "Task cancelled",
        "run_id": run_id,
    }
