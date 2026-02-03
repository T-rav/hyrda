"""Cache and thread information models"""

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict


class CacheStats(BaseModel):
    model_config = ConfigDict(frozen=True)

    hit_rate_percent: float
    miss_rate_percent: float
    total_keys: int
    memory_usage_mb: float
    evicted_keys: int
    expired_keys: int
    connections: int
    uptime_seconds: float


@dataclass(frozen=True)
class ThreadInfo:
    exists: bool
    message_count: int
    bot_is_participant: bool
    messages: list[dict[str, Any]]  # Raw Slack message objects
    participant_ids: list[str]
    error: str | None = None

    # Optional metadata
    channel: str | None = None
    thread_ts: str | None = None
