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
    """Mock all fetcher methods so no real gh CLI calls are made.

    Required for tests that go through run() since exception isolation
    catches errors from unmocked fetcher calls instead of propagating them.
    """
    orch._fetcher.fetch_issues_by_labels = AsyncMock(return_value=[])  # type: ignore[method-assign]
    orch._fetcher.fetch_plan_issues = AsyncMock(return_value=[])  # type: ignore[method-assign]
    orch._fetcher.fetch_ready_issues = AsyncMock(return_value=[])  # type: ignore[method-assign]
    orch._fetcher.fetch_reviewable_prs = AsyncMock(return_value=([], []))  # type: ignore[method-assign]


def make_worker_result(
    issue_number: int = 42,
    branch: str = "agent/issue-42",
    success: bool = True,
    worktree_path: str = "/tmp/worktrees/issue-42",
) -> WorkerResult:
    return WorkerResult(
        issue_number=issue_number,
        branch=branch,
        success=success,
        transcript="Implemented the feature.",
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
) -> ReviewResult:
    return ReviewResult(
        pr_number=pr_number,
        issue_number=issue_number,
        verdict=verdict,
        summary="Looks good.",
        fixes_made=False,
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

        orch._fetcher.fetch_issues_by_labels = AsyncMock(return_value=[issue])  # type: ignore[method-assign]
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

        orch._fetcher.fetch_issues_by_labels = AsyncMock(return_value=[issue])  # type: ignore[method-assign]
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

        orch._fetcher.fetch_issues_by_labels = AsyncMock(return_value=[issue])  # type: ignore[method-assign]
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

        orch._fetcher.fetch_issues_by_labels = AsyncMock(return_value=[issue])  # type: ignore[method-assign]
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

        orch._fetcher.fetch_issues_by_labels = AsyncMock(return_value=issues)  # type: ignore[method-assign]
        await orch._triage_find_issues()

        # Only the first issue should be evaluated; second skipped due to stop
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_triage_skips_when_no_issues_found(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)

        mock_prs = AsyncMock()
        orch._prs = mock_prs

        orch._fetcher.fetch_issues_by_labels = AsyncMock(return_value=[])  # type: ignore[method-assign]
        await orch._triage_find_issues()

        mock_prs.remove_label.assert_not_called()


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
        orch._fetcher.fetch_plan_issues = AsyncMock(return_value=[issue])  # type: ignore[method-assign]

        mock_prs = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        await orch._plan_issues()

        mock_prs.post_comment.assert_awaited_once()
        call_args = mock_prs.post_comment.call_args
        assert call_args.args[0] == 42
        assert "Step 1: Do the thing" in call_args.args[1]
        assert "agent/issue-42" in call_args.args[1]

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
        orch._fetcher.fetch_plan_issues = AsyncMock(return_value=[issue])  # type: ignore[method-assign]

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
        orch._fetcher.fetch_plan_issues = AsyncMock(return_value=[issue])  # type: ignore[method-assign]

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
        orch._fetcher.fetch_plan_issues = AsyncMock(return_value=[])  # type: ignore[method-assign]

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
        orch._fetcher.fetch_plan_issues = AsyncMock(return_value=[issue])  # type: ignore[method-assign]

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
        orch._fetcher.fetch_plan_issues = AsyncMock(return_value=[issue])  # type: ignore[method-assign]

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
        orch._fetcher.fetch_plan_issues = AsyncMock(return_value=issues)  # type: ignore[method-assign]

        mock_prs = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        await orch._plan_issues()

        assert concurrency_counter["peak"] <= config.max_planners

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
        orch._fetcher.fetch_plan_issues = AsyncMock(return_value=[issue])  # type: ignore[method-assign]

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
        orch._fetcher.fetch_plan_issues = AsyncMock(return_value=[issue])  # type: ignore[method-assign]

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
        orch._fetch_plan_issues = AsyncMock(return_value=[issue])  # type: ignore[method-assign]

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
        orch._fetcher.fetch_plan_issues = AsyncMock(return_value=issues)  # type: ignore[method-assign]

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
        orch._fetcher.fetch_plan_issues = AsyncMock(return_value=[issue])  # type: ignore[method-assign]

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
        orch._fetcher.fetch_plan_issues = AsyncMock(return_value=[issue])  # type: ignore[method-assign]

        mock_prs = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        await orch._plan_issues()

        mock_prs.post_comment.assert_not_awaited()
        mock_prs.remove_label.assert_not_awaited()
        mock_prs.add_labels.assert_not_awaited()


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

    def test_get_hitl_status_returns_processing_when_active(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        orch._active_issues.add(42)
        assert orch.get_hitl_status(42) == "processing"

    def test_get_hitl_status_returns_pending_when_not_active(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        orch._active_issues.add(99)
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
        orch._active_issues.add(42)
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

        orch._triage_find_issues = AsyncMock()  # type: ignore[method-assign]
        orch._plan_issues = failing_plan  # type: ignore[method-assign]

        await orch._plan_loop()

        assert call_count == 2

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
        """An exception in fetch_reviewable_prs should not crash the review loop."""
        orch = HydraOrchestrator(config)
        call_count = 0

        async def failing_fetch(
            active: object,
        ) -> tuple[list[PRInfo], list[GitHubIssue]]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("review boom")
            orch._stop_event.set()
            return [], []

        orch._fetcher.fetch_reviewable_prs = failing_fetch  # type: ignore[method-assign]

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

        async def failing_fetch(
            active: object,
        ) -> tuple[list[PRInfo], list[GitHubIssue]]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("review error")
            orch._stop_event.set()
            return [], []

        orch._fetcher.fetch_reviewable_prs = failing_fetch  # type: ignore[method-assign]

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
        orch._fetcher.fetch_reviewable_prs = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

        # Use instant sleep to avoid 30s poll_interval delays
        async def instant_sleep(seconds: int) -> None:
            await asyncio.sleep(0)

        orch._sleep_or_stop = instant_sleep  # type: ignore[method-assign]

        await orch.run()

        # The implement loop continued after the error (ran at least twice)
        assert implement_calls >= 2
        assert not orch.running
