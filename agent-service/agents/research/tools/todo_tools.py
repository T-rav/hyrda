"""TODO management tools for research agent."""

import logging
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from ..services.todo_manager import ResearchTodoManager

logger = logging.getLogger(__name__)


class CreateTaskInput(BaseModel):
    """Input for creating a research task."""

    description: str = Field(
        min_length=10,
        description="Clear, specific description of what needs to be researched",
    )
    priority: str = Field(
        default="medium",
        description='Priority level: "low", "medium", or "high"',
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="List of task IDs this task depends on (must complete first)",
    )


class CompleteTaskInput(BaseModel):
    """Input for completing a research task."""

    task_id: str = Field(description="ID of the task to mark as complete")
    findings: str = Field(
        min_length=50,
        description="Comprehensive research findings for this task (minimum 50 characters)",
    )


class CreateTaskTool(BaseTool):
    """Create a new research subtask in the TODO list.

    Use this to break down complex research into manageable tasks.
    Supports priorities and task dependencies.
    """

    name: str = "create_research_task"
    description: str = (
        "Create a new research subtask with description, priority, and optional dependencies. "
        "Use this to organize research into structured tasks. "
        "Returns the created task with a unique task_id."
    )
    args_schema: type[BaseModel] = CreateTaskInput

    todo_manager: ResearchTodoManager

    class Config:
        """Config."""

        arbitrary_types_allowed = True

    def __init__(self, todo_manager: ResearchTodoManager, **kwargs: Any):
        """Initialize with TODO manager.

        Args:
            todo_manager: Shared TODO manager instance
            **kwargs: Additional BaseTool arguments
        """
        kwargs["todo_manager"] = todo_manager
        super().__init__(**kwargs)

    def _run(
        self,
        description: str,
        priority: str = "medium",
        dependencies: list[str] | None = None,
    ) -> str:
        """Create research task.

        Args:
            description: Task description
            priority: Priority level
            dependencies: Optional dependency task IDs

        Returns:
            Success message with task ID
        """
        try:
            task = self.todo_manager.create_task(
                description=description,
                priority=priority,
                dependencies=dependencies or [],
            )
            return f"✅ Created task {task.task_id}: {description[:60]}... (Priority: {priority})"
        except Exception as e:
            logger.error(f"Error creating task: {e}")
            return f"❌ Error creating task: {str(e)}"


class CompleteTaskTool(BaseTool):
    """Mark a research task as completed with findings.

    Use this when you've finished researching a task and have comprehensive findings.
    """

    name: str = "complete_research_task"
    description: str = (
        "Mark a research task as completed and record the findings. "
        "Use this after thoroughly researching a task. "
        "Findings should be comprehensive and well-structured."
    )
    args_schema: type[BaseModel] = CompleteTaskInput

    todo_manager: ResearchTodoManager

    class Config:
        """Config."""

        arbitrary_types_allowed = True

    def __init__(self, todo_manager: ResearchTodoManager, **kwargs: Any):
        """Initialize with TODO manager.

        Args:
            todo_manager: Shared TODO manager instance
            **kwargs: Additional BaseTool arguments
        """
        kwargs["todo_manager"] = todo_manager
        super().__init__(**kwargs)

    def _run(self, task_id: str, findings: str) -> str:
        """Complete research task.

        Args:
            task_id: Task ID
            findings: Research findings

        Returns:
            Success message or error
        """
        try:
            task = self.todo_manager.complete_task(task_id, findings)
            if task:
                return f"✅ Completed task {task_id}: {task.description[:60]}..."
            else:
                return f"❌ Task {task_id} not found"
        except Exception as e:
            logger.error(f"Error completing task {task_id}: {e}")
            return f"❌ Error completing task: {str(e)}"
