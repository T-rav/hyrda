"""Typed response models for service layer operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class HealthCheckResponse:
    """Standardized health check response."""

    status: Literal["healthy", "degraded", "unhealthy"]
    timestamp: datetime
    service_name: str
    details: str | None = None
    metrics: dict[str, Any] | None = None


@dataclass(frozen=True)
class SystemStatus:
    """Comprehensive system status information."""

    service_name: str
    status: Literal["running", "stopped", "error"]
    uptime_seconds: float
    memory_usage_mb: float | None = None
    cpu_usage_percent: float | None = None
    active_connections: int | None = None
    last_error: str | None = None


@dataclass(frozen=True)
class ApiResponse:
    """Generic API response wrapper."""

    success: bool
    data: Any | None = None
    error_message: str | None = None
    error_code: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)


class MetricsData(BaseModel):
    """Metrics collection data structure."""

    service_name: str
    metric_type: Literal["usage", "performance", "error", "custom"]
    value: float
    unit: str
    timestamp: datetime = Field(default_factory=datetime.now)
    labels: dict[str, str] = Field(default_factory=dict)

    class Config:
        frozen = True


@dataclass(frozen=True)
class UsageMetrics:
    """Usage metrics aggregation."""

    requests_count: int
    active_users: int
    average_response_time_ms: float
    error_rate_percent: float
    peak_concurrent_users: int
    total_data_processed_mb: float


@dataclass(frozen=True)
class PerformanceMetrics:
    """Performance metrics aggregation."""

    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    throughput_rps: float
    memory_usage_percent: float
    cpu_usage_percent: float


class CacheStats(BaseModel):
    """Cache statistics and health information."""

    hit_rate_percent: float
    miss_rate_percent: float
    total_keys: int
    memory_usage_mb: float
    evicted_keys: int
    expired_keys: int
    connections: int
    uptime_seconds: float

    class Config:
        frozen = True


@dataclass(frozen=True)
class ThreadInfo:
    """Slack thread information and participation status."""

    exists: bool
    message_count: int
    bot_is_participant: bool
    messages: list[dict[str, Any]]  # Raw Slack message objects
    participant_ids: list[str]
    error: str | None = None

    # Optional metadata
    channel: str | None = None
    thread_ts: str | None = None
