"""Live web dashboard for Hydra — FastAPI + WebSocket."""

import asyncio
import contextlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from config import HydraConfig
from events import EventBus, HydraEvent
from models import ControlStatusConfig, ControlStatusResponse, HITLItem, PRListItem
from state import StateTracker
from subprocess_util import run_subprocess

if TYPE_CHECKING:
    from orchestrator import HydraOrchestrator

logger = logging.getLogger("hydra.dashboard")

# React build output or fallback HTML template
_UI_DIST_DIR = Path(__file__).parent / "ui" / "dist"
_TEMPLATE_DIR = Path(__file__).parent / "templates"


class HydraDashboard:
    """Serves the live dashboard and streams events via WebSocket.

    Runs a uvicorn server in a background asyncio task so it
    doesn't block the orchestrator.
    """

    def __init__(
        self,
        config: HydraConfig,
        event_bus: EventBus,
        state: StateTracker,
        orchestrator: Optional["HydraOrchestrator"] = None,
    ) -> None:
        self._config = config
        self._bus = event_bus
        self._state = state
        self._orchestrator = orchestrator
        self._server_task: asyncio.Task[None] | None = None
        self._run_task: asyncio.Task[None] | None = None
        self._app: Any = None

    def create_app(self) -> Any:
        """Build and return the FastAPI application."""
        try:
            from fastapi import FastAPI, WebSocket, WebSocketDisconnect
            from fastapi.responses import HTMLResponse, JSONResponse
        except ImportError:
            logger.error(
                "FastAPI not installed. Run: uv pip install fastapi uvicorn websockets"
            )
            raise

        from fastapi.staticfiles import StaticFiles

        app = FastAPI(title="Hydra Dashboard", version="1.0.0")

        # Serve React build if available, otherwise fall back to template
        if _UI_DIST_DIR.exists() and (_UI_DIST_DIR / "index.html").exists():
            # Mount static assets first (js, css, etc.)
            assets_dir = _UI_DIST_DIR / "assets"
            if assets_dir.exists():
                app.mount(
                    "/assets",
                    StaticFiles(directory=str(assets_dir)),
                    name="assets",
                )

        @app.get("/", response_class=HTMLResponse)
        async def index() -> HTMLResponse:
            # Prefer React build
            react_index = _UI_DIST_DIR / "index.html"
            if react_index.exists():
                return HTMLResponse(react_index.read_text())
            # Fall back to plain HTML template
            template_path = _TEMPLATE_DIR / "index.html"
            if template_path.exists():
                return HTMLResponse(template_path.read_text())
            return HTMLResponse(
                "<h1>Hydra Dashboard</h1><p>Run 'make ui' to build.</p>"
            )

        @app.get("/api/state")
        async def get_state() -> JSONResponse:
            return JSONResponse(self._state.to_dict())

        @app.get("/api/stats")
        async def get_stats() -> JSONResponse:
            return JSONResponse(self._state.get_lifetime_stats())

        @app.get("/api/events")
        async def get_events() -> JSONResponse:
            history = self._bus.get_history()
            return JSONResponse([e.model_dump() for e in history])

        @app.get("/api/prs")
        async def get_prs() -> JSONResponse:
            """Fetch all open Hydra PRs from GitHub."""
            import json as _json

            try:
                seen: set[int] = set()
                prs: list[PRListItem] = []

                all_labels = list(
                    {
                        *self._config.ready_label,
                        *self._config.review_label,
                        *self._config.fixed_label,
                        *self._config.hitl_label,
                        *self._config.planner_label,
                    }
                )
                for label in all_labels:
                    try:
                        stdout = await run_subprocess(
                            "gh",
                            "pr",
                            "list",
                            "--repo",
                            self._config.repo,
                            "--label",
                            label,
                            "--state",
                            "open",
                            "--json",
                            "number,url,headRefName,isDraft,title",
                            "--limit",
                            "50",
                            gh_token=self._config.gh_token,
                        )
                    except RuntimeError:
                        continue

                    raw = _json.loads(stdout)
                    for p in raw:
                        pr_num = p["number"]
                        if pr_num in seen:
                            continue
                        seen.add(pr_num)
                        # Extract issue number from branch name agent/issue-N
                        branch = p.get("headRefName", "")
                        issue_num = 0
                        if branch.startswith("agent/issue-"):
                            with contextlib.suppress(ValueError):
                                issue_num = int(branch.split("-")[-1])
                        prs.append(
                            PRListItem(
                                pr=pr_num,
                                issue=issue_num,
                                branch=branch,
                                url=p.get("url", ""),
                                draft=p.get("isDraft", False),
                                title=p.get("title", ""),
                            )
                        )
                return JSONResponse([item.model_dump() for item in prs])
            except Exception:
                return JSONResponse([])

        @app.get("/api/hitl")
        async def get_hitl() -> JSONResponse:
            """Fetch issues/PRs labeled for human-in-the-loop (stuck on CI)."""
            import json as _json

            try:
                # Fetch issues with any HITL label, deduplicated
                seen_issues: set[int] = set()
                raw_issues: list[dict[str, Any]] = []
                for label in self._config.hitl_label:
                    try:
                        stdout = await run_subprocess(
                            "gh",
                            "issue",
                            "list",
                            "--repo",
                            self._config.repo,
                            "--label",
                            label,
                            "--state",
                            "open",
                            "--json",
                            "number,title,url",
                            "--limit",
                            "50",
                            gh_token=self._config.gh_token,
                        )
                    except RuntimeError:
                        continue
                    for issue in _json.loads(stdout):
                        if issue["number"] not in seen_issues:
                            seen_issues.add(issue["number"])
                            raw_issues.append(issue)

                items: list[HITLItem] = []
                for issue in raw_issues:
                    branch = self._config.branch_for_issue(issue["number"])
                    # Look up the PR for this issue's branch
                    pr_number = 0
                    pr_url = ""
                    try:
                        pr_stdout = await run_subprocess(
                            "gh",
                            "pr",
                            "list",
                            "--repo",
                            self._config.repo,
                            "--head",
                            branch,
                            "--state",
                            "open",
                            "--json",
                            "number,url",
                            "--limit",
                            "1",
                            gh_token=self._config.gh_token,
                        )
                        pr_data = _json.loads(pr_stdout)
                        if pr_data:
                            pr_number = pr_data[0]["number"]
                            pr_url = pr_data[0].get("url", "")
                    except RuntimeError:
                        pass

                    items.append(
                        HITLItem(
                            issue=issue["number"],
                            title=issue.get("title", ""),
                            issueUrl=issue.get("url", ""),
                            pr=pr_number,
                            prUrl=pr_url,
                            branch=branch,
                        )
                    )
                return JSONResponse([item.model_dump() for item in items])
            except Exception:
                return JSONResponse([])

        @app.get("/api/human-input")
        async def get_human_input_requests() -> JSONResponse:
            if self._orchestrator:
                return JSONResponse(self._orchestrator.human_input_requests)
            return JSONResponse({})

        @app.post("/api/human-input/{issue_number}")
        async def provide_human_input(issue_number: int, body: dict) -> JSONResponse:  # type: ignore[type-arg]
            if self._orchestrator:
                answer = body.get("answer", "")
                self._orchestrator.provide_human_input(issue_number, answer)
                return JSONResponse({"status": "ok"})
            return JSONResponse({"status": "no orchestrator"}, status_code=400)

        @app.post("/api/control/start")
        async def start_orchestrator() -> JSONResponse:
            if self._orchestrator and self._orchestrator.running:
                return JSONResponse({"error": "already running"}, status_code=409)

            from orchestrator import HydraOrchestrator

            orch = HydraOrchestrator(
                self._config,
                event_bus=self._bus,
                state=self._state,
            )
            self._orchestrator = orch
            self._run_task = asyncio.create_task(orch.run())
            return JSONResponse({"status": "started"})

        @app.post("/api/control/stop")
        async def stop_orchestrator() -> JSONResponse:
            if not self._orchestrator or not self._orchestrator.running:
                return JSONResponse({"error": "not running"}, status_code=400)
            await self._orchestrator.request_stop()
            return JSONResponse({"status": "stopping"})

        @app.get("/api/control/status")
        async def get_control_status() -> JSONResponse:
            status = "idle"
            if self._orchestrator:
                status = self._orchestrator.run_status
            response = ControlStatusResponse(
                status=status,
                config=ControlStatusConfig(
                    repo=self._config.repo,
                    ready_label=self._config.ready_label,
                    find_label=self._config.find_label,
                    planner_label=self._config.planner_label,
                    review_label=self._config.review_label,
                    hitl_label=self._config.hitl_label,
                    fixed_label=self._config.fixed_label,
                    max_workers=self._config.max_workers,
                    max_planners=self._config.max_planners,
                    max_reviewers=self._config.max_reviewers,
                    batch_size=self._config.batch_size,
                    model=self._config.model,
                ),
            )
            return JSONResponse(response.model_dump())

        @app.websocket("/ws")
        async def websocket_endpoint(ws: WebSocket) -> None:
            await ws.accept()

            # Snapshot history BEFORE subscribing to avoid duplicates.
            # Events published between snapshot and subscribe are picked
            # up by the live queue, never sent twice.
            history = self._bus.get_history()
            queue = self._bus.subscribe()

            # Send history on connect
            for event in history:
                try:
                    await ws.send_text(event.model_dump_json())
                except Exception:
                    logger.warning(
                        "WebSocket error during history replay", exc_info=True
                    )
                    break

            # Stream live events
            try:
                while True:
                    event: HydraEvent = await queue.get()
                    await ws.send_text(event.model_dump_json())
            except WebSocketDisconnect:
                pass
            except Exception:
                logger.warning("WebSocket error during live streaming", exc_info=True)
                pass
            finally:
                self._bus.unsubscribe(queue)

        self._app = app
        return app

    async def start(self) -> None:
        """Start the dashboard server in a background task."""
        try:
            import uvicorn
        except ImportError:
            logger.warning("uvicorn not installed — dashboard disabled")
            return

        app = self.create_app()
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=self._config.dashboard_port,
            log_level="warning",
        )
        server = uvicorn.Server(config)

        self._server_task = asyncio.create_task(server.serve())
        logger.info(
            "Dashboard running at http://localhost:%d",
            self._config.dashboard_port,
        )

    async def stop(self) -> None:
        """Stop the background server task."""
        if self._server_task and not self._server_task.done():
            self._server_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._server_task
        logger.info("Dashboard stopped")
