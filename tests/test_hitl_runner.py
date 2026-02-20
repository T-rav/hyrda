"""Tests for hitl_runner.py — HITLRunner class."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from events import EventBus, EventType
from hitl_runner import HITLRunner
from models import GitHubIssue, HITLStatus
from tests.helpers import ConfigFactory, make_streaming_proc

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_runner(config=None, event_bus=None):
    config = config or ConfigFactory.create()
    event_bus = event_bus or EventBus()
    return HITLRunner(config=config, event_bus=event_bus)


def _make_issue(number: int = 42) -> GitHubIssue:
    return GitHubIssue(
        number=number,
        title="Fix the bug",
        body="Details about the bug.",
        labels=["hydra-hitl"],
        comments=[],
        url=f"https://github.com/test-org/test-repo/issues/{number}",
    )


# ---------------------------------------------------------------------------
# _build_command
# ---------------------------------------------------------------------------


class TestBuildCommand:
    def test_includes_claude_and_model(self, config):
        runner = _make_runner(config)
        cmd = runner._build_command()
        assert "claude" in cmd
        assert "-p" in cmd
        assert "--model" in cmd
        model_idx = cmd.index("--model")
        assert cmd[model_idx + 1] == config.model

    def test_includes_budget_when_set(self, config):
        runner = _make_runner(config)
        cmd = runner._build_command()
        assert "--max-budget-usd" in cmd

    def test_omits_budget_when_zero(self, tmp_path):
        cfg = ConfigFactory.create(
            max_budget_usd=0,
            repo_root=tmp_path / "repo",
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        runner = _make_runner(cfg)
        cmd = runner._build_command()
        assert "--max-budget-usd" not in cmd

    def test_includes_stream_json_output_format(self, config):
        runner = _make_runner(config)
        cmd = runner._build_command()
        assert "--output-format" in cmd
        fmt_idx = cmd.index("--output-format")
        assert cmd[fmt_idx + 1] == "stream-json"


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    def test_includes_issue_context(self, config):
        runner = _make_runner(config)
        issue = _make_issue()
        prompt = runner._build_prompt(issue, "Fix the auth flow")
        assert "Fix the bug" in prompt
        assert "#42" in prompt
        assert "Details about the bug" in prompt

    def test_includes_correction_text(self, config):
        runner = _make_runner(config)
        issue = _make_issue()
        correction = "Please update the validation logic"
        prompt = runner._build_prompt(issue, correction)
        assert "Please update the validation logic" in prompt
        assert "Human Correction" in prompt


# ---------------------------------------------------------------------------
# correct() — dry run
# ---------------------------------------------------------------------------


class TestCorrectDryRun:
    @pytest.mark.asyncio
    async def test_dry_run_returns_success(self, tmp_path):
        cfg = ConfigFactory.create(
            dry_run=True,
            repo_root=tmp_path / "repo",
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        bus = EventBus()
        runner = HITLRunner(cfg, bus)
        issue = _make_issue()

        result = await runner.correct(issue, "Fix it", tmp_path, worker_id=0)

        assert result.success is True
        assert result.issue_number == 42
        assert result.duration_seconds >= 0

    @pytest.mark.asyncio
    async def test_dry_run_publishes_status_events(self, tmp_path):
        cfg = ConfigFactory.create(
            dry_run=True,
            repo_root=tmp_path / "repo",
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        bus = EventBus()
        runner = HITLRunner(cfg, bus)
        issue = _make_issue()

        await runner.correct(issue, "Fix it", tmp_path)

        history = bus.get_history()
        hitl_events = [e for e in history if e.type == EventType.HITL_UPDATE]
        assert len(hitl_events) == 2
        assert hitl_events[0].data["status"] == HITLStatus.RUNNING.value
        assert hitl_events[1].data["status"] == HITLStatus.DONE.value


# ---------------------------------------------------------------------------
# correct() — real execution (mocked subprocess)
# ---------------------------------------------------------------------------


class TestCorrectExecution:
    @pytest.mark.asyncio
    async def test_correct_runs_agent_and_returns_result(self, config, tmp_path):
        bus = EventBus()
        runner = HITLRunner(config, bus)
        issue = _make_issue()

        # Mock the subprocess execution
        mock_proc = make_streaming_proc(returncode=0, stdout="Applied fix")

        # Mock quality check to succeed
        quality_proc = AsyncMock()
        quality_proc.returncode = 0
        quality_proc.communicate = AsyncMock(return_value=(b"OK", b""))

        wt = tmp_path / "worktree"
        wt.mkdir()
        log_dir = config.repo_root / ".hydra" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            # First call is the claude process (via stream_claude_process)
            # Second call is make quality
            mock_exec.side_effect = [mock_proc.return_value, quality_proc]

            # Mock stream_claude_process directly for cleaner test
            with patch(
                "hitl_runner.stream_claude_process", new_callable=AsyncMock
            ) as mock_stream:
                mock_stream.return_value = "Applied the correction"

                result = await runner.correct(issue, "Fix auth", wt)

        assert result.issue_number == 42
        # Success depends on quality check
        assert result.transcript == "Applied the correction"

    @pytest.mark.asyncio
    async def test_correct_publishes_status_events(self, config, tmp_path):
        bus = EventBus()
        runner = HITLRunner(config, bus)
        issue = _make_issue()

        wt = tmp_path / "worktree"
        wt.mkdir()
        log_dir = config.repo_root / ".hydra" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        quality_proc = AsyncMock()
        quality_proc.returncode = 0
        quality_proc.communicate = AsyncMock(return_value=(b"OK", b""))

        with (
            patch(
                "hitl_runner.stream_claude_process", new_callable=AsyncMock
            ) as mock_stream,
            patch("asyncio.create_subprocess_exec", return_value=quality_proc),
        ):
            mock_stream.return_value = "Fixed"
            await runner.correct(issue, "Fix it", wt)

        history = bus.get_history()
        hitl_events = [e for e in history if e.type == EventType.HITL_UPDATE]
        statuses = [e.data["status"] for e in hitl_events]
        assert HITLStatus.RUNNING.value in statuses
        assert HITLStatus.TESTING.value in statuses


# ---------------------------------------------------------------------------
# terminate
# ---------------------------------------------------------------------------


class TestTerminate:
    def test_terminate_kills_active_processes(self, config):
        runner = _make_runner(config)

        mock_proc = AsyncMock()
        mock_proc.pid = 12345
        runner._active_procs.add(mock_proc)

        with patch("hitl_runner.terminate_processes") as mock_term:
            runner.terminate()
            mock_term.assert_called_once_with(runner._active_procs)
