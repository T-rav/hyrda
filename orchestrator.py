"""Main orchestrator loop — plan, implement, review, cleanup, repeat."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from agent import AgentRunner
from config import HydraConfig
from events import EventBus, EventType, HydraEvent
from implement_phase import ImplementPhase
from issue_fetcher import IssueFetcher
from models import (
    GitHubIssue,
    Phase,
    PlanResult,
)
from planner import PlannerRunner
from pr_manager import PRManager
from review_phase import ReviewPhase
from reviewer import ReviewRunner
from state import StateTracker
from triage import TriageRunner
from worktree import WorktreeManager

logger = logging.getLogger("hydra.orchestrator")


class HydraOrchestrator:
    """Coordinates the full Hydra pipeline.

    Each phase runs as an independent polling loop so new work is picked
    up continuously — planner, implementer, and reviewer all run
    concurrently without waiting on each other.
    """

    def __init__(
        self,
        config: HydraConfig,
        event_bus: EventBus | None = None,
        state: StateTracker | None = None,
    ) -> None:
        self._config = config
        self._bus = event_bus or EventBus()
        self._state = state or StateTracker(config.state_file)
        self._worktrees = WorktreeManager(config)
        self._agents = AgentRunner(config, self._bus)
        self._planners = PlannerRunner(config, self._bus)
        self._prs = PRManager(config, self._bus)
        self._reviewers = ReviewRunner(config, self._bus)
        self._triage = TriageRunner(config, self._bus)
        self._dashboard: object | None = None
        # Pending human-input requests: {issue_number: question}
        self._human_input_requests: dict[int, str] = {}
        # Fulfilled human-input responses: {issue_number: answer}
        self._human_input_responses: dict[int, str] = {}
        # In-memory tracking of issues active in this run (avoids double-processing)
        self._active_issues: set[int] = set()
        # HITL corrections: {issue_number: correction_text}
        self._hitl_corrections: dict[int, str] = {}
        # Stop mechanism for dashboard control
        self._stop_event = asyncio.Event()
        self._running = False

        # Delegate phases to focused modules
        self._fetcher = IssueFetcher(config)
        self._implementer = ImplementPhase(
            config,
            self._state,
            self._worktrees,
            self._agents,
            self._prs,
            self._fetcher,
            self._stop_event,
            self._active_issues,
        )
        self._reviewer = ReviewPhase(
            config,
            self._state,
            self._worktrees,
            self._reviewers,
            self._prs,
            self._stop_event,
            self._active_issues,
            agents=self._agents,
            event_bus=self._bus,
        )

    @property
    def event_bus(self) -> EventBus:
        """Expose event bus for dashboard integration."""
        return self._bus

    @property
    def state(self) -> StateTracker:
        """Expose state for dashboard integration."""
        return self._state

    @property
    def running(self) -> bool:
        """Whether the orchestrator is currently executing."""
        return self._running

    @property
    def run_status(self) -> str:
        """Return the current lifecycle status: idle, running, stopping, or done."""
        if self._stop_event.is_set() and self._running:
            return "stopping"
        if self._running:
            return "running"
        # Check if we finished naturally (DONE phase in history)
        for event in reversed(self._bus.get_history()):
            if (
                event.type == EventType.PHASE_CHANGE
                and event.data.get("phase") == Phase.DONE.value
            ):
                return "done"
        return "idle"

    @property
    def human_input_requests(self) -> dict[int, str]:
        """Pending questions for the human operator."""
        return self._human_input_requests

    def provide_human_input(self, issue_number: int, answer: str) -> None:
        """Provide an answer to a paused agent's question."""
        self._human_input_responses[issue_number] = answer
        self._human_input_requests.pop(issue_number, None)

    def submit_hitl_correction(self, issue_number: int, correction: str) -> None:
        """Store a correction for a HITL issue to guide retry."""
        self._hitl_corrections[issue_number] = correction

    def get_hitl_status(self, issue_number: int) -> str:
        """Return the HITL status for an issue: processing if active, else pending."""
        if issue_number in self._active_issues:
            return "processing"
        return "pending"

    def skip_hitl_issue(self, issue_number: int) -> None:
        """Remove an issue from HITL tracking."""
        self._hitl_corrections.pop(issue_number, None)

    async def stop(self) -> None:
        """Signal the orchestrator to stop and kill active subprocesses."""
        self._stop_event.set()
        logger.info("Stop requested — terminating active processes")
        self._planners.terminate()
        self._agents.terminate()
        self._reviewers.terminate()
        await self._publish_status()

    # Alias for backward compatibility
    request_stop = stop

    def reset(self) -> None:
        """Reset the stop event so the orchestrator can be started again."""
        self._stop_event.clear()
        self._running = False
        self._active_issues.clear()

    async def _publish_status(self) -> None:
        """Broadcast the current orchestrator status to all subscribers."""
        await self._bus.publish(
            HydraEvent(
                type=EventType.ORCHESTRATOR_STATUS,
                data={"status": self.run_status},
            )
        )

    async def run(self) -> None:
        """Run three independent, continuous loops — plan, implement, review.

        Each loop polls for its own work on ``poll_interval`` and processes
        whatever it finds.  No phase blocks another; new issues are picked
        up as soon as they arrive.  Loops run until explicitly stopped.
        """
        self._stop_event.clear()
        self._running = True
        await self._publish_status()
        logger.info(
            "Hydra starting — repo=%s label=%s workers=%d poll=%ds",
            self._config.repo,
            ",".join(self._config.ready_label),
            self._config.max_workers,
            self._config.poll_interval,
        )

        await self._prs.ensure_labels_exist()

        try:
            await self._supervise_loops()
        finally:
            self._running = False
            self._planners.terminate()
            self._agents.terminate()
            self._reviewers.terminate()
            await self._publish_status()
            logger.info("Hydra stopped")

    async def _supervise_loops(self) -> None:
        """Run all four loops, restarting any that crash unexpectedly."""
        loop_factories: list[tuple[str, Callable[[], Coroutine[Any, Any, None]]]] = [
            ("triage", self._triage_loop),
            ("plan", self._plan_loop),
            ("implement", self._implement_loop),
            ("review", self._review_loop),
        ]
        tasks: dict[str, asyncio.Task[None]] = {}
        for name, factory in loop_factories:
            tasks[name] = asyncio.create_task(factory(), name=f"hydra-{name}")

        try:
            while not self._stop_event.is_set():
                done, _ = await asyncio.wait(
                    tasks.values(), return_when=asyncio.FIRST_COMPLETED
                )
                for task in done:
                    name = task.get_name().removeprefix("hydra-")
                    if self._stop_event.is_set():
                        break
                    exc = task.exception()
                    if exc is not None:
                        logger.error("Loop %r crashed — restarting: %s", name, exc)
                        await self._bus.publish(
                            HydraEvent(
                                type=EventType.ERROR,
                                data={
                                    "message": f"Loop {name} crashed and was restarted",
                                    "source": name,
                                },
                            )
                        )
                        factory_fn = dict(loop_factories)[name]
                        tasks[name] = asyncio.create_task(
                            factory_fn(), name=f"hydra-{name}"
                        )
        finally:
            for task in tasks.values():
                task.cancel()
            await asyncio.gather(*tasks.values(), return_exceptions=True)

    async def _triage_loop(self) -> None:
        """Continuously poll for find-labeled issues and triage them."""
        while not self._stop_event.is_set():
            try:
                await self._triage_find_issues()
            except Exception:
                logger.exception("Triage loop iteration failed — will retry next cycle")
                await self._bus.publish(
                    HydraEvent(
                        type=EventType.ERROR,
                        data={"message": "Triage loop error", "source": "triage"},
                    )
                )
            await self._sleep_or_stop(self._config.poll_interval)

    async def _plan_loop(self) -> None:
        """Continuously poll for planner-labeled issues."""
        while not self._stop_event.is_set():
            try:
                await self._triage_find_issues()
                await self._plan_issues()
            except Exception:
                logger.exception("Plan loop iteration failed — will retry next cycle")
                await self._bus.publish(
                    HydraEvent(
                        type=EventType.ERROR,
                        data={"message": "Plan loop error", "source": "plan"},
                    )
                )
            await self._sleep_or_stop(self._config.poll_interval)

    async def _implement_loop(self) -> None:
        """Continuously poll for ``hydra-ready`` issues and implement them."""
        while not self._stop_event.is_set():
            try:
                await self._implementer.run_batch()
            except Exception:
                logger.exception(
                    "Implement loop iteration failed — will retry next cycle"
                )
                await self._bus.publish(
                    HydraEvent(
                        type=EventType.ERROR,
                        data={"message": "Implement loop error", "source": "implement"},
                    )
                )
            await self._sleep_or_stop(self._config.poll_interval)

    async def _review_loop(self) -> None:
        """Continuously poll for ``hydra-review`` issues and review their PRs."""
        while not self._stop_event.is_set():
            try:
                prs, issues = await self._fetcher.fetch_reviewable_prs(
                    self._active_issues
                )
                if prs:
                    review_results = await self._reviewer.review_prs(prs, issues)
                    any_merged = any(r.merged for r in review_results)
                    if any_merged:
                        await asyncio.sleep(5)
                        await self._prs.pull_main()
            except Exception:
                logger.exception("Review loop iteration failed — will retry next cycle")
                await self._bus.publish(
                    HydraEvent(
                        type=EventType.ERROR,
                        data={"message": "Review loop error", "source": "review"},
                    )
                )
            await self._sleep_or_stop(self._config.poll_interval)

    async def _sleep_or_stop(self, seconds: int) -> None:
        """Sleep for *seconds*, waking early if stop is requested."""
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._stop_event.wait(), timeout=seconds)

    # --- Phase implementations (triage + plan remain here) ---

    async def _triage_find_issues(self) -> None:
        """Evaluate ``find_label`` issues and route them.

        Issues with enough context go to ``planner_label`` (planning).
        Issues lacking detail are escalated to ``hitl_label`` with a
        comment explaining what is missing so the dashboard surfaces
        them as "needs attention".
        """
        if not self._config.find_label:
            return

        issues = await self._fetcher.fetch_issues_by_labels(
            self._config.find_label, self._config.batch_size
        )
        if not issues:
            return

        logger.info("Triaging %d found issues", len(issues))
        for issue in issues:
            if self._stop_event.is_set():
                logger.info("Stop requested — aborting triage loop")
                return

            result = await self._triage.evaluate(issue)

            if self._config.dry_run:
                continue

            # Remove find label regardless of outcome
            for lbl in self._config.find_label:
                await self._prs.remove_label(issue.number, lbl)

            if result.ready:
                await self._prs.add_labels(
                    issue.number, [self._config.planner_label[0]]
                )
                logger.info(
                    "Issue #%d triaged → %s (ready for planning)",
                    issue.number,
                    self._config.planner_label[0],
                )
            else:
                self._state.set_hitl_origin(issue.number, self._config.find_label[0])
                await self._prs.add_labels(issue.number, [self._config.hitl_label[0]])
                note = (
                    "## Needs More Information\n\n"
                    "This issue was picked up by Hydra but doesn't have "
                    "enough detail to begin planning.\n\n"
                    "**Missing:**\n"
                    + "\n".join(f"- {r}" for r in result.reasons)
                    + "\n\n"
                    "Please update the issue with more context and re-apply "
                    f"the `{self._config.find_label[0]}` label when ready.\n\n"
                    "---\n*Generated by Hydra Triage*"
                )
                await self._prs.post_comment(issue.number, note)
                await self._bus.publish(
                    HydraEvent(
                        type=EventType.HITL_UPDATE,
                        data={
                            "issue": issue.number,
                            "action": "escalated",
                        },
                    )
                )
                logger.info(
                    "Issue #%d triaged → %s (needs attention: %s)",
                    issue.number,
                    self._config.hitl_label[0],
                    "; ".join(result.reasons),
                )

    async def _plan_issues(self) -> list[PlanResult]:
        """Run planning agents on issues labeled with the planner label."""
        issues = await self._fetcher.fetch_plan_issues()
        if not issues:
            return []

        semaphore = asyncio.Semaphore(self._config.max_planners)
        results: list[PlanResult] = []

        async def _plan_one(idx: int, issue: GitHubIssue) -> PlanResult:
            if self._stop_event.is_set():
                return PlanResult(issue_number=issue.number, error="stopped")

            async with semaphore:
                if self._stop_event.is_set():
                    return PlanResult(issue_number=issue.number, error="stopped")

                result = await self._planners.plan(issue, worker_id=idx)

                if result.success and result.plan:
                    # Post plan + branch as comment on the issue
                    branch = self._config.branch_for_issue(issue.number)
                    comment_body = (
                        f"## Implementation Plan\n\n"
                        f"{result.plan}\n\n"
                        f"**Branch:** `{branch}`\n\n"
                        f"---\n"
                        f"*Generated by Hydra Planner*"
                    )
                    await self._prs.post_comment(issue.number, comment_body)

                    # Swap labels: remove planner label(s), add implementation label
                    for lbl in self._config.planner_label:
                        await self._prs.remove_label(issue.number, lbl)
                    await self._prs.add_labels(
                        issue.number, [self._config.ready_label[0]]
                    )

                    # File new issues discovered during planning
                    for new_issue in result.new_issues:
                        if len(new_issue.body) < 50:
                            logger.warning(
                                "Skipping discovered issue %r — body too short "
                                "(%d chars, need ≥50)",
                                new_issue.title,
                                len(new_issue.body),
                            )
                            continue
                        labels = new_issue.labels or (
                            [self._config.planner_label[0]]
                            if self._config.planner_label
                            else []
                        )
                        await self._prs.create_issue(
                            new_issue.title, new_issue.body, labels
                        )
                        self._state.record_issue_created()

                    logger.info(
                        "Plan posted and labels swapped for issue #%d",
                        issue.number,
                    )
                else:
                    logger.warning(
                        "Planning failed for issue #%d — skipping label swap",
                        issue.number,
                    )

                return result

        all_tasks = [
            asyncio.create_task(_plan_one(i, issue)) for i, issue in enumerate(issues)
        ]
        for task in asyncio.as_completed(all_tasks):
            results.append(await task)
            # Cancel remaining tasks if stop requested
            if self._stop_event.is_set():
                for t in all_tasks:
                    t.cancel()
                break

        return results

    async def _set_phase(self, phase: Phase) -> None:
        """Update the current phase and broadcast."""
        logger.info("Phase: %s", phase.value)
        await self._bus.publish(
            HydraEvent(
                type=EventType.PHASE_CHANGE,
                data={"phase": phase.value},
            )
        )
