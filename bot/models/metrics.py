"""Metrics and performance models"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


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
