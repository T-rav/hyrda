"""Tests for the review skip guard — preventing re-review when no new commits."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config import HydraFlowConfig

from models import ReviewVerdict, StateData
from tests.conftest import IssueFactory, PRInfoFactory, ReviewResultFactory
from tests.helpers import make_review_phase

# ---------------------------------------------------------------------------
# StateData model — last_reviewed_sha field
# ---------------------------------------------------------------------------


class TestStateDataLastReviewedSha:
    """Tests for the last_reviewed_sha field on StateData."""

    def test_defaults_to_empty_dict(self) -> None:
        data = StateData()
        assert data.last_reviewed_sha == {}

    def test_migration_from_old_state_file(self, tmp_path: Path) -> None:
        """Loading a state file without last_reviewed_sha should default to {}."""
        from state import StateTracker

        state_file = tmp_path / "state.json"
        old_data = {
            "current_batch": 5,
            "processed_issues": {"1": "success"},
            "active_worktrees": {},
            "active_branches": {},
            "reviewed_prs": {},
            "last_updated": None,
        }
        state_file.write_text(json.dumps(old_data))

        tracker = StateTracker(state_file)
        assert tracker.get_last_reviewed_sha(101) is None
        assert tracker.get_current_batch() == 5


# ---------------------------------------------------------------------------
# StateTracker — last_reviewed_sha methods
# ---------------------------------------------------------------------------


class TestStateTrackerLastReviewedSha:
    """Tests for set/get/clear last_reviewed_sha on StateTracker."""

    def test_set_and_get_last_reviewed_sha(self, tmp_path: Path) -> None:
        from state import StateTracker

        tracker = StateTracker(tmp_path / "state.json")
        tracker.set_last_reviewed_sha(101, "abc123")
        assert tracker.get_last_reviewed_sha(101) == "abc123"

    def test_get_returns_none_for_unknown(self, tmp_path: Path) -> None:
        from state import StateTracker

        tracker = StateTracker(tmp_path / "state.json")
        assert tracker.get_last_reviewed_sha(999) is None

    def test_clear_last_reviewed_sha(self, tmp_path: Path) -> None:
        from state import StateTracker

        tracker = StateTracker(tmp_path / "state.json")
        tracker.set_last_reviewed_sha(101, "abc123")
        tracker.clear_last_reviewed_sha(101)
        assert tracker.get_last_reviewed_sha(101) is None

    def test_clear_nonexistent_is_noop(self, tmp_path: Path) -> None:
        from state import StateTracker

        tracker = StateTracker(tmp_path / "state.json")
        tracker.clear_last_reviewed_sha(999)
        assert tracker.get_last_reviewed_sha(999) is None

    def test_persists_across_reload(self, tmp_path: Path) -> None:
        from state import StateTracker

        state_file = tmp_path / "state.json"
        tracker = StateTracker(state_file)
        tracker.set_last_reviewed_sha(101, "abc123")

        tracker2 = StateTracker(state_file)
        assert tracker2.get_last_reviewed_sha(101) == "abc123"

    def test_set_overwrites_previous(self, tmp_path: Path) -> None:
        from state import StateTracker

        tracker = StateTracker(tmp_path / "state.json")
        tracker.set_last_reviewed_sha(101, "abc123")
        tracker.set_last_reviewed_sha(101, "def456")
        assert tracker.get_last_reviewed_sha(101) == "def456"

    def test_multiple_prs_tracked_independently(self, tmp_path: Path) -> None:
        from state import StateTracker

        tracker = StateTracker(tmp_path / "state.json")
        tracker.set_last_reviewed_sha(101, "sha_a")
        tracker.set_last_reviewed_sha(102, "sha_b")
        assert tracker.get_last_reviewed_sha(101) == "sha_a"
        assert tracker.get_last_reviewed_sha(102) == "sha_b"

    def test_reset_clears_last_reviewed_sha(self, tmp_path: Path) -> None:
        from state import StateTracker

        tracker = StateTracker(tmp_path / "state.json")
        tracker.set_last_reviewed_sha(101, "abc123")
        tracker.reset()
        assert tracker.get_last_reviewed_sha(101) is None


# ---------------------------------------------------------------------------
# PRManager — get_pr_reviews
# ---------------------------------------------------------------------------


class TestGetPrReviews:
    """Tests for PRManager.get_pr_reviews."""

    @pytest.mark.asyncio
    async def test_returns_review_list(self, config: HydraFlowConfig) -> None:
        from pr_manager import PRManager

        pr_mgr = PRManager(config, AsyncMock())
        reviews = [
            {"author": "bot-user", "state": "CHANGES_REQUESTED"},
            {"author": "human", "state": "APPROVED"},
        ]
        pr_mgr._run_gh = AsyncMock(return_value=json.dumps(reviews))

        result = await pr_mgr.get_pr_reviews(101)
        assert len(result) == 2
        assert result[0]["state"] == "CHANGES_REQUESTED"
        assert result[1]["author"] == "human"

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self, config: HydraFlowConfig) -> None:
        from pr_manager import PRManager

        pr_mgr = PRManager(config, AsyncMock())
        pr_mgr._run_gh = AsyncMock(side_effect=RuntimeError("API error"))

        result = await pr_mgr.get_pr_reviews(101)
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_json_decode_error(
        self, config: HydraFlowConfig
    ) -> None:
        from pr_manager import PRManager

        pr_mgr = PRManager(config, AsyncMock())
        pr_mgr._run_gh = AsyncMock(return_value="not json")

        result = await pr_mgr.get_pr_reviews(101)
        assert result == []


# ---------------------------------------------------------------------------
# PRManager — get_pr_head_sha
# ---------------------------------------------------------------------------


class TestGetPrHeadSha:
    """Tests for PRManager.get_pr_head_sha."""

    @pytest.mark.asyncio
    async def test_returns_sha_string(self, config: HydraFlowConfig) -> None:
        from pr_manager import PRManager

        pr_mgr = PRManager(config, AsyncMock())
        pr_mgr._run_gh = AsyncMock(return_value="abc123def456\n")

        result = await pr_mgr.get_pr_head_sha(101)
        assert result == "abc123def456"

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self, config: HydraFlowConfig) -> None:
        from pr_manager import PRManager

        pr_mgr = PRManager(config, AsyncMock())
        pr_mgr._run_gh = AsyncMock(side_effect=RuntimeError("API error"))

        result = await pr_mgr.get_pr_head_sha(101)
        assert result == ""


# ---------------------------------------------------------------------------
# ReviewPhase — _should_skip_review
# ---------------------------------------------------------------------------


class TestShouldSkipReview:
    """Tests for ReviewPhase._should_skip_review."""

    @pytest.mark.asyncio
    async def test_skip_when_sha_matches(self, config: HydraFlowConfig) -> None:
        """Skip review when last reviewed SHA matches current HEAD."""
        phase = make_review_phase(config)
        pr = PRInfoFactory.create()

        phase._prs.get_pr_head_sha = AsyncMock(return_value="abc123")
        phase._state.set_last_reviewed_sha(pr.number, "abc123")

        assert await phase._should_skip_review(pr) is True

    @pytest.mark.asyncio
    async def test_proceed_when_sha_differs(self, config: HydraFlowConfig) -> None:
        """Proceed when new commits have been pushed since last review."""
        phase = make_review_phase(config)
        pr = PRInfoFactory.create()

        phase._prs.get_pr_head_sha = AsyncMock(return_value="new_sha")
        phase._state.set_last_reviewed_sha(pr.number, "old_sha")

        assert await phase._should_skip_review(pr) is False

    @pytest.mark.asyncio
    async def test_proceed_when_no_prior_review(self, config: HydraFlowConfig) -> None:
        """Proceed when no last_reviewed_sha exists (first review)."""
        phase = make_review_phase(config)
        pr = PRInfoFactory.create()

        phase._prs.get_pr_head_sha = AsyncMock(return_value="abc123")
        # No set_last_reviewed_sha call — returns None

        assert await phase._should_skip_review(pr) is False

    @pytest.mark.asyncio
    async def test_proceed_when_head_sha_fetch_fails(
        self, config: HydraFlowConfig
    ) -> None:
        """Proceed (safe fallback) when HEAD SHA cannot be determined."""
        phase = make_review_phase(config)
        pr = PRInfoFactory.create()

        phase._prs.get_pr_head_sha = AsyncMock(return_value="")

        assert await phase._should_skip_review(pr) is False


# ---------------------------------------------------------------------------
# ReviewPhase — SHA recorded after review
# ---------------------------------------------------------------------------


class TestShaRecordedAfterReview:
    """Tests that last_reviewed_sha is set after a review completes."""

    @pytest.mark.asyncio
    async def test_sha_recorded_during_review(self, config: HydraFlowConfig) -> None:
        """Verify set_last_reviewed_sha is called with the HEAD SHA after review."""
        phase = make_review_phase(config)
        issue = IssueFactory.create()
        pr = PRInfoFactory.create()

        phase._reviewers.review = AsyncMock(return_value=ReviewResultFactory.create())
        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.get_pr_diff_names = AsyncMock(return_value=[])
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=True)
        phase._prs.get_pr_head_sha = AsyncMock(return_value="review_sha_123")
        phase._prs.post_pr_comment = AsyncMock()
        phase._prs.submit_review = AsyncMock(return_value=True)
        phase._prs.swap_pipeline_labels = AsyncMock()
        phase._prs.remove_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()
        phase._prs.post_comment = AsyncMock()

        # Ensure worktree path exists
        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        # Spy on set_last_reviewed_sha to verify it was called
        with patch.object(
            phase._state,
            "set_last_reviewed_sha",
            wraps=phase._state.set_last_reviewed_sha,
        ) as spy:
            await phase.review_prs([pr], [issue])
            spy.assert_called_with(pr.number, "review_sha_123")

    @pytest.mark.asyncio
    async def test_sha_cleared_after_successful_merge(
        self, config: HydraFlowConfig
    ) -> None:
        phase = make_review_phase(config)
        issue = IssueFactory.create()
        pr = PRInfoFactory.create()

        # APPROVE verdict with successful merge — SHA recorded then cleared
        phase._reviewers.review = AsyncMock(return_value=ReviewResultFactory.create())
        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.get_pr_diff_names = AsyncMock(return_value=[])
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.merge_pr = AsyncMock(return_value=True)
        phase._prs.get_pr_head_sha = AsyncMock(return_value="review_sha_123")
        phase._prs.post_pr_comment = AsyncMock()
        phase._prs.submit_review = AsyncMock(return_value=True)
        phase._prs.swap_pipeline_labels = AsyncMock()
        phase._prs.remove_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()
        phase._prs.post_comment = AsyncMock()

        # Ensure worktree path exists
        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs([pr], [issue])

        # SHA should be cleared after successful merge
        assert phase._state.get_last_reviewed_sha(pr.number) is None


# ---------------------------------------------------------------------------
# ReviewPhase — SHA cleared on re-queue
# ---------------------------------------------------------------------------


class TestShaClearedOnRequeue:
    """Tests that last_reviewed_sha is cleared when PR is re-queued."""

    @pytest.mark.asyncio
    async def test_sha_cleared_on_rejected_review_requeue(
        self, config: HydraFlowConfig
    ) -> None:
        phase = make_review_phase(config)
        issue = IssueFactory.create()
        pr = PRInfoFactory.create()

        # Set up a REQUEST_CHANGES result so the PR is re-queued
        reject_result = ReviewResultFactory.create(
            verdict=ReviewVerdict.REQUEST_CHANGES,
            summary="Needs fixes",
            transcript="review",
        )
        phase._reviewers.review = AsyncMock(return_value=reject_result)
        phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
        phase._prs.get_pr_diff_names = AsyncMock(return_value=[])
        phase._prs.push_branch = AsyncMock(return_value=True)
        phase._prs.get_pr_head_sha = AsyncMock(return_value="sha_before_requeue")
        phase._prs.post_pr_comment = AsyncMock()
        phase._prs.submit_review = AsyncMock(return_value=True)
        phase._prs.swap_pipeline_labels = AsyncMock()
        phase._prs.remove_label = AsyncMock()
        phase._prs.add_labels = AsyncMock()
        phase._prs.post_comment = AsyncMock()

        # Pre-set SHA to verify it gets cleared
        phase._state.set_last_reviewed_sha(pr.number, "old_sha")

        # Ensure worktree path exists
        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        await phase.review_prs([pr], [issue])

        # SHA should be cleared since the PR was re-queued for implementation
        assert phase._state.get_last_reviewed_sha(pr.number) is None


# ---------------------------------------------------------------------------
# ReviewPhase — SHA cleared on HITL escalation
# ---------------------------------------------------------------------------


class TestShaClearedOnHitlEscalation:
    """Tests that last_reviewed_sha is cleared on HITL escalation."""

    @pytest.mark.asyncio
    async def test_sha_cleared_on_hitl_escalation(
        self, config: HydraFlowConfig
    ) -> None:
        phase = make_review_phase(config)
        pr = PRInfoFactory.create()

        # Pre-set SHA
        phase._state.set_last_reviewed_sha(pr.number, "some_sha")

        phase._prs.swap_pipeline_labels = AsyncMock()
        phase._prs.post_pr_comment = AsyncMock()

        await phase._escalate_to_hitl(
            issue_number=pr.issue_number,
            pr_number=pr.number,
            cause="Test escalation",
            origin_label="hydraflow-review",
            comment="Escalating for test",
        )

        assert phase._state.get_last_reviewed_sha(pr.number) is None


# ---------------------------------------------------------------------------
# ReviewPhase — skipped PR returns benign ReviewResult
# ---------------------------------------------------------------------------


class TestSkippedPrReturnsResult:
    """Tests that a skipped PR returns a ReviewResult without errors."""

    @pytest.mark.asyncio
    async def test_skipped_pr_returns_result_with_summary(
        self, config: HydraFlowConfig
    ) -> None:
        phase = make_review_phase(config)
        issue = IssueFactory.create()
        pr = PRInfoFactory.create()

        # Set up skip condition: SHA matches
        phase._prs.get_pr_head_sha = AsyncMock(return_value="matched_sha")
        phase._state.set_last_reviewed_sha(pr.number, "matched_sha")

        # Ensure worktree path exists
        wt = config.worktree_base / "issue-42"
        wt.mkdir(parents=True, exist_ok=True)

        results = await phase.review_prs([pr], [issue])

        assert len(results) == 1
        assert results[0].summary == "Skipped — already reviewed at current HEAD"
        assert results[0].pr_number == pr.number
        assert results[0].issue_number == pr.issue_number

        # review() should NOT have been called
        phase._reviewers.review.assert_not_awaited()  # type: ignore[union-attr]
