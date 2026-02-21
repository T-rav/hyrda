"""Tests for the /api/issues endpoint in dashboard_routes.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from events import EventBus
from models import IssueListItem
from state import StateTracker


def make_state(tmp_path: Path) -> StateTracker:
    return StateTracker(tmp_path / "state.json")


def _create_router(config, event_bus, tmp_path):
    """Helper to create a router with standard test dependencies."""
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
    return router, pr_mgr, state


def _find_endpoint(router, path: str):
    """Find the endpoint function for a given route path."""
    for route in router.routes:
        if hasattr(route, "path") and route.path == path and hasattr(route, "endpoint"):
            return route.endpoint
    return None


class TestIssuesEndpoint:
    """Tests for GET /api/issues."""

    def test_issues_route_is_registered(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        router, _, _ = _create_router(config, event_bus, tmp_path)
        paths = {route.path for route in router.routes if hasattr(route, "path")}
        assert "/api/issues" in paths

    @pytest.mark.asyncio
    async def test_returns_issue_list_items(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """Endpoint returns IssueListItem data as JSON."""
        router, pr_mgr, _ = _create_router(config, event_bus, tmp_path)

        items = [
            IssueListItem(
                issue=42,
                title="Fix bug",
                url="https://github.com/org/repo/issues/42",
                status="implement",
                pr=101,
                prUrl="https://github.com/org/repo/pull/101",
                labels=["hydra-ready"],
            ),
            IssueListItem(
                issue=43,
                title="Add feature",
                url="https://github.com/org/repo/issues/43",
                status="plan",
                labels=["hydra-plan"],
            ),
        ]
        pr_mgr.list_issues_by_labels = AsyncMock(return_value=items)

        endpoint = _find_endpoint(router, "/api/issues")
        assert endpoint is not None

        response = await endpoint()
        data = json.loads(response.body)

        assert len(data) == 2
        assert data[0]["issue"] == 42
        assert data[0]["status"] == "implement"
        assert data[0]["pr"] == 101
        assert data[1]["issue"] == 43
        assert data[1]["status"] == "plan"

    @pytest.mark.asyncio
    async def test_empty_response(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """Endpoint returns empty list when no issues exist."""
        router, pr_mgr, _ = _create_router(config, event_bus, tmp_path)
        pr_mgr.list_issues_by_labels = AsyncMock(return_value=[])

        endpoint = _find_endpoint(router, "/api/issues")
        assert endpoint is not None

        response = await endpoint()
        data = json.loads(response.body)
        assert data == []

    @pytest.mark.asyncio
    async def test_status_overridden_by_processed_issues_success(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """Issues with state.processed_issues 'success' should show status 'merged'."""
        router, pr_mgr, state = _create_router(config, event_bus, tmp_path)

        items = [
            IssueListItem(
                issue=42,
                title="Fix bug",
                status="review",
                labels=["hydra-review"],
            ),
        ]
        pr_mgr.list_issues_by_labels = AsyncMock(return_value=items)

        # Mark issue 42 as successfully processed
        state.mark_issue(42, "success")

        endpoint = _find_endpoint(router, "/api/issues")
        response = await endpoint()
        data = json.loads(response.body)

        assert len(data) == 1
        assert data[0]["status"] == "merged"

    @pytest.mark.asyncio
    async def test_status_overridden_by_processed_issues_failed(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """Issues with state.processed_issues 'failed' should show status 'failed'."""
        router, pr_mgr, state = _create_router(config, event_bus, tmp_path)

        items = [
            IssueListItem(
                issue=42,
                title="Fix bug",
                status="implement",
                labels=["hydra-ready"],
            ),
        ]
        pr_mgr.list_issues_by_labels = AsyncMock(return_value=items)

        state.mark_issue(42, "failed")

        endpoint = _find_endpoint(router, "/api/issues")
        response = await endpoint()
        data = json.loads(response.body)

        assert len(data) == 1
        assert data[0]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_status_not_overridden_when_not_processed(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """Issues without state entries keep their label-derived status."""
        router, pr_mgr, _ = _create_router(config, event_bus, tmp_path)

        items = [
            IssueListItem(
                issue=42,
                title="Fix bug",
                status="review",
                labels=["hydra-review"],
            ),
        ]
        pr_mgr.list_issues_by_labels = AsyncMock(return_value=items)

        endpoint = _find_endpoint(router, "/api/issues")
        response = await endpoint()
        data = json.loads(response.body)

        assert data[0]["status"] == "review"

    @pytest.mark.asyncio
    async def test_labels_and_pr_url_included(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """Returned items include labels and PR URL fields."""
        router, pr_mgr, _ = _create_router(config, event_bus, tmp_path)

        items = [
            IssueListItem(
                issue=42,
                title="Fix bug",
                status="implement",
                pr=101,
                prUrl="https://github.com/org/repo/pull/101",
                labels=["hydra-ready", "bug"],
            ),
        ]
        pr_mgr.list_issues_by_labels = AsyncMock(return_value=items)

        endpoint = _find_endpoint(router, "/api/issues")
        response = await endpoint()
        data = json.loads(response.body)

        assert data[0]["labels"] == ["hydra-ready", "bug"]
        assert data[0]["prUrl"] == "https://github.com/org/repo/pull/101"
