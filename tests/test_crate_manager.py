"""Tests for crate_manager.py — CrateManager active crate lifecycle."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from crate_manager import CrateManager
from events import EventBus, EventType
from models import Crate
from tests.conftest import TaskFactory
from tests.helpers import ConfigFactory


def _make_manager(
    *,
    auto_crate: bool = False,
    active_crate: int | None = None,
) -> tuple[CrateManager, MagicMock, AsyncMock, EventBus]:
    """Create a CrateManager with mocked dependencies."""
    config = ConfigFactory.create()
    config.auto_crate = auto_crate

    state = MagicMock()
    state.get_active_crate_number.return_value = active_crate
    state.set_active_crate_number = MagicMock()

    pr_manager = AsyncMock()
    bus = EventBus()

    cm = CrateManager(config, state, pr_manager, bus)
    return cm, state, pr_manager, bus


class TestIsInActiveCrate:
    """Tests for is_in_active_crate gating logic."""

    def test_returns_true_when_task_matches_active_crate(self) -> None:
        cm, _, _, _ = _make_manager(active_crate=5)
        task = TaskFactory.create(id=10, tags=["hydraflow-plan"])
        task.metadata["milestone_number"] = 5

        assert cm.is_in_active_crate(task) is True

    def test_returns_false_when_task_has_different_milestone(self) -> None:
        cm, _, _, _ = _make_manager(active_crate=5)
        task = TaskFactory.create(id=10, tags=["hydraflow-plan"])
        task.metadata["milestone_number"] = 99

        assert cm.is_in_active_crate(task) is False

    def test_returns_false_when_task_has_no_milestone(self) -> None:
        cm, _, _, _ = _make_manager(active_crate=5)
        task = TaskFactory.create(id=10, tags=["hydraflow-plan"])

        assert cm.is_in_active_crate(task) is False

    def test_returns_false_when_no_active_crate(self) -> None:
        cm, _, _, _ = _make_manager(active_crate=None)
        task = TaskFactory.create(id=10, tags=["hydraflow-plan"])
        task.metadata["milestone_number"] = 5

        assert cm.is_in_active_crate(task) is False


class TestActivateCrate:
    """Tests for activate_crate persistence and event publishing."""

    @pytest.mark.asyncio
    async def test_persists_to_state_and_publishes_event(self) -> None:
        cm, state_mock, _, bus = _make_manager()
        queue = bus.subscribe()

        await cm.activate_crate(7)

        state_mock.set_active_crate_number.assert_called_once_with(7)

        event = queue.get_nowait()
        assert event.type == EventType.CRATE_ACTIVATED
        assert event.data["crate_number"] == 7


class TestCheckAndAdvance:
    """Tests for check_and_advance crate progression."""

    @pytest.mark.asyncio
    async def test_does_nothing_when_no_active_crate(self) -> None:
        cm, state_mock, pr_mock, _ = _make_manager(active_crate=None)

        await cm.check_and_advance()

        pr_mock.list_milestones.assert_not_called()

    @pytest.mark.asyncio
    async def test_stays_when_active_crate_has_open_issues(self) -> None:
        cm, state_mock, pr_mock, _ = _make_manager(active_crate=3)
        pr_mock.list_milestones.return_value = [
            Crate(number=3, title="Sprint 1", open_issues=2, closed_issues=5),
        ]

        await cm.check_and_advance()

        state_mock.set_active_crate_number.assert_not_called()

    @pytest.mark.asyncio
    async def test_advances_to_next_when_done(self) -> None:
        cm, state_mock, pr_mock, bus = _make_manager(active_crate=3)
        pr_mock.list_milestones.return_value = [
            Crate(number=3, title="Sprint 1", open_issues=0, closed_issues=5),
            Crate(number=7, title="Sprint 2", open_issues=3, closed_issues=0),
        ]
        queue = bus.subscribe()

        await cm.check_and_advance()

        # Should publish CRATE_COMPLETED for 3, then CRATE_ACTIVATED for 7
        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        types = [e.type for e in events]
        assert EventType.CRATE_COMPLETED in types
        assert EventType.CRATE_ACTIVATED in types

        # Should have activated crate 7
        state_mock.set_active_crate_number.assert_any_call(7)

    @pytest.mark.asyncio
    async def test_clears_active_when_no_next_crate(self) -> None:
        cm, state_mock, pr_mock, bus = _make_manager(active_crate=3)
        pr_mock.list_milestones.return_value = [
            Crate(number=3, title="Sprint 1", open_issues=0, closed_issues=5),
        ]

        await cm.check_and_advance()

        state_mock.set_active_crate_number.assert_any_call(None)


class TestAutoPackageIfNeeded:
    """Tests for auto_package_if_needed milestone creation."""

    @pytest.mark.asyncio
    async def test_does_nothing_when_auto_crate_disabled(self) -> None:
        cm, _, pr_mock, _ = _make_manager(auto_crate=False)
        task = TaskFactory.create(id=1, tags=["hydraflow-plan"])

        await cm.auto_package_if_needed([task])

        pr_mock.create_milestone.assert_not_called()

    @pytest.mark.asyncio
    async def test_does_nothing_when_active_crate_exists(self) -> None:
        cm, _, pr_mock, _ = _make_manager(auto_crate=True, active_crate=5)
        task = TaskFactory.create(id=1, tags=["hydraflow-plan"])

        await cm.auto_package_if_needed([task])

        pr_mock.create_milestone.assert_not_called()

    @pytest.mark.asyncio
    async def test_does_nothing_when_no_uncrated_issues(self) -> None:
        cm, _, pr_mock, _ = _make_manager(auto_crate=True, active_crate=None)

        await cm.auto_package_if_needed([])

        pr_mock.create_milestone.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_milestone_assigns_and_activates(self) -> None:
        cm, state_mock, pr_mock, bus = _make_manager(auto_crate=True, active_crate=None)
        pr_mock.create_milestone.return_value = Crate(
            number=10, title="Delivery 2026-03-01"
        )
        task1 = TaskFactory.create(id=1, tags=["hydraflow-plan"])
        task2 = TaskFactory.create(id=2, tags=["hydraflow-plan"])

        await cm.auto_package_if_needed([task1, task2])

        pr_mock.create_milestone.assert_called_once()
        assert pr_mock.set_issue_milestone.call_count == 2
        pr_mock.set_issue_milestone.assert_any_call(1, 10)
        pr_mock.set_issue_milestone.assert_any_call(2, 10)
        state_mock.set_active_crate_number.assert_called_with(10)
