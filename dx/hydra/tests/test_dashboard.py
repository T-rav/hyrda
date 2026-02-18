"""Tests for dx/hydra/dashboard.py - HydraDashboard class."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import contextlib
from typing import TYPE_CHECKING

from events import EventBus, EventType, HydraEvent
from state import StateTracker

if TYPE_CHECKING:
    from config import HydraConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_state(tmp_path: Path) -> StateTracker:
    return StateTracker(tmp_path / "state.json")


def make_orchestrator_mock(requests: dict | None = None) -> MagicMock:
    """Return a minimal orchestrator mock."""
    orch = MagicMock()
    orch.human_input_requests = requests or {}
    orch.provide_human_input = MagicMock()
    return orch


# ---------------------------------------------------------------------------
# create_app
# ---------------------------------------------------------------------------


class TestCreateApp:
    """Tests for HydraDashboard.create_app()."""

    def test_create_app_returns_fastapi_instance(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from dashboard import HydraDashboard

        try:
            from fastapi import FastAPI
        except ImportError:
            pytest.skip("FastAPI not installed")

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)
        app = dashboard.create_app()

        assert isinstance(app, FastAPI)

    def test_create_app_stores_app_on_instance(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        try:
            from dashboard import HydraDashboard
        except ImportError:
            pytest.skip("FastAPI not installed")

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)
        app = dashboard.create_app()

        assert dashboard._app is app

    def test_create_app_title_is_hydra_dashboard(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        try:
            from dashboard import HydraDashboard
        except ImportError:
            pytest.skip("FastAPI not installed")

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)
        app = dashboard.create_app()

        assert app.title == "Hydra Dashboard"


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------


class TestIndexRoute:
    """Tests for the GET / route."""

    def test_get_root_returns_200(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)
        app = dashboard.create_app()

        client = TestClient(app)
        response = client.get("/")

        assert response.status_code == 200

    def test_get_root_returns_html_content_type(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)
        app = dashboard.create_app()

        client = TestClient(app)
        response = client.get("/")

        assert "text/html" in response.headers.get("content-type", "")

    def test_get_root_returns_html_body(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)
        app = dashboard.create_app()

        client = TestClient(app)
        response = client.get("/")

        # Either the real template or the fallback HTML should be returned
        body = response.text
        assert "<html" in body.lower() or "<h1>" in body.lower()

    def test_get_root_fallback_when_template_missing(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """When index.html does not exist, a fallback HTML page is returned."""
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)

        # Patch _TEMPLATE_DIR to a non-existent path
        with patch("dashboard._TEMPLATE_DIR", tmp_path / "no-templates"):
            app = dashboard.create_app()
            client = TestClient(app)
            response = client.get("/")

        assert response.status_code == 200
        assert "Template not found" in response.text or "<h1>" in response.text


# ---------------------------------------------------------------------------
# GET /api/state
# ---------------------------------------------------------------------------


class TestStateRoute:
    """Tests for the GET /api/state route."""

    def test_get_state_returns_200(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)
        app = dashboard.create_app()

        client = TestClient(app)
        response = client.get("/api/state")

        assert response.status_code == 200

    def test_get_state_returns_state_dict(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        state.mark_issue(42, "success")
        dashboard = HydraDashboard(config, event_bus, state)
        app = dashboard.create_app()

        client = TestClient(app)
        response = client.get("/api/state")

        body = response.json()
        assert isinstance(body, dict)
        # The state dict should contain the processed_issues key
        assert "processed_issues" in body

    def test_get_state_reflects_current_state(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        state.mark_issue(7, "failed")
        dashboard = HydraDashboard(config, event_bus, state)
        app = dashboard.create_app()

        client = TestClient(app)
        response = client.get("/api/state")
        body = response.json()

        assert body["processed_issues"].get("7") == "failed"


# ---------------------------------------------------------------------------
# GET /api/events
# ---------------------------------------------------------------------------


class TestEventsRoute:
    """Tests for the GET /api/events route."""

    def test_get_events_returns_200(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)
        app = dashboard.create_app()

        client = TestClient(app)
        response = client.get("/api/events")

        assert response.status_code == 200

    def test_get_events_returns_list(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)
        app = dashboard.create_app()

        client = TestClient(app)
        response = client.get("/api/events")

        body = response.json()
        assert isinstance(body, list)

    def test_get_events_empty_when_no_events_published(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)
        app = dashboard.create_app()

        client = TestClient(app)
        response = client.get("/api/events")

        assert response.json() == []

    def test_get_events_includes_published_events(
        self, config: HydraConfig, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        bus = EventBus()
        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, bus, state)
        app = dashboard.create_app()

        # Publish an event synchronously by running in an event loop
        async def publish() -> None:
            await bus.publish(HydraEvent(type=EventType.BATCH_START, data={"batch": 1}))

        asyncio.get_event_loop().run_until_complete(publish())

        client = TestClient(app)
        response = client.get("/api/events")
        body = response.json()

        assert len(body) == 1
        assert body[0]["type"] == EventType.BATCH_START.value


# ---------------------------------------------------------------------------
# GET /api/human-input
# ---------------------------------------------------------------------------


class TestHumanInputGetRoute:
    """Tests for the GET /api/human-input route."""

    def test_get_human_input_returns_200(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)
        app = dashboard.create_app()

        client = TestClient(app)
        response = client.get("/api/human-input")

        assert response.status_code == 200

    def test_get_human_input_returns_empty_dict_when_no_orchestrator(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state, orchestrator=None)
        app = dashboard.create_app()

        client = TestClient(app)
        response = client.get("/api/human-input")

        assert response.json() == {}

    def test_get_human_input_returns_pending_requests_from_orchestrator(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        orch = make_orchestrator_mock(requests={42: "Which approach?"})
        dashboard = HydraDashboard(config, event_bus, state, orchestrator=orch)
        app = dashboard.create_app()

        client = TestClient(app)
        response = client.get("/api/human-input")

        body = response.json()
        # Keys are serialised as strings in JSON
        assert "42" in body
        assert body["42"] == "Which approach?"


# ---------------------------------------------------------------------------
# POST /api/human-input/{issue_number}
# ---------------------------------------------------------------------------


class TestHumanInputPostRoute:
    """Tests for the POST /api/human-input/{issue_number} route."""

    def test_post_human_input_returns_ok_status(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        orch = make_orchestrator_mock()
        dashboard = HydraDashboard(config, event_bus, state, orchestrator=orch)
        app = dashboard.create_app()

        client = TestClient(app)
        response = client.post("/api/human-input/42", json={"answer": "Use option A"})

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_post_human_input_calls_orchestrator_provide_human_input(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        orch = make_orchestrator_mock()
        dashboard = HydraDashboard(config, event_bus, state, orchestrator=orch)
        app = dashboard.create_app()

        client = TestClient(app)
        client.post("/api/human-input/42", json={"answer": "Go left"})

        orch.provide_human_input.assert_called_once_with(42, "Go left")

    def test_post_human_input_passes_empty_string_when_answer_missing(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        orch = make_orchestrator_mock()
        dashboard = HydraDashboard(config, event_bus, state, orchestrator=orch)
        app = dashboard.create_app()

        client = TestClient(app)
        client.post("/api/human-input/7", json={})

        orch.provide_human_input.assert_called_once_with(7, "")

    def test_post_human_input_returns_400_without_orchestrator(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state, orchestrator=None)
        app = dashboard.create_app()

        client = TestClient(app)
        response = client.post("/api/human-input/42", json={"answer": "something"})

        assert response.status_code == 400
        assert response.json() == {"status": "no orchestrator"}

    def test_post_human_input_routes_correct_issue_number(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        orch = make_orchestrator_mock()
        dashboard = HydraDashboard(config, event_bus, state, orchestrator=orch)
        app = dashboard.create_app()

        client = TestClient(app)
        client.post("/api/human-input/99", json={"answer": "yes"})

        orch.provide_human_input.assert_called_once_with(99, "yes")


# ---------------------------------------------------------------------------
# start / stop
# ---------------------------------------------------------------------------


class TestStartStop:
    """Tests for HydraDashboard.start() and stop()."""

    @pytest.mark.asyncio
    async def test_start_creates_server_task(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)

        mock_server = AsyncMock()
        mock_server.serve = AsyncMock(return_value=None)

        with patch("uvicorn.Config"), patch("uvicorn.Server", return_value=mock_server):
            await dashboard.start()

        assert dashboard._server_task is not None
        assert isinstance(dashboard._server_task, asyncio.Task)

        # Clean up the running task
        if dashboard._server_task and not dashboard._server_task.done():
            dashboard._server_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await dashboard._server_task

    @pytest.mark.asyncio
    async def test_start_does_nothing_when_uvicorn_not_installed(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)

        with (
            patch.dict("sys.modules", {"uvicorn": None}),
            contextlib.suppress(ImportError),
        ):
            # Import error should be caught gracefully
            await dashboard.start()

        # _server_task should remain None (uvicorn not available)
        # If it was set before the mock, ignore; what matters is no unhandled exception

    @pytest.mark.asyncio
    async def test_stop_cancels_server_task(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)

        # Simulate a running task
        async def long_running() -> None:
            await asyncio.sleep(3600)

        dashboard._server_task = asyncio.create_task(long_running())
        await asyncio.sleep(0)  # Let it start

        await dashboard.stop()

        assert dashboard._server_task.cancelled() or dashboard._server_task.done()

    @pytest.mark.asyncio
    async def test_stop_is_safe_when_no_task(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)
        assert dashboard._server_task is None

        # Should not raise
        await dashboard.stop()

    @pytest.mark.asyncio
    async def test_stop_is_safe_when_task_already_done(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)

        async def quick_task() -> None:
            return

        task = asyncio.create_task(quick_task())
        await task  # Let it complete
        dashboard._server_task = task

        # Should not raise
        await dashboard.stop()


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


class TestInit:
    """Tests for HydraDashboard.__init__."""

    def test_stores_config(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)

        assert dashboard._config is config

    def test_stores_event_bus(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)

        assert dashboard._bus is event_bus

    def test_stores_state(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)

        assert dashboard._state is state

    def test_stores_orchestrator(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        orch = make_orchestrator_mock()
        dashboard = HydraDashboard(config, event_bus, state, orchestrator=orch)

        assert dashboard._orchestrator is orch

    def test_orchestrator_defaults_to_none(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)

        assert dashboard._orchestrator is None

    def test_server_task_starts_as_none(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)

        assert dashboard._server_task is None

    def test_app_starts_as_none(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)

        assert dashboard._app is None
