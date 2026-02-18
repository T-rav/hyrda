"""Implementation agent runner — launches Claude Code to solve issues."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path

from config import HydraConfig
from events import EventBus, EventType, HydraEvent
from models import GitHubIssue, WorkerResult, WorkerStatus

logger = logging.getLogger("hydra.agent")


class AgentRunner:
    """Launches a ``claude -p`` process to implement a GitHub issue.

    The agent works inside an isolated git worktree and commits its
    changes but does **not** push or create PRs.
    """

    def __init__(self, config: HydraConfig, event_bus: EventBus) -> None:
        self._config = config
        self._bus = event_bus

    async def run(
        self,
        issue: GitHubIssue,
        worktree_path: Path,
        branch: str,
        worker_id: int = 0,
    ) -> WorkerResult:
        """Run the implementation agent for *issue*.

        Returns a :class:`WorkerResult` with success/failure info.
        """
        start = time.monotonic()
        result = WorkerResult(
            issue_number=issue.number,
            branch=branch,
            worktree_path=str(worktree_path),
        )

        await self._emit_status(issue.number, worker_id, WorkerStatus.RUNNING)

        if self._config.dry_run:
            logger.info("[dry-run] Would run agent for issue #%d", issue.number)
            result.success = True
            result.duration_seconds = time.monotonic() - start
            await self._emit_status(issue.number, worker_id, WorkerStatus.DONE)
            return result

        try:
            # Build and run the claude command
            cmd = self._build_command(worktree_path)
            prompt = self._build_prompt(issue)
            transcript = await self._execute(cmd, prompt, worktree_path, issue.number)
            result.transcript = transcript

            # Verify the agent produced valid work
            await self._emit_status(issue.number, worker_id, WorkerStatus.TESTING)
            success, verify_msg = await self._verify_result(worktree_path, branch)
            result.success = success
            if not success:
                result.error = verify_msg

            # Count commits
            result.commits = await self._count_commits(worktree_path, branch)

            status = WorkerStatus.DONE if success else WorkerStatus.FAILED
            await self._emit_status(issue.number, worker_id, status)

        except Exception as exc:
            result.success = False
            result.error = str(exc)
            logger.error(
                "Agent failed for issue #%d: %s",
                issue.number,
                exc,
                extra={"issue": issue.number},
            )
            await self._emit_status(issue.number, worker_id, WorkerStatus.FAILED)

        result.duration_seconds = time.monotonic() - start

        # Persist transcript to disk
        self._save_transcript(result)

        return result

    def _save_transcript(self, result: WorkerResult) -> None:
        """Write the transcript to .hydra-logs/ for post-mortem review."""
        log_dir = self._config.repo_root / ".hydra-logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / f"issue-{result.issue_number}.txt"
        path.write_text(result.transcript)
        logger.info(
            "Transcript saved to %s", path, extra={"issue": result.issue_number}
        )

    def _build_command(self, worktree_path: Path) -> list[str]:
        """Construct the ``claude`` CLI invocation."""
        return [
            "claude",
            "-p",
            "--cwd",
            str(worktree_path),
            "--output-format",
            "text",
            "--model",
            self._config.model,
            "--max-budget-usd",
            str(self._config.max_budget_usd),
            "--verbose",
        ]

    def _build_prompt(self, issue: GitHubIssue) -> str:
        """Build the implementation prompt for the agent."""
        comments_section = ""
        if issue.comments:
            formatted = "\n".join(f"- {c}" for c in issue.comments)
            comments_section = f"\n\n## Discussion\n{formatted}"

        return f"""You are implementing GitHub issue #{issue.number}.

## Issue: {issue.title}

{issue.body}{comments_section}

## Instructions

1. Read the issue carefully and understand what needs to be done.
2. Explore the codebase to understand the relevant code.
3. Write comprehensive tests FIRST (TDD approach).
4. Implement the solution.
5. Run `make lint` to auto-fix formatting issues.
6. Run `make test-fast` to verify all tests pass.
7. Commit your changes with a message: "Fixes #{issue.number}: <concise summary>"

## Rules

- Follow the project's CLAUDE.md guidelines strictly.
- Write tests for all new code — tests are mandatory.
- Do NOT push to remote. Do NOT create pull requests.
- Do NOT run `git push` or `gh pr create`.
- Ensure `make lint` and `make test-fast` pass before committing.
- If you encounter issues, commit what works with a descriptive message.
"""

    async def _execute(
        self,
        cmd: list[str],
        prompt: str,
        worktree_path: Path,
        issue_number: int,
    ) -> str:
        """Run the claude process and stream its output."""
        env = {**os.environ}
        env.pop("CLAUDECODE", None)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(worktree_path),
            env=env,
        )

        # Send the prompt on stdin and close it
        stdout_bytes, stderr_bytes = await proc.communicate(prompt.encode())
        transcript = stdout_bytes.decode(errors="replace")

        # Emit transcript lines
        for line in transcript.splitlines():
            if line.strip():
                await self._bus.publish(
                    HydraEvent(
                        type=EventType.TRANSCRIPT_LINE,
                        data={"issue": issue_number, "line": line},
                    )
                )

        if proc.returncode != 0:
            stderr_text = stderr_bytes.decode(errors="replace").strip()
            logger.warning(
                "Agent process exited with code %d for issue #%d: %s",
                proc.returncode,
                issue_number,
                stderr_text[:500],
            )

        return transcript

    async def _verify_result(
        self, worktree_path: Path, branch: str
    ) -> tuple[bool, str]:
        """Check that the agent produced commits and tests pass.

        Returns ``(success, message)``.
        """
        # Check for commits on the branch
        commit_count = await self._count_commits(worktree_path, branch)
        if commit_count == 0:
            return False, "No commits found on branch"

        # Run tests
        try:
            proc = await asyncio.create_subprocess_exec(
                "make",
                "test-fast",
                cwd=str(worktree_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                output = stdout.decode(errors="replace") + stderr.decode(
                    errors="replace"
                )
                return False, f"Tests failed:\n{output[-2000:]}"
        except FileNotFoundError:
            return False, "make not found — cannot run tests"

        return True, "OK"

    async def _count_commits(self, worktree_path: Path, branch: str) -> int:
        """Count commits on *branch* ahead of main."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "git",
                "rev-list",
                "--count",
                f"origin/{self._config.main_branch}..{branch}",
                cwd=str(worktree_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            return int(stdout.decode().strip())
        except (ValueError, FileNotFoundError):
            return 0

    async def _emit_status(
        self, issue_number: int, worker_id: int, status: WorkerStatus
    ) -> None:
        """Publish a worker status event."""
        await self._bus.publish(
            HydraEvent(
                type=EventType.WORKER_UPDATE,
                data={
                    "issue": issue_number,
                    "worker": worker_id,
                    "status": status.value,
                },
            )
        )
