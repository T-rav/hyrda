"""Tests for review_phase.py - ReviewPhase class."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config import HydraConfig

from models import (
    GitHubIssue,
    PRInfo,
    ReviewResult,
    ReviewVerdict,
)
from review_phase import ReviewPhase
from state import StateTracker

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


def _make_phase(config: HydraConfig) -> ReviewPhase:
    """Build a ReviewPhase with standard dependencies."""
    state = StateTracker(config.state_file)
    stop_event = asyncio.Event()
    active_issues: set[int] = set()

    mock_wt = AsyncMock()
    mock_wt.destroy = AsyncMock()

    mock_reviewers = AsyncMock()
    mock_prs = AsyncMock()

    phase = ReviewPhase(
        config=config,
        state=state,
        worktrees=mock_wt,
        reviewers=mock_reviewers,
        prs=mock_prs,
        stop_event=stop_event,
        active_issues=active_issues,
    )

    return phase


# ---------------------------------------------------------------------------
# review_prs
# ---------------------------------------------------------------------------


class TestReviewPRs:
    """Tests for the ReviewPhase.review_prs method."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_prs(self, config: HydraConfig) -> None:
        phase = _make_phase(config)
        results = await phase.review_prs([], [make_issue()])
        assert results == []

    @pytest.mark.asyncio
    async def test_reviews_non_draft_prs(self, config: HydraConfig) -> None:
        phase = _make_phase(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        phase._reviewers.review = AsyncMock(return_value=make_review_result(101, 42))
        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=True)
        phase._prs.remove_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()

        # Ensure worktree path exists
        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await phase.review_prs([pr], [issue])

        phase._reviewers.review.assert_awaited_once()
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_marks_pr_status_in_state(self, config: HydraConfig) -> None:
        phase = _make_phase(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        phase._reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=True)
        phase._prs.remove_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs([pr], [issue])

        assert phase._state.get_pr_status(101) == "approve"

    @pytest.mark.asyncio
    async def test_reviewer_concurrency_limited_by_config_max_reviewers(
        self, config: HydraConfig
    ) -> None:
        """At most config.max_reviewers concurrent reviews."""
        concurrency_counter = {"current": 0, "peak": 0}

        async def fake_review(pr, issue, wt_path, diff, worker_id=0):
            concurrency_counter["current"] += 1
            concurrency_counter["peak"] = max(
                concurrency_counter["peak"],
                concurrency_counter["current"],
            )
            await asyncio.sleep(0)
            concurrency_counter["current"] -= 1
            return make_review_result(pr.number, issue.number)

        phase = _make_phase(config)
        phase._reviewers.review = fake_review  # type: ignore[method-assign]

        phase._prs.get_pr_diff = AsyncMock(return_value="diff")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=True)
        phase._prs.remove_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()

        issues = [make_issue(i) for i in range(1, 7)]
        prs = [make_pr_info(100 + i, i, draft=False) for i in range(1, 7)]

        for i in range(1, 7):
            wt = config.worktree_base / f"issue-{i}"
            wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs(prs, issues)

        assert concurrency_counter["peak"] <= config.max_reviewers

    @pytest.mark.asyncio
    async def test_returns_comment_verdict_when_issue_missing(
        self, config: HydraConfig
    ) -> None:
        phase = _make_phase(config)
        # PR with issue_number not in issue_map
        pr = make_pr_info(101, 999, draft=False)

        phase._prs.get_pr_diff = AsyncMock(return_value="diff")

        # Worktree for issue-999 exists
        wt = config.worktree_base / "issue-999"
        wt.mkdir(parents=True, exist_ok=True)

        results = await phase.review_prs([pr], [])  # no matching issues

        assert len(results) == 1
        assert results[0].pr_number == 101
        assert results[0].summary == "Issue not found"

    @pytest.mark.asyncio
    async def test_review_merges_approved_pr(self, config: HydraConfig) -> None:
        """review_prs should merge PRs that the reviewer approves."""
        phase = _make_phase(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        phase._reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=True)
        phase._prs.remove_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await phase.review_prs([pr], [issue])

        assert results[0].merged is True
        phase._prs.merge_pr.assert_awaited_once_with(101)

    @pytest.mark.asyncio
    async def test_review_does_not_merge_rejected_pr(self, config: HydraConfig) -> None:
        """review_prs should not merge PRs with REQUEST_CHANGES verdict."""
        phase = _make_phase(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        phase._reviewers.review = AsyncMock(
            return_value=make_review_result(
                101, 42, verdict=ReviewVerdict.REQUEST_CHANGES
            )
        )
        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=True)

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await phase.review_prs([pr], [issue])

        assert results[0].merged is False
        phase._prs.merge_pr.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_review_rebases_before_reviewing(self, config: HydraConfig) -> None:
        """review_prs should rebase onto main and push before reviewing."""
        phase = _make_phase(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        phase._reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=True)
        phase._prs.remove_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()
        phase._worktrees.rebase = AsyncMock(return_value=True)

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await phase.review_prs([pr], [issue])

        assert results[0].merged is True
        phase._worktrees.rebase.assert_awaited_once()
        phase._prs.push_branch.assert_awaited()
        phase._reviewers.review.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_review_rebase_conflict_escalates_to_hitl(
        self, config: HydraConfig
    ) -> None:
        """When pre-review rebase fails (conflicts), should skip review and escalate."""
        phase = _make_phase(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        phase._prs.post_pr_comment = AsyncMock()
        phase._prs.remove_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()
        phase._worktrees.rebase = AsyncMock(return_value=False)  # Conflicts

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await phase.review_prs([pr], [issue])

        assert results[0].merged is False
        assert "conflicts" in results[0].summary.lower()
        # Review should NOT have been called
        phase._reviewers.review.assert_not_awaited()
        # Should escalate to HITL
        phase._prs.add_labels.assert_awaited_once_with(42, ["hydra-hitl"])

    @pytest.mark.asyncio
    async def test_review_merge_failure_escalates_to_hitl(
        self, config: HydraConfig
    ) -> None:
        """When merge fails after successful rebase, should escalate to HITL."""
        phase = _make_phase(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        phase._reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=False)
        phase._prs.post_pr_comment = AsyncMock()
        phase._prs.remove_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()
        phase._worktrees.rebase = AsyncMock(return_value=True)

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await phase.review_prs([pr], [issue])

        assert results[0].merged is False
        hitl_calls = [
            c
            for c in phase._prs.post_pr_comment.call_args_list
            if "Merge failed" in str(c)
        ]
        assert len(hitl_calls) == 1
        phase._prs.add_labels.assert_any_await(42, ["hydra-hitl"])

    @pytest.mark.asyncio
    async def test_review_merge_records_lifetime_stats(
        self, config: HydraConfig
    ) -> None:
        """Merging a PR should record both pr_merged and issue_completed."""
        phase = _make_phase(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        phase._reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=True)
        phase._prs.pull_main = AsyncMock()
        phase._prs.remove_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs([pr], [issue])

        stats = phase._state.get_lifetime_stats()
        assert stats["prs_merged"] == 1
        assert stats["issues_completed"] == 1

    @pytest.mark.asyncio
    async def test_review_merge_labels_issue_hydra_fixed(
        self, config: HydraConfig
    ) -> None:
        """Merging a PR should swap label from hydra-review to hydra-fixed."""
        phase = _make_phase(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        phase._reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=True)
        phase._prs.remove_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs([pr], [issue])

        # Should remove hydra-review and add hydra-fixed
        remove_calls = [c.args for c in phase._prs.remove_label.call_args_list]
        assert (42, "hydra-review") in remove_calls
        add_calls = [c.args for c in phase._prs.add_labels.call_args_list]
        assert (42, ["hydra-fixed"]) in add_calls

    @pytest.mark.asyncio
    async def test_review_merge_failure_does_not_record_lifetime_stats(
        self, config: HydraConfig
    ) -> None:
        """Failed merge should not increment lifetime stats."""
        phase = _make_phase(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        phase._reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=False)

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs([pr], [issue])

        stats = phase._state.get_lifetime_stats()
        assert stats["prs_merged"] == 0
        assert stats["issues_completed"] == 0

    @pytest.mark.asyncio
    async def test_review_merge_marks_issue_as_merged(
        self, config: HydraConfig
    ) -> None:
        """Successful merge should mark issue status as 'merged'."""
        phase = _make_phase(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        phase._reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=True)
        phase._prs.remove_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs([pr], [issue])

        assert phase._state.get_issue_status(42) == "merged"

    @pytest.mark.asyncio
    async def test_review_merge_failure_keeps_reviewed_status(
        self, config: HydraConfig
    ) -> None:
        """Failed merge should leave issue as 'reviewed', not 'merged'."""
        phase = _make_phase(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        phase._reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=False)

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs([pr], [issue])

        assert phase._state.get_issue_status(42) == "reviewed"

    @pytest.mark.asyncio
    async def test_review_posts_pr_comment_with_summary(
        self, config: HydraConfig
    ) -> None:
        """post_pr_comment should be called with the review summary."""
        phase = _make_phase(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        review = make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)

        phase._reviewers.review = AsyncMock(return_value=review)
        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=True)
        phase._prs.post_pr_comment = AsyncMock()
        phase._prs.submit_review = AsyncMock(return_value=True)
        phase._prs.remove_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs([pr], [issue])

        phase._prs.post_pr_comment.assert_awaited_once_with(101, "Looks good.")

    @pytest.mark.asyncio
    async def test_review_skips_submit_review_for_approve(
        self, config: HydraConfig
    ) -> None:
        """submit_review should NOT be called for approve to avoid self-approval errors."""
        phase = _make_phase(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        review = make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)

        phase._reviewers.review = AsyncMock(return_value=review)
        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=True)
        phase._prs.post_pr_comment = AsyncMock()
        phase._prs.submit_review = AsyncMock(return_value=True)
        phase._prs.remove_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs([pr], [issue])

        phase._prs.submit_review.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "verdict",
        [ReviewVerdict.REQUEST_CHANGES, ReviewVerdict.COMMENT],
    )
    async def test_review_submits_review_for_non_approve_verdicts(
        self, config: HydraConfig, verdict: ReviewVerdict
    ) -> None:
        """submit_review should be called for request-changes and comment verdicts."""
        phase = _make_phase(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        review = make_review_result(101, 42, verdict=verdict)

        phase._reviewers.review = AsyncMock(return_value=review)
        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=True)
        phase._prs.post_pr_comment = AsyncMock()
        phase._prs.submit_review = AsyncMock(return_value=True)
        phase._prs.remove_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs([pr], [issue])

        phase._prs.submit_review.assert_awaited_once_with(101, verdict, "Looks good.")

    @pytest.mark.asyncio
    async def test_review_skips_pr_comment_when_summary_empty(
        self, config: HydraConfig
    ) -> None:
        """post_pr_comment should NOT be called when summary is empty."""
        phase = _make_phase(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        review = ReviewResult(
            pr_number=101,
            issue_number=42,
            verdict=ReviewVerdict.APPROVE,
            summary="",
            fixes_made=False,
        )

        phase._reviewers.review = AsyncMock(return_value=review)
        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=True)
        phase._prs.post_pr_comment = AsyncMock()
        phase._prs.submit_review = AsyncMock(return_value=True)
        phase._prs.remove_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs([pr], [issue])

        phase._prs.post_pr_comment.assert_not_awaited()
        # submit_review should NOT be called for approve verdict
        phase._prs.submit_review.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_review_comment_before_merge(self, config: HydraConfig) -> None:
        """post_pr_comment should be called before merge; submit_review skipped for approve."""
        phase = _make_phase(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        review = make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)

        phase._reviewers.review = AsyncMock(return_value=review)

        call_order: list[str] = []

        async def fake_post_pr_comment(pr_number: int, body: str) -> None:
            call_order.append("post_pr_comment")

        async def fake_merge(pr_number: int) -> bool:
            call_order.append("merge")
            return True

        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.post_pr_comment = fake_post_pr_comment
        phase._prs.submit_review = AsyncMock(return_value=True)
        phase._prs.merge_pr = fake_merge
        phase._prs.remove_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs([pr], [issue])

        assert call_order.index("post_pr_comment") < call_order.index("merge")
        phase._prs.submit_review.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_review_posts_comment_even_when_merge_fails(
        self, config: HydraConfig
    ) -> None:
        """post_pr_comment should be called regardless of merge outcome."""
        phase = _make_phase(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        review = make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)

        phase._reviewers.review = AsyncMock(return_value=review)
        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.post_pr_comment = AsyncMock()
        phase._prs.submit_review = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=False)
        phase._prs.remove_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs([pr], [issue])

        # Review comment + HITL escalation comment
        comment_bodies = [c.args[1] for c in phase._prs.post_pr_comment.call_args_list]
        assert "Looks good." in comment_bodies
        assert any("Merge failed" in b for b in comment_bodies)
        phase._prs.submit_review.assert_not_awaited()


# ---------------------------------------------------------------------------
# CI wait/fix loop (wait_and_fix_ci)
# ---------------------------------------------------------------------------


class TestWaitAndFixCI:
    """Tests for the wait_and_fix_ci method and CI gate in review_prs."""

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
        phase = _make_phase(cfg)
        issue = make_issue(42)
        pr = make_pr_info(101, 42)

        phase._reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        phase._prs.get_pr_diff = AsyncMock(return_value="diff")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=True)
        phase._prs.wait_for_ci = AsyncMock(return_value=(True, "All 3 checks passed"))
        phase._prs.remove_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await phase.review_prs([pr], [issue])

        assert results[0].merged is True
        assert results[0].ci_passed is True
        phase._prs.merge_pr.assert_awaited_once_with(101)

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
        phase = _make_phase(cfg)
        issue = make_issue(42)
        pr = make_pr_info(101, 42)

        fix_result = ReviewResult(
            pr_number=101,
            issue_number=42,
            verdict=ReviewVerdict.REQUEST_CHANGES,
            fixes_made=True,
        )

        phase._reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        phase._reviewers.fix_ci = AsyncMock(return_value=fix_result)
        phase._prs.get_pr_diff = AsyncMock(return_value="diff")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=True)
        phase._prs.wait_for_ci = AsyncMock(return_value=(False, "Failed checks: ci"))
        phase._prs.post_pr_comment = AsyncMock()
        phase._prs.remove_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await phase.review_prs([pr], [issue])

        assert results[0].merged is False
        assert results[0].ci_passed is False
        phase._prs.merge_pr.assert_not_awaited()

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
        phase = _make_phase(cfg)
        issue = make_issue(42)
        pr = make_pr_info(101, 42)

        phase._reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        phase._prs.get_pr_diff = AsyncMock(return_value="diff")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=True)
        phase._prs.wait_for_ci = AsyncMock(return_value=(True, "passed"))
        phase._prs.remove_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await phase.review_prs([pr], [issue])

        assert results[0].merged is True
        # wait_for_ci should NOT have been called
        phase._prs.wait_for_ci.assert_not_awaited()

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
        phase = _make_phase(cfg)
        issue = make_issue(42)
        pr = make_pr_info(101, 42)

        phase._reviewers.review = AsyncMock(
            return_value=make_review_result(
                101, 42, verdict=ReviewVerdict.REQUEST_CHANGES
            )
        )
        phase._prs.get_pr_diff = AsyncMock(return_value="diff")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=True)
        phase._prs.wait_for_ci = AsyncMock(return_value=(True, "passed"))

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await phase.review_prs([pr], [issue])

        assert results[0].merged is False
        phase._prs.wait_for_ci.assert_not_awaited()
        phase._prs.merge_pr.assert_not_awaited()

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
        phase = _make_phase(cfg)
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

        phase._reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        phase._reviewers.fix_ci = AsyncMock(return_value=fix_result)
        phase._prs.get_pr_diff = AsyncMock(return_value="diff")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=True)
        phase._prs.wait_for_ci = fake_wait_for_ci
        phase._prs.remove_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await phase.review_prs([pr], [issue])

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
        phase = _make_phase(cfg)
        issue = make_issue(42)
        pr = make_pr_info(101, 42)

        fix_result = ReviewResult(
            pr_number=101,
            issue_number=42,
            verdict=ReviewVerdict.REQUEST_CHANGES,
            fixes_made=False,  # No changes made
        )

        phase._reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        phase._reviewers.fix_ci = AsyncMock(return_value=fix_result)
        phase._prs.get_pr_diff = AsyncMock(return_value="diff")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=True)
        phase._prs.wait_for_ci = AsyncMock(return_value=(False, "Failed checks: ci"))
        phase._prs.post_pr_comment = AsyncMock()
        phase._prs.remove_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await phase.review_prs([pr], [issue])

        assert results[0].merged is False
        assert results[0].ci_passed is False
        # Only 1 fix attempt (stopped early because no changes)
        assert results[0].ci_fix_attempts == 1
        # fix_ci called once, not 3 times
        phase._reviewers.fix_ci.assert_awaited_once()

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
        phase = _make_phase(cfg)
        issue = make_issue(42)
        pr = make_pr_info(101, 42)

        fix_result = ReviewResult(
            pr_number=101,
            issue_number=42,
            verdict=ReviewVerdict.REQUEST_CHANGES,
            fixes_made=True,
        )

        phase._reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        phase._reviewers.fix_ci = AsyncMock(return_value=fix_result)
        phase._prs.get_pr_diff = AsyncMock(return_value="diff")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=True)
        phase._prs.wait_for_ci = AsyncMock(return_value=(False, "Failed checks: ci"))
        phase._prs.post_pr_comment = AsyncMock()
        phase._prs.remove_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs([pr], [issue])

        # Should have posted a CI failure comment
        comment_calls = [c.args for c in phase._prs.post_pr_comment.call_args_list]
        ci_comments = [c for c in comment_calls if "CI failed" in c[1]]
        assert len(ci_comments) == 1
        assert "Failed checks: ci" in ci_comments[0][1]

        # Should swap label to hydra-hitl
        remove_calls = [c.args for c in phase._prs.remove_label.call_args_list]
        assert (42, "hydra-review") in remove_calls
        add_calls = [c.args for c in phase._prs.add_labels.call_args_list]
        assert (42, ["hydra-hitl"]) in add_calls
