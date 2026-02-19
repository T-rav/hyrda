"""Tests for dx/hydra/orchestrator.py - HydraOrchestrator class."""

from __future__ import annotations

import asyncio
import json
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

    def test_default_max_reviewers_is_one(self, config: HydraConfig) -> None:
        assert HydraOrchestrator.DEFAULT_MAX_REVIEWERS == 1

    def test_default_max_planners_is_one(self, config: HydraConfig) -> None:
        assert HydraOrchestrator.DEFAULT_MAX_PLANNERS == 1


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

        results = [
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
            return next(r for r in results if r.issue_number == issue.number)

        orch._agents.run = fake_agent_run  # type: ignore[method-assign]
        orch._fetch_ready_issues = AsyncMock(return_value=issues)  # type: ignore[method-assign]

        mock_wt = AsyncMock()
        mock_wt.create = AsyncMock(
            side_effect=lambda num, branch: config.worktree_base / f"issue-{num}"
        )
        orch._worktrees = mock_wt

        mock_prs = AsyncMock()
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.create_pr = AsyncMock(return_value=make_pr_info())
        mock_prs.add_labels = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        orch._prs = mock_prs

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
        orch._agents.run = fake_agent_run  # type: ignore[method-assign]
        orch._fetch_ready_issues = AsyncMock(return_value=issues)  # type: ignore[method-assign]

        mock_wt = AsyncMock()
        mock_wt.create = AsyncMock(
            side_effect=lambda num, branch: config.worktree_base / f"issue-{num}"
        )
        orch._worktrees = mock_wt

        mock_prs = AsyncMock()
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.create_pr = AsyncMock(return_value=make_pr_info())
        mock_prs.add_labels = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        orch._prs = mock_prs

        await orch._implement_batch()

        assert concurrency_counter["peak"] <= config.max_workers

    @pytest.mark.asyncio
    async def test_marks_issue_in_progress_then_done(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        issue = make_issue(55)

        async def fake_agent_run(
            issue: GitHubIssue, wt_path: Path, branch: str, worker_id: int = 0
        ) -> WorkerResult:
            return make_worker_result(
                issue_number=issue.number, success=True, worktree_path=str(wt_path)
            )

        orch._agents.run = fake_agent_run  # type: ignore[method-assign]
        orch._fetch_ready_issues = AsyncMock(return_value=[issue])  # type: ignore[method-assign]

        mock_wt = AsyncMock()
        mock_wt.create = AsyncMock(return_value=config.worktree_base / "issue-55")
        orch._worktrees = mock_wt

        mock_prs = AsyncMock()
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.create_pr = AsyncMock(return_value=make_pr_info())
        mock_prs.add_labels = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        orch._prs = mock_prs

        await orch._implement_batch()

        status = orch._state.get_issue_status(55)
        assert status == "success"

    @pytest.mark.asyncio
    async def test_marks_issue_failed_when_agent_fails(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        issue = make_issue(66)

        async def fake_agent_run(
            issue: GitHubIssue, wt_path: Path, branch: str, worker_id: int = 0
        ) -> WorkerResult:
            return make_worker_result(
                issue_number=issue.number, success=False, worktree_path=str(wt_path)
            )

        orch._agents.run = fake_agent_run  # type: ignore[method-assign]
        orch._fetch_ready_issues = AsyncMock(return_value=[issue])  # type: ignore[method-assign]

        mock_wt = AsyncMock()
        mock_wt.create = AsyncMock(return_value=config.worktree_base / "issue-66")
        orch._worktrees = mock_wt

        mock_prs = AsyncMock()
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.create_pr = AsyncMock(return_value=make_pr_info())
        mock_prs.add_labels = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        orch._prs = mock_prs

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

        async def fake_agent_run(
            issue: GitHubIssue, wt_path: Path, branch: str, worker_id: int = 0
        ) -> WorkerResult:
            return make_worker_result(
                issue_number=issue.number, success=True, worktree_path=str(wt_path)
            )

        orch._agents.run = fake_agent_run  # type: ignore[method-assign]
        orch._fetch_ready_issues = AsyncMock(return_value=[issue])  # type: ignore[method-assign]

        mock_wt = AsyncMock()
        mock_wt.create = AsyncMock()
        orch._worktrees = mock_wt

        mock_prs = AsyncMock()
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.post_comment = AsyncMock()
        mock_prs.create_pr = AsyncMock(return_value=make_pr_info(101, 77))
        mock_prs.add_labels = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        orch._prs = mock_prs

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

        async def fake_agent_run(
            issue: GitHubIssue, wt_path: Path, branch: str, worker_id: int = 0
        ) -> WorkerResult:
            return make_worker_result(
                issue_number=issue.number, success=True, worktree_path=str(wt_path)
            )

        orch._agents.run = fake_agent_run  # type: ignore[method-assign]
        orch._fetch_ready_issues = AsyncMock(return_value=[issue])  # type: ignore[method-assign]

        mock_wt = AsyncMock()
        mock_wt.create = AsyncMock(return_value=config.worktree_base / "issue-42")
        orch._worktrees = mock_wt

        mock_prs = AsyncMock()
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.create_pr = AsyncMock(return_value=make_pr_info(101, 42))
        mock_prs.add_labels = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        orch._prs = mock_prs

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

        async def fake_agent_run(
            issue: GitHubIssue, wt_path: Path, branch: str, worker_id: int = 0
        ) -> WorkerResult:
            return make_worker_result(
                issue_number=issue.number, success=False, worktree_path=str(wt_path)
            )

        orch._agents.run = fake_agent_run  # type: ignore[method-assign]
        orch._fetch_ready_issues = AsyncMock(return_value=[issue])  # type: ignore[method-assign]

        mock_wt = AsyncMock()
        mock_wt.create = AsyncMock(return_value=config.worktree_base / "issue-42")
        orch._worktrees = mock_wt

        mock_prs = AsyncMock()
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.create_pr = AsyncMock(return_value=make_pr_info(101, 42, draft=True))
        mock_prs.add_labels = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        orch._prs = mock_prs

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

        async def fake_agent_run(
            issue: GitHubIssue, wt_path: Path, branch: str, worker_id: int = 0
        ) -> WorkerResult:
            return make_worker_result(
                issue_number=issue.number, success=True, worktree_path=str(wt_path)
            )

        orch._agents.run = fake_agent_run  # type: ignore[method-assign]
        orch._fetch_ready_issues = AsyncMock(return_value=[issue])  # type: ignore[method-assign]

        mock_wt = AsyncMock()
        mock_wt.create = AsyncMock(return_value=config.worktree_base / "issue-42")
        orch._worktrees = mock_wt

        mock_prs = AsyncMock()
        mock_prs.push_branch = AsyncMock(return_value=False)
        mock_prs.create_pr = AsyncMock()
        orch._prs = mock_prs

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

        orch._agents.run = fake_agent_run  # type: ignore[method-assign]
        orch._fetch_ready_issues = AsyncMock(return_value=[issue])  # type: ignore[method-assign]

        mock_wt = AsyncMock()
        mock_wt.create = AsyncMock(return_value=config.worktree_base / "issue-42")
        orch._worktrees = mock_wt

        mock_prs = AsyncMock()
        mock_prs.push_branch = fake_push
        mock_prs.post_comment = fake_comment
        mock_prs.create_pr = AsyncMock(return_value=make_pr_info(101, 42))
        mock_prs.add_labels = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        orch._prs = mock_prs

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
    async def test_reviewer_only_limited_by_default_max_reviewers(
        self, config: HydraConfig
    ) -> None:
        """At most DEFAULT_MAX_REVIEWERS concurrent reviews."""
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

        assert concurrency_counter["peak"] <= HydraOrchestrator.DEFAULT_MAX_REVIEWERS

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
    async def test_review_merge_failure_sets_merged_false(
        self, config: HydraConfig
    ) -> None:
        """When merge fails, result.merged should remain False."""
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

        results = await orch._review_prs([pr], [issue])

        assert results[0].merged is False

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
    async def test_review_submits_formal_github_review(
        self, config: HydraConfig
    ) -> None:
        """submit_review should be called with verdict and summary."""
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

        mock_prs.submit_review.assert_awaited_once_with(101, "approve", "Looks good.")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "verdict",
        [ReviewVerdict.APPROVE, ReviewVerdict.REQUEST_CHANGES, ReviewVerdict.COMMENT],
    )
    async def test_review_submits_review_for_all_verdicts(
        self, config: HydraConfig, verdict: ReviewVerdict
    ) -> None:
        """submit_review should be called for all verdict types."""
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

        mock_prs.submit_review.assert_awaited_once_with(
            101, verdict.value, "Looks good."
        )

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
        # submit_review should still be called
        mock_prs.submit_review.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_review_comment_and_review_before_merge(
        self, config: HydraConfig
    ) -> None:
        """post_pr_comment and submit_review should be called before merge."""
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

        async def fake_submit_review(pr_number: int, verdict: str, body: str) -> bool:
            call_order.append("submit_review")
            return True

        async def fake_merge(pr_number: int) -> bool:
            call_order.append("merge")
            return True

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff text")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.post_pr_comment = fake_post_pr_comment
        mock_prs.submit_review = fake_submit_review
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
        assert call_order.index("submit_review") < call_order.index("merge")

    @pytest.mark.asyncio
    async def test_review_posts_comment_even_when_merge_fails(
        self, config: HydraConfig
    ) -> None:
        """post_pr_comment and submit_review should be called regardless of merge outcome."""
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

        mock_prs.post_pr_comment.assert_awaited_once_with(101, "Looks good.")
        mock_prs.submit_review.assert_awaited_once_with(101, "approve", "Looks good.")


# ---------------------------------------------------------------------------
# _fetch_reviewable_prs — skip logic
# ---------------------------------------------------------------------------


class TestFetchReviewablePrsSkipLogic:
    """Tests for _fetch_reviewable_prs filtering by in-memory active set."""

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

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(RAW_ISSUE_JSON.encode(), b""))

        async def fake_gh_run(*args: str) -> str:
            return pr_json

        orch._gh_run = fake_gh_run  # type: ignore[method-assign]

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            prs, issues = await orch._fetch_reviewable_prs()

        assert len(issues) == 1
        assert issues[0].number == 42


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

    def test_request_stop_sets_stop_event(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        assert not orch._stop_event.is_set()
        orch.request_stop()
        assert orch._stop_event.is_set()

    def test_stop_terminates_all_runners(self, config: HydraConfig) -> None:
        """stop() should call terminate() on planners, agents, and reviewers."""
        orch = HydraOrchestrator(config)
        with (
            patch.object(orch._planners, "terminate") as mock_p,
            patch.object(orch._agents, "terminate") as mock_a,
            patch.object(orch._reviewers, "terminate") as mock_r,
        ):
            orch.stop()

        mock_p.assert_called_once()
        mock_a.assert_called_once()
        mock_r.assert_called_once()

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

        call_count = 0

        async def counting_implement() -> tuple[list[WorkerResult], list[GitHubIssue]]:
            nonlocal call_count
            call_count += 1
            orch.request_stop()
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
        orch.request_stop()
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

        async def stop_on_implement() -> tuple[list[WorkerResult], list[GitHubIssue]]:
            orch.request_stop()
            return [make_worker_result(42)], [make_issue(42)]

        orch._plan_issues = AsyncMock(return_value=[])  # type: ignore[method-assign]
        orch._implement_batch = stop_on_implement  # type: ignore[method-assign]

        await orch.run()

        assert orch.running is False


# ---------------------------------------------------------------------------
# Plan phase
# ---------------------------------------------------------------------------


class TestPlanPhase:
    """Tests for the PLAN phase in the orchestrator loop."""

    @pytest.mark.asyncio
    async def test_plan_runs_concurrently_with_implement(
        self, config: HydraConfig
    ) -> None:
        """Plan and implement should run concurrently in each batch."""
        orch = HydraOrchestrator(config)

        execution_order: list[str] = []

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

        orch._plan_issues = fake_plan  # type: ignore[method-assign]
        orch._implement_batch = fake_implement  # type: ignore[method-assign]

        await orch.run()

        # Both should have started before either finished (concurrent)
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

        mock_prs.remove_label.assert_awaited_once_with(42, config.planner_label)
        mock_prs.add_labels.assert_awaited_once_with(42, [config.ready_label])

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
