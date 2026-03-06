"""Tests for service_registry.py — ServiceRegistry and build_services factory."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config import HydraFlowConfig

from unittest.mock import patch

import pytest

from events import EventBus, EventType, HydraFlowEvent
from service_registry import OrchestratorCallbacks, ServiceRegistry, build_services
from state import StateTracker


def _make_callbacks() -> OrchestratorCallbacks:
    """Create a stub OrchestratorCallbacks."""
    return OrchestratorCallbacks(
        sync_active_issue_numbers=lambda: None,
        update_bg_worker_status=lambda *args, **kwargs: None,
        is_bg_worker_enabled=lambda name: True,
        sleep_or_stop=AsyncMock(),
        get_bg_worker_interval=lambda name: 60,
    )


class TestBuildServices:
    """Tests for the build_services factory function."""

    def test_returns_service_registry(self, config: HydraFlowConfig) -> None:
        """build_services should return a ServiceRegistry instance."""
        bus = EventBus()
        state = StateTracker(config.state_file)
        stop_event = asyncio.Event()
        callbacks = _make_callbacks()

        registry = build_services(config, bus, state, stop_event, callbacks)

        assert isinstance(registry, ServiceRegistry)

    def test_all_fields_are_set(self, config: HydraFlowConfig) -> None:
        """All ServiceRegistry fields should be non-None."""
        bus = EventBus()
        state = StateTracker(config.state_file)
        stop_event = asyncio.Event()
        callbacks = _make_callbacks()

        registry = build_services(config, bus, state, stop_event, callbacks)

        for field_name in ServiceRegistry.__dataclass_fields__:
            assert getattr(registry, field_name) is not None, f"{field_name} is None"

    def test_agents_runner_is_shared(self, config: HydraFlowConfig) -> None:
        """Agents, planners, reviewers, and HITL runner should share the subprocess runner."""
        bus = EventBus()
        state = StateTracker(config.state_file)
        stop_event = asyncio.Event()
        callbacks = _make_callbacks()

        registry = build_services(config, bus, state, stop_event, callbacks)

        assert registry.agents._runner is registry.subprocess_runner
        assert registry.planners._runner is registry.subprocess_runner
        assert registry.reviewers._runner is registry.subprocess_runner
        # Verify the runner type matches the expected execution mode
        from docker_runner import get_docker_runner

        runner = get_docker_runner(config)
        assert type(registry.subprocess_runner) is type(runner)

    def test_store_uses_fetcher(self, config: HydraFlowConfig) -> None:
        """IssueStore should be initialized with the fetcher."""
        bus = EventBus()
        state = StateTracker(config.state_file)
        stop_event = asyncio.Event()
        callbacks = _make_callbacks()

        registry = build_services(config, bus, state, stop_event, callbacks)

        from issue_fetcher import GitHubTaskFetcher

        assert isinstance(registry.store._fetcher, GitHubTaskFetcher)
        assert registry.store._fetcher._fetcher is registry.fetcher

    def test_uses_get_docker_runner(self, config: HydraFlowConfig) -> None:
        """build_services should use get_docker_runner to create the subprocess runner."""
        bus = EventBus()
        state = StateTracker(config.state_file)
        stop_event = asyncio.Event()
        callbacks = _make_callbacks()

        with patch("service_registry.get_docker_runner") as mock_factory:
            from execution import get_default_runner

            mock_factory.return_value = get_default_runner()
            build_services(config, bus, state, stop_event, callbacks)

        mock_factory.assert_called_once_with(config)


class TestServiceRegistryWiring:
    """Integration checks for ServiceRegistry wiring and shared dependencies."""

    @staticmethod
    def _build_registry(
        config: HydraFlowConfig,
    ) -> tuple[ServiceRegistry, EventBus, StateTracker, asyncio.Event]:
        bus = EventBus()
        state = StateTracker(config.state_file)
        stop_event = asyncio.Event()
        callbacks = _make_callbacks()
        registry = build_services(config, bus, state, stop_event, callbacks)
        return registry, bus, state, stop_event

    def test_phases_share_event_bus(self, config: HydraFlowConfig) -> None:
        registry, bus, _, _ = self._build_registry(config)

        bus_consumers = [
            registry.triager._bus,
            registry.planner_phase._bus,
            registry.reviewer._bus,
            registry.hitl_phase._bus,
            registry.agents._bus,
            registry.planners._bus,
            registry.reviewers._bus,
            registry.hitl_runner._bus,
            registry.triage._bus,
            registry.prs._bus,
            registry.store._bus,
        ]

        assert all(component is bus for component in bus_consumers)

    def test_phases_share_state_tracker(self, config: HydraFlowConfig) -> None:
        registry, _, state, _ = self._build_registry(config)

        assert registry.triager._state is state
        assert registry.planner_phase._state is state
        assert registry.implementer._state is state
        assert registry.reviewer._state is state
        assert registry.hitl_phase._state is state

    def test_phases_share_stop_event(self, config: HydraFlowConfig) -> None:
        registry, _, _, stop_event = self._build_registry(config)

        assert registry.triager._stop_event is stop_event
        assert registry.planner_phase._stop_event is stop_event
        assert registry.implementer._stop_event is stop_event
        assert registry.reviewer._stop_event is stop_event
        assert registry.hitl_phase._stop_event is stop_event

    @pytest.mark.asyncio
    async def test_event_bus_propagation(self, config: HydraFlowConfig) -> None:
        registry, bus, _, _ = self._build_registry(config)
        queue = bus.subscribe()

        try:
            event = HydraFlowEvent(type=EventType.SYSTEM_ALERT, data={"source": "test"})
            await registry.triager._bus.publish(event)

            received = await asyncio.wait_for(queue.get(), timeout=1)
            assert received is event
        finally:
            bus.unsubscribe(queue)
