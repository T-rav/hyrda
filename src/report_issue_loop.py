"""Background worker loop — report issue processing.

Dequeues pending bug reports from state, uploads screenshots, and
invokes the configured CLI agent to create GitHub issues.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Callable, Coroutine
from typing import Any

from agent_cli import build_agent_command
from base_background_loop import BaseBackgroundLoop
from config import HydraFlowConfig
from events import EventBus
from execution import SubprocessRunner
from models import StatusCallback, TranscriptEventData
from pr_manager import PRManager
from runner_utils import stream_claude_process
from screenshot_scanner import scan_base64_for_secrets
from state import StateTracker

logger = logging.getLogger("hydraflow.report_issue_loop")


class ReportIssueLoop(BaseBackgroundLoop):
    """Processes queued bug reports into GitHub issues via the configured agent."""

    _ISSUE_URL_RE = re.compile(r"https://github\.com/[^/\s]+/[^/\s]+/issues/(\d+)")

    def __init__(
        self,
        config: HydraFlowConfig,
        state: StateTracker,
        pr_manager: PRManager,
        event_bus: EventBus,
        stop_event: asyncio.Event,
        status_cb: StatusCallback,
        enabled_cb: Callable[[str], bool],
        sleep_fn: Callable[[int | float], Coroutine[Any, Any, None]],
        interval_cb: Callable[[str], int] | None = None,
        runner: SubprocessRunner | None = None,
    ) -> None:
        super().__init__(
            worker_name="report_issue",
            config=config,
            bus=event_bus,
            stop_event=stop_event,
            status_cb=status_cb,
            enabled_cb=enabled_cb,
            sleep_fn=sleep_fn,
            interval_cb=interval_cb,
        )
        self._state = state
        self._pr_manager = pr_manager
        self._runner = runner
        self._active_procs: set[asyncio.subprocess.Process] = set()

    def _get_default_interval(self) -> int:
        return self._config.report_issue_interval

    async def _do_work(self) -> dict[str, Any] | None:
        if self._config.dry_run:
            return None

        report = self._state.dequeue_report()
        if report is None:
            return None

        # Upload screenshot gist if present (skip if secrets detected)
        screenshot_url = ""
        if report.screenshot_base64:
            secret_hits = (
                scan_base64_for_secrets(report.screenshot_base64)
                if self._config.screenshot_redaction_enabled
                else []
            )
            if secret_hits:
                logger.warning(
                    "Screenshot for report %s contains potential secrets (%s); "
                    "stripping screenshot from report",
                    report.id,
                    ", ".join(secret_hits),
                )
            else:
                screenshot_url = await self._pr_manager.upload_screenshot_gist(
                    report.screenshot_base64
                )

        # Build the enrichment prompt — the agent analyses the raw report,
        # researches the codebase, and files a well-structured issue.
        repo = self._config.repo
        labels_list = list(self._config.planner_label)
        labels = ",".join(labels_list)

        context_parts = [f"User report: {report.description}"]
        if screenshot_url:
            context_parts.append(f"Screenshot: {screenshot_url}")

        env = report.environment
        if env:
            source = env.get("source", "dashboard")
            version = env.get("app_version", "unknown")
            status = env.get("orchestrator_status", "unknown")
            queue_depths = env.get("queue_depths", {})
            queue_line = ", ".join(
                f"{k}={queue_depths.get(k, 0)}"
                for k in ("triage", "plan", "implement", "review")
            )
            context_parts.append(
                f"Environment: version={version}, status={status}, "
                f"queues=[{queue_line}], source={source}"
            )

        raw_context = "\n".join(context_parts)

        prompt = (
            f"A user submitted a bug report from the HydraFlow dashboard. "
            f"Your job is to interpret it, research the codebase, and create "
            f"a well-structured GitHub issue.\n\n"
            f"--- RAW REPORT ---\n{raw_context}\n--- END ---\n\n"
            f"Instructions:\n"
            f"1. Interpret the user's description"
            + (f" and the screenshot at {screenshot_url}" if screenshot_url else "")
            + ".\n"
            f"2. Search the codebase (Grep, Glob, Read) to find the relevant "
            f"files, components, and code paths.\n"
            f"3. Create a GitHub issue with `gh issue create --repo {repo} "
            f'--label "{labels}"` using the structure below.\n\n'
            f"Issue structure:\n"
            f"- **Title**: Short, descriptive (under 70 chars). "
            f"Do NOT just copy the user's raw text.\n"
            f"- **Body** (use --body-file with a temp file):\n"
            f"  ## Problem\n"
            f"  Clear description of what's broken. Include the screenshot "
            f"if available.\n\n"
            f"  ## Current State\n"
            f"  Reference specific files and code found during research.\n\n"
            f"  ## Proposed Solution\n"
            f"  Concrete fix description referencing existing patterns.\n\n"
            f"  ## Scope\n"
            f"  List files/services involved and key integration points.\n\n"
            f"  ## Acceptance Criteria\n"
            f"  - [ ] Checklist of verifiable outcomes\n\n"
            f"The body MUST be at least 200 characters. "
            f"Output the issue URL when done."
        )

        cmd = build_agent_command(
            tool=self._config.report_issue_tool,
            model=self._config.report_issue_model,
            max_turns=10,
        )

        event_data: TranscriptEventData = {
            "source": "report_issue",
        }

        issue_number = 0
        try:
            transcript = await stream_claude_process(
                cmd=cmd,
                prompt=prompt,
                cwd=self._config.repo_root,
                active_procs=self._active_procs,
                event_bus=self._bus,
                event_data=event_data,
                logger=logger,
                runner=self._runner,
                gh_token=self._config.gh_token,
            )
            issue_number = self._extract_issue_number_from_transcript(transcript)
        except Exception:
            logger.exception("Report issue agent failed for report %s", report.id)

        # Reliability guard: if the agent didn't create the issue, fall back
        # to a basic gh issue create via PRManager.
        fallback_title = f"[Bug Report] {report.description[:100]}"
        if issue_number <= 0:
            fallback_body = f"## Bug Report\n\n{report.description}"
            if screenshot_url:
                fallback_body += f"\n\n![Screenshot]({screenshot_url})"
            issue_number = await self._pr_manager.create_issue(
                fallback_title, fallback_body, labels_list
            )
        if issue_number <= 0:
            logger.error(
                "Report %s failed: issue was not created via agent or fallback",
                report.id,
            )
            return {"processed": 0, "report_id": report.id, "error": True}

        logger.info(
            "Processed report %s as issue #%d: %s",
            report.id,
            issue_number,
            fallback_title,
        )
        return {"processed": 1, "report_id": report.id, "issue_number": issue_number}

    @classmethod
    def _extract_issue_number_from_transcript(cls, transcript: str) -> int:
        """Return issue number parsed from transcript output, or 0 when absent."""
        match = cls._ISSUE_URL_RE.search(transcript or "")
        if not match:
            return 0
        try:
            return int(match.group(1))
        except ValueError:
            return 0
