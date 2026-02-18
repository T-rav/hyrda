"""Hydra configuration via Pydantic."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, model_validator


class HydraConfig(BaseModel):
    """Configuration for the Hydra orchestrator."""

    # Issue selection
    label: str = Field(default="hydra-ready", description="GitHub issue label to filter by")
    batch_size: int = Field(default=15, ge=1, le=50, description="Issues per batch")
    repo: str = Field(
        default="8thlight/insightmesh", description="GitHub repo (owner/name)"
    )

    # Worker configuration
    max_workers: int = Field(default=2, ge=1, le=10, description="Concurrent agents")
    max_budget_usd: float = Field(
        default=0, ge=0, description="USD cap per implementation agent (0 = unlimited)"
    )
    model: str = Field(default="sonnet", description="Model for implementation agents")

    # Review configuration
    review_model: str = Field(
        default="opus", description="Model for review agents (higher quality)"
    )
    review_budget_usd: float = Field(
        default=0, ge=0, description="USD cap per review agent (0 = unlimited)"
    )

    # Planner configuration
    planner_label: str = Field(
        default="claude-find", description="Label for issues needing plans"
    )
    planner_model: str = Field(default="opus", description="Model for planning agents")
    planner_budget_usd: float = Field(
        default=0, ge=0, description="USD cap per planning agent (0 = unlimited)"
    )

    # Git configuration
    main_branch: str = Field(default="main", description="Base branch name")

    # Paths (auto-detected)
    repo_root: Path = Field(default=Path("."), description="Repository root directory")
    worktree_base: Path = Field(
        default=Path("."), description="Base directory for worktrees"
    )
    state_file: Path = Field(default=Path("."), description="Path to state JSON file")

    # Dashboard
    dashboard_port: int = Field(
        default=5555, ge=1024, le=65535, description="Dashboard web UI port"
    )
    dashboard_enabled: bool = Field(
        default=True, description="Enable the live web dashboard"
    )

    # Polling
    poll_interval: int = Field(
        default=30, ge=5, le=300, description="Seconds between work-queue polls"
    )

    # Execution mode
    dry_run: bool = Field(
        default=False, description="Log actions without executing them"
    )

    model_config = {"arbitrary_types_allowed": True}

    @model_validator(mode="after")
    def resolve_paths(self) -> HydraConfig:
        """Resolve repo_root and derived paths."""
        if self.repo_root == Path("."):
            self.repo_root = _find_repo_root()
        if self.worktree_base == Path("."):
            self.worktree_base = self.repo_root.parent / "insightmesh-hydra"
        if self.state_file == Path("."):
            self.state_file = self.repo_root / ".hydra" / "state.json"
        return self


def _find_repo_root() -> Path:
    """Walk up from cwd to find the git repo root."""
    current = Path.cwd().resolve()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return Path.cwd().resolve()
