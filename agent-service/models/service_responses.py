"""Typed response models for service layer operations.

DEPRECATED: This module is maintained for backward compatibility.
Please import from specific model modules:
    from models.health import HealthCheckResponse, SystemStatus
    from models.api import ApiResponse
    from models.metrics import MetricsData, UsageMetrics, PerformanceMetrics
    from models.cache import CacheStats, ThreadInfo
"""

# Backward compatibility imports
from models.api import ApiResponse
from models.cache import CacheStats, ThreadInfo
from models.health import HealthCheckResponse, SystemStatus
from models.metrics import MetricsData, PerformanceMetrics, UsageMetrics

__all__ = [
    "HealthCheckResponse",
    "SystemStatus",
    "ApiResponse",
    "MetricsData",
    "UsageMetrics",
    "PerformanceMetrics",
    "CacheStats",
    "ThreadInfo",
]
