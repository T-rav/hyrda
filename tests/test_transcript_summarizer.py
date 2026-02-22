"""Tests for the transcript summarization system."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from events import EventType
from tests.helpers import ConfigFactory
from transcript_summarizer import (
    TranscriptSummarizer,
    _truncate_transcript,
    build_transcript_summary_body,
)

# --- build_transcript_summary_body tests ---


class TestBuildTranscriptSummaryBody:
    """Tests for formatting the GitHub issue body."""

    def test_includes_all_metadata(self) -> None:
        body = build_transcript_summary_body(
            issue_number=42,
            phase="implement",
            summary_content="### Key Decisions\n- Used factory pattern",
            issue_title="Add logging feature",
            duration_seconds=120.5,
        )
        assert "## Transcript Summary" in body
        assert "#42 — Add logging feature" in body
        assert "**Phase:** implement" in body
        assert "**Duration:** 120s" in body
        assert "### Key Decisions" in body
        assert "Used factory pattern" in body

    def test_footer_present(self) -> None:
        body = build_transcript_summary_body(
            issue_number=7,
            phase="review",
            summary_content="Some summary",
        )
        assert "Auto-generated from transcript of issue #7 (review phase)" in body

    def test_no_title(self) -> None:
        body = build_transcript_summary_body(
            issue_number=99,
            phase="plan",
            summary_content="Summary",
        )
        assert "**Issue:** #99" in body
        assert "—" not in body.split("\n")[2]

    def test_no_duration(self) -> None:
        body = build_transcript_summary_body(
            issue_number=1,
            phase="hitl",
            summary_content="Summary",
            duration_seconds=0.0,
        )
        assert "Duration" not in body


# --- _truncate_transcript tests ---


class TestTruncateTranscript:
    """Tests for transcript truncation logic."""

    def test_under_limit_unchanged(self) -> None:
        text = "Short transcript"
        result = _truncate_transcript(text, max_chars=1000)
        assert result == text

    def test_over_limit_truncated_from_beginning(self) -> None:
        text = "A" * 100 + "B" * 100
        result = _truncate_transcript(text, max_chars=150)
        # End should be preserved (the Bs)
        assert result.endswith("B" * 100)
        assert "truncated" in result
        assert len(result) <= 150

    def test_empty_transcript(self) -> None:
        result = _truncate_transcript("", max_chars=100)
        assert result == ""

    def test_exactly_at_limit(self) -> None:
        text = "x" * 100
        result = _truncate_transcript(text, max_chars=100)
        assert result == text


# --- TranscriptSummarizer tests ---


class TestTranscriptSummarizer:
    """Tests for the main TranscriptSummarizer class."""

    @pytest.mark.asyncio
    async def test_summarize_publishes_issue(self, tmp_path: Path) -> None:
        """Happy path: model returns summary, issue is created."""
        config = ConfigFactory.create(repo_root=tmp_path)
        prs = MagicMock()
        prs.create_issue = AsyncMock(return_value=999)
        bus = MagicMock()
        bus.publish = AsyncMock()
        state = MagicMock()

        summarizer = TranscriptSummarizer(config, prs, bus, state)

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(
            return_value=(b"### Key Decisions\n- Used factory pattern\n", b"")
        )

        import asyncio as _asyncio

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                _asyncio,
                "create_subprocess_exec",
                AsyncMock(return_value=mock_proc),
            )
            result = await summarizer.summarize_and_publish(
                transcript="x" * 1000,
                issue_number=42,
                phase="implement",
                issue_title="Add feature",
                duration_seconds=60.0,
            )

        assert result == 999
        prs.create_issue.assert_called_once()
        call_args = prs.create_issue.call_args
        assert call_args[0][0] == "[Transcript Summary] Issue #42 — implement phase"
        assert "hydra-improve" in call_args[0][2]
        assert "hydra-hitl" in call_args[0][2]
        assert "Key Decisions" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_summarize_sets_hitl_origin_and_cause(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(repo_root=tmp_path)
        prs = MagicMock()
        prs.create_issue = AsyncMock(return_value=123)
        bus = MagicMock()
        bus.publish = AsyncMock()
        state = MagicMock()

        summarizer = TranscriptSummarizer(config, prs, bus, state)

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"Summary content", b""))

        import asyncio as _asyncio

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                _asyncio,
                "create_subprocess_exec",
                AsyncMock(return_value=mock_proc),
            )
            await summarizer.summarize_and_publish(
                transcript="x" * 1000, issue_number=42, phase="implement"
            )

        state.set_hitl_origin.assert_called_once_with(123, "hydra-improve")
        state.set_hitl_cause.assert_called_once_with(123, "Transcript summary")

    @pytest.mark.asyncio
    async def test_summarize_emits_event(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(repo_root=tmp_path)
        prs = MagicMock()
        prs.create_issue = AsyncMock(return_value=999)
        bus = MagicMock()
        bus.publish = AsyncMock()
        state = MagicMock()

        summarizer = TranscriptSummarizer(config, prs, bus, state)

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"Summary", b""))

        import asyncio as _asyncio

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                _asyncio,
                "create_subprocess_exec",
                AsyncMock(return_value=mock_proc),
            )
            await summarizer.summarize_and_publish(
                transcript="x" * 1000, issue_number=42, phase="review"
            )

        bus.publish.assert_called_once()
        event = bus.publish.call_args[0][0]
        assert event.type == EventType.TRANSCRIPT_SUMMARY
        assert event.data["source_issue"] == 42
        assert event.data["phase"] == "review"
        assert event.data["summary_issue"] == 999

    @pytest.mark.asyncio
    async def test_summarize_skips_when_disabled(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(
            repo_root=tmp_path, transcript_summarization_enabled=False
        )
        prs = MagicMock()
        prs.create_issue = AsyncMock()
        bus = MagicMock()
        state = MagicMock()

        summarizer = TranscriptSummarizer(config, prs, bus, state)
        result = await summarizer.summarize_and_publish(
            transcript="x" * 1000, issue_number=42, phase="implement"
        )

        assert result is None
        prs.create_issue.assert_not_called()

    @pytest.mark.asyncio
    async def test_summarize_skips_empty_transcript(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(repo_root=tmp_path)
        prs = MagicMock()
        prs.create_issue = AsyncMock()
        bus = MagicMock()
        state = MagicMock()

        summarizer = TranscriptSummarizer(config, prs, bus, state)

        for empty in ("", "   ", "\n\n"):
            result = await summarizer.summarize_and_publish(
                transcript=empty, issue_number=42, phase="implement"
            )
            assert result is None

        prs.create_issue.assert_not_called()

    @pytest.mark.asyncio
    async def test_summarize_skips_short_transcript(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(repo_root=tmp_path)
        prs = MagicMock()
        prs.create_issue = AsyncMock()
        bus = MagicMock()
        state = MagicMock()

        summarizer = TranscriptSummarizer(config, prs, bus, state)
        result = await summarizer.summarize_and_publish(
            transcript="x" * 499, issue_number=42, phase="implement"
        )

        assert result is None
        prs.create_issue.assert_not_called()

    @pytest.mark.asyncio
    async def test_summarize_truncates_long_transcript(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(
            repo_root=tmp_path, max_transcript_summary_chars=10_000
        )
        prs = MagicMock()
        prs.create_issue = AsyncMock(return_value=1)
        bus = MagicMock()
        bus.publish = AsyncMock()
        state = MagicMock()

        summarizer = TranscriptSummarizer(config, prs, bus, state)

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"Summary", b""))

        import asyncio as _asyncio

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                _asyncio,
                "create_subprocess_exec",
                AsyncMock(return_value=mock_proc),
            )
            await summarizer.summarize_and_publish(
                transcript="x" * 50_000, issue_number=42, phase="implement"
            )

        # Verify the stdin passed to the model was truncated
        call_args = mock_proc.communicate.call_args
        stdin_data = (
            call_args[1]["input"]
            if "input" in call_args[1]
            else call_args[0][0]
            if call_args[0]
            else None
        )
        assert stdin_data is not None
        # The prompt includes the transcript, check it's capped
        assert len(stdin_data) < 50_000

    @pytest.mark.asyncio
    async def test_summarize_handles_model_failure(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(repo_root=tmp_path)
        prs = MagicMock()
        prs.create_issue = AsyncMock()
        bus = MagicMock()
        state = MagicMock()

        summarizer = TranscriptSummarizer(config, prs, bus, state)

        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"error"))

        import asyncio as _asyncio

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                _asyncio,
                "create_subprocess_exec",
                AsyncMock(return_value=mock_proc),
            )
            result = await summarizer.summarize_and_publish(
                transcript="x" * 1000, issue_number=42, phase="implement"
            )

        assert result is None
        prs.create_issue.assert_not_called()

    @pytest.mark.asyncio
    async def test_summarize_handles_timeout(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(repo_root=tmp_path)
        prs = MagicMock()
        prs.create_issue = AsyncMock()
        bus = MagicMock()
        state = MagicMock()

        summarizer = TranscriptSummarizer(config, prs, bus, state)

        mock_proc = AsyncMock()

        async def _raise_timeout(*a, **kw):  # noqa: ANN002, ANN003
            raise TimeoutError

        mock_proc.communicate = _raise_timeout

        import asyncio as _asyncio

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                _asyncio,
                "create_subprocess_exec",
                AsyncMock(return_value=mock_proc),
            )
            result = await summarizer.summarize_and_publish(
                transcript="x" * 1000, issue_number=42, phase="implement"
            )

        assert result is None
        prs.create_issue.assert_not_called()

    @pytest.mark.asyncio
    async def test_summarize_handles_subprocess_error(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(repo_root=tmp_path)
        prs = MagicMock()
        prs.create_issue = AsyncMock()
        bus = MagicMock()
        state = MagicMock()

        summarizer = TranscriptSummarizer(config, prs, bus, state)

        import asyncio as _asyncio

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                _asyncio,
                "create_subprocess_exec",
                AsyncMock(side_effect=FileNotFoundError("claude not found")),
            )
            result = await summarizer.summarize_and_publish(
                transcript="x" * 1000, issue_number=42, phase="implement"
            )

        assert result is None
        prs.create_issue.assert_not_called()

    @pytest.mark.asyncio
    async def test_summarize_dry_run(self, tmp_path: Path) -> None:
        """In dry-run, create_issue returns 0 — summarizer handles gracefully."""
        config = ConfigFactory.create(repo_root=tmp_path, dry_run=True)
        prs = MagicMock()
        prs.create_issue = AsyncMock(return_value=0)
        bus = MagicMock()
        bus.publish = AsyncMock()
        state = MagicMock()

        summarizer = TranscriptSummarizer(config, prs, bus, state)

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"Summary", b""))

        import asyncio as _asyncio

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                _asyncio,
                "create_subprocess_exec",
                AsyncMock(return_value=mock_proc),
            )
            result = await summarizer.summarize_and_publish(
                transcript="x" * 1000, issue_number=42, phase="implement"
            )

        # create_issue is still called (it handles dry-run internally)
        prs.create_issue.assert_called_once()
        # But result is None because create_issue returned 0
        assert result is None

    @pytest.mark.asyncio
    async def test_labels_match_memory_suggestion_pattern(self, tmp_path: Path) -> None:
        """Labels should be improve_label + hitl_label, same as memory suggestions."""
        config = ConfigFactory.create(
            repo_root=tmp_path,
            improve_label=["custom-improve"],
            hitl_label=["custom-hitl"],
        )
        prs = MagicMock()
        prs.create_issue = AsyncMock(return_value=1)
        bus = MagicMock()
        bus.publish = AsyncMock()
        state = MagicMock()

        summarizer = TranscriptSummarizer(config, prs, bus, state)

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"Summary", b""))

        import asyncio as _asyncio

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                _asyncio,
                "create_subprocess_exec",
                AsyncMock(return_value=mock_proc),
            )
            await summarizer.summarize_and_publish(
                transcript="x" * 1000, issue_number=42, phase="implement"
            )

        call_args = prs.create_issue.call_args
        labels = call_args[0][2]
        assert labels == ["custom-improve", "custom-hitl"]

    @pytest.mark.asyncio
    async def test_summarize_empty_model_output(self, tmp_path: Path) -> None:
        """If the model returns empty output, no issue should be created."""
        config = ConfigFactory.create(repo_root=tmp_path)
        prs = MagicMock()
        prs.create_issue = AsyncMock()
        bus = MagicMock()
        state = MagicMock()

        summarizer = TranscriptSummarizer(config, prs, bus, state)

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        import asyncio as _asyncio

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                _asyncio,
                "create_subprocess_exec",
                AsyncMock(return_value=mock_proc),
            )
            result = await summarizer.summarize_and_publish(
                transcript="x" * 1000, issue_number=42, phase="implement"
            )

        assert result is None
        prs.create_issue.assert_not_called()
