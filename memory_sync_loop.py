"""Background worker loop — memory sync."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from config import HydraConfig
from events import EventBus, EventType, HydraEvent
from issue_fetcher import IssueFetcher
from memory import MemorySyncWorker
from models import MemoryIssueData
from subprocess_util import AuthenticationError, CreditExhaustedError

logger = logging.getLogger("hydra.memory_sync_loop")


class MemorySyncLoop:
    """Polls ``hydra-memory`` issues and rebuilds the digest."""

    def __init__(
        self,
        config: HydraConfig,
        fetcher: IssueFetcher,
        memory_sync: MemorySyncWorker,
        bus: EventBus,
        stop_event: asyncio.Event,
        status_cb: Callable[[str, str, dict[str, Any] | None], None],
        enabled_cb: Callable[[str], bool],
        sleep_fn: Callable[[int | float], Coroutine[Any, Any, None]],
    ) -> None:
        self._config = config
        self._fetcher = fetcher
        self._memory_sync = memory_sync
        self._bus = bus
        self._stop_event = stop_event
        self._status_cb = status_cb
        self._enabled_cb = enabled_cb
        self._sleep_fn = sleep_fn

    async def run(self) -> None:
        """Continuously poll ``hydra-memory`` issues and rebuild the digest."""
        while not self._stop_event.is_set():
            if not self._enabled_cb("memory_sync"):
                await self._sleep_fn(self._config.memory_sync_interval)
                continue
            try:
                issues = await self._fetcher.fetch_issues_by_labels(
                    self._config.memory_label, limit=100
                )
                # Convert to typed dicts for the sync worker
                issue_dicts: list[MemoryIssueData] = [
                    MemoryIssueData(
                        number=i.number,
                        title=i.title,
                        body=i.body,
                        createdAt=i.created_at,
                    )
                    for i in issues
                ]
                stats = await self._memory_sync.sync(issue_dicts)
                await self._memory_sync.publish_sync_event(stats)
                self._status_cb("memory_sync", "ok", dict(stats))
            except (AuthenticationError, CreditExhaustedError):
                raise
            except Exception:
                logger.exception(
                    "Memory sync loop iteration failed — will retry next cycle"
                )
                self._status_cb("memory_sync", "error", None)
                await self._bus.publish(
                    HydraEvent(
                        type=EventType.ERROR,
                        data={
                            "message": "Memory sync loop error",
                            "source": "memory_sync",
                        },
                    )
                )
            await self._sleep_fn(self._config.memory_sync_interval)
