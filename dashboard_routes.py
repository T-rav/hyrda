"""Route handlers for the Hydra dashboard API."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import ValidationError

from config import HydraConfig, save_config_file
from events import EventBus, EventType, HydraEvent
from models import (
    BackgroundWorkersResponse,
    BackgroundWorkerStatus,
    ControlStatusConfig,
    ControlStatusResponse,
    IntentRequest,
    IntentResponse,
    MetricsHistoryResponse,
    MetricsResponse,
    PipelineIssue,
    PipelineSnapshot,
    QueueStats,
)
from pr_manager import PRManager
from state import StateTracker
from timeline import TimelineBuilder

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

    def _serve_spa_index() -> HTMLResponse:
        """Serve the SPA index.html, falling back to template or placeholder."""
        react_index = ui_dist_dir / "index.html"
        if react_index.exists():
            return HTMLResponse(react_index.read_text())
        template_path = template_dir / "index.html"
        if template_path.exists():
            return HTMLResponse(template_path.read_text())
        return HTMLResponse("<h1>Hydra Dashboard</h1><p>Run 'make ui' to build.</p>")

    @router.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        return _serve_spa_index()

    @router.get("/api/state")
    async def get_state() -> JSONResponse:
        return JSONResponse(state.to_dict())

    @router.get("/api/stats")
    async def get_stats() -> JSONResponse:
        data: dict[str, Any] = state.get_lifetime_stats().model_dump()
        orch = get_orchestrator()
        if orch:
            data["queue"] = orch.issue_store.get_queue_stats().model_dump()
        return JSONResponse(data)

    @router.get("/api/queue")
    async def get_queue() -> JSONResponse:
        """Return current queue depths, active counts, and throughput."""
        orch = get_orchestrator()
        if orch:
            return JSONResponse(orch.issue_store.get_queue_stats().model_dump())
        return JSONResponse(QueueStats().model_dump())

    # Backend stage keys → frontend stage names
    _STAGE_NAME_MAP = {
        "find": "triage",
        "plan": "plan",
        "ready": "implement",
        "review": "review",
        "hitl": "hitl",
    }

    @router.get("/api/pipeline")
    async def get_pipeline() -> JSONResponse:
        """Return current pipeline snapshot with issues per stage."""
        orch = get_orchestrator()
        if orch:
            raw = orch.issue_store.get_pipeline_snapshot()
            mapped: dict[str, list[dict[str, object]]] = {}
            for backend_stage, issues in raw.items():
                frontend_stage = _STAGE_NAME_MAP.get(backend_stage, backend_stage)
                mapped[frontend_stage] = issues
            snapshot = PipelineSnapshot(
                stages={
                    k: [PipelineIssue(**i) for i in v]  # type: ignore[arg-type]
                    for k, v in mapped.items()
                }
            )
            return JSONResponse(snapshot.model_dump())
        return JSONResponse(PipelineSnapshot().model_dump())

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
                *config.improve_label,
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
            origin = state.get_hitl_origin(item.issue)
            if not cause and origin:
                if origin in config.improve_label:
                    cause = "Self-improvement proposal"
                elif origin in config.review_label:
                    cause = "Review escalation"
                elif origin in config.find_label:
                    cause = "Triage escalation"
                else:
                    cause = "Escalation (reason not recorded)"
            if cause:
                data["cause"] = cause
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
        for lbl in config.improve_label:
            await pr_manager.remove_label(issue_number, lbl)
        for lbl in config.hitl_label:
            await pr_manager.remove_label(issue_number, lbl)
        await pr_manager.add_labels(issue_number, config.memory_label)
        orch = get_orchestrator()
        if orch:
            orch.skip_hitl_issue(issue_number)
        state.remove_hitl_origin(issue_number)
        state.remove_hitl_cause(issue_number)
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
                improve_label=config.improve_label,
                memory_label=config.memory_label,
                max_workers=config.max_workers,
                max_planners=config.max_planners,
                max_reviewers=config.max_reviewers,
                max_hitl_workers=config.max_hitl_workers,
                batch_size=config.batch_size,
                model=config.model,
            ),
        )
        return JSONResponse(response.model_dump())

    # Mutable fields that can be changed at runtime via PATCH
    _MUTABLE_FIELDS = {
        "max_workers",
        "max_planners",
        "max_reviewers",
        "max_hitl_workers",
        "max_budget_usd",
        "model",
        "review_model",
        "review_budget_usd",
        "planner_model",
        "planner_budget_usd",
        "batch_size",
        "max_ci_fix_attempts",
        "max_quality_fix_attempts",
        "max_review_fix_attempts",
        "min_review_findings",
        "max_merge_conflict_fix_attempts",
        "ci_check_timeout",
        "ci_poll_interval",
        "poll_interval",
    }

    @router.patch("/api/control/config")
    async def patch_config(body: dict) -> JSONResponse:  # type: ignore[type-arg]
        """Update runtime config fields. Pass ``persist: true`` to save to disk."""
        persist = body.pop("persist", False)
        updates: dict[str, Any] = {}

        for key, value in body.items():
            if key not in _MUTABLE_FIELDS:
                continue
            if not hasattr(config, key):
                continue
            updates[key] = value

        if not updates:
            return JSONResponse({"status": "ok", "updated": {}})

        # Validate updates through Pydantic field constraints
        test_values = config.model_dump()
        test_values.update(updates)
        try:
            validated = HydraConfig.model_validate(test_values)
        except ValidationError as exc:
            errors = exc.errors()
            msg = "; ".join(
                f"{e['loc'][-1]}: {e['msg']}" for e in errors if e.get("loc")
            )
            return JSONResponse(
                {"status": "error", "message": msg or str(exc)},
                status_code=422,
            )

        # Apply validated values to the live config
        applied: dict[str, Any] = {}
        for key in updates:
            validated_value = getattr(validated, key)
            object.__setattr__(config, key, validated_value)
            applied[key] = validated_value

        if persist and applied:
            save_config_file(config.config_file, applied)

        return JSONResponse({"status": "ok", "updated": applied})

    # Known workers with human-friendly labels (pipeline loops + background)
    _bg_worker_defs = [
        ("triage", "Triage"),
        ("plan", "Plan"),
        ("implement", "Implement"),
        ("review", "Review"),
        ("memory_sync", "Memory Manager"),
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
            enabled = orch.is_bg_worker_enabled(name) if orch else True
            if name in bg_states:
                entry = bg_states[name]
                workers.append(
                    BackgroundWorkerStatus(
                        name=name,
                        label=label,
                        status=entry["status"],
                        enabled=enabled,
                        last_run=entry.get("last_run"),
                        details=entry.get("details", {}),
                    )
                )
            else:
                workers.append(
                    BackgroundWorkerStatus(name=name, label=label, enabled=enabled)
                )
        return JSONResponse(BackgroundWorkersResponse(workers=workers).model_dump())

    @router.post("/api/control/bg-worker")
    async def toggle_bg_worker(body: dict) -> JSONResponse:  # type: ignore[type-arg]
        """Enable or disable a background worker."""
        name = body.get("name")
        enabled = body.get("enabled")
        if not name or enabled is None:
            return JSONResponse(
                {"error": "name and enabled are required"}, status_code=400
            )
        orch = get_orchestrator()
        if not orch:
            return JSONResponse({"error": "no orchestrator"}, status_code=400)
        orch.set_bg_worker_enabled(name, bool(enabled))
        return JSONResponse({"status": "ok", "name": name, "enabled": bool(enabled)})

    @router.get("/api/metrics")
    async def get_metrics() -> JSONResponse:
        """Return lifetime stats and derived rates."""
        lifetime = state.get_lifetime_stats()
        rates: dict[str, float] = {}
        total_reviews = (
            lifetime.total_review_approvals + lifetime.total_review_request_changes
        )
        if lifetime.issues_completed > 0:
            rates["merge_rate"] = lifetime.prs_merged / lifetime.issues_completed
            rates["quality_fix_rate"] = (
                lifetime.total_quality_fix_rounds / lifetime.issues_completed
            )
            rates["hitl_escalation_rate"] = (
                lifetime.total_hitl_escalations / lifetime.issues_completed
            )
            rates["avg_implementation_seconds"] = (
                lifetime.total_implementation_seconds / lifetime.issues_completed
            )
        if total_reviews > 0:
            rates["first_pass_approval_rate"] = (
                lifetime.total_review_approvals / total_reviews
            )
            rates["reviewer_fix_rate"] = lifetime.total_reviewer_fixes / total_reviews
        return JSONResponse(
            MetricsResponse(lifetime=lifetime, rates=rates).model_dump()
        )

    @router.get("/api/metrics/github")
    async def get_github_metrics() -> JSONResponse:
        """Query GitHub for issue/PR counts by label state."""
        counts = await pr_manager.get_label_counts(config)
        return JSONResponse(counts)

    @router.get("/api/metrics/history")
    async def get_metrics_history() -> JSONResponse:
        """Historical snapshots from the metrics issue + current in-memory snapshot."""
        orch = get_orchestrator()
        if orch is None:
            return JSONResponse(MetricsHistoryResponse().model_dump())
        mgr = orch.metrics_manager
        snapshots = await mgr.fetch_history_from_issue()
        current = mgr.latest_snapshot
        return JSONResponse(
            MetricsHistoryResponse(
                snapshots=snapshots,
                current=current,
            ).model_dump()
        )

    @router.get("/api/timeline")
    async def get_timeline() -> JSONResponse:
        builder = TimelineBuilder(event_bus)
        timelines = builder.build_all()
        return JSONResponse([t.model_dump() for t in timelines])

    @router.get("/api/timeline/issue/{issue_num}")
    async def get_timeline_issue(issue_num: int) -> JSONResponse:
        builder = TimelineBuilder(event_bus)
        timeline = builder.build_for_issue(issue_num)
        if timeline is None:
            return JSONResponse({"error": "Issue not found"}, status_code=404)
        return JSONResponse(timeline.model_dump())

    @router.post("/api/intent")
    async def submit_intent(request: IntentRequest) -> JSONResponse:
        """Create a GitHub issue from a user intent typed in the dashboard."""
        title = request.text[:120]
        body = request.text
        labels = list(config.planner_label)

        issue_number = await pr_manager.create_issue(
            title=title, body=body, labels=labels
        )

        if issue_number == 0:
            return JSONResponse({"error": "Failed to create issue"}, status_code=500)

        url = f"https://github.com/{config.repo}/issues/{issue_number}"
        response = IntentResponse(issue_number=issue_number, title=title, url=url)
        return JSONResponse(response.model_dump())

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

    # SPA catch-all: serve index.html for any path not matched above.
    # This must be registered LAST so it doesn't shadow API/WS routes.
    @router.get("/{path:path}", response_model=None)
    async def spa_catchall(path: str) -> Response:
        # Don't catch API, WebSocket, or static-asset paths
        if path.startswith(("api/", "ws/", "assets/", "static/")) or path == "ws":
            return JSONResponse({"detail": "Not Found"}, status_code=404)

        # Serve root-level static files from ui/dist/ (e.g. logos, favicon)
        static_file = (ui_dist_dir / path).resolve()
        if static_file.is_relative_to(ui_dist_dir.resolve()) and static_file.is_file():
            return FileResponse(static_file)

        return _serve_spa_index()

    return router
