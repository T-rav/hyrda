"""Jobs system for scheduled tasks.

Jobs can self-register similar to agents.
Import this module to trigger auto-registration of all jobs.
"""

from .base_job import BaseJob
from .job_registry import JobRegistry
from .metric_sync import MetricSyncJob
from .portal_sync import PortalSyncJob
from .slack_user_import import SlackUserImportJob

__all__ = [
    "BaseJob",
    "JobRegistry",
    "MetricSyncJob",
    "PortalSyncJob",
    "SlackUserImportJob",
]
