"""Tests for dx/hydra/reviewer.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import AsyncMock, patch

import pytest

from events import EventType
from models import ReviewVerdict
from reviewer import ReviewRunner

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_runner(config, event_bus):
    return ReviewRunner(config=config, event_bus=event_bus)


def _make_subprocess_mock(returncode: int = 0, stdout: str = "", stderr: str = ""):
    """Build a mock for asyncio.create_subprocess_exec."""
    mock_proc = AsyncMock()
    mock_proc.returncode = returncode
    mock_proc.communicate = AsyncMock(return_value=(stdout.encode(), stderr.encode()))
    mock_proc.wait = AsyncMock(return_value=returncode)
    return AsyncMock(return_value=mock_proc)


# ---------------------------------------------------------------------------
# _build_command
# ---------------------------------------------------------------------------


def test_build_command_uses_review_model_and_budget(config, tmp_path):
    runner = _make_runner(config, None)
    cmd = runner._build_command(tmp_path)

    assert "claude" in cmd
    assert "-p" in cmd
    assert "--model" in cmd
    model_idx = cmd.index("--model")
    assert cmd[model_idx + 1] == config.review_model

    assert "--max-budget-usd" in cmd
    budget_idx = cmd.index("--max-budget-usd")
    assert cmd[budget_idx + 1] == str(config.review_budget_usd)


def test_build_command_does_not_include_cwd(config, tmp_path):
    runner = _make_runner(config, None)
    cmd = runner._build_command(tmp_path)

    assert "--cwd" not in cmd


def test_build_command_includes_output_format(config, tmp_path):
    runner = _make_runner(config, None)
    cmd = runner._build_command(tmp_path)

    assert "--output-format" in cmd
    fmt_idx = cmd.index("--output-format")
    assert cmd[fmt_idx + 1] == "text"


# ---------------------------------------------------------------------------
# _build_review_prompt
# ---------------------------------------------------------------------------


def test_build_review_prompt_includes_pr_number(config, event_bus, pr_info, issue):
    runner = _make_runner(config, event_bus)
    prompt = runner._build_review_prompt(pr_info, issue, "some diff")

    assert f"#{pr_info.number}" in prompt


def test_build_review_prompt_includes_issue_context(config, event_bus, pr_info, issue):
    runner = _make_runner(config, event_bus)
    prompt = runner._build_review_prompt(pr_info, issue, "some diff")

    assert issue.title in prompt
    assert issue.body in prompt
    assert f"#{issue.number}" in prompt


def test_build_review_prompt_includes_diff(config, event_bus, pr_info, issue):
    runner = _make_runner(config, event_bus)
    diff = "diff --git a/foo.py b/foo.py\n+added line"
    prompt = runner._build_review_prompt(pr_info, issue, diff)

    assert diff in prompt


def test_build_review_prompt_includes_review_instructions(
    config, event_bus, pr_info, issue
):
    runner = _make_runner(config, event_bus)
    prompt = runner._build_review_prompt(pr_info, issue, "diff")

    assert "VERDICT" in prompt
    assert "SUMMARY" in prompt
    assert "APPROVE" in prompt
    assert "REQUEST_CHANGES" in prompt


# ---------------------------------------------------------------------------
# _parse_verdict
# ---------------------------------------------------------------------------


def test_parse_verdict_approve(config, event_bus):
    runner = _make_runner(config, event_bus)
    transcript = "All looks good.\nVERDICT: APPROVE\nSUMMARY: looks good"
    verdict = runner._parse_verdict(transcript)
    assert verdict == ReviewVerdict.APPROVE


def test_parse_verdict_request_changes(config, event_bus):
    runner = _make_runner(config, event_bus)
    transcript = "Issues found.\nVERDICT: REQUEST_CHANGES\nSUMMARY: needs work"
    verdict = runner._parse_verdict(transcript)
    assert verdict == ReviewVerdict.REQUEST_CHANGES


def test_parse_verdict_comment(config, event_bus):
    runner = _make_runner(config, event_bus)
    transcript = "Minor notes.\nVERDICT: COMMENT\nSUMMARY: minor issues"
    verdict = runner._parse_verdict(transcript)
    assert verdict == ReviewVerdict.COMMENT


def test_parse_verdict_no_verdict_defaults_to_comment(config, event_bus):
    runner = _make_runner(config, event_bus)
    transcript = "This is a review without any verdict line at all."
    verdict = runner._parse_verdict(transcript)
    assert verdict == ReviewVerdict.COMMENT


def test_parse_verdict_case_insensitive(config, event_bus):
    runner = _make_runner(config, event_bus)

    transcript_lower = "verdict: approve\nsummary: lgtm"
    assert runner._parse_verdict(transcript_lower) == ReviewVerdict.APPROVE

    transcript_mixed = "Verdict: Request_Changes\nSummary: needs fixes"
    assert runner._parse_verdict(transcript_mixed) == ReviewVerdict.REQUEST_CHANGES

    transcript_upper = "VERDICT: COMMENT\nSUMMARY: minor"
    assert runner._parse_verdict(transcript_upper) == ReviewVerdict.COMMENT


# ---------------------------------------------------------------------------
# _extract_summary
# ---------------------------------------------------------------------------


def test_extract_summary_with_summary_line(config, event_bus):
    runner = _make_runner(config, event_bus)
    transcript = "Review done.\nVERDICT: APPROVE\nSUMMARY: looks good to me"
    summary = runner._extract_summary(transcript)
    assert summary == "looks good to me"


def test_extract_summary_case_insensitive(config, event_bus):
    runner = _make_runner(config, event_bus)
    transcript = "summary: everything checks out"
    summary = runner._extract_summary(transcript)
    assert summary == "everything checks out"


def test_extract_summary_strips_whitespace(config, event_bus):
    runner = _make_runner(config, event_bus)
    transcript = "SUMMARY:   extra spaces around this   "
    summary = runner._extract_summary(transcript)
    assert summary == "extra spaces around this"


def test_extract_summary_fallback_to_last_line(config, event_bus):
    runner = _make_runner(config, event_bus)
    transcript = "First line.\nSecond line.\nThis is the last line"
    summary = runner._extract_summary(transcript)
    assert summary == "This is the last line"


def test_extract_summary_fallback_ignores_empty_lines(config, event_bus):
    runner = _make_runner(config, event_bus)
    transcript = "First line.\nSecond line.\n\n   \n"
    summary = runner._extract_summary(transcript)
    assert summary == "Second line."


# ---------------------------------------------------------------------------
# review - success path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_success_path(config, event_bus, pr_info, issue, tmp_path):
    runner = _make_runner(config, event_bus)
    transcript = (
        "All checks pass.\nVERDICT: APPROVE\nSUMMARY: Implementation looks good"
    )

    mock_execute = AsyncMock(return_value=transcript)
    mock_has_commits = AsyncMock(return_value=False)

    with (
        patch.object(runner, "_execute", mock_execute),
        patch.object(runner, "_has_new_commits", mock_has_commits),
        patch.object(runner, "_save_transcript"),
    ):
        result = await runner.review(pr_info, issue, tmp_path, "some diff", worker_id=0)

    assert result.pr_number == pr_info.number
    assert result.issue_number == issue.number
    assert result.verdict == ReviewVerdict.APPROVE
    assert result.summary == "Implementation looks good"
    assert result.transcript == transcript
    assert result.fixes_made is False


@pytest.mark.asyncio
async def test_review_success_path_with_fixes(
    config, event_bus, pr_info, issue, tmp_path
):
    runner = _make_runner(config, event_bus)
    transcript = (
        "Found issues, fixed them.\nVERDICT: APPROVE\nSUMMARY: Fixed and approved"
    )

    mock_execute = AsyncMock(return_value=transcript)
    mock_has_commits = AsyncMock(return_value=True)

    with (
        patch.object(runner, "_execute", mock_execute),
        patch.object(runner, "_has_new_commits", mock_has_commits),
        patch.object(runner, "_save_transcript"),
    ):
        result = await runner.review(pr_info, issue, tmp_path, "some diff")

    assert result.fixes_made is True
    assert result.verdict == ReviewVerdict.APPROVE


# ---------------------------------------------------------------------------
# review - failure path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_failure_path_on_exception(
    config, event_bus, pr_info, issue, tmp_path
):
    runner = _make_runner(config, event_bus)

    mock_execute = AsyncMock(side_effect=RuntimeError("subprocess crashed"))

    with patch.object(runner, "_execute", mock_execute):
        result = await runner.review(pr_info, issue, tmp_path, "some diff")

    assert result.verdict == ReviewVerdict.COMMENT
    assert "Review failed" in result.summary
    assert "subprocess crashed" in result.summary


# ---------------------------------------------------------------------------
# review - dry_run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_dry_run_returns_auto_approved(
    dry_config, event_bus, pr_info, issue, tmp_path
):
    runner = _make_runner(dry_config, event_bus)
    mock_create = _make_subprocess_mock(returncode=0, stdout="")

    with patch("asyncio.create_subprocess_exec", mock_create):
        result = await runner.review(pr_info, issue, tmp_path, "some diff")

    mock_create.assert_not_called()
    assert result.verdict == ReviewVerdict.APPROVE
    assert result.summary == "Dry-run: auto-approved"
    assert result.pr_number == pr_info.number


# ---------------------------------------------------------------------------
# _save_transcript
# ---------------------------------------------------------------------------


def test_save_transcript_writes_to_correct_path(config, event_bus, tmp_path):
    # Point repo_root to tmp_path so we can check the file
    from config import HydraConfig

    cfg = HydraConfig(
        label=config.label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
        review_model=config.review_model,
        review_budget_usd=config.review_budget_usd,
    )
    runner = ReviewRunner(config=cfg, event_bus=event_bus)
    transcript = "This is the review transcript."

    runner._save_transcript(42, transcript)

    expected_path = tmp_path / ".hydra-logs" / "review-pr-42.txt"
    assert expected_path.exists()
    assert expected_path.read_text() == transcript


def test_save_transcript_creates_log_directory(config, event_bus, tmp_path):
    from config import HydraConfig

    cfg = HydraConfig(
        label=config.label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
        review_model=config.review_model,
        review_budget_usd=config.review_budget_usd,
    )
    runner = ReviewRunner(config=cfg, event_bus=event_bus)
    log_dir = tmp_path / ".hydra-logs"
    assert not log_dir.exists()

    runner._save_transcript(7, "transcript content")

    assert log_dir.exists()
    assert log_dir.is_dir()


# ---------------------------------------------------------------------------
# REVIEW_UPDATE events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_publishes_review_update_events(
    config, event_bus, pr_info, issue, tmp_path
):
    runner = _make_runner(config, event_bus)
    transcript = "All good.\nVERDICT: APPROVE\nSUMMARY: Looks great"

    with (
        patch.object(runner, "_execute", AsyncMock(return_value=transcript)),
        patch.object(runner, "_has_new_commits", AsyncMock(return_value=False)),
        patch.object(runner, "_save_transcript"),
    ):
        await runner.review(pr_info, issue, tmp_path, "diff", worker_id=2)

    events = event_bus.get_history()
    review_events = [e for e in events if e.type == EventType.REVIEW_UPDATE]

    # Should have at least two: one for "reviewing" and one for "done"
    assert len(review_events) >= 2

    statuses = [e.data["status"] for e in review_events]
    assert "reviewing" in statuses
    assert "done" in statuses


@pytest.mark.asyncio
async def test_review_start_event_includes_worker_id(
    config, event_bus, pr_info, issue, tmp_path
):
    runner = _make_runner(config, event_bus)
    transcript = "VERDICT: APPROVE\nSUMMARY: ok"

    with (
        patch.object(runner, "_execute", AsyncMock(return_value=transcript)),
        patch.object(runner, "_has_new_commits", AsyncMock(return_value=False)),
        patch.object(runner, "_save_transcript"),
    ):
        await runner.review(pr_info, issue, tmp_path, "diff", worker_id=3)

    events = event_bus.get_history()
    reviewing_event = next(
        e
        for e in events
        if e.type == EventType.REVIEW_UPDATE and e.data.get("status") == "reviewing"
    )
    assert reviewing_event.data["worker"] == 3
    assert reviewing_event.data["pr"] == pr_info.number
    assert reviewing_event.data["issue"] == issue.number


@pytest.mark.asyncio
async def test_review_done_event_includes_verdict_and_duration(
    config, event_bus, pr_info, issue, tmp_path
):
    runner = _make_runner(config, event_bus)
    transcript = "VERDICT: REQUEST_CHANGES\nSUMMARY: needs work"

    with (
        patch.object(runner, "_execute", AsyncMock(return_value=transcript)),
        patch.object(runner, "_has_new_commits", AsyncMock(return_value=False)),
        patch.object(runner, "_save_transcript"),
    ):
        await runner.review(pr_info, issue, tmp_path, "diff")

    events = event_bus.get_history()
    done_event = next(
        e
        for e in events
        if e.type == EventType.REVIEW_UPDATE and e.data.get("status") == "done"
    )
    assert done_event.data["verdict"] == ReviewVerdict.REQUEST_CHANGES.value
    assert "duration" in done_event.data


@pytest.mark.asyncio
async def test_review_dry_run_still_publishes_review_update_event(
    dry_config, event_bus, pr_info, issue, tmp_path
):
    runner = _make_runner(dry_config, event_bus)

    await runner.review(pr_info, issue, tmp_path, "diff")

    events = event_bus.get_history()
    review_events = [e for e in events if e.type == EventType.REVIEW_UPDATE]
    # The "reviewing" event is published before the dry-run check
    assert any(e.data.get("status") == "reviewing" for e in review_events)


# ---------------------------------------------------------------------------
# _has_new_commits
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_has_new_commits_returns_true_when_staged(config, event_bus, tmp_path):
    runner = _make_runner(config, event_bus)
    # returncode != 0 means there are staged changes
    mock_create = _make_subprocess_mock(returncode=1)

    with patch("asyncio.create_subprocess_exec", mock_create):
        result = await runner._has_new_commits(tmp_path)

    assert result is True


@pytest.mark.asyncio
async def test_has_new_commits_returns_false_when_clean(config, event_bus, tmp_path):
    runner = _make_runner(config, event_bus)
    # returncode 0 means no staged changes
    mock_create = _make_subprocess_mock(returncode=0)

    with patch("asyncio.create_subprocess_exec", mock_create):
        result = await runner._has_new_commits(tmp_path)

    assert result is False


@pytest.mark.asyncio
async def test_has_new_commits_returns_false_on_file_not_found(
    config, event_bus, tmp_path
):
    runner = _make_runner(config, event_bus)
    mock_create = AsyncMock(side_effect=FileNotFoundError("git not found"))

    with patch("asyncio.create_subprocess_exec", mock_create):
        result = await runner._has_new_commits(tmp_path)

    assert result is False


# ---------------------------------------------------------------------------
# _execute
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_returns_transcript(config, event_bus, pr_info, tmp_path):
    runner = _make_runner(config, event_bus)
    expected_output = "VERDICT: APPROVE\nSUMMARY: looks good"
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(expected_output.encode(), b""))
    mock_create = AsyncMock(return_value=mock_proc)

    with patch("asyncio.create_subprocess_exec", mock_create):
        transcript = await runner._execute(
            ["claude", "-p"],
            "review prompt",
            tmp_path,
            pr_info.number,
        )

    assert transcript == expected_output


@pytest.mark.asyncio
async def test_execute_publishes_transcript_line_events(
    config, event_bus, pr_info, tmp_path
):
    runner = _make_runner(config, event_bus)
    output = "Line one\nLine two\nLine three"
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(output.encode(), b""))
    mock_create = AsyncMock(return_value=mock_proc)

    with patch("asyncio.create_subprocess_exec", mock_create):
        await runner._execute(
            ["claude", "-p"],
            "prompt",
            tmp_path,
            pr_info.number,
        )

    events = event_bus.get_history()
    transcript_events = [e for e in events if e.type == EventType.TRANSCRIPT_LINE]
    assert len(transcript_events) == 3
    lines = [e.data["line"] for e in transcript_events]
    assert "Line one" in lines
    assert "Line two" in lines
    assert "Line three" in lines
    # All events should carry the correct pr number and source
    for ev in transcript_events:
        assert ev.data["pr"] == pr_info.number
        assert ev.data["source"] == "reviewer"
