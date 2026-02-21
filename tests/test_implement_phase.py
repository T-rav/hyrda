"""Tests for implement_phase.py - ImplementPhase class."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config import HydraConfig

from implement_phase import ImplementPhase
from models import (
    GitHubIssue,
    PRInfo,
    WorkerResult,
)

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


def _make_phase(
    config: HydraConfig,
    issues: list[GitHubIssue],
    *,
    agent_run: Any | None = None,
    success: bool = True,
    push_return: bool = True,
    create_pr_return: PRInfo | None = None,
) -> tuple[ImplementPhase, AsyncMock, AsyncMock]:
    """Build an ImplementPhase with standard mocks.

    Returns ``(phase, mock_wt, mock_prs)``.
    """
    from state import StateTracker

    state = StateTracker(config.state_file)
    stop_event = asyncio.Event()
    active_issues: set[int] = set()

    if agent_run is None:

        async def _default_agent_run(
            issue: GitHubIssue,
            wt_path: Path,
            branch: str,
            worker_id: int = 0,
            review_feedback: str = "",
        ) -> WorkerResult:
            return make_worker_result(
                issue_number=issue.number,
                success=success,
                worktree_path=str(wt_path),
            )

        agent_run = _default_agent_run

    mock_agents = AsyncMock()
    mock_agents.run = agent_run

    mock_fetcher = AsyncMock()
    mock_fetcher.fetch_ready_issues = AsyncMock(return_value=issues)

    mock_wt = AsyncMock()
    mock_wt.create = AsyncMock(
        side_effect=lambda num, branch: config.worktree_base / f"issue-{num}"
    )

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

    phase = ImplementPhase(
        config=config,
        state=state,
        worktrees=mock_wt,
        agents=mock_agents,
        prs=mock_prs,
        fetcher=mock_fetcher,
        stop_event=stop_event,
        active_issues=active_issues,
    )

    return phase, mock_wt, mock_prs


# ---------------------------------------------------------------------------
# run_batch
# ---------------------------------------------------------------------------


class TestImplementBatch:
    """Tests for the ImplementPhase.run_batch method."""

    @pytest.mark.asyncio
    async def test_returns_worker_results_for_each_issue(
        self, config: HydraConfig
    ) -> None:
        issues = [make_issue(1), make_issue(2)]

        expected = [
            make_worker_result(
                issue_number=1,
                worktree_path=str(config.worktree_base / "issue-1"),
            ),
            make_worker_result(
                issue_number=2,
                worktree_path=str(config.worktree_base / "issue-2"),
            ),
        ]

        async def fake_agent_run(
            issue: GitHubIssue,
            wt_path: Path,
            branch: str,
            worker_id: int = 0,
            review_feedback: str = "",
        ) -> WorkerResult:
            return next(r for r in expected if r.issue_number == issue.number)

        phase, _, _ = _make_phase(config, issues, agent_run=fake_agent_run)

        returned, fetched = await phase.run_batch()
        assert len(returned) == 2
        issue_numbers = {r.issue_number for r in returned}
        assert issue_numbers == {1, 2}
        assert fetched == issues

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self, config: HydraConfig) -> None:
        """max_workers=2 means at most 2 agents run concurrently."""
        concurrency_counter = {"current": 0, "peak": 0}

        async def fake_agent_run(
            issue: GitHubIssue,
            wt_path: Path,
            branch: str,
            worker_id: int = 0,
            review_feedback: str = "",
        ) -> WorkerResult:
            concurrency_counter["current"] += 1
            concurrency_counter["peak"] = max(
                concurrency_counter["peak"],
                concurrency_counter["current"],
            )
            await asyncio.sleep(0)  # yield
            concurrency_counter["current"] -= 1
            return make_worker_result(
                issue_number=issue.number, worktree_path=str(wt_path)
            )

        issues = [make_issue(i) for i in range(1, 6)]

        phase, _, _ = _make_phase(config, issues, agent_run=fake_agent_run)

        await phase.run_batch()

        assert concurrency_counter["peak"] <= config.max_workers

    @pytest.mark.asyncio
    async def test_marks_issue_in_progress_then_done(self, config: HydraConfig) -> None:
        issue = make_issue(55)

        phase, _, _ = _make_phase(config, [issue])

        await phase.run_batch()

        status = phase._state.get_issue_status(55)
        assert status == "success"

    @pytest.mark.asyncio
    async def test_marks_issue_failed_when_agent_fails(
        self, config: HydraConfig
    ) -> None:
        issue = make_issue(66)

        phase, _, _ = _make_phase(config, [issue], success=False)

        await phase.run_batch()

        status = phase._state.get_issue_status(66)
        assert status == "failed"

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_issues(self, config: HydraConfig) -> None:
        """When fetch_ready_issues returns empty, return ([], [])."""
        phase, _, _ = _make_phase(config, [])

        results, issues = await phase.run_batch()

        assert results == []
        assert issues == []

    @pytest.mark.asyncio
    async def test_resumes_existing_worktree(self, config: HydraConfig) -> None:
        """If worktree dir already exists, skip create and reuse it."""
        issue = make_issue(77)

        # Pre-create worktree directory to simulate resume
        wt_path = config.worktree_base / "issue-77"
        wt_path.mkdir(parents=True, exist_ok=True)

        phase, mock_wt, _ = _make_phase(
            config, [issue], create_pr_return=make_pr_info(101, 77)
        )

        await phase.run_batch()

        # create should NOT have been called since worktree already exists
        mock_wt.create.assert_not_awaited()


# ---------------------------------------------------------------------------
# Implement includes push + PR creation
# ---------------------------------------------------------------------------


class TestImplementIncludesPush:
    """Tests that run_batch pushes and creates PRs per worker."""

    @pytest.mark.asyncio
    async def test_worker_result_contains_pr_info(self, config: HydraConfig) -> None:
        """After implementation, worker result should contain pr_info."""
        issue = make_issue(42)

        phase, _, _ = _make_phase(
            config, [issue], create_pr_return=make_pr_info(101, 42)
        )

        results, _ = await phase.run_batch()

        assert len(results) == 1
        assert results[0].pr_info is not None
        assert results[0].pr_info.number == 101

    @pytest.mark.asyncio
    async def test_worker_creates_draft_pr_on_failure(
        self, config: HydraConfig
    ) -> None:
        """When agent fails, PR should be created as draft and label kept."""
        issue = make_issue(42)

        phase, _, mock_prs = _make_phase(
            config,
            [issue],
            success=False,
            create_pr_return=make_pr_info(101, 42, draft=True),
        )

        await phase.run_batch()

        call_kwargs = mock_prs.create_pr.call_args
        assert call_kwargs.kwargs.get("draft") is True

        # On failure: should NOT remove hydra-ready or add hydra-review
        mock_prs.remove_label.assert_not_awaited()
        add_calls = [c.args for c in mock_prs.add_labels.call_args_list]
        assert (42, ["hydra-review"]) not in add_calls

    @pytest.mark.asyncio
    async def test_worker_no_pr_when_push_fails(self, config: HydraConfig) -> None:
        """When push fails, pr_info should remain None."""
        issue = make_issue(42)

        phase, _, mock_prs = _make_phase(config, [issue], push_return=False)

        results, _ = await phase.run_batch()

        assert results[0].pr_info is None
        mock_prs.create_pr.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_branch_pushed_and_commented_before_agent_runs(
        self, config: HydraConfig
    ) -> None:
        """Branch should be pushed and a comment posted before the agent starts."""
        issue = make_issue(42)

        call_order: list[str] = []

        async def fake_push(wt_path: Path, branch: str) -> bool:
            call_order.append("push")
            return True

        async def fake_comment(issue_number: int, body: str) -> None:
            call_order.append("comment")

        async def fake_agent_run(
            issue: GitHubIssue,
            wt_path: Path,
            branch: str,
            worker_id: int = 0,
            review_feedback: str = "",
        ) -> WorkerResult:
            call_order.append("agent")
            return make_worker_result(
                issue_number=issue.number,
                success=True,
                worktree_path=str(wt_path),
            )

        phase, _, mock_prs = _make_phase(
            config,
            [issue],
            agent_run=fake_agent_run,
            create_pr_return=make_pr_info(101, 42),
        )
        mock_prs.push_branch = fake_push
        mock_prs.post_comment = fake_comment

        await phase.run_batch()

        # push and comment must happen before agent
        assert call_order.index("push") < call_order.index("agent")
        assert call_order.index("comment") < call_order.index("agent")

    @pytest.mark.asyncio
    async def test_releases_active_issues_for_review(self, config: HydraConfig) -> None:
        """After implementation, issue should be removed from active_issues
        so the review loop can pick it up."""
        issue = make_issue(42)

        phase, _, _ = _make_phase(config, [issue])

        results, _ = await phase.run_batch()

        assert len(results) == 1
        assert results[0].success is True
        # Issue should have been released from active_issues
        assert 42 not in phase._active_issues


# ---------------------------------------------------------------------------
# Worker exception isolation
# ---------------------------------------------------------------------------


class TestWorkerExceptionIsolation:
    """Tests that _worker catches exceptions and returns failed results."""

    @pytest.mark.asyncio
    async def test_worker_exception_returns_failed_result(
        self, config: HydraConfig
    ) -> None:
        """When agent.run raises, worker should return a WorkerResult with error."""
        issue = make_issue(42)

        async def crashing_agent(
            issue: GitHubIssue,
            wt_path: Path,
            branch: str,
            worker_id: int = 0,
            review_feedback: str = "",
        ) -> WorkerResult:
            raise RuntimeError("agent crashed")

        phase, _, _ = _make_phase(config, [issue], agent_run=crashing_agent)

        results, _ = await phase.run_batch()

        assert len(results) == 1
        assert results[0].success is False
        assert results[0].error is not None
        assert "Worker exception" in results[0].error

    @pytest.mark.asyncio
    async def test_worker_exception_marks_issue_failed(
        self, config: HydraConfig
    ) -> None:
        """When worker crashes, issue should be marked as 'failed' in state."""
        issue = make_issue(42)

        async def crashing_agent(
            issue: GitHubIssue,
            wt_path: Path,
            branch: str,
            worker_id: int = 0,
            review_feedback: str = "",
        ) -> WorkerResult:
            raise RuntimeError("agent crashed")

        phase, _, _ = _make_phase(config, [issue], agent_run=crashing_agent)

        await phase.run_batch()

        assert phase._state.get_issue_status(42) == "failed"

    @pytest.mark.asyncio
    async def test_worker_exception_releases_active_issues(
        self, config: HydraConfig
    ) -> None:
        """When worker crashes, issue should be removed from active_issues."""
        issue = make_issue(42)

        async def crashing_agent(
            issue: GitHubIssue,
            wt_path: Path,
            branch: str,
            worker_id: int = 0,
            review_feedback: str = "",
        ) -> WorkerResult:
            raise RuntimeError("agent crashed")

        phase, _, _ = _make_phase(config, [issue], agent_run=crashing_agent)

        await phase.run_batch()

        assert 42 not in phase._active_issues

    @pytest.mark.asyncio
    async def test_worker_exception_does_not_crash_batch(
        self, config: HydraConfig
    ) -> None:
        """With 2 issues, first worker crashing should not prevent the second."""
        issues = [make_issue(1), make_issue(2)]

        call_count = 0

        async def sometimes_crashing_agent(
            issue: GitHubIssue,
            wt_path: Path,
            branch: str,
            worker_id: int = 0,
            review_feedback: str = "",
        ) -> WorkerResult:
            nonlocal call_count
            call_count += 1
            if issue.number == 1:
                raise RuntimeError("agent crashed for issue 1")
            return make_worker_result(
                issue_number=issue.number,
                success=True,
                worktree_path=str(wt_path),
            )

        phase, _, _ = _make_phase(config, issues, agent_run=sometimes_crashing_agent)

        results, _ = await phase.run_batch()

        # Both results should be returned
        assert len(results) == 2
        issue_numbers = {r.issue_number for r in results}
        assert issue_numbers == {1, 2}
        # Issue 1 failed, issue 2 succeeded
        result_map = {r.issue_number: r for r in results}
        assert result_map[1].success is False
        assert result_map[1].error is not None
        assert result_map[2].success is True


# ---------------------------------------------------------------------------
# Lifecycle metric recording
# ---------------------------------------------------------------------------


class TestImplementLifecycleMetrics:
    """Tests that run_batch records new lifecycle metrics in state."""

    @pytest.mark.asyncio
    async def test_records_implementation_duration(self, config: HydraConfig) -> None:
        """Successful implementation should record duration in state."""
        issue = make_issue(42)

        async def agent_with_duration(
            issue: GitHubIssue,
            wt_path: Path,
            branch: str,
            worker_id: int = 0,
            review_feedback: str = "",
        ) -> WorkerResult:
            return WorkerResult(
                issue_number=issue.number,
                branch=branch,
                success=True,
                worktree_path=str(wt_path),
                duration_seconds=60.5,
            )

        phase, _, _ = _make_phase(config, [issue], agent_run=agent_with_duration)
        await phase.run_batch()

        stats = phase._state.get_lifetime_stats()
        assert stats["total_implementation_seconds"] == pytest.approx(60.5)

    @pytest.mark.asyncio
    async def test_does_not_record_zero_duration(self, config: HydraConfig) -> None:
        """Zero duration should not be recorded."""
        issue = make_issue(42)

        async def agent_zero_duration(
            issue: GitHubIssue,
            wt_path: Path,
            branch: str,
            worker_id: int = 0,
            review_feedback: str = "",
        ) -> WorkerResult:
            return WorkerResult(
                issue_number=issue.number,
                branch=branch,
                success=True,
                worktree_path=str(wt_path),
                duration_seconds=0.0,
            )

        phase, _, _ = _make_phase(config, [issue], agent_run=agent_zero_duration)
        await phase.run_batch()

        stats = phase._state.get_lifetime_stats()
        assert stats["total_implementation_seconds"] == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_records_quality_fix_rounds(self, config: HydraConfig) -> None:
        """Quality fix attempts should be recorded in state."""
        issue = make_issue(42)

        async def agent_with_qf(
            issue: GitHubIssue,
            wt_path: Path,
            branch: str,
            worker_id: int = 0,
            review_feedback: str = "",
        ) -> WorkerResult:
            return WorkerResult(
                issue_number=issue.number,
                branch=branch,
                success=True,
                worktree_path=str(wt_path),
                quality_fix_attempts=2,
            )

        phase, _, _ = _make_phase(config, [issue], agent_run=agent_with_qf)
        await phase.run_batch()

        stats = phase._state.get_lifetime_stats()
        assert stats["total_quality_fix_rounds"] == 2

    @pytest.mark.asyncio
    async def test_does_not_record_zero_quality_fix_rounds(
        self, config: HydraConfig
    ) -> None:
        """Zero quality fix attempts should not be recorded."""
        issue = make_issue(42)

        phase, _, _ = _make_phase(config, [issue])
        await phase.run_batch()

        stats = phase._state.get_lifetime_stats()
        assert stats["total_quality_fix_rounds"] == 0

    @pytest.mark.asyncio
    async def test_accumulates_across_multiple_issues(
        self, config: HydraConfig
    ) -> None:
        """Metrics should accumulate across multiple issues in a batch."""
        issues = [make_issue(1), make_issue(2)]

        async def agent_with_metrics(
            issue: GitHubIssue,
            wt_path: Path,
            branch: str,
            worker_id: int = 0,
            review_feedback: str = "",
        ) -> WorkerResult:
            return WorkerResult(
                issue_number=issue.number,
                branch=branch,
                success=True,
                worktree_path=str(wt_path),
                duration_seconds=30.0,
                quality_fix_attempts=1,
            )

        phase, _, _ = _make_phase(config, issues, agent_run=agent_with_metrics)
        await phase.run_batch()

        stats = phase._state.get_lifetime_stats()
        assert stats["total_implementation_seconds"] == pytest.approx(60.0)
        assert stats["total_quality_fix_rounds"] == 2


# ---------------------------------------------------------------------------
# Review feedback passing
# ---------------------------------------------------------------------------


class TestReviewFeedbackPassing:
    """Tests that review feedback is fetched, passed to agent, and cleared."""

    @pytest.mark.asyncio
    async def test_passes_review_feedback_to_agent(self, config: HydraConfig) -> None:
        """When review feedback exists in state, it should be passed to agent.run."""
        issue = make_issue(42)
        captured_feedback: list[str] = []

        async def capturing_agent(
            issue: GitHubIssue,
            wt_path: Path,
            branch: str,
            worker_id: int = 0,
            review_feedback: str = "",
        ) -> WorkerResult:
            captured_feedback.append(review_feedback)
            return make_worker_result(
                issue_number=issue.number,
                success=True,
                worktree_path=str(wt_path),
            )

        phase, _, _ = _make_phase(
            config,
            [issue],
            agent_run=capturing_agent,
            create_pr_return=make_pr_info(101, 42),
        )
        # Set review feedback in state before running
        phase._state.set_review_feedback(42, "Fix the error handling")

        await phase.run_batch()

        assert len(captured_feedback) == 1
        assert captured_feedback[0] == "Fix the error handling"

    @pytest.mark.asyncio
    async def test_clears_review_feedback_after_implementation(
        self, config: HydraConfig
    ) -> None:
        """Review feedback should be cleared from state after agent run."""
        issue = make_issue(42)

        async def simple_agent(
            issue: GitHubIssue,
            wt_path: Path,
            branch: str,
            worker_id: int = 0,
            review_feedback: str = "",
        ) -> WorkerResult:
            return make_worker_result(
                issue_number=issue.number,
                success=True,
                worktree_path=str(wt_path),
            )

        phase, _, _ = _make_phase(
            config,
            [issue],
            agent_run=simple_agent,
            create_pr_return=make_pr_info(101, 42),
        )
        phase._state.set_review_feedback(42, "Fix the tests")

        await phase.run_batch()

        # Feedback should be cleared
        assert phase._state.get_review_feedback(42) is None

    @pytest.mark.asyncio
    async def test_no_feedback_passes_empty_string(self, config: HydraConfig) -> None:
        """When no review feedback exists, agent should receive empty string."""
        issue = make_issue(42)
        captured_feedback: list[str] = []

        async def capturing_agent(
            issue: GitHubIssue,
            wt_path: Path,
            branch: str,
            worker_id: int = 0,
            review_feedback: str = "",
        ) -> WorkerResult:
            captured_feedback.append(review_feedback)
            return make_worker_result(
                issue_number=issue.number,
                success=True,
                worktree_path=str(wt_path),
            )

        phase, _, _ = _make_phase(
            config,
            [issue],
            agent_run=capturing_agent,
            create_pr_return=make_pr_info(101, 42),
        )
        # Do NOT set any feedback

        await phase.run_batch()

        assert len(captured_feedback) == 1
        assert captured_feedback[0] == ""

    @pytest.mark.asyncio
    async def test_skips_pr_creation_on_retry(self, config: HydraConfig) -> None:
        """When review_feedback is present (retry), PR creation should be skipped."""
        issue = make_issue(42)

        async def simple_agent(
            issue: GitHubIssue,
            wt_path: Path,
            branch: str,
            worker_id: int = 0,
            review_feedback: str = "",
        ) -> WorkerResult:
            return make_worker_result(
                issue_number=issue.number,
                success=True,
                worktree_path=str(wt_path),
            )

        phase, _, mock_prs = _make_phase(
            config,
            [issue],
            agent_run=simple_agent,
            create_pr_return=make_pr_info(101, 42),
        )
        # Set review feedback to simulate a retry cycle
        phase._state.set_review_feedback(42, "Fix error handling")

        results, _ = await phase.run_batch()

        # PR creation should be skipped on retry
        mock_prs.create_pr.assert_not_awaited()
        # But result should still be successful
        assert results[0].success is True
        # pr_info should be None since PR creation was skipped
        assert results[0].pr_info is None

    @pytest.mark.asyncio
    async def test_creates_pr_on_first_run(self, config: HydraConfig) -> None:
        """Without review feedback (first run), PR should be created normally."""
        issue = make_issue(42)

        async def simple_agent(
            issue: GitHubIssue,
            wt_path: Path,
            branch: str,
            worker_id: int = 0,
            review_feedback: str = "",
        ) -> WorkerResult:
            return make_worker_result(
                issue_number=issue.number,
                success=True,
                worktree_path=str(wt_path),
            )

        phase, _, mock_prs = _make_phase(
            config,
            [issue],
            agent_run=simple_agent,
            create_pr_return=make_pr_info(101, 42),
        )
        # No review feedback — first run

        results, _ = await phase.run_batch()

        # PR creation should happen
        mock_prs.create_pr.assert_awaited_once()
        assert results[0].pr_info is not None
        assert results[0].pr_info.number == 101


# ---------------------------------------------------------------------------
# Worker result metadata persistence
# ---------------------------------------------------------------------------


class TestWorkerResultMetaPersistence:
    """Tests that worker result metadata is persisted to state."""

    @pytest.mark.asyncio
    async def test_worker_result_meta_persisted_after_run(
        self, config: HydraConfig
    ) -> None:
        """Worker result metadata should be saved to state after agent run."""
        issue = make_issue(42)

        async def agent_with_metrics(
            issue: GitHubIssue,
            wt_path: Path,
            branch: str,
            worker_id: int = 0,
            review_feedback: str = "",
        ) -> WorkerResult:
            return WorkerResult(
                issue_number=issue.number,
                branch=branch,
                success=True,
                worktree_path=str(wt_path),
                quality_fix_attempts=2,
                duration_seconds=150.5,
                error=None,
            )

        phase, _, _ = _make_phase(config, [issue], agent_run=agent_with_metrics)

        await phase.run_batch()

        meta = phase._state.get_worker_result_meta(42)
        assert meta["quality_fix_attempts"] == 2
        assert meta["duration_seconds"] == 150.5
        assert meta["error"] is None

    @pytest.mark.asyncio
    async def test_worker_result_meta_includes_error(self, config: HydraConfig) -> None:
        """When agent fails, error should be captured in metadata."""
        issue = make_issue(42)

        async def failing_agent(
            issue: GitHubIssue,
            wt_path: Path,
            branch: str,
            worker_id: int = 0,
            review_feedback: str = "",
        ) -> WorkerResult:
            return WorkerResult(
                issue_number=issue.number,
                branch=branch,
                success=False,
                worktree_path=str(wt_path),
                quality_fix_attempts=0,
                duration_seconds=30.0,
                error="make quality failed",
            )

        phase, _, _ = _make_phase(config, [issue], agent_run=failing_agent)

        await phase.run_batch()

        meta = phase._state.get_worker_result_meta(42)
        assert meta["error"] == "make quality failed"


# ---------------------------------------------------------------------------
# Zero-commit already-satisfied handling
# ---------------------------------------------------------------------------


class TestAlreadySatisfiedZeroCommit:
    """Tests that zero-commit failures close the issue as already satisfied."""

    @pytest.mark.asyncio
    async def test_zero_commit_closes_issue_with_dup_label(
        self, config: HydraConfig
    ) -> None:
        """When agent returns zero commits, issue should be closed with dup label."""
        issue = make_issue(42)

        async def zero_commit_agent(
            issue: GitHubIssue,
            wt_path: Path,
            branch: str,
            worker_id: int = 0,
            review_feedback: str = "",
        ) -> WorkerResult:
            return WorkerResult(
                issue_number=issue.number,
                branch=branch,
                success=False,
                error="No commits found on branch",
                commits=0,
                worktree_path=str(wt_path),
            )

        phase, _, mock_prs = _make_phase(config, [issue], agent_run=zero_commit_agent)
        mock_prs.close_issue = AsyncMock()

        results, _ = await phase.run_batch()

        # dup labels should be added
        add_calls = [c.args for c in mock_prs.add_labels.call_args_list]
        assert any(config.dup_label == c[1] for c in add_calls)

        # Comment should be posted with "Already Satisfied"
        comment_calls = [c.args for c in mock_prs.post_comment.call_args_list]
        assert any("Already Satisfied" in c[1] for c in comment_calls)

        # Issue should be closed
        mock_prs.close_issue.assert_awaited_once_with(42)

    @pytest.mark.asyncio
    async def test_zero_commit_marks_issue_already_satisfied(
        self, config: HydraConfig
    ) -> None:
        """When zero-commit detected, issue state should be 'already_satisfied'."""
        issue = make_issue(42)

        async def zero_commit_agent(
            issue: GitHubIssue,
            wt_path: Path,
            branch: str,
            worker_id: int = 0,
            review_feedback: str = "",
        ) -> WorkerResult:
            return WorkerResult(
                issue_number=issue.number,
                branch=branch,
                success=False,
                error="No commits found on branch",
                commits=0,
                worktree_path=str(wt_path),
            )

        phase, _, mock_prs = _make_phase(config, [issue], agent_run=zero_commit_agent)
        mock_prs.close_issue = AsyncMock()

        await phase.run_batch()

        assert phase._state.get_issue_status(42) == "already_satisfied"

    @pytest.mark.asyncio
    async def test_zero_commit_removes_ready_labels(self, config: HydraConfig) -> None:
        """When zero-commit detected, ready labels should be removed."""
        issue = make_issue(42)

        async def zero_commit_agent(
            issue: GitHubIssue,
            wt_path: Path,
            branch: str,
            worker_id: int = 0,
            review_feedback: str = "",
        ) -> WorkerResult:
            return WorkerResult(
                issue_number=issue.number,
                branch=branch,
                success=False,
                error="No commits found on branch",
                commits=0,
                worktree_path=str(wt_path),
            )

        phase, _, mock_prs = _make_phase(config, [issue], agent_run=zero_commit_agent)
        mock_prs.close_issue = AsyncMock()

        await phase.run_batch()

        remove_calls = [c.args for c in mock_prs.remove_label.call_args_list]
        for lbl in config.ready_label:
            assert (42, lbl) in remove_calls

    @pytest.mark.asyncio
    async def test_nonzero_commits_not_treated_as_already_satisfied(
        self, config: HydraConfig
    ) -> None:
        """A failed result with commits > 0 should NOT be treated as already satisfied."""
        issue = make_issue(42)

        async def failing_with_commits(
            issue: GitHubIssue,
            wt_path: Path,
            branch: str,
            worker_id: int = 0,
            review_feedback: str = "",
        ) -> WorkerResult:
            return WorkerResult(
                issue_number=issue.number,
                branch=branch,
                success=False,
                error="make quality failed",
                commits=2,
                worktree_path=str(wt_path),
            )

        phase, _, mock_prs = _make_phase(
            config, [issue], agent_run=failing_with_commits
        )
        mock_prs.close_issue = AsyncMock()

        await phase.run_batch()

        # Should NOT close the issue
        mock_prs.close_issue.assert_not_awaited()
        assert phase._state.get_issue_status(42) == "failed"


# ---------------------------------------------------------------------------
# Retry cap escalation
# ---------------------------------------------------------------------------


class TestRetryCapEscalation:
    """Tests that issues exceeding max_issue_attempts escalate to HITL."""

    @pytest.mark.asyncio
    async def test_issue_under_cap_proceeds_normally(self, tmp_path: Path) -> None:
        """Issues under the cap should proceed to agent run."""
        from tests.helpers import ConfigFactory

        config = ConfigFactory.create(
            max_issue_attempts=3,
            repo_root=tmp_path / "repo",
            worktree_base=tmp_path / "worktrees",
            state_file=tmp_path / "state.json",
        )
        issue = make_issue(42)
        phase, _, _ = _make_phase(config, [issue])

        # Pre-set 1 attempt (will be incremented to 2, still under cap of 3)
        phase._state.increment_issue_attempts(42)

        results, _ = await phase.run_batch()

        assert len(results) == 1
        assert results[0].success is True
        assert phase._state.get_issue_attempts(42) == 2

    @pytest.mark.asyncio
    async def test_issue_at_cap_escalates_to_hitl(self, tmp_path: Path) -> None:
        """Issues at the cap should escalate to HITL without running the agent."""
        from tests.helpers import ConfigFactory

        config = ConfigFactory.create(
            max_issue_attempts=2,
            repo_root=tmp_path / "repo",
            worktree_base=tmp_path / "worktrees",
            state_file=tmp_path / "state.json",
        )
        issue = make_issue(42)

        agent_called = False

        async def tracking_agent(
            issue: GitHubIssue,
            wt_path: Path,
            branch: str,
            worker_id: int = 0,
            review_feedback: str = "",
        ) -> WorkerResult:
            nonlocal agent_called
            agent_called = True
            return make_worker_result(
                issue_number=issue.number,
                success=True,
                worktree_path=str(wt_path),
            )

        phase, _, mock_prs = _make_phase(config, [issue], agent_run=tracking_agent)

        # Pre-set attempts to match cap (2), so next increment = 3 > 2
        phase._state.increment_issue_attempts(42)
        phase._state.increment_issue_attempts(42)

        results, _ = await phase.run_batch()

        assert len(results) == 1
        assert results[0].success is False
        assert "attempt cap exceeded" in (results[0].error or "")
        assert not agent_called

        # Labels should be swapped to HITL
        add_calls = [c.args for c in mock_prs.add_labels.call_args_list]
        assert any(c[1] == ["hydra-hitl"] for c in add_calls)

        # Comment should mention attempt cap
        comment_calls = [c.args for c in mock_prs.post_comment.call_args_list]
        assert any("attempt cap exceeded" in c[1] for c in comment_calls)

        # HITL origin and cause should be set
        assert phase._state.get_hitl_origin(42) is not None
        assert phase._state.get_hitl_cause(42) is not None

    @pytest.mark.asyncio
    async def test_boundary_attempt_proceeds(self, tmp_path: Path) -> None:
        """With max_issue_attempts=3, the 3rd attempt should proceed (not escalate)."""
        from tests.helpers import ConfigFactory

        config = ConfigFactory.create(
            max_issue_attempts=3,
            repo_root=tmp_path / "repo",
            worktree_base=tmp_path / "worktrees",
            state_file=tmp_path / "state.json",
        )
        issue = make_issue(42)
        phase, _, _ = _make_phase(config, [issue])

        # Pre-set 2 attempts; next increment = 3 == max, should proceed
        phase._state.increment_issue_attempts(42)
        phase._state.increment_issue_attempts(42)

        results, _ = await phase.run_batch()

        assert len(results) == 1
        assert results[0].success is True
        assert phase._state.get_issue_attempts(42) == 3


# ---------------------------------------------------------------------------
# Commits persisted in worker result metadata
# ---------------------------------------------------------------------------


class TestCommitsPersistedInMeta:
    """Tests that commits field is included in worker_result_meta."""

    @pytest.mark.asyncio
    async def test_commits_in_worker_result_meta(self, config: HydraConfig) -> None:
        """After agent run, worker_result_meta should contain 'commits' key."""
        issue = make_issue(42)

        async def agent_with_commits(
            issue: GitHubIssue,
            wt_path: Path,
            branch: str,
            worker_id: int = 0,
            review_feedback: str = "",
        ) -> WorkerResult:
            return WorkerResult(
                issue_number=issue.number,
                branch=branch,
                success=True,
                worktree_path=str(wt_path),
                commits=3,
                quality_fix_attempts=1,
                duration_seconds=90.0,
            )

        phase, _, _ = _make_phase(config, [issue], agent_run=agent_with_commits)

        await phase.run_batch()

        meta = phase._state.get_worker_result_meta(42)
        assert meta["commits"] == 3
        assert meta["quality_fix_attempts"] == 1
        assert meta["duration_seconds"] == 90.0


# ---------------------------------------------------------------------------
# Active issue persistence
# ---------------------------------------------------------------------------


class TestActiveIssuePersistence:
    """Tests that active issues are persisted to state."""

    @pytest.mark.asyncio
    async def test_active_issue_persisted_and_removed(
        self, config: HydraConfig
    ) -> None:
        """After run_batch, active_issue_numbers should be cleared."""
        issue = make_issue(42)
        phase, _, _ = _make_phase(config, [issue])

        await phase.run_batch()

        # After completion, issue should not be in active list
        active = phase._state.get_active_issue_numbers()
        assert 42 not in active
