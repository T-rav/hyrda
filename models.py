"""Data models for Hydra."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

# --- GitHub ---


class GitHubIssue(BaseModel):
    """A GitHub issue fetched for processing."""

    number: int
    title: str
    body: str = ""
    labels: list[str] = Field(default_factory=list)
    comments: list[str] = Field(default_factory=list)
    url: str = ""


# --- Triage ---


class TriageStatus(StrEnum):
    """Lifecycle status of a triage evaluation."""

    EVALUATING = "evaluating"
    DONE = "done"
    FAILED = "failed"


class TriageResult(BaseModel):
    """Outcome of evaluating a single issue for readiness."""

    issue_number: int
    ready: bool = False
    reasons: list[str] = Field(default_factory=list)


# --- Planner ---


class PlannerStatus(StrEnum):
    """Lifecycle status of a planning agent."""

    QUEUED = "queued"
    PLANNING = "planning"
    DONE = "done"
    FAILED = "failed"


class NewIssueSpec(BaseModel):
    """Specification for a new issue discovered during planning."""

    title: str
    body: str = ""
    labels: list[str] = Field(default_factory=list)


class PlanResult(BaseModel):
    """Outcome of a planner agent run."""

    issue_number: int
    success: bool = False
    plan: str = ""
    summary: str = ""
    error: str | None = None
    transcript: str = ""
    duration_seconds: float = 0.0
    new_issues: list[NewIssueSpec] = Field(default_factory=list)


# --- Worker ---


class WorkerStatus(StrEnum):
    """Lifecycle status of an implementation worker."""

    QUEUED = "queued"
    RUNNING = "running"
    TESTING = "testing"
    COMMITTING = "committing"
    QUALITY_FIX = "quality_fix"
    DONE = "done"
    FAILED = "failed"


class WorkerResult(BaseModel):
    """Outcome of an implementation worker run."""

    issue_number: int
    branch: str
    worktree_path: str = ""
    success: bool = False
    error: str | None = None
    transcript: str = ""
    commits: int = 0
    duration_seconds: float = 0.0
    quality_fix_attempts: int = 0
    pr_info: PRInfo | None = None


# --- Pull Requests ---


class PRInfo(BaseModel):
    """Metadata for a created pull request."""

    number: int
    issue_number: int
    branch: str
    url: str = ""
    draft: bool = False


# --- Reviews ---


class ReviewVerdict(StrEnum):
    """Verdict from a reviewer agent."""

    APPROVE = "approve"
    REQUEST_CHANGES = "request-changes"
    COMMENT = "comment"


class ReviewResult(BaseModel):
    """Outcome of a reviewer agent run."""

    pr_number: int
    issue_number: int
    verdict: ReviewVerdict = ReviewVerdict.COMMENT
    summary: str = ""
    fixes_made: bool = False
    transcript: str = ""
    merged: bool = False
    ci_passed: bool | None = None  # None = not checked, True/False = outcome
    ci_fix_attempts: int = 0


# --- Batch ---


class BatchResult(BaseModel):
    """Summary of a full batch cycle."""

    batch_number: int
    issues: list[GitHubIssue] = Field(default_factory=list)
    plan_results: list[PlanResult] = Field(default_factory=list)
    worker_results: list[WorkerResult] = Field(default_factory=list)
    pr_infos: list[PRInfo] = Field(default_factory=list)
    review_results: list[ReviewResult] = Field(default_factory=list)
    merged_prs: list[int] = Field(default_factory=list)


# --- Orchestrator Phases ---


class Phase(StrEnum):
    """Phases of the orchestrator loop."""

    IDLE = "idle"
    PLAN = "plan"
    IMPLEMENT = "implement"
    REVIEW = "review"
    CLEANUP = "cleanup"
    DONE = "done"


# --- Dashboard API Responses ---


class PRListItem(BaseModel):
    """A PR entry returned by GET /api/prs."""

    pr: int
    issue: int = 0
    branch: str = ""
    url: str = ""
    draft: bool = False
    title: str = ""


class HITLItem(BaseModel):
    """A HITL issue entry returned by GET /api/hitl."""

    issue: int
    title: str = ""
    issueUrl: str = ""  # camelCase to match existing frontend contract
    pr: int = 0
    prUrl: str = ""  # camelCase to match existing frontend contract
    branch: str = ""


class ControlStatusConfig(BaseModel):
    """Config subset returned by GET /api/control/status."""

    repo: str = ""
    ready_label: list[str] = Field(default_factory=list)
    find_label: list[str] = Field(default_factory=list)
    planner_label: list[str] = Field(default_factory=list)
    review_label: list[str] = Field(default_factory=list)
    hitl_label: list[str] = Field(default_factory=list)
    fixed_label: list[str] = Field(default_factory=list)
    max_workers: int = 0
    max_planners: int = 0
    max_reviewers: int = 0
    batch_size: int = 0
    model: str = ""


class ControlStatusResponse(BaseModel):
    """Response for GET /api/control/status."""

    status: str = "idle"
    config: ControlStatusConfig = Field(default_factory=ControlStatusConfig)
