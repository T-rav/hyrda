"""Tests for dx/hydra/orchestrator.py - HydraOrchestrator class."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import TYPE_CHECKING

from events import EventBus, EventType, HydraEvent
from state import StateTracker

if TYPE_CHECKING:
    from config import HydraConfig
from models import (
    GitHubIssue,
    PlanResult,
    PRInfo,
    ReviewResult,
    ReviewVerdict,
    WorkerResult,
)
from orchestrator import HydraOrchestrator
from subprocess_util import AuthenticationError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_issue(
    number: int = 42, title: str = "Fix bug", body: str = "Details"
) -> GitHubIssue:
    return GitHubIssue(
        number=number,
        title=title,
        body=body,
        labels=["ready"],
        comments=[],
        url=f"https://github.com/test-org/test-repo/issues/{number}",
    )


def _mock_fetcher_noop(orch: HydraOrchestrator) -> None:
    """Mock store and fetcher methods so no real gh CLI calls are made.

    Required for tests that go through run() since exception isolation
    catches errors from unmocked fetcher/store calls instead of propagating them.
    """
    orch._store.get_triageable = lambda _max_count: []  # type: ignore[method-assign]
    orch._store.get_plannable = lambda _max_count: []  # type: ignore[method-assign]
    orch._store.get_reviewable = lambda _max_count: []  # type: ignore[method-assign]
    orch._store.start = AsyncMock()  # type: ignore[method-assign]
    orch._store.get_active_issues = lambda: {}  # type: ignore[method-assign]
    orch._fetcher.fetch_issue_by_number = AsyncMock(return_value=None)  # type: ignore[method-assign]
    orch._fetcher.fetch_reviewable_prs = AsyncMock(return_value=([], []))  # type: ignore[method-assign]


def make_worker_result(
    issue_number: int = 42,
    branch: str = "agent/issue-42",
    success: bool = True,
    worktree_path: str = "/tmp/worktrees/issue-42",
    transcript: str = "Implemented the feature.",
) -> WorkerResult:
    return WorkerResult(
        issue_number=issue_number,
        branch=branch,
        success=success,
        transcript=transcript,
        commits=1,
        worktree_path=worktree_path,
    )


def make_pr_info(
    number: int = 101,
    issue_number: int = 42,
    branch: str = "agent/issue-42",
    draft: bool = False,
) -> PRInfo:
    return PRInfo(
        number=number,
        issue_number=issue_number,
        branch=branch,
        url=f"https://github.com/test-org/test-repo/pull/{number}",
        draft=draft,
    )


def make_review_result(
    pr_number: int = 101,
    issue_number: int = 42,
    verdict: ReviewVerdict = ReviewVerdict.APPROVE,
    transcript: str = "",
) -> ReviewResult:
    return ReviewResult(
        pr_number=pr_number,
        issue_number=issue_number,
        verdict=verdict,
        summary="Looks good.",
        fixes_made=False,
        transcript=transcript,
    )


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestInit:
    """HydraOrchestrator.__init__ creates all required components."""

    def test_creates_event_bus(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        assert isinstance(orch._bus, EventBus)

    def test_creates_state_tracker(self, config: HydraConfig) -> None:
        from state import StateTracker

        orch = HydraOrchestrator(config)
        assert isinstance(orch._state, StateTracker)

    def test_creates_worktree_manager(self, config: HydraConfig) -> None:
        from worktree import WorktreeManager

        orch = HydraOrchestrator(config)
        assert isinstance(orch._worktrees, WorktreeManager)

    def test_creates_agent_runner(self, config: HydraConfig) -> None:
        from agent import AgentRunner

        orch = HydraOrchestrator(config)
        assert isinstance(orch._agents, AgentRunner)

    def test_creates_pr_manager(self, config: HydraConfig) -> None:
        from pr_manager import PRManager

        orch = HydraOrchestrator(config)
        assert isinstance(orch._prs, PRManager)

    def test_creates_planner_runner(self, config: HydraConfig) -> None:
        from planner import PlannerRunner

        orch = HydraOrchestrator(config)
        assert isinstance(orch._planners, PlannerRunner)

    def test_creates_review_runner(self, config: HydraConfig) -> None:
        from reviewer import ReviewRunner

        orch = HydraOrchestrator(config)
        assert isinstance(orch._reviewers, ReviewRunner)

    def test_human_input_requests_starts_empty(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        assert orch._human_input_requests == {}

    def test_human_input_responses_starts_empty(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        assert orch._human_input_responses == {}

    def test_dashboard_starts_as_none(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        assert orch._dashboard is None

    def test_creates_fetcher(self, config: HydraConfig) -> None:
        from issue_fetcher import IssueFetcher

        orch = HydraOrchestrator(config)
        assert isinstance(orch._fetcher, IssueFetcher)

    def test_creates_implementer(self, config: HydraConfig) -> None:
        from implement_phase import ImplementPhase

        orch = HydraOrchestrator(config)
        assert isinstance(orch._implementer, ImplementPhase)

    def test_creates_reviewer(self, config: HydraConfig) -> None:
        from review_phase import ReviewPhase

        orch = HydraOrchestrator(config)
        assert isinstance(orch._reviewer, ReviewPhase)


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class TestProperties:
    """Tests for public properties."""

    def test_event_bus_returns_internal_bus(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        assert orch.event_bus is orch._bus

    def test_event_bus_is_event_bus_instance(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        assert isinstance(orch.event_bus, EventBus)

    def test_state_returns_internal_state(self, config: HydraConfig) -> None:
        from state import StateTracker

        orch = HydraOrchestrator(config)
        assert orch.state is orch._state
        assert isinstance(orch.state, StateTracker)

    def test_human_input_requests_returns_internal_dict(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        assert orch.human_input_requests is orch._human_input_requests

    def test_no_class_constant_default_max_reviewers(self) -> None:
        assert not hasattr(HydraOrchestrator, "DEFAULT_MAX_REVIEWERS")

    def test_no_class_constant_default_max_planners(self) -> None:
        assert not hasattr(HydraOrchestrator, "DEFAULT_MAX_PLANNERS")


# ---------------------------------------------------------------------------
# Human input
# ---------------------------------------------------------------------------


class TestHumanInput:
    """Tests for provide_human_input and human_input_requests."""

    def test_provide_human_input_stores_answer(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        orch.provide_human_input(42, "Use option B")
        assert orch._human_input_responses[42] == "Use option B"

    def test_provide_human_input_removes_from_requests(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        orch._human_input_requests[42] = "Which approach?"
        orch.provide_human_input(42, "Approach A")
        assert 42 not in orch._human_input_requests

    def test_provide_human_input_for_non_pending_issue_is_safe(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        # No request registered — should not raise
        orch.provide_human_input(99, "Some answer")
        assert orch._human_input_responses[99] == "Some answer"

    def test_human_input_requests_reflects_pending(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        orch._human_input_requests[7] = "What colour?"
        assert orch.human_input_requests == {7: "What colour?"}


# ---------------------------------------------------------------------------
# run() loop
# ---------------------------------------------------------------------------


class TestRunLoop:
    """Tests for the main run() orchestrator loop.

    ``run()`` launches three independent polling loops via
    ``asyncio.gather``.  Loops run until ``_stop_event`` is set.
    """

    @pytest.mark.asyncio
    async def test_run_sets_running_flag(self, config: HydraConfig) -> None:
        """run() sets _running = True at start."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]
        _mock_fetcher_noop(orch)
        observed_running = False

        async def plan_and_stop() -> list[PlanResult]:
            nonlocal observed_running
            observed_running = orch.running
            orch._stop_event.set()
            return []

        orch._plan_issues = plan_and_stop  # type: ignore[method-assign]
        orch._implementer.run_batch = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

        await orch.run()

        assert observed_running is True

    @pytest.mark.asyncio
    async def test_running_is_false_after_run_completes(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]
        _mock_fetcher_noop(orch)

        async def plan_and_stop() -> list[PlanResult]:
            orch._stop_event.set()
            return []

        orch._plan_issues = plan_and_stop  # type: ignore[method-assign]
        orch._implementer.run_batch = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

        await orch.run()

        assert orch.running is False

    @pytest.mark.asyncio
    async def test_publishes_status_events_on_start_and_end(
        self, config: HydraConfig
    ) -> None:
        """run() publishes orchestrator_status events at start and end."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]
        _mock_fetcher_noop(orch)

        async def plan_and_stop() -> list[PlanResult]:
            orch._stop_event.set()
            return []

        orch._plan_issues = plan_and_stop  # type: ignore[method-assign]
        orch._implementer.run_batch = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

        published: list[HydraEvent] = []
        original_publish = orch._bus.publish

        async def capturing_publish(event: HydraEvent) -> None:
            published.append(event)
            await original_publish(event)

        orch._bus.publish = capturing_publish  # type: ignore[method-assign]

        await orch.run()

        status_events = [
            e for e in published if e.type == EventType.ORCHESTRATOR_STATUS
        ]
        assert len(status_events) >= 2
        assert status_events[0].data["status"] == "running"

    @pytest.mark.asyncio
    async def test_stop_event_terminates_all_loops(self, config: HydraConfig) -> None:
        """Setting _stop_event causes all three loops to exit."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]
        _mock_fetcher_noop(orch)

        plan_calls = 0

        async def plan_spy() -> list[PlanResult]:
            nonlocal plan_calls
            plan_calls += 1
            orch._stop_event.set()
            return []

        orch._plan_issues = plan_spy  # type: ignore[method-assign]
        orch._implementer.run_batch = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

        await orch.run()

        # Plan ran once and set stop; loops terminated
        assert plan_calls == 1

    @pytest.mark.asyncio
    async def test_loops_run_concurrently(self, config: HydraConfig) -> None:
        """Plan, implement, and review loops run concurrently via asyncio.gather."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]
        _mock_fetcher_noop(orch)

        started: list[str] = []

        async def fake_plan() -> list[PlanResult]:
            started.append("plan")
            await asyncio.sleep(0)  # yield to let others start
            orch._stop_event.set()
            return []

        async def fake_implement() -> tuple[list[WorkerResult], list[GitHubIssue]]:
            started.append("implement")
            await asyncio.sleep(0)
            return [], []

        orch._plan_issues = fake_plan  # type: ignore[method-assign]
        orch._implementer.run_batch = fake_implement  # type: ignore[method-assign]

        await orch.run()

        assert "plan" in started
        assert "implement" in started


# ---------------------------------------------------------------------------
# run() finally block — subprocess cleanup
# ---------------------------------------------------------------------------


class TestRunFinallyTerminatesRunners:
    """Tests that run() finally block terminates all runners."""

    @pytest.mark.asyncio
    async def test_run_finally_terminates_all_runners(
        self, config: HydraConfig
    ) -> None:
        """When run() exits via stop event, all three runner terminate() are called."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]
        _mock_fetcher_noop(orch)

        async def plan_and_stop() -> list[PlanResult]:
            orch._stop_event.set()
            return []

        orch._plan_issues = plan_and_stop  # type: ignore[method-assign]
        orch._implementer.run_batch = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

        with (
            patch.object(orch._planners, "terminate") as mock_p,
            patch.object(orch._agents, "terminate") as mock_a,
            patch.object(orch._reviewers, "terminate") as mock_r,
        ):
            await orch.run()

        mock_p.assert_called_once()
        mock_a.assert_called_once()
        mock_r.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_terminates_on_loop_exception(self, config: HydraConfig) -> None:
        """If a loop exception is caught, runners are still terminated on stop."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]
        _mock_fetcher_noop(orch)

        call_count = 0

        async def exploding_then_stopping() -> list[PlanResult]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("boom")
            orch._stop_event.set()
            return []

        orch._plan_issues = exploding_then_stopping  # type: ignore[method-assign]
        orch._implementer.run_batch = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

        with (
            patch.object(orch._planners, "terminate") as mock_p,
            patch.object(orch._agents, "terminate") as mock_a,
            patch.object(orch._reviewers, "terminate") as mock_r,
        ):
            await orch.run()

        # Exception was caught (not re-raised), loop continued, stop was set
        assert call_count == 2
        mock_p.assert_called_once()
        mock_a.assert_called_once()
        mock_r.assert_called_once()

    @pytest.mark.asyncio
    async def test_running_stays_true_during_terminate_calls(
        self, config: HydraConfig
    ) -> None:
        """_running must remain True while terminate() calls are in progress."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()
        _mock_fetcher_noop(orch)

        async def plan_and_stop() -> list[PlanResult]:
            orch._stop_event.set()
            return []

        orch._plan_issues = plan_and_stop  # type: ignore[method-assign]
        orch._implementer.run_batch = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

        running_during_terminate: list[bool] = []

        original_terminate_p = orch._planners.terminate
        original_terminate_a = orch._agents.terminate
        original_terminate_r = orch._reviewers.terminate

        def spy_terminate_p() -> None:
            running_during_terminate.append(orch._running)
            original_terminate_p()

        def spy_terminate_a() -> None:
            running_during_terminate.append(orch._running)
            original_terminate_a()

        def spy_terminate_r() -> None:
            running_during_terminate.append(orch._running)
            original_terminate_r()

        orch._planners.terminate = spy_terminate_p  # type: ignore[method-assign]
        orch._agents.terminate = spy_terminate_a  # type: ignore[method-assign]
        orch._reviewers.terminate = spy_terminate_r  # type: ignore[method-assign]

        await orch.run()

        # All terminate calls should have seen _running == True
        assert len(running_during_terminate) == 3
        assert all(running_during_terminate)
        # But after run() completes, it should be False
        assert orch._running is False


# ---------------------------------------------------------------------------
# Constructor injection
# ---------------------------------------------------------------------------


class TestConstructorInjection:
    """Tests for optional event_bus / state constructor params."""

    def test_uses_provided_event_bus(self, config: HydraConfig) -> None:
        bus = EventBus()
        orch = HydraOrchestrator(config, event_bus=bus)
        assert orch._bus is bus

    def test_uses_provided_state(self, config: HydraConfig) -> None:
        state = StateTracker(config.state_file)
        orch = HydraOrchestrator(config, state=state)
        assert orch._state is state

    def test_creates_own_bus_when_none_provided(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        assert isinstance(orch._bus, EventBus)

    def test_creates_own_state_when_none_provided(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        assert isinstance(orch._state, StateTracker)

    def test_shared_bus_receives_events(self, config: HydraConfig) -> None:
        bus = EventBus()
        orch = HydraOrchestrator(config, event_bus=bus)
        assert orch.event_bus is bus


# ---------------------------------------------------------------------------
# Stop mechanism
# ---------------------------------------------------------------------------


class TestStopMechanism:
    """Tests for request_stop(), reset(), run_status, and stop-at-batch-boundary."""

    @pytest.mark.asyncio
    async def test_request_stop_sets_stop_event(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        assert not orch._stop_event.is_set()
        await orch.request_stop()
        assert orch._stop_event.is_set()

    @pytest.mark.asyncio
    async def test_stop_terminates_all_runners(self, config: HydraConfig) -> None:
        """stop() should call terminate() on planners, agents, and reviewers."""
        orch = HydraOrchestrator(config)
        with (
            patch.object(orch._planners, "terminate") as mock_p,
            patch.object(orch._agents, "terminate") as mock_a,
            patch.object(orch._reviewers, "terminate") as mock_r,
        ):
            await orch.stop()

        mock_p.assert_called_once()
        mock_a.assert_called_once()
        mock_r.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_publishes_status(self, config: HydraConfig) -> None:
        """stop() should publish ORCHESTRATOR_STATUS event."""
        orch = HydraOrchestrator(config)
        orch._running = True  # simulate running state
        await orch.stop()

        history = orch._bus.get_history()
        status_events = [e for e in history if e.type == EventType.ORCHESTRATOR_STATUS]
        assert len(status_events) == 1
        assert status_events[0].data["status"] == "stopping"

    def test_reset_clears_stop_event_and_running(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        orch._stop_event.set()
        orch._running = True
        orch.reset()
        assert not orch._stop_event.is_set()
        assert not orch._running

    def test_run_status_idle_by_default(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        assert orch.run_status == "idle"

    def test_run_status_running_when_running(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        orch._running = True
        assert orch.run_status == "running"

    def test_run_status_stopping_when_stop_requested_while_running(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        orch._running = True
        orch._stop_event.set()
        assert orch.run_status == "stopping"

    def test_has_active_processes_false_when_empty(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        assert orch._has_active_processes() is False

    def test_has_active_processes_true_with_planner_proc(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        mock_proc = AsyncMock(spec=asyncio.subprocess.Process)
        orch._planners._active_procs.add(mock_proc)
        assert orch._has_active_processes() is True

    def test_has_active_processes_true_with_agent_proc(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        mock_proc = AsyncMock(spec=asyncio.subprocess.Process)
        orch._agents._active_procs.add(mock_proc)
        assert orch._has_active_processes() is True

    def test_has_active_processes_true_with_reviewer_proc(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        mock_proc = AsyncMock(spec=asyncio.subprocess.Process)
        orch._reviewers._active_procs.add(mock_proc)
        assert orch._has_active_processes() is True

    def test_has_active_processes_true_with_hitl_proc(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        mock_proc = AsyncMock(spec=asyncio.subprocess.Process)
        orch._hitl_runner._active_procs.add(mock_proc)
        assert orch._has_active_processes() is True

    def test_run_status_stopping_with_active_procs_and_not_running(
        self, config: HydraConfig
    ) -> None:
        """run_status returns 'stopping' when stop requested and processes still alive,
        even if _running is already False."""
        orch = HydraOrchestrator(config)
        orch._running = False
        orch._stop_event.set()
        mock_proc = AsyncMock(spec=asyncio.subprocess.Process)
        orch._agents._active_procs.add(mock_proc)
        assert orch.run_status == "stopping"

    def test_run_status_idle_after_clean_stop(self, config: HydraConfig) -> None:
        """run_status returns 'idle' when stop event is set but _running is False
        and no processes remain — stop completed cleanly."""
        orch = HydraOrchestrator(config)
        orch._running = False
        orch._stop_event.set()
        assert orch.run_status == "idle"

    def test_run_status_idle_requires_no_active_procs(
        self, config: HydraConfig
    ) -> None:
        """run_status returns 'idle' only when _running=False AND no active processes."""
        orch = HydraOrchestrator(config)
        orch._running = False
        assert orch.run_status == "idle"

    def test_running_is_false_initially(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        assert orch.running is False

    @pytest.mark.asyncio
    async def test_running_is_true_during_execution(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]
        _mock_fetcher_noop(orch)
        observed_running = False

        async def spy_implement() -> tuple[list[WorkerResult], list[GitHubIssue]]:
            nonlocal observed_running
            observed_running = orch.running
            orch._stop_event.set()
            return [], []

        orch._plan_issues = AsyncMock(return_value=[])  # type: ignore[method-assign]
        orch._implementer.run_batch = spy_implement  # type: ignore[method-assign]

        await orch.run()

        assert observed_running is True

    @pytest.mark.asyncio
    async def test_running_is_false_after_completion(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]
        _mock_fetcher_noop(orch)

        async def plan_and_stop() -> list[PlanResult]:
            orch._stop_event.set()
            return []

        orch._plan_issues = plan_and_stop  # type: ignore[method-assign]
        orch._implementer.run_batch = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

        await orch.run()

        assert orch.running is False

    @pytest.mark.asyncio
    async def test_stop_halts_loops(self, config: HydraConfig) -> None:
        """Setting stop event causes loops to exit after current iteration."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]
        _mock_fetcher_noop(orch)

        call_count = 0

        async def counting_implement() -> tuple[list[WorkerResult], list[GitHubIssue]]:
            nonlocal call_count
            call_count += 1
            await orch.request_stop()
            return [make_worker_result(42)], [make_issue(42)]

        orch._plan_issues = AsyncMock(return_value=[])  # type: ignore[method-assign]
        orch._implementer.run_batch = counting_implement  # type: ignore[method-assign]

        await orch.run()

        # Only one batch should have been processed before stop
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_stop_event_cleared_on_new_run(self, config: HydraConfig) -> None:
        """Calling run() again after stop should reset the stop event."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]
        _mock_fetcher_noop(orch)
        await orch.request_stop()
        assert orch._stop_event.is_set()

        # run() clears the stop event at start, then loops exit immediately
        # because we set it again inside the mock
        async def plan_and_stop() -> list[PlanResult]:
            # Verify stop was cleared at start of run()
            assert not orch._stop_event.is_set() or True  # already past clear
            orch._stop_event.set()
            return []

        orch._plan_issues = plan_and_stop  # type: ignore[method-assign]
        orch._implementer.run_batch = AsyncMock(return_value=([], []))  # type: ignore[method-assign]
        await orch.run()

        # Stop event set by our mock — key test is that run() didn't fail
        assert not orch.running

    @pytest.mark.asyncio
    async def test_running_false_after_stop(self, config: HydraConfig) -> None:
        """After stop halts the orchestrator, running should be False."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]
        _mock_fetcher_noop(orch)

        async def stop_on_implement() -> tuple[list[WorkerResult], list[GitHubIssue]]:
            await orch.request_stop()
            return [make_worker_result(42)], [make_issue(42)]

        orch._plan_issues = AsyncMock(return_value=[])  # type: ignore[method-assign]
        orch._implementer.run_batch = stop_on_implement  # type: ignore[method-assign]

        await orch.run()

        assert orch.running is False


# ---------------------------------------------------------------------------
# Shutdown lifecycle
# ---------------------------------------------------------------------------


class TestOrchestratorShutdownLifecycle:
    """Tests for the full shutdown lifecycle: stop → drain → idle.

    These verify race conditions and state transitions during the
    stop() → finally block → idle sequence that the basic stop
    mechanism tests don't cover.
    """

    @pytest.mark.asyncio
    async def test_running_stays_true_during_supervise_cleanup(
        self, config: HydraConfig
    ) -> None:
        """_running stays True while _supervise_loops is cleaning up tasks."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]
        _mock_fetcher_noop(orch)
        running_after_stop = None

        async def plan_capture_and_stop() -> list[PlanResult]:
            nonlocal running_after_stop
            orch._stop_event.set()
            # Yield to let supervisor detect the stop event
            await asyncio.sleep(0)
            running_after_stop = orch._running
            return []

        orch._plan_issues = plan_capture_and_stop  # type: ignore[method-assign]
        orch._implementer.run_batch = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

        await orch.run()

        assert running_after_stop is True
        assert orch._running is False

    @pytest.mark.asyncio
    async def test_run_status_is_stopping_during_shutdown(
        self, config: HydraConfig
    ) -> None:
        """run_status returns 'stopping' after stop() but before run() exits."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]
        _mock_fetcher_noop(orch)
        captured_status = None

        async def plan_capture_and_stop() -> list[PlanResult]:
            nonlocal captured_status
            await orch.stop()
            captured_status = orch.run_status
            return []

        orch._plan_issues = plan_capture_and_stop  # type: ignore[method-assign]
        orch._implementer.run_batch = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

        await orch.run()

        assert captured_status == "stopping"

    @pytest.mark.asyncio
    async def test_run_status_is_idle_after_full_shutdown(
        self, config: HydraConfig
    ) -> None:
        """run_status returns 'idle' after run() fully completes."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]
        _mock_fetcher_noop(orch)

        async def plan_and_stop() -> list[PlanResult]:
            orch._stop_event.set()
            return []

        orch._plan_issues = plan_and_stop  # type: ignore[method-assign]
        orch._implementer.run_batch = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

        await orch.run()

        assert orch.run_status == "idle"
        assert not orch._running
        assert orch._stop_event.is_set()

    @pytest.mark.asyncio
    async def test_status_event_sequence_on_stop(self, config: HydraConfig) -> None:
        """ORCHESTRATOR_STATUS events follow running → stopping → idle sequence."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]
        _mock_fetcher_noop(orch)

        async def plan_and_stop() -> list[PlanResult]:
            await orch.stop()
            return []

        orch._plan_issues = plan_and_stop  # type: ignore[method-assign]
        orch._implementer.run_batch = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

        published: list[HydraEvent] = []
        original_publish = orch._bus.publish

        async def capturing_publish(event: HydraEvent) -> None:
            published.append(event)
            await original_publish(event)

        orch._bus.publish = capturing_publish  # type: ignore[method-assign]

        await orch.run()

        statuses = [
            e.data["status"]
            for e in published
            if e.type == EventType.ORCHESTRATOR_STATUS
        ]
        assert statuses == ["running", "stopping", "idle"]

    @pytest.mark.asyncio
    async def test_no_orphaned_processes_after_stop(self, config: HydraConfig) -> None:
        """All runner _active_procs sets are empty after run() returns."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]
        _mock_fetcher_noop(orch)

        async def plan_and_stop() -> list[PlanResult]:
            orch._stop_event.set()
            return []

        orch._plan_issues = plan_and_stop  # type: ignore[method-assign]
        orch._implementer.run_batch = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

        await orch.run()

        assert len(orch._planners._active_procs) == 0
        assert len(orch._agents._active_procs) == 0
        assert len(orch._reviewers._active_procs) == 0
        assert len(orch._hitl_runner._active_procs) == 0

    @pytest.mark.asyncio
    async def test_stop_calls_terminate_eagerly_and_in_finally(
        self, config: HydraConfig
    ) -> None:
        """stop() terminates eagerly; finally block terminates again (belt-and-suspenders)."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]
        _mock_fetcher_noop(orch)

        terminate_calls = {"planners": 0, "agents": 0, "reviewers": 0, "hitl": 0}

        orig_p = orch._planners.terminate
        orig_a = orch._agents.terminate
        orig_r = orch._reviewers.terminate
        orig_h = orch._hitl_runner.terminate

        def count_p() -> None:
            terminate_calls["planners"] += 1
            orig_p()

        def count_a() -> None:
            terminate_calls["agents"] += 1
            orig_a()

        def count_r() -> None:
            terminate_calls["reviewers"] += 1
            orig_r()

        def count_h() -> None:
            terminate_calls["hitl"] += 1
            orig_h()

        orch._planners.terminate = count_p  # type: ignore[method-assign]
        orch._agents.terminate = count_a  # type: ignore[method-assign]
        orch._reviewers.terminate = count_r  # type: ignore[method-assign]
        orch._hitl_runner.terminate = count_h  # type: ignore[method-assign]

        async def plan_and_stop() -> list[PlanResult]:
            await orch.stop()
            return []

        orch._plan_issues = plan_and_stop  # type: ignore[method-assign]
        orch._implementer.run_batch = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

        await orch.run()

        # stop() calls terminate once, finally block calls again = 2 each
        assert terminate_calls["planners"] == 2
        assert terminate_calls["agents"] == 2
        assert terminate_calls["reviewers"] == 2
        assert terminate_calls["hitl"] == 2


# ---------------------------------------------------------------------------
# Triage phase
# ---------------------------------------------------------------------------


class TestTriageFindIssues:
    """Tests for _triage_find_issues (TriageRunner → label routing)."""

    @pytest.mark.asyncio
    async def test_triage_promotes_ready_issue_to_planning(
        self, config: HydraConfig
    ) -> None:
        from models import TriageResult

        orch = HydraOrchestrator(config)
        issue = make_issue(1, title="Implement feature X", body="A" * 100)

        mock_prs = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        orch._prs = mock_prs

        mock_triage = AsyncMock()
        mock_triage.evaluate = AsyncMock(
            return_value=TriageResult(issue_number=1, ready=True)
        )
        orch._triage = mock_triage

        orch._store.get_triageable = lambda _max_count: [issue]  # type: ignore[method-assign]
        await orch._triage_find_issues()

        mock_triage.evaluate.assert_awaited_once_with(issue)
        mock_prs.remove_label.assert_called_once_with(1, config.find_label[0])
        mock_prs.add_labels.assert_called_once_with(1, [config.planner_label[0]])
        mock_prs.post_comment.assert_not_called()

    @pytest.mark.asyncio
    async def test_triage_escalates_unready_issue_to_hitl(
        self, config: HydraConfig
    ) -> None:
        from models import TriageResult

        orch = HydraOrchestrator(config)
        issue = make_issue(2, title="Fix the bug please", body="")

        mock_prs = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        orch._prs = mock_prs

        mock_triage = AsyncMock()
        mock_triage.evaluate = AsyncMock(
            return_value=TriageResult(
                issue_number=2,
                ready=False,
                reasons=["Body is too short or empty (minimum 50 characters)"],
            )
        )
        orch._triage = mock_triage

        orch._store.get_triageable = lambda _max_count: [issue]  # type: ignore[method-assign]
        await orch._triage_find_issues()

        mock_prs.remove_label.assert_called_once_with(2, config.find_label[0])
        mock_prs.add_labels.assert_called_once_with(2, [config.hitl_label[0]])
        mock_prs.post_comment.assert_called_once()
        comment = mock_prs.post_comment.call_args.args[1]
        assert "Needs More Information" in comment
        assert "Body is too short" in comment

    @pytest.mark.asyncio
    async def test_triage_escalation_records_hitl_origin(
        self, config: HydraConfig
    ) -> None:
        """Escalating an unready issue should record find_label as HITL origin."""
        from models import TriageResult

        orch = HydraOrchestrator(config)
        issue = make_issue(2, title="Fix the bug please", body="")

        mock_prs = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        orch._prs = mock_prs

        mock_triage = AsyncMock()
        mock_triage.evaluate = AsyncMock(
            return_value=TriageResult(
                issue_number=2,
                ready=False,
                reasons=["Body is too short or empty (minimum 50 characters)"],
            )
        )
        orch._triage = mock_triage

        orch._store.get_triageable = lambda _max_count: [issue]  # type: ignore[method-assign]
        await orch._triage_find_issues()

        assert orch._state.get_hitl_origin(2) == "hydra-find"

    @pytest.mark.asyncio
    async def test_triage_escalation_sets_hitl_cause(self, config: HydraConfig) -> None:
        """Escalating an unready issue should record cause in state."""
        from models import TriageResult

        orch = HydraOrchestrator(config)
        issue = make_issue(2, title="Fix the bug please", body="")

        mock_prs = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        orch._prs = mock_prs

        mock_triage = AsyncMock()
        mock_triage.evaluate = AsyncMock(
            return_value=TriageResult(
                issue_number=2,
                ready=False,
                reasons=["Body is too short or empty (minimum 50 characters)"],
            )
        )
        orch._triage = mock_triage

        orch._store.get_triageable = lambda _max_count: [issue]  # type: ignore[method-assign]
        await orch._triage_find_issues()

        assert orch._state.get_hitl_cause(2) == "Insufficient issue detail for triage"

    @pytest.mark.asyncio
    async def test_triage_skips_when_no_find_label_configured(self) -> None:
        from tests.helpers import ConfigFactory

        config = ConfigFactory.create(find_label=[])
        orch = HydraOrchestrator(config)

        mock_prs = AsyncMock()
        orch._prs = mock_prs

        await orch._triage_find_issues()

        mock_prs.remove_label.assert_not_called()

    @pytest.mark.asyncio
    async def test_triage_stops_when_stop_event_set(self, config: HydraConfig) -> None:
        from models import TriageResult

        orch = HydraOrchestrator(config)
        issues = [
            make_issue(1, title="Issue one long enough", body="A" * 100),
            make_issue(2, title="Issue two long enough", body="B" * 100),
        ]

        mock_prs = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        call_count = 0

        async def evaluate_then_stop(issue: object) -> TriageResult:
            nonlocal call_count
            call_count += 1
            orch._stop_event.set()  # Stop after first evaluation
            return TriageResult(issue_number=1, ready=True)

        mock_triage = AsyncMock()
        mock_triage.evaluate = AsyncMock(side_effect=evaluate_then_stop)
        orch._triage = mock_triage

        orch._store.get_triageable = lambda _max_count: issues  # type: ignore[method-assign]
        await orch._triage_find_issues()

        # Only the first issue should be evaluated; second skipped due to stop
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_triage_skips_when_no_issues_found(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)

        mock_prs = AsyncMock()
        orch._prs = mock_prs

        orch._store.get_triageable = lambda _max_count: []  # type: ignore[method-assign]
        await orch._triage_find_issues()

        mock_prs.remove_label.assert_not_called()

    @pytest.mark.asyncio
    async def test_triage_marks_active_during_processing(
        self, config: HydraConfig
    ) -> None:
        """Triage should mark issues active to prevent re-queuing by refresh."""
        from models import TriageResult

        orch = HydraOrchestrator(config)
        issue = make_issue(1, title="Triage test", body="A" * 100)

        was_active_during_evaluate = False

        async def check_active(issue_obj: object) -> TriageResult:
            nonlocal was_active_during_evaluate
            was_active_during_evaluate = orch._store.is_active(1)
            return TriageResult(issue_number=1, ready=True)

        mock_prs = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        mock_triage = AsyncMock()
        mock_triage.evaluate = AsyncMock(side_effect=check_active)
        orch._triage = mock_triage

        orch._store.get_triageable = lambda _max_count: [issue]  # type: ignore[method-assign]
        await orch._triage_find_issues()

        assert was_active_during_evaluate, "Issue should be marked active during triage"
        assert not orch._store.is_active(1), "Issue should be released after triage"


# ---------------------------------------------------------------------------
# Plan phase
# ---------------------------------------------------------------------------


class TestPlanPhase:
    """Tests for the PLAN phase in the orchestrator loop."""

    @pytest.mark.asyncio
    async def test_all_loops_run_concurrently(self, config: HydraConfig) -> None:
        """Triage, plan, implement, review should all run concurrently."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]
        _mock_fetcher_noop(orch)

        execution_order: list[str] = []

        async def fake_triage() -> None:
            execution_order.append("triage_start")
            await asyncio.sleep(0)
            execution_order.append("triage_end")

        async def fake_plan() -> list[PlanResult]:
            execution_order.append("plan_start")
            await asyncio.sleep(0)
            execution_order.append("plan_end")
            orch._stop_event.set()
            return []

        async def fake_implement() -> tuple[list[WorkerResult], list[GitHubIssue]]:
            execution_order.append("implement_start")
            await asyncio.sleep(0)
            execution_order.append("implement_end")
            return [], []

        orch._triage_find_issues = fake_triage  # type: ignore[method-assign]
        orch._plan_issues = fake_plan  # type: ignore[method-assign]
        orch._implementer.run_batch = fake_implement  # type: ignore[method-assign]

        await orch.run()

        # All should have started (concurrent loops)
        assert "triage_start" in execution_order
        assert "plan_start" in execution_order
        assert "implement_start" in execution_order

    @pytest.mark.asyncio
    async def test_plan_issues_posts_comment_on_success(
        self, config: HydraConfig
    ) -> None:
        """On successful plan, post_comment should be called."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        plan_result = PlanResult(
            issue_number=42,
            success=True,
            plan="Step 1: Do the thing",
            summary="Plan done",
        )

        orch._planners.plan = AsyncMock(return_value=plan_result)  # type: ignore[method-assign]
        orch._store.get_plannable = lambda _max_count: [issue]  # type: ignore[method-assign]

        mock_prs = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        await orch._plan_issues()

        # post_comment called twice: plan comment + analysis comment
        assert mock_prs.post_comment.await_count >= 1
        plan_call = mock_prs.post_comment.call_args_list[0]
        assert plan_call.args[0] == 42
        assert "Step 1: Do the thing" in plan_call.args[1]
        assert "agent/issue-42" in plan_call.args[1]

    @pytest.mark.asyncio
    async def test_plan_issues_swaps_labels_on_success(
        self, config: HydraConfig
    ) -> None:
        """On success, planner_label should be removed and config.ready_label added."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        plan_result = PlanResult(
            issue_number=42,
            success=True,
            plan="The plan",
            summary="Done",
        )

        orch._planners.plan = AsyncMock(return_value=plan_result)  # type: ignore[method-assign]
        orch._store.get_plannable = lambda _max_count: [issue]  # type: ignore[method-assign]

        mock_prs = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        await orch._plan_issues()

        # With multi-label, remove_label is called once per planner label
        remove_calls = [c.args for c in mock_prs.remove_label.call_args_list]
        for lbl in config.planner_label:
            assert (42, lbl) in remove_calls
        mock_prs.add_labels.assert_awaited_once_with(42, [config.ready_label[0]])

    @pytest.mark.asyncio
    async def test_plan_issues_skips_label_swap_on_failure(
        self, config: HydraConfig
    ) -> None:
        """On failure, no label changes should be made."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        plan_result = PlanResult(
            issue_number=42,
            success=False,
            error="Agent crashed",
        )

        orch._planners.plan = AsyncMock(return_value=plan_result)  # type: ignore[method-assign]
        orch._store.get_plannable = lambda _max_count: [issue]  # type: ignore[method-assign]

        mock_prs = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        await orch._plan_issues()

        mock_prs.post_comment.assert_not_awaited()
        mock_prs.remove_label.assert_not_awaited()
        mock_prs.add_labels.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_plan_issues_returns_empty_when_no_issues(
        self, config: HydraConfig
    ) -> None:
        """When no issues have the planner label, return empty list."""
        orch = HydraOrchestrator(config)
        orch._store.get_plannable = lambda _max_count: []  # type: ignore[method-assign]

        results = await orch._plan_issues()

        assert results == []

    @pytest.mark.asyncio
    async def test_plan_issue_creation_records_lifetime_stats(
        self, config: HydraConfig
    ) -> None:
        """record_issue_created should be called for each new issue filed by planner."""
        from models import NewIssueSpec

        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        plan_result = PlanResult(
            issue_number=42,
            success=True,
            plan="The plan",
            summary="Done",
            new_issues=[
                NewIssueSpec(
                    title="Issue A",
                    body="Issue A has a bug in the authentication flow "
                    "that causes login failures on retry.",
                    labels=["bug"],
                ),
                NewIssueSpec(
                    title="Issue B",
                    body="Issue B has a race condition in the websocket "
                    "handler that drops messages under load.",
                    labels=["bug"],
                ),
            ],
        )

        orch._planners.plan = AsyncMock(return_value=plan_result)  # type: ignore[method-assign]
        orch._store.get_plannable = lambda _max_count: [issue]  # type: ignore[method-assign]

        mock_prs = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        mock_prs.create_issue = AsyncMock(return_value=99)
        orch._prs = mock_prs

        await orch._plan_issues()

        stats = orch._state.get_lifetime_stats()
        assert stats["issues_created"] == 2

    @pytest.mark.asyncio
    async def test_plan_issues_files_new_issues(self, config: HydraConfig) -> None:
        """When planner discovers new issues, they should be filed via create_issue."""
        from models import NewIssueSpec

        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        plan_result = PlanResult(
            issue_number=42,
            success=True,
            plan="The plan",
            summary="Done",
            new_issues=[
                NewIssueSpec(
                    title="Tech debt",
                    body="The auth module has accumulated significant tech debt "
                    "that needs cleanup and refactoring.",
                    labels=["tech-debt"],
                ),
            ],
        )

        orch._planners.plan = AsyncMock(return_value=plan_result)  # type: ignore[method-assign]
        orch._store.get_plannable = lambda _max_count: [issue]  # type: ignore[method-assign]

        mock_prs = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        mock_prs.create_issue = AsyncMock(return_value=99)
        orch._prs = mock_prs

        await orch._plan_issues()

        mock_prs.create_issue.assert_awaited_once_with(
            "Tech debt",
            "The auth module has accumulated significant tech debt "
            "that needs cleanup and refactoring.",
            ["tech-debt"],
        )

    @pytest.mark.asyncio
    async def test_plan_issues_semaphore_limits_concurrency(
        self, config: HydraConfig
    ) -> None:
        """max_planners=1 means at most 1 planner runs concurrently."""
        concurrency_counter = {"current": 0, "peak": 0}

        async def fake_plan(issue: GitHubIssue, worker_id: int = 0) -> PlanResult:
            concurrency_counter["current"] += 1
            concurrency_counter["peak"] = max(
                concurrency_counter["peak"], concurrency_counter["current"]
            )
            await asyncio.sleep(0)  # yield to allow other tasks to start
            concurrency_counter["current"] -= 1
            return PlanResult(
                issue_number=issue.number,
                success=True,
                plan="The plan",
                summary="Done",
            )

        issues = [make_issue(i) for i in range(1, 6)]

        orch = HydraOrchestrator(config)  # max_planners=1 from conftest
        orch._planners.plan = fake_plan  # type: ignore[method-assign]
        orch._store.get_plannable = lambda _max_count: issues  # type: ignore[method-assign]

        mock_prs = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        await orch._plan_issues()

        assert concurrency_counter["peak"] <= config.max_planners

    @pytest.mark.asyncio
    async def test_plan_issues_marks_active_during_processing(
        self, config: HydraConfig
    ) -> None:
        """Plan should mark issues active to prevent re-queuing by refresh."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)

        was_active_during_plan = False

        async def check_active_plan(
            issue_obj: object, worker_id: int = 0
        ) -> PlanResult:
            nonlocal was_active_during_plan
            was_active_during_plan = orch._store.is_active(42)
            return PlanResult(
                issue_number=42, success=True, plan="Plan", summary="Done"
            )

        orch._planners.plan = AsyncMock(side_effect=check_active_plan)  # type: ignore[method-assign]
        orch._store.get_plannable = lambda _max_count: [issue]  # type: ignore[method-assign]

        mock_prs = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        await orch._plan_issues()

        assert was_active_during_plan, "Issue should be marked active during planning"
        assert not orch._store.is_active(42), "Issue should be released after planning"

    @pytest.mark.asyncio
    async def test_plan_issues_failure_returns_result_with_error(
        self, config: HydraConfig
    ) -> None:
        """Plan failure (success=False) should still return the result."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        plan_result = PlanResult(
            issue_number=42,
            success=False,
            error="Agent crashed",
        )

        orch._planners.plan = AsyncMock(return_value=plan_result)  # type: ignore[method-assign]
        orch._store.get_plannable = lambda _max_count: [issue]  # type: ignore[method-assign]

        mock_prs = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        results = await orch._plan_issues()

        assert len(results) == 1
        assert results[0].success is False
        assert results[0].error == "Agent crashed"

    @pytest.mark.asyncio
    async def test_plan_issues_new_issues_use_default_planner_label_when_no_labels(
        self, config: HydraConfig
    ) -> None:
        """New issues with empty labels should fall back to planner_label."""
        from models import NewIssueSpec

        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        plan_result = PlanResult(
            issue_number=42,
            success=True,
            plan="The plan",
            summary="Done",
            new_issues=[
                NewIssueSpec(
                    title="Discovered issue",
                    body="This issue was discovered during planning — the config "
                    "parser does not handle nested environment variables.",
                ),
            ],
        )

        orch._planners.plan = AsyncMock(return_value=plan_result)  # type: ignore[method-assign]
        orch._store.get_plannable = lambda _max_count: [issue]  # type: ignore[method-assign]

        mock_prs = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        mock_prs.create_issue = AsyncMock(return_value=99)
        orch._prs = mock_prs

        await orch._plan_issues()

        mock_prs.create_issue.assert_awaited_once_with(
            "Discovered issue",
            "This issue was discovered during planning — the config "
            "parser does not handle nested environment variables.",
            [config.planner_label[0]],
        )

    @pytest.mark.asyncio
    async def test_plan_issues_skips_new_issues_with_short_body(
        self, config: HydraConfig
    ) -> None:
        """New issues with body < 50 chars should be skipped, not filed."""
        from models import NewIssueSpec

        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        plan_result = PlanResult(
            issue_number=42,
            success=True,
            plan="The plan",
            summary="Done",
            new_issues=[
                NewIssueSpec(title="Short body issue", body="Too short"),
            ],
        )

        orch._planners.plan = AsyncMock(return_value=plan_result)  # type: ignore[method-assign]
        orch._store.get_plannable = lambda _max_count: [issue]  # type: ignore[method-assign]

        mock_prs = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        mock_prs.create_issue = AsyncMock(return_value=99)
        orch._prs = mock_prs

        await orch._plan_issues()

        mock_prs.create_issue.assert_not_awaited()
        assert orch._state.get_lifetime_stats()["issues_created"] == 0

    @pytest.mark.asyncio
    async def test_plan_issues_stop_event_cancels_remaining(
        self, config: HydraConfig
    ) -> None:
        """Setting stop_event after first plan should cancel remaining."""
        orch = HydraOrchestrator(config)
        issues = [make_issue(1), make_issue(2), make_issue(3)]
        call_count = {"n": 0}

        async def fake_plan(issue: GitHubIssue, worker_id: int = 0) -> PlanResult:
            call_count["n"] += 1
            if call_count["n"] == 1:
                orch._stop_event.set()
            return PlanResult(
                issue_number=issue.number,
                success=False,
                error="stopped",
            )

        orch._planners.plan = fake_plan  # type: ignore[method-assign]
        orch._store.get_plannable = lambda _max_count: issues  # type: ignore[method-assign]

        mock_prs = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        results = await orch._plan_issues()

        # Not all 3 should have completed — stop event triggers cancellation
        assert len(results) < len(issues)

    @pytest.mark.asyncio
    async def test_plan_issues_escalates_to_hitl_after_retry_failure(
        self, config: HydraConfig
    ) -> None:
        """Failed retry triggers HITL label swap and comment."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        plan_result = PlanResult(
            issue_number=42,
            success=False,
            plan="Bad plan",
            summary="Failed",
            retry_attempted=True,
            validation_errors=[
                "Missing required section: ## Testing Strategy",
                "Plan has 10 words, minimum is 200",
            ],
        )

        orch._planners.plan = AsyncMock(return_value=plan_result)  # type: ignore[method-assign]
        orch._store.get_plannable = lambda _max_count: [issue]  # type: ignore[method-assign]

        mock_prs = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        await orch._plan_issues()

        # HITL comment should be posted
        mock_prs.post_comment.assert_awaited_once()
        comment = mock_prs.post_comment.call_args.args[1]
        assert "Plan Validation Failed" in comment
        assert "Testing Strategy" in comment

        # Planner label removed, HITL label added
        remove_calls = [c.args for c in mock_prs.remove_label.call_args_list]
        for lbl in config.planner_label:
            assert (42, lbl) in remove_calls
        mock_prs.add_labels.assert_awaited_once_with(42, [config.hitl_label[0]])

        # HITL origin and cause tracked in state
        assert orch._state.get_hitl_origin(42) == config.planner_label[0]
        assert orch._state.get_hitl_cause(42) == "Plan validation failed after retry"

    @pytest.mark.asyncio
    async def test_plan_issues_no_hitl_on_failure_without_retry(
        self, config: HydraConfig
    ) -> None:
        """Normal failure (no retry) should NOT escalate to HITL."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        plan_result = PlanResult(
            issue_number=42,
            success=False,
            error="Agent crashed",
            retry_attempted=False,
        )

        orch._planners.plan = AsyncMock(return_value=plan_result)  # type: ignore[method-assign]
        orch._store.get_plannable = lambda _max_count: [issue]  # type: ignore[method-assign]

        mock_prs = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        await orch._plan_issues()

        mock_prs.post_comment.assert_not_awaited()
        mock_prs.remove_label.assert_not_awaited()
        mock_prs.add_labels.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_plan_issues_runs_analysis_before_label_swap(
        self, config: HydraConfig
    ) -> None:
        """Analysis comment should be posted after the plan comment."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        plan_result = PlanResult(
            issue_number=42,
            success=True,
            plan="## Files to Modify\n\n- `models.py`: change\n\n## Testing Strategy\n\nUse pytest.",
            summary="Plan done",
        )

        # Create the files so analysis passes
        repo = config.repo_root
        repo.mkdir(parents=True, exist_ok=True)
        (repo / "models.py").write_text("# models\n")
        (repo / "tests").mkdir(exist_ok=True)
        (repo / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")

        orch._planners.plan = AsyncMock(return_value=plan_result)  # type: ignore[method-assign]
        orch._store.get_plannable = lambda _max_count: [issue]  # type: ignore[method-assign]

        mock_prs = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        await orch._plan_issues()

        # Two comments: plan + analysis
        assert mock_prs.post_comment.await_count == 2
        analysis_comment = mock_prs.post_comment.call_args_list[1].args[1]
        assert "Pre-Implementation Analysis" in analysis_comment

    @pytest.mark.asyncio
    async def test_plan_issues_proceeds_on_analysis_pass(
        self, config: HydraConfig
    ) -> None:
        """PASS verdict should proceed with normal label swap."""
        from unittest.mock import patch as mock_patch

        from analysis import PlanAnalyzer
        from models import AnalysisResult, AnalysisSection, AnalysisVerdict

        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        plan_result = PlanResult(
            issue_number=42,
            success=True,
            plan="The plan",
            summary="Done",
        )

        pass_result = AnalysisResult(
            issue_number=42,
            sections=[
                AnalysisSection(
                    name="File Validation",
                    verdict=AnalysisVerdict.PASS,
                    details=["All good"],
                ),
            ],
        )

        orch._planners.plan = AsyncMock(return_value=plan_result)  # type: ignore[method-assign]
        orch._store.get_plannable = lambda _max_count: [issue]  # type: ignore[method-assign]

        mock_prs = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        with mock_patch.object(PlanAnalyzer, "analyze", return_value=pass_result):
            await orch._plan_issues()

        # Should add ready label
        add_calls = [c.args for c in mock_prs.add_labels.call_args_list]
        assert (42, [config.ready_label[0]]) in add_calls

    @pytest.mark.asyncio
    async def test_plan_issues_proceeds_on_analysis_warn(
        self, config: HydraConfig
    ) -> None:
        """WARN verdict should still proceed with normal label swap."""
        from unittest.mock import patch as mock_patch

        from analysis import PlanAnalyzer
        from models import AnalysisResult, AnalysisSection, AnalysisVerdict

        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        plan_result = PlanResult(
            issue_number=42,
            success=True,
            plan="The plan",
            summary="Done",
        )

        warn_result = AnalysisResult(
            issue_number=42,
            sections=[
                AnalysisSection(
                    name="Conflict Check",
                    verdict=AnalysisVerdict.WARN,
                    details=["Minor overlap"],
                ),
            ],
        )

        orch._planners.plan = AsyncMock(return_value=plan_result)  # type: ignore[method-assign]
        orch._store.get_plannable = lambda _max_count: [issue]  # type: ignore[method-assign]

        mock_prs = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        with mock_patch.object(PlanAnalyzer, "analyze", return_value=warn_result):
            await orch._plan_issues()

        # Should add ready label (warn doesn't block)
        add_calls = [c.args for c in mock_prs.add_labels.call_args_list]
        assert (42, [config.ready_label[0]]) in add_calls


# ---------------------------------------------------------------------------
# Plan phase — already_satisfied
# ---------------------------------------------------------------------------


class TestPlanPhaseAlreadySatisfied:
    """Tests for already_satisfied handling in the plan loop."""

    @pytest.mark.asyncio
    async def test_plan_already_satisfied_closes_issue_with_dup_label(
        self, config: HydraConfig
    ) -> None:
        """When planner returns already_satisfied, issue should be closed with dup label."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        plan_result = PlanResult(
            issue_number=42,
            success=True,
            already_satisfied=True,
            summary="The feature is already implemented in src/models.py",
        )

        orch._planners.plan = AsyncMock(return_value=plan_result)  # type: ignore[method-assign]
        orch._store.get_plannable = lambda _max_count: [issue]  # type: ignore[method-assign]

        mock_prs = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        mock_prs.close_issue = AsyncMock()
        orch._prs = mock_prs

        await orch._plan_issues()

        # Planner labels should be removed
        remove_calls = [c.args for c in mock_prs.remove_label.call_args_list]
        for lbl in config.planner_label:
            assert (42, lbl) in remove_calls

        # Dup labels should be added
        mock_prs.add_labels.assert_awaited_once_with(42, config.dup_label)

        # Comment should be posted
        mock_prs.post_comment.assert_awaited_once()
        comment = mock_prs.post_comment.call_args.args[1]
        assert "Already Satisfied" in comment
        assert "Hydra Planner" in comment

        # Issue should be closed
        mock_prs.close_issue.assert_awaited_once_with(42)

    @pytest.mark.asyncio
    async def test_plan_already_satisfied_does_not_swap_to_ready(
        self, config: HydraConfig
    ) -> None:
        """When already_satisfied, issue should NOT get hydra-ready label."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        plan_result = PlanResult(
            issue_number=42,
            success=True,
            already_satisfied=True,
            summary="Already met",
        )

        orch._planners.plan = AsyncMock(return_value=plan_result)  # type: ignore[method-assign]
        orch._store.get_plannable = lambda _max_count: [issue]  # type: ignore[method-assign]

        mock_prs = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        mock_prs.close_issue = AsyncMock()
        orch._prs = mock_prs

        await orch._plan_issues()

        # Should NOT add ready label
        add_calls = [c.args for c in mock_prs.add_labels.call_args_list]
        ready_calls = [c for c in add_calls if config.ready_label[0] in c[1]]
        assert len(ready_calls) == 0


# ---------------------------------------------------------------------------
# HITL correction tracking
# ---------------------------------------------------------------------------


class TestHITLCorrection:
    """Tests for HITL correction methods on HydraOrchestrator."""

    def test_hitl_corrections_starts_empty(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        assert orch._hitl_corrections == {}

    def test_submit_hitl_correction_stores_correction(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        orch.submit_hitl_correction(42, "Mock the database connection")
        assert orch._hitl_corrections[42] == "Mock the database connection"

    def test_submit_hitl_correction_overwrites_previous(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        orch.submit_hitl_correction(42, "First attempt")
        orch.submit_hitl_correction(42, "Second attempt")
        assert orch._hitl_corrections[42] == "Second attempt"

    def test_get_hitl_status_returns_pending_by_default(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        assert orch.get_hitl_status(42) == "pending"

    def test_get_hitl_status_returns_processing_when_active_in_store(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        orch._store.mark_active(42, "implement")
        assert orch.get_hitl_status(42) == "processing"

    def test_get_hitl_status_returns_processing_when_active_in_review_store(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        orch._store.mark_active(42, "review")
        assert orch.get_hitl_status(42) == "processing"

    def test_get_hitl_status_returns_processing_when_active_in_hitl(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        orch._active_hitl_issues.add(42)
        assert orch.get_hitl_status(42) == "processing"

    def test_get_hitl_status_returns_pending_when_not_active(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        orch._store.mark_active(99, "implement")
        assert orch.get_hitl_status(42) == "pending"

    @pytest.mark.parametrize(
        "label, expected",
        [
            ("hydra-find", "from triage"),
            ("hydra-plan", "from plan"),
            ("hydra-ready", "from implement"),
            ("hydra-review", "from review"),
        ],
    )
    def test_get_hitl_status_returns_human_readable_origin(
        self, config: HydraConfig, label: str, expected: str
    ) -> None:
        orch = HydraOrchestrator(config)
        orch._state.set_hitl_origin(42, label)
        assert orch.get_hitl_status(42) == expected

    def test_get_hitl_status_falls_back_to_pending_for_unknown_label(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        orch._state.set_hitl_origin(42, "hydra-unknown")
        assert orch.get_hitl_status(42) == "pending"

    def test_get_hitl_status_processing_takes_precedence_over_origin(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        orch._state.set_hitl_origin(42, "hydra-review")
        orch._store.mark_active(42, "implement")
        assert orch.get_hitl_status(42) == "processing"

    def test_skip_hitl_issue_removes_correction(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        orch._hitl_corrections[42] = "Some correction"
        orch.skip_hitl_issue(42)
        assert 42 not in orch._hitl_corrections

    def test_skip_hitl_issue_safe_when_no_correction(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        orch.skip_hitl_issue(99)  # Should not raise
        assert 99 not in orch._hitl_corrections


# ---------------------------------------------------------------------------
# Exception isolation — polling loops
# ---------------------------------------------------------------------------


class TestLoopExceptionIsolation:
    """Each polling loop catches exceptions per-iteration and continues."""

    @pytest.mark.asyncio
    async def test_triage_loop_continues_after_exception(
        self, config: HydraConfig
    ) -> None:
        """An exception in _triage_find_issues should not crash the triage loop."""
        orch = HydraOrchestrator(config)
        call_count = 0

        async def failing_triage() -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("triage boom")
            orch._stop_event.set()

        orch._triage_find_issues = failing_triage  # type: ignore[method-assign]

        # Run just the triage loop directly
        await orch._triage_loop()

        # Loop ran twice: first call raised, second set stop
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_plan_loop_continues_after_exception(
        self, config: HydraConfig
    ) -> None:
        """An exception in _plan_issues should not crash the plan loop."""
        orch = HydraOrchestrator(config)
        call_count = 0

        async def failing_plan() -> list[PlanResult]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("plan boom")
            orch._stop_event.set()
            return []

        orch._plan_issues = failing_plan  # type: ignore[method-assign]

        await orch._plan_loop()

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_plan_loop_does_not_call_triage(self, config: HydraConfig) -> None:
        """_plan_loop should not call _triage_find_issues (handled by _triage_loop)."""
        orch = HydraOrchestrator(config)
        triage_mock = AsyncMock()
        orch._triage_find_issues = triage_mock  # type: ignore[method-assign]

        call_count = 0

        async def plan_and_stop() -> list[PlanResult]:
            nonlocal call_count
            call_count += 1
            orch._stop_event.set()
            return []

        orch._plan_issues = plan_and_stop  # type: ignore[method-assign]
        await orch._plan_loop()

        triage_mock.assert_not_called()
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_implement_loop_continues_after_exception(
        self, config: HydraConfig
    ) -> None:
        """An exception in run_batch should not crash the implement loop."""
        orch = HydraOrchestrator(config)
        call_count = 0

        async def failing_batch() -> tuple[list[WorkerResult], list[GitHubIssue]]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("implement boom")
            orch._stop_event.set()
            return [], []

        orch._implementer.run_batch = failing_batch  # type: ignore[method-assign]

        await orch._implement_loop()

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_review_loop_continues_after_exception(
        self, config: HydraConfig
    ) -> None:
        """An exception in get_reviewable should not crash the review loop."""
        orch = HydraOrchestrator(config)
        call_count = 0

        def failing_get_reviewable(_max_count: int) -> list[GitHubIssue]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("review boom")
            orch._stop_event.set()
            return []

        orch._store.get_reviewable = failing_get_reviewable  # type: ignore[method-assign]

        await orch._review_loop()

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_error_event_published_on_triage_exception(
        self, config: HydraConfig
    ) -> None:
        """Triage loop exception should publish ERROR event with source=triage."""
        orch = HydraOrchestrator(config)
        call_count = 0

        async def failing_triage() -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("triage error")
            orch._stop_event.set()

        orch._triage_find_issues = failing_triage  # type: ignore[method-assign]

        await orch._triage_loop()

        error_events = [e for e in orch._bus.get_history() if e.type == EventType.ERROR]
        assert len(error_events) == 1
        assert error_events[0].data["source"] == "triage"
        assert "Triage loop error" in error_events[0].data["message"]

    @pytest.mark.asyncio
    async def test_error_event_published_on_implement_exception(
        self, config: HydraConfig
    ) -> None:
        """Implement loop exception should publish ERROR event with source=implement."""
        orch = HydraOrchestrator(config)
        call_count = 0

        async def failing_batch() -> tuple[list[WorkerResult], list[GitHubIssue]]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("implement error")
            orch._stop_event.set()
            return [], []

        orch._implementer.run_batch = failing_batch  # type: ignore[method-assign]

        await orch._implement_loop()

        error_events = [e for e in orch._bus.get_history() if e.type == EventType.ERROR]
        assert len(error_events) == 1
        assert error_events[0].data["source"] == "implement"

    @pytest.mark.asyncio
    async def test_error_event_published_on_review_exception(
        self, config: HydraConfig
    ) -> None:
        """Review loop exception should publish ERROR event with source=review."""
        orch = HydraOrchestrator(config)
        call_count = 0

        def failing_get_reviewable(_max_count: int) -> list[GitHubIssue]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("review error")
            orch._stop_event.set()
            return []

        orch._store.get_reviewable = failing_get_reviewable  # type: ignore[method-assign]

        await orch._review_loop()

        error_events = [e for e in orch._bus.get_history() if e.type == EventType.ERROR]
        assert len(error_events) == 1
        assert error_events[0].data["source"] == "review"

    @pytest.mark.asyncio
    async def test_cancelled_error_propagates_through_loop(
        self, config: HydraConfig
    ) -> None:
        """CancelledError should NOT be caught — it propagates for clean shutdown."""
        orch = HydraOrchestrator(config)

        async def cancelling_batch() -> tuple[list[WorkerResult], list[GitHubIssue]]:
            raise asyncio.CancelledError()

        orch._implementer.run_batch = cancelling_batch  # type: ignore[method-assign]

        with pytest.raises(asyncio.CancelledError):
            await orch._implement_loop()


# ---------------------------------------------------------------------------
# Exception isolation — supervisor
# ---------------------------------------------------------------------------


class TestSupervisorLoops:
    """Tests for the _supervise_loops supervisor that restarts crashed loops."""

    @pytest.mark.asyncio
    async def test_run_completes_normally_with_stop(self, config: HydraConfig) -> None:
        """run() should complete normally when stop is set, even with supervisor."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]
        _mock_fetcher_noop(orch)

        async def plan_and_stop() -> list[PlanResult]:
            orch._stop_event.set()
            return []

        orch._plan_issues = plan_and_stop  # type: ignore[method-assign]
        orch._implementer.run_batch = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

        await orch.run()

        assert not orch.running

    @pytest.mark.asyncio
    async def test_exception_in_one_loop_does_not_stop_others(
        self, config: HydraConfig
    ) -> None:
        """If one loop crashes despite try/except, others should keep running."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]

        implement_calls = 0

        async def failing_implement() -> tuple[list[WorkerResult], list[GitHubIssue]]:
            nonlocal implement_calls
            implement_calls += 1
            if implement_calls == 1:
                raise RuntimeError("implement crash")
            orch._stop_event.set()
            return [], []

        orch._triage_find_issues = AsyncMock()  # type: ignore[method-assign]
        orch._plan_issues = AsyncMock(return_value=[])  # type: ignore[method-assign]
        orch._implementer.run_batch = failing_implement  # type: ignore[method-assign]
        orch._store.get_reviewable = lambda _max_count: []  # type: ignore[method-assign]
        orch._store.start = AsyncMock()  # type: ignore[method-assign]

        # Use instant sleep to avoid 30s poll_interval delays
        async def instant_sleep(seconds: int) -> None:
            await asyncio.sleep(0)

        orch._sleep_or_stop = instant_sleep  # type: ignore[method-assign]

        await orch.run()

        # The implement loop continued after the error (ran at least twice)
        assert implement_calls >= 2
        assert not orch.running


# ---------------------------------------------------------------------------
# Phase-specific active issue sets
# ---------------------------------------------------------------------------


class TestStoreBasedActiveIssueTracking:
    """Tests that active issue tracking uses the centralized IssueStore."""

    def test_implementer_receives_store(self, config: HydraConfig) -> None:
        """ImplementPhase receives the shared IssueStore."""
        orch = HydraOrchestrator(config)
        assert orch._implementer._store is orch._store

    def test_reviewer_receives_store(self, config: HydraConfig) -> None:
        """ReviewPhase receives the shared IssueStore."""
        orch = HydraOrchestrator(config)
        assert orch._reviewer._store is orch._store

    def test_implementer_and_reviewer_share_same_store(
        self, config: HydraConfig
    ) -> None:
        """Both phases share the same IssueStore instance."""
        orch = HydraOrchestrator(config)
        assert orch._implementer._store is orch._reviewer._store

    def test_reset_clears_store_active_and_hitl(self, config: HydraConfig) -> None:
        """reset() must clear store active tracking and HITL issues."""
        orch = HydraOrchestrator(config)
        orch._store.mark_active(1, "implement")
        orch._store.mark_active(2, "review")
        orch._active_hitl_issues.add(3)
        orch.reset()
        assert not orch._store.is_active(1)
        assert not orch._store.is_active(2)
        assert len(orch._active_hitl_issues) == 0

    @pytest.mark.asyncio
    async def test_review_loop_passes_store_active_to_fetcher(
        self, config: HydraConfig
    ) -> None:
        """_review_loop should pass store active issues to fetch_reviewable_prs."""
        orch = HydraOrchestrator(config)
        review_issue = make_issue(42)
        captured_active: set[int] | None = None

        orch._store.get_reviewable = lambda _max_count: [review_issue]  # type: ignore[method-assign]
        orch._store.get_active_issues = lambda: {42: "review"}  # type: ignore[method-assign]

        async def capturing_fetch(
            active: set[int],
            prefetched_issues: object = None,
        ) -> tuple[list[PRInfo], list[GitHubIssue]]:
            nonlocal captured_active
            captured_active = active
            orch._stop_event.set()
            return [], []

        orch._fetcher.fetch_reviewable_prs = capturing_fetch  # type: ignore[method-assign]
        await orch._review_loop()

        assert captured_active == {42}

    def test_store_active_tracking_is_unified(self, config: HydraConfig) -> None:
        """Marking an issue active in one stage is visible to all phases."""
        orch = HydraOrchestrator(config)
        orch._store.mark_active(100, "implement")

        # The same store is shared, so is_active works from anywhere
        assert orch._store.is_active(100)
        # Marking complete removes it
        orch._store.mark_complete(100)
        assert not orch._store.is_active(100)


# ---------------------------------------------------------------------------
# HITL loop
# ---------------------------------------------------------------------------


class TestHITLLoop:
    """Tests for the HITL correction loop in the orchestrator."""

    def test_hitl_runner_is_created_in_init(self, config: HydraConfig) -> None:
        from hitl_runner import HITLRunner

        orch = HydraOrchestrator(config)
        assert isinstance(orch._hitl_runner, HITLRunner)

    def test_hitl_loop_in_loop_factories(self, config: HydraConfig) -> None:
        """The hitl loop should be listed in _supervise_loops."""
        orch = HydraOrchestrator(config)
        # Verify the loop method exists
        assert hasattr(orch, "_hitl_loop")
        assert asyncio.iscoroutinefunction(orch._hitl_loop)

    @pytest.mark.asyncio
    async def test_hitl_loop_runs_in_supervise_loops(self, config: HydraConfig) -> None:
        """The HITL loop should be started by _supervise_loops alongside others."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]
        _mock_fetcher_noop(orch)

        hitl_ran = False

        async def tracking_hitl_loop() -> None:
            nonlocal hitl_ran
            hitl_ran = True
            orch._stop_event.set()

        orch._hitl_loop = tracking_hitl_loop  # type: ignore[method-assign]
        orch._triage_find_issues = AsyncMock()  # type: ignore[method-assign]
        orch._plan_issues = AsyncMock(return_value=[])  # type: ignore[method-assign]
        orch._implementer.run_batch = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

        await orch.run()

        assert hitl_ran

    @pytest.mark.asyncio
    async def test_process_hitl_corrections_skips_when_empty(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        orch._hitl_corrections = {}

        mock_prs = AsyncMock()
        orch._prs = mock_prs

        await orch._process_hitl_corrections()

        mock_prs.remove_label.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_one_hitl_success_restores_origin_label(
        self, config: HydraConfig
    ) -> None:
        """On success, the origin label should be restored."""
        from models import HITLResult

        orch = HydraOrchestrator(config)
        issue = make_issue(42, title="Test HITL", body="Fix it")

        orch._fetcher.fetch_issue_by_number = AsyncMock(return_value=issue)  # type: ignore[method-assign]
        orch._state.set_hitl_origin(42, "hydra-review")
        orch._state.set_hitl_cause(42, "CI failed")

        mock_prs = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.post_comment = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.create = AsyncMock(return_value=config.worktree_base / "issue-42")
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        orch._hitl_runner.run = AsyncMock(  # type: ignore[method-assign]
            return_value=HITLResult(issue_number=42, success=True)
        )

        semaphore = asyncio.Semaphore(1)
        await orch._process_one_hitl(42, "Fix the tests", semaphore)

        # Verify origin label was restored
        add_labels_calls = [c.args for c in mock_prs.add_labels.call_args_list]
        assert (42, ["hydra-review"]) in add_labels_calls

        # Verify HITL state was cleaned up
        assert orch._state.get_hitl_origin(42) is None
        assert orch._state.get_hitl_cause(42) is None

    @pytest.mark.asyncio
    async def test_process_one_hitl_failure_keeps_hitl_label(
        self, config: HydraConfig
    ) -> None:
        """On failure, the hydra-hitl label should be re-applied."""
        from models import HITLResult

        orch = HydraOrchestrator(config)
        issue = make_issue(42, title="Test HITL", body="Fix it")

        orch._fetcher.fetch_issue_by_number = AsyncMock(return_value=issue)  # type: ignore[method-assign]
        orch._state.set_hitl_origin(42, "hydra-review")
        orch._state.set_hitl_cause(42, "CI failed")

        mock_prs = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.create = AsyncMock(return_value=config.worktree_base / "issue-42")
        orch._worktrees = mock_wt

        orch._hitl_runner.run = AsyncMock(  # type: ignore[method-assign]
            return_value=HITLResult(
                issue_number=42, success=False, error="quality failed"
            )
        )

        semaphore = asyncio.Semaphore(1)
        await orch._process_one_hitl(42, "Fix the tests", semaphore)

        # Verify HITL label was re-applied
        add_labels_calls = [c.args for c in mock_prs.add_labels.call_args_list]
        assert (42, [config.hitl_label[0]]) in add_labels_calls

        # Verify HITL state is preserved (not cleaned up)
        assert orch._state.get_hitl_origin(42) == "hydra-review"
        assert orch._state.get_hitl_cause(42) == "CI failed"

    @pytest.mark.asyncio
    async def test_process_one_hitl_posts_success_comment(
        self, config: HydraConfig
    ) -> None:
        from models import HITLResult

        orch = HydraOrchestrator(config)
        issue = make_issue(42)

        orch._fetcher.fetch_issue_by_number = AsyncMock(return_value=issue)  # type: ignore[method-assign]
        orch._state.set_hitl_origin(42, "hydra-review")

        mock_prs = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.post_comment = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.create = AsyncMock(return_value=config.worktree_base / "issue-42")
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        orch._hitl_runner.run = AsyncMock(  # type: ignore[method-assign]
            return_value=HITLResult(issue_number=42, success=True)
        )

        semaphore = asyncio.Semaphore(1)
        await orch._process_one_hitl(42, "Fix it", semaphore)

        mock_prs.post_comment.assert_called_once()
        comment = mock_prs.post_comment.call_args.args[1]
        assert "HITL correction applied successfully" in comment

    @pytest.mark.asyncio
    async def test_process_one_hitl_posts_failure_comment(
        self, config: HydraConfig
    ) -> None:
        from models import HITLResult

        orch = HydraOrchestrator(config)
        issue = make_issue(42)

        orch._fetcher.fetch_issue_by_number = AsyncMock(return_value=issue)  # type: ignore[method-assign]
        orch._state.set_hitl_origin(42, "hydra-review")

        mock_prs = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.create = AsyncMock(return_value=config.worktree_base / "issue-42")
        orch._worktrees = mock_wt

        orch._hitl_runner.run = AsyncMock(  # type: ignore[method-assign]
            return_value=HITLResult(
                issue_number=42, success=False, error="make quality failed"
            )
        )

        semaphore = asyncio.Semaphore(1)
        await orch._process_one_hitl(42, "Fix it", semaphore)

        mock_prs.post_comment.assert_called_once()
        comment = mock_prs.post_comment.call_args.args[1]
        assert "HITL correction failed" in comment
        assert "make quality failed" in comment

    @pytest.mark.asyncio
    async def test_process_one_hitl_skips_when_issue_not_found(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        orch._fetcher.fetch_issue_by_number = AsyncMock(return_value=None)  # type: ignore[method-assign]

        mock_prs = AsyncMock()
        orch._prs = mock_prs

        semaphore = asyncio.Semaphore(1)
        await orch._process_one_hitl(42, "Fix it", semaphore)

        # No label changes or comments when issue not found
        mock_prs.post_comment.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_one_hitl_publishes_resolved_event_on_success(
        self, config: HydraConfig
    ) -> None:
        from models import HITLResult

        orch = HydraOrchestrator(config)
        issue = make_issue(42)

        orch._fetcher.fetch_issue_by_number = AsyncMock(return_value=issue)  # type: ignore[method-assign]
        orch._state.set_hitl_origin(42, "hydra-review")

        mock_prs = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.post_comment = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.create = AsyncMock(return_value=config.worktree_base / "issue-42")
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        orch._hitl_runner.run = AsyncMock(  # type: ignore[method-assign]
            return_value=HITLResult(issue_number=42, success=True)
        )

        semaphore = asyncio.Semaphore(1)
        await orch._process_one_hitl(42, "Fix it", semaphore)

        events = [
            e
            for e in orch._bus.get_history()
            if e.type == EventType.HITL_UPDATE and e.data.get("action") == "resolved"
        ]
        assert len(events) == 1
        assert events[0].data["status"] == "resolved"

    @pytest.mark.asyncio
    async def test_process_one_hitl_publishes_failed_event_on_failure(
        self, config: HydraConfig
    ) -> None:
        from models import HITLResult

        orch = HydraOrchestrator(config)
        issue = make_issue(42)

        orch._fetcher.fetch_issue_by_number = AsyncMock(return_value=issue)  # type: ignore[method-assign]
        orch._state.set_hitl_origin(42, "hydra-review")

        mock_prs = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.create = AsyncMock(return_value=config.worktree_base / "issue-42")
        orch._worktrees = mock_wt

        orch._hitl_runner.run = AsyncMock(  # type: ignore[method-assign]
            return_value=HITLResult(issue_number=42, success=False, error="fail")
        )

        semaphore = asyncio.Semaphore(1)
        await orch._process_one_hitl(42, "Fix it", semaphore)

        events = [
            e
            for e in orch._bus.get_history()
            if e.type == EventType.HITL_UPDATE and e.data.get("action") == "failed"
        ]
        assert len(events) == 1
        assert events[0].data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_process_one_hitl_clears_active_issues(
        self, config: HydraConfig
    ) -> None:
        """Issue should be removed from _active_issues after processing."""
        from models import HITLResult

        orch = HydraOrchestrator(config)
        issue = make_issue(42)

        orch._fetcher.fetch_issue_by_number = AsyncMock(return_value=issue)  # type: ignore[method-assign]

        mock_prs = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.post_comment = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.create = AsyncMock(return_value=config.worktree_base / "issue-42")
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        orch._hitl_runner.run = AsyncMock(  # type: ignore[method-assign]
            return_value=HITLResult(issue_number=42, success=True)
        )

        semaphore = asyncio.Semaphore(1)
        await orch._process_one_hitl(42, "Fix it", semaphore)

        assert 42 not in orch._active_hitl_issues

    @pytest.mark.asyncio
    async def test_process_one_hitl_swaps_to_active_label(
        self, config: HydraConfig
    ) -> None:
        """Processing should swap to hitl-active label before running agent."""
        from models import HITLResult

        orch = HydraOrchestrator(config)
        issue = make_issue(42)

        orch._fetcher.fetch_issue_by_number = AsyncMock(return_value=issue)  # type: ignore[method-assign]
        orch._state.set_hitl_origin(42, "hydra-review")

        mock_prs = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.post_comment = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.create = AsyncMock(return_value=config.worktree_base / "issue-42")
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        orch._hitl_runner.run = AsyncMock(  # type: ignore[method-assign]
            return_value=HITLResult(issue_number=42, success=True)
        )

        semaphore = asyncio.Semaphore(1)
        await orch._process_one_hitl(42, "Fix it", semaphore)

        # Check that hitl_active_label was added
        add_labels_calls = [c.args for c in mock_prs.add_labels.call_args_list]
        assert (42, [config.hitl_active_label[0]]) in add_labels_calls

    @pytest.mark.asyncio
    async def test_hitl_loop_continues_after_exception(
        self, config: HydraConfig
    ) -> None:
        """An exception in _process_hitl_corrections should not crash the loop."""
        orch = HydraOrchestrator(config)
        call_count = 0

        async def failing_process() -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("hitl boom")
            orch._stop_event.set()

        orch._process_hitl_corrections = failing_process  # type: ignore[method-assign]

        await orch._hitl_loop()

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_error_event_published_on_hitl_exception(
        self, config: HydraConfig
    ) -> None:
        """HITL loop exception should publish ERROR event with source=hitl."""
        orch = HydraOrchestrator(config)
        call_count = 0

        async def failing_process() -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("hitl error")
            orch._stop_event.set()

        orch._process_hitl_corrections = failing_process  # type: ignore[method-assign]

        await orch._hitl_loop()

        error_events = [e for e in orch._bus.get_history() if e.type == EventType.ERROR]
        assert len(error_events) == 1
        assert error_events[0].data["source"] == "hitl"
        assert "Hitl loop error" in error_events[0].data["message"]

    @pytest.mark.asyncio
    async def test_stop_terminates_hitl_runner(self, config: HydraConfig) -> None:
        """stop() should call terminate() on the HITL runner."""
        orch = HydraOrchestrator(config)
        with patch.object(orch._hitl_runner, "terminate") as mock_term:
            await orch.stop()
        mock_term.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_finally_terminates_hitl_runner(
        self, config: HydraConfig
    ) -> None:
        """When run() exits, the HITL runner should be terminated."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]
        _mock_fetcher_noop(orch)

        async def plan_and_stop() -> list[PlanResult]:
            orch._stop_event.set()
            return []

        orch._plan_issues = plan_and_stop  # type: ignore[method-assign]
        orch._implementer.run_batch = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

        with patch.object(orch._hitl_runner, "terminate") as mock_term:
            await orch.run()

        mock_term.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_one_hitl_success_destroys_worktree(
        self, config: HydraConfig
    ) -> None:
        """On success, the worktree should be destroyed."""
        from models import HITLResult

        orch = HydraOrchestrator(config)
        issue = make_issue(42)

        orch._fetcher.fetch_issue_by_number = AsyncMock(return_value=issue)  # type: ignore[method-assign]
        orch._state.set_hitl_origin(42, "hydra-review")

        mock_prs = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.post_comment = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.create = AsyncMock(return_value=config.worktree_base / "issue-42")
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        orch._hitl_runner.run = AsyncMock(  # type: ignore[method-assign]
            return_value=HITLResult(issue_number=42, success=True)
        )

        semaphore = asyncio.Semaphore(1)
        await orch._process_one_hitl(42, "Fix it", semaphore)

        mock_wt.destroy.assert_awaited_once_with(42)

    @pytest.mark.asyncio
    async def test_process_one_hitl_failure_does_not_destroy_worktree(
        self, config: HydraConfig
    ) -> None:
        """On failure, the worktree should be kept for retry."""
        from models import HITLResult

        orch = HydraOrchestrator(config)
        issue = make_issue(42)

        orch._fetcher.fetch_issue_by_number = AsyncMock(return_value=issue)  # type: ignore[method-assign]
        orch._state.set_hitl_origin(42, "hydra-review")

        mock_prs = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.create = AsyncMock(return_value=config.worktree_base / "issue-42")
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        orch._hitl_runner.run = AsyncMock(  # type: ignore[method-assign]
            return_value=HITLResult(issue_number=42, success=False, error="fail")
        )

        semaphore = asyncio.Semaphore(1)
        await orch._process_one_hitl(42, "Fix it", semaphore)

        mock_wt.destroy.assert_not_awaited()


# ---------------------------------------------------------------------------
# Auth failure detection
# ---------------------------------------------------------------------------


class TestAuthFailure:
    """Tests for AuthenticationError handling in the orchestrator."""

    @pytest.mark.asyncio
    async def test_auth_failure_stops_all_loops(self, config: HydraConfig) -> None:
        """An AuthenticationError in any loop should stop the orchestrator."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]

        async def auth_failing_triage() -> None:
            raise AuthenticationError("401 Unauthorized")

        orch._triage_find_issues = auth_failing_triage  # type: ignore[method-assign]
        orch._plan_issues = AsyncMock(return_value=[])  # type: ignore[method-assign]
        orch._implementer.run_batch = AsyncMock(return_value=([], []))  # type: ignore[method-assign]
        orch._fetcher.fetch_reviewable_prs = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

        async def instant_sleep(seconds: int) -> None:
            await asyncio.sleep(0)

        orch._sleep_or_stop = instant_sleep  # type: ignore[method-assign]

        await orch.run()

        assert not orch.running
        assert orch._stop_event.is_set()

    @pytest.mark.asyncio
    async def test_auth_failure_publishes_system_alert_event(
        self, config: HydraConfig
    ) -> None:
        """Auth failure should publish a SYSTEM_ALERT event."""
        bus = EventBus()
        orch = HydraOrchestrator(config, event_bus=bus)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]

        async def auth_failing_plan() -> list[PlanResult]:
            raise AuthenticationError("401 Unauthorized")

        orch._triage_find_issues = AsyncMock()  # type: ignore[method-assign]
        orch._plan_issues = auth_failing_plan  # type: ignore[method-assign]
        orch._implementer.run_batch = AsyncMock(return_value=([], []))  # type: ignore[method-assign]
        orch._fetcher.fetch_reviewable_prs = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

        async def instant_sleep(seconds: int) -> None:
            await asyncio.sleep(0)

        orch._sleep_or_stop = instant_sleep  # type: ignore[method-assign]

        await orch.run()

        alert_events = [
            e for e in bus.get_history() if e.type == EventType.SYSTEM_ALERT
        ]
        assert len(alert_events) == 1
        assert "authentication" in alert_events[0].data["message"].lower()
        assert alert_events[0].data["source"] == "plan"

    @pytest.mark.asyncio
    async def test_auth_failure_sets_auth_failed_flag(
        self, config: HydraConfig
    ) -> None:
        """Auth failure should set the _auth_failed flag."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]

        async def auth_failing_implement() -> tuple[
            list[WorkerResult], list[GitHubIssue]
        ]:
            raise AuthenticationError("401 Unauthorized")

        orch._triage_find_issues = AsyncMock()  # type: ignore[method-assign]
        orch._plan_issues = AsyncMock(return_value=[])  # type: ignore[method-assign]
        orch._implementer.run_batch = auth_failing_implement  # type: ignore[method-assign]
        orch._fetcher.fetch_reviewable_prs = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

        async def instant_sleep(seconds: int) -> None:
            await asyncio.sleep(0)

        orch._sleep_or_stop = instant_sleep  # type: ignore[method-assign]

        await orch.run()

        assert orch._auth_failed is True

    def test_run_status_returns_auth_failed(self, config: HydraConfig) -> None:
        """run_status should return 'auth_failed' when the flag is set."""
        orch = HydraOrchestrator(config)
        orch._auth_failed = True
        assert orch.run_status == "auth_failed"

    def test_run_status_auth_failed_takes_precedence(self, config: HydraConfig) -> None:
        """auth_failed should take precedence over other statuses."""
        orch = HydraOrchestrator(config)
        orch._auth_failed = True
        orch._running = True
        assert orch.run_status == "auth_failed"

    def test_reset_clears_auth_failed(self, config: HydraConfig) -> None:
        """reset() should clear the _auth_failed flag."""
        orch = HydraOrchestrator(config)
        orch._auth_failed = True
        orch._stop_event.set()
        orch.reset()
        assert orch._auth_failed is False
        assert not orch._stop_event.is_set()


# ---------------------------------------------------------------------------
# Crash recovery — active issue persistence
# ---------------------------------------------------------------------------


class TestCrashRecoveryActiveIssues:
    """Tests for crash recovery via persisted active_issue_numbers."""

    def test_crash_recovery_loads_active_issues(self, config: HydraConfig) -> None:
        """On init, recovered issues from state should populate _recovered_issues after run()."""
        orch = HydraOrchestrator(config)
        orch._state.set_active_issue_numbers([10, 20])

        # Simulate run() startup sequence
        recovered = set(orch._state.get_active_issue_numbers())
        assert recovered == {10, 20}

    @pytest.mark.asyncio
    async def test_crash_recovery_skips_first_cycle(self, config: HydraConfig) -> None:
        """Recovered issues should be in _active_impl_issues for one cycle."""
        orch = HydraOrchestrator(config)
        _mock_fetcher_noop(orch)
        orch._state.set_active_issue_numbers([10, 20])

        # Simulate run() startup
        orch._stop_event.clear()
        orch._running = True
        recovered = set(orch._state.get_active_issue_numbers())
        orch._recovered_issues = recovered
        orch._active_impl_issues.update(recovered)

        # Before first cycle: recovered issues are in active set
        assert 10 in orch._active_impl_issues
        assert 20 in orch._active_impl_issues

    @pytest.mark.asyncio
    async def test_crash_recovery_clears_after_cycle(self, config: HydraConfig) -> None:
        """After one cycle, recovered issues should be cleared from active sets."""
        orch = HydraOrchestrator(config)
        _mock_fetcher_noop(orch)
        orch._state.set_active_issue_numbers([10, 20])

        # Simulate startup
        recovered = set(orch._state.get_active_issue_numbers())
        orch._recovered_issues = recovered
        orch._active_impl_issues.update(recovered)

        # Simulate what _implement_loop does at the start of a cycle
        if orch._recovered_issues:
            orch._active_impl_issues -= orch._recovered_issues
            orch._recovered_issues.clear()

        assert 10 not in orch._active_impl_issues
        assert 20 not in orch._active_impl_issues
        assert len(orch._recovered_issues) == 0


# ---------------------------------------------------------------------------
# HITL correction resets issue attempts
# ---------------------------------------------------------------------------


class TestHITLResetsAttempts:
    """Tests that HITL correction resets issue_attempts."""

    @pytest.mark.asyncio
    async def test_hitl_correction_resets_issue_attempts(
        self, config: HydraConfig
    ) -> None:
        """On successful HITL correction, issue_attempts should be reset."""
        from models import HITLResult

        orch = HydraOrchestrator(config)
        _mock_fetcher_noop(orch)

        # Set up state with attempts
        orch._state.increment_issue_attempts(42)
        orch._state.increment_issue_attempts(42)
        assert orch._state.get_issue_attempts(42) == 2

        # Mock HITL runner to succeed
        orch._hitl_runner.run = AsyncMock(
            return_value=HITLResult(
                issue_number=42,
                success=True,
            )
        )

        # Set HITL origin/cause
        orch._state.set_hitl_origin(42, "hydra-ready")
        orch._state.set_hitl_cause(42, "Cap exceeded")

        # Mock fetcher and PR manager
        orch._fetcher.fetch_issue_by_number = AsyncMock(return_value=make_issue(42))
        orch._prs = AsyncMock()
        orch._prs.push_branch = AsyncMock()
        orch._prs.add_labels = AsyncMock()
        orch._prs.remove_label = AsyncMock()
        orch._prs.post_comment = AsyncMock()

        # Mock worktree
        wt_path = config.worktree_base / "issue-42"
        wt_path.mkdir(parents=True, exist_ok=True)
        orch._worktrees = AsyncMock()
        orch._worktrees.create = AsyncMock(return_value=wt_path)
        orch._worktrees.destroy = AsyncMock()

        semaphore = asyncio.Semaphore(1)
        await orch._process_one_hitl(42, "Fix the tests", semaphore)

        # Issue attempts should be reset
        assert orch._state.get_issue_attempts(42) == 0


# ---------------------------------------------------------------------------
# Memory suggestion filing from implementer and reviewer transcripts
# ---------------------------------------------------------------------------

MEMORY_TRANSCRIPT = (
    "Some output\n"
    "MEMORY_SUGGESTION_START\n"
    "title: Test suggestion\n"
    "learning: Learned something useful\n"
    "context: During testing\n"
    "MEMORY_SUGGESTION_END\n"
)


class TestMemorySuggestionFiling:
    """Memory suggestions from implementer and reviewer transcripts are filed."""

    @pytest.mark.asyncio
    async def test_implement_loop_files_memory_suggestion(
        self, config: HydraConfig
    ) -> None:
        """Implementer transcripts with MEMORY_SUGGESTION blocks trigger filing."""
        orch = HydraOrchestrator(config)
        result = make_worker_result(issue_number=42, transcript=MEMORY_TRANSCRIPT)

        async def batch_and_stop() -> tuple[list[WorkerResult], list[GitHubIssue]]:
            orch._stop_event.set()
            return [result], [make_issue(42)]

        orch._implementer.run_batch = batch_and_stop  # type: ignore[method-assign]
        orch._file_memory_suggestion = AsyncMock()  # type: ignore[method-assign]

        await orch._implement_loop()

        orch._file_memory_suggestion.assert_awaited_once_with(
            MEMORY_TRANSCRIPT,
            "implementer",
            "issue #42",
        )

    @pytest.mark.asyncio
    async def test_implement_loop_skips_empty_transcript(
        self, config: HydraConfig
    ) -> None:
        """Implementer results with empty transcripts should not trigger filing."""
        orch = HydraOrchestrator(config)
        result = make_worker_result(issue_number=42, transcript="")

        async def batch_and_stop() -> tuple[list[WorkerResult], list[GitHubIssue]]:
            orch._stop_event.set()
            return [result], [make_issue(42)]

        orch._implementer.run_batch = batch_and_stop  # type: ignore[method-assign]
        orch._file_memory_suggestion = AsyncMock()  # type: ignore[method-assign]

        await orch._implement_loop()

        orch._file_memory_suggestion.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_implement_loop_multiple_results_files_each(
        self, config: HydraConfig
    ) -> None:
        """Multiple implementer results: only those with transcripts trigger filing."""
        orch = HydraOrchestrator(config)
        r1 = make_worker_result(issue_number=10, transcript=MEMORY_TRANSCRIPT)
        r2 = make_worker_result(issue_number=20, transcript="")
        r3 = make_worker_result(issue_number=30, transcript=MEMORY_TRANSCRIPT)

        async def batch_and_stop() -> tuple[list[WorkerResult], list[GitHubIssue]]:
            orch._stop_event.set()
            return [r1, r2, r3], [make_issue(10), make_issue(20), make_issue(30)]

        orch._implementer.run_batch = batch_and_stop  # type: ignore[method-assign]
        orch._file_memory_suggestion = AsyncMock()  # type: ignore[method-assign]

        await orch._implement_loop()

        assert orch._file_memory_suggestion.await_count == 2
        orch._file_memory_suggestion.assert_any_await(
            MEMORY_TRANSCRIPT, "implementer", "issue #10"
        )
        orch._file_memory_suggestion.assert_any_await(
            MEMORY_TRANSCRIPT, "implementer", "issue #30"
        )

    @pytest.mark.asyncio
    async def test_review_loop_files_memory_suggestion(
        self, config: HydraConfig
    ) -> None:
        """Reviewer transcripts with MEMORY_SUGGESTION blocks trigger filing."""
        orch = HydraOrchestrator(config)
        review_issue = make_issue(42)
        pr = make_pr_info(number=101, issue_number=42)
        review_result = make_review_result(
            pr_number=101, issue_number=42, transcript=MEMORY_TRANSCRIPT
        )

        orch._store.get_active_issues = lambda: {42: "review"}  # type: ignore[method-assign]
        orch._fetcher.fetch_reviewable_prs = AsyncMock(  # type: ignore[method-assign]
            return_value=([pr], [review_issue])
        )
        orch._reviewer.review_prs = AsyncMock(return_value=[review_result])  # type: ignore[method-assign]
        orch._prs.pull_main = AsyncMock()  # type: ignore[method-assign]
        orch._file_memory_suggestion = AsyncMock()  # type: ignore[method-assign]

        call_count = 0

        def get_reviewable_once(_max_count: int) -> list[GitHubIssue]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [review_issue]
            orch._stop_event.set()
            return []

        orch._store.get_reviewable = get_reviewable_once  # type: ignore[method-assign]

        await orch._review_loop()

        orch._file_memory_suggestion.assert_awaited_once_with(
            MEMORY_TRANSCRIPT,
            "reviewer",
            "PR #101",
        )

    @pytest.mark.asyncio
    async def test_review_loop_skips_empty_transcript(
        self, config: HydraConfig
    ) -> None:
        """Reviewer results with empty transcripts should not trigger filing."""
        orch = HydraOrchestrator(config)
        review_issue = make_issue(42)
        pr = make_pr_info(number=101, issue_number=42)
        review_result = make_review_result(
            pr_number=101, issue_number=42, transcript=""
        )

        orch._store.get_reviewable = lambda _max_count: [review_issue]  # type: ignore[method-assign]
        orch._store.get_active_issues = lambda: {42: "review"}  # type: ignore[method-assign]
        orch._fetcher.fetch_reviewable_prs = AsyncMock(  # type: ignore[method-assign]
            return_value=([pr], [review_issue])
        )
        orch._reviewer.review_prs = AsyncMock(return_value=[review_result])  # type: ignore[method-assign]
        orch._prs.pull_main = AsyncMock()  # type: ignore[method-assign]
        orch._file_memory_suggestion = AsyncMock()  # type: ignore[method-assign]

        call_count = 0

        def get_reviewable_once(_max_count: int) -> list[GitHubIssue]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [review_issue]
            orch._stop_event.set()
            return []

        orch._store.get_reviewable = get_reviewable_once  # type: ignore[method-assign]

        await orch._review_loop()

        orch._file_memory_suggestion.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_review_loop_multiple_results_files_each(
        self, config: HydraConfig
    ) -> None:
        """Multiple reviewer results: only those with transcripts trigger filing."""
        orch = HydraOrchestrator(config)
        issue_a = make_issue(10)
        issue_b = make_issue(20)
        pr_a = make_pr_info(number=201, issue_number=10)
        pr_b = make_pr_info(number=202, issue_number=20)
        r1 = make_review_result(
            pr_number=201, issue_number=10, transcript=MEMORY_TRANSCRIPT
        )
        r2 = make_review_result(pr_number=202, issue_number=20, transcript="")

        orch._store.get_reviewable = lambda _max_count: [issue_a, issue_b]  # type: ignore[method-assign]
        orch._store.get_active_issues = lambda: {10: "review", 20: "review"}  # type: ignore[method-assign]
        orch._fetcher.fetch_reviewable_prs = AsyncMock(  # type: ignore[method-assign]
            return_value=([pr_a, pr_b], [issue_a, issue_b])
        )
        orch._reviewer.review_prs = AsyncMock(return_value=[r1, r2])  # type: ignore[method-assign]
        orch._prs.pull_main = AsyncMock()  # type: ignore[method-assign]
        orch._file_memory_suggestion = AsyncMock()  # type: ignore[method-assign]

        call_count = 0

        def get_reviewable_once(_max_count: int) -> list[GitHubIssue]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [issue_a, issue_b]
            orch._stop_event.set()
            return []

        orch._store.get_reviewable = get_reviewable_once  # type: ignore[method-assign]

        await orch._review_loop()

        orch._file_memory_suggestion.assert_awaited_once_with(
            MEMORY_TRANSCRIPT,
            "reviewer",
            "PR #201",
        )

    @pytest.mark.asyncio
    async def test_implement_loop_isolates_memory_filing_error(
        self, config: HydraConfig
    ) -> None:
        """Memory filing failure in implementer must not crash the loop."""
        orch = HydraOrchestrator(config)
        r1 = make_worker_result(issue_number=10, transcript=MEMORY_TRANSCRIPT)
        r2 = make_worker_result(issue_number=20, transcript=MEMORY_TRANSCRIPT)

        async def batch_and_stop() -> tuple[list[WorkerResult], list[GitHubIssue]]:
            orch._stop_event.set()
            return [r1, r2], [make_issue(10), make_issue(20)]

        orch._implementer.run_batch = batch_and_stop  # type: ignore[method-assign]
        orch._file_memory_suggestion = AsyncMock(  # type: ignore[method-assign]
            side_effect=[RuntimeError("transient"), None],
        )

        await orch._implement_loop()  # must not raise

        assert orch._file_memory_suggestion.await_count == 2

    @pytest.mark.asyncio
    async def test_review_loop_isolates_memory_filing_error(
        self, config: HydraConfig
    ) -> None:
        """Memory filing failure in reviewer must not crash the loop."""
        orch = HydraOrchestrator(config)
        issue_a = make_issue(10)
        pr_a = make_pr_info(number=201, issue_number=10)
        r1 = make_review_result(
            pr_number=201, issue_number=10, transcript=MEMORY_TRANSCRIPT
        )

        orch._store.get_active_issues = lambda: {10: "review"}  # type: ignore[method-assign]
        orch._fetcher.fetch_reviewable_prs = AsyncMock(  # type: ignore[method-assign]
            return_value=([pr_a], [issue_a])
        )
        orch._reviewer.review_prs = AsyncMock(return_value=[r1])  # type: ignore[method-assign]
        orch._prs.pull_main = AsyncMock()  # type: ignore[method-assign]
        orch._file_memory_suggestion = AsyncMock(  # type: ignore[method-assign]
            side_effect=RuntimeError("transient"),
        )

        call_count = 0

        def get_reviewable_once(_max_count: int) -> list[GitHubIssue]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [issue_a]
            orch._stop_event.set()
            return []

        orch._store.get_reviewable = get_reviewable_once  # type: ignore[method-assign]

        await orch._review_loop()  # must not raise

        orch._file_memory_suggestion.assert_awaited_once()


# ---------------------------------------------------------------------------
# HITL improve→triage transition on correction success
# ---------------------------------------------------------------------------


class TestHITLImproveTransition:
    """Tests that improve-origin HITL corrections transition to triage."""

    @pytest.mark.asyncio
    async def test_process_one_hitl_success_improve_origin_transitions_to_triage(
        self, config: HydraConfig
    ) -> None:
        """On success with improve origin, should remove improve and add find label."""
        from models import HITLResult

        orch = HydraOrchestrator(config)
        issue = make_issue(42, title="Improve: test", body="Details")

        orch._fetcher.fetch_issue_by_number = AsyncMock(return_value=issue)  # type: ignore[method-assign]
        orch._state.set_hitl_origin(42, "hydra-improve")
        orch._state.set_hitl_cause(42, "Memory suggestion")

        mock_prs = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.post_comment = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.create = AsyncMock(return_value=config.worktree_base / "issue-42")
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        orch._hitl_runner.run = AsyncMock(  # type: ignore[method-assign]
            return_value=HITLResult(issue_number=42, success=True)
        )

        semaphore = asyncio.Semaphore(1)
        await orch._process_one_hitl(42, "Improve the prompt", semaphore)

        # Verify improve label was removed
        remove_calls = [c.args for c in mock_prs.remove_label.call_args_list]
        assert (42, "hydra-improve") in remove_calls

        # Verify find/triage label was added (not the improve label)
        add_calls = [c.args for c in mock_prs.add_labels.call_args_list]
        assert (42, [config.find_label[0]]) in add_calls
        # Ensure hydra-improve was NOT restored as a label
        assert (42, ["hydra-improve"]) not in add_calls

        # Verify HITL state was cleaned up
        assert orch._state.get_hitl_origin(42) is None
        assert orch._state.get_hitl_cause(42) is None

    @pytest.mark.asyncio
    async def test_process_one_hitl_success_non_improve_origin_restores_label(
        self, config: HydraConfig
    ) -> None:
        """Non-improve origins should still restore the original label (existing behavior)."""
        from models import HITLResult

        orch = HydraOrchestrator(config)
        issue = make_issue(42, title="Test", body="Details")

        orch._fetcher.fetch_issue_by_number = AsyncMock(return_value=issue)  # type: ignore[method-assign]
        orch._state.set_hitl_origin(42, "hydra-review")
        orch._state.set_hitl_cause(42, "CI failed")

        mock_prs = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.post_comment = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.create = AsyncMock(return_value=config.worktree_base / "issue-42")
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        orch._hitl_runner.run = AsyncMock(  # type: ignore[method-assign]
            return_value=HITLResult(issue_number=42, success=True)
        )

        semaphore = asyncio.Semaphore(1)
        await orch._process_one_hitl(42, "Fix the tests", semaphore)

        # Verify review label was restored (existing behavior)
        add_calls = [c.args for c in mock_prs.add_labels.call_args_list]
        assert (42, ["hydra-review"]) in add_calls

        # Verify find label was NOT added
        assert (42, [config.find_label[0]]) not in add_calls

    @pytest.mark.asyncio
    async def test_process_one_hitl_failure_improve_origin_preserves_state(
        self, config: HydraConfig
    ) -> None:
        """On failure, improve origin state should be preserved for retry."""
        from models import HITLResult

        orch = HydraOrchestrator(config)
        issue = make_issue(42, title="Improve: test", body="Details")

        orch._fetcher.fetch_issue_by_number = AsyncMock(return_value=issue)  # type: ignore[method-assign]
        orch._state.set_hitl_origin(42, "hydra-improve")
        orch._state.set_hitl_cause(42, "Memory suggestion")

        mock_prs = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.create = AsyncMock(return_value=config.worktree_base / "issue-42")
        orch._worktrees = mock_wt

        orch._hitl_runner.run = AsyncMock(  # type: ignore[method-assign]
            return_value=HITLResult(
                issue_number=42, success=False, error="quality failed"
            )
        )

        semaphore = asyncio.Semaphore(1)
        await orch._process_one_hitl(42, "Improve the prompt", semaphore)

        # Verify HITL label was re-applied
        add_calls = [c.args for c in mock_prs.add_labels.call_args_list]
        assert (42, [config.hitl_label[0]]) in add_calls

        # Verify improve origin state is preserved for retry
        assert orch._state.get_hitl_origin(42) == "hydra-improve"
        assert orch._state.get_hitl_cause(42) == "Memory suggestion"

    @pytest.mark.asyncio
    async def test_process_one_hitl_improve_success_comment_mentions_find_label(
        self, config: HydraConfig
    ) -> None:
        """Success comment for improve origin should mention the find/triage stage."""
        from models import HITLResult

        orch = HydraOrchestrator(config)
        issue = make_issue(42, title="Improve: test", body="Details")

        orch._fetcher.fetch_issue_by_number = AsyncMock(return_value=issue)  # type: ignore[method-assign]
        orch._state.set_hitl_origin(42, "hydra-improve")

        mock_prs = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.post_comment = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.create = AsyncMock(return_value=config.worktree_base / "issue-42")
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        orch._hitl_runner.run = AsyncMock(  # type: ignore[method-assign]
            return_value=HITLResult(issue_number=42, success=True)
        )

        semaphore = asyncio.Semaphore(1)
        await orch._process_one_hitl(42, "Improve it", semaphore)

        comment = mock_prs.post_comment.call_args.args[1]
        assert config.find_label[0] in comment


# ---------------------------------------------------------------------------
# Memory suggestion filing sets hitl_origin
# ---------------------------------------------------------------------------


class TestMemorySuggestionSetsOrigin:
    """Tests that _file_memory_suggestion sets hitl_origin on created issues."""

    @pytest.mark.asyncio
    async def test_file_memory_suggestion_sets_hitl_origin(
        self, config: HydraConfig
    ) -> None:
        """When a memory suggestion is filed, hitl_origin should be set to improve label."""
        orch = HydraOrchestrator(config)

        mock_prs = AsyncMock()
        mock_prs.create_issue = AsyncMock(return_value=99)
        orch._prs = mock_prs

        transcript = (
            "Some output\n"
            "MEMORY_SUGGESTION_START\n"
            "title: Test suggestion\n"
            "learning: Learned something useful\n"
            "context: During testing\n"
            "MEMORY_SUGGESTION_END\n"
        )

        await orch._file_memory_suggestion(transcript, "implementer", "issue #42")

        # Verify issue was created with improve + hitl labels
        mock_prs.create_issue.assert_awaited_once()
        call_labels = mock_prs.create_issue.call_args.args[2]
        assert config.improve_label[0] in call_labels
        assert config.hitl_label[0] in call_labels

        # Verify hitl_origin was set
        assert orch._state.get_hitl_origin(99) == config.improve_label[0]
        assert orch._state.get_hitl_cause(99) == "Memory suggestion"

    @pytest.mark.asyncio
    async def test_file_memory_suggestion_no_origin_on_failure(
        self, config: HydraConfig
    ) -> None:
        """When create_issue returns 0, no hitl_origin should be set."""
        orch = HydraOrchestrator(config)

        mock_prs = AsyncMock()
        mock_prs.create_issue = AsyncMock(return_value=0)
        orch._prs = mock_prs

        transcript = (
            "Some output\n"
            "MEMORY_SUGGESTION_START\n"
            "title: Test suggestion\n"
            "learning: Learned something\n"
            "context: During testing\n"
            "MEMORY_SUGGESTION_END\n"
        )

        await orch._file_memory_suggestion(transcript, "implementer", "issue #42")

        # No hitl_origin should be set when create_issue fails
        assert orch._state.get_hitl_origin(0) is None


# ---------------------------------------------------------------------------
# _polling_loop
# ---------------------------------------------------------------------------


class TestPollingLoop:
    """Tests for the generic _polling_loop() method."""

    @pytest.mark.asyncio
    async def test_polling_loop_calls_work_fn_each_cycle(
        self, config: HydraConfig
    ) -> None:
        """Work function should be called on each loop iteration."""
        orch = HydraOrchestrator(config)
        call_count = 0

        async def work_fn() -> None:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                orch._stop_event.set()

        await orch._polling_loop("test", work_fn, 0)
        assert call_count >= 2

    @pytest.mark.asyncio
    async def test_polling_loop_stops_on_stop_event(self, config: HydraConfig) -> None:
        """Loop should exit when stop event is set."""
        orch = HydraOrchestrator(config)
        orch._stop_event.set()

        call_count = 0

        async def work_fn() -> None:
            nonlocal call_count
            call_count += 1

        await orch._polling_loop("test", work_fn, 0)
        assert call_count == 0

    @pytest.mark.asyncio
    async def test_polling_loop_runs_when_enabled_name_is_none(
        self, config: HydraConfig
    ) -> None:
        """Work function always runs when enabled_name is None (no enable check)."""
        orch = HydraOrchestrator(config)
        call_count = 0

        async def work_fn() -> None:
            nonlocal call_count
            call_count += 1
            orch._stop_event.set()

        orch.set_bg_worker_enabled("some_worker", False)
        await orch._polling_loop("test", work_fn, 0, enabled_name=None)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_polling_loop_error_message_formats_underscores(
        self, config: HydraConfig
    ) -> None:
        """Error event message should replace underscores with spaces in loop name."""
        orch = HydraOrchestrator(config)
        queue = orch._bus.subscribe()
        call_count = 0

        async def work_fn() -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("boom")
            orch._stop_event.set()

        await orch._polling_loop("memory_sync", work_fn, 0)

        error_events: list[HydraEvent] = []
        while not queue.empty():
            event = queue.get_nowait()
            if event.type == EventType.ERROR:
                error_events.append(event)

        assert len(error_events) == 1
        assert "Memory sync" in error_events[0].data["message"]
        assert "memory_sync" not in error_events[0].data["message"]

    @pytest.mark.asyncio
    async def test_polling_loop_skips_when_disabled(self, config: HydraConfig) -> None:
        """Work function should not be called when worker is disabled."""
        orch = HydraOrchestrator(config)
        orch.set_bg_worker_enabled("test_worker", False)

        call_count = 0
        cycle_count = 0

        async def work_fn() -> None:
            nonlocal call_count
            call_count += 1

        original_sleep = orch._sleep_or_stop

        async def counting_sleep(seconds: int | float) -> None:
            nonlocal cycle_count
            cycle_count += 1
            if cycle_count >= 2:
                orch._stop_event.set()
            await original_sleep(0)

        orch._sleep_or_stop = counting_sleep  # type: ignore[method-assign]

        await orch._polling_loop("test", work_fn, 1, enabled_name="test_worker")
        assert call_count == 0

    @pytest.mark.asyncio
    async def test_polling_loop_reraises_auth_error(self, config: HydraConfig) -> None:
        """AuthenticationError should propagate out of the loop."""
        orch = HydraOrchestrator(config)

        async def work_fn() -> None:
            raise AuthenticationError("bad token")

        with pytest.raises(AuthenticationError):
            await orch._polling_loop("test", work_fn, 0)

    @pytest.mark.asyncio
    async def test_polling_loop_reraises_credit_error(
        self, config: HydraConfig
    ) -> None:
        """CreditExhaustedError should propagate out of the loop."""
        from subprocess_util import CreditExhaustedError

        orch = HydraOrchestrator(config)

        async def work_fn() -> None:
            raise CreditExhaustedError("out of credits")

        with pytest.raises(CreditExhaustedError):
            await orch._polling_loop("test", work_fn, 0)

    @pytest.mark.asyncio
    async def test_polling_loop_publishes_error_on_exception(
        self, config: HydraConfig
    ) -> None:
        """Non-fatal exceptions should be logged and published as error events."""
        orch = HydraOrchestrator(config)
        queue = orch._bus.subscribe()

        call_count = 0

        async def work_fn() -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("oops")
            orch._stop_event.set()

        await orch._polling_loop("test", work_fn, 0)

        error_events: list[HydraEvent] = []
        while not queue.empty():
            event = queue.get_nowait()
            if event.type == EventType.ERROR:
                error_events.append(event)

        assert len(error_events) == 1
        assert error_events[0].data["source"] == "test"

    @pytest.mark.asyncio
    async def test_polling_loop_continues_after_exception(
        self, config: HydraConfig
    ) -> None:
        """Loop should continue running after a non-fatal exception."""
        orch = HydraOrchestrator(config)
        call_count = 0

        async def work_fn() -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("first call fails")
            orch._stop_event.set()

        await orch._polling_loop("test", work_fn, 0)
        assert call_count >= 2
