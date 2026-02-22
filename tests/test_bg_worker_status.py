"""Tests for background worker status tracking and API endpoints."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from events import EventBus, EventType
from models import BackgroundWorkersResponse, BackgroundWorkerStatus, MetricsResponse
from tests.conftest import make_state


class TestEventTypes:
    """Verify the new EventType members exist with correct values."""

    def test_memory_sync_event_type(self) -> None:
        assert EventType.MEMORY_SYNC == "memory_sync"

    def test_retrospective_event_type(self) -> None:
        assert EventType.RETROSPECTIVE == "retrospective"

    def test_metrics_update_event_type(self) -> None:
        assert EventType.METRICS_UPDATE == "metrics_update"

    def test_review_insight_event_type(self) -> None:
        assert EventType.REVIEW_INSIGHT == "review_insight"

    def test_background_worker_status_event_type(self) -> None:
        assert EventType.BACKGROUND_WORKER_STATUS == "background_worker_status"


class TestBackgroundWorkerStatusModel:
    """Verify BackgroundWorkerStatus Pydantic model."""

    def test_default_status_is_disabled(self) -> None:
        status = BackgroundWorkerStatus(name="test", label="Test")
        assert status.status == "disabled"
        assert status.last_run is None
        assert status.details == {}

    def test_full_model_serializes_correctly(self) -> None:
        status = BackgroundWorkerStatus(
            name="memory_sync",
            label="Memory Manager",
            status="ok",
            last_run="2026-02-20T10:30:00Z",
            details={"item_count": 12, "digest_chars": 2400},
        )
        data = status.model_dump()
        assert data["name"] == "memory_sync"
        assert data["label"] == "Memory Manager"
        assert data["status"] == "ok"
        assert data["last_run"] == "2026-02-20T10:30:00Z"
        assert data["details"]["item_count"] == 12

    def test_workers_response_model(self) -> None:
        resp = BackgroundWorkersResponse(
            workers=[
                BackgroundWorkerStatus(name="a", label="A", status="ok"),
                BackgroundWorkerStatus(name="b", label="B"),
            ]
        )
        data = resp.model_dump()
        assert len(data["workers"]) == 2
        assert data["workers"][0]["status"] == "ok"
        assert data["workers"][1]["status"] == "disabled"


class TestMetricsResponseModel:
    """Verify MetricsResponse Pydantic model."""

    def test_default_metrics_response(self) -> None:
        resp = MetricsResponse()
        data = resp.model_dump()
        assert data["lifetime"]["issues_completed"] == 0
        assert data["lifetime"]["prs_merged"] == 0
        assert data["rates"] == {}

    def test_metrics_with_rates(self) -> None:
        from models import LifetimeStats

        resp = MetricsResponse(
            lifetime=LifetimeStats(issues_completed=10, prs_merged=8),
            rates={"merge_rate": 0.8},
        )
        data = resp.model_dump()
        assert data["rates"]["merge_rate"] == 0.8


class TestOrchestratorBgWorkerTracking:
    """Verify orchestrator background worker state tracking."""

    def test_update_stores_state(self, config, event_bus: EventBus) -> None:
        from orchestrator import HydraOrchestrator

        orch = HydraOrchestrator(config, event_bus=event_bus)
        orch.update_bg_worker_status("memory_sync", "ok", {"item_count": 5})

        states = orch.get_bg_worker_states()
        assert "memory_sync" in states
        assert states["memory_sync"]["status"] == "ok"
        assert states["memory_sync"]["details"]["item_count"] == 5
        assert states["memory_sync"]["last_run"] is not None

    def test_get_returns_copy(self, config, event_bus: EventBus) -> None:
        from orchestrator import HydraOrchestrator

        orch = HydraOrchestrator(config, event_bus=event_bus)
        orch.update_bg_worker_status("metrics", "ok")

        states1 = orch.get_bg_worker_states()
        states2 = orch.get_bg_worker_states()
        assert states1 is not states2

    def test_update_replaces_previous(self, config, event_bus: EventBus) -> None:
        from orchestrator import HydraOrchestrator

        orch = HydraOrchestrator(config, event_bus=event_bus)
        orch.update_bg_worker_status("memory_sync", "ok", {"count": 1})
        orch.update_bg_worker_status("memory_sync", "error", {"count": 2})

        states = orch.get_bg_worker_states()
        assert states["memory_sync"]["status"] == "error"
        assert states["memory_sync"]["details"]["count"] == 2

    def test_empty_states_initially(self, config, event_bus: EventBus) -> None:
        from orchestrator import HydraOrchestrator

        orch = HydraOrchestrator(config, event_bus=event_bus)
        assert orch.get_bg_worker_states() == {}


class TestBgWorkerEnabled:
    """Tests for is_bg_worker_enabled / set_bg_worker_enabled."""

    def test_is_bg_worker_enabled_defaults_to_true(
        self, config, event_bus: EventBus
    ) -> None:
        from orchestrator import HydraOrchestrator

        orch = HydraOrchestrator(config, event_bus=event_bus)
        assert orch.is_bg_worker_enabled("memory_sync") is True

    def test_set_bg_worker_enabled_false(self, config, event_bus: EventBus) -> None:
        from orchestrator import HydraOrchestrator

        orch = HydraOrchestrator(config, event_bus=event_bus)
        orch.set_bg_worker_enabled("memory_sync", False)
        assert orch.is_bg_worker_enabled("memory_sync") is False

    def test_set_bg_worker_enabled_true_after_disable(
        self, config, event_bus: EventBus
    ) -> None:
        from orchestrator import HydraOrchestrator

        orch = HydraOrchestrator(config, event_bus=event_bus)
        orch.set_bg_worker_enabled("metrics", False)
        orch.set_bg_worker_enabled("metrics", True)
        assert orch.is_bg_worker_enabled("metrics") is True

    def test_get_bg_worker_states_includes_enabled_flag(
        self, config, event_bus: EventBus
    ) -> None:
        from orchestrator import HydraOrchestrator

        orch = HydraOrchestrator(config, event_bus=event_bus)
        orch.update_bg_worker_status("memory_sync", "ok")
        orch.set_bg_worker_enabled("memory_sync", False)

        states = orch.get_bg_worker_states()
        assert states["memory_sync"]["enabled"] is False


class TestSystemWorkersEndpoint:
    """Tests for GET /api/system/workers."""

    def _make_router(
        self,
        config,
        event_bus: EventBus,
        tmp_path: Path,
        orch=None,
    ):
        from dashboard_routes import create_router
        from pr_manager import PRManager

        state = make_state(tmp_path)
        pr_mgr = PRManager(config, event_bus)

        return create_router(
            config=config,
            event_bus=event_bus,
            state=state,
            pr_manager=pr_mgr,
            get_orchestrator=lambda: orch,
            set_orchestrator=lambda o: None,
            set_run_task=lambda t: None,
            ui_dist_dir=tmp_path / "no-dist",
            template_dir=tmp_path / "no-templates",
        )

    def _find_endpoint(self, router, path: str):
        for route in router.routes:
            if (
                hasattr(route, "path")
                and route.path == path
                and hasattr(route, "endpoint")
            ):
                return route.endpoint
        return None

    @pytest.mark.asyncio
    async def test_returns_all_workers(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        router = self._make_router(config, event_bus, tmp_path)
        endpoint = self._find_endpoint(router, "/api/system/workers")
        assert endpoint is not None

        response = await endpoint()
        data = json.loads(response.body)
        assert len(data["workers"]) == 9
        names = [w["name"] for w in data["workers"]]
        assert names == [
            "triage",
            "plan",
            "implement",
            "review",
            "memory_sync",
            "retrospective",
            "metrics",
            "review_insights",
            "pr_unsticker",
        ]

    @pytest.mark.asyncio
    async def test_returns_disabled_when_no_orchestrator(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        router = self._make_router(config, event_bus, tmp_path, orch=None)
        endpoint = self._find_endpoint(router, "/api/system/workers")
        response = await endpoint()
        data = json.loads(response.body)
        for w in data["workers"]:
            assert w["status"] == "disabled"
            assert w["last_run"] is None

    @pytest.mark.asyncio
    async def test_returns_tracked_state(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from orchestrator import HydraOrchestrator

        orch = HydraOrchestrator(config, event_bus=event_bus)
        orch.update_bg_worker_status("memory_sync", "ok", {"item_count": 12})

        router = self._make_router(config, event_bus, tmp_path, orch=orch)
        endpoint = self._find_endpoint(router, "/api/system/workers")
        response = await endpoint()
        data = json.loads(response.body)

        ms = next(w for w in data["workers"] if w["name"] == "memory_sync")
        assert ms["status"] == "ok"
        assert ms["details"]["item_count"] == 12
        assert ms["last_run"] is not None

        # Others should still be disabled
        retro = next(w for w in data["workers"] if w["name"] == "retrospective")
        assert retro["status"] == "disabled"


class TestMetricsEndpoint:
    """Tests for GET /api/metrics."""

    @pytest.mark.asyncio
    async def test_returns_lifetime_stats(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from dashboard_routes import create_router
        from pr_manager import PRManager

        state = make_state(tmp_path)
        state.record_issue_completed()
        state.record_issue_completed()
        state.record_pr_merged()

        pr_mgr = PRManager(config, event_bus)
        router = create_router(
            config=config,
            event_bus=event_bus,
            state=state,
            pr_manager=pr_mgr,
            get_orchestrator=lambda: None,
            set_orchestrator=lambda o: None,
            set_run_task=lambda t: None,
            ui_dist_dir=tmp_path / "no-dist",
            template_dir=tmp_path / "no-templates",
        )

        endpoint = None
        for route in router.routes:
            if (
                hasattr(route, "path")
                and route.path == "/api/metrics"
                and hasattr(route, "endpoint")
            ):
                endpoint = route.endpoint
                break

        assert endpoint is not None
        response = await endpoint()
        data = json.loads(response.body)
        assert data["lifetime"]["issues_completed"] == 2
        assert data["lifetime"]["prs_merged"] == 1
        assert data["rates"]["merge_rate"] == 0.5

    @pytest.mark.asyncio
    async def test_returns_empty_rates_when_no_issues(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from dashboard_routes import create_router
        from pr_manager import PRManager

        state = make_state(tmp_path)
        pr_mgr = PRManager(config, event_bus)
        router = create_router(
            config=config,
            event_bus=event_bus,
            state=state,
            pr_manager=pr_mgr,
            get_orchestrator=lambda: None,
            set_orchestrator=lambda o: None,
            set_run_task=lambda t: None,
            ui_dist_dir=tmp_path / "no-dist",
            template_dir=tmp_path / "no-templates",
        )

        endpoint = None
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/api/metrics":
                endpoint = route.endpoint
                break

        assert endpoint is not None
        response = await endpoint()
        data = json.loads(response.body)
        assert data["rates"] == {}
        assert data["lifetime"]["issues_completed"] == 0


class TestRouteRegistration:
    """Verify new routes are registered."""

    def test_system_workers_and_metrics_routes_registered(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from dashboard_routes import create_router
        from pr_manager import PRManager

        state = make_state(tmp_path)
        pr_mgr = PRManager(config, event_bus)
        router = create_router(
            config=config,
            event_bus=event_bus,
            state=state,
            pr_manager=pr_mgr,
            get_orchestrator=lambda: None,
            set_orchestrator=lambda o: None,
            set_run_task=lambda t: None,
            ui_dist_dir=tmp_path / "no-dist",
            template_dir=tmp_path / "no-templates",
        )

        paths = {route.path for route in router.routes}
        assert "/api/system/workers" in paths
        assert "/api/metrics" in paths
