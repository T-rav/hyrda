"""Route handlers for the Hydra dashboard API."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse

from config import HydraConfig
from events import EventBus, EventType, HydraEvent
from models import (
    BackgroundWorkersResponse,
    BackgroundWorkerStatus,
    ControlStatusConfig,
    ControlStatusResponse,
    LifetimeStats,
    MetricsResponse,
)
from pr_manager import PRManager
from state import StateTracker

if TYPE_CHECKING:
    from orchestrator import HydraOrchestrator

logger = logging.getLogger("hydra.dashboard")


def create_router(
    config: HydraConfig,
    event_bus: EventBus,
    state: StateTracker,
    pr_manager: PRManager,
    get_orchestrator: Callable[[], HydraOrchestrator | None],
    set_orchestrator: Callable[[HydraOrchestrator], None],
    set_run_task: Callable[[asyncio.Task[None]], None],
    ui_dist_dir: Path,
    template_dir: Path,
) -> APIRouter:
    """Create an APIRouter with all dashboard route handlers."""
    router = APIRouter()

    @router.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        react_index = ui_dist_dir / "index.html"
        if react_index.exists():
            return HTMLResponse(react_index.read_text())
        template_path = template_dir / "index.html"
        if template_path.exists():
            return HTMLResponse(template_path.read_text())
        return HTMLResponse("<h1>Hydra Dashboard</h1><p>Run 'make ui' to build.</p>")

    @router.get("/api/state")
    async def get_state() -> JSONResponse:
        return JSONResponse(state.to_dict())

    @router.get("/api/stats")
    async def get_stats() -> JSONResponse:
        return JSONResponse(state.get_lifetime_stats())

    @router.get("/api/events")
    async def get_events(since: str | None = None) -> JSONResponse:
        if since is not None:
            from datetime import datetime

            try:
                since_dt = datetime.fromisoformat(since)
                if since_dt.tzinfo is None:
                    since_dt = since_dt.replace(tzinfo=UTC)
                events = await event_bus.load_events_since(since_dt)
                if events is not None:
                    return JSONResponse([e.model_dump() for e in events])
            except (ValueError, TypeError):
                pass  # Fall through to in-memory history
        history = event_bus.get_history()
        return JSONResponse([e.model_dump() for e in history])

    @router.get("/api/prs")
    async def get_prs() -> JSONResponse:
        """Fetch all open Hydra PRs from GitHub."""
        all_labels = list(
            {
                *config.ready_label,
                *config.review_label,
                *config.fixed_label,
                *config.hitl_label,
                *config.hitl_active_label,
                *config.planner_label,
            }
        )
        items = await pr_manager.list_open_prs(all_labels)
        return JSONResponse([item.model_dump() for item in items])

    @router.get("/api/hitl")
    async def get_hitl() -> JSONResponse:
        """Fetch issues/PRs labeled for human-in-the-loop (stuck on CI)."""
        items = await pr_manager.list_hitl_items(config.hitl_label)
        orch = get_orchestrator()
        enriched = []
        for item in items:
            data = item.model_dump()
            if orch:
                data["status"] = orch.get_hitl_status(item.issue)
            cause = state.get_hitl_cause(item.issue)
            if cause:
                data["cause"] = cause
            origin = state.get_hitl_origin(item.issue)
            if origin and origin in config.improve_label:
                data["isMemorySuggestion"] = True
            enriched.append(data)
        return JSONResponse(enriched)

    @router.post("/api/hitl/{issue_number}/correct")
    async def hitl_correct(issue_number: int, body: dict) -> JSONResponse:  # type: ignore[type-arg]
        """Submit a correction for a HITL issue to guide retry."""
        orch = get_orchestrator()
        if not orch:
            return JSONResponse({"status": "no orchestrator"}, status_code=400)
        correction = body.get("correction", "")
        orch.submit_hitl_correction(issue_number, correction)

        # Swap labels for immediate dashboard feedback
        for lbl in config.hitl_label:
            await pr_manager.remove_label(issue_number, lbl)
        await pr_manager.add_labels(issue_number, config.hitl_active_label)

        await event_bus.publish(
            HydraEvent(
                type=EventType.HITL_UPDATE,
                data={
                    "issue": issue_number,
                    "status": "processing",
                    "action": "correct",
                },
            )
        )
        return JSONResponse({"status": "ok"})

    @router.post("/api/hitl/{issue_number}/skip")
    async def hitl_skip(issue_number: int) -> JSONResponse:
        """Remove a HITL issue from the queue without action."""
        orch = get_orchestrator()
        if not orch:
            return JSONResponse({"status": "no orchestrator"}, status_code=400)
        orch.skip_hitl_issue(issue_number)
        state.remove_hitl_origin(issue_number)
        for lbl in config.hitl_label:
            await pr_manager.remove_label(issue_number, lbl)
        await event_bus.publish(
            HydraEvent(
                type=EventType.HITL_UPDATE,
                data={
                    "issue": issue_number,
                    "status": "resolved",
                    "action": "skip",
                },
            )
        )
        return JSONResponse({"status": "ok"})

    @router.post("/api/hitl/{issue_number}/close")
    async def hitl_close(issue_number: int) -> JSONResponse:
        """Close a HITL issue on GitHub."""
        orch = get_orchestrator()
        if not orch:
            return JSONResponse({"status": "no orchestrator"}, status_code=400)
        orch.skip_hitl_issue(issue_number)
        state.remove_hitl_origin(issue_number)
        await pr_manager.close_issue(issue_number)
        await event_bus.publish(
            HydraEvent(
                type=EventType.HITL_UPDATE,
                data={
                    "issue": issue_number,
                    "status": "resolved",
                    "action": "close",
                },
            )
        )
        return JSONResponse({"status": "ok"})

    @router.post("/api/hitl/{issue_number}/approve-memory")
    async def hitl_approve_memory(issue_number: int) -> JSONResponse:
        """Approve a HITL item as a memory suggestion, relabeling for sync."""
        orch = get_orchestrator()
        if not orch:
            return JSONResponse({"status": "no orchestrator"}, status_code=400)
        for lbl in config.improve_label:
            await pr_manager.remove_label(issue_number, lbl)
        for lbl in config.hitl_label:
            await pr_manager.remove_label(issue_number, lbl)
        await pr_manager.add_labels(issue_number, config.memory_label)
        orch.skip_hitl_issue(issue_number)
        state.remove_hitl_origin(issue_number)
        await event_bus.publish(
            HydraEvent(
                type=EventType.HITL_UPDATE,
                data={
                    "issue": issue_number,
                    "status": "resolved",
                    "action": "approved_as_memory",
                },
            )
        )
        return JSONResponse({"status": "ok"})

    @router.get("/api/human-input")
    async def get_human_input_requests() -> JSONResponse:
        orch = get_orchestrator()
        if orch:
            return JSONResponse(orch.human_input_requests)
        return JSONResponse({})

    @router.post("/api/human-input/{issue_number}")
    async def provide_human_input(issue_number: int, body: dict) -> JSONResponse:  # type: ignore[type-arg]
        orch = get_orchestrator()
        if orch:
            answer = body.get("answer", "")
            orch.provide_human_input(issue_number, answer)
            return JSONResponse({"status": "ok"})
        return JSONResponse({"status": "no orchestrator"}, status_code=400)

    @router.post("/api/control/start")
    async def start_orchestrator() -> JSONResponse:
        orch = get_orchestrator()
        if orch and orch.running:
            return JSONResponse({"error": "already running"}, status_code=409)

        from orchestrator import HydraOrchestrator

        new_orch = HydraOrchestrator(
            config,
            event_bus=event_bus,
            state=state,
        )
        set_orchestrator(new_orch)
        set_run_task(asyncio.create_task(new_orch.run()))
        return JSONResponse({"status": "started"})

    @router.post("/api/control/stop")
    async def stop_orchestrator() -> JSONResponse:
        orch = get_orchestrator()
        if not orch or not orch.running:
            return JSONResponse({"error": "not running"}, status_code=400)
        await orch.request_stop()
        return JSONResponse({"status": "stopping"})

    @router.get("/api/control/status")
    async def get_control_status() -> JSONResponse:
        orch = get_orchestrator()
        status = "idle"
        if orch:
            status = orch.run_status
        response = ControlStatusResponse(
            status=status,
            config=ControlStatusConfig(
                repo=config.repo,
                ready_label=config.ready_label,
                find_label=config.find_label,
                planner_label=config.planner_label,
                review_label=config.review_label,
                hitl_label=config.hitl_label,
                hitl_active_label=config.hitl_active_label,
                fixed_label=config.fixed_label,
                max_workers=config.max_workers,
                max_planners=config.max_planners,
                max_reviewers=config.max_reviewers,
                max_hitl_workers=config.max_hitl_workers,
                batch_size=config.batch_size,
                model=config.model,
            ),
        )
        return JSONResponse(response.model_dump())

    # Known background workers with human-friendly labels
    _bg_worker_defs = [
        ("memory_sync", "Memory Sync"),
        ("retrospective", "Retrospective"),
        ("metrics", "Metrics"),
        ("review_insights", "Review Insights"),
    ]

    @router.get("/api/system/workers")
    async def get_system_workers() -> JSONResponse:
        """Return last known status of each background worker."""
        orch = get_orchestrator()
        bg_states = orch.get_bg_worker_states() if orch else {}
        workers = []
        for name, label in _bg_worker_defs:
            if name in bg_states:
                entry = bg_states[name]
                workers.append(
                    BackgroundWorkerStatus(
                        name=name,
                        label=label,
                        status=entry["status"],
                        last_run=entry.get("last_run"),
                        details=entry.get("details", {}),
                    )
                )
            else:
                workers.append(BackgroundWorkerStatus(name=name, label=label))
        return JSONResponse(BackgroundWorkersResponse(workers=workers).model_dump())

    @router.get("/api/metrics")
    async def get_metrics() -> JSONResponse:
        """Return lifetime stats and derived rates."""
        lifetime_data = state.get_lifetime_stats()
        lifetime = LifetimeStats(**lifetime_data)
        rates: dict[str, float] = {}
        if lifetime.issues_completed > 0:
            rates["merge_rate"] = lifetime.prs_merged / lifetime.issues_completed
        return JSONResponse(
            MetricsResponse(lifetime=lifetime, rates=rates).model_dump()
        )

    @router.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket) -> None:
        await ws.accept()

        # Snapshot history BEFORE subscribing to avoid duplicates.
        # Events published between snapshot and subscribe are picked
        # up by the live queue, never sent twice.
        history = event_bus.get_history()

        async with event_bus.subscription() as queue:
            # Send history on connect
            for event in history:
                try:
                    await ws.send_text(event.model_dump_json())
                except Exception:
                    logger.warning(
                        "WebSocket error during history replay", exc_info=True
                    )
                    return

            # Stream live events
            try:
                while True:
                    event: HydraEvent = await queue.get()
                    await ws.send_text(event.model_dump_json())
            except WebSocketDisconnect:
                pass
            except Exception:
                logger.warning("WebSocket error during live streaming", exc_info=True)

    return router
