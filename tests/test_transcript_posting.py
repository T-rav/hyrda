"""Tests for posting agent transcripts as collapsible GitHub comments."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from events import EventBus
from models import PlanResult, ReviewResult, ReviewVerdict, WorkerResult
from pr_manager import PRManager
from tests.conftest import IssueFactory, PRInfoFactory
from tests.helpers import ConfigFactory

# --- helpers ---


def _make_manager(config, event_bus: EventBus | None = None) -> PRManager:
    return PRManager(config, event_bus or EventBus())


# ============================================================
# PRManager._format_transcript_comment tests
# ============================================================


class TestFormatTranscriptComment:
    """Unit tests for the static transcript formatting method."""

    def test_includes_details_summary_tags(self) -> None:
        body = PRManager._format_transcript_comment(
            "planner", "issue #42", 154.0, True, "some transcript"
        )
        assert "<details>" in body
        assert "</details>" in body
        assert "<summary>" in body
        assert "</summary>" in body

    def test_includes_role_and_identifier(self) -> None:
        body = PRManager._format_transcript_comment(
            "planner", "issue #42", 60.0, True, "transcript text"
        )
        assert "Planner Transcript" in body
        assert "issue #42" in body

    def test_includes_correct_emoji_planner(self) -> None:
        body = PRManager._format_transcript_comment(
            "planner", "issue #1", 0.0, True, "t"
        )
        assert "\U0001f50d" in body

    def test_includes_correct_emoji_implementer(self) -> None:
        body = PRManager._format_transcript_comment(
            "implementer", "issue #1", 0.0, True, "t"
        )
        assert "\U0001f528" in body

    def test_includes_correct_emoji_reviewer(self) -> None:
        body = PRManager._format_transcript_comment("reviewer", "PR #1", 0.0, True, "t")
        assert "\U0001f4cb" in body

    def test_includes_fallback_emoji_for_unknown_role(self) -> None:
        body = PRManager._format_transcript_comment(
            "unknown", "issue #1", 0.0, True, "t"
        )
        assert "\U0001f4dd" in body

    def test_includes_duration_minutes_and_seconds(self) -> None:
        body = PRManager._format_transcript_comment(
            "planner", "issue #42", 154.0, True, "text"
        )
        assert "2m 34s" in body

    def test_includes_duration_seconds_only(self) -> None:
        body = PRManager._format_transcript_comment(
            "planner", "issue #42", 45.0, True, "text"
        )
        assert "45s" in body

    def test_includes_success_indicator(self) -> None:
        body = PRManager._format_transcript_comment(
            "planner", "issue #42", 10.0, True, "text"
        )
        assert "\u2705" in body

    def test_includes_failure_indicator(self) -> None:
        body = PRManager._format_transcript_comment(
            "planner", "issue #42", 10.0, False, "text"
        )
        assert "\u274c" in body

    def test_wraps_in_pre_code_block(self) -> None:
        body = PRManager._format_transcript_comment(
            "planner", "issue #42", 10.0, True, "my transcript content"
        )
        assert "<pre><code>" in body
        assert "</code></pre>" in body
        assert "my transcript content" in body

    def test_escapes_html_closing_tags_in_transcript(self) -> None:
        transcript = "text </details> and </pre> and </code> end"
        body = PRManager._format_transcript_comment(
            "planner", "issue #42", 10.0, True, transcript
        )
        # The actual <details> wrapper should still be present
        assert body.count("</details>") == 1  # only the wrapper's closing tag
        assert "&lt;/details&gt;" in body
        assert "&lt;/pre&gt;" in body
        assert "&lt;/code&gt;" in body

    def test_truncates_very_large_transcript(self) -> None:
        huge = "x" * 100_000
        body = PRManager._format_transcript_comment(
            "planner", "issue #42", 10.0, True, huge
        )
        assert len(body) <= PRManager._GITHUB_COMMENT_LIMIT
        assert "truncated" in body

    def test_does_not_truncate_small_transcript(self) -> None:
        small = "small transcript"
        body = PRManager._format_transcript_comment(
            "planner", "issue #42", 10.0, True, small
        )
        assert "truncated" not in body
        assert "small transcript" in body


# ============================================================
# PRManager._format_duration tests
# ============================================================


class TestFormatDuration:
    def test_zero_seconds(self) -> None:
        assert PRManager._format_duration(0.0) == "0s"

    def test_seconds_only(self) -> None:
        assert PRManager._format_duration(45.0) == "45s"

    def test_minutes_and_seconds(self) -> None:
        assert PRManager._format_duration(154.0) == "2m 34s"

    def test_exact_minute(self) -> None:
        assert PRManager._format_duration(120.0) == "2m 0s"


# ============================================================
# PRManager.post_transcript_comment tests
# ============================================================


class TestPostTranscriptComment:
    @pytest.mark.asyncio
    async def test_delegates_to_post_comment(self, tmp_path: Path) -> None:
        cfg = ConfigFactory.create(repo_root=tmp_path, post_transcripts=True)
        mgr = _make_manager(cfg)
        mgr.post_comment = AsyncMock()

        await mgr.post_transcript_comment(
            42, "planner", "issue #42", 60.0, True, "transcript text"
        )

        mgr.post_comment.assert_awaited_once()
        body = mgr.post_comment.call_args[0][1]
        assert "<details>" in body
        assert "Planner Transcript" in body

    @pytest.mark.asyncio
    async def test_skipped_when_config_disabled(self, tmp_path: Path) -> None:
        cfg = ConfigFactory.create(repo_root=tmp_path, post_transcripts=False)
        mgr = _make_manager(cfg)
        mgr.post_comment = AsyncMock()

        await mgr.post_transcript_comment(
            42, "planner", "issue #42", 60.0, True, "transcript text"
        )

        mgr.post_comment.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skipped_when_empty_transcript(self, tmp_path: Path) -> None:
        cfg = ConfigFactory.create(repo_root=tmp_path, post_transcripts=True)
        mgr = _make_manager(cfg)
        mgr.post_comment = AsyncMock()

        await mgr.post_transcript_comment(42, "planner", "issue #42", 60.0, True, "")

        mgr.post_comment.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_does_not_crash_on_error(self, tmp_path: Path) -> None:
        cfg = ConfigFactory.create(repo_root=tmp_path, post_transcripts=True)
        mgr = _make_manager(cfg)
        mgr.post_comment = AsyncMock(side_effect=RuntimeError("boom"))

        # Should not raise
        await mgr.post_transcript_comment(
            42, "planner", "issue #42", 60.0, True, "transcript text"
        )


# ============================================================
# PRManager.post_pr_transcript_comment tests
# ============================================================


class TestPostPrTranscriptComment:
    @pytest.mark.asyncio
    async def test_delegates_to_post_pr_comment(self, tmp_path: Path) -> None:
        cfg = ConfigFactory.create(repo_root=tmp_path, post_transcripts=True)
        mgr = _make_manager(cfg)
        mgr.post_pr_comment = AsyncMock()

        await mgr.post_pr_transcript_comment(
            101, "reviewer", "PR #101", 120.0, True, "review transcript"
        )

        mgr.post_pr_comment.assert_awaited_once()
        body = mgr.post_pr_comment.call_args[0][1]
        assert "<details>" in body
        assert "Reviewer Transcript" in body

    @pytest.mark.asyncio
    async def test_skipped_when_config_disabled(self, tmp_path: Path) -> None:
        cfg = ConfigFactory.create(repo_root=tmp_path, post_transcripts=False)
        mgr = _make_manager(cfg)
        mgr.post_pr_comment = AsyncMock()

        await mgr.post_pr_transcript_comment(
            101, "reviewer", "PR #101", 120.0, True, "review transcript"
        )

        mgr.post_pr_comment.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skipped_when_empty_transcript(self, tmp_path: Path) -> None:
        cfg = ConfigFactory.create(repo_root=tmp_path, post_transcripts=True)
        mgr = _make_manager(cfg)
        mgr.post_pr_comment = AsyncMock()

        await mgr.post_pr_transcript_comment(
            101, "reviewer", "PR #101", 120.0, True, ""
        )

        mgr.post_pr_comment.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_does_not_crash_on_error(self, tmp_path: Path) -> None:
        cfg = ConfigFactory.create(repo_root=tmp_path, post_transcripts=True)
        mgr = _make_manager(cfg)
        mgr.post_pr_comment = AsyncMock(side_effect=RuntimeError("boom"))

        # Should not raise
        await mgr.post_pr_transcript_comment(
            101, "reviewer", "PR #101", 120.0, True, "review transcript"
        )


# ============================================================
# Plan phase transcript posting tests
# ============================================================


class TestPlanPhaseTranscriptPosting:
    @pytest.mark.asyncio
    async def test_posts_transcript_on_success(self, tmp_path: Path) -> None:
        from orchestrator import HydraOrchestrator

        cfg = ConfigFactory.create(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
            post_transcripts=True,
        )
        orch = HydraOrchestrator(cfg)

        issue = IssueFactory.create(number=42)

        plan_result = PlanResult(
            issue_number=42,
            success=True,
            plan="## Plan\n\n1. Do the thing",
            summary="Plan summary",
            transcript="planner transcript content",
            duration_seconds=90.0,
        )

        orch._planners = AsyncMock()
        orch._planners.plan = AsyncMock(return_value=plan_result)

        orch._prs = AsyncMock()
        orch._prs.post_comment = AsyncMock()
        orch._prs.post_transcript_comment = AsyncMock()
        orch._prs.remove_label = AsyncMock()
        orch._prs.add_labels = AsyncMock()
        orch._prs.create_issue = AsyncMock(return_value=0)

        orch._fetcher = AsyncMock()
        orch._fetcher.fetch_plan_issues = AsyncMock(return_value=[issue])

        results = await orch._plan_issues()

        orch._prs.post_transcript_comment.assert_awaited_once_with(
            42,
            role="planner",
            identifier="issue #42",
            duration_seconds=90.0,
            success=True,
            transcript="planner transcript content",
        )
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_posts_transcript_on_failure(self, tmp_path: Path) -> None:
        from orchestrator import HydraOrchestrator

        cfg = ConfigFactory.create(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
            post_transcripts=True,
        )
        orch = HydraOrchestrator(cfg)

        issue = IssueFactory.create(number=7)

        plan_result = PlanResult(
            issue_number=7,
            success=False,
            transcript="failed planner transcript",
            duration_seconds=30.0,
        )

        orch._planners = AsyncMock()
        orch._planners.plan = AsyncMock(return_value=plan_result)

        orch._prs = AsyncMock()
        orch._prs.post_comment = AsyncMock()
        orch._prs.post_transcript_comment = AsyncMock()
        orch._prs.remove_label = AsyncMock()
        orch._prs.add_labels = AsyncMock()

        orch._fetcher = AsyncMock()
        orch._fetcher.fetch_plan_issues = AsyncMock(return_value=[issue])

        results = await orch._plan_issues()

        orch._prs.post_transcript_comment.assert_awaited_once_with(
            7,
            role="planner",
            identifier="issue #7",
            duration_seconds=30.0,
            success=False,
            transcript="failed planner transcript",
        )
        assert len(results) == 1


# ============================================================
# Implement phase transcript posting tests
# ============================================================


class TestImplementPhaseTranscriptPosting:
    @pytest.mark.asyncio
    async def test_posts_transcript_after_agent_run(self, tmp_path: Path) -> None:
        from implement_phase import ImplementPhase

        cfg = ConfigFactory.create(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
            post_transcripts=True,
        )
        stop = asyncio.Event()
        active: set[int] = set()

        wt_path = tmp_path / "wt" / "issue-42"
        wt_path.mkdir(parents=True)

        agent_result = WorkerResult(
            issue_number=42,
            branch="agent/issue-42",
            success=True,
            transcript="implementation transcript",
            duration_seconds=200.0,
            worktree_path=str(wt_path),
            commits=3,
        )

        mock_agents = AsyncMock()
        mock_agents.run = AsyncMock(return_value=agent_result)

        mock_prs = AsyncMock()
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.post_comment = AsyncMock()
        mock_prs.post_transcript_comment = AsyncMock()
        mock_prs.create_pr = AsyncMock(
            return_value=PRInfoFactory.create(number=101, issue_number=42)
        )
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        mock_prs.add_pr_labels = AsyncMock()

        mock_state = AsyncMock()
        mock_state.mark_issue = AsyncMock()
        mock_state.set_branch = AsyncMock()
        mock_state.set_worktree = AsyncMock()

        mock_worktrees = AsyncMock()
        mock_worktrees.create = AsyncMock(return_value=wt_path)

        mock_fetcher = AsyncMock()
        issue = IssueFactory.create(number=42)
        mock_fetcher.fetch_ready_issues = AsyncMock(return_value=[issue])

        phase = ImplementPhase(
            cfg,
            mock_state,
            mock_worktrees,
            mock_agents,
            mock_prs,
            mock_fetcher,
            stop,
            active,
        )

        results, issues = await phase.run_batch()

        mock_prs.post_transcript_comment.assert_awaited_once_with(
            42,
            role="implementer",
            identifier="issue #42",
            duration_seconds=200.0,
            success=True,
            transcript="implementation transcript",
        )
        assert len(results) == 1


# ============================================================
# Review phase transcript posting tests
# ============================================================


class TestReviewPhaseTranscriptPosting:
    @pytest.mark.asyncio
    async def test_posts_transcript_after_review(self, tmp_path: Path) -> None:
        from review_phase import ReviewPhase

        cfg = ConfigFactory.create(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
            post_transcripts=True,
        )
        stop = asyncio.Event()
        active: set[int] = set()

        wt_path = tmp_path / "wt" / "issue-42"
        wt_path.mkdir(parents=True)

        review_result = ReviewResult(
            pr_number=101,
            issue_number=42,
            verdict=ReviewVerdict.APPROVE,
            summary="LGTM",
            transcript="reviewer transcript text",
            duration_seconds=150.0,
        )

        mock_reviewers = AsyncMock()
        mock_reviewers.review = AsyncMock(return_value=review_result)

        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value="diff text")
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.post_pr_comment = AsyncMock()
        mock_prs.post_pr_transcript_comment = AsyncMock()
        mock_prs.submit_review = AsyncMock(return_value=True)
        mock_prs.merge_pr = AsyncMock(return_value=True)
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        mock_prs.add_pr_labels = AsyncMock()
        mock_prs.remove_pr_label = AsyncMock()

        mock_state = AsyncMock()
        mock_state.mark_pr = AsyncMock()
        mock_state.mark_issue = AsyncMock()
        mock_state.remove_worktree = AsyncMock()
        mock_state.record_pr_merged = AsyncMock()
        mock_state.record_issue_completed = AsyncMock()

        mock_worktrees = AsyncMock()
        mock_worktrees.destroy = AsyncMock()
        mock_worktrees.merge_main = AsyncMock(return_value=True)

        bus = EventBus()
        issue = IssueFactory.create(number=42)
        pr = PRInfoFactory.create(number=101, issue_number=42)

        phase = ReviewPhase(
            cfg,
            mock_state,
            mock_worktrees,
            mock_reviewers,
            mock_prs,
            stop,
            active,
            event_bus=bus,
        )

        results = await phase.review_prs([pr], [issue])

        mock_prs.post_pr_transcript_comment.assert_awaited_once_with(
            101,
            role="reviewer",
            identifier="PR #101",
            duration_seconds=150.0,
            success=True,
            transcript="reviewer transcript text",
        )
        assert len(results) == 1


# ============================================================
# Config tests
# ============================================================


class TestPostTranscriptsConfig:
    def test_default_true(self, tmp_path: Path) -> None:
        cfg = ConfigFactory.create(repo_root=tmp_path)
        assert cfg.post_transcripts is True

    def test_explicit_false(self, tmp_path: Path) -> None:
        cfg = ConfigFactory.create(repo_root=tmp_path, post_transcripts=False)
        assert cfg.post_transcripts is False

    def test_env_override_false(self, tmp_path: Path) -> None:
        with patch.dict(os.environ, {"HYDRA_POST_TRANSCRIPTS": "false"}):
            cfg = ConfigFactory.create(repo_root=tmp_path)
        assert cfg.post_transcripts is False

    def test_env_override_zero(self, tmp_path: Path) -> None:
        with patch.dict(os.environ, {"HYDRA_POST_TRANSCRIPTS": "0"}):
            cfg = ConfigFactory.create(repo_root=tmp_path)
        assert cfg.post_transcripts is False

    def test_env_override_true_keeps_default(self, tmp_path: Path) -> None:
        with patch.dict(os.environ, {"HYDRA_POST_TRANSCRIPTS": "true"}):
            cfg = ConfigFactory.create(repo_root=tmp_path)
        assert cfg.post_transcripts is True
