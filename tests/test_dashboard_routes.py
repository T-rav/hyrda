"""Tests for dashboard_routes.py — route factory and handler registration."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from events import EventBus
from state import StateTracker


def make_state(tmp_path: Path) -> StateTracker:
    return StateTracker(tmp_path / "state.json")


def _make_router(config, event_bus, tmp_path, pr_manager=None):
    """Helper to create a router with test defaults."""
    from dashboard_routes import create_router
    from pr_manager import PRManager

    state = make_state(tmp_path)
    pr_mgr = pr_manager or PRManager(config, event_bus)

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


class TestCreateRouter:
    """Tests for create_router factory function."""

    def test_create_router_returns_api_router(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi import APIRouter

        router = _make_router(config, event_bus, tmp_path)
        assert isinstance(router, APIRouter)

    def test_router_registers_expected_routes(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        router = _make_router(config, event_bus, tmp_path)
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
            "/api/intent",
            "/ws",
        }

        assert expected_paths.issubset(paths)


class TestIntentEndpoint:
    """Tests for POST /api/intent endpoint."""

    @pytest.mark.asyncio
    async def test_intent_creates_issue(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        mock_pr_manager = AsyncMock()
        mock_pr_manager.create_issue = AsyncMock(return_value=99)

        router = _make_router(config, event_bus, tmp_path, pr_manager=mock_pr_manager)
        app = FastAPI()
        app.include_router(router)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/intent",
                json={"text": "Add rate limiting to API endpoints"},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["issue_number"] == 99
        assert data["title"] == "Add rate limiting to API endpoints"
        assert "issues/99" in data["url"]

        mock_pr_manager.create_issue.assert_called_once()
        call_kwargs = mock_pr_manager.create_issue.call_args
        assert call_kwargs.kwargs["title"] == "Add rate limiting to API endpoints"
        assert "Submitted via Hydra Dashboard" in call_kwargs.kwargs["body"]

    @pytest.mark.asyncio
    async def test_intent_empty_text_returns_422(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        mock_pr_manager = AsyncMock()
        router = _make_router(config, event_bus, tmp_path, pr_manager=mock_pr_manager)
        app = FastAPI()
        app.include_router(router)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/intent", json={"text": ""})

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_intent_whitespace_only_returns_400(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        mock_pr_manager = AsyncMock()
        router = _make_router(config, event_bus, tmp_path, pr_manager=mock_pr_manager)
        app = FastAPI()
        app.include_router(router)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/intent", json={"text": "   "})

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_intent_truncates_long_title(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        mock_pr_manager = AsyncMock()
        mock_pr_manager.create_issue = AsyncMock(return_value=50)

        router = _make_router(config, event_bus, tmp_path, pr_manager=mock_pr_manager)
        app = FastAPI()
        app.include_router(router)

        long_text = "A" * 200
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/intent", json={"text": long_text})

        assert resp.status_code == 201
        data = resp.json()
        assert len(data["title"]) == 70
        call_kwargs = mock_pr_manager.create_issue.call_args
        assert len(call_kwargs.kwargs["title"]) == 70

    @pytest.mark.asyncio
    async def test_intent_uses_find_label(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        mock_pr_manager = AsyncMock()
        mock_pr_manager.create_issue = AsyncMock(return_value=10)

        router = _make_router(config, event_bus, tmp_path, pr_manager=mock_pr_manager)
        app = FastAPI()
        app.include_router(router)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/intent", json={"text": "test intent"})

        assert resp.status_code == 201
        call_kwargs = mock_pr_manager.create_issue.call_args
        assert "hydra-find" in call_kwargs.kwargs["labels"]

    @pytest.mark.asyncio
    async def test_intent_create_issue_failure_returns_500(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        mock_pr_manager = AsyncMock()
        mock_pr_manager.create_issue = AsyncMock(return_value=0)

        router = _make_router(config, event_bus, tmp_path, pr_manager=mock_pr_manager)
        app = FastAPI()
        app.include_router(router)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/intent", json={"text": "something"})

        assert resp.status_code == 500
        assert "error" in resp.json()
