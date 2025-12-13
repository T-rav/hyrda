"""TODO manager for research tasks.

Tracks research subtasks with dependencies, priorities, and status.
"""

import logging
import uuid
from datetime import datetime

from ..state import ResearchTask

logger = logging.getLogger(__name__)


class ResearchTodoManager:
    """Manages research TODO list with dependencies and priorities."""

    def __init__(self):
        """Initialize TODO manager."""
        self.tasks: dict[str, ResearchTask] = {}

    def create_task(
        self,
        description: str,
        priority: str = "medium",
        dependencies: list[str] | None = None,
    ) -> ResearchTask:
        """Create a new research task.

        Args:
            description: Clear description of research task
            priority: Priority level (low, medium, high)
            dependencies: List of task IDs this depends on

        Returns:
            Created ResearchTask
        """
        task_id = str(uuid.uuid4())[:8]
        task = ResearchTask(
            task_id=task_id,
            description=description,
            priority=priority,
            status="pending",
            dependencies=dependencies or [],
            findings=None,
            created_at=datetime.now().isoformat(),
            completed_at=None,
        )
        self.tasks[task_id] = task
        logger.info(
            f"Created task {task_id} ({priority} priority): {description[:50]}..."
        )
        return task

    def get_task(self, task_id: str) -> ResearchTask | None:
        """Get task by ID.

        Args:
            task_id: Task ID

        Returns:
            ResearchTask or None if not found
        """
        return self.tasks.get(task_id)

    def complete_task(self, task_id: str, findings: str) -> ResearchTask | None:
        """Mark task as completed with findings.

        Args:
            task_id: Task ID
            findings: Research findings

        Returns:
            Updated ResearchTask or None if not found
        """
        task = self.tasks.get(task_id)
        if not task:
            logger.warning(f"Task {task_id} not found")
            return None

        task.status = "completed"
        task.findings = findings
        task.completed_at = datetime.now().isoformat()
        logger.info(f"Completed task {task_id}: {task.description[:50]}...")
        return task

    def get_pending_tasks(self) -> list[ResearchTask]:
        """Get all pending tasks with satisfied dependencies.

        Returns:
            List of tasks ready to execute
        """
        pending = []
        for task in self.tasks.values():
            if task.status != "pending":
                continue

            # Check if dependencies are satisfied
            deps_satisfied = all(
                self.tasks.get(dep_id, ResearchTask(status="pending")).status
                == "completed"
                for dep_id in task.dependencies
            )

            if deps_satisfied:
                pending.append(task)

        # Sort by priority (high > medium > low)
        priority_order = {"high": 3, "medium": 2, "low": 1}
        pending.sort(key=lambda t: priority_order.get(t.priority, 0), reverse=True)
        return pending

    def get_completed_tasks(self) -> list[ResearchTask]:
        """Get all completed tasks.

        Returns:
            List of completed tasks
        """
        return [t for t in self.tasks.values() if t.status == "completed"]

    def get_blocked_tasks(self) -> list[ResearchTask]:
        """Get tasks blocked by dependencies.

        Returns:
            List of blocked tasks
        """
        blocked = []
        for task in self.tasks.values():
            if task.status != "pending":
                continue

            # Check if any dependency is not completed
            deps_satisfied = all(
                self.tasks.get(dep_id, ResearchTask(status="pending")).status
                == "completed"
                for dep_id in task.dependencies
            )

            if not deps_satisfied:
                blocked.append(task)

        return blocked

    def get_all_tasks(self) -> list[ResearchTask]:
        """Get all tasks.

        Returns:
            List of all tasks
        """
        return list(self.tasks.values())

    def get_task_summary(self) -> dict[str, int]:
        """Get summary of task statuses.

        Returns:
            Dict with counts by status
        """
        pending_ready = len(self.get_pending_tasks())
        blocked = len(self.get_blocked_tasks())
        completed = len(self.get_completed_tasks())
        in_progress = len([t for t in self.tasks.values() if t.status == "in_progress"])

        return {
            "total": len(self.tasks),
            "pending_ready": pending_ready,
            "in_progress": in_progress,
            "blocked": blocked,
            "completed": completed,
        }

    def mark_in_progress(self, task_id: str) -> ResearchTask | None:
        """Mark task as in progress.

        Args:
            task_id: Task ID

        Returns:
            Updated ResearchTask or None if not found
        """
        task = self.tasks.get(task_id)
        if not task:
            return None

        task.status = "in_progress"
        logger.info(f"Started task {task_id}: {task.description[:50]}...")
        return task

    def cancel_task(self, task_id: str) -> bool:
        """Cancel/remove a task.

        Args:
            task_id: Task ID

        Returns:
            True if cancelled, False if not found
        """
        if task_id in self.tasks:
            del self.tasks[task_id]
            logger.info(f"Cancelled task {task_id}")
            return True
        return False
