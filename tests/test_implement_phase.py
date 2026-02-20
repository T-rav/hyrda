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
