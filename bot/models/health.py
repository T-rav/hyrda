"""Health check and system status models"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal


@dataclass(frozen=True)
class HealthCheckResponse:
    status: Literal["healthy", "degraded", "unhealthy"]
    timestamp: datetime
    service_name: str
    details: str | None = None
    metrics: dict[str, Any] | None = None


@dataclass(frozen=True)
class SystemStatus:
    service_name: str
    status: Literal["running", "stopped", "error"]
    uptime_seconds: float
    memory_usage_mb: float | None = None
    cpu_usage_percent: float | None = None
    active_connections: int | None = None
    last_error: str | None = None
