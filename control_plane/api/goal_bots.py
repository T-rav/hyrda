"""Goal bot management endpoints."""

import logging
import sys
from datetime import datetime, timezone
from typing import Any

# Add shared directory to path
sys.path.insert(0, str(__file__).rsplit("/", 4)[0])

from dependencies.service_auth import verify_service_auth
from fastapi import APIRouter, Depends, HTTPException, Request
from models import (
    GoalBot,
    GoalBotLog,
    GoalBotRun,
    GoalBotState,
    MilestoneType,
    RunStatus,
    ScheduleType,
    TriggeredBy,
    get_db_session,
)
from pydantic import BaseModel, Field
from shared.utils.error_responses import (
    internal_error,
    not_found_error,
    validation_error,
)
from sqlalchemy import desc
from utils.pagination import (
    build_pagination_response,
    get_pagination_params,
    paginate_query,
)
from utils.permissions import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/goal-bots",
    tags=["goal-bots"],
)


# Pydantic schemas for request validation
class ScheduleConfig(BaseModel):
    """Schedule configuration."""

    cron_expression: str | None = None
    interval_seconds: int | None = None


class CreateGoalBotRequest(BaseModel):
    """Request to create a goal bot."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    agent_name: str = Field(..., min_length=1, max_length=50)
    goal_prompt: str = Field(..., min_length=1)
    schedule_type: str = Field(..., pattern="^(cron|interval)$")
    schedule_config: ScheduleConfig
    max_runtime_seconds: int = Field(default=3600, ge=60, le=86400)
    max_iterations: int = Field(default=10, ge=1, le=100)
    notification_channel: str | None = None
    tools: list[str] | None = None


class UpdateGoalBotRequest(BaseModel):
    """Request to update a goal bot."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    goal_prompt: str | None = None
    schedule_type: str | None = Field(None, pattern="^(cron|interval)$")
    schedule_config: ScheduleConfig | None = None
    max_runtime_seconds: int | None = Field(None, ge=60, le=86400)
    max_iterations: int | None = Field(None, ge=1, le=100)
    notification_channel: str | None = None
    tools: list[str] | None = None


class LogMilestoneRequest(BaseModel):
    """Request to log a milestone (from agent-service)."""

    milestone_type: str
    milestone_name: str = Field(..., max_length=200)
    details: dict | None = None
    iteration_number: int = Field(default=0, ge=0)


class UpdateRunRequest(BaseModel):
    """Request to update a run (from agent-service)."""

    status: str | None = None
    iterations_used: int | None = None
    final_outcome: str | None = None
    error_message: str | None = None
    error_traceback: str | None = None


class SaveStateRequest(BaseModel):
    """Request to save bot state (from agent-service)."""

    state_data: dict
    run_id: str | None = None


@router.get("")
async def list_goal_bots(request: Request) -> dict[str, Any]:
    """List all goal bots with pagination.

    Query params:
        include_disabled: If "true", include disabled bots (default: true)
        page: Page number (1-indexed, default: 1)
        per_page: Items per page (default: 50, max: 100)
    """
    try:
        include_disabled = (
            request.query_params.get("include_disabled", "true").lower() == "true"
        )

        page, per_page = get_pagination_params(
            request, default_per_page=50, max_per_page=100
        )

        with get_db_session() as session:
            query = session.query(GoalBot).order_by(desc(GoalBot.created_at))
            if not include_disabled:
                query = query.filter(GoalBot.is_enabled)

            bots, total_count = paginate_query(query, page, per_page)

            # Get running run counts per bot
            running_counts = {}
            for bot in bots:
                count = (
                    session.query(GoalBotRun)
                    .filter(
                        GoalBotRun.bot_id == bot.bot_id,
                        GoalBotRun.status == RunStatus.RUNNING,
                    )
                    .count()
                )
                running_counts[bot.bot_id] = count

            bots_data = []
            for bot in bots:
                bot_dict = bot.to_dict()
                bot_dict["has_running_job"] = running_counts.get(bot.bot_id, 0) > 0
                bots_data.append(bot_dict)

            response = build_pagination_response(bots_data, total_count, page, per_page)
            return {
                "goal_bots": response["items"],
                "pagination": response["pagination"],
            }

    except Exception as e:
        logger.error(f"Error listing goal bots: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=internal_error(str(e)))


@router.post("")
async def create_goal_bot(
    data: CreateGoalBotRequest,
    request: Request,
    admin_check: None = Depends(require_admin),
) -> dict[str, Any]:
    """Create a new goal bot."""
    try:
        # Get current user from session
        session_data = (
            request.state.session if hasattr(request.state, "session") else {}
        )
        created_by = session_data.get("user_id")

        with get_db_session() as session:
            # Check for duplicate name
            existing = session.query(GoalBot).filter(GoalBot.name == data.name).first()
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail={"error": f"Goal bot '{data.name}' already exists"},
                )

            # Create the bot
            bot = GoalBot(
                bot_id=GoalBot.generate_bot_id(),
                name=data.name,
                description=data.description,
                agent_name=data.agent_name,
                goal_prompt=data.goal_prompt,
                schedule_type=ScheduleType(data.schedule_type),
                max_runtime_seconds=data.max_runtime_seconds,
                max_iterations=data.max_iterations,
                is_enabled=True,
                is_paused=False,
                created_by=created_by,
                notification_channel=data.notification_channel,
            )
            bot.set_schedule_config(data.schedule_config.model_dump())
            if data.tools:
                bot.set_tools(data.tools)

            # Calculate next run time
            bot.next_run_at = bot.calculate_next_run()

            session.add(bot)
            session.commit()

            logger.info(f"Created goal bot '{data.name}' (id={bot.bot_id})")

            return {"success": True, "goal_bot": bot.to_dict()}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating goal bot: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=internal_error(str(e)))


async def _verify_service_only(request: Request) -> str:
    """Wrapper for verify_service_auth without allowed_services parameter."""
    return await verify_service_auth(request, allowed_services=None)


@router.post("/register")
async def register_goal_bot(
    request: Request,
    service: str = Depends(_verify_service_only),
) -> dict[str, Any]:
    """Register or update a goal bot (called by agent-service on startup).

    Uses service-to-service authentication.
    """
    try:
        data = await request.json()
        name = data.get("name")
        description = data.get("description", "")
        agent_name = data.get("agent_name", name)
        goal_prompt = data.get("goal_prompt", "")
        schedule_type = data.get("schedule_type", "interval")
        schedule_config = data.get("schedule_config", {"interval_seconds": 86400})
        max_runtime_seconds = data.get("max_runtime_seconds", 3600)
        max_iterations = data.get("max_iterations", 10)
        notification_channel = data.get("notification_channel")
        tools = data.get("tools", [])

        if not name:
            raise HTTPException(
                status_code=400, detail=validation_error("name is required")
            )

        with get_db_session() as session:
            with session.begin():
                # Check if goal bot exists
                existing = session.query(GoalBot).filter(GoalBot.name == name).first()

                if existing:
                    # Update existing
                    existing.description = description
                    existing.goal_prompt = goal_prompt
                    existing.schedule_type = ScheduleType(schedule_type)
                    existing.set_schedule_config(schedule_config)
                    existing.max_runtime_seconds = max_runtime_seconds
                    existing.max_iterations = max_iterations
                    if notification_channel:
                        existing.notification_channel = notification_channel
                    if tools:
                        existing.set_tools(tools)
                    # Recalculate next run
                    existing.next_run_at = existing.calculate_next_run()
                    session.commit()
                    logger.info(f"Updated goal bot '{name}' from agent registration")
                    return {"success": True, "goal_bot": name, "action": "updated"}
                else:
                    # Create new
                    bot = GoalBot(
                        bot_id=GoalBot.generate_bot_id(),
                        name=name,
                        description=description,
                        agent_name=agent_name,
                        goal_prompt=goal_prompt,
                        schedule_type=ScheduleType(schedule_type),
                        max_runtime_seconds=max_runtime_seconds,
                        max_iterations=max_iterations,
                        is_enabled=True,
                        is_paused=False,
                        notification_channel=notification_channel,
                    )
                    bot.set_schedule_config(schedule_config)
                    if tools:
                        bot.set_tools(tools)
                    bot.next_run_at = bot.calculate_next_run()
                    session.add(bot)
                    session.commit()
                    logger.info(f"Registered new goal bot '{name}'")
                    return {"success": True, "goal_bot": name, "action": "created"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering goal bot: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=internal_error(str(e)))


@router.get("/{bot_id}")
async def get_goal_bot(bot_id: str) -> dict[str, Any]:
    """Get detailed information about a specific goal bot."""
    try:
        with get_db_session() as session:
            bot = session.query(GoalBot).filter(GoalBot.bot_id == bot_id).first()
            if not bot:
                raise HTTPException(
                    status_code=404, detail=not_found_error("Goal bot", bot_id)
                )

            # Get total runs count
            total_runs = (
                session.query(GoalBotRun).filter(GoalBotRun.bot_id == bot_id).count()
            )

            # Get recent runs
            recent_runs = (
                session.query(GoalBotRun)
                .filter(GoalBotRun.bot_id == bot_id)
                .order_by(desc(GoalBotRun.created_at))
                .limit(5)
                .all()
            )

            bot_dict = bot.to_dict()
            bot_dict["total_runs"] = total_runs
            bot_dict["recent_runs"] = [run.to_dict() for run in recent_runs]

            # Get state if exists
            state = (
                session.query(GoalBotState)
                .filter(GoalBotState.bot_id == bot_id)
                .first()
            )
            if state:
                bot_dict["state"] = state.to_dict()

            return bot_dict

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting goal bot: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=internal_error(str(e)))


@router.put("/{bot_id}")
async def update_goal_bot(
    bot_id: str,
    data: UpdateGoalBotRequest,
    admin_check: None = Depends(require_admin),
) -> dict[str, Any]:
    """Update a goal bot configuration."""
    try:
        with get_db_session() as session:
            bot = session.query(GoalBot).filter(GoalBot.bot_id == bot_id).first()
            if not bot:
                raise HTTPException(
                    status_code=404, detail=not_found_error("Goal bot", bot_id)
                )

            # Update fields if provided
            if data.name is not None:
                # Check for duplicate name
                existing = (
                    session.query(GoalBot)
                    .filter(GoalBot.name == data.name, GoalBot.bot_id != bot_id)
                    .first()
                )
                if existing:
                    raise HTTPException(
                        status_code=409,
                        detail={"error": f"Goal bot '{data.name}' already exists"},
                    )
                bot.name = data.name

            if data.description is not None:
                bot.description = data.description
            if data.goal_prompt is not None:
                bot.goal_prompt = data.goal_prompt
            if data.schedule_type is not None:
                bot.schedule_type = ScheduleType(data.schedule_type)
            if data.schedule_config is not None:
                bot.set_schedule_config(data.schedule_config.model_dump())
                # Recalculate next run time
                bot.next_run_at = bot.calculate_next_run()
            if data.max_runtime_seconds is not None:
                bot.max_runtime_seconds = data.max_runtime_seconds
            if data.max_iterations is not None:
                bot.max_iterations = data.max_iterations
            if data.notification_channel is not None:
                bot.notification_channel = data.notification_channel
            if data.tools is not None:
                bot.set_tools(data.tools)

            session.commit()

            logger.info(f"Updated goal bot '{bot.name}' (id={bot_id})")

            return {"success": True, "goal_bot": bot.to_dict()}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating goal bot: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=internal_error(str(e)))


@router.delete("/{bot_id}")
async def delete_goal_bot(
    bot_id: str,
    admin_check: None = Depends(require_admin),
) -> dict[str, Any]:
    """Delete a goal bot and all associated data."""
    try:
        with get_db_session() as session:
            bot = session.query(GoalBot).filter(GoalBot.bot_id == bot_id).first()
            if not bot:
                raise HTTPException(
                    status_code=404, detail=not_found_error("Goal bot", bot_id)
                )

            name = bot.name
            session.delete(bot)  # Cascade deletes runs, logs, state
            session.commit()

            logger.info(f"Deleted goal bot '{name}' (id={bot_id})")

            return {"success": True, "message": f"Goal bot '{name}' deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting goal bot: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=internal_error(str(e)))


@router.post("/{bot_id}/toggle")
async def toggle_goal_bot(
    bot_id: str,
    admin_check: None = Depends(require_admin),
) -> dict[str, Any]:
    """Toggle goal bot enabled/disabled state."""
    try:
        with get_db_session() as session:
            bot = session.query(GoalBot).filter(GoalBot.bot_id == bot_id).first()
            if not bot:
                raise HTTPException(
                    status_code=404, detail=not_found_error("Goal bot", bot_id)
                )

            bot.is_enabled = not bot.is_enabled

            # If enabling, recalculate next run time
            if bot.is_enabled:
                bot.next_run_at = bot.calculate_next_run()

            session.commit()

            logger.info(
                f"{'Enabled' if bot.is_enabled else 'Disabled'} goal bot '{bot.name}'"
            )

            return {
                "success": True,
                "bot_id": bot_id,
                "is_enabled": bot.is_enabled,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling goal bot: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=internal_error(str(e)))


@router.post("/{bot_id}/pause")
async def pause_goal_bot(
    bot_id: str,
    admin_check: None = Depends(require_admin),
) -> dict[str, Any]:
    """Pause a goal bot (keeps schedule but skips runs)."""
    try:
        with get_db_session() as session:
            bot = session.query(GoalBot).filter(GoalBot.bot_id == bot_id).first()
            if not bot:
                raise HTTPException(
                    status_code=404, detail=not_found_error("Goal bot", bot_id)
                )

            bot.is_paused = True
            session.commit()

            logger.info(f"Paused goal bot '{bot.name}'")

            return {"success": True, "bot_id": bot_id, "is_paused": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pausing goal bot: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=internal_error(str(e)))


@router.post("/{bot_id}/resume")
async def resume_goal_bot(
    bot_id: str,
    admin_check: None = Depends(require_admin),
) -> dict[str, Any]:
    """Resume a paused goal bot."""
    try:
        with get_db_session() as session:
            bot = session.query(GoalBot).filter(GoalBot.bot_id == bot_id).first()
            if not bot:
                raise HTTPException(
                    status_code=404, detail=not_found_error("Goal bot", bot_id)
                )

            bot.is_paused = False
            # Recalculate next run time
            bot.next_run_at = bot.calculate_next_run()
            session.commit()

            logger.info(f"Resumed goal bot '{bot.name}'")

            return {"success": True, "bot_id": bot_id, "is_paused": False}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resuming goal bot: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=internal_error(str(e)))


@router.post("/{bot_id}/trigger")
async def trigger_goal_bot(
    bot_id: str,
    request: Request,
    admin_check: None = Depends(require_admin),
) -> dict[str, Any]:
    """Manually trigger a goal bot run."""
    try:
        session_data = (
            request.state.session if hasattr(request.state, "session") else {}
        )
        triggered_by_user = session_data.get("user_id")

        with get_db_session() as session:
            bot = session.query(GoalBot).filter(GoalBot.bot_id == bot_id).first()
            if not bot:
                raise HTTPException(
                    status_code=404, detail=not_found_error("Goal bot", bot_id)
                )

            # Check if already running
            running_run = (
                session.query(GoalBotRun)
                .filter(
                    GoalBotRun.bot_id == bot_id,
                    GoalBotRun.status == RunStatus.RUNNING,
                )
                .first()
            )
            if running_run:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "Goal bot is already running",
                        "run_id": running_run.run_id,
                    },
                )

            # Create a new run
            run = GoalBotRun(
                run_id=GoalBotRun.generate_run_id(),
                bot_id=bot_id,
                status=RunStatus.PENDING,
                triggered_by=TriggeredBy.MANUAL,
                triggered_by_user=triggered_by_user,
            )
            session.add(run)
            session.commit()

            logger.info(
                f"Manual trigger for goal bot '{bot.name}' - run_id={run.run_id}"
            )

            return {
                "success": True,
                "message": f"Triggered goal bot '{bot.name}'",
                "run_id": run.run_id,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering goal bot: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=internal_error(str(e)))


@router.post("/{bot_id}/cancel")
async def cancel_goal_bot_run(
    bot_id: str,
    admin_check: None = Depends(require_admin),
) -> dict[str, Any]:
    """Cancel a running goal bot execution."""
    try:
        with get_db_session() as session:
            # Find running run
            run = (
                session.query(GoalBotRun)
                .filter(
                    GoalBotRun.bot_id == bot_id,
                    GoalBotRun.status == RunStatus.RUNNING,
                )
                .first()
            )

            if not run:
                raise HTTPException(
                    status_code=404,
                    detail={"error": "No running job found for this goal bot"},
                )

            run.cancel()
            session.commit()

            logger.info(f"Cancelled goal bot run {run.run_id}")

            return {
                "success": True,
                "message": "Goal bot run cancelled",
                "run_id": run.run_id,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling goal bot: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=internal_error(str(e)))


@router.get("/{bot_id}/runs")
async def list_goal_bot_runs(bot_id: str, request: Request) -> dict[str, Any]:
    """List run history for a goal bot."""
    try:
        page, per_page = get_pagination_params(
            request, default_per_page=20, max_per_page=100
        )

        with get_db_session() as session:
            # Verify bot exists
            bot = session.query(GoalBot).filter(GoalBot.bot_id == bot_id).first()
            if not bot:
                raise HTTPException(
                    status_code=404, detail=not_found_error("Goal bot", bot_id)
                )

            query = (
                session.query(GoalBotRun)
                .filter(GoalBotRun.bot_id == bot_id)
                .order_by(desc(GoalBotRun.created_at))
            )

            runs, total_count = paginate_query(query, page, per_page)
            runs_data = [run.to_dict() for run in runs]

            response = build_pagination_response(runs_data, total_count, page, per_page)
            return {"runs": response["items"], "pagination": response["pagination"]}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing goal bot runs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=internal_error(str(e)))


@router.get("/{bot_id}/runs/{run_id}")
async def get_goal_bot_run(bot_id: str, run_id: str) -> dict[str, Any]:
    """Get details of a specific run including logs."""
    try:
        with get_db_session() as session:
            run = (
                session.query(GoalBotRun)
                .filter(GoalBotRun.bot_id == bot_id, GoalBotRun.run_id == run_id)
                .first()
            )

            if not run:
                raise HTTPException(
                    status_code=404, detail=not_found_error("Run", run_id)
                )

            return run.to_dict(include_logs=True)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting goal bot run: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=internal_error(str(e)))


@router.get("/{bot_id}/state")
async def get_goal_bot_state(bot_id: str) -> dict[str, Any]:
    """Get the persistent state of a goal bot."""
    try:
        with get_db_session() as session:
            bot = session.query(GoalBot).filter(GoalBot.bot_id == bot_id).first()
            if not bot:
                raise HTTPException(
                    status_code=404, detail=not_found_error("Goal bot", bot_id)
                )

            state = (
                session.query(GoalBotState)
                .filter(GoalBotState.bot_id == bot_id)
                .first()
            )

            if state:
                return state.to_dict()
            else:
                return {
                    "bot_id": bot_id,
                    "state": {},
                    "state_version": 0,
                    "last_updated_at": None,
                    "last_run_id": None,
                }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting goal bot state: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=internal_error(str(e)))


@router.delete("/{bot_id}/state")
async def reset_goal_bot_state(
    bot_id: str,
    admin_check: None = Depends(require_admin),
) -> dict[str, Any]:
    """Reset the persistent state of a goal bot."""
    try:
        with get_db_session() as session:
            bot = session.query(GoalBot).filter(GoalBot.bot_id == bot_id).first()
            if not bot:
                raise HTTPException(
                    status_code=404, detail=not_found_error("Goal bot", bot_id)
                )

            state = (
                session.query(GoalBotState)
                .filter(GoalBotState.bot_id == bot_id)
                .first()
            )

            if state:
                session.delete(state)
                session.commit()
                logger.info(f"Reset state for goal bot '{bot.name}'")

            return {"success": True, "message": "State reset"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting goal bot state: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=internal_error(str(e)))


# ============================================================================
# Internal endpoints for agent-service to call
# ============================================================================


@router.get("/due")
async def get_due_goal_bots() -> dict[str, Any]:
    """Get all goal bots that are due to run (for tasks service checker)."""
    try:
        now = datetime.now(timezone.utc)

        with get_db_session() as session:
            due_bots = (
                session.query(GoalBot)
                .filter(
                    GoalBot.is_enabled,
                    ~GoalBot.is_paused,
                    GoalBot.next_run_at <= now,
                )
                .all()
            )

            # Filter out bots that already have a running job
            result = []
            for bot in due_bots:
                running = (
                    session.query(GoalBotRun)
                    .filter(
                        GoalBotRun.bot_id == bot.bot_id,
                        GoalBotRun.status == RunStatus.RUNNING,
                    )
                    .first()
                )
                if not running:
                    result.append(bot.to_dict())

            return {"due_bots": result, "count": len(result)}

    except Exception as e:
        logger.error(f"Error getting due goal bots: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=internal_error(str(e)))


@router.post("/runs/{run_id}/start")
async def start_run(run_id: str) -> dict[str, Any]:
    """Mark a run as started (called by tasks service)."""
    try:
        with get_db_session() as session:
            run = session.query(GoalBotRun).filter(GoalBotRun.run_id == run_id).first()
            if not run:
                raise HTTPException(
                    status_code=404, detail=not_found_error("Run", run_id)
                )

            run.start()

            # Update bot's last_run_at
            bot = session.query(GoalBot).filter(GoalBot.bot_id == run.bot_id).first()
            if bot:
                bot.last_run_at = datetime.now(timezone.utc)
                # Calculate next run time
                bot.next_run_at = bot.calculate_next_run()

            session.commit()

            return {"success": True, "run": run.to_dict()}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting run: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=internal_error(str(e)))


@router.put("/runs/{run_id}")
async def update_run(run_id: str, data: UpdateRunRequest) -> dict[str, Any]:
    """Update a run (called by agent-service)."""
    try:
        with get_db_session() as session:
            run = session.query(GoalBotRun).filter(GoalBotRun.run_id == run_id).first()
            if not run:
                raise HTTPException(
                    status_code=404, detail=not_found_error("Run", run_id)
                )

            if data.status is not None:
                new_status = RunStatus(data.status)
                if new_status == RunStatus.COMPLETED:
                    run.complete(data.final_outcome)
                elif new_status == RunStatus.FAILED:
                    run.fail(
                        data.error_message or "Unknown error", data.error_traceback
                    )
                elif new_status == RunStatus.CANCELLED:
                    run.cancel()
                elif new_status == RunStatus.TIMEOUT:
                    run.timeout()
                else:
                    run.status = new_status

            if data.iterations_used is not None:
                run.iterations_used = data.iterations_used
            if data.final_outcome is not None and run.status != RunStatus.COMPLETED:
                run.final_outcome = data.final_outcome

            session.commit()

            return {"success": True, "run": run.to_dict()}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating run: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=internal_error(str(e)))


@router.post("/runs/{run_id}/logs")
async def log_milestone(run_id: str, data: LogMilestoneRequest) -> dict[str, Any]:
    """Log a milestone for a run (called by agent-service)."""
    try:
        with get_db_session() as session:
            run = session.query(GoalBotRun).filter(GoalBotRun.run_id == run_id).first()
            if not run:
                raise HTTPException(
                    status_code=404, detail=not_found_error("Run", run_id)
                )

            log = GoalBotLog(
                run_id=run_id,
                milestone_type=MilestoneType(data.milestone_type),
                milestone_name=data.milestone_name,
                iteration_number=data.iteration_number,
            )
            if data.details:
                log.set_details(data.details)

            session.add(log)
            session.commit()

            return {"success": True, "log": log.to_dict()}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error logging milestone: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=internal_error(str(e)))


@router.put("/bots/{bot_id}/state")
async def save_bot_state(bot_id: str, data: SaveStateRequest) -> dict[str, Any]:
    """Save bot state (called by agent-service)."""
    try:
        with get_db_session() as session:
            bot = session.query(GoalBot).filter(GoalBot.bot_id == bot_id).first()
            if not bot:
                raise HTTPException(
                    status_code=404, detail=not_found_error("Goal bot", bot_id)
                )

            state = (
                session.query(GoalBotState)
                .filter(GoalBotState.bot_id == bot_id)
                .first()
            )

            if state:
                state.set_state(data.state_data)
                if data.run_id:
                    state.last_run_id = data.run_id
            else:
                state = GoalBotState(
                    bot_id=bot_id,
                    state_data="{}",
                    state_version=0,
                    last_run_id=data.run_id,
                )
                state.set_state(data.state_data)
                session.add(state)

            session.commit()

            return {"success": True, "state": state.to_dict()}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving bot state: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=internal_error(str(e)))


@router.post("/runs")
async def create_scheduled_run(request: Request) -> dict[str, Any]:
    """Create a new run for a bot (called by tasks service checker)."""
    try:
        data = await request.json()
        bot_id = data.get("bot_id")

        if not bot_id:
            raise HTTPException(
                status_code=400, detail=validation_error("bot_id is required")
            )

        with get_db_session() as session:
            bot = session.query(GoalBot).filter(GoalBot.bot_id == bot_id).first()
            if not bot:
                raise HTTPException(
                    status_code=404, detail=not_found_error("Goal bot", bot_id)
                )

            # Check if already running
            running = (
                session.query(GoalBotRun)
                .filter(
                    GoalBotRun.bot_id == bot_id,
                    GoalBotRun.status == RunStatus.RUNNING,
                )
                .first()
            )
            if running:
                return {
                    "success": False,
                    "error": "Bot already has a running job",
                    "run_id": running.run_id,
                }

            run = GoalBotRun(
                run_id=GoalBotRun.generate_run_id(),
                bot_id=bot_id,
                status=RunStatus.PENDING,
                triggered_by=TriggeredBy.SCHEDULER,
            )
            session.add(run)
            session.commit()

            return {"success": True, "run": run.to_dict(), "bot": bot.to_dict()}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating scheduled run: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=internal_error(str(e)))


@router.get("/running")
async def get_running_bots() -> dict[str, Any]:
    """Get all currently running goal bot jobs (for timeout monitoring)."""
    try:
        with get_db_session() as session:
            running_runs = (
                session.query(GoalBotRun)
                .filter(GoalBotRun.status == RunStatus.RUNNING)
                .all()
            )

            result = []
            for run in running_runs:
                bot = (
                    session.query(GoalBot).filter(GoalBot.bot_id == run.bot_id).first()
                )
                if bot:
                    result.append(
                        {
                            "run": run.to_dict(),
                            "bot": {
                                "bot_id": bot.bot_id,
                                "name": bot.name,
                                "max_runtime_seconds": bot.max_runtime_seconds,
                            },
                        }
                    )

            return {"running": result, "count": len(result)}

    except Exception as e:
        logger.error(f"Error getting running bots: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=internal_error(str(e)))
