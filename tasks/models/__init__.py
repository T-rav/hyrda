"""Database models for the tasks service."""

from .base import Base
from .task_run import TaskRun

__all__ = ["Base", "TaskRun"]
