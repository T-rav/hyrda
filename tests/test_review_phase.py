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

from events import EventBus, EventType
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


def _make_phase(
    config: HydraConfig,
    *,
    agents: AsyncMock | None = None,
    event_bus: EventBus | None = None,
) -> ReviewPhase:
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
        agents=agents,
        event_bus=event_bus or EventBus(),
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
    async def test_review_merges_main_before_reviewing(
        self, config: HydraConfig
    ) -> None:
        """review_prs should merge main and push before reviewing."""
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
        phase._worktrees.merge_main = AsyncMock(return_value=True)

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await phase.review_prs([pr], [issue])

        assert results[0].merged is True
        phase._worktrees.merge_main.assert_awaited_once()
        phase._prs.push_branch.assert_awaited()
        phase._reviewers.review.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_review_merge_conflict_escalates_to_hitl(
        self, config: HydraConfig
    ) -> None:
        """When merge fails and agent can't resolve, should escalate to HITL."""
        mock_agents = AsyncMock()
        mock_agents._verify_result = AsyncMock(return_value=(False, ""))
        phase = _make_phase(config, agents=mock_agents)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        phase._prs.post_pr_comment = AsyncMock()
        phase._prs.remove_label = AsyncMock()
        phase._prs.remove_pr_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()
        phase._prs.add_pr_labels = AsyncMock()
        phase._worktrees.merge_main = AsyncMock(return_value=False)  # Conflicts
        # Agent resolution also fails
        phase._worktrees.start_merge_main = AsyncMock(return_value=False)
        phase._worktrees.abort_merge = AsyncMock()

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await phase.review_prs([pr], [issue])

        assert results[0].merged is False
        assert "conflicts" in results[0].summary.lower()
        # Review should NOT have been called
        phase._reviewers.review.assert_not_awaited()
        # Should escalate to HITL on both issue and PR
        phase._prs.add_labels.assert_awaited_once_with(42, ["hydra-hitl"])
        phase._prs.add_pr_labels.assert_awaited_once_with(101, ["hydra-hitl"])

    @pytest.mark.asyncio
    async def test_review_conflict_escalation_records_hitl_origin(
        self, config: HydraConfig
    ) -> None:
        """Merge conflict escalation should record review_label as HITL origin."""
        mock_agents = AsyncMock()
        mock_agents._execute = AsyncMock(return_value="transcript")
        mock_agents._verify_result = AsyncMock(return_value=(False, ""))
        phase = _make_phase(config, agents=mock_agents)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        phase._prs.post_pr_comment = AsyncMock()
        phase._prs.remove_label = AsyncMock()
        phase._prs.remove_pr_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()
        phase._prs.add_pr_labels = AsyncMock()
        phase._worktrees.merge_main = AsyncMock(return_value=False)
        phase._worktrees.start_merge_main = AsyncMock(return_value=False)
        phase._worktrees.abort_merge = AsyncMock()

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs([pr], [issue])

        assert phase._state.get_hitl_origin(42) == "hydra-review"

    @pytest.mark.asyncio
    async def test_review_conflict_escalation_sets_hitl_cause(
        self, config: HydraConfig
    ) -> None:
        """Merge conflict escalation should record cause in state."""
        mock_agents = AsyncMock()
        mock_agents._execute = AsyncMock(return_value="transcript")
        mock_agents._verify_result = AsyncMock(return_value=(False, ""))
        phase = _make_phase(config, agents=mock_agents)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        phase._prs.post_pr_comment = AsyncMock()
        phase._prs.remove_label = AsyncMock()
        phase._prs.remove_pr_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()
        phase._prs.add_pr_labels = AsyncMock()
        phase._worktrees.merge_main = AsyncMock(return_value=False)
        phase._worktrees.start_merge_main = AsyncMock(return_value=False)
        phase._worktrees.abort_merge = AsyncMock()

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs([pr], [issue])

        assert phase._state.get_hitl_cause(42) == "Merge conflict with main branch"

    @pytest.mark.asyncio
    async def test_review_merge_conflict_resolved_by_agent(
        self, config: HydraConfig
    ) -> None:
        """When merge fails but agent resolves conflicts, review should proceed."""
        mock_agents = AsyncMock()
        mock_agents._execute = AsyncMock(return_value="transcript")
        mock_agents._verify_result = AsyncMock(return_value=(True, ""))
        phase = _make_phase(config, agents=mock_agents)
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
        phase._worktrees.merge_main = AsyncMock(return_value=False)  # Conflicts
        # But agent resolves them
        phase._worktrees.start_merge_main = AsyncMock(return_value=False)

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await phase.review_prs([pr], [issue])

        # Agent resolved conflicts, so review should proceed and merge
        phase._reviewers.review.assert_awaited_once()
        assert results[0].merged is True

    @pytest.mark.asyncio
    async def test_review_merge_conflict_no_agent_escalates(
        self, config: HydraConfig
    ) -> None:
        """When no agent runner is configured, conflicts escalate directly to HITL."""
        phase = _make_phase(config)  # No agents passed
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        phase._prs.post_pr_comment = AsyncMock()
        phase._prs.remove_label = AsyncMock()
        phase._prs.remove_pr_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()
        phase._prs.add_pr_labels = AsyncMock()
        phase._worktrees.merge_main = AsyncMock(return_value=False)

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await phase.review_prs([pr], [issue])

        assert results[0].merged is False
        assert "conflicts" in results[0].summary.lower()
        phase._prs.add_labels.assert_awaited_once_with(42, ["hydra-hitl"])

    @pytest.mark.asyncio
    async def test_review_merge_failure_escalates_to_hitl(
        self, config: HydraConfig
    ) -> None:
        """When merge fails after successful merge-main, should escalate to HITL."""
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
        phase._prs.remove_pr_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()
        phase._prs.add_pr_labels = AsyncMock()
        phase._worktrees.merge_main = AsyncMock(return_value=True)

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
        phase._prs.add_pr_labels.assert_any_await(101, ["hydra-hitl"])
        phase._prs.remove_pr_label.assert_awaited()

    @pytest.mark.asyncio
    async def test_review_merge_failure_records_hitl_origin(
        self, config: HydraConfig
    ) -> None:
        """Merge failure escalation should record review_label as HITL origin."""
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
        phase._prs.remove_pr_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()
        phase._prs.add_pr_labels = AsyncMock()
        phase._worktrees.merge_main = AsyncMock(return_value=True)

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs([pr], [issue])

        assert phase._state.get_hitl_origin(42) == "hydra-review"

    @pytest.mark.asyncio
    async def test_review_merge_failure_sets_hitl_cause(
        self, config: HydraConfig
    ) -> None:
        """Merge failure escalation should record cause in state."""
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
        phase._prs.remove_pr_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()
        phase._prs.add_pr_labels = AsyncMock()
        phase._worktrees.merge_main = AsyncMock(return_value=True)

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs([pr], [issue])

        assert phase._state.get_hitl_cause(42) == "PR merge failed on GitHub"

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
    async def test_review_request_changes_self_review_falls_back_gracefully(
        self, config: HydraConfig
    ) -> None:
        """When submit_review raises SelfReviewError, state should still be marked."""
        from pr_manager import SelfReviewError

        phase = _make_phase(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        review = make_review_result(101, 42, verdict=ReviewVerdict.REQUEST_CHANGES)

        phase._reviewers.review = AsyncMock(return_value=review)
        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.post_pr_comment = AsyncMock()
        phase._prs.submit_review = AsyncMock(
            side_effect=SelfReviewError(
                "Can not request changes on your own pull request"
            )
        )

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await phase.review_prs([pr], [issue])

        assert len(results) == 1
        # PR should still be marked with request-changes verdict
        assert phase._state.get_pr_status(101) == "request-changes"
        # Issue should be marked as reviewed
        assert phase._state.get_issue_status(42) == "reviewed"
        # Review summary was posted as PR comment
        phase._prs.post_pr_comment.assert_awaited_once_with(101, "Looks good.")
        # No exception propagated — result is returned normally
        assert results[0].verdict == ReviewVerdict.REQUEST_CHANGES

    @pytest.mark.asyncio
    async def test_review_self_review_error_does_not_crash_batch(
        self, config: HydraConfig
    ) -> None:
        """With multiple PRs, a SelfReviewError on one should not block others."""
        from pr_manager import SelfReviewError

        phase = _make_phase(config)
        issues = [make_issue(1), make_issue(2)]
        prs = [make_pr_info(101, 1, draft=False), make_pr_info(102, 2, draft=False)]

        async def fake_review(pr, issue, wt_path, diff, worker_id=0):
            return make_review_result(
                pr.number, issue.number, verdict=ReviewVerdict.REQUEST_CHANGES
            )

        async def fake_submit_review(pr_number, verdict, summary):
            if pr_number == 101:
                raise SelfReviewError(
                    "Can not request changes on your own pull request"
                )
            return True

        phase._reviewers.review = fake_review  # type: ignore[method-assign]
        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.post_pr_comment = AsyncMock()
        phase._prs.submit_review = fake_submit_review  # type: ignore[method-assign]

        for i in (1, 2):
            wt = config.worktree_base / f"issue-{i}"
            wt.mkdir(parents=True, exist_ok=True)

        results = await phase.review_prs(prs, issues)

        # Both PRs should have been processed
        assert len(results) == 2
        # Both PRs marked in state
        assert phase._state.get_pr_status(101) == "request-changes"
        assert phase._state.get_pr_status(102) == "request-changes"
        # Both issues marked as reviewed
        assert phase._state.get_issue_status(1) == "reviewed"
        assert phase._state.get_issue_status(2) == "reviewed"

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

        # Should swap label to hydra-hitl on both issue and PR
        remove_calls = [c.args for c in phase._prs.remove_label.call_args_list]
        assert (42, "hydra-review") in remove_calls
        add_calls = [c.args for c in phase._prs.add_labels.call_args_list]
        assert (42, ["hydra-hitl"]) in add_calls

    @pytest.mark.asyncio
    async def test_ci_failure_sets_hitl_cause(self, config: HydraConfig) -> None:
        """CI failure escalation should record cause with attempt count in state."""
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

        assert phase._state.get_hitl_cause(42) == "CI failed after 1 fix attempt(s)"

    @pytest.mark.asyncio
    async def test_ci_failure_escalation_records_hitl_origin(
        self, config: HydraConfig
    ) -> None:
        """CI failure escalation should record review_label as HITL origin."""
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

        assert phase._state.get_hitl_origin(42) == "hydra-review"


# ---------------------------------------------------------------------------
# _resolve_merge_conflicts
# ---------------------------------------------------------------------------


class TestResolveMergeConflicts:
    """Tests for the _resolve_merge_conflicts method."""

    @pytest.mark.asyncio
    async def test_returns_false_when_no_agents(self, config: HydraConfig) -> None:
        """Without an agent runner, should return False immediately."""
        phase = _make_phase(config)  # No agents
        pr = make_pr_info(101, 42)
        issue = make_issue(42)

        result = await phase._resolve_merge_conflicts(
            pr, issue, config.worktree_base / "issue-42", worker_id=0
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_when_start_merge_is_clean(
        self, config: HydraConfig
    ) -> None:
        """If start_merge_main returns True (no conflicts), return True."""
        mock_agents = AsyncMock()
        phase = _make_phase(config, agents=mock_agents)
        pr = make_pr_info(101, 42)
        issue = make_issue(42)

        phase._worktrees.start_merge_main = AsyncMock(return_value=True)

        result = await phase._resolve_merge_conflicts(
            pr, issue, config.worktree_base / "issue-42", worker_id=0
        )

        assert result is True
        # Agent should NOT have been invoked
        mock_agents._execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_runs_agent_and_verifies_on_conflicts(
        self, config: HydraConfig
    ) -> None:
        """Should run the agent and verify quality when there are conflicts."""
        mock_agents = AsyncMock()
        mock_agents._execute = AsyncMock(return_value="transcript")
        mock_agents._verify_result = AsyncMock(return_value=(True, ""))
        phase = _make_phase(config, agents=mock_agents)
        pr = make_pr_info(101, 42)
        issue = make_issue(42)

        phase._worktrees.start_merge_main = AsyncMock(return_value=False)

        result = await phase._resolve_merge_conflicts(
            pr, issue, config.worktree_base / "issue-42", worker_id=0
        )

        assert result is True
        mock_agents._build_command.assert_called_once()
        mock_agents._execute.assert_awaited_once()
        mock_agents._verify_result.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_aborts_merge_on_agent_exception(self, config: HydraConfig) -> None:
        """On agent exception on all attempts, should abort merge and return False."""
        mock_agents = AsyncMock()
        mock_agents._execute = AsyncMock(side_effect=RuntimeError("agent crashed"))
        phase = _make_phase(config, agents=mock_agents)
        pr = make_pr_info(101, 42)
        issue = make_issue(42)

        phase._worktrees.start_merge_main = AsyncMock(return_value=False)
        phase._worktrees.abort_merge = AsyncMock()

        result = await phase._resolve_merge_conflicts(
            pr, issue, config.worktree_base / "issue-42", worker_id=0
        )

        assert result is False
        phase._worktrees.abort_merge.assert_awaited()


# ---------------------------------------------------------------------------
# _build_conflict_prompt
# ---------------------------------------------------------------------------


class TestBuildConflictPrompt:
    """Tests for the _build_conflict_prompt method."""

    def test_prompt_without_error(self, config: HydraConfig) -> None:
        """Base prompt should contain issue number and instructions."""
        phase = _make_phase(config)
        issue = make_issue(42, title="Fix widget")

        prompt = phase._build_conflict_prompt(issue, None, 1)

        assert "#42" in prompt
        assert "Fix widget" in prompt
        assert "## Instructions" in prompt
        assert "Previous Attempt Failed" not in prompt

    def test_prompt_with_error_on_retry(self, config: HydraConfig) -> None:
        """Retry prompt should include previous error context."""
        phase = _make_phase(config)
        issue = make_issue(42)

        prompt = phase._build_conflict_prompt(
            issue, last_error="lint error: unused import", attempt=2
        )

        assert "## Previous Attempt Failed" in prompt
        assert "lint error: unused import" in prompt

    def test_prompt_truncates_long_error(self, config: HydraConfig) -> None:
        """Error output longer than 3000 chars should be truncated."""
        phase = _make_phase(config)
        issue = make_issue(42)
        long_error = "x" * 5000

        prompt = phase._build_conflict_prompt(issue, last_error=long_error, attempt=2)

        # The error section should contain at most 3000 chars of the error
        assert "x" * 3000 in prompt
        assert "x" * 5000 not in prompt


# ---------------------------------------------------------------------------
# _resolve_merge_conflicts retry loop
# ---------------------------------------------------------------------------


class TestResolveMergeConflictsRetry:
    """Tests for the retry loop in _resolve_merge_conflicts."""

    @pytest.mark.asyncio
    async def test_retries_on_verify_failure(self, config: HydraConfig) -> None:
        """Should retry when verify fails, and succeed on second attempt."""
        mock_agents = AsyncMock()
        mock_agents._execute = AsyncMock(return_value="transcript")
        mock_agents._verify_result = AsyncMock(
            side_effect=[(False, "quality failed"), (True, "")]
        )
        phase = _make_phase(config, agents=mock_agents)
        pr = make_pr_info(101, 42)
        issue = make_issue(42)

        phase._worktrees.start_merge_main = AsyncMock(return_value=False)
        phase._worktrees.abort_merge = AsyncMock()

        result = await phase._resolve_merge_conflicts(
            pr, issue, config.worktree_base / "issue-42", worker_id=0
        )

        assert result is True
        assert mock_agents._execute.await_count == 2
        assert mock_agents._verify_result.await_count == 2

    @pytest.mark.asyncio
    async def test_exhausts_all_attempts_then_returns_false(
        self, config: HydraConfig
    ) -> None:
        """When all attempts fail verification, should return False."""
        mock_agents = AsyncMock()
        mock_agents._execute = AsyncMock(return_value="transcript")
        mock_agents._verify_result = AsyncMock(return_value=(False, "quality failed"))
        phase = _make_phase(config, agents=mock_agents)
        pr = make_pr_info(101, 42)
        issue = make_issue(42)

        phase._worktrees.start_merge_main = AsyncMock(return_value=False)
        phase._worktrees.abort_merge = AsyncMock()

        result = await phase._resolve_merge_conflicts(
            pr, issue, config.worktree_base / "issue-42", worker_id=0
        )

        assert result is False
        # Default is 3 attempts
        assert mock_agents._execute.await_count == 3
        assert mock_agents._verify_result.await_count == 3

    @pytest.mark.asyncio
    async def test_feeds_error_to_retry_prompt(self, config: HydraConfig) -> None:
        """On retry, the prompt should include the previous error."""
        mock_agents = AsyncMock()
        mock_agents._execute = AsyncMock(return_value="transcript")
        mock_agents._verify_result = AsyncMock(
            side_effect=[(False, "ruff check failed"), (True, "")]
        )
        phase = _make_phase(config, agents=mock_agents)
        pr = make_pr_info(101, 42)
        issue = make_issue(42)

        phase._worktrees.start_merge_main = AsyncMock(return_value=False)
        phase._worktrees.abort_merge = AsyncMock()

        await phase._resolve_merge_conflicts(
            pr, issue, config.worktree_base / "issue-42", worker_id=0
        )

        # Second call to _execute should have received a prompt with the error
        second_call_args = mock_agents._execute.call_args_list[1]
        prompt_arg = second_call_args.args[1]
        assert "ruff check failed" in prompt_arg
        assert "Previous Attempt Failed" in prompt_arg

    @pytest.mark.asyncio
    async def test_aborts_merge_between_retries(self, config: HydraConfig) -> None:
        """abort_merge should be called before attempt 2+."""
        mock_agents = AsyncMock()
        mock_agents._execute = AsyncMock(return_value="transcript")
        mock_agents._verify_result = AsyncMock(
            side_effect=[(False, "failed"), (True, "")]
        )
        phase = _make_phase(config, agents=mock_agents)
        pr = make_pr_info(101, 42)
        issue = make_issue(42)

        phase._worktrees.start_merge_main = AsyncMock(return_value=False)
        phase._worktrees.abort_merge = AsyncMock()

        await phase._resolve_merge_conflicts(
            pr, issue, config.worktree_base / "issue-42", worker_id=0
        )

        # abort_merge called once before attempt 2
        phase._worktrees.abort_merge.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_saves_transcript_per_attempt(self, config: HydraConfig) -> None:
        """A transcript file should be saved for each attempt."""
        mock_agents = AsyncMock()
        mock_agents._execute = AsyncMock(return_value="transcript content")
        mock_agents._verify_result = AsyncMock(
            side_effect=[(False, "failed"), (True, "")]
        )
        phase = _make_phase(config, agents=mock_agents)
        pr = make_pr_info(101, 42)
        issue = make_issue(42)

        phase._worktrees.start_merge_main = AsyncMock(return_value=False)
        phase._worktrees.abort_merge = AsyncMock()

        await phase._resolve_merge_conflicts(
            pr, issue, config.worktree_base / "issue-42", worker_id=0
        )

        log_dir = config.repo_root / ".hydra" / "logs"
        assert (log_dir / "conflict-pr-101-attempt-1.txt").exists()
        assert (log_dir / "conflict-pr-101-attempt-2.txt").exists()

    @pytest.mark.asyncio
    async def test_respects_config_max_attempts(self, config: HydraConfig) -> None:
        """Should honor a custom max_merge_conflict_fix_attempts value."""
        from tests.helpers import ConfigFactory

        cfg = ConfigFactory.create(
            max_merge_conflict_fix_attempts=1,
            repo_root=config.repo_root,
            worktree_base=config.worktree_base,
            state_file=config.state_file,
        )
        mock_agents = AsyncMock()
        mock_agents._execute = AsyncMock(return_value="transcript")
        mock_agents._verify_result = AsyncMock(return_value=(False, "quality failed"))
        phase = _make_phase(cfg, agents=mock_agents)
        pr = make_pr_info(101, 42)
        issue = make_issue(42)

        phase._worktrees.start_merge_main = AsyncMock(return_value=False)
        phase._worktrees.abort_merge = AsyncMock()

        result = await phase._resolve_merge_conflicts(
            pr, issue, cfg.worktree_base / "issue-42", worker_id=0
        )

        assert result is False
        assert mock_agents._execute.await_count == 1

    @pytest.mark.asyncio
    async def test_zero_attempts_returns_false(self, config: HydraConfig) -> None:
        """With max_merge_conflict_fix_attempts=0, should return False without trying."""
        from tests.helpers import ConfigFactory

        cfg = ConfigFactory.create(
            max_merge_conflict_fix_attempts=0,
            repo_root=config.repo_root,
            worktree_base=config.worktree_base,
            state_file=config.state_file,
        )
        mock_agents = AsyncMock()
        phase = _make_phase(cfg, agents=mock_agents)
        pr = make_pr_info(101, 42)
        issue = make_issue(42)

        phase._worktrees.start_merge_main = AsyncMock(return_value=False)
        phase._worktrees.abort_merge = AsyncMock()

        result = await phase._resolve_merge_conflicts(
            pr, issue, cfg.worktree_base / "issue-42", worker_id=0
        )

        assert result is False
        mock_agents._execute.assert_not_awaited()
        # Final abort_merge should still be called
        phase._worktrees.abort_merge.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_clean_merge_on_retry_returns_true(self, config: HydraConfig) -> None:
        """If merge becomes clean on a retry, should return True without running agent."""
        from tests.helpers import ConfigFactory

        cfg = ConfigFactory.create(
            max_merge_conflict_fix_attempts=2,
            repo_root=config.repo_root,
            worktree_base=config.worktree_base,
            state_file=config.state_file,
        )
        mock_agents = AsyncMock()
        mock_agents._execute = AsyncMock(return_value="transcript")
        mock_agents._verify_result = AsyncMock(return_value=(False, "fail"))
        phase = _make_phase(cfg, agents=mock_agents)
        pr = make_pr_info(101, 42)
        issue = make_issue(42)

        # First attempt: conflicts. Second attempt: clean merge.
        phase._worktrees.start_merge_main = AsyncMock(side_effect=[False, True])
        phase._worktrees.abort_merge = AsyncMock()

        result = await phase._resolve_merge_conflicts(
            pr, issue, cfg.worktree_base / "issue-42", worker_id=0
        )

        assert result is True
        # Agent ran once (first attempt), not on second (clean merge)
        assert mock_agents._execute.await_count == 1

    @pytest.mark.asyncio
    async def test_exception_on_non_final_attempt_continues(
        self, config: HydraConfig
    ) -> None:
        """Exception on first attempt should allow retry on next attempt."""
        from tests.helpers import ConfigFactory

        cfg = ConfigFactory.create(
            max_merge_conflict_fix_attempts=2,
            repo_root=config.repo_root,
            worktree_base=config.worktree_base,
            state_file=config.state_file,
        )
        mock_agents = AsyncMock()
        mock_agents._execute = AsyncMock(side_effect=[RuntimeError("crash"), "ok"])
        mock_agents._verify_result = AsyncMock(return_value=(True, "OK"))
        phase = _make_phase(cfg, agents=mock_agents)
        pr = make_pr_info(101, 42)
        issue = make_issue(42)

        phase._worktrees.start_merge_main = AsyncMock(return_value=False)
        phase._worktrees.abort_merge = AsyncMock()

        result = await phase._resolve_merge_conflicts(
            pr, issue, cfg.worktree_base / "issue-42", worker_id=0
        )

        assert result is True
        assert mock_agents._execute.await_count == 2


# ---------------------------------------------------------------------------
# Review exception isolation
# ---------------------------------------------------------------------------


class TestReviewExceptionIsolation:
    """Tests that _review_one catches exceptions and returns failed results."""

    @pytest.mark.asyncio
    async def test_review_exception_returns_failed_result(
        self, config: HydraConfig
    ) -> None:
        """When reviewer.review raises, should return ReviewResult with error summary."""
        phase = _make_phase(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        phase._reviewers.review = AsyncMock(
            side_effect=RuntimeError("reviewer crashed")
        )
        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.push_branch = AsyncMock(return_value=True)

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await phase.review_prs([pr], [issue])

        assert len(results) == 1
        assert results[0].pr_number == 101
        assert "unexpected error" in results[0].summary.lower()

    @pytest.mark.asyncio
    async def test_review_exception_releases_active_issues(
        self, config: HydraConfig
    ) -> None:
        """When review crashes, issue should be removed from active_issues."""
        phase = _make_phase(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        phase._reviewers.review = AsyncMock(
            side_effect=RuntimeError("reviewer crashed")
        )
        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.push_branch = AsyncMock(return_value=True)

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs([pr], [issue])

        assert 42 not in phase._active_issues

    @pytest.mark.asyncio
    async def test_review_exception_does_not_crash_batch(
        self, config: HydraConfig
    ) -> None:
        """With 2 PRs, first review crashing should not prevent the second."""
        phase = _make_phase(config)
        issues = [make_issue(1), make_issue(2)]
        prs = [make_pr_info(101, 1, draft=False), make_pr_info(102, 2, draft=False)]

        call_count = 0

        async def sometimes_crashing_review(
            pr: PRInfo,
            issue: GitHubIssue,
            wt_path: Path,
            diff: str,
            worker_id: int = 0,
        ) -> ReviewResult:
            nonlocal call_count
            call_count += 1
            if pr.issue_number == 1:
                raise RuntimeError("reviewer crashed for PR 1")
            return make_review_result(pr.number, issue.number)

        phase._reviewers.review = sometimes_crashing_review  # type: ignore[method-assign]
        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=True)
        phase._prs.remove_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()

        for i in (1, 2):
            wt = config.worktree_base / f"issue-{i}"
            wt.mkdir(parents=True, exist_ok=True)

        results = await phase.review_prs(prs, issues)

        # Both results should be returned
        assert len(results) == 2
        result_map = {r.pr_number: r for r in results}
        # PR 101 (issue 1) should have error summary
        assert "unexpected error" in result_map[101].summary.lower()
        # PR 102 (issue 2) should have succeeded
        assert result_map[102].summary == "Looks good."


# ---------------------------------------------------------------------------
# _active_issues cleanup
# ---------------------------------------------------------------------------


class TestActiveIssuesCleanup:
    """Tests that _active_issues is cleaned up on all code paths."""

    @pytest.mark.asyncio
    async def test_active_issues_cleaned_on_early_return_issue_not_found(
        self, config: HydraConfig
    ) -> None:
        """When issue is not in issue_map, _active_issues must be cleaned up."""
        phase = _make_phase(config)
        pr = make_pr_info(101, 999)

        wt = config.worktree_base / "issue-999"
        wt.mkdir(parents=True, exist_ok=True)

        results = await phase.review_prs([pr], [])  # no matching issues

        assert 999 not in phase._active_issues
        assert len(results) == 1
        assert results[0].summary == "Issue not found"

    @pytest.mark.asyncio
    async def test_active_issues_cleaned_on_exception_during_merge_main(
        self, config: HydraConfig
    ) -> None:
        """If merge_main raises, _active_issues must still be cleaned up."""
        phase = _make_phase(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42)

        phase._worktrees.merge_main = AsyncMock(
            side_effect=RuntimeError("merge exploded")
        )

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        # Exception isolation catches the error and returns a failed result
        results = await phase.review_prs([pr], [issue])

        assert 42 not in phase._active_issues
        assert len(results) == 1
        assert "unexpected error" in results[0].summary.lower()

    @pytest.mark.asyncio
    async def test_active_issues_cleaned_on_exception_during_review(
        self, config: HydraConfig
    ) -> None:
        """If reviewers.review raises, _active_issues must still be cleaned up."""
        phase = _make_phase(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42)

        phase._reviewers.review = AsyncMock(side_effect=RuntimeError("review crashed"))
        phase._prs.get_pr_diff = AsyncMock(return_value="diff")
        phase._prs.push_branch = AsyncMock(return_value=True)

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        # Exception isolation catches the error and returns a failed result
        results = await phase.review_prs([pr], [issue])

        assert 42 not in phase._active_issues
        assert len(results) == 1
        assert "unexpected error" in results[0].summary.lower()

    @pytest.mark.asyncio
    async def test_active_issues_cleaned_on_exception_during_worktree_create(
        self, config: HydraConfig
    ) -> None:
        """If worktrees.create raises, _active_issues must still be cleaned up."""
        phase = _make_phase(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42)

        phase._worktrees.create = AsyncMock(
            side_effect=RuntimeError("worktree create failed")
        )

        # No worktree dir exists, so create() will be called
        # Exception isolation catches the error and returns a failed result
        results = await phase.review_prs([pr], [issue])

        assert 42 not in phase._active_issues
        assert len(results) == 1
        assert "unexpected error" in results[0].summary.lower()

    @pytest.mark.asyncio
    async def test_active_issues_cleaned_on_happy_path(
        self, config: HydraConfig
    ) -> None:
        """On the happy path, _active_issues must be empty after review_prs."""
        phase = _make_phase(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42)

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

        assert 42 not in phase._active_issues


# ---------------------------------------------------------------------------
# REVIEW_UPDATE start event
# ---------------------------------------------------------------------------


class TestReviewUpdateStartEvent:
    """Tests that a REVIEW_UPDATE event is published at the start of _review_one()."""

    @pytest.mark.asyncio
    async def test_review_update_start_event_published_before_review(
        self, config: HydraConfig
    ) -> None:
        """A REVIEW_UPDATE 'start' event should be published when _review_one() starts."""
        bus = EventBus()
        phase = _make_phase(config, event_bus=bus)
        issue = make_issue(42)
        pr = make_pr_info(101, 42)

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

        # Check that a REVIEW_UPDATE event with status "start" was published
        history = bus.get_history()
        start_events = [
            e
            for e in history
            if e.type == EventType.REVIEW_UPDATE and e.data.get("status") == "start"
        ]
        assert len(start_events) == 1
        assert start_events[0].data["pr"] == 101
        assert start_events[0].data["issue"] == 42
        assert start_events[0].data["role"] == "reviewer"

    @pytest.mark.asyncio
    async def test_review_update_start_event_published_even_when_issue_not_found(
        self, config: HydraConfig
    ) -> None:
        """A REVIEW_UPDATE 'start' event is published even if the issue is missing."""
        bus = EventBus()
        phase = _make_phase(config, event_bus=bus)
        pr = make_pr_info(101, 999)

        wt = config.worktree_base / "issue-999"
        wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs([pr], [])

        history = bus.get_history()
        start_events = [
            e
            for e in history
            if e.type == EventType.REVIEW_UPDATE and e.data.get("status") == "start"
        ]
        assert len(start_events) == 1
        assert start_events[0].data["pr"] == 101
        assert start_events[0].data["issue"] == 999

    @pytest.mark.asyncio
    async def test_review_update_start_event_includes_worker_id(
        self, config: HydraConfig
    ) -> None:
        """The start event should include the worker ID."""
        bus = EventBus()
        phase = _make_phase(config, event_bus=bus)
        issue = make_issue(42)
        pr = make_pr_info(101, 42)

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

        history = bus.get_history()
        start_events = [
            e
            for e in history
            if e.type == EventType.REVIEW_UPDATE and e.data.get("status") == "start"
        ]
        assert len(start_events) == 1
        assert "worker" in start_events[0].data


# ---------------------------------------------------------------------------
# Retrospective integration
# ---------------------------------------------------------------------------


class TestRetrospectiveIntegration:
    """Tests that retrospective.record() is called correctly after merge."""

    @pytest.mark.asyncio
    async def test_retrospective_called_on_successful_merge(
        self, config: HydraConfig
    ) -> None:
        """retrospective.record() should be called when PR is merged."""
        mock_retro = AsyncMock()
        phase = _make_phase(config)
        phase._retrospective = mock_retro

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

        mock_retro.record.assert_awaited_once()
        call_kwargs = mock_retro.record.call_args[1]
        assert call_kwargs["issue_number"] == 42
        assert call_kwargs["pr_number"] == 101
        assert call_kwargs["review_result"].merged is True

    @pytest.mark.asyncio
    async def test_retrospective_not_called_on_failed_merge(
        self, config: HydraConfig
    ) -> None:
        """retrospective.record() should NOT be called when merge fails."""
        mock_retro = AsyncMock()
        phase = _make_phase(config)
        phase._retrospective = mock_retro

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
        phase._prs.remove_pr_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()
        phase._prs.add_pr_labels = AsyncMock()
        phase._worktrees.merge_main = AsyncMock(return_value=True)

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs([pr], [issue])

        mock_retro.record.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_retrospective_failure_does_not_crash_review(
        self, config: HydraConfig
    ) -> None:
        """If retrospective.record() raises, it should not crash the review."""
        mock_retro = AsyncMock()
        mock_retro.record = AsyncMock(side_effect=RuntimeError("retro boom"))
        phase = _make_phase(config)
        phase._retrospective = mock_retro

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

        # Should not raise despite retro failure
        results = await phase.review_prs([pr], [issue])

        assert results[0].merged is True

    @pytest.mark.asyncio
    async def test_retrospective_not_called_when_not_configured(
        self, config: HydraConfig
    ) -> None:
        """When no retrospective is set, merge should work normally."""
        phase = _make_phase(config)
        # phase._retrospective is None by default

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


# ---------------------------------------------------------------------------
# Review insight integration
# ---------------------------------------------------------------------------


class TestReviewInsightIntegration:
    """Tests for review insight recording during the review flow."""

    @pytest.mark.asyncio
    async def test_review_records_insight_after_review(
        self, config: HydraConfig
    ) -> None:
        """After a review, a record should be appended to the insight store."""
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

        # Check that a review record was written
        reviews_path = config.repo_root / ".hydra" / "memory" / "reviews.jsonl"
        assert reviews_path.exists()
        lines = reviews_path.read_text().strip().splitlines()
        assert len(lines) == 1

    @pytest.mark.asyncio
    async def test_review_insight_files_proposal_when_threshold_met(
        self, config: HydraConfig
    ) -> None:
        """When a category crosses the threshold, an improvement issue is filed."""
        from review_insights import ReviewInsightStore, ReviewRecord

        phase = _make_phase(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        # Pre-populate the insight store with records near threshold
        store = ReviewInsightStore(config.repo_root / ".hydra" / "memory")
        for i in range(3):
            store.append_review(
                ReviewRecord(
                    pr_number=90 + i,
                    issue_number=30 + i,
                    timestamp="2026-02-20T10:00:00Z",
                    verdict="request-changes",
                    summary="Missing test coverage",
                    fixes_made=False,
                    categories=["missing_tests"],
                )
            )

        # This review will also have "test" in summary → missing_tests
        review_result = ReviewResult(
            pr_number=101,
            issue_number=42,
            verdict=ReviewVerdict.REQUEST_CHANGES,
            summary="Missing test coverage for edge cases",
            fixes_made=False,
        )
        phase._reviewers.review = AsyncMock(return_value=review_result)
        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.create_issue = AsyncMock(return_value=999)
        phase._prs.submit_review = AsyncMock(return_value=True)

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs([pr], [issue])

        # Should have filed an improvement issue
        phase._prs.create_issue.assert_awaited_once()
        call_args = phase._prs.create_issue.call_args
        assert "[Review Insight]" in call_args.args[0]
        assert "hydra-improve" in call_args.args[2]
        assert "hydra-hitl" in call_args.args[2]

    @pytest.mark.asyncio
    async def test_review_insight_does_not_refile_proposed_category(
        self, config: HydraConfig
    ) -> None:
        """Once a category has been proposed, it should not be re-filed."""
        from review_insights import ReviewInsightStore, ReviewRecord

        phase = _make_phase(config)
        issue = make_issue(42)
        pr = make_pr_info(101, 42, draft=False)

        # Pre-populate and mark as proposed
        store = ReviewInsightStore(config.repo_root / ".hydra" / "memory")
        for i in range(4):
            store.append_review(
                ReviewRecord(
                    pr_number=90 + i,
                    issue_number=30 + i,
                    timestamp="2026-02-20T10:00:00Z",
                    verdict="request-changes",
                    summary="Missing test coverage",
                    fixes_made=False,
                    categories=["missing_tests"],
                )
            )
        store.mark_category_proposed("missing_tests")

        review_result = ReviewResult(
            pr_number=101,
            issue_number=42,
            verdict=ReviewVerdict.REQUEST_CHANGES,
            summary="Missing test coverage",
            fixes_made=False,
        )
        phase._reviewers.review = AsyncMock(return_value=review_result)
        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.create_issue = AsyncMock(return_value=999)
        phase._prs.submit_review = AsyncMock(return_value=True)

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs([pr], [issue])

        # Should NOT have filed an improvement issue
        phase._prs.create_issue.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_review_insight_failure_does_not_crash_review(
        self, config: HydraConfig
    ) -> None:
        """If insight recording fails, the review should still complete."""
        from unittest.mock import patch

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

        # Make the insight store raise
        with patch.object(
            phase._insights, "append_review", side_effect=OSError("disk full")
        ):
            results = await phase.review_prs([pr], [issue])

        # Review should still succeed
        assert len(results) == 1
        assert results[0].merged is True


# ---------------------------------------------------------------------------
# Granular REVIEW_UPDATE status events
# ---------------------------------------------------------------------------


class TestGranularReviewStatusEvents:
    """Tests that review_phase emits granular status events at each lifecycle stage."""

    @pytest.mark.asyncio
    async def test_merge_main_status_emitted(self, config: HydraConfig) -> None:
        """A 'merge_main' event should be published before merging main."""
        bus = EventBus()
        phase = _make_phase(config, event_bus=bus)
        issue = make_issue(42)
        pr = make_pr_info(101, 42)

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

        history = bus.get_history()
        merge_main_events = [
            e
            for e in history
            if e.type == EventType.REVIEW_UPDATE
            and e.data.get("status") == "merge_main"
        ]
        assert len(merge_main_events) == 1
        assert merge_main_events[0].data["pr"] == 101

    @pytest.mark.asyncio
    async def test_conflict_resolution_status_emitted(
        self, config: HydraConfig
    ) -> None:
        """A 'conflict_resolution' event should be published when resolving conflicts."""
        mock_agents = AsyncMock()
        mock_agents._execute = AsyncMock(return_value="transcript")
        mock_agents._verify_result = AsyncMock(return_value=(True, ""))
        bus = EventBus()
        phase = _make_phase(config, agents=mock_agents, event_bus=bus)
        issue = make_issue(42)
        pr = make_pr_info(101, 42)

        phase._reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=True)
        phase._prs.remove_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()
        phase._worktrees.merge_main = AsyncMock(return_value=False)
        phase._worktrees.start_merge_main = AsyncMock(return_value=False)

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs([pr], [issue])

        history = bus.get_history()
        conflict_events = [
            e
            for e in history
            if e.type == EventType.REVIEW_UPDATE
            and e.data.get("status") == "conflict_resolution"
        ]
        # One event from the caller in review_prs, one from the retry loop
        assert len(conflict_events) >= 1
        assert conflict_events[0].data["pr"] == 101

    @pytest.mark.asyncio
    async def test_escalating_status_emitted_on_conflict_failure(
        self, config: HydraConfig
    ) -> None:
        """An 'escalating' event should be published when conflicts can't be resolved."""
        mock_agents = AsyncMock()
        mock_agents._execute = AsyncMock(return_value="transcript")
        mock_agents._verify_result = AsyncMock(return_value=(False, ""))
        bus = EventBus()
        phase = _make_phase(config, agents=mock_agents, event_bus=bus)
        issue = make_issue(42)
        pr = make_pr_info(101, 42)

        phase._prs.post_pr_comment = AsyncMock()
        phase._prs.remove_label = AsyncMock()
        phase._prs.remove_pr_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()
        phase._prs.add_pr_labels = AsyncMock()
        phase._worktrees.merge_main = AsyncMock(return_value=False)
        phase._worktrees.start_merge_main = AsyncMock(return_value=False)
        phase._worktrees.abort_merge = AsyncMock()

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs([pr], [issue])

        history = bus.get_history()
        escalating_events = [
            e
            for e in history
            if e.type == EventType.REVIEW_UPDATE
            and e.data.get("status") == "escalating"
        ]
        assert len(escalating_events) == 1
        assert escalating_events[0].data["pr"] == 101

    @pytest.mark.asyncio
    async def test_merging_status_emitted_before_merge(
        self, config: HydraConfig
    ) -> None:
        """A 'merging' event should be published before merging the PR."""
        bus = EventBus()
        phase = _make_phase(config, event_bus=bus)
        issue = make_issue(42)
        pr = make_pr_info(101, 42)

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

        history = bus.get_history()
        merging_events = [
            e
            for e in history
            if e.type == EventType.REVIEW_UPDATE and e.data.get("status") == "merging"
        ]
        assert len(merging_events) == 1
        assert merging_events[0].data["pr"] == 101

    @pytest.mark.asyncio
    async def test_escalating_status_emitted_on_merge_failure(
        self, config: HydraConfig
    ) -> None:
        """An 'escalating' event should be published when PR merge fails."""
        bus = EventBus()
        phase = _make_phase(config, event_bus=bus)
        issue = make_issue(42)
        pr = make_pr_info(101, 42)

        phase._reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=False)
        phase._prs.post_pr_comment = AsyncMock()
        phase._prs.remove_label = AsyncMock()
        phase._prs.remove_pr_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()
        phase._prs.add_pr_labels = AsyncMock()

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs([pr], [issue])

        history = bus.get_history()
        escalating_events = [
            e
            for e in history
            if e.type == EventType.REVIEW_UPDATE
            and e.data.get("status") == "escalating"
        ]
        assert len(escalating_events) == 1
        assert escalating_events[0].data["pr"] == 101

    @pytest.mark.asyncio
    async def test_ci_wait_status_emitted(self, config: HydraConfig) -> None:
        """A 'ci_wait' event should be published before waiting for CI."""
        from tests.helpers import ConfigFactory

        cfg = ConfigFactory.create(
            max_ci_fix_attempts=2,
            repo_root=config.repo_root,
            worktree_base=config.worktree_base,
            state_file=config.state_file,
        )
        bus = EventBus()
        phase = _make_phase(cfg, event_bus=bus)
        issue = make_issue(42)
        pr = make_pr_info(101, 42)

        phase._reviewers.review = AsyncMock(
            return_value=make_review_result(101, 42, verdict=ReviewVerdict.APPROVE)
        )
        phase._prs.get_pr_diff = AsyncMock(return_value="diff")
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=True)
        phase._prs.wait_for_ci = AsyncMock(return_value=(True, "All checks passed"))
        phase._prs.remove_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()

        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs([pr], [issue])

        history = bus.get_history()
        ci_wait_events = [
            e
            for e in history
            if e.type == EventType.REVIEW_UPDATE and e.data.get("status") == "ci_wait"
        ]
        assert len(ci_wait_events) == 1
        assert ci_wait_events[0].data["pr"] == 101

    @pytest.mark.asyncio
    async def test_ci_fix_status_emitted(self, config: HydraConfig) -> None:
        """A 'ci_fix' event should be published before running the CI fix agent."""
        from tests.helpers import ConfigFactory

        cfg = ConfigFactory.create(
            max_ci_fix_attempts=2,
            repo_root=config.repo_root,
            worktree_base=config.worktree_base,
            state_file=config.state_file,
        )
        bus = EventBus()
        phase = _make_phase(cfg, event_bus=bus)
        issue = make_issue(42)
        pr = make_pr_info(101, 42)

        ci_results = [
            (False, "Failed checks: ci"),
            (True, "All checks passed"),
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

        await phase.review_prs([pr], [issue])

        history = bus.get_history()
        ci_fix_events = [
            e
            for e in history
            if e.type == EventType.REVIEW_UPDATE and e.data.get("status") == "ci_fix"
        ]
        assert len(ci_fix_events) == 1
        assert ci_fix_events[0].data["pr"] == 101

    @pytest.mark.asyncio
    async def test_escalating_status_emitted_on_ci_exhaustion(
        self, config: HydraConfig
    ) -> None:
        """An 'escalating' event should be published when CI fix attempts are exhausted."""
        from tests.helpers import ConfigFactory

        cfg = ConfigFactory.create(
            max_ci_fix_attempts=1,
            repo_root=config.repo_root,
            worktree_base=config.worktree_base,
            state_file=config.state_file,
        )
        bus = EventBus()
        phase = _make_phase(cfg, event_bus=bus)
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

        history = bus.get_history()
        escalating_events = [
            e
            for e in history
            if e.type == EventType.REVIEW_UPDATE
            and e.data.get("status") == "escalating"
        ]
        assert len(escalating_events) == 1
        assert escalating_events[0].data["pr"] == 101

    @pytest.mark.asyncio
    async def test_event_ordering_happy_path(self, config: HydraConfig) -> None:
        """Events should be emitted in order: start -> merge_main -> reviewing -> merging."""
        bus = EventBus()
        phase = _make_phase(config, event_bus=bus)
        issue = make_issue(42)
        pr = make_pr_info(101, 42)

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

        history = bus.get_history()
        review_statuses = [
            e.data["status"] for e in history if e.type == EventType.REVIEW_UPDATE
        ]
        assert review_statuses.index("start") < review_statuses.index("merge_main")
        assert review_statuses.index("merge_main") < review_statuses.index("merging")
        assert review_statuses[-1] == "done"
