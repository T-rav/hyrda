"""In-process event bus for broadcasting state changes to the dashboard."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EventType(StrEnum):
    """Categories of events published by the orchestrator."""

    BATCH_START = "batch_start"
    PHASE_CHANGE = "phase_change"
    WORKER_UPDATE = "worker_update"
    TRANSCRIPT_LINE = "transcript_line"
    PR_CREATED = "pr_created"
    REVIEW_UPDATE = "review_update"
    PLANNER_UPDATE = "planner_update"
    MERGE_UPDATE = "merge_update"
    CI_CHECK = "ci_check"
    ISSUE_CREATED = "issue_created"
    BATCH_COMPLETE = "batch_complete"
    ORCHESTRATOR_STATUS = "orchestrator_status"
    ERROR = "error"


class HydraEvent(BaseModel):
    """A single event published on the bus."""

    type: EventType
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    data: dict[str, Any] = Field(default_factory=dict)


class EventBus:
    """Async pub/sub bus with history replay.

    Subscribers receive an ``asyncio.Queue`` that yields
    :class:`HydraEvent` objects as they are published.
    """

    def __init__(self, max_history: int = 5000) -> None:
        self._subscribers: list[asyncio.Queue[HydraEvent]] = []
        self._history: list[HydraEvent] = []
        self._max_history = max_history

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

    def subscribe(self, max_queue: int = 500) -> asyncio.Queue[HydraEvent]:
        """Return a new queue that will receive future events."""
        queue: asyncio.Queue[HydraEvent] = asyncio.Queue(maxsize=max_queue)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[HydraEvent]) -> None:
        """Remove *queue* from the subscriber list."""
        with contextlib.suppress(ValueError):
            self._subscribers.remove(queue)

    def get_history(self) -> list[HydraEvent]:
        """Return a copy of all recorded events."""
        return list(self._history)

    def clear(self) -> None:
        """Remove all history and subscribers."""
        self._history.clear()
        self._subscribers.clear()
