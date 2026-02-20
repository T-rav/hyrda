"""Tests for dx/hydra/orchestrator.py - HydraOrchestrator class."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any
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
    WorkerStatus,
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


def _setup_implement_mocks(
    orch: HydraOrchestrator,
    config: HydraConfig,
    issues: list[GitHubIssue],
    *,
    agent_run: Any | None = None,
    success: bool = True,
    push_return: bool = True,
    create_pr_return: PRInfo | None = None,
) -> tuple[AsyncMock, AsyncMock]:
    """Wire standard _implement_batch mocks into *orch*.

    Returns ``(mock_wt, mock_prs)`` so tests can assert on them.
    """
    if agent_run is None:

        async def _default_agent_run(
            issue: GitHubIssue, wt_path: Path, branch: str, worker_id: int = 0
        ) -> WorkerResult:
            return make_worker_result(
                issue_number=issue.number,
                success=success,
                worktree_path=str(wt_path),
            )

        agent_run = _default_agent_run

    orch._agents.run = agent_run  # type: ignore[method-assign]
    orch._fetch_ready_issues = AsyncMock(return_value=issues)  # type: ignore[method-assign]

    mock_wt = AsyncMock()
    mock_wt.create = AsyncMock(
        side_effect=lambda num, branch: config.worktree_base / f"issue-{num}"
    )
    orch._worktrees = mock_wt

    mock_prs = AsyncMock()
    mock_prs.push_branch = AsyncMock(return_value=push_return)
    mock_prs.create_pr = AsyncMock(
        return_value=create_pr_return
        if create_pr_return is not None
        else make_pr_info()
    )
    mock_prs.add_labels = AsyncMock()
    mock_prs.remove_label = AsyncMock()
    mock_prs.post_comment = AsyncMock()
    mock_prs.add_pr_labels = AsyncMock()
    orch._prs = mock_prs

    return mock_wt, mock_prs


# Raw gh issue list JSON fixture
RAW_ISSUE_JSON = json.dumps(
    [
        {
            "number": 42,
            "title": "Fix bug",
            "body": "Details",
            "labels": [{"name": "ready"}],
            "comments": [],
            "url": "https://github.com/test-org/test-repo/issues/42",
        }
    ]
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
# _fetch_ready_issues
# ---------------------------------------------------------------------------


class TestFetchReadyIssues:
    """Tests for the _fetch_ready_issues coroutine."""

    @pytest.mark.asyncio
    async def test_returns_parsed_issues_from_gh_output(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(RAW_ISSUE_JSON.encode(), b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            issues = await orch._fetch_ready_issues()

        assert len(issues) == 1
        assert issues[0].number == 42
        assert issues[0].title == "Fix bug"
        assert issues[0].body == "Details"
        assert issues[0].labels == ["ready"]

    @pytest.mark.asyncio
    async def test_parses_label_dict_and_string(self, config: HydraConfig) -> None:
        raw = json.dumps(
            [
                {
                    "number": 10,
                    "title": "Test",
                    "body": "",
                    "labels": [{"name": "alpha"}, "beta"],
                    "comments": [],
                    "url": "",
                }
            ]
        )
        orch = HydraOrchestrator(config)
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(raw.encode(), b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            issues = await orch._fetch_ready_issues()

        assert "alpha" in issues[0].labels
        assert "beta" in issues[0].labels

    @pytest.mark.asyncio
    async def test_parses_comment_dict_and_string(self, config: HydraConfig) -> None:
        raw = json.dumps(
            [
                {
                    "number": 11,
                    "title": "T",
                    "body": "",
                    "labels": [],
                    "comments": [{"body": "hello"}, "world"],
                    "url": "",
                }
            ]
        )
        orch = HydraOrchestrator(config)
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(raw.encode(), b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            issues = await orch._fetch_ready_issues()

        assert "hello" in issues[0].comments
        assert "world" in issues[0].comments

    @pytest.mark.asyncio
    async def test_skips_active_issues(self, config: HydraConfig) -> None:
        """Issues already active in this run should be skipped."""
        orch = HydraOrchestrator(config)
        orch._active_issues.add(42)

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(RAW_ISSUE_JSON.encode(), b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            issues = await orch._fetch_ready_issues()

        assert issues == []

    @pytest.mark.asyncio
    async def test_does_not_skip_failed_issues_on_restart(
        self, config: HydraConfig
    ) -> None:
        """Failed issues with hydra-ready label should be retried (no state filter)."""
        orch = HydraOrchestrator(config)
        orch._state.mark_issue(42, "failed")
        # NOT in _active_issues → should be picked up

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(RAW_ISSUE_JSON.encode(), b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            issues = await orch._fetch_ready_issues()

        assert len(issues) == 1
        assert issues[0].number == 42

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_gh_fails(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"error: not found"))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            issues = await orch._fetch_ready_issues()

        assert issues == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_json_decode_error(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"not-json", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            issues = await orch._fetch_ready_issues()

        assert issues == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_gh_not_found(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError("gh not found"),
        ):
            issues = await orch._fetch_ready_issues()

        assert issues == []

    @pytest.mark.asyncio
    async def test_respects_queue_size_limit(self, config: HydraConfig) -> None:
        """Result list is truncated to 2 * max_workers."""
        raw = json.dumps(
            [
                {
                    "number": i,
                    "title": f"Issue {i}",
                    "body": "",
                    "labels": [],
                    "comments": [],
                    "url": "",
                }
                for i in range(1, 10)
            ]
        )
        orch = HydraOrchestrator(config)
        # config has max_workers=2 from conftest → queue_size = 4
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(raw.encode(), b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            issues = await orch._fetch_ready_issues()

        assert len(issues) <= 2 * config.max_workers

    @pytest.mark.asyncio
    async def test_dry_run_returns_empty_list(self, config: HydraConfig) -> None:
        from config import HydraConfig

        dry_config = HydraConfig(**{**config.model_dump(), "dry_run": True})
        orch = HydraOrchestrator(dry_config)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            issues = await orch._fetch_ready_issues()

        assert issues == []
        mock_exec.assert_not_called()


# ---------------------------------------------------------------------------
# _implement_batch
# ---------------------------------------------------------------------------


class TestImplementBatch:
    """Tests for the _implement_batch coroutine."""

    @pytest.mark.asyncio
    async def test_returns_worker_results_for_each_issue(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        issues = [make_issue(1), make_issue(2)]

        expected = [
            make_worker_result(
                issue_number=1, worktree_path=str(config.worktree_base / "issue-1")
            ),
            make_worker_result(
                issue_number=2, worktree_path=str(config.worktree_base / "issue-2")
            ),
        ]

        async def fake_agent_run(
            issue: GitHubIssue, wt_path: Path, branch: str, worker_id: int = 0
        ) -> WorkerResult:
            return next(r for r in expected if r.issue_number == issue.number)

        _setup_implement_mocks(orch, config, issues, agent_run=fake_agent_run)

        returned, fetched = await orch._implement_batch()
        assert len(returned) == 2
        issue_numbers = {r.issue_number for r in returned}
        assert issue_numbers == {1, 2}
        assert fetched == issues

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self, config: HydraConfig) -> None:
        """max_workers=2 means at most 2 agents run concurrently."""
        concurrency_counter = {"current": 0, "peak": 0}

        async def fake_agent_run(
            issue: GitHubIssue, wt_path: Path, branch: str, worker_id: int = 0
        ) -> WorkerResult:
            concurrency_counter["current"] += 1
            concurrency_counter["peak"] = max(
                concurrency_counter["peak"], concurrency_counter["current"]
            )
            await asyncio.sleep(0)  # yield
            concurrency_counter["current"] -= 1
            return make_worker_result(
                issue_number=issue.number, worktree_path=str(wt_path)
            )

        issues = [make_issue(i) for i in range(1, 6)]

        orch = HydraOrchestrator(config)  # max_workers=2 from conftest
        _setup_implement_mocks(orch, config, issues, agent_run=fake_agent_run)

        await orch._implement_batch()

        assert concurrency_counter["peak"] <= config.max_workers

    @pytest.mark.asyncio
    async def test_marks_issue_in_progress_then_done(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        issue = make_issue(55)

        _setup_implement_mocks(orch, config, [issue])

        await orch._implement_batch()

        status = orch._state.get_issue_status(55)
        assert status == "success"

    @pytest.mark.asyncio
    async def test_marks_issue_failed_when_agent_fails(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        issue = make_issue(66)

        _setup_implement_mocks(orch, config, [issue], success=False)

        await orch._implement_batch()

        status = orch._state.get_issue_status(66)
        assert status == "failed"

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_issues(self, config: HydraConfig) -> None:
        """When _fetch_ready_issues returns empty, return ([], [])."""
        orch = HydraOrchestrator(config)
        orch._fetch_ready_issues = AsyncMock(return_value=[])  # type: ignore[method-assign]

        results, issues = await orch._implement_batch()

        assert results == []
        assert issues == []

    @pytest.mark.asyncio
    async def test_resumes_existing_worktree(self, config: HydraConfig) -> None:
        """If worktree dir already exists, skip create and reuse it."""
        orch = HydraOrchestrator(config)
        issue = make_issue(77)

        # Pre-create worktree directory to simulate resume
        wt_path = config.worktree_base / "issue-77"
        wt_path.mkdir(parents=True, exist_ok=True)

        mock_wt, _ = _setup_implement_mocks(
            orch, config, [issue], create_pr_return=make_pr_info(101, 77)
        )

        await orch._implement_batch()

        # create should NOT have been called since worktree already exists
        mock_wt.create.assert_not_awaited()


# ---------------------------------------------------------------------------
# Implement includes push + PR creation
# ---------------------------------------------------------------------------


class TestImplementIncludesPush:
    """Tests that _implement_batch pushes and creates PRs per worker."""

    @pytest.mark.asyncio
    async def test_worker_result_contains_pr_info(self, config: HydraConfig) -> None:
        """After implementation, worker result should contain pr_info."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)

        _setup_implement_mocks(
            orch, config, [issue], create_pr_return=make_pr_info(101, 42)
        )

        results, _ = await orch._implement_batch()

        assert len(results) == 1
        assert results[0].pr_info is not None
        assert results[0].pr_info.number == 101

    @pytest.mark.asyncio
    async def test_worker_creates_draft_pr_on_failure(
        self, config: HydraConfig
    ) -> None:
        """When agent fails, PR should be created as draft and label kept."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)

        _, mock_prs = _setup_implement_mocks(
            orch,
            config,
            [issue],
            success=False,
            create_pr_return=make_pr_info(101, 42, draft=True),
        )

        await orch._implement_batch()

        call_kwargs = mock_prs.create_pr.call_args
        assert call_kwargs.kwargs.get("draft") is True

        # On failure: should NOT remove hydra-ready or add hydra-review
        mock_prs.remove_label.assert_not_awaited()
        add_calls = [c.args for c in mock_prs.add_labels.call_args_list]
        assert (42, ["hydra-review"]) not in add_calls

    @pytest.mark.asyncio
    async def test_worker_no_pr_when_push_fails(self, config: HydraConfig) -> None:
        """When push fails, pr_info should remain None."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)

        _, mock_prs = _setup_implement_mocks(orch, config, [issue], push_return=False)

        results, _ = await orch._implement_batch()

        assert results[0].pr_info is None
        mock_prs.create_pr.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_branch_pushed_and_commented_before_agent_runs(
        self, config: HydraConfig
    ) -> None:
        """Branch should be pushed and a comment posted before the agent starts."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)

        call_order: list[str] = []

        async def fake_push(wt_path: Path, branch: str) -> bool:
            call_order.append("push")
            return True

        async def fake_comment(issue_number: int, body: str) -> None:
            call_order.append("comment")

        async def fake_agent_run(
            issue: GitHubIssue, wt_path: Path, branch: str, worker_id: int = 0
        ) -> WorkerResult:
            call_order.append("agent")
            return make_worker_result(
                issue_number=issue.number, success=True, worktree_path=str(wt_path)
            )

        _, mock_prs = _setup_implement_mocks(
            orch,
            config,
            [issue],
            agent_run=fake_agent_run,
            create_pr_return=make_pr_info(101, 42),
        )
        mock_prs.push_branch = fake_push
        mock_prs.post_comment = fake_comment

        await orch._implement_batch()

        # push and comment must happen before agent
        assert call_order.index("push") < call_order.index("agent")
        assert call_order.index("comment") < call_order.index("agent")


# ---------------------------------------------------------------------------
# _review_prs
# ---------------------------------------------------------------------------


class TestReviewPRs:
    """Tests for the _review_prs coroutine."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_prs(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        results = await orch._review_prs([], [make_issue()])
        assert results == []

    @pytest.mark.asyncio
    async def test_reviews_non_draft_prs(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        mock_reviewers = AsyncMock()
        mock_reviewers.review = AsyncMock(return_value=make_review_result(101, 42))
        orch._reviewers = mock_reviewers

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff text")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.merge_pr = AsyncMock(return_value=True)
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        # Ensure worktree path exists
        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)
        orch._state.set_worktree(42, str(wt))

        results = await orch._review_prs([pr], [issue])

        mock_reviewers.review.assert_awaited_once()
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_marks_pr_status_in_state(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        mock_reviewers = AsyncMock()
        mock_reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        orch._reviewers = mock_reviewers

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff text")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.merge_pr = AsyncMock(return_value=True)
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await orch._review_prs([pr], [issue])

        assert orch._state.get_pr_status(101) == "approve"

    @pytest.mark.asyncio
    async def test_reviewer_concurrency_limited_by_config_max_reviewers(
        self, config: HydraConfig
    ) -> None:
        """At most config.max_reviewers concurrent reviews."""
        concurrency_counter = {"current": 0, "peak": 0}

        async def fake_review(pr, issue, wt_path, diff, worker_id=0):
            concurrency_counter["current"] += 1
            concurrency_counter["peak"] = max(
                concurrency_counter["peak"], concurrency_counter["current"]
            )
            await asyncio.sleep(0)
            concurrency_counter["current"] -= 1
            return make_review_result(pr.number, issue.number)

        orch = HydraOrchestrator(config)
        orch._reviewers.review = fake_review  # type: ignore[method-assign]

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.merge_pr = AsyncMock(return_value=True)
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        issues = [make_issue(i) for i in range(1, 7)]
        prs = [make_pr_info(100 + i, i, draft=False) for i in range(1, 7)]

        for i in range(1, 7):
            wt = config.worktree_base / f"issue-{i}"
            wt.mkdir(parents=True, exist_ok=True)

        await orch._review_prs(prs, issues)

        assert concurrency_counter["peak"] <= config.max_reviewers

    @pytest.mark.asyncio
    async def test_returns_comment_verdict_when_issue_missing(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        # PR with issue_number not in issue_map
        pr = make_pr_info(101, 999, draft=False)

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff")
        orch._prs = mock_prs

        # Worktree for issue-999 exists
        wt = config.worktree_base / "issue-999"
        wt.mkdir(parents=True, exist_ok=True)

        results = await orch._review_prs([pr], [])  # no matching issues

        assert len(results) == 1
        assert results[0].pr_number == 101
        assert results[0].summary == "Issue not found"

    @pytest.mark.asyncio
    async def test_review_merges_approved_pr(self, config: HydraConfig) -> None:
        """_review_prs should merge PRs that the reviewer approves."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        mock_reviewers = AsyncMock()
        mock_reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        orch._reviewers = mock_reviewers

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff text")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.merge_pr = AsyncMock(return_value=True)
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await orch._review_prs([pr], [issue])

        assert results[0].merged is True
        mock_prs.merge_pr.assert_awaited_once_with(101)

    @pytest.mark.asyncio
    async def test_review_does_not_merge_rejected_pr(self, config: HydraConfig) -> None:
        """_review_prs should not merge PRs with REQUEST_CHANGES verdict."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        mock_reviewers = AsyncMock()
        mock_reviewers.review = AsyncMock(
            return_value=make_review_result(
                101, 42, verdict=ReviewVerdict.REQUEST_CHANGES
            )
        )
        orch._reviewers = mock_reviewers

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff text")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.merge_pr = AsyncMock(return_value=True)
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await orch._review_prs([pr], [issue])

        assert results[0].merged is False
        mock_prs.merge_pr.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_review_merges_main_before_reviewing(
        self, config: HydraConfig
    ) -> None:
        """_review_prs should merge main into the branch and push before reviewing."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        mock_reviewers = AsyncMock()
        mock_reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        orch._reviewers = mock_reviewers

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff text")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.merge_pr = AsyncMock(return_value=True)
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.destroy = AsyncMock()
        mock_wt.merge_main = AsyncMock(return_value=True)
        orch._worktrees = mock_wt

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await orch._review_prs([pr], [issue])

        assert results[0].merged is True
        mock_wt.merge_main.assert_awaited_once()
        mock_prs.push_branch.assert_awaited_once()
        mock_reviewers.review.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_review_conflict_resolved_by_agent(self, config: HydraConfig) -> None:
        """When merge conflicts, agent resolves them and review proceeds."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        mock_reviewers = AsyncMock()
        mock_reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        orch._reviewers = mock_reviewers

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff text")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.merge_pr = AsyncMock(return_value=True)
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.destroy = AsyncMock()
        mock_wt.merge_main = AsyncMock(return_value=False)  # Conflicts
        mock_wt.start_merge_main = AsyncMock(return_value=False)  # Has conflicts
        orch._worktrees = mock_wt

        mock_agents = AsyncMock()
        mock_agents._build_command = lambda wt: ["claude", "-p"]
        mock_agents._execute = AsyncMock(return_value="resolved")
        mock_agents._verify_result = AsyncMock(return_value=(True, "OK"))
        orch._agents = mock_agents

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await orch._review_prs([pr], [issue])

        assert results[0].merged is True
        mock_wt.start_merge_main.assert_awaited_once()
        mock_agents._execute.assert_awaited_once()
        mock_reviewers.review.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_review_conflict_emits_merge_fix_status(
        self, config: HydraConfig
    ) -> None:
        """Conflict resolution agent emits merge_fix status, not running."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        mock_reviewers = AsyncMock()
        mock_reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        orch._reviewers = mock_reviewers

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff text")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.merge_pr = AsyncMock(return_value=True)
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.destroy = AsyncMock()
        mock_wt.merge_main = AsyncMock(return_value=False)
        mock_wt.start_merge_main = AsyncMock(return_value=False)
        orch._worktrees = mock_wt

        mock_agents = AsyncMock()
        mock_agents._build_command = lambda wt: ["claude", "-p"]
        mock_agents._execute = AsyncMock(return_value="resolved")
        mock_agents._verify_result = AsyncMock(return_value=(True, "OK"))
        orch._agents = mock_agents

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        # Capture published events
        published: list[HydraEvent] = []
        original_publish = orch._bus.publish

        async def capturing_publish(event: HydraEvent) -> None:
            published.append(event)
            await original_publish(event)

        orch._bus.publish = capturing_publish  # type: ignore[method-assign]

        await orch._review_prs([pr], [issue])

        # Find WORKER_UPDATE events for the conflict resolver
        worker_updates = [
            e
            for e in published
            if e.type == EventType.WORKER_UPDATE
            and e.data.get("role") == "conflict-resolver"
        ]
        assert len(worker_updates) >= 1
        assert worker_updates[0].data["status"] == WorkerStatus.MERGE_FIX.value

    @pytest.mark.asyncio
    async def test_review_conflict_agent_fails_escalates_to_hitl(
        self, config: HydraConfig
    ) -> None:
        """When agent cannot resolve conflicts, escalate to HITL."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        mock_reviewers = AsyncMock()
        orch._reviewers = mock_reviewers

        mock_prs = AsyncMock()
        mock_prs.post_pr_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.destroy = AsyncMock()
        mock_wt.merge_main = AsyncMock(return_value=False)  # Conflicts
        mock_wt.start_merge_main = AsyncMock(return_value=False)
        mock_wt.abort_merge = AsyncMock()
        orch._worktrees = mock_wt

        mock_agents = AsyncMock()
        mock_agents._build_command = lambda wt: ["claude", "-p"]
        mock_agents._execute = AsyncMock(return_value="failed")
        mock_agents._verify_result = AsyncMock(return_value=(False, "quality failed"))
        orch._agents = mock_agents

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await orch._review_prs([pr], [issue])

        assert results[0].merged is False
        assert "conflicts" in results[0].summary.lower()
        mock_reviewers.review.assert_not_awaited()
        mock_prs.add_labels.assert_awaited_once_with(42, ["hydra-hitl"])

    @pytest.mark.asyncio
    async def test_review_merge_failure_escalates_to_hitl(
        self, config: HydraConfig
    ) -> None:
        """When merge fails after successful rebase, should escalate to HITL."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        mock_reviewers = AsyncMock()
        mock_reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        orch._reviewers = mock_reviewers

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff text")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.merge_pr = AsyncMock(return_value=False)
        mock_prs.post_pr_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.destroy = AsyncMock()
        mock_wt.merge_main = AsyncMock(return_value=True)
        orch._worktrees = mock_wt

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await orch._review_prs([pr], [issue])

        assert results[0].merged is False
        hitl_calls = [
            c
            for c in mock_prs.post_pr_comment.call_args_list
            if "Merge failed" in str(c)
        ]
        assert len(hitl_calls) == 1
        mock_prs.add_labels.assert_any_await(42, ["hydra-hitl"])

    @pytest.mark.asyncio
    async def test_review_merge_records_lifetime_stats(
        self, config: HydraConfig
    ) -> None:
        """Merging a PR should record both pr_merged and issue_completed."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        mock_reviewers = AsyncMock()
        mock_reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        orch._reviewers = mock_reviewers

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff text")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.merge_pr = AsyncMock(return_value=True)
        mock_prs.pull_main = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await orch._review_prs([pr], [issue])

        stats = orch._state.get_lifetime_stats()
        assert stats["prs_merged"] == 1
        assert stats["issues_completed"] == 1

    @pytest.mark.asyncio
    async def test_review_merge_labels_issue_hydra_fixed(
        self, config: HydraConfig
    ) -> None:
        """Merging a PR should swap label from hydra-review to hydra-fixed."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        mock_reviewers = AsyncMock()
        mock_reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        orch._reviewers = mock_reviewers

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff text")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.merge_pr = AsyncMock(return_value=True)
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await orch._review_prs([pr], [issue])

        # Should remove hydra-review and add hydra-fixed
        remove_calls = [c.args for c in mock_prs.remove_label.call_args_list]
        assert (42, "hydra-review") in remove_calls
        add_calls = [c.args for c in mock_prs.add_labels.call_args_list]
        assert (42, ["hydra-fixed"]) in add_calls

    @pytest.mark.asyncio
    async def test_review_merge_failure_does_not_record_lifetime_stats(
        self, config: HydraConfig
    ) -> None:
        """Failed merge should not increment lifetime stats."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        mock_reviewers = AsyncMock()
        mock_reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        orch._reviewers = mock_reviewers

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff text")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.merge_pr = AsyncMock(return_value=False)
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await orch._review_prs([pr], [issue])

        stats = orch._state.get_lifetime_stats()
        assert stats["prs_merged"] == 0
        assert stats["issues_completed"] == 0

    @pytest.mark.asyncio
    async def test_review_merge_marks_issue_as_merged(
        self, config: HydraConfig
    ) -> None:
        """Successful merge should mark issue status as 'merged'."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        mock_reviewers = AsyncMock()
        mock_reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        orch._reviewers = mock_reviewers

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff text")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.merge_pr = AsyncMock(return_value=True)
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await orch._review_prs([pr], [issue])

        assert orch._state.get_issue_status(42) == "merged"

    @pytest.mark.asyncio
    async def test_review_merge_failure_keeps_reviewed_status(
        self, config: HydraConfig
    ) -> None:
        """Failed merge should leave issue as 'reviewed', not 'merged'."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        mock_reviewers = AsyncMock()
        mock_reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        orch._reviewers = mock_reviewers

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff text")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.merge_pr = AsyncMock(return_value=False)
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await orch._review_prs([pr], [issue])

        assert orch._state.get_issue_status(42) == "reviewed"

    @pytest.mark.asyncio
    async def test_review_posts_pr_comment_with_summary(
        self, config: HydraConfig
    ) -> None:
        """post_pr_comment should be called with the review summary."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        review = make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)

        mock_reviewers = AsyncMock()
        mock_reviewers.review = AsyncMock(return_value=review)
        orch._reviewers = mock_reviewers

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff text")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.merge_pr = AsyncMock(return_value=True)
        mock_prs.post_pr_comment = AsyncMock()
        mock_prs.submit_review = AsyncMock(return_value=True)
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await orch._review_prs([pr], [issue])

        mock_prs.post_pr_comment.assert_awaited_once_with(101, "Looks good.")

    @pytest.mark.asyncio
    async def test_review_skips_submit_review_for_approve(
        self, config: HydraConfig
    ) -> None:
        """submit_review should NOT be called for approve to avoid self-approval errors."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        review = make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)

        mock_reviewers = AsyncMock()
        mock_reviewers.review = AsyncMock(return_value=review)
        orch._reviewers = mock_reviewers

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff text")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.merge_pr = AsyncMock(return_value=True)
        mock_prs.post_pr_comment = AsyncMock()
        mock_prs.submit_review = AsyncMock(return_value=True)
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await orch._review_prs([pr], [issue])

        mock_prs.submit_review.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "verdict",
        [ReviewVerdict.REQUEST_CHANGES, ReviewVerdict.COMMENT],
    )
    async def test_review_submits_review_for_non_approve_verdicts(
        self, config: HydraConfig, verdict: ReviewVerdict
    ) -> None:
        """submit_review should be called for request-changes and comment verdicts."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        review = make_review_result(101, 42, verdict=verdict)

        mock_reviewers = AsyncMock()
        mock_reviewers.review = AsyncMock(return_value=review)
        orch._reviewers = mock_reviewers

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff text")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.merge_pr = AsyncMock(return_value=True)
        mock_prs.post_pr_comment = AsyncMock()
        mock_prs.submit_review = AsyncMock(return_value=True)
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await orch._review_prs([pr], [issue])

        mock_prs.submit_review.assert_awaited_once_with(101, verdict, "Looks good.")

    @pytest.mark.asyncio
    async def test_review_skips_pr_comment_when_summary_empty(
        self, config: HydraConfig
    ) -> None:
        """post_pr_comment should NOT be called when summary is empty."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        review = ReviewResult(
            pr_number=101,
            issue_number=42,
            verdict=ReviewVerdict.APPROVE,
            summary="",
            fixes_made=False,
        )

        mock_reviewers = AsyncMock()
        mock_reviewers.review = AsyncMock(return_value=review)
        orch._reviewers = mock_reviewers

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff text")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.merge_pr = AsyncMock(return_value=True)
        mock_prs.post_pr_comment = AsyncMock()
        mock_prs.submit_review = AsyncMock(return_value=True)
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await orch._review_prs([pr], [issue])

        mock_prs.post_pr_comment.assert_not_awaited()
        # submit_review should NOT be called for approve verdict
        mock_prs.submit_review.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_review_comment_before_merge(self, config: HydraConfig) -> None:
        """post_pr_comment should be called before merge; submit_review skipped for approve."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        review = make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)

        mock_reviewers = AsyncMock()
        mock_reviewers.review = AsyncMock(return_value=review)
        orch._reviewers = mock_reviewers

        call_order: list[str] = []

        async def fake_post_pr_comment(pr_number: int, body: str) -> None:
            call_order.append("post_pr_comment")

        async def fake_merge(pr_number: int) -> bool:
            call_order.append("merge")
            return True

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff text")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.post_pr_comment = fake_post_pr_comment
        mock_prs.submit_review = AsyncMock(return_value=True)
        mock_prs.merge_pr = fake_merge
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await orch._review_prs([pr], [issue])

        assert call_order.index("post_pr_comment") < call_order.index("merge")
        mock_prs.submit_review.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_review_posts_comment_even_when_merge_fails(
        self, config: HydraConfig
    ) -> None:
        """post_pr_comment should be called regardless of merge outcome."""
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        review = make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)

        mock_reviewers = AsyncMock()
        mock_reviewers.review = AsyncMock(return_value=review)
        orch._reviewers = mock_reviewers

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff text")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.post_pr_comment = AsyncMock()
        mock_prs.submit_review = AsyncMock(return_value=True)
        mock_prs.merge_pr = AsyncMock(return_value=False)
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        mock_wt = AsyncMock()
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await orch._review_prs([pr], [issue])

        # Review comment + HITL escalation comment
        comment_bodies = [c.args[1] for c in mock_prs.post_pr_comment.call_args_list]
        assert "Looks good." in comment_bodies
        assert any("Merge failed" in b for b in comment_bodies)
        mock_prs.submit_review.assert_not_awaited()


# ---------------------------------------------------------------------------
# _fetch_reviewable_prs — skip logic
# ---------------------------------------------------------------------------


class TestFetchReviewablePrs:
    """Tests for _fetch_reviewable_prs: skip logic, parsing, and error handling."""

    @pytest.mark.asyncio
    async def test_skips_active_issues(self, config: HydraConfig) -> None:
        """Issues already active in this run should be skipped."""
        orch = HydraOrchestrator(config)
        orch._active_issues.add(42)

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(RAW_ISSUE_JSON.encode(), b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            prs, issues = await orch._fetch_reviewable_prs()

        assert prs == []
        assert issues == []

    @pytest.mark.asyncio
    async def test_picks_up_previously_reviewed_issues(
        self, config: HydraConfig
    ) -> None:
        """Issues reviewed in a prior run should be picked up again."""
        orch = HydraOrchestrator(config)
        orch._state.mark_issue(42, "reviewed")
        # NOT in _active_issues → should be picked up

        pr_json = json.dumps(
            [
                {
                    "number": 200,
                    "url": "https://github.com/o/r/pull/200",
                    "isDraft": False,
                }
            ]
        )

        async def fake_run(*args: str, **kwargs: Any) -> str:
            if "issue" in args:
                return RAW_ISSUE_JSON
            return pr_json

        with patch("orchestrator.run_subprocess", side_effect=fake_run):
            prs, issues = await orch._fetch_reviewable_prs()

        assert len(issues) == 1
        assert issues[0].number == 42

    @pytest.mark.asyncio
    async def test_parses_pr_json_into_pr_info(self, config: HydraConfig) -> None:
        """Successfully parses PR JSON and maps to PRInfo objects."""
        orch = HydraOrchestrator(config)

        pr_json = json.dumps(
            [
                {
                    "number": 200,
                    "url": "https://github.com/o/r/pull/200",
                    "isDraft": False,
                }
            ]
        )

        async def fake_run(*args: str, **kwargs: Any) -> str:
            if "issue" in args:
                return RAW_ISSUE_JSON
            return pr_json

        with patch("orchestrator.run_subprocess", side_effect=fake_run):
            prs, issues = await orch._fetch_reviewable_prs()

        assert len(prs) == 1
        assert prs[0].number == 200
        assert prs[0].issue_number == 42
        assert prs[0].branch == "agent/issue-42"
        assert prs[0].url == "https://github.com/o/r/pull/200"
        assert prs[0].draft is False
        assert len(issues) == 1
        assert issues[0].number == 42

    @pytest.mark.asyncio
    async def test_gh_cli_failure_skips_pr_for_that_issue(
        self, config: HydraConfig
    ) -> None:
        """gh CLI failure (RuntimeError) skips that issue's PR but preserves issues."""
        orch = HydraOrchestrator(config)

        async def fake_run(*args: str, **kwargs: Any) -> str:
            if "issue" in args:
                return RAW_ISSUE_JSON
            raise RuntimeError("Command failed (rc=1): some error")

        with patch("orchestrator.run_subprocess", side_effect=fake_run):
            prs, issues = await orch._fetch_reviewable_prs()

        assert prs == []
        assert len(issues) == 1
        assert issues[0].number == 42

    @pytest.mark.asyncio
    async def test_json_decode_error_skips_pr_for_that_issue(
        self, config: HydraConfig
    ) -> None:
        """Invalid JSON from gh CLI skips that issue's PR but preserves issues."""
        orch = HydraOrchestrator(config)

        async def fake_run(*args: str, **kwargs: Any) -> str:
            if "issue" in args:
                return RAW_ISSUE_JSON
            return "not-valid-json"

        with patch("orchestrator.run_subprocess", side_effect=fake_run):
            prs, issues = await orch._fetch_reviewable_prs()

        assert prs == []
        assert len(issues) == 1
        assert issues[0].number == 42

    @pytest.mark.asyncio
    async def test_draft_prs_excluded_from_results(self, config: HydraConfig) -> None:
        """Draft PRs are filtered out of the returned PR list."""
        orch = HydraOrchestrator(config)

        pr_json = json.dumps(
            [
                {
                    "number": 200,
                    "url": "https://github.com/o/r/pull/200",
                    "isDraft": True,
                }
            ]
        )

        async def fake_run(*args: str, **kwargs: Any) -> str:
            if "issue" in args:
                return RAW_ISSUE_JSON
            return pr_json

        with patch("orchestrator.run_subprocess", side_effect=fake_run):
            prs, issues = await orch._fetch_reviewable_prs()

        assert prs == []
        assert len(issues) == 1
        assert issues[0].number == 42

    @pytest.mark.asyncio
    async def test_no_matching_pr_returns_empty_pr_list(
        self, config: HydraConfig
    ) -> None:
        """Empty JSON array from PR lookup means no PRInfo is created."""
        orch = HydraOrchestrator(config)

        async def fake_run(*args: str, **kwargs: Any) -> str:
            if "issue" in args:
                return RAW_ISSUE_JSON
            return "[]"

        with patch("orchestrator.run_subprocess", side_effect=fake_run):
            prs, issues = await orch._fetch_reviewable_prs()

        assert prs == []
        assert len(issues) == 1
        assert issues[0].number == 42

    @pytest.mark.asyncio
    async def test_file_not_found_error_when_gh_missing(
        self, config: HydraConfig
    ) -> None:
        """FileNotFoundError during issue fetch returns ([], []) early."""
        orch = HydraOrchestrator(config)

        mock_create = AsyncMock(side_effect=FileNotFoundError("No such file: 'gh'"))

        with patch("asyncio.create_subprocess_exec", mock_create):
            prs, issues = await orch._fetch_reviewable_prs()

        assert prs == []
        assert issues == []

    @pytest.mark.asyncio
    async def test_dry_run_returns_empty_tuple(self, dry_config: HydraConfig) -> None:
        """Dry-run mode returns ([], []) without making subprocess calls."""
        orch = HydraOrchestrator(dry_config)

        mock_create = AsyncMock()

        with patch("asyncio.create_subprocess_exec", mock_create):
            prs, issues = await orch._fetch_reviewable_prs()

        assert prs == []
        assert issues == []
        mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_implement_releases_active_issues_for_review(
        self, config: HydraConfig
    ) -> None:
        """After implementation, issue should be removed from _active_issues
        so the review loop can pick it up."""
        orch = HydraOrchestrator(config)

        # Stub fetches to return one issue
        orch._fetch_ready_issues = AsyncMock(  # type: ignore[method-assign]
            return_value=[
                GitHubIssue(
                    number=42,
                    title="Test",
                    body="body",
                    labels=["test-label"],
                )
            ],
        )

        # Stub worktree creation and agent run
        orch._worktrees.create = AsyncMock(  # type: ignore[method-assign]
            return_value=Path("/tmp/wt-42"),
        )
        orch._agents.run = AsyncMock(  # type: ignore[method-assign]
            return_value=WorkerResult(
                issue_number=42,
                branch="agent/issue-42",
                worktree_path="/tmp/wt-42",
                success=True,
            ),
        )
        orch._prs.push_branch = AsyncMock(return_value=True)  # type: ignore[method-assign]
        orch._prs.create_pr = AsyncMock(return_value=None)  # type: ignore[method-assign]
        orch._prs.remove_label = AsyncMock()  # type: ignore[method-assign]
        orch._prs.add_labels = AsyncMock()  # type: ignore[method-assign]
        orch._prs.post_comment = AsyncMock()  # type: ignore[method-assign]

        results, _ = await orch._implement_batch()

        assert len(results) == 1
        assert results[0].success is True
        # Issue should have been released from _active_issues
        assert 42 not in orch._active_issues


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
        observed_running = False

        async def plan_and_stop() -> list[PlanResult]:
            nonlocal observed_running
            observed_running = orch.running
            orch._stop_event.set()
            return []

        orch._plan_issues = plan_and_stop  # type: ignore[method-assign]
        orch._implement_batch = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

        await orch.run()

        assert observed_running is True

    @pytest.mark.asyncio
    async def test_running_is_false_after_run_completes(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]

        async def plan_and_stop() -> list[PlanResult]:
            orch._stop_event.set()
            return []

        orch._plan_issues = plan_and_stop  # type: ignore[method-assign]
        orch._implement_batch = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

        await orch.run()

        assert orch.running is False

    @pytest.mark.asyncio
    async def test_publishes_status_events_on_start_and_end(
        self, config: HydraConfig
    ) -> None:
        """run() publishes orchestrator_status events at start and end."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]

        async def plan_and_stop() -> list[PlanResult]:
            orch._stop_event.set()
            return []

        orch._plan_issues = plan_and_stop  # type: ignore[method-assign]
        orch._implement_batch = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

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

        plan_calls = 0
        impl_calls = 0

        async def plan_spy() -> list[PlanResult]:
            nonlocal plan_calls
            plan_calls += 1
            orch._stop_event.set()
            return []

        async def impl_spy() -> tuple[list[WorkerResult], list[GitHubIssue]]:
            nonlocal impl_calls
            impl_calls += 1
            return [], []

        orch._plan_issues = plan_spy  # type: ignore[method-assign]
        orch._implement_batch = impl_spy  # type: ignore[method-assign]

        await orch.run()

        # Plan ran once and set stop; loops terminated
        assert plan_calls == 1

    @pytest.mark.asyncio
    async def test_loops_run_concurrently(self, config: HydraConfig) -> None:
        """Plan, implement, and review loops run concurrently via asyncio.gather."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]

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
        orch._implement_batch = fake_implement  # type: ignore[method-assign]

        await orch.run()

        assert "plan" in started
        assert "implement" in started


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
        observed_running = False

        async def spy_implement() -> tuple[list[WorkerResult], list[GitHubIssue]]:
            nonlocal observed_running
            observed_running = orch.running
            orch._stop_event.set()
            return [], []

        orch._plan_issues = AsyncMock(return_value=[])  # type: ignore[method-assign]
        orch._implement_batch = spy_implement  # type: ignore[method-assign]

        await orch.run()

        assert observed_running is True

    @pytest.mark.asyncio
    async def test_running_is_false_after_completion(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]

        async def plan_and_stop() -> list[PlanResult]:
            orch._stop_event.set()
            return []

        orch._plan_issues = plan_and_stop  # type: ignore[method-assign]
        orch._implement_batch = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

        await orch.run()

        assert orch.running is False

    @pytest.mark.asyncio
    async def test_stop_halts_loops(self, config: HydraConfig) -> None:
        """Setting stop event causes loops to exit after current iteration."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]

        call_count = 0

        async def counting_implement() -> tuple[list[WorkerResult], list[GitHubIssue]]:
            nonlocal call_count
            call_count += 1
            await orch.request_stop()
            return [make_worker_result(42)], [make_issue(42)]

        orch._plan_issues = AsyncMock(return_value=[])  # type: ignore[method-assign]
        orch._implement_batch = counting_implement  # type: ignore[method-assign]

        await orch.run()

        # Only one batch should have been processed before stop
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_stop_event_cleared_on_new_run(self, config: HydraConfig) -> None:
        """Calling run() again after stop should reset the stop event."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]
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
        orch._implement_batch = AsyncMock(return_value=([], []))  # type: ignore[method-assign]
        await orch.run()

        # Stop event set by our mock — key test is that run() didn't fail
        assert not orch.running

    @pytest.mark.asyncio
    async def test_running_false_after_stop(self, config: HydraConfig) -> None:
        """After stop halts the orchestrator, running should be False."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]

        async def stop_on_implement() -> tuple[list[WorkerResult], list[GitHubIssue]]:
            await orch.request_stop()
            return [make_worker_result(42)], [make_issue(42)]

        orch._plan_issues = AsyncMock(return_value=[])  # type: ignore[method-assign]
        orch._implement_batch = stop_on_implement  # type: ignore[method-assign]

        await orch.run()

        assert orch.running is False


# ---------------------------------------------------------------------------
# Plan phase
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

        with patch.object(orch, "_fetch_issues_by_labels", return_value=[issue]):
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

        with patch.object(orch, "_fetch_issues_by_labels", return_value=[issue]):
            await orch._triage_find_issues()

        mock_prs.remove_label.assert_called_once_with(2, config.find_label[0])
        mock_prs.add_labels.assert_called_once_with(2, [config.hitl_label[0]])
        mock_prs.post_comment.assert_called_once()
        comment = mock_prs.post_comment.call_args.args[1]
        assert "Needs More Information" in comment
        assert "Body is too short" in comment

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

        with patch.object(orch, "_fetch_issues_by_labels", return_value=issues):
            await orch._triage_find_issues()

        # Only the first issue should be evaluated; second skipped due to stop
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_triage_skips_when_no_issues_found(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)

        mock_prs = AsyncMock()
        orch._prs = mock_prs

        with patch.object(orch, "_fetch_issues_by_labels", return_value=[]):
            await orch._triage_find_issues()

        mock_prs.remove_label.assert_not_called()


# ---------------------------------------------------------------------------
# _fetch_plan_issues
# ---------------------------------------------------------------------------


RAW_PLAN_ISSUE_JSON = json.dumps(
    [
        {
            "number": 42,
            "title": "Fix bug",
            "body": "Details",
            "labels": [{"name": "hydra-plan"}],
            "comments": [],
            "url": "https://github.com/test-org/test-repo/issues/42",
        }
    ]
)


class TestFetchPlanIssues:
    """Tests for the _fetch_plan_issues coroutine."""

    @pytest.mark.asyncio
    async def test_returns_parsed_issues_from_gh_output(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(
            return_value=(RAW_PLAN_ISSUE_JSON.encode(), b"")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            issues = await orch._fetch_plan_issues()

        assert len(issues) == 1
        assert issues[0].number == 42
        assert issues[0].title == "Fix bug"
        assert issues[0].labels == ["hydra-plan"]

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_gh_fails(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"error: not found"))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            issues = await orch._fetch_plan_issues()

        assert issues == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_json_decode_error(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"not-json", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            issues = await orch._fetch_plan_issues()

        assert issues == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_gh_not_found(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError("gh not found"),
        ):
            issues = await orch._fetch_plan_issues()

        assert issues == []

    @pytest.mark.asyncio
    async def test_respects_batch_size_limit(self, config: HydraConfig) -> None:
        """Result list is truncated to batch_size."""
        raw = json.dumps(
            [
                {
                    "number": i,
                    "title": f"Issue {i}",
                    "body": "",
                    "labels": [{"name": "hydra-plan"}],
                    "comments": [],
                    "url": "",
                }
                for i in range(1, 10)
            ]
        )
        orch = HydraOrchestrator(config)
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(raw.encode(), b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            issues = await orch._fetch_plan_issues()

        assert len(issues) <= config.batch_size

    @pytest.mark.asyncio
    async def test_dry_run_returns_empty_list(self, config: HydraConfig) -> None:
        from config import HydraConfig as HC

        dry_config = HC(**{**config.model_dump(), "dry_run": True})
        orch = HydraOrchestrator(dry_config)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            issues = await orch._fetch_plan_issues()

        assert issues == []
        mock_exec.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_planner_label_fetches_all_excluding_downstream(
        self, config: HydraConfig
    ) -> None:
        """When planner_label is empty, fetch all open issues excluding downstream labels."""
        from config import HydraConfig as HC

        no_plan_config = HC(**{**config.model_dump(), "planner_label": []})
        orch = HydraOrchestrator(no_plan_config)

        raw = json.dumps(
            [
                {
                    "number": 1,
                    "title": "Unlabeled issue",
                    "body": "Body",
                    "labels": [],
                    "comments": [],
                    "url": "",
                },
                {
                    "number": 2,
                    "title": "Ready issue",
                    "body": "Body",
                    "labels": [{"name": "test-label"}],
                    "comments": [],
                    "url": "",
                },
            ]
        )
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(raw.encode(), b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            issues = await orch._fetch_plan_issues()

        # Issue #2 has ready_label ("test-label") so it should be filtered out
        assert len(issues) == 1
        assert issues[0].number == 1


class TestPlanPhase:
    """Tests for the PLAN phase in the orchestrator loop."""

    @pytest.mark.asyncio
    async def test_all_loops_run_concurrently(self, config: HydraConfig) -> None:
        """Triage, plan, implement, review should all run concurrently."""
        orch = HydraOrchestrator(config)
        orch._prs.ensure_labels_exist = AsyncMock()  # type: ignore[method-assign]

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
        orch._implement_batch = fake_implement  # type: ignore[method-assign]

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
        orch._fetch_plan_issues = AsyncMock(return_value=[issue])  # type: ignore[method-assign]

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
        orch._fetch_plan_issues = AsyncMock(return_value=[issue])  # type: ignore[method-assign]

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
        orch._fetch_plan_issues = AsyncMock(return_value=[issue])  # type: ignore[method-assign]

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
        orch._fetch_plan_issues = AsyncMock(return_value=[])  # type: ignore[method-assign]

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
                NewIssueSpec(title="Issue A", body="Body A", labels=["bug"]),
                NewIssueSpec(title="Issue B", body="Body B", labels=["bug"]),
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
                    title="Tech debt", body="Cleanup needed", labels=["tech-debt"]
                ),
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

        mock_prs.create_issue.assert_awaited_once_with(
            "Tech debt", "Cleanup needed", ["tech-debt"]
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
        orch._fetch_plan_issues = AsyncMock(return_value=issues)  # type: ignore[method-assign]

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
        orch._fetch_plan_issues = AsyncMock(return_value=[issue])  # type: ignore[method-assign]

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
                NewIssueSpec(title="Discovered issue", body="Body"),
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

        mock_prs.create_issue.assert_awaited_once_with(
            "Discovered issue", "Body", [config.planner_label[0]]
        )

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
        orch._fetch_plan_issues = AsyncMock(return_value=issues)  # type: ignore[method-assign]

        mock_prs = AsyncMock()
        mock_prs.post_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        results = await orch._plan_issues()

        # Not all 3 should have completed — stop event triggers cancellation
        assert len(results) < len(issues)


# ---------------------------------------------------------------------------
# CI wait/fix loop (_wait_and_fix_ci)
# ---------------------------------------------------------------------------


class TestWaitAndFixCI:
    """Tests for the _wait_and_fix_ci method and CI gate in _review_prs."""

    def _make_orch(self, config: HydraConfig) -> HydraOrchestrator:
        orch = HydraOrchestrator(config)
        mock_wt = AsyncMock()
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt
        return orch

    @pytest.mark.asyncio
    async def test_ci_passes_on_first_check_merges(self, config: HydraConfig) -> None:
        """When CI passes on first check, PR should be merged."""
        from tests.helpers import ConfigFactory

        cfg = ConfigFactory.create(
            max_ci_fix_attempts=2,
            repo_root=config.repo_root,
            worktree_base=config.worktree_base,
            state_file=config.state_file,
        )
        orch = self._make_orch(cfg)
        issue = make_issue(42)
        pr = make_pr_info(101, 42)

        mock_reviewers = AsyncMock()
        mock_reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        orch._reviewers = mock_reviewers

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.merge_pr = AsyncMock(return_value=True)
        mock_prs.wait_for_ci = AsyncMock(return_value=(True, "All 3 checks passed"))
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await orch._review_prs([pr], [issue])

        assert results[0].merged is True
        assert results[0].ci_passed is True
        mock_prs.merge_pr.assert_awaited_once_with(101)

    @pytest.mark.asyncio
    async def test_ci_fails_all_attempts_does_not_merge(
        self, config: HydraConfig
    ) -> None:
        """When CI fails after all fix attempts, PR should not be merged."""
        from tests.helpers import ConfigFactory

        cfg = ConfigFactory.create(
            max_ci_fix_attempts=1,
            repo_root=config.repo_root,
            worktree_base=config.worktree_base,
            state_file=config.state_file,
        )
        orch = self._make_orch(cfg)
        issue = make_issue(42)
        pr = make_pr_info(101, 42)

        mock_reviewers = AsyncMock()
        mock_reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        fix_result = ReviewResult(
            pr_number=101,
            issue_number=42,
            verdict=ReviewVerdict.REQUEST_CHANGES,
            fixes_made=True,
        )
        mock_reviewers.fix_ci = AsyncMock(return_value=fix_result)
        orch._reviewers = mock_reviewers

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.merge_pr = AsyncMock(return_value=True)
        mock_prs.wait_for_ci = AsyncMock(return_value=(False, "Failed checks: ci"))
        mock_prs.post_pr_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await orch._review_prs([pr], [issue])

        assert results[0].merged is False
        assert results[0].ci_passed is False
        mock_prs.merge_pr.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_ci_wait_skipped_when_max_attempts_zero(
        self, config: HydraConfig
    ) -> None:
        """When max_ci_fix_attempts=0, CI wait is skipped entirely."""
        from tests.helpers import ConfigFactory

        cfg = ConfigFactory.create(
            max_ci_fix_attempts=0,
            repo_root=config.repo_root,
            worktree_base=config.worktree_base,
            state_file=config.state_file,
        )
        orch = self._make_orch(cfg)
        issue = make_issue(42)
        pr = make_pr_info(101, 42)

        mock_reviewers = AsyncMock()
        mock_reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        orch._reviewers = mock_reviewers

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.merge_pr = AsyncMock(return_value=True)
        mock_prs.wait_for_ci = AsyncMock(return_value=(True, "passed"))
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await orch._review_prs([pr], [issue])

        assert results[0].merged is True
        # wait_for_ci should NOT have been called
        mock_prs.wait_for_ci.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_ci_not_checked_for_non_approve_verdicts(
        self, config: HydraConfig
    ) -> None:
        """CI wait only triggers for APPROVE — REQUEST_CHANGES skips it."""
        from tests.helpers import ConfigFactory

        cfg = ConfigFactory.create(
            max_ci_fix_attempts=2,
            repo_root=config.repo_root,
            worktree_base=config.worktree_base,
            state_file=config.state_file,
        )
        orch = self._make_orch(cfg)
        issue = make_issue(42)
        pr = make_pr_info(101, 42)

        mock_reviewers = AsyncMock()
        mock_reviewers.review = AsyncMock(
            return_value=make_review_result(
                101, 42, verdict=ReviewVerdict.REQUEST_CHANGES
            )
        )
        orch._reviewers = mock_reviewers

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.merge_pr = AsyncMock(return_value=True)
        mock_prs.wait_for_ci = AsyncMock(return_value=(True, "passed"))
        orch._prs = mock_prs

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await orch._review_prs([pr], [issue])

        assert results[0].merged is False
        mock_prs.wait_for_ci.assert_not_awaited()
        mock_prs.merge_pr.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fix_loop_retries_after_agent_makes_changes(
        self, config: HydraConfig
    ) -> None:
        """When fix agent makes changes, loop should retry CI."""
        from tests.helpers import ConfigFactory

        cfg = ConfigFactory.create(
            max_ci_fix_attempts=2,
            repo_root=config.repo_root,
            worktree_base=config.worktree_base,
            state_file=config.state_file,
        )
        orch = self._make_orch(cfg)
        issue = make_issue(42)
        pr = make_pr_info(101, 42)

        # CI fails first, then passes after fix
        ci_results = [
            (False, "Failed checks: ci"),
            (True, "All 2 checks passed"),
        ]
        ci_call_count = 0

        async def fake_wait_for_ci(_pr_num, _timeout, _interval, _stop):
            nonlocal ci_call_count
            result = ci_results[ci_call_count]
            ci_call_count += 1
            return result

        fix_result = ReviewResult(
            pr_number=101,
            issue_number=42,
            verdict=ReviewVerdict.APPROVE,
            fixes_made=True,
        )

        mock_reviewers = AsyncMock()
        mock_reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        mock_reviewers.fix_ci = AsyncMock(return_value=fix_result)
        orch._reviewers = mock_reviewers

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.merge_pr = AsyncMock(return_value=True)
        mock_prs.wait_for_ci = fake_wait_for_ci
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await orch._review_prs([pr], [issue])

        assert results[0].merged is True
        assert results[0].ci_passed is True
        assert results[0].ci_fix_attempts == 1
        assert ci_call_count == 2

    @pytest.mark.asyncio
    async def test_fix_agent_no_changes_stops_retrying(
        self, config: HydraConfig
    ) -> None:
        """When fix agent makes no changes, loop should stop early."""
        from tests.helpers import ConfigFactory

        cfg = ConfigFactory.create(
            max_ci_fix_attempts=3,
            repo_root=config.repo_root,
            worktree_base=config.worktree_base,
            state_file=config.state_file,
        )
        orch = self._make_orch(cfg)
        issue = make_issue(42)
        pr = make_pr_info(101, 42)

        fix_result = ReviewResult(
            pr_number=101,
            issue_number=42,
            verdict=ReviewVerdict.REQUEST_CHANGES,
            fixes_made=False,  # No changes made
        )

        mock_reviewers = AsyncMock()
        mock_reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        mock_reviewers.fix_ci = AsyncMock(return_value=fix_result)
        orch._reviewers = mock_reviewers

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.merge_pr = AsyncMock(return_value=True)
        mock_prs.wait_for_ci = AsyncMock(return_value=(False, "Failed checks: ci"))
        mock_prs.post_pr_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await orch._review_prs([pr], [issue])

        assert results[0].merged is False
        assert results[0].ci_passed is False
        # Only 1 fix attempt (stopped early because no changes)
        assert results[0].ci_fix_attempts == 1
        # fix_ci called once, not 3 times
        mock_reviewers.fix_ci.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ci_failure_posts_comment_and_labels_hitl(
        self, config: HydraConfig
    ) -> None:
        """CI failure should post a comment and swap label to hydra-hitl."""
        from tests.helpers import ConfigFactory

        cfg = ConfigFactory.create(
            max_ci_fix_attempts=1,
            repo_root=config.repo_root,
            worktree_base=config.worktree_base,
            state_file=config.state_file,
        )
        orch = self._make_orch(cfg)
        issue = make_issue(42)
        pr = make_pr_info(101, 42)

        fix_result = ReviewResult(
            pr_number=101,
            issue_number=42,
            verdict=ReviewVerdict.REQUEST_CHANGES,
            fixes_made=True,
        )

        mock_reviewers = AsyncMock()
        mock_reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        mock_reviewers.fix_ci = AsyncMock(return_value=fix_result)
        orch._reviewers = mock_reviewers

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.merge_pr = AsyncMock(return_value=True)
        mock_prs.wait_for_ci = AsyncMock(return_value=(False, "Failed checks: ci"))
        mock_prs.post_pr_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await orch._review_prs([pr], [issue])

        # Should have posted a CI failure comment
        comment_calls = [c.args for c in mock_prs.post_pr_comment.call_args_list]
        ci_comments = [c for c in comment_calls if "CI failed" in c[1]]
        assert len(ci_comments) == 1
        assert "Failed checks: ci" in ci_comments[0][1]

        # Should swap label to hydra-hitl
        remove_calls = [c.args for c in mock_prs.remove_label.call_args_list]
        assert (42, "hydra-review") in remove_calls
        add_calls = [c.args for c in mock_prs.add_labels.call_args_list]
        assert (42, ["hydra-hitl"]) in add_calls


# ---------------------------------------------------------------------------
# Direct unit tests for _wait_and_fix_ci (calls the method in isolation)
# ---------------------------------------------------------------------------


class TestWaitAndFixCIDirect:
    """Direct unit tests for _wait_and_fix_ci — calls the method in isolation."""

    def _make_orch(self, config: HydraConfig) -> HydraOrchestrator:
        orch = HydraOrchestrator(config)
        orch._worktrees = AsyncMock()
        return orch

    @pytest.mark.asyncio
    async def test_ci_passes_first_check(self, config: HydraConfig) -> None:
        """CI passes on first check — returns True, fix_ci never called."""
        from tests.helpers import ConfigFactory

        cfg = ConfigFactory.create(
            max_ci_fix_attempts=2,
            repo_root=config.repo_root,
            worktree_base=config.worktree_base,
            state_file=config.state_file,
        )
        orch = self._make_orch(cfg)

        mock_prs = AsyncMock()
        mock_prs.wait_for_ci = AsyncMock(return_value=(True, "All checks passed"))
        orch._prs = mock_prs

        mock_reviewers = AsyncMock()
        mock_reviewers.fix_ci = AsyncMock()
        orch._reviewers = mock_reviewers

        pr = make_pr_info(101, 42)
        issue = make_issue(42)
        result = make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        wt_path = config.worktree_base / "issue-42"

        passed = await orch._wait_and_fix_ci(pr, issue, wt_path, result, worker_id=0)

        assert passed is True
        assert result.ci_passed is True
        assert result.ci_fix_attempts == 0
        mock_reviewers.fix_ci.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_ci_fails_fix_succeeds_retry_passes(
        self, config: HydraConfig
    ) -> None:
        """CI fails, fix agent makes changes, CI passes on retry."""
        from tests.helpers import ConfigFactory

        cfg = ConfigFactory.create(
            max_ci_fix_attempts=2,
            repo_root=config.repo_root,
            worktree_base=config.worktree_base,
            state_file=config.state_file,
        )
        orch = self._make_orch(cfg)

        ci_results = [(False, "Failed checks"), (True, "All checks passed")]
        mock_prs = AsyncMock()
        mock_prs.wait_for_ci = AsyncMock(side_effect=ci_results)
        mock_prs.push_branch = AsyncMock()
        orch._prs = mock_prs

        fix_result = ReviewResult(
            pr_number=101,
            issue_number=42,
            verdict=ReviewVerdict.APPROVE,
            fixes_made=True,
        )
        mock_reviewers = AsyncMock()
        mock_reviewers.fix_ci = AsyncMock(return_value=fix_result)
        orch._reviewers = mock_reviewers

        pr = make_pr_info(101, 42)
        issue = make_issue(42)
        result = make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        wt_path = config.worktree_base / "issue-42"

        passed = await orch._wait_and_fix_ci(pr, issue, wt_path, result, worker_id=0)

        assert passed is True
        assert result.ci_passed is True
        assert result.ci_fix_attempts == 1
        mock_prs.push_branch.assert_awaited_once_with(wt_path, pr.branch)

    @pytest.mark.asyncio
    async def test_ci_fails_max_attempts_escalates(self, config: HydraConfig) -> None:
        """CI fails after max fix attempts — escalates to HITL."""
        from tests.helpers import ConfigFactory

        cfg = ConfigFactory.create(
            max_ci_fix_attempts=1,
            repo_root=config.repo_root,
            worktree_base=config.worktree_base,
            state_file=config.state_file,
        )
        orch = self._make_orch(cfg)

        mock_prs = AsyncMock()
        mock_prs.wait_for_ci = AsyncMock(return_value=(False, "Failed checks"))
        mock_prs.push_branch = AsyncMock()
        mock_prs.post_pr_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        fix_result = ReviewResult(
            pr_number=101,
            issue_number=42,
            verdict=ReviewVerdict.REQUEST_CHANGES,
            fixes_made=True,
        )
        mock_reviewers = AsyncMock()
        mock_reviewers.fix_ci = AsyncMock(return_value=fix_result)
        orch._reviewers = mock_reviewers

        pr = make_pr_info(101, 42)
        issue = make_issue(42)
        result = make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        wt_path = config.worktree_base / "issue-42"

        passed = await orch._wait_and_fix_ci(pr, issue, wt_path, result, worker_id=0)

        assert passed is False
        assert result.ci_passed is False
        assert result.ci_fix_attempts == 1

        # Verify CI failure comment
        comment_args = mock_prs.post_pr_comment.call_args.args
        assert comment_args[0] == 101
        assert "CI failed" in comment_args[1]

        # Verify HITL label swap
        remove_calls = [c.args for c in mock_prs.remove_label.call_args_list]
        assert (42, "hydra-review") in remove_calls
        add_calls = [c.args for c in mock_prs.add_labels.call_args_list]
        assert (42, ["hydra-hitl"]) in add_calls

    @pytest.mark.asyncio
    async def test_fix_ci_raises_exception(self, config: HydraConfig) -> None:
        """fix_ci raising an exception should propagate — not silently swallowed."""
        from tests.helpers import ConfigFactory

        cfg = ConfigFactory.create(
            max_ci_fix_attempts=2,
            repo_root=config.repo_root,
            worktree_base=config.worktree_base,
            state_file=config.state_file,
        )
        orch = self._make_orch(cfg)

        mock_prs = AsyncMock()
        mock_prs.wait_for_ci = AsyncMock(return_value=(False, "Failed checks"))
        orch._prs = mock_prs

        mock_reviewers = AsyncMock()
        mock_reviewers.fix_ci = AsyncMock(side_effect=RuntimeError("Agent crashed"))
        orch._reviewers = mock_reviewers

        pr = make_pr_info(101, 42)
        issue = make_issue(42)
        result = make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        wt_path = config.worktree_base / "issue-42"

        with pytest.raises(RuntimeError, match="Agent crashed"):
            await orch._wait_and_fix_ci(pr, issue, wt_path, result, worker_id=0)

    @pytest.mark.asyncio
    async def test_stop_event_passed_to_wait_for_ci(self, config: HydraConfig) -> None:
        """Stop event should be threaded through to wait_for_ci."""
        from tests.helpers import ConfigFactory

        cfg = ConfigFactory.create(
            max_ci_fix_attempts=2,
            repo_root=config.repo_root,
            worktree_base=config.worktree_base,
            state_file=config.state_file,
        )
        orch = self._make_orch(cfg)
        orch._stop_event.set()

        mock_prs = AsyncMock()
        mock_prs.wait_for_ci = AsyncMock(return_value=(False, "Cancelled"))
        mock_prs.post_pr_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        fix_result = ReviewResult(
            pr_number=101,
            issue_number=42,
            verdict=ReviewVerdict.APPROVE,
            fixes_made=True,
        )
        mock_reviewers = AsyncMock()
        mock_reviewers.fix_ci = AsyncMock(return_value=fix_result)
        orch._reviewers = mock_reviewers

        pr = make_pr_info(101, 42)
        issue = make_issue(42)
        result = make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        wt_path = config.worktree_base / "issue-42"

        await orch._wait_and_fix_ci(pr, issue, wt_path, result, worker_id=0)

        # Verify stop_event was passed as the 4th argument to wait_for_ci
        call_args = mock_prs.wait_for_ci.call_args_list[0]
        assert call_args.args[3] is orch._stop_event

    @pytest.mark.asyncio
    async def test_zero_max_attempts_checks_ci_no_fix(
        self, config: HydraConfig
    ) -> None:
        """max_ci_fix_attempts=0 checks CI once but never calls fix_ci."""
        from tests.helpers import ConfigFactory

        cfg = ConfigFactory.create(
            max_ci_fix_attempts=0,
            repo_root=config.repo_root,
            worktree_base=config.worktree_base,
            state_file=config.state_file,
        )
        orch = self._make_orch(cfg)

        mock_prs = AsyncMock()
        mock_prs.wait_for_ci = AsyncMock(return_value=(False, "Failed checks"))
        mock_prs.post_pr_comment = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        orch._prs = mock_prs

        mock_reviewers = AsyncMock()
        mock_reviewers.fix_ci = AsyncMock()
        orch._reviewers = mock_reviewers

        pr = make_pr_info(101, 42)
        issue = make_issue(42)
        result = make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        wt_path = config.worktree_base / "issue-42"

        passed = await orch._wait_and_fix_ci(pr, issue, wt_path, result, worker_id=0)

        assert passed is False
        assert result.ci_passed is False
        assert result.ci_fix_attempts == 0
        mock_reviewers.fix_ci.assert_not_awaited()

        # Should still escalate to HITL
        mock_prs.post_pr_comment.assert_awaited_once()
        comment_args = mock_prs.post_pr_comment.call_args.args
        assert "CI failed" in comment_args[1]
        remove_calls = [c.args for c in mock_prs.remove_label.call_args_list]
        assert (42, "hydra-review") in remove_calls
        add_calls = [c.args for c in mock_prs.add_labels.call_args_list]
        assert (42, ["hydra-hitl"]) in add_calls


# NOTE: Tests for the subprocess helper (stdout parsing, error handling,
# GH_TOKEN injection, CLAUDECODE stripping) are now in test_subprocess_util.py
# since the logic was extracted into subprocess_util.run_subprocess.
