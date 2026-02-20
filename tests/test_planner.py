"""Tests for dx/hydra/planner.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from events import EventType
from models import PlannerStatus
from planner import PlannerRunner
from tests.helpers import ConfigFactory, make_streaming_proc

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_runner(config, event_bus):
    return PlannerRunner(config=config, event_bus=event_bus)


# ---------------------------------------------------------------------------
# _build_command
# ---------------------------------------------------------------------------


def test_build_command_uses_planner_model_and_budget(config):
    runner = _make_runner(config, None)
    cmd = runner._build_command()

    assert "claude" in cmd
    assert "-p" in cmd
    assert "--model" in cmd
    model_idx = cmd.index("--model")
    assert cmd[model_idx + 1] == config.planner_model

    assert "--max-budget-usd" in cmd
    budget_idx = cmd.index("--max-budget-usd")
    assert cmd[budget_idx + 1] == str(config.planner_budget_usd)


def test_build_command_omits_budget_when_zero(tmp_path):
    from tests.conftest import ConfigFactory

    cfg = ConfigFactory.create(
        planner_budget_usd=0,
        repo_root=tmp_path / "repo",
        worktree_base=tmp_path / "wt",
        state_file=tmp_path / "s.json",
    )
    runner = _make_runner(cfg, None)
    cmd = runner._build_command()
    assert "--max-budget-usd" not in cmd


def test_build_command_includes_output_format(config):
    runner = _make_runner(config, None)
    cmd = runner._build_command()

    assert "--output-format" in cmd
    fmt_idx = cmd.index("--output-format")
    assert cmd[fmt_idx + 1] == "stream-json"


def test_build_command_includes_verbose(config):
    runner = _make_runner(config, None)
    cmd = runner._build_command()

    assert "--verbose" in cmd


def test_build_command_disallows_write_tools(config):
    runner = _make_runner(config, None)
    cmd = runner._build_command()

    assert "--disallowedTools" in cmd
    idx = cmd.index("--disallowedTools")
    blocked = cmd[idx + 1]
    assert "Write" in blocked
    assert "Edit" in blocked
    assert "NotebookEdit" in blocked


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------


def test_build_prompt_includes_issue_number(config, event_bus, issue):
    runner = _make_runner(config, event_bus)
    prompt = runner._build_prompt(issue)

    assert f"#{issue.number}" in prompt


def test_build_prompt_includes_issue_context(config, event_bus, issue):
    runner = _make_runner(config, event_bus)
    prompt = runner._build_prompt(issue)

    assert issue.title in prompt
    assert issue.body in prompt


def test_build_prompt_includes_read_only_instructions(config, event_bus, issue):
    runner = _make_runner(config, event_bus)
    prompt = runner._build_prompt(issue)

    assert "READ-ONLY" in prompt
    assert "Do NOT create, modify, or delete any files" in prompt


def test_build_prompt_includes_plan_markers(config, event_bus, issue):
    runner = _make_runner(config, event_bus)
    prompt = runner._build_prompt(issue)

    assert "PLAN_START" in prompt
    assert "PLAN_END" in prompt
    assert "SUMMARY:" in prompt


def test_build_prompt_includes_comments_when_present(config, event_bus):
    from models import GitHubIssue

    issue = GitHubIssue(
        number=42,
        title="Fix the frobnicator",
        body="It is broken.",
        comments=["First comment", "Second comment"],
    )
    runner = _make_runner(config, event_bus)
    prompt = runner._build_prompt(issue)

    assert "First comment" in prompt
    assert "Second comment" in prompt
    assert "Discussion" in prompt


def test_build_prompt_omits_comments_section_when_empty(config, event_bus, issue):
    runner = _make_runner(config, event_bus)
    prompt = runner._build_prompt(issue)

    assert "Discussion" not in prompt


def test_build_prompt_truncates_long_body(config, event_bus):
    from models import GitHubIssue

    issue = GitHubIssue(
        number=1, title="Big issue", body="X" * 20_000, labels=[], comments=[], url=""
    )
    runner = _make_runner(config, event_bus)
    prompt = runner._build_prompt(issue)

    assert "…(truncated)" in prompt
    assert len(prompt) < 10_000  # well under original 20k body


def test_build_prompt_truncates_long_comments(config, event_bus):
    from models import GitHubIssue

    issue = GitHubIssue(
        number=1,
        title="Big comments",
        body="Normal body with enough content",
        labels=[],
        comments=["C" * 5000, "Short"],
        url="",
    )
    runner = _make_runner(config, event_bus)
    prompt = runner._build_prompt(issue)

    # First comment should be truncated, second should be intact
    assert "…" in prompt
    assert "Short" in prompt


def test_build_prompt_truncates_long_lines(config, event_bus):
    """Lines exceeding _MAX_LINE_CHARS are hard-truncated to prevent
    Claude CLI text-splitter failures."""
    from models import GitHubIssue

    long_line = "A" * 2000
    body = f"Short line\n{long_line}\nAnother short line"
    issue = GitHubIssue(
        number=1, title="Long lines", body=body, labels=[], comments=[], url=""
    )
    runner = _make_runner(config, event_bus)
    prompt = runner._build_prompt(issue)

    # No line in the prompt should exceed _MAX_LINE_CHARS + ellipsis
    for line in prompt.splitlines():
        assert len(line) <= runner._MAX_LINE_CHARS + 10  # small margin for marker text


def test_truncate_text_respects_line_boundaries():
    """_truncate_text cuts at line boundaries, not mid-line."""
    text = "line1\nline2\nline3\nline4\nline5"
    result = PlannerRunner._truncate_text(text, char_limit=18, line_limit=500)
    # Should include line1 (5) + \n + line2 (5) + \n + line3 (5) = 17 chars
    assert "line1" in result
    assert "line2" in result
    assert "line3" in result
    assert "line4" not in result or "…(truncated)" in result


def test_truncate_text_no_truncation_when_under_limit():
    """_truncate_text returns text unchanged when under limits."""
    text = "short text"
    result = PlannerRunner._truncate_text(text, char_limit=500, line_limit=500)
    assert result == text
    assert "…(truncated)" not in result


# ---------------------------------------------------------------------------
# _extract_plan
# ---------------------------------------------------------------------------


def test_extract_plan_with_markers(config, event_bus):
    runner = _make_runner(config, event_bus)
    transcript = "Some preamble\nPLAN_START\nStep 1: Do this\nStep 2: Do that\nPLAN_END\nSome epilogue"
    plan = runner._extract_plan(transcript)

    assert plan == "Step 1: Do this\nStep 2: Do that"


def test_extract_plan_without_markers_returns_empty(config, event_bus):
    runner = _make_runner(config, event_bus)
    transcript = "Here is the full plan without markers.\nLine 2."
    plan = runner._extract_plan(transcript)

    assert plan == ""


def test_extract_plan_budget_exceeded_returns_empty(config, event_bus):
    """Budget-exceeded error output must not be treated as a plan."""
    runner = _make_runner(config, event_bus)
    transcript = "Error: Exceeded USD budget (3)"
    plan = runner._extract_plan(transcript)

    assert plan == ""


def test_extract_plan_multiline(config, event_bus):
    runner = _make_runner(config, event_bus)
    transcript = (
        "Analysis:\nPLAN_START\n"
        "## Files to modify\n\n"
        "- models.py: Add new class\n"
        "- tests/test_models.py: Add tests\n\n"
        "## Steps\n\n"
        "1. Create the model\n"
        "2. Write tests\n"
        "PLAN_END\n"
        "SUMMARY: Add new model"
    )
    plan = runner._extract_plan(transcript)

    assert "## Files to modify" in plan
    assert "## Steps" in plan
    assert "SUMMARY" not in plan


def test_extract_plan_empty_transcript(config, event_bus):
    runner = _make_runner(config, event_bus)
    plan = runner._extract_plan("")

    assert plan == ""


# ---------------------------------------------------------------------------
# _extract_summary
# ---------------------------------------------------------------------------


def test_extract_summary_with_summary_line(config, event_bus):
    runner = _make_runner(config, event_bus)
    transcript = "Plan done.\nPLAN_END\nSUMMARY: implement the widget feature"
    summary = runner._extract_summary(transcript)

    assert summary == "implement the widget feature"


def test_extract_summary_case_insensitive(config, event_bus):
    runner = _make_runner(config, event_bus)
    transcript = "summary: all changes identified"
    summary = runner._extract_summary(transcript)

    assert summary == "all changes identified"


def test_extract_summary_fallback_to_last_line(config, event_bus):
    runner = _make_runner(config, event_bus)
    transcript = "First line.\nSecond line.\nThis is the last line"
    summary = runner._extract_summary(transcript)

    assert summary == "This is the last line"


def test_extract_summary_empty_transcript(config, event_bus):
    runner = _make_runner(config, event_bus)
    summary = runner._extract_summary("")

    assert summary == "No summary provided"


# ---------------------------------------------------------------------------
# _significant_words
# ---------------------------------------------------------------------------


def test_significant_words_extracts_long_words(config, event_bus):
    runner = _make_runner(config, event_bus)
    words = runner._significant_words("Fix the broken authentication handler")
    assert "broken" in words
    assert "authentication" in words
    assert "handler" in words
    # "the" is too short (< 4 chars)
    assert "the" not in words
    # "Fix" is too short
    assert "fix" not in words


def test_significant_words_filters_stop_words(config, event_bus):
    runner = _make_runner(config, event_bus)
    words = runner._significant_words("This should have been done with more care")
    # All are stop words or short
    assert "this" not in words
    assert "should" not in words
    assert "have" not in words
    assert "been" not in words
    assert "with" not in words
    assert "more" not in words
    assert "care" in words
    assert "done" in words


def test_significant_words_empty_string(config, event_bus):
    runner = _make_runner(config, event_bus)
    words = runner._significant_words("")
    assert words == set()


# ---------------------------------------------------------------------------
# _validate_plan
# ---------------------------------------------------------------------------


def test_validate_plan_returns_true_when_overlap(config, event_bus):
    from models import GitHubIssue

    runner = _make_runner(config, event_bus)
    issue = GitHubIssue(number=1, title="Fix authentication handler")
    plan = "Step 1: Modify the authentication module"
    assert runner._validate_plan(issue, plan) is True


def test_validate_plan_returns_false_when_no_overlap(config, event_bus):
    from models import GitHubIssue

    runner = _make_runner(config, event_bus)
    issue = GitHubIssue(number=1, title="Fix authentication handler")
    plan = "Step 1: Modify the database schema for migrations"
    assert runner._validate_plan(issue, plan) is False


def test_validate_plan_returns_true_when_title_has_no_significant_words(
    config, event_bus
):
    """If the title is all short/stop words, validation passes vacuously."""
    from models import GitHubIssue

    runner = _make_runner(config, event_bus)
    issue = GitHubIssue(number=1, title="Fix it")
    plan = "Step 1: Do the thing"
    assert runner._validate_plan(issue, plan) is True


def test_validate_plan_logs_warning_on_mismatch(config, event_bus):
    from unittest.mock import patch as mock_patch

    from models import GitHubIssue

    runner = _make_runner(config, event_bus)
    issue = GitHubIssue(number=1, title="Fix authentication handler")
    plan = "Step 1: Modify the database schema"

    with mock_patch("planner.logger") as mock_logger:
        runner._validate_plan(issue, plan)

    mock_logger.warning.assert_called_once()


# ---------------------------------------------------------------------------
# _extract_new_issues
# ---------------------------------------------------------------------------


def test_extract_new_issues_with_markers(config, event_bus):
    runner = _make_runner(config, event_bus)
    transcript = (
        "PLAN_START\nStep 1\nPLAN_END\n"
        "NEW_ISSUES_START\n"
        "- title: Fix the widget\n"
        "  body: The widget is broken\n"
        "  labels: bug, high-priority\n"
        "- title: Refactor auth module\n"
        "  body: Needs cleanup\n"
        "  labels: tech-debt\n"
        "NEW_ISSUES_END\n"
        "SUMMARY: done"
    )
    issues = runner._extract_new_issues(transcript)
    assert len(issues) == 2
    assert issues[0].title == "Fix the widget"
    assert issues[0].body == "The widget is broken"
    assert "bug" in issues[0].labels
    assert "high-priority" in issues[0].labels
    assert issues[1].title == "Refactor auth module"
    assert "tech-debt" in issues[1].labels


def test_extract_new_issues_without_markers(config, event_bus):
    runner = _make_runner(config, event_bus)
    transcript = "PLAN_START\nStep 1\nPLAN_END\nSUMMARY: done"
    issues = runner._extract_new_issues(transcript)
    assert issues == []


def test_extract_new_issues_single_issue(config, event_bus):
    runner = _make_runner(config, event_bus)
    transcript = (
        "NEW_ISSUES_START\n"
        "- title: Add logging\n"
        "  body: We need more logging\n"
        "  labels: enhancement\n"
        "NEW_ISSUES_END"
    )
    issues = runner._extract_new_issues(transcript)
    assert len(issues) == 1
    assert issues[0].title == "Add logging"


def test_extract_new_issues_multiline_body(config, event_bus):
    """Multi-line body continuation lines are concatenated."""
    runner = _make_runner(config, event_bus)
    transcript = (
        "NEW_ISSUES_START\n"
        "- title: Fix the widget\n"
        "  body: The widget is broken in production. Users are seeing\n"
        "    errors when they click the submit button because the form\n"
        "    validation skips required fields.\n"
        "  labels: bug\n"
        "NEW_ISSUES_END"
    )
    issues = runner._extract_new_issues(transcript)
    assert len(issues) == 1
    assert issues[0].title == "Fix the widget"
    assert "widget is broken" in issues[0].body
    assert "form" in issues[0].body
    assert "validation" in issues[0].body
    assert len(issues[0].body) > 50


# ---------------------------------------------------------------------------
# plan - success path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plan_success_path(config, event_bus, issue, tmp_path):
    runner = _make_runner(config, event_bus)
    transcript = (
        "Analysis complete.\n"
        "PLAN_START\n"
        "Step 1: Modify models.py\n"
        "Step 2: Write tests\n"
        "PLAN_END\n"
        "SUMMARY: Two-step implementation plan"
    )

    mock_execute = AsyncMock(return_value=transcript)

    with (
        patch.object(runner, "_execute", mock_execute),
        patch.object(runner, "_save_transcript"),
    ):
        result = await runner.plan(issue, worker_id=0)

    assert result.issue_number == issue.number
    assert result.success is True
    assert result.plan == "Step 1: Modify models.py\nStep 2: Write tests"
    assert result.summary == "Two-step implementation plan"
    assert result.transcript == transcript


# ---------------------------------------------------------------------------
# plan - failure path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plan_failure_on_exception(config, event_bus, issue, tmp_path):
    runner = _make_runner(config, event_bus)

    mock_execute = AsyncMock(side_effect=RuntimeError("subprocess crashed"))

    with patch.object(runner, "_execute", mock_execute):
        result = await runner.plan(issue, worker_id=0)

    assert result.success is False
    assert result.error == "subprocess crashed"


# ---------------------------------------------------------------------------
# plan - dry_run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plan_dry_run(dry_config, event_bus, issue, tmp_path):
    runner = _make_runner(dry_config, event_bus)
    mock_create = make_streaming_proc(returncode=0, stdout="")

    with patch("asyncio.create_subprocess_exec", mock_create):
        result = await runner.plan(issue, worker_id=0)

    mock_create.assert_not_called()
    assert result.success is True
    assert result.summary == "Dry-run: plan skipped"


# ---------------------------------------------------------------------------
# _save_transcript
# ---------------------------------------------------------------------------


def test_save_transcript_writes_to_correct_path(event_bus, tmp_path):
    cfg = ConfigFactory.create(repo_root=tmp_path)
    runner = PlannerRunner(config=cfg, event_bus=event_bus)
    transcript = "This is the planning transcript."

    runner._save_transcript(42, transcript)

    expected_path = tmp_path / ".hydra" / "logs" / "plan-issue-42.txt"
    assert expected_path.exists()
    assert expected_path.read_text() == transcript


def test_save_transcript_creates_log_directory(event_bus, tmp_path):
    cfg = ConfigFactory.create(repo_root=tmp_path)
    runner = PlannerRunner(config=cfg, event_bus=event_bus)
    log_dir = tmp_path / ".hydra" / "logs"
    assert not log_dir.exists()

    runner._save_transcript(7, "transcript content")

    assert log_dir.exists()
    assert log_dir.is_dir()


# ---------------------------------------------------------------------------
# _save_plan
# ---------------------------------------------------------------------------


def test_save_plan_writes_to_correct_path(event_bus, tmp_path):
    cfg = ConfigFactory.create(repo_root=tmp_path)
    runner = PlannerRunner(config=cfg, event_bus=event_bus)

    runner._save_plan(42, "Step 1: Do X\nStep 2: Do Y", "Two-step plan")

    expected_path = tmp_path / ".hydra" / "plans" / "issue-42.md"
    assert expected_path.exists()
    content = expected_path.read_text()
    assert "Step 1: Do X" in content
    assert "Two-step plan" in content


def test_save_plan_creates_plans_directory(event_bus, tmp_path):
    cfg = ConfigFactory.create(repo_root=tmp_path)
    runner = PlannerRunner(config=cfg, event_bus=event_bus)
    plan_dir = tmp_path / ".hydra" / "plans"
    assert not plan_dir.exists()

    runner._save_plan(7, "Some plan", "Summary")

    assert plan_dir.exists()
    assert plan_dir.is_dir()


# ---------------------------------------------------------------------------
# PLANNER_UPDATE events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_planner_events_include_planner_role(config, event_bus, issue, tmp_path):
    """PLANNER_UPDATE events should carry role='planner'."""
    runner = _make_runner(config, event_bus)
    transcript = "PLAN_START\nStep 1\nPLAN_END\nSUMMARY: done"

    with (
        patch.object(runner, "_execute", AsyncMock(return_value=transcript)),
        patch.object(runner, "_save_transcript"),
    ):
        await runner.plan(issue, worker_id=1)

    events = event_bus.get_history()
    planner_events = [e for e in events if e.type == EventType.PLANNER_UPDATE]
    assert len(planner_events) >= 2
    for event in planner_events:
        assert event.data.get("role") == "planner"


@pytest.mark.asyncio
async def test_plan_emits_planning_and_done_events(config, event_bus, issue, tmp_path):
    """Status should go through planning → done on success."""
    runner = _make_runner(config, event_bus)
    transcript = "PLAN_START\nStep 1\nPLAN_END\nSUMMARY: done"

    with (
        patch.object(runner, "_execute", AsyncMock(return_value=transcript)),
        patch.object(runner, "_save_transcript"),
    ):
        await runner.plan(issue, worker_id=0)

    events = event_bus.get_history()
    planner_events = [e for e in events if e.type == EventType.PLANNER_UPDATE]

    statuses = [e.data["status"] for e in planner_events]
    assert PlannerStatus.PLANNING.value in statuses
    assert PlannerStatus.DONE.value in statuses


@pytest.mark.asyncio
async def test_plan_emits_planning_and_failed_events_on_error(
    config, event_bus, issue, tmp_path
):
    """Status should go through planning → failed on exception."""
    runner = _make_runner(config, event_bus)

    with patch.object(runner, "_execute", AsyncMock(side_effect=RuntimeError("boom"))):
        await runner.plan(issue, worker_id=0)

    events = event_bus.get_history()
    planner_events = [e for e in events if e.type == EventType.PLANNER_UPDATE]

    statuses = [e.data["status"] for e in planner_events]
    assert PlannerStatus.PLANNING.value in statuses
    assert PlannerStatus.FAILED.value in statuses


# ---------------------------------------------------------------------------
# terminate
# ---------------------------------------------------------------------------


def test_terminate_kills_active_processes(config, event_bus):
    runner = _make_runner(config, event_bus)
    mock_proc = MagicMock()
    mock_proc.pid = 12345
    runner._active_procs.add(mock_proc)

    with patch("runner_utils.os.killpg") as mock_killpg:
        runner.terminate()

    mock_killpg.assert_called_once()


def test_terminate_handles_process_lookup_error(config, event_bus):
    runner = _make_runner(config, event_bus)
    mock_proc = MagicMock()
    mock_proc.pid = 12345
    runner._active_procs.add(mock_proc)

    with patch("runner_utils.os.killpg", side_effect=ProcessLookupError):
        runner.terminate()  # Should not raise


def test_terminate_with_no_active_processes(config, event_bus):
    runner = _make_runner(config, event_bus)
    runner.terminate()  # Should not raise


# ---------------------------------------------------------------------------
# _execute - transcript lines
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_publishes_transcript_lines(config, event_bus, issue, tmp_path):
    runner = _make_runner(config, event_bus)
    output = "Line one\nLine two\nLine three"
    mock_create = make_streaming_proc(returncode=0, stdout=output)

    with patch("asyncio.create_subprocess_exec", mock_create):
        transcript = await runner._execute(
            ["claude", "-p"],
            "prompt",
            tmp_path,
            issue.number,
        )

    assert transcript == output

    events = event_bus.get_history()
    transcript_events = [e for e in events if e.type == EventType.TRANSCRIPT_LINE]
    assert len(transcript_events) == 3
    for ev in transcript_events:
        assert ev.data["source"] == "planner"
        assert ev.data["issue"] == issue.number


@pytest.mark.asyncio
async def test_execute_uses_large_stream_limit(config, event_bus, issue, tmp_path):
    """_execute should set limit=1MB to handle large stream-json lines."""
    runner = _make_runner(config, event_bus)
    mock_create = make_streaming_proc(returncode=0, stdout="ok")

    with patch("asyncio.create_subprocess_exec", mock_create) as mock_exec:
        await runner._execute(["claude", "-p"], "prompt", tmp_path, issue.number)

    kwargs = mock_exec.call_args[1]
    assert kwargs["limit"] == 1024 * 1024
