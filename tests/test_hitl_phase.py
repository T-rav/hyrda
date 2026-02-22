"""Tests for hitl_phase.py — HITLPhase."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import TYPE_CHECKING

from events import EventBus, EventType
from hitl_phase import HITLPhase
from issue_store import IssueStore
from models import GitHubIssue
from state import StateTracker

if TYPE_CHECKING:
    from config import HydraFlowConfig

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


def _make_phase(
    config: HydraFlowConfig,
) -> tuple[
    HITLPhase, StateTracker, AsyncMock, AsyncMock, AsyncMock, AsyncMock, EventBus
]:
    """Build a HITLPhase with mock dependencies.

    Returns (phase, state, fetcher_mock, prs_mock, worktrees_mock,
             hitl_runner_mock, bus).
    """
    state = StateTracker(config.state_file)
    bus = EventBus()
    fetcher_mock = AsyncMock()
    fetcher_store = AsyncMock()
    store = IssueStore(config, fetcher_store, bus)
    worktrees = AsyncMock()
    worktrees.create = AsyncMock(return_value=config.worktree_base / "issue-42")
    worktrees.destroy = AsyncMock()
    hitl_runner = AsyncMock()
    prs = AsyncMock()
    prs.remove_label = AsyncMock()
    prs.add_labels = AsyncMock()
    prs.push_branch = AsyncMock(return_value=True)
    prs.post_comment = AsyncMock()
    stop_event = asyncio.Event()
    phase = HITLPhase(
        config,
        state,
        store,
        fetcher_mock,
        worktrees,
        hitl_runner,
        prs,
        bus,
        stop_event,
    )
    return phase, state, fetcher_mock, prs, worktrees, hitl_runner, bus


# ---------------------------------------------------------------------------
# HITL phase — process_corrections & _process_one_hitl
# ---------------------------------------------------------------------------


class TestHITLPhaseProcessing:
    """Tests for HITLPhase correction processing."""

    @pytest.mark.asyncio
    async def test_process_corrections_skips_when_empty(
        self, config: HydraFlowConfig
    ) -> None:
        phase, _state, _fetcher, prs, _wt, _runner, _bus = _make_phase(config)

        await phase.process_corrections()

        prs.remove_label.assert_not_called()

    @pytest.mark.asyncio
    async def test_success_restores_origin_label(self, config: HydraFlowConfig) -> None:
        """On success, the origin label should be restored."""
        from models import HITLResult

        phase, state, fetcher, prs, wt, runner, _bus = _make_phase(config)
        issue = make_issue(42, title="Test HITL", body="Fix it")

        fetcher.fetch_issue_by_number = AsyncMock(return_value=issue)
        state.set_hitl_origin(42, "hydraflow-review")
        state.set_hitl_cause(42, "CI failed")

        runner.run = AsyncMock(return_value=HITLResult(issue_number=42, success=True))

        semaphore = asyncio.Semaphore(1)
        await phase._process_one_hitl(42, "Fix the tests", semaphore)

        # Verify origin label was restored
        add_labels_calls = [c.args for c in prs.add_labels.call_args_list]
        assert (42, ["hydraflow-review"]) in add_labels_calls

        # Verify HITL state was cleaned up
        assert state.get_hitl_origin(42) is None
        assert state.get_hitl_cause(42) is None

    @pytest.mark.asyncio
    async def test_failure_keeps_hitl_label(self, config: HydraFlowConfig) -> None:
        """On failure, the hydraflow-hitl label should be re-applied."""
        from models import HITLResult

        phase, state, fetcher, prs, wt, runner, _bus = _make_phase(config)
        issue = make_issue(42, title="Test HITL", body="Fix it")

        fetcher.fetch_issue_by_number = AsyncMock(return_value=issue)
        state.set_hitl_origin(42, "hydraflow-review")
        state.set_hitl_cause(42, "CI failed")

        runner.run = AsyncMock(
            return_value=HITLResult(
                issue_number=42, success=False, error="quality failed"
            )
        )

        semaphore = asyncio.Semaphore(1)
        await phase._process_one_hitl(42, "Fix the tests", semaphore)

        # Verify HITL label was re-applied
        add_labels_calls = [c.args for c in prs.add_labels.call_args_list]
        assert (42, [config.hitl_label[0]]) in add_labels_calls

        # Verify HITL state is preserved (not cleaned up)
        assert state.get_hitl_origin(42) == "hydraflow-review"
        assert state.get_hitl_cause(42) == "CI failed"

    @pytest.mark.asyncio
    async def test_success_posts_comment(self, config: HydraFlowConfig) -> None:
        from models import HITLResult

        phase, state, fetcher, prs, wt, runner, _bus = _make_phase(config)
        issue = make_issue(42)

        fetcher.fetch_issue_by_number = AsyncMock(return_value=issue)
        state.set_hitl_origin(42, "hydraflow-review")

        runner.run = AsyncMock(return_value=HITLResult(issue_number=42, success=True))

        semaphore = asyncio.Semaphore(1)
        await phase._process_one_hitl(42, "Fix it", semaphore)

        prs.post_comment.assert_called_once()
        comment = prs.post_comment.call_args.args[1]
        assert "HITL correction applied successfully" in comment

    @pytest.mark.asyncio
    async def test_failure_posts_comment(self, config: HydraFlowConfig) -> None:
        from models import HITLResult

        phase, state, fetcher, prs, wt, runner, _bus = _make_phase(config)
        issue = make_issue(42)

        fetcher.fetch_issue_by_number = AsyncMock(return_value=issue)
        state.set_hitl_origin(42, "hydraflow-review")

        runner.run = AsyncMock(
            return_value=HITLResult(
                issue_number=42, success=False, error="make quality failed"
            )
        )

        semaphore = asyncio.Semaphore(1)
        await phase._process_one_hitl(42, "Fix it", semaphore)

        prs.post_comment.assert_called_once()
        comment = prs.post_comment.call_args.args[1]
        assert "HITL correction failed" in comment
        assert "make quality failed" in comment

    @pytest.mark.asyncio
    async def test_skips_when_issue_not_found(self, config: HydraFlowConfig) -> None:
        phase, _state, fetcher, prs, _wt, _runner, _bus = _make_phase(config)
        fetcher.fetch_issue_by_number = AsyncMock(return_value=None)

        semaphore = asyncio.Semaphore(1)
        await phase._process_one_hitl(42, "Fix it", semaphore)

        # No label changes or comments when issue not found
        prs.post_comment.assert_not_called()

    @pytest.mark.asyncio
    async def test_publishes_resolved_event_on_success(
        self, config: HydraFlowConfig
    ) -> None:
        from models import HITLResult

        phase, state, fetcher, prs, wt, runner, bus = _make_phase(config)
        issue = make_issue(42)

        fetcher.fetch_issue_by_number = AsyncMock(return_value=issue)
        state.set_hitl_origin(42, "hydraflow-review")

        runner.run = AsyncMock(return_value=HITLResult(issue_number=42, success=True))

        semaphore = asyncio.Semaphore(1)
        await phase._process_one_hitl(42, "Fix it", semaphore)

        events = [
            e
            for e in bus.get_history()
            if e.type == EventType.HITL_UPDATE and e.data.get("action") == "resolved"
        ]
        assert len(events) == 1
        assert events[0].data["status"] == "resolved"

    @pytest.mark.asyncio
    async def test_publishes_failed_event_on_failure(
        self, config: HydraFlowConfig
    ) -> None:
        from models import HITLResult

        phase, state, fetcher, prs, wt, runner, bus = _make_phase(config)
        issue = make_issue(42)

        fetcher.fetch_issue_by_number = AsyncMock(return_value=issue)
        state.set_hitl_origin(42, "hydraflow-review")

        runner.run = AsyncMock(
            return_value=HITLResult(issue_number=42, success=False, error="fail")
        )

        semaphore = asyncio.Semaphore(1)
        await phase._process_one_hitl(42, "Fix it", semaphore)

        events = [
            e
            for e in bus.get_history()
            if e.type == EventType.HITL_UPDATE and e.data.get("action") == "failed"
        ]
        assert len(events) == 1
        assert events[0].data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_clears_active_issues(self, config: HydraFlowConfig) -> None:
        """Issue should be removed from active_hitl_issues after processing."""
        from models import HITLResult

        phase, _state, fetcher, prs, wt, runner, _bus = _make_phase(config)
        issue = make_issue(42)

        fetcher.fetch_issue_by_number = AsyncMock(return_value=issue)

        runner.run = AsyncMock(return_value=HITLResult(issue_number=42, success=True))

        semaphore = asyncio.Semaphore(1)
        await phase._process_one_hitl(42, "Fix it", semaphore)

        assert 42 not in phase.active_hitl_issues

    @pytest.mark.asyncio
    async def test_swaps_to_active_label(self, config: HydraFlowConfig) -> None:
        """Processing should swap to hitl-active label before running agent."""
        from models import HITLResult

        phase, state, fetcher, prs, wt, runner, _bus = _make_phase(config)
        issue = make_issue(42)

        fetcher.fetch_issue_by_number = AsyncMock(return_value=issue)
        state.set_hitl_origin(42, "hydraflow-review")

        runner.run = AsyncMock(return_value=HITLResult(issue_number=42, success=True))

        semaphore = asyncio.Semaphore(1)
        await phase._process_one_hitl(42, "Fix it", semaphore)

        # Check that hitl_active_label was added
        add_labels_calls = [c.args for c in prs.add_labels.call_args_list]
        assert (42, [config.hitl_active_label[0]]) in add_labels_calls

    @pytest.mark.asyncio
    async def test_success_destroys_worktree(self, config: HydraFlowConfig) -> None:
        """On success, the worktree should be destroyed."""
        from models import HITLResult

        phase, state, fetcher, prs, wt, runner, _bus = _make_phase(config)
        issue = make_issue(42)

        fetcher.fetch_issue_by_number = AsyncMock(return_value=issue)
        state.set_hitl_origin(42, "hydraflow-review")

        runner.run = AsyncMock(return_value=HITLResult(issue_number=42, success=True))

        semaphore = asyncio.Semaphore(1)
        await phase._process_one_hitl(42, "Fix it", semaphore)

        wt.destroy.assert_awaited_once_with(42)

    @pytest.mark.asyncio
    async def test_failure_does_not_destroy_worktree(
        self, config: HydraFlowConfig
    ) -> None:
        """On failure, the worktree should be kept for retry."""
        from models import HITLResult

        phase, state, fetcher, prs, wt, runner, _bus = _make_phase(config)
        issue = make_issue(42)

        fetcher.fetch_issue_by_number = AsyncMock(return_value=issue)
        state.set_hitl_origin(42, "hydraflow-review")

        runner.run = AsyncMock(
            return_value=HITLResult(issue_number=42, success=False, error="fail")
        )

        semaphore = asyncio.Semaphore(1)
        await phase._process_one_hitl(42, "Fix it", semaphore)

        wt.destroy.assert_not_awaited()


# ---------------------------------------------------------------------------
# HITL correction resets issue attempts
# ---------------------------------------------------------------------------


class TestHITLResetsAttempts:
    """Tests that HITL correction resets issue_attempts."""

    @pytest.mark.asyncio
    async def test_hitl_correction_resets_issue_attempts(
        self, config: HydraFlowConfig
    ) -> None:
        """On successful HITL correction, issue_attempts should be reset."""
        from models import HITLResult

        phase, state, fetcher, prs, wt, runner, _bus = _make_phase(config)

        # Set up state with attempts
        state.increment_issue_attempts(42)
        state.increment_issue_attempts(42)
        assert state.get_issue_attempts(42) == 2

        # Mock HITL runner to succeed
        runner.run = AsyncMock(return_value=HITLResult(issue_number=42, success=True))

        # Set HITL origin/cause
        state.set_hitl_origin(42, "hydraflow-ready")
        state.set_hitl_cause(42, "Cap exceeded")

        # Mock fetcher and PR manager
        fetcher.fetch_issue_by_number = AsyncMock(return_value=make_issue(42))

        # Create worktree directory
        wt_path = config.worktree_base / "issue-42"
        wt_path.mkdir(parents=True, exist_ok=True)
        wt.create = AsyncMock(return_value=wt_path)

        semaphore = asyncio.Semaphore(1)
        await phase._process_one_hitl(42, "Fix the tests", semaphore)

        # Issue attempts should be reset
        assert state.get_issue_attempts(42) == 0


# ---------------------------------------------------------------------------
# HITL improve→triage transition on correction success
# ---------------------------------------------------------------------------


class TestHITLImproveTransition:
    """Tests that improve-origin HITL corrections transition to triage."""

    @pytest.mark.asyncio
    async def test_success_improve_origin_transitions_to_triage(
        self, config: HydraFlowConfig
    ) -> None:
        """On success with improve origin, should remove improve and add find label."""
        from models import HITLResult

        phase, state, fetcher, prs, wt, runner, _bus = _make_phase(config)
        issue = make_issue(42, title="Improve: test", body="Details")

        fetcher.fetch_issue_by_number = AsyncMock(return_value=issue)
        state.set_hitl_origin(42, "hydraflow-improve")
        state.set_hitl_cause(42, "Memory suggestion")

        runner.run = AsyncMock(return_value=HITLResult(issue_number=42, success=True))

        semaphore = asyncio.Semaphore(1)
        await phase._process_one_hitl(42, "Improve the prompt", semaphore)

        # Verify improve label was removed
        remove_calls = [c.args for c in prs.remove_label.call_args_list]
        assert (42, "hydraflow-improve") in remove_calls

        # Verify find/triage label was added (not the improve label)
        add_calls = [c.args for c in prs.add_labels.call_args_list]
        assert (42, [config.find_label[0]]) in add_calls
        # Ensure hydraflow-improve was NOT restored as a label
        assert (42, ["hydraflow-improve"]) not in add_calls

        # Verify HITL state was cleaned up
        assert state.get_hitl_origin(42) is None
        assert state.get_hitl_cause(42) is None

    @pytest.mark.asyncio
    async def test_success_non_improve_origin_restores_label(
        self, config: HydraFlowConfig
    ) -> None:
        """Non-improve origins should still restore the original label."""
        from models import HITLResult

        phase, state, fetcher, prs, wt, runner, _bus = _make_phase(config)
        issue = make_issue(42, title="Test", body="Details")

        fetcher.fetch_issue_by_number = AsyncMock(return_value=issue)
        state.set_hitl_origin(42, "hydraflow-review")
        state.set_hitl_cause(42, "CI failed")

        runner.run = AsyncMock(return_value=HITLResult(issue_number=42, success=True))

        semaphore = asyncio.Semaphore(1)
        await phase._process_one_hitl(42, "Fix the tests", semaphore)

        # Verify review label was restored (existing behavior)
        add_calls = [c.args for c in prs.add_labels.call_args_list]
        assert (42, ["hydraflow-review"]) in add_calls

        # Verify find label was NOT added
        assert (42, [config.find_label[0]]) not in add_calls

    @pytest.mark.asyncio
    async def test_failure_improve_origin_preserves_state(
        self, config: HydraFlowConfig
    ) -> None:
        """On failure, improve origin state should be preserved for retry."""
        from models import HITLResult

        phase, state, fetcher, prs, wt, runner, _bus = _make_phase(config)
        issue = make_issue(42, title="Improve: test", body="Details")

        fetcher.fetch_issue_by_number = AsyncMock(return_value=issue)
        state.set_hitl_origin(42, "hydraflow-improve")
        state.set_hitl_cause(42, "Memory suggestion")

        runner.run = AsyncMock(
            return_value=HITLResult(
                issue_number=42, success=False, error="quality failed"
            )
        )

        semaphore = asyncio.Semaphore(1)
        await phase._process_one_hitl(42, "Improve the prompt", semaphore)

        # Verify HITL label was re-applied
        add_calls = [c.args for c in prs.add_labels.call_args_list]
        assert (42, [config.hitl_label[0]]) in add_calls

        # Verify improve origin state is preserved for retry
        assert state.get_hitl_origin(42) == "hydraflow-improve"
        assert state.get_hitl_cause(42) == "Memory suggestion"

    @pytest.mark.asyncio
    async def test_improve_success_comment_mentions_find_label(
        self, config: HydraFlowConfig
    ) -> None:
        """Success comment for improve origin should mention the find/triage stage."""
        from models import HITLResult

        phase, state, fetcher, prs, wt, runner, _bus = _make_phase(config)
        issue = make_issue(42, title="Improve: test", body="Details")

        fetcher.fetch_issue_by_number = AsyncMock(return_value=issue)
        state.set_hitl_origin(42, "hydraflow-improve")

        runner.run = AsyncMock(return_value=HITLResult(issue_number=42, success=True))

        semaphore = asyncio.Semaphore(1)
        await phase._process_one_hitl(42, "Improve it", semaphore)

        comment = prs.post_comment.call_args.args[1]
        assert config.find_label[0] in comment
