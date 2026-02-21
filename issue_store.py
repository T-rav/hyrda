"""Centralized issue store with in-memory work queues.

Polls GitHub once per cycle for ALL Hydra-labeled issues, routes them
into per-stage queues, and provides queue accessors for each orchestrator
loop.  Replaces the previous pattern where each loop independently polled
GitHub.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from collections import deque

from config import HydraConfig
from events import EventBus, EventType, HydraEvent
from models import GitHubIssue, QueueStats
from subprocess_util import run_subprocess

logger = logging.getLogger("hydra.issue_store")

# Pipeline stage ordering — higher index = further downstream.
# When an issue carries multiple Hydra labels, route to the most-downstream.
_STAGE_ORDER: dict[str, int] = {
    "find": 0,
    "plan": 1,
    "ready": 2,
    "review": 3,
    "hitl": 4,
}


class IssueStore:
    """Central data layer with per-stage work queues.

    A single background loop polls GitHub for all Hydra-labeled issues
    and routes them into in-memory deques.  Orchestrator loops consume
    from these queues instead of calling ``gh issue list`` directly.
    """

    def __init__(
        self,
        config: HydraConfig,
        event_bus: EventBus | None = None,
    ) -> None:
        self._config = config
        self._bus = event_bus

        # Per-stage work queues
        self._queues: dict[str, deque[GitHubIssue]] = {
            "find": deque(),
            "plan": deque(),
            "ready": deque(),
            "review": deque(),
        }
        # Issues currently being processed: issue_number → stage
        self._active: dict[int, str] = {}
        # All known issues by number (for dedup / change detection)
        self._seen: dict[int, GitHubIssue] = {}
        # HITL issue numbers (display-only, not a work queue)
        self._hitl: set[int] = set()
        # Completion timestamps per stage (for throughput calculation)
        self._completion_times: dict[str, list[float]] = {
            s: [] for s in _STAGE_ORDER if s != "hitl"
        }
        # Total completions per stage
        self._total_processed: dict[str, int] = {
            s: 0 for s in _STAGE_ORDER if s != "hitl"
        }
        # Enqueue timestamps (for wait-time metrics)
        self._enqueue_times: dict[int, float] = {}

        self._lock = asyncio.Lock()
        self._stop_event = asyncio.Event()
        self._poll_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Begin the background polling loop."""
        self._stop_event.clear()
        # Do an initial refresh before entering the loop so queues
        # are populated immediately on startup.
        await self._refresh()
        self._poll_task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        """Signal the polling loop to stop and wait for it."""
        self._stop_event.set()
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._poll_task

    async def _poll_loop(self) -> None:
        """Periodically refresh queues from GitHub."""
        interval = self._config.store_poll_interval
        while not self._stop_event.is_set():
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
            if self._stop_event.is_set():
                break
            await self._refresh()

    # ------------------------------------------------------------------
    # GitHub refresh
    # ------------------------------------------------------------------

    async def _refresh(self) -> None:
        """Fetch all Hydra-labeled issues from GitHub and route into queues."""
        if self._config.dry_run:
            logger.info("[dry-run] Would refresh issue store from GitHub")
            return

        # Fetch issues for each label group concurrently
        fetched: dict[int, tuple[GitHubIssue, str]] = {}

        async def _fetch_stage(stage: str, labels: list[str]) -> None:
            for label in labels:
                try:
                    raw = await run_subprocess(
                        "gh",
                        "issue",
                        "list",
                        "--repo",
                        self._config.repo,
                        "--label",
                        label,
                        "--limit",
                        str(self._config.batch_size),
                        "--json",
                        "number,title,body,labels,comments,url",
                        gh_token=self._config.gh_token,
                    )
                    for item in json.loads(raw):
                        num = item["number"]
                        issue = GitHubIssue.model_validate(item)
                        existing = fetched.get(num)
                        if existing is None:
                            fetched[num] = (issue, stage)
                        else:
                            # Route to most-downstream stage
                            _, existing_stage = existing
                            if _STAGE_ORDER.get(stage, 0) > _STAGE_ORDER.get(
                                existing_stage, 0
                            ):
                                fetched[num] = (issue, stage)
                except (
                    RuntimeError,
                    json.JSONDecodeError,
                    FileNotFoundError,
                ) as exc:
                    logger.error("gh issue list failed for label=%r: %s", label, exc)

        # Handle scan-all mode for plan stage (empty planner_label)
        stages_to_fetch = self._get_stages_to_fetch()

        await asyncio.gather(
            *[_fetch_stage(stage, labels) for stage, labels in stages_to_fetch]
        )

        # Handle scan-all mode: fetch all open issues, exclude downstream
        if not self._config.planner_label:
            await self._fetch_scan_all(fetched)

        async with self._lock:
            self._route_fetched(fetched)

        # Publish stats event
        if self._bus:
            stats = self.get_stats()
            await self._bus.publish(
                HydraEvent(
                    type=EventType.QUEUE_STATS,
                    data=stats.model_dump(),
                )
            )

    def _get_stages_to_fetch(self) -> list[tuple[str, list[str]]]:
        """Return (stage, labels) pairs for each configured label group."""
        stages: list[tuple[str, list[str]]] = []
        if self._config.find_label:
            stages.append(("find", self._config.find_label))
        if self._config.planner_label:
            stages.append(("plan", self._config.planner_label))
        if self._config.ready_label:
            stages.append(("ready", self._config.ready_label))
        if self._config.review_label:
            stages.append(("review", self._config.review_label))
        if self._config.hitl_label:
            stages.append(("hitl", self._config.hitl_label))
        return stages

    async def _fetch_scan_all(
        self,
        fetched: dict[int, tuple[GitHubIssue, str]],
    ) -> None:
        """Scan-all mode: fetch all open issues, exclude downstream ones."""
        exclude_labels = list(
            {
                *self._config.ready_label,
                *self._config.review_label,
                *self._config.hitl_label,
                *self._config.fixed_label,
            }
        )
        exclude_set = set(exclude_labels)
        try:
            raw = await run_subprocess(
                "gh",
                "issue",
                "list",
                "--repo",
                self._config.repo,
                "--limit",
                str(self._config.batch_size),
                "--json",
                "number,title,body,labels,comments,url",
                gh_token=self._config.gh_token,
            )
            for item in json.loads(raw):
                num = item["number"]
                if num in fetched:
                    continue
                issue = GitHubIssue.model_validate(item)
                # Skip if the issue has any downstream labels
                if set(issue.labels) & exclude_set:
                    continue
                fetched[num] = (issue, "plan")
        except (RuntimeError, json.JSONDecodeError, FileNotFoundError) as exc:
            logger.error("gh issue list (scan-all) failed: %s", exc)

    def _route_fetched(
        self,
        fetched: dict[int, tuple[GitHubIssue, str]],
    ) -> None:
        """Route fetched issues into queues, handling moves and removals."""
        now = time.monotonic()
        fetched_numbers = set(fetched.keys())

        # Track which issues are in which queue for fast lookup
        queue_membership: dict[int, str] = {}
        for stage, q in self._queues.items():
            for issue in q:
                queue_membership[issue.number] = stage

        # Process fetched issues
        for num, (issue, stage) in fetched.items():
            if num in self._active:
                # Issue is being processed — update _seen but don't re-queue
                self._seen[num] = issue
                continue

            if stage == "hitl":
                self._hitl.add(num)
                # Remove from any work queue
                old_stage = queue_membership.get(num)
                if old_stage:
                    self._queues[old_stage] = deque(
                        i for i in self._queues[old_stage] if i.number != num
                    )
                self._seen[num] = issue
                continue

            current_stage = queue_membership.get(num)

            if current_stage == stage:
                # Already in correct queue — update issue data in-place
                self._queues[stage] = deque(
                    issue if i.number == num else i for i in self._queues[stage]
                )
                self._seen[num] = issue
            elif current_stage is not None:
                # Label changed — move to new queue
                self._queues[current_stage] = deque(
                    i for i in self._queues[current_stage] if i.number != num
                )
                self._queues[stage].append(issue)
                self._seen[num] = issue
                self._enqueue_times[num] = now
            else:
                # New issue
                self._queues[stage].append(issue)
                self._seen[num] = issue
                self._enqueue_times.setdefault(num, now)

        # Remove issues no longer present in GitHub results
        # (closed or label removed) — but only from queues, not active
        for stage, q in self._queues.items():
            self._queues[stage] = deque(i for i in q if i.number in fetched_numbers)

        # Clean up hitl set
        self._hitl = {n for n in self._hitl if n in fetched_numbers}

        # Clean up seen dict
        self._seen = {
            n: i
            for n, i in self._seen.items()
            if n in fetched_numbers or n in self._active
        }

    # ------------------------------------------------------------------
    # Queue accessors
    # ------------------------------------------------------------------

    def get_triageable(self, limit: int = 0) -> list[GitHubIssue]:
        """Pop up to *limit* issues from the find queue."""
        return self._pop_from_queue("find", limit)

    def get_plannable(self, limit: int = 0) -> list[GitHubIssue]:
        """Pop up to *limit* issues from the plan queue."""
        return self._pop_from_queue("plan", limit)

    def get_implementable(self, limit: int = 0) -> list[GitHubIssue]:
        """Pop up to *limit* issues from the ready queue."""
        return self._pop_from_queue("ready", limit)

    def get_reviewable(self, limit: int = 0) -> list[GitHubIssue]:
        """Pop up to *limit* issues from the review queue."""
        return self._pop_from_queue("review", limit)

    def _pop_from_queue(self, stage: str, limit: int) -> list[GitHubIssue]:
        """Pop up to *limit* issues from the given stage queue.

        Issues are removed from the queue but NOT marked active — the
        caller should call :meth:`mark_active` when processing begins.
        If *limit* is 0, return all items.
        """
        q = self._queues.get(stage, deque())
        if not q:
            return []
        count = len(q) if limit <= 0 else min(limit, len(q))
        return [q.popleft() for _ in range(count)]

    # ------------------------------------------------------------------
    # Active issue tracking
    # ------------------------------------------------------------------

    def mark_active(self, issue_number: int, stage: str) -> None:
        """Record that *issue_number* is being processed in *stage*."""
        self._active[issue_number] = stage

    def mark_done(self, issue_number: int) -> None:
        """Mark *issue_number* as done and record completion time."""
        stage = self._active.pop(issue_number, None)
        if stage:
            now = time.monotonic()
            self._completion_times.setdefault(stage, []).append(now)
            self._total_processed.setdefault(stage, 0)
            self._total_processed[stage] += 1
        self._enqueue_times.pop(issue_number, None)
        self._seen.pop(issue_number, None)

    def is_active(self, issue_number: int) -> bool:
        """Return *True* if *issue_number* is currently being processed."""
        return issue_number in self._active

    def get_active_issues(self) -> set[int]:
        """Return the set of currently active issue numbers."""
        return set(self._active.keys())

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> QueueStats:
        """Compute current queue statistics."""
        queue_depth: dict[str, int] = {}
        for stage, q in self._queues.items():
            queue_depth[stage] = len(q)
        queue_depth["hitl"] = len(self._hitl)

        active_count: dict[str, int] = {}
        for stage in self._active.values():
            active_count[stage] = active_count.get(stage, 0) + 1

        throughput = self._compute_throughput()

        return QueueStats(
            queue_depth=queue_depth,
            active_count=active_count,
            throughput=throughput,
            total_processed=dict(self._total_processed),
        )

    def _compute_throughput(self) -> dict[str, float]:
        """Compute issues completed per hour over a rolling 1-hour window."""
        now = time.monotonic()
        one_hour_ago = now - 3600
        throughput: dict[str, float] = {}
        for stage, times in self._completion_times.items():
            # Prune old entries
            recent = [t for t in times if t > one_hour_ago]
            self._completion_times[stage] = recent
            throughput[stage] = float(len(recent))
        return throughput
