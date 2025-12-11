"""Jobs system for scheduled tasks.

All jobs are now loaded from external_tasks/ directory.
This module only contains the base job class and registry framework.
"""

from .base_job import BaseJob
from .job_registry import JobRegistry

__all__ = [
    "BaseJob",
    "JobRegistry",
]
