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
            "/api/events",
            "/api/prs",
            "/api/hitl",
            "/api/human-input",
            "/api/human-input/{issue_number}",
            "/api/control/start",
            "/api/control/stop",
            "/api/control/status",
            "/api/system/workers",
            "/api/metrics",
            "/ws",
        }

        assert expected_paths.issubset(paths)


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
        # cause should be the default empty string from model_dump, not overwritten
        assert items[0]["cause"] == ""


class TestApproveMemoryEndpoint:
    """Tests for POST /api/hitl/{issue_number}/approve-memory."""

    def test_approve_memory_route_registered(
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

        paths = {route.path for route in router.routes if hasattr(route, "path")}
        assert "/api/hitl/{issue_number}/approve-memory" in paths

    @pytest.mark.asyncio
    async def test_approve_memory_relabels_correctly(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from dashboard_routes import create_router
        from pr_manager import PRManager

        state = make_state(tmp_path)
        pr_mgr = PRManager(config, event_bus)

        mock_orch = AsyncMock()
        mock_orch.skip_hitl_issue = AsyncMock()

        router = create_router(
            config=config,
            event_bus=event_bus,
            state=state,
            pr_manager=pr_mgr,
            get_orchestrator=lambda: mock_orch,
            set_orchestrator=lambda o: None,
            set_run_task=lambda t: None,
            ui_dist_dir=tmp_path / "no-dist",
            template_dir=tmp_path / "no-templates",
        )

        # Mock label operations
        pr_mgr.remove_label = AsyncMock()  # type: ignore[method-assign]
        pr_mgr.add_labels = AsyncMock()  # type: ignore[method-assign]

        # Find and call the approve-memory endpoint
        endpoint = None
        for route in router.routes:
            if (
                hasattr(route, "path")
                and route.path == "/api/hitl/{issue_number}/approve-memory"
                and hasattr(route, "endpoint")
            ):
                endpoint = route.endpoint  # type: ignore[union-attr]
                break

        assert endpoint is not None
        response = await endpoint(42)

        import json

        data = json.loads(response.body)
        assert data["status"] == "ok"
        pr_mgr.add_labels.assert_called_once_with(42, config.memory_label)


class TestControlStatusIncludesMemoryLabel:
    """Tests that GET /api/control/status includes memory_label."""

    @pytest.mark.asyncio
    async def test_get_control_status_includes_memory_label(
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

        # Find and call the get_control_status handler
        endpoint = None
        for route in router.routes:
            if (
                hasattr(route, "path")
                and route.path == "/api/control/status"
                and hasattr(route, "endpoint")
            ):
                endpoint = route.endpoint  # type: ignore[union-attr]
                break

        assert endpoint is not None
        response = await endpoint()

        import json

        data = json.loads(response.body)
        assert "memory_label" in data["config"]
        assert data["config"]["memory_label"] == config.memory_label
