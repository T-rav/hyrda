"""PR review agent runner — launches Claude Code to review and fix PRs."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from pathlib import Path

from config import HydraConfig
from events import EventBus, EventType, HydraEvent
from models import GitHubIssue, PRInfo, ReviewResult, ReviewVerdict
from stream_parser import StreamParser

logger = logging.getLogger("hydra.reviewer")


class ReviewRunner:
    """Launches a ``claude -p`` process to review a pull request.

    The reviewer reads the PR diff, checks code quality and test
    coverage, optionally makes fixes, and returns a verdict.
    """

    def __init__(self, config: HydraConfig, event_bus: EventBus) -> None:
        self._config = config
        self._bus = event_bus
        self._active_procs: set[asyncio.subprocess.Process] = set()

    async def review(
        self,
        pr: PRInfo,
        issue: GitHubIssue,
        worktree_path: Path,
        diff: str,
        worker_id: int = 0,
    ) -> ReviewResult:
        """Run the review agent for *pr*.

        Returns a :class:`ReviewResult` with the verdict and summary.
        """
        start = time.monotonic()
        result = ReviewResult(
            pr_number=pr.number,
            issue_number=issue.number,
        )

        await self._bus.publish(
            HydraEvent(
                type=EventType.REVIEW_UPDATE,
                data={
                    "pr": pr.number,
                    "issue": issue.number,
                    "worker": worker_id,
                    "status": "reviewing",
                    "role": "reviewer",
                },
            )
        )

        if self._config.dry_run:
            logger.info("[dry-run] Would review PR #%d", pr.number)
            result.verdict = ReviewVerdict.APPROVE
            result.summary = "Dry-run: auto-approved"
            return result

        try:
            cmd = self._build_command(worktree_path)
            prompt = self._build_review_prompt(pr, issue, diff)
            transcript = await self._execute(cmd, prompt, worktree_path, pr.number)
            result.transcript = transcript

            # Parse the verdict from the transcript
            result.verdict = self._parse_verdict(transcript)
            result.summary = self._extract_summary(transcript)

            # Check if the reviewer made any commits (fixes)
            result.fixes_made = await self._has_new_commits(worktree_path)

            # Persist to disk
            self._save_transcript(pr.number, transcript)

        except Exception as exc:
            result.verdict = ReviewVerdict.COMMENT
            result.summary = f"Review failed: {exc}"
            logger.error("Review failed for PR #%d: %s", pr.number, exc)

        await self._bus.publish(
            HydraEvent(
                type=EventType.REVIEW_UPDATE,
                data={
                    "pr": pr.number,
                    "issue": issue.number,
                    "worker": worker_id,
                    "status": "done",
                    "verdict": result.verdict.value,
                    "duration": time.monotonic() - start,
                    "role": "reviewer",
                },
            )
        )

        return result

    def _build_command(self, worktree_path: Path) -> list[str]:
        """Construct the ``claude`` CLI invocation for review.

        The working directory is set via ``cwd`` in the subprocess call,
        not via a CLI flag.
        """
        cmd = [
            "claude",
            "-p",
            "--output-format",
            "stream-json",
            "--model",
            self._config.review_model,
            "--verbose",
            "--permission-mode",
            "bypass",
        ]
        if self._config.review_budget_usd > 0:
            cmd.extend(["--max-budget-usd", str(self._config.review_budget_usd)])
        return cmd

    def _build_review_prompt(self, pr: PRInfo, issue: GitHubIssue, diff: str) -> str:
        """Build the review prompt for the agent."""
        return f"""You are reviewing PR #{pr.number} which implements issue #{issue.number}.

## Issue: {issue.title}

{issue.body}

## PR Diff

```diff
{diff[:15000]}
```

## Review Instructions

1. Check that the implementation correctly addresses the issue.
2. Verify comprehensive test coverage (tests are MANDATORY per CLAUDE.md).
3. Check code quality: type annotations, proper error handling, no security issues.
4. Check CLAUDE.md compliance: linting, formatting, no secrets committed.
5. Run `make lint` and `make test-fast` to verify everything passes.
6. Run the project's audit commands on the changed code:
   - Review code quality patterns (SRP, type hints, naming, complexity)
   - Review test quality (3As structure, factories, edge cases)
   - Check for security issues (injection, crypto, auth)

## If Issues Found

If you find issues that you can fix:
1. Make the fixes directly.
2. Run `make lint` and `make test-fast`.
3. Commit with message: "review: fix <description> (PR #{pr.number})"

## Required Output

End your response with EXACTLY one of these verdict lines:
- VERDICT: APPROVE
- VERDICT: REQUEST_CHANGES
- VERDICT: COMMENT

Then a brief summary on the next line starting with "SUMMARY: ".

Example:
VERDICT: APPROVE
SUMMARY: Implementation looks good, tests are comprehensive, all checks pass.
"""

    def _parse_verdict(self, transcript: str) -> ReviewVerdict:
        """Extract the verdict from the reviewer transcript."""
        pattern = r"VERDICT:\s*(APPROVE|REQUEST_CHANGES|COMMENT)"
        match = re.search(pattern, transcript, re.IGNORECASE)
        if match:
            raw = match.group(1).upper().replace("_", "-")
            # Map the parsed string to the enum
            mapping = {
                "APPROVE": ReviewVerdict.APPROVE,
                "REQUEST-CHANGES": ReviewVerdict.REQUEST_CHANGES,
                "COMMENT": ReviewVerdict.COMMENT,
            }
            return mapping.get(raw, ReviewVerdict.COMMENT)
        return ReviewVerdict.COMMENT

    def _extract_summary(self, transcript: str) -> str:
        """Extract the summary line from the reviewer transcript."""
        pattern = r"SUMMARY:\s*(.+)"
        match = re.search(pattern, transcript, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        # Fallback: last non-empty line
        lines = [ln.strip() for ln in transcript.splitlines() if ln.strip()]
        return lines[-1][:200] if lines else "No summary provided"

    def terminate(self) -> None:
        """Kill all active reviewer subprocesses."""
        for proc in list(self._active_procs):
            try:
                proc.kill()
            except ProcessLookupError:
                pass

    async def _execute(
        self,
        cmd: list[str],
        prompt: str,
        worktree_path: Path,
        pr_number: int,
    ) -> str:
        """Run the claude review process."""
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
        self._active_procs.add(proc)

        try:
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
                            data={"pr": pr_number, "line": display, "source": "reviewer"},
                        )
                    )

            await stderr_task
            await proc.wait()
            return result_text or "\n".join(raw_lines)
        except asyncio.CancelledError:
            proc.kill()
            raise
        finally:
            self._active_procs.discard(proc)

    def _save_transcript(self, pr_number: int, transcript: str) -> None:
        """Write the review transcript to .hydra/logs/ for post-mortem review."""
        log_dir = self._config.repo_root / ".hydra" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / f"review-pr-{pr_number}.txt"
        path.write_text(transcript)
        logger.info("Review transcript saved to %s", path, extra={"pr": pr_number})

    async def _has_new_commits(self, worktree_path: Path) -> bool:
        """Check if the reviewer added commits (dirty working tree)."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "git",
                "diff",
                "--cached",
                "--quiet",
                cwd=str(worktree_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            return proc.returncode != 0
        except FileNotFoundError:
            return False
