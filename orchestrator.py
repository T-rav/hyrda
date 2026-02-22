"""Main orchestrator loop — plan, implement, review, cleanup, repeat."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from typing import Any

from acceptance_criteria import AcceptanceCriteriaGenerator
from agent import AgentRunner
from config import HydraConfig
from epic import EpicCompletionChecker
from events import EventBus, EventType, HydraEvent
from hitl_phase import HITLPhase
from hitl_runner import HITLRunner
from implement_phase import ImplementPhase
from issue_fetcher import IssueFetcher
from issue_store import IssueStore
from memory import MemorySyncWorker, file_memory_suggestion
from memory_sync_loop import MemorySyncLoop
from metrics_sync_loop import MetricsSyncLoop
from models import Phase
from plan_phase import PlanPhase
from planner import PlannerRunner
from pr_manager import PRManager
from pr_unsticker import PRUnsticker
from pr_unsticker_loop import PRUnstickerLoop
from retrospective import RetrospectiveCollector
from review_phase import ReviewPhase
from reviewer import ReviewRunner
from state import StateTracker
from subprocess_util import AuthenticationError, CreditExhaustedError
from triage import TriageRunner
from triage_phase import TriagePhase
from verification_judge import VerificationJudge
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
        self._hitl_runner = HITLRunner(config, self._bus)
        self._triage = TriageRunner(config, self._bus)
        self._dashboard: object | None = None
        # Pending human-input requests: {issue_number: question}
        self._human_input_requests: dict[int, str] = {}
        # Fulfilled human-input responses: {issue_number: answer}
        self._human_input_responses: dict[int, str] = {}
        # In-memory tracking of active issues (avoids double-processing)
        self._active_impl_issues: set[int] = set()
        self._active_review_issues: set[int] = set()
        # Issues recovered from persisted state on startup (one-cycle grace period)
        self._recovered_issues: set[int] = set()
        # Stop mechanism for dashboard control
        self._stop_event = asyncio.Event()
        self._running = False
        # Background worker last-known status: {worker_name: status dict}
        self._bg_worker_states: dict[str, dict[str, Any]] = {}
        # Background worker enabled flags: {worker_name: bool}
        self._bg_worker_enabled: dict[str, bool] = {}
        # Auth failure flag — set when a loop crashes due to AuthenticationError
        self._auth_failed = False
        # Dynamic interval overrides: {worker_name: seconds}
        self._bg_worker_intervals: dict[str, int] = {}
        # Credit pause — set when API credits are exhausted
        self._credits_paused_until: datetime | None = None
        self._credit_pause_lock = asyncio.Lock()

        # Centralized issue store and fetcher
        self._fetcher = IssueFetcher(config)
        self._store = IssueStore(config, self._fetcher, self._bus)

        # Delegate phases to focused modules
        self._triager = TriagePhase(
            config,
            self._state,
            self._store,
            self._triage,
            self._prs,
            self._bus,
            self._stop_event,
        )
        self._planner_phase = PlanPhase(
            config,
            self._state,
            self._store,
            self._planners,
            self._prs,
            self._bus,
            self._stop_event,
        )
        self._hitl_phase = HITLPhase(
            config,
            self._state,
            self._store,
            self._fetcher,
            self._worktrees,
            self._hitl_runner,
            self._prs,
            self._bus,
            self._stop_event,
            active_issues_cb=self._sync_active_issue_numbers,
        )
        self._implementer = ImplementPhase(
            config,
            self._state,
            self._worktrees,
            self._agents,
            self._prs,
            self._store,
            self._stop_event,
        )
        from metrics_manager import MetricsManager

        self._metrics_manager = MetricsManager(
            config, self._state, self._prs, self._bus
        )
        self._pr_unsticker = PRUnsticker(
            config,
            self._state,
            self._bus,
            self._prs,
            self._agents,
            self._worktrees,
            self._fetcher,
        )
        self._memory_sync = MemorySyncWorker(config, self._state, self._bus)
        self._retrospective = RetrospectiveCollector(config, self._state, self._prs)
        self._ac_generator = AcceptanceCriteriaGenerator(config, self._prs, self._bus)
        self._verification_judge = VerificationJudge(config, self._bus)
        self._epic_checker = EpicCompletionChecker(config, self._prs, self._fetcher)
        self._reviewer = ReviewPhase(
            config,
            self._state,
            self._worktrees,
            self._reviewers,
            self._prs,
            self._stop_event,
            self._store,
            agents=self._agents,
            event_bus=self._bus,
            retrospective=self._retrospective,
            ac_generator=self._ac_generator,
            verification_judge=self._verification_judge,
            epic_checker=self._epic_checker,
        )
        self._memory_sync_bg = MemorySyncLoop(
            config,
            self._fetcher,
            self._memory_sync,
            self._bus,
            self._stop_event,
            status_cb=self.update_bg_worker_status,
            enabled_cb=self.is_bg_worker_enabled,
            sleep_fn=self._sleep_or_stop,
            interval_cb=self.get_bg_worker_interval,
        )
        self._metrics_sync_bg = MetricsSyncLoop(
            config,
            self._store,
            self._metrics_manager,
            self._bus,
            self._stop_event,
            status_cb=self.update_bg_worker_status,
            enabled_cb=self.is_bg_worker_enabled,
            sleep_fn=self._sleep_or_stop,
            interval_cb=self.get_bg_worker_interval,
        )
        self._pr_unsticker_loop = PRUnstickerLoop(
            config,
            self._pr_unsticker,
            self._prs,
            self._bus,
            self._stop_event,
            status_cb=self.update_bg_worker_status,
            enabled_cb=self.is_bg_worker_enabled,
            sleep_fn=self._sleep_or_stop,
        )

    @property
    def event_bus(self) -> EventBus:
        """Expose event bus for dashboard integration."""
        return self._bus

    @property
    def issue_store(self) -> IssueStore:
        """Expose the centralized issue store for dashboard integration."""
        return self._store

    @property
    def state(self) -> StateTracker:
        """Expose state for dashboard integration."""
        return self._state

    @property
    def metrics_manager(self) -> Any:
        """Expose metrics manager for dashboard API."""
        return self._metrics_manager

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
        """Return the current lifecycle status: idle, running, stopping, auth_failed, credits_paused, or done."""
        if self._auth_failed:
            return "auth_failed"
        if (
            self._credits_paused_until is not None
            and self._credits_paused_until > datetime.now(UTC)
        ):
            return "credits_paused"
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
        self._hitl_phase.submit_correction(issue_number, correction)

    def get_hitl_status(self, issue_number: int) -> str:
        """Return the HITL status for an issue."""
        return self._hitl_phase.get_status(issue_number)

    def skip_hitl_issue(self, issue_number: int) -> None:
        """Remove an issue from HITL tracking."""
        self._hitl_phase.skip_issue(issue_number)

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
        self._credits_paused_until = None
        self._store.clear_active()
        self._active_impl_issues.clear()
        self._active_review_issues.clear()
        self._hitl_phase.active_hitl_issues.clear()

    @property
    def _active_hitl_issues(self) -> set[int]:
        """Backward-compatible access to HITL active issues."""
        return self._hitl_phase.active_hitl_issues

    @property
    def _hitl_corrections(self) -> dict[int, str]:
        """Backward-compatible access to HITL corrections dict."""
        return self._hitl_phase.hitl_corrections

    def _sync_active_issue_numbers(self) -> None:
        """Persist the combined active issue set to state."""
        self._state.set_active_issue_numbers(
            list(
                self._active_impl_issues
                | self._active_review_issues
                | self._hitl_phase.active_hitl_issues
            )
        )

    def update_bg_worker_status(
        self, name: str, status: str, details: dict[str, Any] | None = None
    ) -> None:
        """Record the latest heartbeat from a background worker."""
        self._bg_worker_states[name] = {
            "name": name,
            "status": status,
            "last_run": datetime.now(UTC).isoformat(),
            "details": details or {},
        }

    def set_bg_worker_enabled(self, name: str, enabled: bool) -> None:
        """Enable or disable a background worker by name."""
        self._bg_worker_enabled[name] = enabled

    def is_bg_worker_enabled(self, name: str) -> bool:
        """Return whether a background worker is enabled (defaults to True)."""
        return self._bg_worker_enabled.get(name, True)

    def get_bg_worker_states(self) -> dict[str, dict[str, Any]]:
        """Return a copy of all background worker states with enabled flag."""
        result: dict[str, dict[str, Any]] = {}
        for name, state_dict in self._bg_worker_states.items():
            result[name] = {**state_dict, "enabled": self.is_bg_worker_enabled(name)}
        return result

    def set_bg_worker_interval(self, name: str, seconds: int) -> None:
        """Set a dynamic interval override for a background worker."""
        self._bg_worker_intervals[name] = seconds
        self._state.set_worker_intervals(dict(self._bg_worker_intervals))

    def get_bg_worker_interval(self, name: str) -> int:
        """Return the effective interval for a background worker.

        Returns the dynamic override if set, otherwise the config default.
        """
        if name in self._bg_worker_intervals:
            return self._bg_worker_intervals[name]
        if name == "memory_sync":
            return self._config.memory_sync_interval
        if name == "metrics":
            return self._config.metrics_sync_interval
        return self._config.poll_interval

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

        # Restore interval overrides from persisted state
        saved_intervals = self._state.get_worker_intervals()
        if saved_intervals:
            self._bg_worker_intervals.update(saved_intervals)
            logger.info(
                "Restored %d worker interval override(s) from state",
                len(saved_intervals),
            )

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
        """Run all loops plus the IssueStore poller, restarting any that crash."""

        async def _store_loop() -> None:
            await self._store.start(self._stop_event)

        loop_factories: list[tuple[str, Callable[[], Coroutine[Any, Any, None]]]] = [
            ("store", _store_loop),
            ("triage", self._triage_loop),
            ("plan", self._plan_loop),
            ("implement", self._implement_loop),
            ("review", self._review_loop),
            ("hitl", self._hitl_loop),
            ("memory_sync", self._memory_sync_loop),
            ("metrics", self._metrics_sync_loop),
            ("pr_unsticker", self._pr_unsticker_loop.run),
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

                        if isinstance(exc, CreditExhaustedError):
                            await self._pause_for_credits(
                                exc, name, tasks, loop_factories
                            )
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

    async def _polling_loop(
        self,
        name: str,
        work_fn: Callable[[], Coroutine[Any, Any, Any]],
        interval: int,
        enabled_name: str | None = None,
    ) -> None:
        """Generic polling loop: check enabled -> try work -> except -> sleep."""
        while not self._stop_event.is_set():
            if enabled_name is not None and not self.is_bg_worker_enabled(enabled_name):
                await self._sleep_or_stop(interval)
                continue
            try:
                await work_fn()
            except (AuthenticationError, CreditExhaustedError):
                raise
            except Exception:
                display = name.replace("_", " ").capitalize()
                logger.exception(
                    "%s loop iteration failed — will retry next cycle",
                    display,
                )
                await self._bus.publish(
                    HydraEvent(
                        type=EventType.ERROR,
                        data={
                            "message": f"{display} loop error",
                            "source": name,
                        },
                    )
                )
            await self._sleep_or_stop(interval)

    async def _triage_loop(self) -> None:
        """Continuously poll for find-labeled issues and triage them."""
        await self._polling_loop(
            "triage",
            self._triager.triage_issues,
            self._config.poll_interval,
            enabled_name="triage",
        )

    async def _plan_loop(self) -> None:
        """Continuously poll for planner-labeled issues."""
        await self._polling_loop(
            "plan",
            self._planner_phase.plan_issues,
            self._config.poll_interval,
            enabled_name="plan",
        )

    async def _implement_loop(self) -> None:
        """Continuously poll for ``hydra-ready`` issues and implement them."""
        await self._polling_loop(
            "implement",
            self._do_implement_work,
            self._config.poll_interval,
            enabled_name="implement",
        )

    async def _review_loop(self) -> None:
        """Continuously consume reviewable issues from the store and review their PRs."""
        await self._polling_loop(
            "review",
            self._do_review_work,
            self._config.poll_interval,
            enabled_name="review",
        )

    async def _hitl_loop(self) -> None:
        """Continuously process HITL corrections submitted via the dashboard."""
        await self._polling_loop(
            "hitl",
            self._hitl_phase.process_corrections,
            self._config.poll_interval,
        )

    async def _memory_sync_loop(self) -> None:
        """Continuously poll ``hydra-memory`` issues and rebuild the digest."""
        await self._memory_sync_bg.run()

    async def _metrics_sync_loop(self) -> None:
        """Continuously aggregate and persist metrics snapshots."""
        await self._metrics_sync_bg.run()

    async def _do_implement_work(self) -> None:
        """Work function for the implement loop."""
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
        results, _issues = await self._implementer.run_batch()
        for result in results:
            if result.transcript:
                try:
                    await file_memory_suggestion(
                        result.transcript,
                        "implementer",
                        f"issue #{result.issue_number}",
                        self._config,
                        self._prs,
                        self._state,
                    )
                except Exception:
                    logger.exception(
                        "Failed to file memory suggestion for issue #%d",
                        result.issue_number,
                    )

    async def _do_review_work(self) -> None:
        """Work function for the review loop."""
        review_issues = self._store.get_reviewable(self._config.batch_size)
        if not review_issues:
            return
        active_in_store = set(self._store.get_active_issues().keys())
        prs, issues = await self._fetcher.fetch_reviewable_prs(
            active_in_store, prefetched_issues=review_issues
        )
        if not prs:
            return
        review_results = await self._reviewer.review_prs(prs, issues)
        for result in review_results:
            if result.transcript:
                try:
                    await file_memory_suggestion(
                        result.transcript,
                        "reviewer",
                        f"PR #{result.pr_number}",
                        self._config,
                        self._prs,
                        self._state,
                    )
                except Exception:
                    logger.exception(
                        "Failed to file memory suggestion for PR #%d",
                        result.pr_number,
                    )
        if any(r.merged for r in review_results):
            await asyncio.sleep(5)
            await self._prs.pull_main()

    async def _sleep_or_stop(self, seconds: int | float) -> None:
        """Sleep for *seconds*, waking early if stop is requested."""
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._stop_event.wait(), timeout=seconds)

    async def _pause_for_credits(
        self,
        exc: CreditExhaustedError,
        source: str,
        tasks: dict[str, asyncio.Task[None]],
        loop_factories: list[tuple[str, Callable[[], Coroutine[Any, Any, None]]]],
    ) -> None:
        """Pause all loops until API credits reset, then restart them.

        Uses ``asyncio.Lock`` to prevent multiple loops from racing into
        the pause logic simultaneously.
        """
        async with self._credit_pause_lock:
            # If another loop already triggered a pause, skip
            if (
                self._credits_paused_until is not None
                and self._credits_paused_until > datetime.now(UTC)
            ):
                return

            buffer = timedelta(minutes=self._config.credit_pause_buffer_minutes)
            now = datetime.now(UTC)

            if exc.resume_at is not None:
                resume_at = exc.resume_at + buffer
            else:
                # Default: 5 hours if no reset time is parseable
                resume_at = now + timedelta(hours=5) + buffer

            self._credits_paused_until = resume_at
            pause_seconds = max((resume_at - now).total_seconds(), 0)

            logger.warning(
                "Credit limit reached (detected in %r). "
                "Pausing all loops until %s (%.0f minutes).",
                source,
                resume_at.isoformat(),
                pause_seconds / 60,
            )

            await self._bus.publish(
                HydraEvent(
                    type=EventType.SYSTEM_ALERT,
                    data={
                        "message": (
                            f"Credit limit reached. Pausing all loops until "
                            f"{resume_at.strftime('%H:%M UTC')}. "
                            f"Will resume automatically."
                        ),
                        "source": source,
                    },
                )
            )

            # Cancel all running loop tasks
            for task in tasks.values():
                task.cancel()
            await asyncio.gather(*tasks.values(), return_exceptions=True)

            # Terminate active subprocesses — no point running them
            self._planners.terminate()
            self._agents.terminate()
            self._reviewers.terminate()
            self._hitl_runner.terminate()

        # Sleep until resume (interruptible by stop)
        await self._sleep_or_stop(pause_seconds)

        if self._stop_event.is_set():
            self._credits_paused_until = None
            return

        await self._resume_loops_after_credit_pause(tasks, loop_factories, source)

    async def _resume_loops_after_credit_pause(
        self,
        tasks: dict[str, asyncio.Task[None]],
        loop_factories: list[tuple[str, Callable[[], Coroutine[Any, Any, None]]]],
        source: str,
    ) -> None:
        """Clear pause state and restart all loops after credit pause."""
        self._credits_paused_until = None
        logger.info("Credit pause ended — restarting all loops")
        await self._bus.publish(
            HydraEvent(
                type=EventType.SYSTEM_ALERT,
                data={
                    "message": "Credit pause ended. Resuming all loops.",
                    "source": source,
                },
            )
        )
        for loop_name, factory in loop_factories:
            tasks[loop_name] = asyncio.create_task(factory(), name=f"hydra-{loop_name}")
