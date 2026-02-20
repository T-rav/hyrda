"""HITL correction agent runner — launches Claude Code to apply human corrections."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from config import HydraConfig
from events import EventBus, EventType, HydraEvent
from models import GitHubIssue, HITLResult, HITLStatus
from runner_utils import stream_claude_process, terminate_processes

logger = logging.getLogger("hydra.hitl")


class HITLRunner:
    """Launches a ``claude -p`` process to apply a human-provided correction.

    The agent works inside an existing git worktree, applies the
    correction, runs quality checks, and commits changes but does
    **not** push or create PRs.
    """

    def __init__(self, config: HydraConfig, event_bus: EventBus) -> None:
        self._config = config
        self._bus = event_bus
        self._active_procs: set[asyncio.subprocess.Process] = set()

    async def correct(
        self,
        issue: GitHubIssue,
        correction: str,
        worktree_path: Path,
        worker_id: int = 0,
    ) -> HITLResult:
        """Run the correction agent for *issue* with human-provided instructions.

        Returns a :class:`HITLResult` with success/failure info.
        """
        start = time.monotonic()
        result = HITLResult(issue_number=issue.number)

        await self._emit_status(issue.number, worker_id, HITLStatus.RUNNING)

        if self._config.dry_run:
            logger.info(
                "[dry-run] Would run HITL correction for issue #%d", issue.number
            )
            result.success = True
            result.duration_seconds = time.monotonic() - start
            await self._emit_status(issue.number, worker_id, HITLStatus.DONE)
            return result

        try:
            cmd = self._build_command()
            prompt = self._build_prompt(issue, correction)
            transcript = await self._execute(cmd, prompt, worktree_path, issue.number)
            result.transcript = transcript

            await self._emit_status(issue.number, worker_id, HITLStatus.TESTING)

            # Run quality checks
            success, error_msg = await self._verify_quality(worktree_path)
            result.success = success
            if not success:
                result.error = error_msg

            status = HITLStatus.DONE if success else HITLStatus.FAILED
            await self._emit_status(issue.number, worker_id, status)

        except Exception as exc:
            result.success = False
            result.error = str(exc)
            logger.error(
                "HITL correction failed for issue #%d: %s",
                issue.number,
                exc,
                extra={"issue": issue.number},
            )
            await self._emit_status(issue.number, worker_id, HITLStatus.FAILED)

        result.duration_seconds = time.monotonic() - start
        self._save_transcript(result)
        return result

    def _build_command(self) -> list[str]:
        """Construct the ``claude`` CLI invocation for HITL correction."""
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

    def _build_prompt(self, issue: GitHubIssue, correction: str) -> str:
        """Build the correction prompt incorporating issue context and human instructions."""
        return f"""You are applying a human-provided correction for GitHub issue #{issue.number}.

## Issue: {issue.title}

{issue.body}

## Human Correction

The human operator has provided the following correction/instructions:

{correction}

## Instructions

1. Read the correction carefully and understand what needs to be done.
2. Apply the requested changes.
3. Run `make lint` to auto-fix formatting issues.
4. Run `make test-fast` to quickly check for test failures.
5. Run `make quality` to verify the full quality gate (lint + typecheck + security + tests).
6. Commit your changes with a message: "hitl-fix: <concise summary> (#{issue.number})"

## Rules

- Follow the project's CLAUDE.md guidelines strictly.
- Write tests for any new code — tests are mandatory.
- Do NOT push to remote. Do NOT create pull requests.
- Do NOT run `git push` or `gh pr create`.
- Ensure `make quality` passes before committing.
"""

    def terminate(self) -> None:
        """Kill all active HITL correction subprocesses."""
        terminate_processes(self._active_procs)

    async def _execute(
        self,
        cmd: list[str],
        prompt: str,
        worktree_path: Path,
        issue_number: int,
    ) -> str:
        """Run the claude correction process and stream its output."""
        return await stream_claude_process(
            cmd=cmd,
            prompt=prompt,
            cwd=worktree_path,
            active_procs=self._active_procs,
            event_bus=self._bus,
            event_data={"issue": issue_number, "source": "hitl"},
            logger=logger,
        )

    async def _verify_quality(self, worktree_path: Path) -> tuple[bool, str]:
        """Run ``make quality`` and return ``(success, error_output)``."""
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

    def _save_transcript(self, result: HITLResult) -> None:
        """Write the transcript to .hydra/logs/ for post-mortem review."""
        log_dir = self._config.repo_root / ".hydra" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / f"hitl-issue-{result.issue_number}.txt"
        path.write_text(result.transcript)
        logger.info(
            "HITL transcript saved to %s",
            path,
            extra={"issue": result.issue_number},
        )

    async def _emit_status(
        self, issue_number: int, worker_id: int, status: HITLStatus
    ) -> None:
        """Publish an HITL status event."""
        await self._bus.publish(
            HydraEvent(
                type=EventType.HITL_UPDATE,
                data={
                    "issue": issue_number,
                    "worker": worker_id,
                    "status": status.value,
                    "action": "correction",
                },
            )
        )
