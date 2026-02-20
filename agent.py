"""Implementation agent runner — launches Claude Code to solve issues."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from pathlib import Path

from config import HydraConfig
from events import EventBus, EventType, HydraEvent
from models import GitHubIssue, WorkerResult, WorkerStatus
from stream_parser import StreamParser
from subprocess_util import make_clean_env

logger = logging.getLogger("hydra.agent")


class AgentRunner:
    """Launches a ``claude -p`` process to implement a GitHub issue.

    The agent works inside an isolated git worktree and commits its
    changes but does **not** push or create PRs.
    """

    def __init__(self, config: HydraConfig, event_bus: EventBus) -> None:
        self._config = config
        self._bus = event_bus
        self._active_procs: set[asyncio.subprocess.Process] = set()

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

            # If quality failed but commits exist, try the fix loop
            if (
                not success
                and verify_msg != "No commits found on branch"
                and self._config.max_quality_fix_attempts > 0
            ):
                success, verify_msg, attempts = await self._run_quality_fix_loop(
                    issue, worktree_path, branch, verify_msg, worker_id
                )
                result.quality_fix_attempts = attempts

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
        """Write the transcript to .hydra/logs/ for post-mortem review."""
        log_dir = self._config.repo_root / ".hydra" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / f"issue-{result.issue_number}.txt"
        path.write_text(result.transcript)
        logger.info(
            "Transcript saved to %s", path, extra={"issue": result.issue_number}
        )

    def _build_command(self, worktree_path: Path) -> list[str]:
        """Construct the ``claude`` CLI invocation.

        The working directory is set via ``cwd`` in the subprocess call,
        not via a CLI flag.
        """
        cmd = [
            "claude",
            "-p",
            "--output-format",
            "stream-json",
            "--model",
            self._config.model,
            "--verbose",
            "--permission-mode",
            "bypassPermissions",
        ]
        if self._config.max_budget_usd > 0:
            cmd.extend(["--max-budget-usd", str(self._config.max_budget_usd)])
        return cmd

    @staticmethod
    def _extract_plan_comment(comments: list[str]) -> tuple[str, list[str]]:
        """Separate the planner's implementation plan from other comments.

        Returns ``(plan_text, remaining_comments)``.  *plan_text* is the
        raw body of the first comment that contains ``## Implementation Plan``,
        or an empty string if none is found.
        """
        plan = ""
        remaining: list[str] = []
        for c in comments:
            if not plan and "## Implementation Plan" in c:
                plan = c
            else:
                remaining.append(c)
        return plan, remaining

    def _build_prompt(self, issue: GitHubIssue) -> str:
        """Build the implementation prompt for the agent."""
        plan_comment, other_comments = self._extract_plan_comment(issue.comments)

        plan_section = ""
        if plan_comment:
            plan_section = (
                f"\n\n## Implementation Plan\n\n"
                f"Follow this plan closely. It was created by a planner agent "
                f"that already analyzed the codebase.\n\n"
                f"{plan_comment}"
            )

        comments_section = ""
        if other_comments:
            formatted = "\n".join(f"- {c}" for c in other_comments)
            comments_section = f"\n\n## Discussion\n{formatted}"

        return f"""You are implementing GitHub issue #{issue.number}.

## Issue: {issue.title}

{issue.body}{plan_section}{comments_section}

## Instructions

1. Read the issue carefully and understand what needs to be done.
2. Explore the codebase to understand the relevant code.
3. Write comprehensive tests FIRST (TDD approach).
4. Implement the solution.
5. Run `make lint` to auto-fix formatting issues.
6. Run `make test-fast` to quickly check for test failures.
7. Run `make quality` to verify the full quality gate (lint + typecheck + security + tests).
8. Commit your changes with a message: "Fixes #{issue.number}: <concise summary>"

## Rules

- Follow the project's CLAUDE.md guidelines strictly.
- Write tests for all new code — tests are mandatory.
- Do NOT push to remote. Do NOT create pull requests.
- Do NOT run `git push` or `gh pr create`.
- Ensure `make quality` passes before committing.
- If you encounter issues, commit what works with a descriptive message.
"""

    def terminate(self) -> None:
        """Kill all active agent subprocesses."""
        for proc in list(self._active_procs):
            with contextlib.suppress(ProcessLookupError):
                proc.kill()

    async def _execute(
        self,
        cmd: list[str],
        prompt: str,
        worktree_path: Path,
        issue_number: int,
    ) -> str:
        """Run the claude process and stream its output."""
        env = make_clean_env()

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(worktree_path),
            env=env,
            limit=1024 * 1024,  # 1 MB — stream-json lines can exceed 64 KB default
        )
        self._active_procs.add(proc)

        try:
            # Send the prompt on stdin and close it
            assert proc.stdin is not None
            assert proc.stdout is not None
            assert proc.stderr is not None

            proc.stdin.write(prompt.encode())
            await proc.stdin.drain()
            proc.stdin.close()

            # Drain stderr in background to prevent deadlock
            stderr_task = asyncio.create_task(proc.stderr.read())

            parser = StreamParser()
            raw_lines: list[str] = []
            result_text = ""
            async for raw in proc.stdout:
                line = raw.decode(errors="replace").rstrip("\n")
                raw_lines.append(line)
                if not line.strip():
                    continue

                display, result = parser.parse(line)
                if result is not None:
                    result_text = result

                if display.strip():
                    await self._bus.publish(
                        HydraEvent(
                            type=EventType.TRANSCRIPT_LINE,
                            data={"issue": issue_number, "line": display},
                        )
                    )

            stderr_bytes = await stderr_task
            await proc.wait()

            if proc.returncode != 0:
                stderr_text = stderr_bytes.decode(errors="replace").strip()
                logger.warning(
                    "Agent process exited with code %d for issue #%d: %s",
                    proc.returncode,
                    issue_number,
                    stderr_text[:500],
                )

            return result_text or "\n".join(raw_lines)
        except asyncio.CancelledError:
            proc.kill()
            raise
        finally:
            self._active_procs.discard(proc)

    async def _verify_result(
        self, worktree_path: Path, branch: str
    ) -> tuple[bool, str]:
        """Check that the agent produced commits and ``make quality`` passes.

        Returns ``(success, error_output)``.  On failure the error output
        contains the last 3000 characters of combined stdout/stderr.
        """
        # Check for commits on the branch
        commit_count = await self._count_commits(worktree_path, branch)
        if commit_count == 0:
            return False, "No commits found on branch"

        # Run the full quality gate
        try:
            proc = await asyncio.create_subprocess_exec(
                "make",
                "quality",
                cwd=str(worktree_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                output = stdout.decode(errors="replace") + stderr.decode(
                    errors="replace"
                )
                return False, f"`make quality` failed:\n{output[-3000:]}"
        except FileNotFoundError:
            return False, "make not found — cannot run quality checks"

        return True, "OK"

    def _build_quality_fix_prompt(
        self,
        issue: GitHubIssue,
        error_output: str,
        attempt: int,
    ) -> str:
        """Build a focused prompt for fixing quality gate failures."""
        return f"""You are fixing quality gate failures for issue #{issue.number}: {issue.title}

## Quality Gate Failure Output

```
{error_output[-3000:]}
```

## Fix Attempt {attempt}

1. Read the failing output above carefully.
2. Fix ALL lint, type-check, security, and test issues.
3. Do NOT skip or disable tests, type checks, or lint rules.
4. Run `make quality` to verify your fixes pass the full pipeline.
5. Commit your fixes with message: "quality-fix: <description> (#{issue.number})"

Focus on fixing the root causes, not suppressing warnings.
"""

    async def _run_quality_fix_loop(
        self,
        issue: GitHubIssue,
        worktree_path: Path,
        branch: str,
        error_output: str,
        worker_id: int,
    ) -> tuple[bool, str, int]:
        """Retry loop: invoke Claude to fix quality failures.

        Returns ``(success, last_error, attempts_made)``.
        """
        max_attempts = self._config.max_quality_fix_attempts
        last_error = error_output

        for attempt in range(1, max_attempts + 1):
            logger.info(
                "Quality fix attempt %d/%d for issue #%d",
                attempt,
                max_attempts,
                issue.number,
            )
            await self._emit_status(issue.number, worker_id, WorkerStatus.QUALITY_FIX)

            prompt = self._build_quality_fix_prompt(issue, last_error, attempt)
            cmd = self._build_command(worktree_path)
            await self._execute(cmd, prompt, worktree_path, issue.number)

            success, verify_msg = await self._verify_result(worktree_path, branch)
            if success:
                return True, "OK", attempt

            last_error = verify_msg

        return False, last_error, max_attempts

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
                    "role": "implementer",
                },
            )
        )
