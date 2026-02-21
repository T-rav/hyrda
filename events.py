"""In-process event bus for broadcasting state changes to the dashboard."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import tempfile
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger("hydra.events")


class EventType(StrEnum):
    """Categories of events published by the orchestrator."""

    BATCH_START = "batch_start"
    PHASE_CHANGE = "phase_change"
    WORKER_UPDATE = "worker_update"
    TRANSCRIPT_LINE = "transcript_line"
    PR_CREATED = "pr_created"
    REVIEW_UPDATE = "review_update"
    TRIAGE_UPDATE = "triage_update"
    PLANNER_UPDATE = "planner_update"
    MERGE_UPDATE = "merge_update"
    CI_CHECK = "ci_check"
    HITL_ESCALATION = "hitl_escalation"
    ISSUE_CREATED = "issue_created"
    BATCH_COMPLETE = "batch_complete"
    HITL_UPDATE = "hitl_update"
    ORCHESTRATOR_STATUS = "orchestrator_status"
    ERROR = "error"
    MEMORY_SYNC = "memory_sync"
    RETROSPECTIVE = "retrospective"
    METRICS_UPDATE = "metrics_update"
    REVIEW_INSIGHT = "review_insight"
    BACKGROUND_WORKER_STATUS = "background_worker_status"
    QUEUE_UPDATE = "queue_update"


class HydraEvent(BaseModel):
    """A single event published on the bus."""

    type: EventType
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    data: dict[str, Any] = Field(default_factory=dict)


class EventLog:
    """Append-only JSONL file for persisting events to disk.

    Each event is serialized as a single JSON line. Corrupt lines
    are skipped during loading (logged as warnings, never crash).
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def _append_sync(self, line: str) -> None:
        """Synchronous append — called via ``asyncio.to_thread``."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "a") as f:
            f.write(line + "\n")
            f.flush()

    async def append(self, event: HydraEvent) -> None:
        """Serialize *event* to JSON and append a line to the log file."""
        line = event.model_dump_json()
        await asyncio.to_thread(self._append_sync, line)

    def _load_sync(
        self,
        since: datetime | None = None,
        max_events: int = 5000,
    ) -> list[HydraEvent]:
        """Synchronous load — called via ``asyncio.to_thread``."""
        if not self._path.exists():
            return []

        events: list[HydraEvent] = []
        with open(self._path) as f:
            for line_num, raw_line in enumerate(f, 1):
                stripped = raw_line.strip()
                if not stripped:
                    continue
                try:
                    event = HydraEvent.model_validate_json(stripped)
                except Exception:
                    logger.warning(
                        "Skipping corrupt event log line %d in %s",
                        line_num,
                        self._path,
                    )
                    continue

                if since is not None:
                    try:
                        ts = datetime.fromisoformat(event.timestamp)
                        if ts < since:
                            continue
                    except (ValueError, TypeError):
                        pass  # Keep events with unparseable timestamps

                events.append(event)

        # Return only the last max_events
        if len(events) > max_events:
            events = events[-max_events:]
        return events

    async def load(
        self,
        since: datetime | None = None,
        max_events: int = 5000,
    ) -> list[HydraEvent]:
        """Read events from the JSONL file, optionally filtered by timestamp."""
        return await asyncio.to_thread(self._load_sync, since, max_events)

    def _rotate_sync(self, max_size_bytes: int, max_age_days: int) -> None:
        """Synchronous rotation — called via ``asyncio.to_thread``."""
        if not self._path.exists():
            return

        try:
            file_size = self._path.stat().st_size
        except OSError:
            return

        if file_size <= max_size_bytes:
            return

        cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
        kept_lines: list[str] = []

        with open(self._path) as f:
            for raw_line in f:
                stripped = raw_line.strip()
                if not stripped:
                    continue
                try:
                    event = HydraEvent.model_validate_json(stripped)
                    ts = datetime.fromisoformat(event.timestamp)
                    if ts >= cutoff:
                        kept_lines.append(stripped)
                except Exception:
                    # Drop corrupt / unparseable lines during rotation
                    continue

        # Atomic write: temp file + os.replace (same pattern as StateTracker)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=self._path.parent,
            prefix=".events-",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w") as f:
                for line in kept_lines:
                    f.write(line + "\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self._path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise

    async def rotate(self, max_size_bytes: int, max_age_days: int) -> None:
        """Rotate the log file if it exceeds *max_size_bytes*.

        Keeps only events within *max_age_days*. Uses atomic write
        (temp file + ``os.replace``) following the ``StateTracker`` pattern.
        """
        await asyncio.to_thread(self._rotate_sync, max_size_bytes, max_age_days)


class EventBus:
    """Async pub/sub bus with history replay.

    Subscribers receive an ``asyncio.Queue`` that yields
    :class:`HydraEvent` objects as they are published.
    """

    def __init__(
        self,
        max_history: int = 5000,
        event_log: EventLog | None = None,
    ) -> None:
        self._subscribers: list[asyncio.Queue[HydraEvent]] = []
        self._history: list[HydraEvent] = []
        self._max_history = max_history
        self._event_log = event_log

    async def publish(self, event: HydraEvent) -> None:
        """Publish *event* to all subscribers and append to history."""
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]
        for queue in self._subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest if subscriber is slow
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
                queue.put_nowait(event)

        if self._event_log is not None:
            asyncio.ensure_future(self._persist_event(event))

    async def _persist_event(self, event: HydraEvent) -> None:
        """Write event to disk, logging any errors without crashing."""
        try:
            assert self._event_log is not None  # noqa: S101
            await self._event_log.append(event)
        except Exception:
            logger.warning("Failed to persist event to disk", exc_info=True)

    async def load_history_from_disk(self) -> None:
        """Populate in-memory history from the on-disk event log."""
        if self._event_log is None:
            return
        events = await self._event_log.load(max_events=self._max_history)
        self._history = events

    async def load_events_since(self, since: datetime) -> list[HydraEvent] | None:
        """Load persisted events from disk since *since*.

        Returns ``None`` when no event log is configured (caller should
        fall back to in-memory history).
        """
        if self._event_log is None:
            return None
        return await self._event_log.load(since=since)

    async def rotate_log(self, max_size_bytes: int, max_age_days: int) -> None:
        """Rotate the on-disk event log if it exceeds *max_size_bytes*."""
        if self._event_log is None:
            return
        await self._event_log.rotate(max_size_bytes, max_age_days)

    def subscribe(self, max_queue: int = 500) -> asyncio.Queue[HydraEvent]:
        """Return a new queue that will receive future events."""
        queue: asyncio.Queue[HydraEvent] = asyncio.Queue(maxsize=max_queue)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[HydraEvent]) -> None:
        """Remove *queue* from the subscriber list."""
        with contextlib.suppress(ValueError):
            self._subscribers.remove(queue)

    @contextlib.asynccontextmanager
    async def subscription(
        self, max_queue: int = 500
    ) -> AsyncIterator[asyncio.Queue[HydraEvent]]:
        """Async context manager that auto-unsubscribes on exit."""
        queue = self.subscribe(max_queue)
        try:
            yield queue
        finally:
            self.unsubscribe(queue)

    def get_history(self) -> list[HydraEvent]:
        """Return a copy of all recorded events."""
        return list(self._history)

    def clear(self) -> None:
        """Remove all history and subscribers."""
        self._history.clear()
        self._subscribers.clear()
