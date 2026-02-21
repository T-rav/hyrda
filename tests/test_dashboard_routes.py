"""Tests for dashboard_routes.py — route factory and handler registration."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from events import EventBus
from models import HITLItem
from state import StateTracker


def make_state(tmp_path: Path) -> StateTracker:
    return StateTracker(tmp_path / "state.json")


class TestCreateRouter:
    """Tests for create_router factory function."""

    def test_create_router_returns_api_router(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi import APIRouter

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

        assert isinstance(router, APIRouter)

    def test_router_registers_expected_routes(
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

        expected_paths = {
            "/",
            "/api/state",
            "/api/stats",
            "/api/metrics",
            "/api/events",
            "/api/prs",
            "/api/hitl",
            "/api/human-input",
            "/api/human-input/{issue_number}",
            "/api/control/start",
            "/api/control/stop",
            "/api/control/status",
            "/api/system/workers",
            "/api/hitl/{issue_number}/correct",
            "/api/hitl/{issue_number}/skip",
            "/api/hitl/{issue_number}/close",
            "/api/timeline",
            "/api/timeline/issue/{issue_num}",
            "/ws",
            "/{path:path}",
        }

        assert expected_paths.issubset(paths)


class TestControlStatusImproveLabel:
    """Tests that /api/control/status includes improve_label."""

    @pytest.mark.asyncio
    async def test_control_status_includes_improve_label(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """GET /api/control/status should include improve_label from config."""
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

        get_control_status = None
        for route in router.routes:
            if (
                hasattr(route, "path")
                and route.path == "/api/control/status"
                and hasattr(route, "endpoint")
            ):
                get_control_status = route.endpoint  # type: ignore[union-attr]
                break

        assert get_control_status is not None
        response = await get_control_status()
        import json

        data = json.loads(response.body)
        assert "config" in data
        assert "improve_label" in data["config"]
        assert data["config"]["improve_label"] == config.improve_label


class TestHITLEndpointCause:
    """Tests that /api/hitl includes the cause from state."""

    @pytest.mark.asyncio
    async def test_hitl_endpoint_includes_cause_from_state(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """When a HITL cause is set in state, it should appear in the response."""
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

        # Set a cause in state for issue 42
        state.set_hitl_cause(42, "CI failed after 2 fix attempt(s)")

        # Mock list_hitl_items to return a single item
        hitl_item = HITLItem(issue=42, title="Fix bug", pr=101)
        pr_mgr.list_hitl_items = AsyncMock(return_value=[hitl_item])  # type: ignore[method-assign]

        # Find and call the get_hitl handler
        get_hitl = None
        for route in router.routes:
            if (
                hasattr(route, "path")
                and route.path == "/api/hitl"
                and hasattr(route, "endpoint")
            ):
                get_hitl = route.endpoint  # type: ignore[union-attr]
                break

        assert get_hitl is not None
        response = await get_hitl()
        data = response.body  # JSONResponse stores body as bytes
        import json

        items = json.loads(data)
        assert len(items) == 1
        assert items[0]["cause"] == "CI failed after 2 fix attempt(s)"

    @pytest.mark.asyncio
    async def test_hitl_endpoint_omits_cause_when_not_set(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """When no cause is set, the default empty string from model should be present."""
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

        # No cause set in state
        hitl_item = HITLItem(issue=42, title="Fix bug", pr=101)
        pr_mgr.list_hitl_items = AsyncMock(return_value=[hitl_item])  # type: ignore[method-assign]

        get_hitl = None
        for route in router.routes:
            if (
                hasattr(route, "path")
                and route.path == "/api/hitl"
                and hasattr(route, "endpoint")
            ):
                get_hitl = route.endpoint  # type: ignore[union-attr]
                break

        assert get_hitl is not None
        response = await get_hitl()
        import json

        items = json.loads(response.body)
        assert len(items) == 1
        # No cause or origin — should remain empty
        assert items[0]["cause"] == ""

    @pytest.mark.asyncio
    async def test_hitl_endpoint_falls_back_to_origin_label(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """When no cause is set but origin is, should fall back to origin description."""
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

        # Set origin but not cause
        state.set_hitl_origin(42, "hydra-review")

        hitl_item = HITLItem(issue=42, title="Fix bug", pr=101)
        pr_mgr.list_hitl_items = AsyncMock(return_value=[hitl_item])  # type: ignore[method-assign]

        get_hitl = None
        for route in router.routes:
            if (
                hasattr(route, "path")
                and route.path == "/api/hitl"
                and hasattr(route, "endpoint")
            ):
                get_hitl = route.endpoint  # type: ignore[union-attr]
                break

        assert get_hitl is not None
        response = await get_hitl()
        import json

        items = json.loads(response.body)
        assert len(items) == 1
        assert items[0]["cause"] == "Review escalation"

    @pytest.mark.asyncio
    async def test_hitl_endpoint_origin_fallback_unknown_label(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """Unknown origin label should produce generic fallback message."""
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

        state.set_hitl_origin(42, "some-unknown-label")

        hitl_item = HITLItem(issue=42, title="Fix bug", pr=101)
        pr_mgr.list_hitl_items = AsyncMock(return_value=[hitl_item])  # type: ignore[method-assign]

        get_hitl = None
        for route in router.routes:
            if (
                hasattr(route, "path")
                and route.path == "/api/hitl"
                and hasattr(route, "endpoint")
            ):
                get_hitl = route.endpoint  # type: ignore[union-attr]
                break

        assert get_hitl is not None
        response = await get_hitl()
        import json

        items = json.loads(response.body)
        assert len(items) == 1
        assert items[0]["cause"] == "Escalation (reason not recorded)"

    @pytest.mark.asyncio
    async def test_hitl_endpoint_cause_takes_precedence_over_origin(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """When both cause and origin are set, cause should take precedence."""
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

        state.set_hitl_cause(42, "CI failed after 2 fix attempt(s)")
        state.set_hitl_origin(42, "hydra-review")

        hitl_item = HITLItem(issue=42, title="Fix bug", pr=101)
        pr_mgr.list_hitl_items = AsyncMock(return_value=[hitl_item])  # type: ignore[method-assign]

        get_hitl = None
        for route in router.routes:
            if (
                hasattr(route, "path")
                and route.path == "/api/hitl"
                and hasattr(route, "endpoint")
            ):
                get_hitl = route.endpoint  # type: ignore[union-attr]
                break

        assert get_hitl is not None
        response = await get_hitl()
        import json

        items = json.loads(response.body)
        assert len(items) == 1
        assert items[0]["cause"] == "CI failed after 2 fix attempt(s)"


# ---------------------------------------------------------------------------
# /api/metrics endpoint
# ---------------------------------------------------------------------------


class TestMetricsEndpoint:
    """Tests for the GET /api/metrics endpoint."""

    def _make_router(self, config, event_bus, state, tmp_path):
        from dashboard_routes import create_router
        from pr_manager import PRManager

        pr_mgr = PRManager(config, event_bus)
        return create_router(
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

    def _find_endpoint(self, router, path):
        for route in router.routes:
            if (
                hasattr(route, "path")
                and route.path == path
                and hasattr(route, "endpoint")
            ):
                return route.endpoint  # type: ignore[union-attr]
        return None

    @pytest.mark.asyncio
    async def test_metrics_returns_zero_rates_when_no_data(
        self, config, event_bus, tmp_path
    ) -> None:
        import json

        state = make_state(tmp_path)
        router = self._make_router(config, event_bus, state, tmp_path)
        get_metrics = self._find_endpoint(router, "/api/metrics")
        assert get_metrics is not None

        response = await get_metrics()
        data = json.loads(response.body)

        assert data["rates"].get("quality_fix_rate", 0.0) == pytest.approx(0.0)
        assert data["rates"].get("first_pass_approval_rate", 0.0) == pytest.approx(0.0)
        assert data["rates"].get("hitl_escalation_rate", 0.0) == pytest.approx(0.0)
        assert data["lifetime"]["issues_completed"] == 0
        assert data["lifetime"]["prs_merged"] == 0

    @pytest.mark.asyncio
    async def test_metrics_returns_computed_rates(
        self, config, event_bus, tmp_path
    ) -> None:
        import json

        state = make_state(tmp_path)
        # Set up some stats
        for _ in range(10):
            state.record_issue_completed()
        for _ in range(5):
            state.record_pr_merged()
        state.record_quality_fix_rounds(4)
        state.record_review_verdict("approve", fixes_made=False)
        state.record_review_verdict("approve", fixes_made=False)
        state.record_review_verdict("request-changes", fixes_made=True)
        state.record_hitl_escalation()
        state.record_hitl_escalation()
        state.record_implementation_duration(100.0)

        router = self._make_router(config, event_bus, state, tmp_path)
        get_metrics = self._find_endpoint(router, "/api/metrics")
        response = await get_metrics()
        data = json.loads(response.body)

        assert data["rates"]["quality_fix_rate"] == pytest.approx(0.4)  # 4/10
        assert data["rates"]["first_pass_approval_rate"] == pytest.approx(
            2.0 / 3.0
        )  # 2/3
        assert data["rates"]["hitl_escalation_rate"] == pytest.approx(0.2)  # 2/10
        assert data["rates"]["avg_implementation_seconds"] == pytest.approx(
            10.0
        )  # 100/10
        assert data["rates"]["reviewer_fix_rate"] == pytest.approx(1.0 / 3.0)  # 1/3
        assert data["lifetime"]["issues_completed"] == 10
        assert data["lifetime"]["prs_merged"] == 5

    @pytest.mark.asyncio
    async def test_metrics_no_division_by_zero_on_reviews(
        self, config, event_bus, tmp_path
    ) -> None:
        """When no reviews exist, approval rate should be 0 not crash."""
        import json

        state = make_state(tmp_path)
        for _ in range(5):
            state.record_issue_completed()

        router = self._make_router(config, event_bus, state, tmp_path)
        get_metrics = self._find_endpoint(router, "/api/metrics")
        response = await get_metrics()
        data = json.loads(response.body)

        assert data["rates"].get("first_pass_approval_rate", 0.0) == pytest.approx(0.0)
        assert data["rates"].get("reviewer_fix_rate", 0.0) == pytest.approx(0.0)
