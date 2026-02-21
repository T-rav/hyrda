"""Tests for dx/hydra/state.py - StateTracker class."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from models import LifetimeStats, StateData
from state import StateTracker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_tracker(tmp_path: Path, *, filename: str = "state.json") -> StateTracker:
    """Return a StateTracker backed by a temp file."""
    return StateTracker(tmp_path / filename)


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestInitialization:
    def test_defaults_when_no_file_exists(self, tmp_path: Path) -> None:
        """A fresh tracker with no backing file should start from defaults."""
        tracker = make_tracker(tmp_path)
        assert tracker.get_current_batch() == 0
        assert tracker.get_active_worktrees() == {}
        assert tracker.get_issue_status(1) is None
        assert tracker.get_branch(1) is None
        assert tracker.get_pr_status(1) is None

    def test_defaults_structure_matches_expected_keys(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        d = tracker.to_dict()
        assert "current_batch" in d
        assert "processed_issues" in d
        assert "active_worktrees" in d
        assert "active_branches" in d
        assert "reviewed_prs" in d
        assert "last_updated" in d

    def test_loads_existing_file_on_init(self, tmp_path: Path) -> None:
        """If a state file already exists on disk it should be loaded."""
        state_file = tmp_path / "state.json"
        initial_data = {
            "current_batch": 3,
            "processed_issues": {"7": "success"},
            "active_worktrees": {},
            "active_branches": {},
            "reviewed_prs": {},
            "last_updated": None,
        }
        state_file.write_text(json.dumps(initial_data))

        tracker = StateTracker(state_file)
        assert tracker.get_current_batch() == 3
        assert tracker.get_issue_status(7) == "success"


# ---------------------------------------------------------------------------
# Persistence (load / save round-trip)
# ---------------------------------------------------------------------------


class TestLoadSave:
    def test_save_creates_file(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        state_file = tmp_path / "state.json"
        assert not state_file.exists()
        tracker.save()
        assert state_file.exists()

    def test_save_writes_valid_json(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.save()
        raw = (tmp_path / "state.json").read_text()
        data = json.loads(raw)  # must not raise
        assert isinstance(data, dict)

    def test_save_sets_last_updated(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.save()
        d = tracker.to_dict()
        assert d["last_updated"] is not None
        # Should be a valid ISO string
        assert "T" in d["last_updated"]

    def test_round_trip_preserves_data(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        tracker = StateTracker(state_file)
        tracker.mark_issue(10, "success")
        tracker.set_worktree(10, "/tmp/wt-10")
        tracker.set_branch(10, "agent/issue-10")
        tracker.mark_pr(99, "merged")
        tracker.increment_batch()

        # Load a second tracker from the same file
        tracker2 = StateTracker(state_file)
        assert tracker2.get_issue_status(10) == "success"
        assert tracker2.get_active_worktrees() == {10: "/tmp/wt-10"}
        assert tracker2.get_branch(10) == "agent/issue-10"
        assert tracker2.get_pr_status(99) == "merged"
        assert tracker2.get_current_batch() == 1

    def test_explicit_load_returns_dict(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        result = tracker.load()
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Issue tracking
# ---------------------------------------------------------------------------


class TestIssueTracking:
    def test_mark_issue_stores_status(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.mark_issue(42, "in_progress")
        assert tracker.get_issue_status(42) == "in_progress"

    def test_mark_issue_overwrites_previous_status(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.mark_issue(42, "in_progress")
        tracker.mark_issue(42, "success")
        assert tracker.get_issue_status(42) == "success"

    def test_mark_issue_triggers_save(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        tracker = StateTracker(state_file)
        tracker.mark_issue(5, "success")
        # File must exist after mark_issue
        assert state_file.exists()

    def test_is_processed_true_for_success(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.mark_issue(1, "success")
        assert tracker.is_processed(1) is True

    def test_is_processed_false_for_failed(self, tmp_path: Path) -> None:
        """Failed issues are NOT processed — they should be retried."""
        tracker = make_tracker(tmp_path)
        tracker.mark_issue(2, "failed")
        assert tracker.is_processed(2) is False

    def test_is_processed_false_for_in_progress(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.mark_issue(3, "in_progress")
        assert tracker.is_processed(3) is False

    def test_is_processed_false_for_unknown_issue(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        assert tracker.is_processed(999) is False

    def test_get_issue_status_returns_none_for_unknown(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        assert tracker.get_issue_status(123) is None

    def test_multiple_issues_tracked_independently(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.mark_issue(1, "success")
        tracker.mark_issue(2, "failed")
        tracker.mark_issue(3, "in_progress")

        assert tracker.get_issue_status(1) == "success"
        assert tracker.get_issue_status(2) == "failed"
        assert tracker.get_issue_status(3) == "in_progress"


# ---------------------------------------------------------------------------
# Worktree tracking
# ---------------------------------------------------------------------------


class TestWorktreeTracking:
    def test_set_worktree_stores_path(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.set_worktree(7, "/tmp/wt-7")
        assert tracker.get_active_worktrees() == {7: "/tmp/wt-7"}

    def test_set_worktree_triggers_save(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        tracker = StateTracker(state_file)
        tracker.set_worktree(7, "/tmp/wt-7")
        assert state_file.exists()

    def test_remove_worktree_deletes_entry(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.set_worktree(7, "/tmp/wt-7")
        tracker.remove_worktree(7)
        assert 7 not in tracker.get_active_worktrees()

    def test_remove_worktree_nonexistent_is_noop(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        # Should not raise
        tracker.remove_worktree(999)
        assert tracker.get_active_worktrees() == {}

    def test_get_active_worktrees_returns_int_keys(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.set_worktree(10, "/wt/10")
        tracker.set_worktree(20, "/wt/20")
        wt = tracker.get_active_worktrees()
        assert all(isinstance(k, int) for k in wt)

    def test_multiple_worktrees(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.set_worktree(1, "/wt/1")
        tracker.set_worktree(2, "/wt/2")
        assert tracker.get_active_worktrees() == {1: "/wt/1", 2: "/wt/2"}

    def test_remove_one_worktree_leaves_others(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.set_worktree(1, "/wt/1")
        tracker.set_worktree(2, "/wt/2")
        tracker.remove_worktree(1)
        assert tracker.get_active_worktrees() == {2: "/wt/2"}


# ---------------------------------------------------------------------------
# Branch tracking
# ---------------------------------------------------------------------------


class TestBranchTracking:
    def test_set_and_get_branch(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.set_branch(42, "agent/issue-42")
        assert tracker.get_branch(42) == "agent/issue-42"

    def test_get_branch_returns_none_for_unknown(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        assert tracker.get_branch(999) is None

    def test_set_branch_triggers_save(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        tracker = StateTracker(state_file)
        tracker.set_branch(1, "agent/issue-1")
        assert state_file.exists()

    def test_set_branch_overwrites(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.set_branch(5, "branch-v1")
        tracker.set_branch(5, "branch-v2")
        assert tracker.get_branch(5) == "branch-v2"

    def test_multiple_branches_tracked_independently(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.set_branch(1, "agent/issue-1")
        tracker.set_branch(2, "agent/issue-2")
        assert tracker.get_branch(1) == "agent/issue-1"
        assert tracker.get_branch(2) == "agent/issue-2"


# ---------------------------------------------------------------------------
# PR tracking
# ---------------------------------------------------------------------------


class TestPRTracking:
    def test_mark_pr_stores_status(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.mark_pr(101, "open")
        assert tracker.get_pr_status(101) == "open"

    def test_mark_pr_overwrites_status(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.mark_pr(101, "open")
        tracker.mark_pr(101, "merged")
        assert tracker.get_pr_status(101) == "merged"

    def test_get_pr_status_returns_none_for_unknown(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        assert tracker.get_pr_status(999) is None

    def test_mark_pr_triggers_save(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        tracker = StateTracker(state_file)
        tracker.mark_pr(50, "open")
        assert state_file.exists()

    def test_multiple_prs_tracked_independently(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.mark_pr(1, "open")
        tracker.mark_pr(2, "closed")
        assert tracker.get_pr_status(1) == "open"
        assert tracker.get_pr_status(2) == "closed"


# ---------------------------------------------------------------------------
# HITL origin tracking
# ---------------------------------------------------------------------------


class TestHITLOriginTracking:
    def test_set_hitl_origin_stores_label(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.set_hitl_origin(42, "hydra-review")
        assert tracker.get_hitl_origin(42) == "hydra-review"

    def test_get_hitl_origin_returns_none_for_unknown(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        assert tracker.get_hitl_origin(999) is None

    def test_set_hitl_origin_triggers_save(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        tracker = StateTracker(state_file)
        tracker.set_hitl_origin(42, "hydra-review")
        assert state_file.exists()

    def test_set_hitl_origin_overwrites(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.set_hitl_origin(42, "hydra-find")
        tracker.set_hitl_origin(42, "hydra-review")
        assert tracker.get_hitl_origin(42) == "hydra-review"

    def test_remove_hitl_origin_deletes_entry(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.set_hitl_origin(42, "hydra-review")
        tracker.remove_hitl_origin(42)
        assert tracker.get_hitl_origin(42) is None

    def test_remove_hitl_origin_nonexistent_is_noop(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        # Should not raise
        tracker.remove_hitl_origin(999)
        assert tracker.get_hitl_origin(999) is None

    def test_multiple_origins_tracked_independently(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.set_hitl_origin(1, "hydra-find")
        tracker.set_hitl_origin(2, "hydra-review")
        assert tracker.get_hitl_origin(1) == "hydra-find"
        assert tracker.get_hitl_origin(2) == "hydra-review"

    def test_hitl_origin_persists_across_reload(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        tracker = StateTracker(state_file)
        tracker.set_hitl_origin(42, "hydra-review")

        tracker2 = StateTracker(state_file)
        assert tracker2.get_hitl_origin(42) == "hydra-review"

    def test_reset_clears_hitl_origins(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.set_hitl_origin(42, "hydra-review")
        tracker.reset()
        assert tracker.get_hitl_origin(42) is None

    def test_migration_adds_hitl_origins_to_old_file(self, tmp_path: Path) -> None:
        """Loading a state file without hitl_origins should default to {}."""
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
        assert tracker.get_hitl_origin(1) is None
        # Existing data is preserved
        assert tracker.get_current_batch() == 5
        assert tracker.get_issue_status(1) == "success"


# ---------------------------------------------------------------------------
# HITL cause tracking
# ---------------------------------------------------------------------------


class TestHITLCauseTracking:
    def test_set_hitl_cause_stores_cause(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.set_hitl_cause(42, "CI failed after 2 fix attempts")
        assert tracker.get_hitl_cause(42) == "CI failed after 2 fix attempts"

    def test_get_hitl_cause_returns_none_for_unknown(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        assert tracker.get_hitl_cause(999) is None

    def test_set_hitl_cause_triggers_save(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        tracker = StateTracker(state_file)
        tracker.set_hitl_cause(42, "Merge conflict with main branch")
        assert state_file.exists()

    def test_set_hitl_cause_overwrites(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.set_hitl_cause(42, "First cause")
        tracker.set_hitl_cause(42, "Second cause")
        assert tracker.get_hitl_cause(42) == "Second cause"

    def test_remove_hitl_cause_deletes_entry(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.set_hitl_cause(42, "Some cause")
        tracker.remove_hitl_cause(42)
        assert tracker.get_hitl_cause(42) is None

    def test_remove_hitl_cause_nonexistent_is_noop(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        # Should not raise
        tracker.remove_hitl_cause(999)
        assert tracker.get_hitl_cause(999) is None

    def test_multiple_causes_tracked_independently(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.set_hitl_cause(1, "CI failed after 2 fix attempts")
        tracker.set_hitl_cause(2, "Merge conflict with main branch")
        assert tracker.get_hitl_cause(1) == "CI failed after 2 fix attempts"
        assert tracker.get_hitl_cause(2) == "Merge conflict with main branch"

    def test_hitl_cause_persists_across_reload(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        tracker = StateTracker(state_file)
        tracker.set_hitl_cause(42, "PR merge failed on GitHub")

        tracker2 = StateTracker(state_file)
        assert tracker2.get_hitl_cause(42) == "PR merge failed on GitHub"

    def test_reset_clears_hitl_causes(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.set_hitl_cause(42, "Some cause")
        tracker.reset()
        assert tracker.get_hitl_cause(42) is None

    def test_migration_adds_hitl_causes_to_old_file(self, tmp_path: Path) -> None:
        """Loading a state file without hitl_causes should default to {}."""
        state_file = tmp_path / "state.json"
        old_data = {
            "current_batch": 5,
            "processed_issues": {"1": "success"},
            "active_worktrees": {},
            "active_branches": {},
            "reviewed_prs": {},
            "hitl_origins": {"42": "hydra-review"},
            "last_updated": None,
        }
        state_file.write_text(json.dumps(old_data))

        tracker = StateTracker(state_file)
        assert tracker.get_hitl_cause(42) is None
        # Existing data is preserved
        assert tracker.get_current_batch() == 5
        assert tracker.get_issue_status(1) == "success"


# ---------------------------------------------------------------------------
# Batch tracking
# ---------------------------------------------------------------------------


class TestBatchTracking:
    def test_initial_batch_is_zero(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        assert tracker.get_current_batch() == 0

    def test_increment_batch_returns_new_value(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        result = tracker.increment_batch()
        assert result == 1

    def test_increment_batch_multiple_times(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.increment_batch()
        tracker.increment_batch()
        result = tracker.increment_batch()
        assert result == 3
        assert tracker.get_current_batch() == 3

    def test_increment_batch_triggers_save(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        tracker = StateTracker(state_file)
        tracker.increment_batch()
        assert state_file.exists()

    def test_increment_batch_persists(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        tracker = StateTracker(state_file)
        tracker.increment_batch()
        tracker.increment_batch()

        tracker2 = StateTracker(state_file)
        assert tracker2.get_current_batch() == 2


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------


class TestReset:
    def test_reset_clears_processed_issues(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.mark_issue(1, "success")
        tracker.reset()
        assert tracker.get_issue_status(1) is None

    def test_reset_clears_active_worktrees(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.set_worktree(1, "/wt/1")
        tracker.reset()
        assert tracker.get_active_worktrees() == {}

    def test_reset_clears_active_branches(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.set_branch(1, "agent/issue-1")
        tracker.reset()
        assert tracker.get_branch(1) is None

    def test_reset_clears_reviewed_prs(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.mark_pr(99, "merged")
        tracker.reset()
        assert tracker.get_pr_status(99) is None

    def test_reset_resets_batch_to_zero(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.increment_batch()
        tracker.increment_batch()
        tracker.reset()
        assert tracker.get_current_batch() == 0

    def test_reset_persists_to_disk(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        tracker = StateTracker(state_file)
        tracker.mark_issue(1, "success")
        tracker.reset()

        tracker2 = StateTracker(state_file)
        assert tracker2.get_issue_status(1) is None
        assert tracker2.get_current_batch() == 0

    def test_reset_clears_all_state_at_once(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.mark_issue(1, "success")
        tracker.set_worktree(1, "/wt/1")
        tracker.set_branch(1, "agent/issue-1")
        tracker.mark_pr(10, "open")
        tracker.set_hitl_origin(1, "hydra-review")
        tracker.set_hitl_cause(1, "CI failed after 2 fix attempts")
        tracker.increment_batch()

        tracker.reset()

        assert tracker.get_current_batch() == 0
        assert tracker.get_active_worktrees() == {}
        assert tracker.get_issue_status(1) is None
        assert tracker.get_branch(1) is None
        assert tracker.get_pr_status(10) is None
        assert tracker.get_hitl_origin(1) is None
        assert tracker.get_hitl_cause(1) is None


# ---------------------------------------------------------------------------
# Corrupt file handling
# ---------------------------------------------------------------------------


class TestCorruptFileHandling:
    def test_corrupt_json_falls_back_to_defaults(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        state_file.write_text("{ this is not valid JSON }")

        # Should not raise; should silently reset to defaults
        tracker = StateTracker(state_file)
        assert tracker.get_current_batch() == 0
        assert tracker.get_active_worktrees() == {}

    def test_empty_file_falls_back_to_defaults(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        state_file.write_text("")

        tracker = StateTracker(state_file)
        assert tracker.get_current_batch() == 0

    def test_load_with_corrupt_file_falls_back_to_defaults(
        self, tmp_path: Path
    ) -> None:
        state_file = tmp_path / "state.json"
        # Start with a valid tracker then corrupt it
        tracker = StateTracker(state_file)
        tracker.mark_issue(1, "success")

        state_file.write_text("{ bad json !!!")
        result = tracker.load()

        assert isinstance(result, dict)
        assert result.get("processed_issues") == {}

    def test_corrupt_file_does_not_raise(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        state_file.write_text("null")

        # Constructing a tracker on a file containing 'null' should not raise
        try:
            tracker = StateTracker(state_file)
            _ = tracker.get_current_batch()
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"Unexpected exception for corrupt file: {exc}")


# ---------------------------------------------------------------------------
# to_dict
# ---------------------------------------------------------------------------


class TestToDict:
    def test_to_dict_returns_dict(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        assert isinstance(tracker.to_dict(), dict)

    def test_to_dict_contains_all_default_keys(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        d = tracker.to_dict()
        expected_keys = {
            "current_batch",
            "processed_issues",
            "active_worktrees",
            "active_branches",
            "reviewed_prs",
            "hitl_origins",
            "hitl_causes",
            "review_attempts",
            "review_feedback",
            "worker_result_meta",
            "lifetime_stats",
            "last_updated",
        }
        assert expected_keys.issubset(d.keys())

    def test_to_dict_returns_copy_not_reference(self, tmp_path: Path) -> None:
        """Mutating the returned dict must not affect the tracker's internal state."""
        tracker = make_tracker(tmp_path)
        d = tracker.to_dict()
        d["current_batch"] = 999
        assert tracker.get_current_batch() == 0

    def test_to_dict_contains_lifetime_stats_key(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        d = tracker.to_dict()
        assert "lifetime_stats" in d

    def test_to_dict_reflects_current_state(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.mark_issue(7, "success")
        tracker.increment_batch()
        d = tracker.to_dict()
        assert d["processed_issues"]["7"] == "success"
        assert d["current_batch"] == 1


# ---------------------------------------------------------------------------
# Lifetime stats
# ---------------------------------------------------------------------------


class TestLifetimeStats:
    def test_defaults_include_lifetime_stats(self, tmp_path: Path) -> None:
        """A fresh tracker should include zeroed lifetime_stats."""
        tracker = make_tracker(tmp_path)
        stats = tracker.get_lifetime_stats()
        assert stats == {"issues_completed": 0, "prs_merged": 0, "issues_created": 0}

    def test_record_issue_completed_increments(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.record_issue_completed()
        assert tracker.get_lifetime_stats()["issues_completed"] == 1

    def test_record_pr_merged_increments(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.record_pr_merged()
        assert tracker.get_lifetime_stats()["prs_merged"] == 1

    def test_record_issue_created_increments(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.record_issue_created()
        assert tracker.get_lifetime_stats()["issues_created"] == 1

    def test_multiple_increments_accumulate(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        for _ in range(3):
            tracker.record_pr_merged()
        assert tracker.get_lifetime_stats()["prs_merged"] == 3

    def test_get_lifetime_stats_returns_copy(self, tmp_path: Path) -> None:
        """Mutating the returned dict must not affect internal state."""
        tracker = make_tracker(tmp_path)
        tracker.record_issue_completed()
        stats = tracker.get_lifetime_stats()
        stats["issues_completed"] = 999
        assert tracker.get_lifetime_stats()["issues_completed"] == 1

    def test_lifetime_stats_persist_across_reload(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        tracker = StateTracker(state_file)
        tracker.record_pr_merged()
        tracker.record_issue_created()
        tracker.record_issue_created()

        tracker2 = StateTracker(state_file)
        stats = tracker2.get_lifetime_stats()
        assert stats["prs_merged"] == 1
        assert stats["issues_created"] == 2

    def test_reset_preserves_lifetime_stats(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.record_pr_merged()
        tracker.record_issue_completed()
        tracker.record_issue_created()
        tracker.mark_issue(1, "success")
        tracker.increment_batch()

        tracker.reset()

        # Batch and issues should be cleared
        assert tracker.get_current_batch() == 0
        assert tracker.get_issue_status(1) is None
        # Lifetime stats should survive
        stats = tracker.get_lifetime_stats()
        assert stats["prs_merged"] == 1
        assert stats["issues_completed"] == 1
        assert stats["issues_created"] == 1

    def test_migration_adds_lifetime_stats_to_old_file(self, tmp_path: Path) -> None:
        """Loading a state file without lifetime_stats should inject zero defaults."""
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
        stats = tracker.get_lifetime_stats()
        assert stats == {"issues_completed": 0, "prs_merged": 0, "issues_created": 0}
        # Existing data is preserved
        assert tracker.get_current_batch() == 5
        assert tracker.get_issue_status(1) == "success"


# ---------------------------------------------------------------------------
# Atomic save
# ---------------------------------------------------------------------------


class TestAtomicSave:
    def test_save_uses_atomic_replace(self, tmp_path: Path) -> None:
        """save() should write to a temp file then atomically replace."""
        tracker = make_tracker(tmp_path)
        with patch("state.os.replace", wraps=os.replace) as mock_replace:
            tracker.save()
            mock_replace.assert_called_once()
            args = mock_replace.call_args[0]
            # Second arg should be the state file path
            assert str(args[1]) == str(tmp_path / "state.json")
            # First arg (temp file) should no longer exist after replace
            assert not Path(args[0]).exists()

    def test_save_cleans_up_temp_on_write_failure(self, tmp_path: Path) -> None:
        """If writing to the temp file fails, the temp file should be removed."""
        tracker = make_tracker(tmp_path)
        state_dir = tmp_path

        with (
            patch("state.os.fdopen", side_effect=OSError("disk full")),
            pytest.raises(OSError, match="disk full"),
        ):
            tracker.save()

        # No leftover temp files
        temps = list(state_dir.glob(".state-*.tmp"))
        assert temps == []

    def test_save_cleans_up_temp_on_fsync_failure(self, tmp_path: Path) -> None:
        """If fsync fails, the temp file should be cleaned up."""
        tracker = make_tracker(tmp_path)

        with (
            patch("state.os.fsync", side_effect=OSError("fsync failed")),
            pytest.raises(OSError, match="fsync failed"),
        ):
            tracker.save()

        temps = list(tmp_path.glob(".state-*.tmp"))
        assert temps == []

    def test_save_does_not_corrupt_existing_file_on_failure(
        self, tmp_path: Path
    ) -> None:
        """A failed save must leave the original state file intact."""
        state_file = tmp_path / "state.json"
        tracker = StateTracker(state_file)
        tracker.mark_issue(1, "success")

        original_content = state_file.read_text()

        with (
            patch("state.os.fsync", side_effect=OSError("fsync failed")),
            pytest.raises(OSError),
        ):
            tracker.save()

        # Original file should be unchanged
        assert state_file.read_text() == original_content
        data = json.loads(state_file.read_text())
        assert data["processed_issues"]["1"] == "success"

    def test_no_temp_files_left_after_successful_save(self, tmp_path: Path) -> None:
        """After a normal save, no temp files should remain."""
        tracker = make_tracker(tmp_path)
        tracker.save()

        temps = list(tmp_path.glob(".state-*.tmp"))
        assert temps == []

    def test_save_temp_file_in_same_directory(self, tmp_path: Path) -> None:
        """The temp file must be created in the same dir as the state file."""
        tracker = make_tracker(tmp_path)
        with patch(
            "state.tempfile.mkstemp", wraps=__import__("tempfile").mkstemp
        ) as mock_mkstemp:
            tracker.save()
            mock_mkstemp.assert_called_once()
            kwargs = mock_mkstemp.call_args[1]
            assert str(kwargs["dir"]) == str(tmp_path)


# ---------------------------------------------------------------------------
# Review attempt tracking
# ---------------------------------------------------------------------------


class TestReviewAttemptTracking:
    def test_get_review_attempts_defaults_to_zero(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        assert tracker.get_review_attempts(42) == 0

    def test_increment_review_attempts_returns_new_count(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        assert tracker.increment_review_attempts(42) == 1
        assert tracker.increment_review_attempts(42) == 2

    def test_reset_review_attempts_clears_counter(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.increment_review_attempts(42)
        tracker.increment_review_attempts(42)
        tracker.reset_review_attempts(42)
        assert tracker.get_review_attempts(42) == 0

    def test_reset_review_attempts_nonexistent_is_noop(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.reset_review_attempts(999)
        assert tracker.get_review_attempts(999) == 0

    def test_multiple_issues_tracked_independently(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.increment_review_attempts(1)
        tracker.increment_review_attempts(1)
        tracker.increment_review_attempts(2)
        assert tracker.get_review_attempts(1) == 2
        assert tracker.get_review_attempts(2) == 1

    def test_review_attempts_persist_across_reload(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        tracker = StateTracker(state_file)
        tracker.increment_review_attempts(42)
        tracker.increment_review_attempts(42)

        tracker2 = StateTracker(state_file)
        assert tracker2.get_review_attempts(42) == 2

    def test_reset_clears_review_attempts(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.increment_review_attempts(42)
        tracker.reset()
        assert tracker.get_review_attempts(42) == 0


# ---------------------------------------------------------------------------
# Review feedback storage
# ---------------------------------------------------------------------------


class TestReviewFeedbackStorage:
    def test_set_and_get_review_feedback(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.set_review_feedback(42, "Fix the error handling")
        assert tracker.get_review_feedback(42) == "Fix the error handling"

    def test_get_review_feedback_returns_none_for_unknown(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        assert tracker.get_review_feedback(999) is None

    def test_clear_review_feedback(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.set_review_feedback(42, "Some feedback")
        tracker.clear_review_feedback(42)
        assert tracker.get_review_feedback(42) is None

    def test_clear_review_feedback_nonexistent_is_noop(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.clear_review_feedback(999)
        assert tracker.get_review_feedback(999) is None

    def test_review_feedback_persists_across_reload(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        tracker = StateTracker(state_file)
        tracker.set_review_feedback(42, "Needs more tests")

        tracker2 = StateTracker(state_file)
        assert tracker2.get_review_feedback(42) == "Needs more tests"

    def test_set_review_feedback_overwrites(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.set_review_feedback(42, "First feedback")
        tracker.set_review_feedback(42, "Updated feedback")
        assert tracker.get_review_feedback(42) == "Updated feedback"

    def test_reset_clears_review_feedback(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.set_review_feedback(42, "Some feedback")
        tracker.reset()
        assert tracker.get_review_feedback(42) is None


# ---------------------------------------------------------------------------
# StateData / LifetimeStats Pydantic models
# ---------------------------------------------------------------------------


class TestStateDataModel:
    def test_defaults(self) -> None:
        """StateData() should have correct zero/empty defaults."""
        data = StateData()
        assert data.current_batch == 0
        assert data.processed_issues == {}
        assert data.active_worktrees == {}
        assert data.active_branches == {}
        assert data.reviewed_prs == {}
        assert data.hitl_origins == {}
        assert data.hitl_causes == {}
        assert data.review_attempts == {}
        assert data.review_feedback == {}
        assert data.worker_result_meta == {}
        assert data.lifetime_stats == LifetimeStats()
        assert data.last_updated is None

    def test_validates_correct_data(self) -> None:
        """model_validate should accept a well-formed dict."""
        raw = {
            "current_batch": 5,
            "processed_issues": {"1": "success"},
            "active_worktrees": {"2": "/wt/2"},
            "active_branches": {"2": "agent/issue-2"},
            "reviewed_prs": {"10": "merged"},
            "hitl_origins": {"42": "hydra-review"},
            "hitl_causes": {"42": "CI failed after 2 fix attempts"},
            "lifetime_stats": {
                "issues_completed": 3,
                "prs_merged": 1,
                "issues_created": 2,
            },
            "last_updated": "2025-01-01T00:00:00",
        }
        data = StateData.model_validate(raw)
        assert data.current_batch == 5
        assert data.processed_issues["1"] == "success"
        assert data.hitl_causes["42"] == "CI failed after 2 fix attempts"
        assert data.lifetime_stats.prs_merged == 1

    def test_handles_partial_data(self) -> None:
        """Missing keys should get defaults — enables migration from old files."""
        data = StateData.model_validate({"current_batch": 2})
        assert data.current_batch == 2
        assert data.processed_issues == {}
        assert data.lifetime_stats.issues_completed == 0

    def test_rejects_wrong_types(self) -> None:
        """Pydantic should reject structurally invalid data."""
        with pytest.raises(ValidationError):
            StateData.model_validate({"current_batch": "not_an_int"})

    def test_model_dump_roundtrip(self) -> None:
        """model_dump_json → model_validate_json should round-trip."""
        original = StateData(
            current_batch=3,
            processed_issues={"1": "success"},
            lifetime_stats=LifetimeStats(issues_completed=5),
        )
        json_str = original.model_dump_json()
        restored = StateData.model_validate_json(json_str)
        assert restored == original

    def test_save_writes_model_dump_json(self, tmp_path: Path) -> None:
        """The saved file should be parseable by StateData.model_validate_json."""
        tracker = make_tracker(tmp_path)
        tracker.mark_issue(1, "success")
        tracker.record_pr_merged()

        raw = (tmp_path / "state.json").read_text()
        restored = StateData.model_validate_json(raw)
        assert restored.processed_issues["1"] == "success"
        assert restored.lifetime_stats.prs_merged == 1


class TestWorkerResultMeta:
    """Tests for worker result metadata tracking."""

    def test_set_and_get_worker_result_meta(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        meta = {"quality_fix_attempts": 2, "duration_seconds": 120.5, "error": None}
        tracker.set_worker_result_meta(42, meta)
        assert tracker.get_worker_result_meta(42) == meta

    def test_get_returns_empty_for_unknown(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        assert tracker.get_worker_result_meta(999) == {}

    def test_set_triggers_save(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        tracker = StateTracker(state_file)
        tracker.set_worker_result_meta(42, {"quality_fix_attempts": 1})
        assert state_file.exists()

    def test_persists_across_reload(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        tracker = StateTracker(state_file)
        meta = {"quality_fix_attempts": 3, "duration_seconds": 200.0}
        tracker.set_worker_result_meta(42, meta)

        tracker2 = StateTracker(state_file)
        assert tracker2.get_worker_result_meta(42) == meta

    def test_multiple_issues_tracked_independently(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.set_worker_result_meta(1, {"quality_fix_attempts": 0})
        tracker.set_worker_result_meta(2, {"quality_fix_attempts": 3})
        assert tracker.get_worker_result_meta(1) == {"quality_fix_attempts": 0}
        assert tracker.get_worker_result_meta(2) == {"quality_fix_attempts": 3}

    def test_overwrites_previous_meta(self, tmp_path: Path) -> None:
        tracker = make_tracker(tmp_path)
        tracker.set_worker_result_meta(42, {"quality_fix_attempts": 1})
        tracker.set_worker_result_meta(42, {"quality_fix_attempts": 5})
        assert tracker.get_worker_result_meta(42) == {"quality_fix_attempts": 5}

    def test_migration_adds_worker_result_meta_to_old_file(
        self, tmp_path: Path
    ) -> None:
        """Loading a state file without worker_result_meta should default to {}."""
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
        assert tracker.get_worker_result_meta(42) == {}
        assert tracker.get_current_batch() == 5


class TestLifetimeStatsModel:
    def test_defaults(self) -> None:
        stats = LifetimeStats()
        assert stats.issues_completed == 0
        assert stats.prs_merged == 0
        assert stats.issues_created == 0

    def test_model_copy_is_independent(self) -> None:
        """model_copy should produce an independent instance."""
        stats = LifetimeStats(issues_completed=5)
        copy = stats.model_copy()
        copy.issues_completed = 99
        assert stats.issues_completed == 5
