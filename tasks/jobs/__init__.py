"""Jobs system for scheduled tasks.

Jobs can self-register similar to agents.
Import this module to trigger auto-registration of all jobs.
"""

from .base_job import BaseJob
from .gdrive_ingest import GDriveIngestJob
from .goal_bot_scheduler import GoalBotSchedulerJob
from .job_registry import JobRegistry
from .metric_sync import MetricSyncJob
from .slack_user_import import SlackUserImportJob
from .website_scrape import WebsiteScrapeJob
from .youtube_ingest import YouTubeIngestJob

__all__ = [
    "BaseJob",
    "GDriveIngestJob",
    "GoalBotSchedulerJob",
    "JobRegistry",
    "MetricSyncJob",
    "SlackUserImportJob",
    "WebsiteScrapeJob",
    "YouTubeIngestJob",
]
