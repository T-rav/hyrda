"""Tests for dx/hydra/agent.py — AgentRunner."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import AsyncMock, patch

import pytest

from agent import AgentRunner
from events import EventBus, EventType
from models import WorkerStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_proc(
    returncode: int = 0,
    stdout: bytes = b"",
    stderr: bytes = b"",
) -> AsyncMock:
    """Build a minimal mock subprocess object."""
    proc = AsyncMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    return proc


# ---------------------------------------------------------------------------
# AgentRunner._build_command
# ---------------------------------------------------------------------------


class TestBuildCommand:
    """Tests for AgentRunner._build_command."""

    def test_build_command_starts_with_claude(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """Command should start with 'claude'."""
        runner = AgentRunner(config, event_bus)
        cmd = runner._build_command(tmp_path)
        assert cmd[0] == "claude"

    def test_build_command_includes_print_flag(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """Command should include the -p (print/non-interactive) flag."""
        runner = AgentRunner(config, event_bus)
        cmd = runner._build_command(tmp_path)
        assert "-p" in cmd

    def test_build_command_does_not_include_cwd(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """Command should not include --cwd; cwd is set on the subprocess."""
        runner = AgentRunner(config, event_bus)
        cmd = runner._build_command(tmp_path)
        assert "--cwd" not in cmd

    def test_build_command_includes_model(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """Command should include --model matching config.model."""
        runner = AgentRunner(config, event_bus)
        cmd = runner._build_command(tmp_path)
        assert "--model" in cmd
        model_index = cmd.index("--model")
        assert cmd[model_index + 1] == config.model

    def test_build_command_includes_max_budget(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """Command should include --max-budget-usd matching config.max_budget_usd."""
        runner = AgentRunner(config, event_bus)
        cmd = runner._build_command(tmp_path)
        assert "--max-budget-usd" in cmd
        budget_index = cmd.index("--max-budget-usd")
        assert cmd[budget_index + 1] == str(config.max_budget_usd)

    def test_build_command_includes_output_format_text(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """Command should pass --output-format text."""
        runner = AgentRunner(config, event_bus)
        cmd = runner._build_command(tmp_path)
        assert "--output-format" in cmd
        fmt_index = cmd.index("--output-format")
        assert cmd[fmt_index + 1] == "text"

    def test_build_command_includes_verbose(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """Command should include --verbose."""
        runner = AgentRunner(config, event_bus)
        cmd = runner._build_command(tmp_path)
        assert "--verbose" in cmd


# ---------------------------------------------------------------------------
# AgentRunner._build_prompt
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    """Tests for AgentRunner._build_prompt."""

    def test_prompt_includes_issue_number(
        self, config, event_bus: EventBus, issue
    ) -> None:
        """Prompt should reference the issue number."""
        runner = AgentRunner(config, event_bus)
        prompt = runner._build_prompt(issue)
        assert str(issue.number) in prompt

    def test_prompt_includes_title(self, config, event_bus: EventBus, issue) -> None:
        """Prompt should include the issue title."""
        runner = AgentRunner(config, event_bus)
        prompt = runner._build_prompt(issue)
        assert issue.title in prompt

    def test_prompt_includes_body(self, config, event_bus: EventBus, issue) -> None:
        """Prompt should include the issue body text."""
        runner = AgentRunner(config, event_bus)
        prompt = runner._build_prompt(issue)
        assert issue.body in prompt

    def test_prompt_includes_rules(self, config, event_bus: EventBus, issue) -> None:
        """Prompt should contain the mandatory rules section."""
        runner = AgentRunner(config, event_bus)
        prompt = runner._build_prompt(issue)
        assert "Rules" in prompt or "rules" in prompt.lower()

    def test_prompt_includes_comments_section_when_comments_exist(
        self, config, event_bus: EventBus
    ) -> None:
        """Prompt should include a Discussion section when the issue has comments."""
        from models import GitHubIssue

        issue_with_comments = GitHubIssue(
            number=10,
            title="Add feature X",
            body="We need feature X",
            comments=["Please also handle edge case Y", "What about Z?"],
        )
        runner = AgentRunner(config, event_bus)
        prompt = runner._build_prompt(issue_with_comments)

        assert "Discussion" in prompt
        assert "Please also handle edge case Y" in prompt
        assert "What about Z?" in prompt

    def test_prompt_omits_comments_section_when_no_comments(
        self, config, event_bus: EventBus, issue
    ) -> None:
        """Prompt should not include a Discussion section when there are no comments."""
        # Default issue fixture has empty comments
        runner = AgentRunner(config, event_bus)
        prompt = runner._build_prompt(issue)
        assert "Discussion" not in prompt

    def test_prompt_instructs_no_push_or_pr(
        self, config, event_bus: EventBus, issue
    ) -> None:
        """Prompt should explicitly tell the agent not to push or create PRs."""
        runner = AgentRunner(config, event_bus)
        prompt = runner._build_prompt(issue)
        assert "push" in prompt.lower() or "Do NOT push" in prompt
        assert "pull request" in prompt.lower() or "pr create" in prompt.lower()


# ---------------------------------------------------------------------------
# AgentRunner.run — success path
# ---------------------------------------------------------------------------


class TestRunSuccess:
    """Tests for the happy path of AgentRunner.run."""

    @pytest.mark.asyncio
    async def test_run_success_returns_worker_result_with_success_true(
        self, config, event_bus: EventBus, issue, tmp_path: Path
    ) -> None:
        """run should return a WorkerResult with success=True on the happy path."""
        runner = AgentRunner(config, event_bus)

        with (
            patch.object(
                runner, "_execute", new_callable=AsyncMock, return_value="transcript"
            ),
            patch.object(
                runner,
                "_verify_result",
                new_callable=AsyncMock,
                return_value=(True, "OK"),
            ),
            patch.object(
                runner,
                "_count_commits",
                new_callable=AsyncMock,
                return_value=2,
            ),
            patch.object(runner, "_save_transcript"),
        ):
            result = await runner.run(issue, tmp_path, "agent/issue-42")

        assert result.success is True
        assert result.issue_number == issue.number
        assert result.branch == "agent/issue-42"
        assert result.commits == 2
        assert result.transcript == "transcript"

    @pytest.mark.asyncio
    async def test_run_success_sets_duration(
        self, config, event_bus: EventBus, issue, tmp_path: Path
    ) -> None:
        """run should record a positive duration_seconds."""
        runner = AgentRunner(config, event_bus)

        with (
            patch.object(runner, "_execute", new_callable=AsyncMock, return_value=""),
            patch.object(
                runner,
                "_verify_result",
                new_callable=AsyncMock,
                return_value=(True, "OK"),
            ),
            patch.object(
                runner, "_count_commits", new_callable=AsyncMock, return_value=1
            ),
            patch.object(runner, "_save_transcript"),
        ):
            result = await runner.run(issue, tmp_path, "agent/issue-42")

        assert result.duration_seconds >= 0


# ---------------------------------------------------------------------------
# AgentRunner.run — failure paths
# ---------------------------------------------------------------------------


class TestRunFailure:
    """Tests for failure paths of AgentRunner.run."""

    @pytest.mark.asyncio
    async def test_run_failure_when_verify_returns_false(
        self, config, event_bus: EventBus, issue, tmp_path: Path
    ) -> None:
        """run should return success=False when _verify_result returns (False, msg)."""
        runner = AgentRunner(config, event_bus)

        with (
            patch.object(
                runner, "_execute", new_callable=AsyncMock, return_value="output"
            ),
            patch.object(
                runner,
                "_verify_result",
                new_callable=AsyncMock,
                return_value=(False, "Tests failed"),
            ),
            patch.object(
                runner, "_count_commits", new_callable=AsyncMock, return_value=1
            ),
            patch.object(runner, "_save_transcript"),
        ):
            result = await runner.run(issue, tmp_path, "agent/issue-42")

        assert result.success is False
        assert result.error == "Tests failed"

    @pytest.mark.asyncio
    async def test_run_handles_exception_and_returns_failure(
        self, config, event_bus: EventBus, issue, tmp_path: Path
    ) -> None:
        """run should catch unexpected exceptions and return success=False."""
        runner = AgentRunner(config, event_bus)

        with (
            patch.object(
                runner,
                "_execute",
                new_callable=AsyncMock,
                side_effect=RuntimeError("subprocess exploded"),
            ),
            patch.object(runner, "_save_transcript"),
        ):
            result = await runner.run(issue, tmp_path, "agent/issue-42")

        assert result.success is False
        assert "subprocess exploded" in (result.error or "")

    @pytest.mark.asyncio
    async def test_run_records_error_message_on_exception(
        self, config, event_bus: EventBus, issue, tmp_path: Path
    ) -> None:
        """run should store the exception message in result.error."""
        runner = AgentRunner(config, event_bus)

        with (
            patch.object(
                runner,
                "_execute",
                new_callable=AsyncMock,
                side_effect=ValueError("unexpected value"),
            ),
            patch.object(runner, "_save_transcript"),
        ):
            result = await runner.run(issue, tmp_path, "agent/issue-42")

        assert result.error is not None
        assert "unexpected value" in result.error


# ---------------------------------------------------------------------------
# AgentRunner.run — dry-run mode
# ---------------------------------------------------------------------------


class TestRunDryRun:
    """Tests for dry-run behaviour of AgentRunner.run."""

    @pytest.mark.asyncio
    async def test_dry_run_returns_success_without_executing(
        self, dry_config, event_bus: EventBus, issue, tmp_path: Path
    ) -> None:
        """In dry-run mode, run should succeed without calling _execute."""
        runner = AgentRunner(dry_config, event_bus)

        execute_mock = AsyncMock()
        with patch.object(runner, "_execute", execute_mock):
            result = await runner.run(issue, tmp_path, "agent/issue-42")

        execute_mock.assert_not_awaited()
        assert result.success is True

    @pytest.mark.asyncio
    async def test_dry_run_does_not_call_verify_result(
        self, dry_config, event_bus: EventBus, issue, tmp_path: Path
    ) -> None:
        """In dry-run mode, _verify_result should not be called."""
        runner = AgentRunner(dry_config, event_bus)

        verify_mock = AsyncMock()
        with patch.object(runner, "_verify_result", verify_mock):
            await runner.run(issue, tmp_path, "agent/issue-42")

        verify_mock.assert_not_awaited()


# ---------------------------------------------------------------------------
# AgentRunner._verify_result
# ---------------------------------------------------------------------------


class TestVerifyResult:
    """Tests for AgentRunner._verify_result."""

    @pytest.mark.asyncio
    async def test_verify_returns_false_when_no_commits(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """_verify_result should return (False, ...) when commit count is 0."""
        runner = AgentRunner(config, event_bus)

        with patch.object(
            runner, "_count_commits", new_callable=AsyncMock, return_value=0
        ):
            success, msg = await runner._verify_result(tmp_path, "agent/issue-42")

        assert success is False
        assert "commit" in msg.lower()

    @pytest.mark.asyncio
    async def test_verify_runs_make_test_fast_when_commits_exist(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """_verify_result should run 'make test-fast' when at least one commit exists."""
        runner = AgentRunner(config, event_bus)

        success_proc = _make_proc(returncode=0, stdout=b"All tests passed")

        with (
            patch.object(
                runner, "_count_commits", new_callable=AsyncMock, return_value=1
            ),
            patch(
                "asyncio.create_subprocess_exec", return_value=success_proc
            ) as mock_exec,
        ):
            success, msg = await runner._verify_result(tmp_path, "agent/issue-42")

        assert success is True
        assert msg == "OK"
        # Ensure 'make test-fast' was invoked
        assert mock_exec.call_args.args[:2] == ("make", "test-fast")

    @pytest.mark.asyncio
    async def test_verify_returns_false_when_tests_fail(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """_verify_result should return (False, ...) when tests exit non-zero."""
        runner = AgentRunner(config, event_bus)

        fail_proc = _make_proc(
            returncode=1, stdout=b"FAILED test_foo.py::test_bar", stderr=b""
        )

        with (
            patch.object(
                runner, "_count_commits", new_callable=AsyncMock, return_value=1
            ),
            patch("asyncio.create_subprocess_exec", return_value=fail_proc),
        ):
            success, msg = await runner._verify_result(tmp_path, "agent/issue-42")

        assert success is False
        assert "Tests failed" in msg or "failed" in msg.lower()

    @pytest.mark.asyncio
    async def test_verify_returns_false_when_make_not_found(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """_verify_result should handle FileNotFoundError from missing 'make'."""
        runner = AgentRunner(config, event_bus)

        with (
            patch.object(
                runner, "_count_commits", new_callable=AsyncMock, return_value=1
            ),
            patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError),
        ):
            success, msg = await runner._verify_result(tmp_path, "agent/issue-42")

        assert success is False
        assert "make" in msg.lower()


# ---------------------------------------------------------------------------
# AgentRunner._save_transcript
# ---------------------------------------------------------------------------


class TestSaveTranscript:
    """Tests for AgentRunner._save_transcript."""

    def test_save_transcript_writes_to_hydra_logs(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """_save_transcript should write to <repo_root>/.hydra-logs/issue-N.txt."""
        from models import WorkerResult

        config.repo_root.mkdir(parents=True, exist_ok=True)
        runner = AgentRunner(config, event_bus)

        result = WorkerResult(
            issue_number=42,
            branch="agent/issue-42",
            transcript="This is the agent transcript",
        )
        runner._save_transcript(result)

        expected_path = config.repo_root / ".hydra-logs" / "issue-42.txt"
        assert expected_path.exists()
        assert expected_path.read_text() == "This is the agent transcript"

    def test_save_transcript_creates_log_directory(
        self, config, event_bus: EventBus
    ) -> None:
        """_save_transcript should create .hydra-logs/ if it does not exist."""
        from models import WorkerResult

        config.repo_root.mkdir(parents=True, exist_ok=True)
        log_dir = config.repo_root / ".hydra-logs"
        assert not log_dir.exists()

        runner = AgentRunner(config, event_bus)
        result = WorkerResult(
            issue_number=7,
            branch="agent/issue-7",
            transcript="output",
        )
        runner._save_transcript(result)

        assert log_dir.is_dir()

    def test_save_transcript_uses_issue_number_in_filename(
        self, config, event_bus: EventBus
    ) -> None:
        """_save_transcript filename should be issue-<number>.txt."""
        from models import WorkerResult

        config.repo_root.mkdir(parents=True, exist_ok=True)
        runner = AgentRunner(config, event_bus)

        result = WorkerResult(
            issue_number=123,
            branch="agent/issue-123",
            transcript="content",
        )
        runner._save_transcript(result)

        log_file = config.repo_root / ".hydra-logs" / "issue-123.txt"
        assert log_file.exists()


# ---------------------------------------------------------------------------
# AgentRunner — event publishing
# ---------------------------------------------------------------------------


class TestEventPublishing:
    """Tests verifying that the correct events are published during a run."""

    @pytest.mark.asyncio
    async def test_run_emits_running_status_at_start(
        self, config, event_bus: EventBus, issue, tmp_path: Path
    ) -> None:
        """run should publish WORKER_UPDATE with status=running before executing."""
        runner = AgentRunner(config, event_bus)
        received_events = []

        # Subscribe BEFORE the run
        queue = event_bus.subscribe()

        with (
            patch.object(runner, "_execute", new_callable=AsyncMock, return_value=""),
            patch.object(
                runner,
                "_verify_result",
                new_callable=AsyncMock,
                return_value=(True, "OK"),
            ),
            patch.object(
                runner, "_count_commits", new_callable=AsyncMock, return_value=1
            ),
            patch.object(runner, "_save_transcript"),
        ):
            await runner.run(issue, tmp_path, "agent/issue-42")

        while not queue.empty():
            received_events.append(queue.get_nowait())

        worker_updates = [
            e for e in received_events if e.type == EventType.WORKER_UPDATE
        ]
        statuses = [e.data.get("status") for e in worker_updates]
        assert WorkerStatus.RUNNING.value in statuses

    @pytest.mark.asyncio
    async def test_run_emits_done_status_on_success(
        self, config, event_bus: EventBus, issue, tmp_path: Path
    ) -> None:
        """run should publish WORKER_UPDATE with status=done on a successful run."""
        runner = AgentRunner(config, event_bus)
        queue = event_bus.subscribe()

        with (
            patch.object(runner, "_execute", new_callable=AsyncMock, return_value=""),
            patch.object(
                runner,
                "_verify_result",
                new_callable=AsyncMock,
                return_value=(True, "OK"),
            ),
            patch.object(
                runner, "_count_commits", new_callable=AsyncMock, return_value=1
            ),
            patch.object(runner, "_save_transcript"),
        ):
            await runner.run(issue, tmp_path, "agent/issue-42")

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        worker_updates = [e for e in events if e.type == EventType.WORKER_UPDATE]
        statuses = [e.data.get("status") for e in worker_updates]
        assert WorkerStatus.DONE.value in statuses

    @pytest.mark.asyncio
    async def test_run_emits_failed_status_on_exception(
        self, config, event_bus: EventBus, issue, tmp_path: Path
    ) -> None:
        """run should publish WORKER_UPDATE with status=failed when an exception occurs."""
        runner = AgentRunner(config, event_bus)
        queue = event_bus.subscribe()

        with (
            patch.object(
                runner,
                "_execute",
                new_callable=AsyncMock,
                side_effect=RuntimeError("boom"),
            ),
            patch.object(runner, "_save_transcript"),
        ):
            await runner.run(issue, tmp_path, "agent/issue-42")

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        worker_updates = [e for e in events if e.type == EventType.WORKER_UPDATE]
        statuses = [e.data.get("status") for e in worker_updates]
        assert WorkerStatus.FAILED.value in statuses

    @pytest.mark.asyncio
    async def test_run_emits_testing_status_during_verification(
        self, config, event_bus: EventBus, issue, tmp_path: Path
    ) -> None:
        """run should publish WORKER_UPDATE with status=testing before verifying."""
        runner = AgentRunner(config, event_bus)
        queue = event_bus.subscribe()

        with (
            patch.object(runner, "_execute", new_callable=AsyncMock, return_value=""),
            patch.object(
                runner,
                "_verify_result",
                new_callable=AsyncMock,
                return_value=(True, "OK"),
            ),
            patch.object(
                runner, "_count_commits", new_callable=AsyncMock, return_value=1
            ),
            patch.object(runner, "_save_transcript"),
        ):
            await runner.run(issue, tmp_path, "agent/issue-42")

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        worker_updates = [e for e in events if e.type == EventType.WORKER_UPDATE]
        statuses = [e.data.get("status") for e in worker_updates]
        assert WorkerStatus.TESTING.value in statuses

    @pytest.mark.asyncio
    async def test_run_events_include_correct_issue_number(
        self, config, event_bus: EventBus, issue, tmp_path: Path
    ) -> None:
        """WORKER_UPDATE events should carry the correct issue number."""
        runner = AgentRunner(config, event_bus)
        queue = event_bus.subscribe()

        with (
            patch.object(runner, "_execute", new_callable=AsyncMock, return_value=""),
            patch.object(
                runner,
                "_verify_result",
                new_callable=AsyncMock,
                return_value=(True, "OK"),
            ),
            patch.object(
                runner, "_count_commits", new_callable=AsyncMock, return_value=1
            ),
            patch.object(runner, "_save_transcript"),
        ):
            await runner.run(issue, tmp_path, "agent/issue-42", worker_id=3)

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        worker_updates = [e for e in events if e.type == EventType.WORKER_UPDATE]
        for event in worker_updates:
            assert event.data.get("issue") == issue.number
            assert event.data.get("worker") == 3

    @pytest.mark.asyncio
    async def test_dry_run_emits_running_and_done_events(
        self, dry_config, event_bus: EventBus, issue, tmp_path: Path
    ) -> None:
        """In dry-run mode, run should still emit RUNNING and DONE status events."""
        runner = AgentRunner(dry_config, event_bus)
        queue = event_bus.subscribe()

        await runner.run(issue, tmp_path, "agent/issue-42")

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        worker_updates = [e for e in events if e.type == EventType.WORKER_UPDATE]
        statuses = [e.data.get("status") for e in worker_updates]
        assert WorkerStatus.RUNNING.value in statuses
        assert WorkerStatus.DONE.value in statuses
