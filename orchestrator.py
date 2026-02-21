"""Main orchestrator loop — plan, implement, review, cleanup, repeat."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from agent import AgentRunner
from analysis import PlanAnalyzer
from config import HydraConfig
from events import EventBus, EventType, HydraEvent
from hitl_runner import HITLRunner
from implement_phase import ImplementPhase
from issue_fetcher import IssueFetcher
from models import (
    GitHubIssue,
    Phase,
    PlanResult,
)
from planner import PlannerRunner
from pr_manager import PRManager
from retrospective import RetrospectiveCollector
from review_phase import ReviewPhase
from reviewer import ReviewRunner
from state import StateTracker
from subprocess_util import AuthenticationError
from triage import TriageRunner
from worktree import WorktreeManager

logger = logging.getLogger("hydra.orchestrator")

_HITL_ORIGIN_DISPLAY: dict[str, str] = {
    "hydra-find": "from triage",
    "hydra-plan": "from plan",
    "hydra-ready": "from implement",
    "hydra-review": "from review",
}


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
        self._hitl_runner = HITLRunner(config, self._bus)
        self._triage = TriageRunner(config, self._bus)
        self._dashboard: object | None = None
        # Pending human-input requests: {issue_number: question}
        self._human_input_requests: dict[int, str] = {}
        # Fulfilled human-input responses: {issue_number: answer}
        self._human_input_responses: dict[int, str] = {}
        # In-memory tracking of issues active per phase (avoids double-processing)
        self._active_impl_issues: set[int] = set()
        self._active_review_issues: set[int] = set()
        self._active_hitl_issues: set[int] = set()
        # Issues recovered from persisted state on startup (one-cycle grace period)
        self._recovered_issues: set[int] = set()
        # HITL corrections: {issue_number: correction_text}
        self._hitl_corrections: dict[int, str] = {}
        # Stop mechanism for dashboard control
        self._stop_event = asyncio.Event()
        self._running = False
        # Background worker last-known status: {worker_name: status dict}
        self._bg_worker_states: dict[str, dict[str, Any]] = {}
        # Auth failure flag — set when a loop crashes due to AuthenticationError
        self._auth_failed = False

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
            self._active_impl_issues,
        )
        self._retrospective = RetrospectiveCollector(config, self._state, self._prs)
        self._reviewer = ReviewPhase(
            config,
            self._state,
            self._worktrees,
            self._reviewers,
            self._prs,
            self._stop_event,
            self._active_review_issues,
            agents=self._agents,
            event_bus=self._bus,
            retrospective=self._retrospective,
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

    def _has_active_processes(self) -> bool:
        """Return True if any runner pool still has live subprocesses."""
        return bool(
            self._planners._active_procs
            or self._agents._active_procs
            or self._reviewers._active_procs
            or self._hitl_runner._active_procs
        )

    @property
    def run_status(self) -> str:
        """Return the current lifecycle status: idle, running, stopping, auth_failed, or done."""
        if self._auth_failed:
            return "auth_failed"
        if self._stop_event.is_set() and (
            self._running or self._has_active_processes()
        ):
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
        """Return the HITL status for an issue.

        Returns ``"processing"`` for actively-running issues, or a
        human-readable origin label (e.g. ``"from review"``) for items
        waiting on human action.  Falls back to ``"pending"`` when no
        origin data is available.
        """
        if (
            issue_number in self._active_impl_issues
            or issue_number in self._active_review_issues
            or issue_number in self._active_hitl_issues
        ):
            return "processing"
        origin = self._state.get_hitl_origin(issue_number)
        if origin:
            return _HITL_ORIGIN_DISPLAY.get(origin, "pending")
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
        self._hitl_runner.terminate()
        await self._publish_status()

    # Alias for backward compatibility
    request_stop = stop

    def reset(self) -> None:
        """Reset the stop event so the orchestrator can be started again."""
        self._stop_event.clear()
        self._running = False
        self._auth_failed = False
        self._active_impl_issues.clear()
        self._active_review_issues.clear()
        self._active_hitl_issues.clear()

    def update_bg_worker_status(
        self, name: str, status: str, details: dict[str, Any] | None = None
    ) -> None:
        """Record the latest heartbeat from a background worker."""
        from datetime import UTC, datetime

        self._bg_worker_states[name] = {
            "name": name,
            "status": status,
            "last_run": datetime.now(UTC).isoformat(),
            "details": details or {},
        }

    def get_bg_worker_states(self) -> dict[str, dict[str, Any]]:
        """Return a copy of all background worker states."""
        return dict(self._bg_worker_states)

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

        # Restore active issues from persisted state for crash recovery
        recovered = set(self._state.get_active_issue_numbers())
        if recovered:
            self._recovered_issues = recovered
            # Add to implementation active set so they're skipped for one poll cycle
            self._active_impl_issues.update(recovered)
            logger.info(
                "Crash recovery: loaded %d active issue(s) from state: %s",
                len(recovered),
                recovered,
            )

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
            self._planners.terminate()
            self._agents.terminate()
            self._reviewers.terminate()
            self._hitl_runner.terminate()
            await asyncio.sleep(0)
            self._running = False
            await self._publish_status()
            logger.info("Hydra stopped")

    async def _supervise_loops(self) -> None:
        """Run all five loops, restarting any that crash unexpectedly."""
        loop_factories: list[tuple[str, Callable[[], Coroutine[Any, Any, None]]]] = [
            ("triage", self._triage_loop),
            ("plan", self._plan_loop),
            ("implement", self._implement_loop),
            ("review", self._review_loop),
            ("hitl", self._hitl_loop),
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
                        if isinstance(exc, AuthenticationError):
                            logger.error(
                                "GitHub authentication failed in %r — "
                                "pausing all loops: %s",
                                name,
                                exc,
                            )
                            self._auth_failed = True
                            await self._bus.publish(
                                HydraEvent(
                                    type=EventType.SYSTEM_ALERT,
                                    data={
                                        "message": (
                                            "GitHub authentication failed. "
                                            "Check your gh token and restart."
                                        ),
                                        "source": name,
                                    },
                                )
                            )
                            self._stop_event.set()
                            break

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
            except AuthenticationError:
                raise
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
                await self._plan_issues()
            except AuthenticationError:
                raise
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
            # After one poll cycle, release crash-recovered issues
            if self._recovered_issues:
                self._active_impl_issues -= self._recovered_issues
                self._recovered_issues.clear()
                self._state.set_active_issue_numbers(
                    list(
                        self._active_impl_issues
                        | self._active_review_issues
                        | self._active_hitl_issues
                    )
                )
            try:
                await self._implementer.run_batch()
            except AuthenticationError:
                raise
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
                    self._active_review_issues
                )
                if prs:
                    review_results = await self._reviewer.review_prs(prs, issues)
                    any_merged = any(r.merged for r in review_results)
                    if any_merged:
                        await asyncio.sleep(5)
                        await self._prs.pull_main()
            except AuthenticationError:
                raise
            except Exception:
                logger.exception("Review loop iteration failed — will retry next cycle")
                await self._bus.publish(
                    HydraEvent(
                        type=EventType.ERROR,
                        data={"message": "Review loop error", "source": "review"},
                    )
                )
            await self._sleep_or_stop(self._config.poll_interval)

    async def _hitl_loop(self) -> None:
        """Continuously process HITL corrections submitted via the dashboard."""
        while not self._stop_event.is_set():
            try:
                await self._process_hitl_corrections()
            except AuthenticationError:
                raise
            except Exception:
                logger.exception("HITL loop iteration failed — will retry next cycle")
                await self._bus.publish(
                    HydraEvent(
                        type=EventType.ERROR,
                        data={"message": "HITL loop error", "source": "hitl"},
                    )
                )
            await self._sleep_or_stop(self._config.poll_interval)

    async def _process_hitl_corrections(self) -> None:
        """Process all pending HITL corrections."""
        if not self._hitl_corrections:
            return

        semaphore = asyncio.Semaphore(self._config.max_hitl_workers)

        # Snapshot and clear pending corrections to avoid re-processing
        pending = dict(self._hitl_corrections)
        for issue_number in pending:
            self._hitl_corrections.pop(issue_number, None)

        tasks = [
            asyncio.create_task(
                self._process_one_hitl(issue_number, correction, semaphore)
            )
            for issue_number, correction in pending.items()
        ]

        for task in asyncio.as_completed(tasks):
            await task
            if self._stop_event.is_set():
                for t in tasks:
                    t.cancel()
                break

    async def _process_one_hitl(
        self,
        issue_number: int,
        correction: str,
        semaphore: asyncio.Semaphore,
    ) -> None:
        """Process a single HITL correction for *issue_number*."""
        async with semaphore:
            if self._stop_event.is_set():
                return

            self._active_hitl_issues.add(issue_number)
            self._state.set_active_issue_numbers(
                list(
                    self._active_impl_issues
                    | self._active_review_issues
                    | self._active_hitl_issues
                )
            )
            try:
                issue = await self._fetcher.fetch_issue_by_number(issue_number)
                if not issue:
                    logger.warning(
                        "Could not fetch issue #%d for HITL correction",
                        issue_number,
                    )
                    return

                cause = self._state.get_hitl_cause(issue_number) or "Unknown escalation"
                origin = self._state.get_hitl_origin(issue_number)

                # Get or create worktree
                branch = self._config.branch_for_issue(issue_number)
                wt_path = self._config.worktree_path_for_issue(issue_number)
                if not wt_path.is_dir():
                    wt_path = await self._worktrees.create(issue_number, branch)
                self._state.set_worktree(issue_number, str(wt_path))

                # Swap to active label
                for lbl in self._config.hitl_label:
                    await self._prs.remove_label(issue_number, lbl)
                await self._prs.add_labels(
                    issue_number, [self._config.hitl_active_label[0]]
                )

                result = await self._hitl_runner.run(issue, correction, cause, wt_path)

                # Remove active label
                for lbl in self._config.hitl_active_label:
                    await self._prs.remove_label(issue_number, lbl)

                if result.success:
                    await self._prs.push_branch(wt_path, branch)

                    if origin:
                        await self._prs.add_labels(issue_number, [origin])

                    self._state.remove_hitl_origin(issue_number)
                    self._state.remove_hitl_cause(issue_number)
                    self._state.reset_issue_attempts(issue_number)

                    await self._prs.post_comment(
                        issue_number,
                        f"**HITL correction applied successfully.**\n\n"
                        f"Returning issue to `{origin or 'pipeline'}` stage."
                        f"\n\n---\n*Applied by Hydra HITL*",
                    )
                    await self._bus.publish(
                        HydraEvent(
                            type=EventType.HITL_UPDATE,
                            data={
                                "issue": issue_number,
                                "action": "resolved",
                                "status": "resolved",
                            },
                        )
                    )
                    logger.info(
                        "HITL correction succeeded for issue #%d — returning to %s",
                        issue_number,
                        origin,
                    )
                else:
                    await self._prs.add_labels(
                        issue_number, [self._config.hitl_label[0]]
                    )
                    await self._prs.post_comment(
                        issue_number,
                        f"**HITL correction failed.**\n\n"
                        f"Error: {result.error or 'No details available'}"
                        f"\n\nPlease retry with different guidance."
                        f"\n\n---\n*Applied by Hydra HITL*",
                    )
                    await self._bus.publish(
                        HydraEvent(
                            type=EventType.HITL_UPDATE,
                            data={
                                "issue": issue_number,
                                "action": "failed",
                                "status": "pending",
                            },
                        )
                    )
                    logger.warning(
                        "HITL correction failed for issue #%d: %s",
                        issue_number,
                        result.error,
                    )

                # Clean up worktree on success; keep on failure for retry
                if result.success:
                    try:
                        await self._worktrees.destroy(issue_number)
                        self._state.remove_worktree(issue_number)
                    except RuntimeError as exc:
                        logger.warning(
                            "Could not destroy worktree for issue #%d: %s",
                            issue_number,
                            exc,
                        )
            except Exception:
                logger.exception("HITL processing failed for issue #%d", issue_number)
            finally:
                self._active_hitl_issues.discard(issue_number)
                self._state.set_active_issue_numbers(
                    list(
                        self._active_impl_issues
                        | self._active_review_issues
                        | self._active_hitl_issues
                    )
                )

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
                self._state.set_hitl_cause(
                    issue.number,
                    "Insufficient issue detail for triage",
                )
                self._state.record_hitl_escalation()
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

                if result.already_satisfied:
                    # Issue is already satisfied — close with dup label
                    for lbl in self._config.planner_label:
                        await self._prs.remove_label(issue.number, lbl)
                    await self._prs.add_labels(issue.number, self._config.dup_label)
                    await self._prs.post_comment(
                        issue.number,
                        f"## Already Satisfied\n\n"
                        f"The planner determined that this issue's requirements "
                        f"are already met by the existing codebase.\n\n"
                        f"{result.summary}\n\n"
                        f"---\n"
                        f"*Generated by Hydra Planner*",
                    )
                    await self._prs.close_issue(issue.number)
                    logger.info(
                        "Issue #%d closed as already satisfied",
                        issue.number,
                    )
                    return result

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

                    # Run pre-implementation analysis
                    analyzer = PlanAnalyzer(
                        repo_root=self._config.repo_root,
                    )
                    analysis = analyzer.analyze(result.plan, issue.number)

                    # Post analysis comment
                    await self._prs.post_comment(
                        issue.number, analysis.format_comment()
                    )

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
                elif result.retry_attempted:
                    # Both plan attempts failed validation — escalate to HITL
                    error_list = "\n".join(f"- {e}" for e in result.validation_errors)
                    hitl_comment = (
                        f"## Plan Validation Failed\n\n"
                        f"The planner was unable to produce a valid plan "
                        f"after two attempts for issue #{issue.number}.\n\n"
                        f"**Validation errors:**\n{error_list}\n\n"
                        f"---\n"
                        f"*Generated by Hydra Planner*"
                    )
                    await self._prs.post_comment(issue.number, hitl_comment)
                    for lbl in self._config.planner_label:
                        await self._prs.remove_label(issue.number, lbl)
                    self._state.set_hitl_origin(
                        issue.number, self._config.planner_label[0]
                    )
                    self._state.set_hitl_cause(
                        issue.number,
                        "Plan validation failed after retry",
                    )
                    self._state.record_hitl_escalation()
                    await self._prs.add_labels(
                        issue.number, [self._config.hitl_label[0]]
                    )
                    logger.warning(
                        "Planning failed validation for issue #%d after retry — "
                        "escalated to HITL",
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
