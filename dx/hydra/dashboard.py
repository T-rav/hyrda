"""Live web dashboard for Hydra — FastAPI + WebSocket."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING

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
        orchestrator: HydraOrchestrator | None = None,
    ) -> None:
        self._config = config
        self._bus = event_bus
        self._state = state
        self._orchestrator = orchestrator
        self._server_task: asyncio.Task[None] | None = None
        self._app: object | None = None

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

        @app.get("/api/events")
        async def get_events() -> JSONResponse:
            history = self._bus.get_history()
            return JSONResponse([e.model_dump() for e in history])

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

        @app.websocket("/ws")
        async def websocket_endpoint(ws: WebSocket) -> None:
            await ws.accept()
            queue = self._bus.subscribe()

            # Send history on connect
            for event in self._bus.get_history():
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
            host="0.0.0.0",
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
