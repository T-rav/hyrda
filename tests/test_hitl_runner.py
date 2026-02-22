"""Tests for hitl_runner.py — HITLRunner class."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from events import EventBus, EventType
from hitl_runner import HITLRunner, _classify_cause
from tests.conftest import HITLResultFactory, IssueFactory

if TYPE_CHECKING:
    from config import HydraConfig


# ---------------------------------------------------------------------------
# Cause classification
# ---------------------------------------------------------------------------


class TestClassifyCause:
    """Tests for _classify_cause helper function."""

    def test_ci_failure_maps_to_ci(self) -> None:
        assert _classify_cause("CI failed after 2 fix attempt(s)") == "ci"

    def test_check_keyword_maps_to_ci(self) -> None:
        assert _classify_cause("Failed checks: lint, test") == "ci"

    def test_test_fail_keyword_maps_to_ci(self) -> None:
        assert _classify_cause("test fail in module") == "ci"

    def test_merge_conflict_maps_correctly(self) -> None:
        assert _classify_cause("Merge conflict with main branch") == "merge_conflict"

    def test_insufficient_detail_maps_to_needs_info(self) -> None:
        assert _classify_cause("Insufficient issue detail for triage") == "needs_info"

    def test_needs_more_info_maps_to_needs_info(self) -> None:
        assert _classify_cause("Needs more information") == "needs_info"

    def test_unknown_cause_maps_to_default(self) -> None:
        assert _classify_cause("Unknown escalation") == "default"

    def test_pr_merge_failed_maps_to_default(self) -> None:
        assert _classify_cause("PR merge failed on GitHub") == "default"

    def test_empty_cause_maps_to_default(self) -> None:
        assert _classify_cause("") == "default"


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    """Tests for HITLRunner._build_prompt."""

    def test_prompt_includes_issue_title(self, config: HydraConfig) -> None:
        runner = HITLRunner(config, EventBus())
        issue = IssueFactory.create(number=42, title="Fix the widget")
        prompt = runner._build_prompt(issue, "Try mocking the DB", "CI failed")
        assert "Fix the widget" in prompt

    def test_prompt_includes_correction_text(self, config: HydraConfig) -> None:
        runner = HITLRunner(config, EventBus())
        issue = IssueFactory.create(number=42)
        prompt = runner._build_prompt(issue, "Mock the database layer", "CI failed")
        assert "Mock the database layer" in prompt

    def test_prompt_includes_cause(self, config: HydraConfig) -> None:
        runner = HITLRunner(config, EventBus())
        issue = IssueFactory.create(number=42)
        prompt = runner._build_prompt(issue, "Fix it", "CI failed after 2 attempts")
        assert "CI failed after 2 attempts" in prompt

    def test_prompt_uses_ci_instructions_for_ci_cause(
        self, config: HydraConfig
    ) -> None:
        runner = HITLRunner(config, EventBus())
        issue = IssueFactory.create(number=42)
        prompt = runner._build_prompt(issue, "Fix", "CI failed after 2 fix attempt(s)")
        assert "make quality" in prompt
        assert "do NOT skip or disable tests" in prompt

    def test_prompt_uses_merge_instructions_for_conflict_cause(
        self, config: HydraConfig
    ) -> None:
        runner = HITLRunner(config, EventBus())
        issue = IssueFactory.create(number=42)
        prompt = runner._build_prompt(issue, "Fix", "Merge conflict with main branch")
        assert "git status" in prompt
        assert "conflict" in prompt.lower()

    def test_prompt_uses_needs_info_instructions(self, config: HydraConfig) -> None:
        runner = HITLRunner(config, EventBus())
        issue = IssueFactory.create(number=42)
        prompt = runner._build_prompt(
            issue, "Add logging", "Insufficient issue detail for triage"
        )
        assert "TDD" in prompt

    def test_prompt_includes_issue_number_in_commit_message(
        self, config: HydraConfig
    ) -> None:
        runner = HITLRunner(config, EventBus())
        issue = IssueFactory.create(number=99)
        prompt = runner._build_prompt(issue, "Fix it", "Unknown")
        assert "#99" in prompt

    def test_prompt_includes_no_push_rule(self, config: HydraConfig) -> None:
        runner = HITLRunner(config, EventBus())
        issue = IssueFactory.create(number=42)
        prompt = runner._build_prompt(issue, "Fix", "CI failed")
        assert "Do NOT push to remote" in prompt


# ---------------------------------------------------------------------------
# Command building
# ---------------------------------------------------------------------------


class TestBuildCommand:
    """Tests for HITLRunner._build_command."""

    def test_command_includes_claude(self, config: HydraConfig) -> None:
        runner = HITLRunner(config, EventBus())
        cmd = runner._build_command(Path("/tmp/wt"))
        assert cmd[0] == "claude"
        assert "-p" in cmd

    def test_command_includes_model(self, config: HydraConfig) -> None:
        runner = HITLRunner(config, EventBus())
        cmd = runner._build_command(Path("/tmp/wt"))
        assert "--model" in cmd
        idx = cmd.index("--model")
        assert cmd[idx + 1] == config.model

    def test_command_includes_budget_when_set(self, config: HydraConfig) -> None:
        runner = HITLRunner(config, EventBus())
        cmd = runner._build_command(Path("/tmp/wt"))
        assert "--max-budget-usd" in cmd

    def test_command_omits_budget_when_zero(self) -> None:
        from tests.helpers import ConfigFactory

        cfg = ConfigFactory.create(max_budget_usd=0)
        runner = HITLRunner(cfg, EventBus())
        cmd = runner._build_command(Path("/tmp/wt"))
        assert "--max-budget-usd" not in cmd


# ---------------------------------------------------------------------------
# Run — dry run mode
# ---------------------------------------------------------------------------


class TestRunDryMode:
    """Tests for HITLRunner.run in dry-run mode."""

    @pytest.mark.asyncio
    async def test_dry_run_returns_success(self, dry_config: HydraConfig) -> None:
        runner = HITLRunner(dry_config, EventBus())
        issue = IssueFactory.create(number=42)
        result = await runner.run(issue, "correction", "cause", Path("/tmp/wt"))
        assert result.success is True
        assert result.issue_number == 42

    @pytest.mark.asyncio
    async def test_dry_run_publishes_event(self, dry_config: HydraConfig) -> None:
        bus = EventBus()
        runner = HITLRunner(dry_config, bus)
        issue = IssueFactory.create(number=42)
        await runner.run(issue, "correction", "cause", Path("/tmp/wt"))

        events = [e for e in bus.get_history() if e.type == EventType.HITL_UPDATE]
        assert len(events) >= 1
        assert events[0].data["status"] == "running"


# ---------------------------------------------------------------------------
# Run — execution
# ---------------------------------------------------------------------------


class TestRunExecution:
    """Tests for HITLRunner.run with mocked execution."""

    @pytest.mark.asyncio
    async def test_run_success_returns_result(self, config: HydraConfig) -> None:
        bus = EventBus()
        runner = HITLRunner(config, bus)
        issue = IssueFactory.create(number=42)

        runner._execute = AsyncMock(return_value="transcript text")  # type: ignore[method-assign]
        runner._verify_quality = AsyncMock(return_value=(True, "OK"))  # type: ignore[method-assign]
        runner._save_transcript = lambda *a: None  # type: ignore[method-assign]

        result = await runner.run(issue, "fix the test", "CI failed", Path("/tmp/wt"))

        assert result.success is True
        assert result.issue_number == 42
        assert result.transcript == "transcript text"
        assert result.duration_seconds > 0

    @pytest.mark.asyncio
    async def test_run_failure_sets_error(self, config: HydraConfig) -> None:
        bus = EventBus()
        runner = HITLRunner(config, bus)
        issue = IssueFactory.create(number=42)

        runner._execute = AsyncMock(return_value="transcript text")  # type: ignore[method-assign]
        runner._verify_quality = AsyncMock(  # type: ignore[method-assign]
            return_value=(False, "`make quality` failed:\ntest_foo FAILED")
        )
        runner._save_transcript = lambda *a: None  # type: ignore[method-assign]

        result = await runner.run(issue, "fix the test", "CI failed", Path("/tmp/wt"))

        assert result.success is False
        assert result.error is not None
        assert "make quality" in result.error

    @pytest.mark.asyncio
    async def test_run_exception_sets_error(self, config: HydraConfig) -> None:
        bus = EventBus()
        runner = HITLRunner(config, bus)
        issue = IssueFactory.create(number=42)

        runner._execute = AsyncMock(side_effect=RuntimeError("boom"))  # type: ignore[method-assign]

        result = await runner.run(issue, "fix the test", "CI failed", Path("/tmp/wt"))

        assert result.success is False
        assert result.error == "boom"

    @pytest.mark.asyncio
    async def test_run_publishes_start_and_end_events(
        self, config: HydraConfig
    ) -> None:
        bus = EventBus()
        runner = HITLRunner(config, bus)
        issue = IssueFactory.create(number=42)

        runner._execute = AsyncMock(return_value="transcript")  # type: ignore[method-assign]
        runner._verify_quality = AsyncMock(return_value=(True, "OK"))  # type: ignore[method-assign]
        runner._save_transcript = lambda *a: None  # type: ignore[method-assign]

        await runner.run(issue, "fix it", "CI failed", Path("/tmp/wt"))

        hitl_events = [e for e in bus.get_history() if e.type == EventType.HITL_UPDATE]
        statuses = [e.data["status"] for e in hitl_events]
        assert "running" in statuses
        assert "done" in statuses

    @pytest.mark.asyncio
    async def test_run_failure_publishes_failed_status(
        self, config: HydraConfig
    ) -> None:
        bus = EventBus()
        runner = HITLRunner(config, bus)
        issue = IssueFactory.create(number=42)

        runner._execute = AsyncMock(return_value="transcript")  # type: ignore[method-assign]
        runner._verify_quality = AsyncMock(  # type: ignore[method-assign]
            return_value=(False, "quality failed")
        )
        runner._save_transcript = lambda *a: None  # type: ignore[method-assign]

        await runner.run(issue, "fix it", "CI failed", Path("/tmp/wt"))

        hitl_events = [e for e in bus.get_history() if e.type == EventType.HITL_UPDATE]
        statuses = [e.data["status"] for e in hitl_events]
        assert "failed" in statuses


# ---------------------------------------------------------------------------
# Transcript saving
# ---------------------------------------------------------------------------


class TestSaveTranscript:
    """Tests for HITLRunner._save_transcript."""

    def test_saves_transcript_to_disk(self, config: HydraConfig) -> None:
        config.repo_root.mkdir(parents=True, exist_ok=True)
        runner = HITLRunner(config, EventBus())
        runner._save_transcript(42, "test transcript content")

        path = config.repo_root / ".hydra" / "logs" / "hitl-issue-42.txt"
        assert path.exists()
        assert path.read_text() == "test transcript content"

    def test_save_transcript_handles_oserror(
        self, config: HydraConfig, caplog: pytest.LogCaptureFixture
    ) -> None:
        config.repo_root.mkdir(parents=True, exist_ok=True)
        runner = HITLRunner(config, EventBus())

        with patch.object(Path, "write_text", side_effect=OSError("disk full")):
            runner._save_transcript(42, "transcript")  # should not raise

        assert "Could not save transcript" in caplog.text


# ---------------------------------------------------------------------------
# Terminate
# ---------------------------------------------------------------------------


class TestTerminate:
    """Tests for HITLRunner.terminate."""

    def test_terminate_with_no_active_procs(self, config: HydraConfig) -> None:
        runner = HITLRunner(config, EventBus())
        runner.terminate()  # Should not raise

    def test_terminate_calls_terminate_processes(self, config: HydraConfig) -> None:
        runner = HITLRunner(config, EventBus())
        with patch("hitl_runner.terminate_processes") as mock_term:
            runner.terminate()
            mock_term.assert_called_once_with(runner._active_procs)


# ---------------------------------------------------------------------------
# HITLResult model
# ---------------------------------------------------------------------------


class TestHITLResult:
    """Tests for the HITLResult Pydantic model."""

    def test_defaults(self) -> None:
        result = HITLResultFactory.create(success=False)
        assert result.issue_number == 42
        assert result.success is False
        assert result.error is None
        assert result.transcript == ""
        assert result.duration_seconds == 0.0

    def test_success_result(self) -> None:
        result = HITLResultFactory.create(transcript="done")
        assert result.success is True
        assert result.transcript == "done"
