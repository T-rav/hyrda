"""State definitions for goal executor workflow.

Defines the step-based execution model following the OpenClaw mesh pattern.
"""

from enum import StrEnum
from typing import Annotated, Any

from langchain_core.messages import MessageLikeRepresentation
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class StepStatus(StrEnum):
    """Status of a goal step."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class GoalStatus(StrEnum):
    """Status of the overall goal execution."""

    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class GoalStep(BaseModel):
    """Individual step in the goal execution plan.

    Steps have:
    - A unique ID for tracking
    - A prompt describing what to accomplish
    - Dependencies on other steps (must complete first)
    - Status tracking through execution
    - Result storage on completion
    """

    id: str = Field(..., description="Unique step identifier")
    name: str = Field("", description="Human-readable step name")
    prompt: str = Field(..., description="What this step should accomplish")
    depends_on: list[str] = Field(
        default_factory=list,
        description="IDs of steps that must complete before this one",
    )
    status: StepStatus = Field(default=StepStatus.PENDING)
    attempts: int = Field(default=0, description="Number of execution attempts")
    result: str | None = Field(default=None, description="Step execution result")
    error: str | None = Field(default=None, description="Error message if failed")
    started_at: str | None = Field(default=None)
    completed_at: str | None = Field(default=None)


class GoalPlan(BaseModel):
    """Plan for achieving a goal, consisting of ordered steps."""

    plan_id: str = Field(..., description="Unique plan identifier")
    goal: str = Field(..., description="The goal this plan achieves")
    steps: list[GoalStep] = Field(default_factory=list)
    created_at: str | None = Field(default=None)
    source: str = Field(
        default="auto", description="How plan was created: auto, manual"
    )


# Tool schemas for goal execution
class CreateStep(BaseModel):
    """Tool for creating a new step in the plan."""

    name: str = Field(..., description="Human-readable step name")
    prompt: str = Field(..., description="What this step should accomplish")
    depends_on: list[str] = Field(
        default_factory=list,
        description="IDs of steps that must complete before this one",
    )


class CompleteStep(BaseModel):
    """Tool for marking a step as complete."""

    step_id: str = Field(..., description="ID of the step to complete")
    result: str = Field(..., description="Result/outcome of the step")


class FailStep(BaseModel):
    """Tool for marking a step as failed."""

    step_id: str = Field(..., description="ID of the step that failed")
    error: str = Field(..., description="Error message describing the failure")


class SkipStep(BaseModel):
    """Tool for skipping a step (e.g., dependency failed)."""

    step_id: str = Field(..., description="ID of the step to skip")
    reason: str = Field(..., description="Reason for skipping")


class GoalComplete(BaseModel):
    """Tool for signaling the goal has been achieved."""

    summary: str = Field(..., description="Summary of what was accomplished")


class GoalFailed(BaseModel):
    """Tool for signaling the goal cannot be achieved."""

    reason: str = Field(..., description="Why the goal failed")


# Main state for goal executor
class _GoalExecutorStateRequired(TypedDict):
    """Required fields for GoalExecutorState."""

    goal: str  # The goal to achieve


class GoalExecutorState(_GoalExecutorStateRequired, total=False):
    """Main state for goal executor workflow.

    Tracks the goal, plan, step execution, and overall progress.

    Attributes:
        goal: The goal to achieve (REQUIRED)
        messages: Conversation history with AI
        status: Overall goal status
        plan: The execution plan with steps
        current_step_id: Step currently being executed
        completed_results: Results from completed steps
        iteration_count: Number of plan-execute-check loops
        max_iterations: Maximum allowed iterations
        max_parallel: Maximum concurrent step executions
        final_outcome: Summary when goal completes
        error_message: Error when goal fails
        persistent_state: State persisted between runs (for goal bots)
    """

    messages: Annotated[list[MessageLikeRepresentation], add_messages]
    status: GoalStatus
    plan: GoalPlan | None
    current_step_id: str | None
    completed_results: dict[str, str]  # step_id -> result
    iteration_count: int
    max_iterations: int
    max_parallel: int
    final_outcome: str | None
    error_message: str | None
    persistent_state: dict[str, Any]  # State that persists between goal bot runs


# Input/Output schemas
class GoalExecutorInputState(TypedDict):
    """Input to the goal executor graph."""

    goal: str
    persistent_state: dict[str, Any] | None


class GoalExecutorOutputState(TypedDict):
    """Output from the goal executor graph."""

    messages: list[MessageLikeRepresentation]
    status: GoalStatus
    plan: GoalPlan | None
    completed_results: dict[str, str]
    final_outcome: str | None
    error_message: str | None
    persistent_state: dict[str, Any]


# Executor subgraph state
class StepExecutorState(TypedDict):
    """State for step executor subgraph."""

    step: GoalStep
    messages: list[MessageLikeRepresentation]
    tool_iterations: int
    result: str | None
    error: str | None
