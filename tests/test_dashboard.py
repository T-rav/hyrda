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


def make_orchestrator_mock(
    requests: dict | None = None,
    running: bool = False,
    run_status: str = "idle",
) -> MagicMock:
    """Return a minimal orchestrator mock."""
    orch = MagicMock()
    orch.human_input_requests = requests or {}
    orch.provide_human_input = MagicMock()
    orch.running = running
    orch.run_status = run_status
    orch.stop = MagicMock()
    orch.request_stop = MagicMock()
    orch._publish_status = AsyncMock()
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

        # Patch both _UI_DIST_DIR and _TEMPLATE_DIR to non-existent paths
        with (
            patch("dashboard._UI_DIST_DIR", tmp_path / "no-dist"),
            patch("dashboard._TEMPLATE_DIR", tmp_path / "no-templates"),
        ):
            app = dashboard.create_app()
            client = TestClient(app)
            response = client.get("/")

        assert response.status_code == 200
        assert "<h1>" in response.text


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
        assert "processed_issues" in body

    def test_get_state_includes_lifetime_stats(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)
        app = dashboard.create_app()

        client = TestClient(app)
        response = client.get("/api/state")

        body = response.json()
        assert "lifetime_stats" in body

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
# GET /api/stats
# ---------------------------------------------------------------------------


class TestStatsRoute:
    """Tests for the GET /api/stats route."""

    def test_stats_endpoint_returns_lifetime_stats(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)
        app = dashboard.create_app()

        client = TestClient(app)
        response = client.get("/api/stats")

        assert response.status_code == 200
        body = response.json()
        assert body == {"issues_completed": 0, "prs_merged": 0, "issues_created": 0}

    def test_stats_endpoint_reflects_incremented_values(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        state.record_pr_merged()
        state.record_issue_completed()
        state.record_issue_created()
        state.record_issue_created()
        dashboard = HydraDashboard(config, event_bus, state)
        app = dashboard.create_app()

        client = TestClient(app)
        response = client.get("/api/stats")

        body = response.json()
        assert body["prs_merged"] == 1
        assert body["issues_completed"] == 1
        assert body["issues_created"] == 2


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

        async def publish() -> None:
            await bus.publish(HydraEvent(type=EventType.BATCH_START, data={"batch": 1}))

        asyncio.run(publish())

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
            await dashboard.start()

    @pytest.mark.asyncio
    async def test_stop_cancels_server_task(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)

        async def long_running() -> None:
            await asyncio.sleep(3600)

        dashboard._server_task = asyncio.create_task(long_running())
        await asyncio.sleep(0)

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
        await task
        dashboard._server_task = task

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

    def test_run_task_starts_as_none(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)

        assert dashboard._run_task is None


# ---------------------------------------------------------------------------
# POST /api/control/start
# ---------------------------------------------------------------------------


class TestControlStartEndpoint:
    """Tests for the POST /api/control/start route."""

    def test_start_returns_started(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)
        app = dashboard.create_app()

        client = TestClient(app)

        with patch("orchestrator.HydraOrchestrator") as MockOrch:
            mock_orch_inst = AsyncMock()
            mock_orch_inst.run = AsyncMock(return_value=None)
            mock_orch_inst.running = False
            mock_orch_inst.stop = MagicMock()
            MockOrch.return_value = mock_orch_inst

            response = client.post("/api/control/start")

        assert response.status_code == 200
        assert response.json()["status"] == "started"

    def test_start_returns_409_when_already_running(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        orch = make_orchestrator_mock(running=True, run_status="running")
        dashboard = HydraDashboard(config, event_bus, state, orchestrator=orch)
        app = dashboard.create_app()

        client = TestClient(app)
        response = client.post("/api/control/start")

        assert response.status_code == 409
        assert "already running" in response.json()["error"]


# ---------------------------------------------------------------------------
# POST /api/control/stop
# ---------------------------------------------------------------------------


class TestControlStopEndpoint:
    """Tests for the POST /api/control/stop route."""

    def test_stop_returns_400_when_not_running(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)
        app = dashboard.create_app()

        client = TestClient(app)
        response = client.post("/api/control/stop")

        assert response.status_code == 400
        assert "not running" in response.json()["error"]

    def test_stop_returns_stopping_when_running(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        orch = make_orchestrator_mock(running=True, run_status="running")
        dashboard = HydraDashboard(config, event_bus, state, orchestrator=orch)
        app = dashboard.create_app()

        client = TestClient(app)
        response = client.post("/api/control/stop")

        assert response.status_code == 200
        assert response.json()["status"] == "stopping"
        orch.request_stop.assert_called_once()

    def test_stop_returns_400_when_orchestrator_not_running(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        orch = make_orchestrator_mock(running=False, run_status="idle")
        dashboard = HydraDashboard(config, event_bus, state, orchestrator=orch)
        app = dashboard.create_app()

        client = TestClient(app)
        response = client.post("/api/control/stop")

        assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/control/status
# ---------------------------------------------------------------------------


class TestControlStatusEndpoint:
    """Tests for the GET /api/control/status route."""

    def test_status_returns_idle_when_no_orchestrator(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)
        app = dashboard.create_app()

        client = TestClient(app)
        response = client.get("/api/control/status")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "idle"

    def test_status_returns_running_when_orchestrator_active(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        orch = make_orchestrator_mock(running=True, run_status="running")
        dashboard = HydraDashboard(config, event_bus, state, orchestrator=orch)
        app = dashboard.create_app()

        client = TestClient(app)
        response = client.get("/api/control/status")

        assert response.status_code == 200
        assert response.json()["status"] == "running"

    def test_status_includes_config_info(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)
        app = dashboard.create_app()

        client = TestClient(app)
        response = client.get("/api/control/status")

        body = response.json()
        assert body["config"]["repo"] == config.repo
        assert body["config"]["ready_label"] == config.ready_label
        assert body["config"]["find_label"] == config.find_label
        assert body["config"]["planner_label"] == config.planner_label
        assert body["config"]["review_label"] == config.review_label
        assert body["config"]["hitl_label"] == config.hitl_label
        assert body["config"]["fixed_label"] == config.fixed_label
        assert body["config"]["max_planners"] == config.max_planners
        assert body["config"]["max_reviewers"] == config.max_reviewers


# ---------------------------------------------------------------------------
# GET /api/hitl
# ---------------------------------------------------------------------------


def _make_gh_proc(stdout: str = "[]", returncode: int = 0) -> AsyncMock:
    """Build a mock for asyncio.create_subprocess_exec returning *stdout*."""
    proc = AsyncMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout.encode(), b""))
    return proc


class TestHITLRoute:
    """Tests for the GET /api/hitl route."""

    def test_hitl_returns_200(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)
        app = dashboard.create_app()

        client = TestClient(app)
        with patch("asyncio.create_subprocess_exec", return_value=_make_gh_proc()):
            response = client.get("/api/hitl")

        assert response.status_code == 200

    def test_hitl_returns_empty_list_when_no_issues(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)
        app = dashboard.create_app()

        client = TestClient(app)
        with patch("asyncio.create_subprocess_exec", return_value=_make_gh_proc("[]")):
            response = client.get("/api/hitl")

        assert response.json() == []

    def test_hitl_returns_issues_with_pr_info(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        import json as _json

        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)
        app = dashboard.create_app()

        issues_json = _json.dumps(
            [
                {
                    "number": 42,
                    "title": "Fix widget",
                    "url": "https://github.com/org/repo/issues/42",
                },
            ]
        )
        pr_json = _json.dumps(
            [
                {"number": 99, "url": "https://github.com/org/repo/pull/99"},
            ]
        )

        call_count = 0

        async def mock_exec(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_gh_proc(issues_json)
            return _make_gh_proc(pr_json)

        client = TestClient(app)
        with patch("asyncio.create_subprocess_exec", side_effect=mock_exec):
            response = client.get("/api/hitl")

        body = response.json()
        assert len(body) == 1
        assert body[0]["issue"] == 42
        assert body[0]["title"] == "Fix widget"
        assert body[0]["pr"] == 99
        assert body[0]["branch"] == "agent/issue-42"

    def test_hitl_returns_empty_on_gh_failure(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)
        app = dashboard.create_app()

        client = TestClient(app)
        with patch(
            "asyncio.create_subprocess_exec",
            return_value=_make_gh_proc("", returncode=1),
        ):
            response = client.get("/api/hitl")

        assert response.json() == []

    def test_hitl_shows_zero_pr_when_no_pr_found(
        self, config: HydraConfig, event_bus: EventBus, tmp_path: Path
    ) -> None:
        import json as _json

        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, event_bus, state)
        app = dashboard.create_app()

        issues_json = _json.dumps(
            [
                {"number": 10, "title": "Broken thing", "url": ""},
            ]
        )

        call_count = 0

        async def mock_exec(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_gh_proc(issues_json)
            return _make_gh_proc("[]")  # No PR found

        client = TestClient(app)
        with patch("asyncio.create_subprocess_exec", side_effect=mock_exec):
            response = client.get("/api/hitl")

        body = response.json()
        assert len(body) == 1
        assert body[0]["pr"] == 0
        assert body[0]["prUrl"] == ""


# ---------------------------------------------------------------------------
# WebSocket error logging
# ---------------------------------------------------------------------------


class TestWebSocketErrorLogging:
    """Tests that unexpected WebSocket errors are logged, not silently swallowed."""

    def test_websocket_logs_warning_on_history_replay_error(
        self, config: HydraConfig, tmp_path: Path
    ) -> None:
        """When send_text raises during history replay, a warning is logged."""
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        bus = EventBus()
        state = make_state(tmp_path)

        # Publish an event so history is non-empty
        async def publish() -> None:
            await bus.publish(HydraEvent(type=EventType.BATCH_START, data={"batch": 1}))

        asyncio.run(publish())

        dashboard = HydraDashboard(config, bus, state)
        app = dashboard.create_app()
        client = TestClient(app)

        with patch("dashboard.logger") as mock_logger:
            with (
                patch(
                    "starlette.websockets.WebSocket.send_text",
                    side_effect=RuntimeError("serialization failed"),
                ),
                client.websocket_connect("/ws"),
            ):
                pass

            mock_logger.warning.assert_any_call(
                "WebSocket error during history replay", exc_info=True
            )

    def test_websocket_logs_warning_on_live_stream_error(
        self, config: HydraConfig, tmp_path: Path
    ) -> None:
        """When send_text raises during live streaming, a warning is logged."""
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        bus = EventBus()
        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, bus, state)
        app = dashboard.create_app()
        client = TestClient(app)

        # Pre-populate a queue with one event so queue.get() returns immediately
        event = HydraEvent(type=EventType.BATCH_START, data={"x": 1})
        pre_populated_queue: asyncio.Queue[HydraEvent] = asyncio.Queue()
        pre_populated_queue.put_nowait(event)

        with patch("dashboard.logger") as mock_logger:
            # subscribe() returns the pre-populated queue (no history, so
            # send_text is only called during the live streaming phase)
            with (
                patch.object(bus, "subscribe", return_value=pre_populated_queue),
                patch.object(bus, "get_history", return_value=[]),
                patch(
                    "starlette.websockets.WebSocket.send_text",
                    side_effect=RuntimeError("live stream send failed"),
                ),
                client.websocket_connect("/ws"),
            ):
                pass

            mock_logger.warning.assert_any_call(
                "WebSocket error during live streaming", exc_info=True
            )

    def test_websocket_disconnect_not_logged(
        self, config: HydraConfig, tmp_path: Path
    ) -> None:
        """WebSocketDisconnect should be handled silently (no warning logged)."""
        from fastapi.testclient import TestClient

        from dashboard import HydraDashboard

        bus = EventBus()
        state = make_state(tmp_path)
        dashboard = HydraDashboard(config, bus, state)
        app = dashboard.create_app()
        client = TestClient(app)

        with patch("dashboard.logger") as mock_logger:
            with client.websocket_connect("/ws"):
                # Just connect and disconnect normally
                pass

            # logger.warning should NOT have been called with WebSocket error messages
            for call in mock_logger.warning.call_args_list:
                assert "WebSocket error" not in str(call)
