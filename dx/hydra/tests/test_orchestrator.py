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

if TYPE_CHECKING:
    from config import HydraConfig
from models import (
    GitHubIssue,
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

    def test_default_max_reviewers_is_two(self, config: HydraConfig) -> None:
        assert HydraOrchestrator.DEFAULT_MAX_REVIEWERS == 2


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
# _fetch_issues
# ---------------------------------------------------------------------------


class TestFetchIssues:
    """Tests for the _fetch_issues coroutine."""

    @pytest.mark.asyncio
    async def test_returns_parsed_issues_from_gh_output(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(RAW_ISSUE_JSON.encode(), b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            issues = await orch._fetch_issues()

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
            issues = await orch._fetch_issues()

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
            issues = await orch._fetch_issues()

        assert "hello" in issues[0].comments
        assert "world" in issues[0].comments

    @pytest.mark.asyncio
    async def test_skips_already_processed_issues(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        orch._state.mark_issue(42, "success")

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(RAW_ISSUE_JSON.encode(), b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            issues = await orch._fetch_issues()

        assert issues == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_gh_fails(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"error: not found"))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            issues = await orch._fetch_issues()

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
            issues = await orch._fetch_issues()

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
            issues = await orch._fetch_issues()

        assert issues == []

    @pytest.mark.asyncio
    async def test_respects_batch_size_limit(self, config: HydraConfig) -> None:
        """Result list is truncated to config.batch_size."""
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
        # config has batch_size=3 from conftest fixture
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(raw.encode(), b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            issues = await orch._fetch_issues()

        assert len(issues) <= config.batch_size

    @pytest.mark.asyncio
    async def test_dry_run_returns_empty_list(self, config: HydraConfig) -> None:
        from config import HydraConfig

        dry_config = HydraConfig(**{**config.model_dump(), "dry_run": True})
        orch = HydraOrchestrator(dry_config)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            issues = await orch._fetch_issues()

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

        mock_wt = AsyncMock()
        mock_wt.create = AsyncMock(
            side_effect=lambda num, branch: config.worktree_base / f"issue-{num}"
        )
        orch._worktrees = mock_wt

        returned = await orch._implement_batch(issues)
        assert len(returned) == 2
        issue_numbers = {r.issue_number for r in returned}
        assert issue_numbers == {1, 2}

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self, config: HydraConfig) -> None:
        """max_workers=2 means at most 2 agents run concurrently."""
        concurrency_counter = {"current": 0, "peak": 0}
        asyncio.Event()

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

        orch = HydraOrchestrator(config)  # max_workers=2 from conftest
        orch._agents.run = fake_agent_run  # type: ignore[method-assign]

        mock_wt = AsyncMock()
        mock_wt.create = AsyncMock(
            side_effect=lambda num, branch: config.worktree_base / f"issue-{num}"
        )
        orch._worktrees = mock_wt

        issues = [make_issue(i) for i in range(1, 6)]
        await orch._implement_batch(issues)

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

        mock_wt = AsyncMock()
        mock_wt.create = AsyncMock(return_value=config.worktree_base / "issue-55")
        orch._worktrees = mock_wt

        await orch._implement_batch([issue])

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

        mock_wt = AsyncMock()
        mock_wt.create = AsyncMock(return_value=config.worktree_base / "issue-66")
        orch._worktrees = mock_wt

        await orch._implement_batch([issue])

        status = orch._state.get_issue_status(66)
        assert status == "failed"


# ---------------------------------------------------------------------------
# _push_and_create_prs
# ---------------------------------------------------------------------------


class TestPushAndCreatePRs:
    """Tests for the _push_and_create_prs coroutine."""

    @pytest.mark.asyncio
    async def test_creates_standard_pr_for_successful_result(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        result = make_worker_result(42, success=True, worktree_path="/tmp/wt/issue-42")

        mock_prs = AsyncMock()
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.create_pr = AsyncMock(return_value=make_pr_info(101, 42, draft=False))
        mock_prs.add_labels = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        orch._prs = mock_prs

        pr_infos = await orch._push_and_create_prs([result], [issue])

        mock_prs.create_pr.assert_awaited_once()
        call_kwargs = mock_prs.create_pr.call_args
        assert call_kwargs.kwargs.get("draft") is False or (
            len(call_kwargs.args) >= 3 and call_kwargs.args[2] is False
        )
        assert len(pr_infos) == 1
        assert not pr_infos[0].draft

    @pytest.mark.asyncio
    async def test_creates_draft_pr_for_failed_result(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        result = make_worker_result(42, success=False, worktree_path="/tmp/wt/issue-42")

        mock_prs = AsyncMock()
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.create_pr = AsyncMock(return_value=make_pr_info(101, 42, draft=True))
        mock_prs.add_labels = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        orch._prs = mock_prs

        await orch._push_and_create_prs([result], [issue])

        # create_pr should be called with draft=True
        call_kwargs = mock_prs.create_pr.call_args
        assert call_kwargs.kwargs.get("draft") is True

    @pytest.mark.asyncio
    async def test_removes_source_label_and_adds_agent_processed(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        result = make_worker_result(42, success=True, worktree_path="/tmp/wt/issue-42")

        mock_prs = AsyncMock()
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.create_pr = AsyncMock(return_value=make_pr_info(101, 42))
        mock_prs.add_labels = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        orch._prs = mock_prs

        await orch._push_and_create_prs([result], [issue])

        mock_prs.remove_label.assert_awaited_once_with(42, config.label)
        # agent-processed must be in add_labels calls
        all_add_calls = [call.args for call in mock_prs.add_labels.call_args_list]
        all_labels_added = [lbl for _, labels in all_add_calls for lbl in labels]
        assert "agent-processed" in all_labels_added

    @pytest.mark.asyncio
    async def test_adds_needs_review_for_draft_pr(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        result = make_worker_result(42, success=False, worktree_path="/tmp/wt/issue-42")

        mock_prs = AsyncMock()
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.create_pr = AsyncMock(return_value=make_pr_info(101, 42, draft=True))
        mock_prs.add_labels = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        orch._prs = mock_prs

        await orch._push_and_create_prs([result], [issue])

        all_add_calls = [call.args for call in mock_prs.add_labels.call_args_list]
        all_labels_added = [lbl for _, labels in all_add_calls for lbl in labels]
        assert "needs-review" in all_labels_added

    @pytest.mark.asyncio
    async def test_skips_result_when_push_fails(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        result = make_worker_result(42, success=True, worktree_path="/tmp/wt/issue-42")

        mock_prs = AsyncMock()
        mock_prs.push_branch = AsyncMock(return_value=False)
        mock_prs.create_pr = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        mock_prs.remove_label = AsyncMock()
        orch._prs = mock_prs

        pr_infos = await orch._push_and_create_prs([result], [issue])

        assert pr_infos == []
        mock_prs.create_pr.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skips_result_with_no_worktree_path(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        issue = make_issue(42)
        result = WorkerResult(
            issue_number=42,
            branch="agent/issue-42",
            worktree_path="",  # empty / None
            success=True,
        )

        mock_prs = AsyncMock()
        mock_prs.push_branch = AsyncMock()
        mock_prs.create_pr = AsyncMock()
        orch._prs = mock_prs

        pr_infos = await orch._push_and_create_prs([result], [issue])

        assert pr_infos == []
        mock_prs.push_branch.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skips_result_with_no_matching_issue(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        issue = make_issue(99)
        result = make_worker_result(
            42, worktree_path="/tmp/wt/issue-42"
        )  # mismatched issue

        mock_prs = AsyncMock()
        mock_prs.push_branch = AsyncMock()
        mock_prs.create_pr = AsyncMock()
        orch._prs = mock_prs

        pr_infos = await orch._push_and_create_prs([result], [issue])

        assert pr_infos == []
        mock_prs.push_branch.assert_not_awaited()


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
        orch._prs = mock_prs

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
        orch._prs = mock_prs

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
        orch._prs = mock_prs

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


# ---------------------------------------------------------------------------
# _merge_approved
# ---------------------------------------------------------------------------


class TestMergeApproved:
    """Tests for the _merge_approved coroutine."""

    @pytest.mark.asyncio
    async def test_merges_only_approved_prs(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        approved = make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        rejected = make_review_result(102, 43, verdict=ReviewVerdict.REQUEST_CHANGES)
        comment = make_review_result(103, 44, verdict=ReviewVerdict.COMMENT)

        mock_prs = AsyncMock()
        mock_prs.merge_pr = AsyncMock(return_value=True)
        mock_prs.pull_main = AsyncMock()
        orch._prs = mock_prs

        with patch("asyncio.sleep", return_value=None):
            merged = await orch._merge_approved([approved, rejected, comment])

        assert merged == [101]
        mock_prs.merge_pr.assert_awaited_once_with(101)

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_approved(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        reviews = [
            make_review_result(101, 42, verdict=ReviewVerdict.REQUEST_CHANGES),
            make_review_result(102, 43, verdict=ReviewVerdict.COMMENT),
        ]

        mock_prs = AsyncMock()
        mock_prs.merge_pr = AsyncMock(return_value=True)
        mock_prs.pull_main = AsyncMock()
        orch._prs = mock_prs

        merged = await orch._merge_approved(reviews)

        assert merged == []
        mock_prs.merge_pr.assert_not_awaited()
        mock_prs.pull_main.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skips_pr_with_number_zero(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        bad_review = ReviewResult(
            pr_number=0,
            issue_number=42,
            verdict=ReviewVerdict.APPROVE,
        )

        mock_prs = AsyncMock()
        mock_prs.merge_pr = AsyncMock(return_value=True)
        mock_prs.pull_main = AsyncMock()
        orch._prs = mock_prs

        merged = await orch._merge_approved([bad_review])

        assert merged == []
        mock_prs.merge_pr.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_pulls_main_after_successful_merges(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        review = make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)

        mock_prs = AsyncMock()
        mock_prs.merge_pr = AsyncMock(return_value=True)
        mock_prs.pull_main = AsyncMock()
        orch._prs = mock_prs

        with patch("asyncio.sleep", return_value=None):
            await orch._merge_approved([review])

        mock_prs.pull_main.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_pull_main_when_nothing_merged(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        review = make_review_result(101, 42, verdict=ReviewVerdict.REQUEST_CHANGES)

        mock_prs = AsyncMock()
        mock_prs.pull_main = AsyncMock()
        orch._prs = mock_prs

        await orch._merge_approved([review])

        mock_prs.pull_main.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_merge_failure_does_not_add_to_merged(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)
        review = make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)

        mock_prs = AsyncMock()
        mock_prs.merge_pr = AsyncMock(return_value=False)
        mock_prs.pull_main = AsyncMock()
        orch._prs = mock_prs

        with patch("asyncio.sleep", return_value=None):
            merged = await orch._merge_approved([review])

        assert merged == []


# ---------------------------------------------------------------------------
# _cleanup_batch
# ---------------------------------------------------------------------------


class TestCleanupBatch:
    """Tests for the _cleanup_batch coroutine."""

    @pytest.mark.asyncio
    async def test_destroys_worktrees_for_all_issues(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        issues = [make_issue(1), make_issue(2), make_issue(3)]

        mock_wt = AsyncMock()
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        await orch._cleanup_batch(issues)

        assert mock_wt.destroy.await_count == 3
        destroyed_nums = {call.args[0] for call in mock_wt.destroy.call_args_list}
        assert destroyed_nums == {1, 2, 3}

    @pytest.mark.asyncio
    async def test_removes_worktree_from_state(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        issues = [make_issue(42)]
        orch._state.set_worktree(42, "/tmp/wt/issue-42")

        mock_wt = AsyncMock()
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        await orch._cleanup_batch(issues)

        assert orch._state.get_active_worktrees().get(42) is None

    @pytest.mark.asyncio
    async def test_continues_when_destroy_raises(self, config: HydraConfig) -> None:
        """A RuntimeError from destroy should not abort cleanup of other issues."""
        orch = HydraOrchestrator(config)
        issues = [make_issue(1), make_issue(2)]

        mock_wt = AsyncMock()
        mock_wt.destroy = AsyncMock(side_effect=[RuntimeError("gone"), None])
        orch._worktrees = mock_wt

        # Should not raise
        await orch._cleanup_batch(issues)

        assert mock_wt.destroy.await_count == 2

    @pytest.mark.asyncio
    async def test_empty_issue_list_is_a_no_op(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        mock_wt = AsyncMock()
        mock_wt.destroy = AsyncMock()
        orch._worktrees = mock_wt

        await orch._cleanup_batch([])

        mock_wt.destroy.assert_not_awaited()


# ---------------------------------------------------------------------------
# run() loop
# ---------------------------------------------------------------------------


class TestRunLoop:
    """Tests for the main run() orchestrator loop."""

    @pytest.mark.asyncio
    async def test_stops_immediately_when_no_issues_returned(
        self, config: HydraConfig
    ) -> None:
        orch = HydraOrchestrator(config)

        # _fetch_issues always returns empty — loop should break after first iteration
        orch._fetch_issues = AsyncMock(return_value=[])  # type: ignore[method-assign]

        await orch.run()

        orch._fetch_issues.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_publishes_batch_start_event(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        orch._fetch_issues = AsyncMock(return_value=[])  # type: ignore[method-assign]

        published: list[HydraEvent] = []
        original_publish = orch._bus.publish

        async def capturing_publish(event: HydraEvent) -> None:
            published.append(event)
            await original_publish(event)

        orch._bus.publish = capturing_publish  # type: ignore[method-assign]

        await orch.run()

        batch_start_events = [e for e in published if e.type == EventType.BATCH_START]
        assert len(batch_start_events) >= 1

    @pytest.mark.asyncio
    async def test_publishes_phase_change_events(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        orch._fetch_issues = AsyncMock(return_value=[])  # type: ignore[method-assign]

        published: list[HydraEvent] = []
        original_publish = orch._bus.publish

        async def capturing_publish(event: HydraEvent) -> None:
            published.append(event)
            await original_publish(event)

        orch._bus.publish = capturing_publish  # type: ignore[method-assign]

        await orch.run()

        phase_events = [e for e in published if e.type == EventType.PHASE_CHANGE]
        assert len(phase_events) >= 1

    @pytest.mark.asyncio
    async def test_sets_done_phase_at_end(self, config: HydraConfig) -> None:
        orch = HydraOrchestrator(config)
        orch._fetch_issues = AsyncMock(return_value=[])  # type: ignore[method-assign]

        published: list[HydraEvent] = []
        original_publish = orch._bus.publish

        async def capturing_publish(event: HydraEvent) -> None:
            published.append(event)
            await original_publish(event)

        orch._bus.publish = capturing_publish  # type: ignore[method-assign]

        await orch.run()

        phase_values = [
            e.data.get("phase") for e in published if e.type == EventType.PHASE_CHANGE
        ]
        assert "done" in phase_values

    @pytest.mark.asyncio
    async def test_full_batch_cycle_with_one_issue(self, config: HydraConfig) -> None:
        """Run a complete batch cycle end-to-end with all phases mocked."""
        issue = make_issue(42)
        worker_result = make_worker_result(
            42, worktree_path=str(config.worktree_base / "issue-42")
        )
        pr = make_pr_info(101, 42, draft=False)
        review = make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)

        orch = HydraOrchestrator(config)

        # First call returns one issue; second call returns empty to stop the loop
        orch._fetch_issues = AsyncMock(side_effect=[[issue], []])  # type: ignore[method-assign]
        orch._implement_batch = AsyncMock(return_value=[worker_result])  # type: ignore[method-assign]
        orch._push_and_create_prs = AsyncMock(return_value=[pr])  # type: ignore[method-assign]
        orch._review_prs = AsyncMock(return_value=[review])  # type: ignore[method-assign]
        orch._merge_approved = AsyncMock(return_value=[101])  # type: ignore[method-assign]
        orch._cleanup_batch = AsyncMock()  # type: ignore[method-assign]

        await orch.run()

        orch._implement_batch.assert_awaited_once_with([issue])
        orch._push_and_create_prs.assert_awaited_once()
        orch._review_prs.assert_awaited_once()
        orch._merge_approved.assert_awaited_once()
        orch._cleanup_batch.assert_awaited()

    @pytest.mark.asyncio
    async def test_batch_complete_event_published(self, config: HydraConfig) -> None:
        issue = make_issue(42)
        worker_result = make_worker_result(
            42, worktree_path=str(config.worktree_base / "issue-42")
        )
        pr = make_pr_info(101, 42, draft=False)
        review = make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)

        orch = HydraOrchestrator(config)
        orch._fetch_issues = AsyncMock(side_effect=[[issue], []])  # type: ignore[method-assign]
        orch._implement_batch = AsyncMock(return_value=[worker_result])  # type: ignore[method-assign]
        orch._push_and_create_prs = AsyncMock(return_value=[pr])  # type: ignore[method-assign]
        orch._review_prs = AsyncMock(return_value=[review])  # type: ignore[method-assign]
        orch._merge_approved = AsyncMock(return_value=[101])  # type: ignore[method-assign]
        orch._cleanup_batch = AsyncMock()  # type: ignore[method-assign]

        published: list[HydraEvent] = []
        original_publish = orch._bus.publish

        async def capturing_publish(event: HydraEvent) -> None:
            published.append(event)
            await original_publish(event)

        orch._bus.publish = capturing_publish  # type: ignore[method-assign]

        await orch.run()

        complete_events = [e for e in published if e.type == EventType.BATCH_COMPLETE]
        assert len(complete_events) == 1
        data = complete_events[0].data
        assert "batch" in data
        assert "merged" in data

    @pytest.mark.asyncio
    async def test_increments_batch_counter_each_iteration(
        self, config: HydraConfig
    ) -> None:
        issue = make_issue(42)

        orch = HydraOrchestrator(config)
        # Returns [issue] twice (two full cycles), then [] to stop.
        # The loop increments the batch counter BEFORE fetching, so when
        # the empty list is returned the counter has already been bumped to 3.
        orch._fetch_issues = AsyncMock(side_effect=[[issue], [issue], []])  # type: ignore[method-assign]
        orch._implement_batch = AsyncMock(return_value=[make_worker_result(42)])  # type: ignore[method-assign]
        orch._push_and_create_prs = AsyncMock(return_value=[])  # type: ignore[method-assign]
        orch._review_prs = AsyncMock(return_value=[])  # type: ignore[method-assign]
        orch._merge_approved = AsyncMock(return_value=[])  # type: ignore[method-assign]
        orch._cleanup_batch = AsyncMock()  # type: ignore[method-assign]

        await orch.run()

        # 3 iterations were started (2 productive + 1 empty-stop), so batch == 3
        assert orch._state.get_current_batch() == 3
