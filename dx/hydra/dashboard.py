"""Live web dashboard for Hydra — FastAPI + WebSocket."""

import asyncio
import contextlib
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from config import HydraConfig
from events import EventBus, HydraEvent
from state import StateTracker

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
        self._server_task: Optional[asyncio.Task[None]] = None
        self._run_task: Optional[asyncio.Task[None]] = None
        self._app: Optional[object] = None

    def create_app(self) -> object:
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
            """Fetch open PRs labeled hydra-review from GitHub."""
            import json as _json

            try:
                env = {**os.environ}
                env.pop("CLAUDECODE", None)
                proc = await asyncio.create_subprocess_exec(
                    "gh", "pr", "list",
                    "--repo", self._config.repo,
                    "--label", "hydra-review",
                    "--state", "open",
                    "--json", "number,url,headRefName,isDraft,title",
                    "--limit", "50",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )
                stdout, _ = await proc.communicate()
                if proc.returncode != 0:
                    return JSONResponse([])

                raw = _json.loads(stdout.decode())
                prs = []
                for p in raw:
                    # Extract issue number from branch name agent/issue-N
                    branch = p.get("headRefName", "")
                    issue_num = 0
                    if branch.startswith("agent/issue-"):
                        try:
                            issue_num = int(branch.split("-")[-1])
                        except ValueError:
                            pass
                    prs.append({
                        "pr": p["number"],
                        "issue": issue_num,
                        "branch": branch,
                        "url": p.get("url", ""),
                        "draft": p.get("isDraft", False),
                        "title": p.get("title", ""),
                    })
                return JSONResponse(prs)
            except Exception:
                return JSONResponse([])

        @app.get("/api/hitl")
        async def get_hitl() -> JSONResponse:
            """Fetch issues/PRs labeled hydra-hitl (stuck on CI)."""
            import json as _json

            try:
                env = {**os.environ}
                env.pop("CLAUDECODE", None)

                # Fetch issues with hydra-hitl label
                proc = await asyncio.create_subprocess_exec(
                    "gh", "issue", "list",
                    "--repo", self._config.repo,
                    "--label", "hydra-hitl",
                    "--state", "open",
                    "--json", "number,title,url",
                    "--limit", "50",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )
                stdout, _ = await proc.communicate()
                if proc.returncode != 0:
                    return JSONResponse([])

                raw_issues = _json.loads(stdout.decode())
                items = []
                for issue in raw_issues:
                    branch = f"agent/issue-{issue['number']}"
                    # Look up the PR for this issue's branch
                    pr_proc = await asyncio.create_subprocess_exec(
                        "gh", "pr", "list",
                        "--repo", self._config.repo,
                        "--head", branch,
                        "--state", "open",
                        "--json", "number,url",
                        "--limit", "1",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        env=env,
                    )
                    pr_stdout, _ = await pr_proc.communicate()
                    pr_number = 0
                    pr_url = ""
                    if pr_proc.returncode == 0:
                        pr_data = _json.loads(pr_stdout.decode())
                        if pr_data:
                            pr_number = pr_data[0]["number"]
                            pr_url = pr_data[0].get("url", "")

                    items.append({
                        "issue": issue["number"],
                        "title": issue.get("title", ""),
                        "issueUrl": issue.get("url", ""),
                        "pr": pr_number,
                        "prUrl": pr_url,
                        "branch": branch,
                    })
                return JSONResponse(items)
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
            self._orchestrator.request_stop()
            await self._orchestrator._publish_status()
            return JSONResponse({"status": "stopping"})

        @app.get("/api/control/status")
        async def get_control_status() -> JSONResponse:
            status = "idle"
            if self._orchestrator:
                status = self._orchestrator.run_status
            return JSONResponse(
                {
                    "status": status,
                    "config": {
                        "repo": self._config.repo,
                        "label": self._config.label,
                        "max_workers": self._config.max_workers,
                        "batch_size": self._config.batch_size,
                        "model": self._config.model,
                    },
                }
            )

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
                    break

            # Stream live events
            try:
                while True:
                    event: HydraEvent = await queue.get()
                    await ws.send_text(event.model_dump_json())
            except WebSocketDisconnect:
                pass
            except Exception:
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
