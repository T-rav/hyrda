"""Planning agent runner — launches Claude Code to explore and plan issue implementation."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from pathlib import Path

from config import HydraConfig
from events import EventBus, EventType, HydraEvent
from models import GitHubIssue, NewIssueSpec, PlannerStatus, PlanResult
from runner_utils import stream_claude_process, terminate_processes

logger = logging.getLogger("hydra.planner")


class PlannerRunner:
    """Launches a ``claude -p`` process to explore the codebase and create an implementation plan.

    The planner works READ-ONLY against the repo root (no worktree needed).
    It produces a structured plan that is posted as a comment on the issue.
    """

    def __init__(self, config: HydraConfig, event_bus: EventBus) -> None:
        self._config = config
        self._bus = event_bus
        self._active_procs: set[asyncio.subprocess.Process] = set()

    async def plan(
        self,
        issue: GitHubIssue,
        worker_id: int = 0,
    ) -> PlanResult:
        """Run the planning agent for *issue*.

        Returns a :class:`PlanResult` with the plan and summary.
        """
        start = time.monotonic()
        result = PlanResult(issue_number=issue.number)

        await self._emit_status(issue.number, worker_id, PlannerStatus.PLANNING)

        if self._config.dry_run:
            logger.info("[dry-run] Would plan issue #%d", issue.number)
            result.success = True
            result.summary = "Dry-run: plan skipped"
            result.duration_seconds = time.monotonic() - start
            await self._emit_status(issue.number, worker_id, PlannerStatus.DONE)
            return result

        try:
            cmd = self._build_command()
            prompt = self._build_prompt(issue)
            transcript = await self._execute(
                cmd, prompt, self._config.repo_root, issue.number
            )
            result.transcript = transcript

            result.plan = self._extract_plan(transcript)
            result.summary = self._extract_summary(transcript)
            result.new_issues = self._extract_new_issues(transcript)
            if result.plan:
                self._validate_plan(issue, result.plan)
            result.success = bool(result.plan)

            status = PlannerStatus.DONE if result.success else PlannerStatus.FAILED
            await self._emit_status(issue.number, worker_id, status)

        except Exception as exc:
            result.success = False
            result.error = str(exc)
            logger.error(
                "Planner failed for issue #%d: %s",
                issue.number,
                exc,
                extra={"issue": issue.number},
            )
            await self._emit_status(issue.number, worker_id, PlannerStatus.FAILED)

        result.duration_seconds = time.monotonic() - start
        self._save_transcript(issue.number, result.transcript)
        if result.success and result.plan:
            self._save_plan(issue.number, result.plan, result.summary)
        return result

    def _build_command(self) -> list[str]:
        """Construct the ``claude`` CLI invocation for planning."""
        cmd = [
            "claude",
            "-p",
            "--output-format",
            "stream-json",
            "--model",
            self._config.planner_model,
            "--verbose",
            "--permission-mode",
            "bypassPermissions",
            "--disallowedTools",
            "Write,Edit,NotebookEdit",
        ]
        if self._config.planner_budget_usd > 0:
            cmd.extend(["--max-budget-usd", str(self._config.planner_budget_usd)])
        return cmd

    # Maximum characters for issue body and comments in the prompt.
    # Keep conservative to avoid hitting Claude CLI's internal text-splitter
    # limits (RecursiveCharacterTextSplitter fails on very long unsplittable lines).
    _MAX_BODY_CHARS = 4_000
    _MAX_COMMENT_CHARS = 1_000
    _MAX_LINE_CHARS = 500

    @staticmethod
    def _truncate_text(text: str, char_limit: int, line_limit: int) -> str:
        """Truncate *text* at a line boundary, also breaking long lines.

        Lines exceeding *line_limit* are hard-truncated to avoid producing
        unsplittable chunks that crash Claude CLI's text splitter.
        """
        lines: list[str] = []
        total = 0
        for raw_line in text.splitlines():
            capped = (
                raw_line[:line_limit] + "…" if len(raw_line) > line_limit else raw_line
            )
            if total + len(capped) + 1 > char_limit:
                break
            lines.append(capped)
            total += len(capped) + 1  # +1 for newline
        result = "\n".join(lines)
        if len(result) < len(text):
            result += "\n\n…(truncated)"
        return result

    def _build_prompt(self, issue: GitHubIssue) -> str:
        """Build the planning prompt for the agent."""
        comments_section = ""
        if issue.comments:
            truncated = [
                self._truncate_text(c, self._MAX_COMMENT_CHARS, self._MAX_LINE_CHARS)
                for c in issue.comments
            ]
            formatted = "\n".join(f"- {c}" for c in truncated)
            comments_section = f"\n\n## Discussion\n{formatted}"

        body = self._truncate_text(
            issue.body or "", self._MAX_BODY_CHARS, self._MAX_LINE_CHARS
        )

        find_label = (
            self._config.find_label[0] if self._config.find_label else "hydra-find"
        )

        return f"""You are a planning agent for GitHub issue #{issue.number}.

## Issue: {issue.title}

{body}{comments_section}

## Instructions

You are in READ-ONLY mode. Do NOT create, modify, or delete any files.
Do NOT run any commands that change state (no git commit, no file writes, no installs).

Your job is to explore the codebase and create a detailed implementation plan.

## Exploration Strategy — USE SEMANTIC TOOLS

You have access to powerful semantic navigation tools. Use them instead of grep:

1. **claude-context (search_code)** — Semantic code search. Use this FIRST to find
   relevant code by describing what you're looking for in natural language.
   Example: search for "authentication middleware" or "database connection pool".

2. **claude-context (index_codebase)** — If search_code returns an error about
   missing index, index the codebase first, then search.

3. **cclsp (find_definition)** — Jump to the definition of any symbol (function, class, variable).
4. **cclsp (find_references)** — Find all callers/usages of a symbol across the workspace.
5. **cclsp (find_implementation)** — Find implementations of an interface or abstract method.
6. **cclsp (get_incoming_calls)** — Find what calls a given function.
7. **cclsp (get_outgoing_calls)** — Find what a function calls.
8. **cclsp (find_workspace_symbols)** — Search for symbols by name across the workspace.

Use these tools to build a deep understanding of the code:
- Start with `search_code` to find relevant areas
- Use `find_definition` and `find_references` to trace through the code
- Use `get_incoming_calls` / `get_outgoing_calls` to understand call graphs
- Only fall back to Grep for simple text pattern matching

## Planning Steps

1. Read the issue carefully and understand what needs to be done.
2. Restate what the issue asks for before diving into details — this ensures your plan stays on target.
3. Use semantic search and LSP navigation to explore the relevant code.
4. Identify what needs to change and where.
5. Consider testing strategy (what tests to write, what to mock).
6. Consider edge cases and potential pitfalls.

## Required Output

Output your plan between these exact markers:

PLAN_START
<your detailed implementation plan here>
PLAN_END

Then provide a one-line summary:
SUMMARY: <brief one-line description of the plan>

## Plan Format

Your plan should include:
- **Files to modify** — list each file and what changes are needed
- **New files** — if any new files are needed, describe their purpose
- **Implementation steps** — ordered steps for the implementer to follow
- **Testing strategy** — what tests to write and what to verify
- **Key considerations** — edge cases, backward compatibility, dependencies

## Optional: Discovered Issues

If you discover bugs, tech debt, or out-of-scope work during exploration,
you can file them as new GitHub issues using these markers:

NEW_ISSUES_START
- title: Short issue title
  body: Description of the issue
  labels: {find_label}
- title: Another issue
  body: Another description
  labels: {find_label}
NEW_ISSUES_END

Only include this section if you actually discover issues worth filing.

**IMPORTANT:** You MUST only use the following label for new issues: `{find_label}`
Do NOT invent labels. All discovered issues enter the pipeline via the find label.
"""

    @staticmethod
    def _significant_words(text: str, min_length: int = 4) -> set[str]:
        """Return lowercase words from *text* that are at least *min_length* chars.

        Filters out common stop words to focus on meaningful terms.
        """
        stop = {
            "this",
            "that",
            "with",
            "from",
            "have",
            "been",
            "will",
            "should",
            "would",
            "could",
            "about",
            "into",
            "when",
            "them",
            "then",
            "than",
            "also",
            "more",
            "some",
            "only",
            "each",
            "make",
            "like",
            "need",
            "does",
        }
        words = set()
        for w in re.findall(r"[a-zA-Z]+", text.lower()):
            if len(w) >= min_length and w not in stop:
                words.add(w)
        return words

    def _validate_plan(self, issue: GitHubIssue, plan: str) -> bool:
        """Soft-validate that *plan* addresses *issue*.

        Checks that at least one significant word from the issue title
        appears in the plan text. Logs a warning on mismatch but does
        **not** reject the plan.
        """
        title_words = self._significant_words(issue.title)
        plan_words = self._significant_words(plan)
        overlap = title_words & plan_words
        if not overlap and title_words:
            logger.warning(
                "Plan for issue #%d may not address the issue title %r "
                "(no significant word overlap)",
                issue.number,
                issue.title,
            )
            return False
        return True

    def _extract_plan(self, transcript: str) -> str:
        """Extract the plan from between PLAN_START/PLAN_END markers.

        Returns an empty string when the markers are absent — this prevents
        error output (e.g. budget-exceeded messages) from being treated as
        a valid plan.
        """
        pattern = r"PLAN_START\s*\n(.*?)\nPLAN_END"
        match = re.search(pattern, transcript, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""

    def _extract_summary(self, transcript: str) -> str:
        """Extract the summary line from the planner transcript."""
        pattern = r"SUMMARY:\s*(.+)"
        match = re.search(pattern, transcript, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        # Fallback: last non-empty line
        lines = [ln.strip() for ln in transcript.splitlines() if ln.strip()]
        return lines[-1][:200] if lines else "No summary provided"

    @staticmethod
    def _extract_new_issues(transcript: str) -> list[NewIssueSpec]:
        """Parse NEW_ISSUES_START/NEW_ISSUES_END markers into issue specs."""
        pattern = r"NEW_ISSUES_START\s*\n(.*?)\nNEW_ISSUES_END"
        match = re.search(pattern, transcript, re.DOTALL)
        if not match:
            return []

        block = match.group(1)
        issues: list[NewIssueSpec] = []
        current: dict[str, str] = {}

        for line in block.splitlines():
            stripped = line.strip()
            if stripped.startswith("- title:"):
                if current.get("title"):
                    issues.append(
                        NewIssueSpec(
                            title=current["title"],
                            body=current.get("body", ""),
                            labels=[
                                lbl.strip()
                                for lbl in current.get("labels", "").split(",")
                                if lbl.strip()
                            ],
                        )
                    )
                current = {"title": stripped[len("- title:") :].strip()}
            elif stripped.startswith("body:"):
                current["body"] = stripped[len("body:") :].strip()
            elif stripped.startswith("labels:"):
                current["labels"] = stripped[len("labels:") :].strip()

        # Don't forget the last entry
        if current.get("title"):
            issues.append(
                NewIssueSpec(
                    title=current["title"],
                    body=current.get("body", ""),
                    labels=[
                        lbl.strip()
                        for lbl in current.get("labels", "").split(",")
                        if lbl.strip()
                    ],
                )
            )

        return issues

    def terminate(self) -> None:
        """Kill all active planner subprocesses."""
        terminate_processes(self._active_procs)

    async def _execute(
        self,
        cmd: list[str],
        prompt: str,
        cwd: Path,
        issue_number: int,
    ) -> str:
        """Run the claude planning process."""

        def _check_plan_complete(accumulated: str) -> bool:
            if "PLAN_END" in accumulated:
                logger.info(
                    "Plan markers found for issue #%d — terminating planner",
                    issue_number,
                )
                return True
            return False

        return await stream_claude_process(
            cmd=cmd,
            prompt=prompt,
            cwd=cwd,
            active_procs=self._active_procs,
            event_bus=self._bus,
            event_data={"issue": issue_number, "source": "planner"},
            logger=logger,
            on_output=_check_plan_complete,
        )

    async def _emit_status(
        self, issue_number: int, worker_id: int, status: PlannerStatus
    ) -> None:
        """Publish a planner status event."""
        await self._bus.publish(
            HydraEvent(
                type=EventType.PLANNER_UPDATE,
                data={
                    "issue": issue_number,
                    "worker": worker_id,
                    "status": status.value,
                    "role": "planner",
                },
            )
        )

    def _save_transcript(self, issue_number: int, transcript: str) -> None:
        """Write the planning transcript to .hydra/logs/ for post-mortem review."""
        log_dir = self._config.repo_root / ".hydra" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / f"plan-issue-{issue_number}.txt"
        path.write_text(transcript)
        logger.info("Plan transcript saved to %s", path, extra={"issue": issue_number})

    def _save_plan(self, issue_number: int, plan: str, summary: str) -> None:
        """Write the extracted plan to .hydra/plans/ for the implementation worker."""
        plan_dir = self._config.repo_root / ".hydra" / "plans"
        plan_dir.mkdir(parents=True, exist_ok=True)
        path = plan_dir / f"issue-{issue_number}.md"
        path.write_text(
            f"# Plan for Issue #{issue_number}\n\n{plan}\n\n---\n**Summary:** {summary}\n"
        )
        logger.info("Plan saved to %s", path, extra={"issue": issue_number})
