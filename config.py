"""Hydra configuration via Pydantic."""

from __future__ import annotations

import contextlib
import json
import logging
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger("hydra.config")


class HydraConfig(BaseModel):
    """Configuration for the Hydra orchestrator."""

    # Issue selection
    ready_label: list[str] = Field(
        default=["hydra-ready"],
        description="GitHub issue labels to filter by (OR logic)",
    )
    batch_size: int = Field(default=15, ge=1, le=50, description="Issues per batch")
    repo: str = Field(
        default="",
        description="GitHub repo (owner/name); auto-detected from git remote if empty",
    )

    # Worker configuration
    max_workers: int = Field(default=3, ge=1, le=10, description="Concurrent agents")
    max_planners: int = Field(
        default=1, ge=1, le=10, description="Concurrent planning agents"
    )
    max_reviewers: int = Field(
        default=5, ge=1, le=10, description="Concurrent review agents"
    )
    max_hitl_workers: int = Field(
        default=1, ge=1, le=5, description="Concurrent HITL correction agents"
    )
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

    # CI check configuration
    ci_check_timeout: int = Field(
        default=600, ge=30, le=3600, description="Seconds to wait for CI checks"
    )
    ci_poll_interval: int = Field(
        default=30, ge=5, le=120, description="Seconds between CI status polls"
    )
    max_ci_fix_attempts: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Max CI fix-and-retry cycles (0 = skip CI wait)",
    )
    max_quality_fix_attempts: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Max quality fix-and-retry cycles before marking agent as failed",
    )
    max_review_fix_attempts: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Max review fix-and-retry cycles before HITL escalation",
    )
    min_review_findings: int = Field(
        default=3,
        ge=0,
        le=20,
        description="Minimum review findings threshold for adversarial review",
    )
    max_merge_conflict_fix_attempts: int = Field(
        default=3,
        ge=0,
        le=5,
        description="Max merge conflict resolution retry cycles",
    )
    max_issue_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Max total implementation attempts per issue before HITL escalation",
    )
    gh_max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Max retry attempts for gh CLI calls",
    )

    # Label lifecycle
    review_label: list[str] = Field(
        default=["hydra-review"],
        description="Labels for issues/PRs under review (OR logic)",
    )
    hitl_label: list[str] = Field(
        default=["hydra-hitl"],
        description="Labels for issues escalated to human-in-the-loop (OR logic)",
    )
    hitl_active_label: list[str] = Field(
        default=["hydra-hitl-active"],
        description="Labels for HITL items being actively processed (OR logic)",
    )
    fixed_label: list[str] = Field(
        default=["hydra-fixed"],
        description="Labels applied after PR is merged (OR logic)",
    )
    improve_label: list[str] = Field(
        default=["hydra-improve"],
        description="Labels for improvement/memory suggestion issues (OR logic)",
    )
    memory_label: list[str] = Field(
        default=["hydra-memory"],
        description="Labels for accepted agent learnings (OR logic)",
    )
    metrics_label: list[str] = Field(
        default=["hydra-metrics"],
        description="Labels for the metrics persistence issue (OR logic)",
    )
    dup_label: list[str] = Field(
        default=["hydra-dup"],
        description="Labels applied when issue is already satisfied (no changes needed)",
    )

    # Discovery / planner configuration
    find_label: list[str] = Field(
        default=["hydra-find"],
        description="Labels for new issues to discover and triage into planning (OR logic)",
    )
    planner_label: list[str] = Field(
        default=["hydra-plan"],
        description="Labels for issues needing plans (OR logic)",
    )
    planner_model: str = Field(default="opus", description="Model for planning agents")
    planner_budget_usd: float = Field(
        default=0, ge=0, description="USD cap per planning agent (0 = unlimited)"
    )
    min_plan_words: int = Field(
        default=200,
        ge=50,
        le=2000,
        description="Minimum word count for a valid plan",
    )
    max_new_files_warning: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Warn if plan creates more than this many new files",
    )
    lite_plan_labels: list[str] = Field(
        default=["bug", "typo", "docs"],
        description="Issue labels that trigger a lite plan (fewer required sections)",
    )
    # Metric thresholds for improvement proposals
    quality_fix_rate_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Alert if quality fix rate exceeds this (0.0-1.0)",
    )
    approval_rate_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Alert if first-pass approval rate drops below this (0.0-1.0)",
    )
    hitl_rate_threshold: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Alert if HITL escalation rate exceeds this (0.0-1.0)",
    )

    # Review insight aggregation
    review_insight_window: int = Field(
        default=10,
        ge=3,
        le=50,
        description="Number of recent reviews to analyze for patterns",
    )
    review_pattern_threshold: int = Field(
        default=3,
        ge=2,
        le=10,
        description="Minimum category frequency to trigger improvement proposal",
    )

    # Agent prompt configuration
    test_command: str = Field(
        default="make test",
        description="Quick test command for agent prompts",
    )
    max_issue_body_chars: int = Field(
        default=10_000,
        ge=1_000,
        le=100_000,
        description="Max characters for issue body in agent prompts before truncation",
    )
    max_review_diff_chars: int = Field(
        default=15_000,
        ge=1_000,
        le=200_000,
        description="Max characters for PR diff in reviewer prompts before truncation",
    )
    max_memory_chars: int = Field(
        default=4000,
        ge=500,
        le=50_000,
        description="Max characters for memory digest before compaction",
    )
    max_memory_prompt_chars: int = Field(
        default=4000,
        ge=500,
        le=50_000,
        description="Max characters for memory digest injected into agent prompts",
    )
    memory_compaction_model: str = Field(
        default="haiku",
        description="Cheap model for summarising memory digest when over size limit",
    )

    # Git configuration
    main_branch: str = Field(default="main", description="Base branch name")
    git_user_name: str = Field(
        default="",
        description="Git user.name for worktree commits; falls back to global git config if empty",
    )
    git_user_email: str = Field(
        default="",
        description="Git user.email for worktree commits; falls back to global git config if empty",
    )

    # Paths (auto-detected)
    repo_root: Path = Field(default=Path("."), description="Repository root directory")
    worktree_base: Path = Field(
        default=Path("."), description="Base directory for worktrees"
    )
    state_file: Path = Field(default=Path("."), description="Path to state JSON file")

    # Event persistence
    event_log_path: Path = Field(
        default=Path("."),
        description="Path to event log JSONL file",
    )
    event_log_max_size_mb: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Max event log file size in MB before rotation",
    )
    event_log_retention_days: int = Field(
        default=7,
        ge=1,
        le=90,
        description="Days of event history to retain during rotation",
    )

    # Config file persistence
    config_file: Path | None = Field(
        default=None,
        description="Path to JSON config file for persisting runtime changes",
    )

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
    memory_sync_interval: int = Field(
        default=120,
        ge=10,
        le=1200,
        description="Seconds between memory sync polls (default: poll_interval * 4)",
    )
    metrics_sync_interval: int = Field(
        default=300,
        ge=30,
        le=3600,
        description="Seconds between metrics snapshot syncs",
    )
    data_poll_interval: int = Field(
        default=60,
        ge=10,
        le=600,
        description="Seconds between centralized GitHub issue store polls",
    )

    # Acceptance criteria generation
    ac_model: str = Field(
        default="sonnet",
        description="Model for acceptance criteria generation (post-merge)",
    )
    ac_budget_usd: float = Field(
        default=0, ge=0, description="USD cap for AC generation agent (0 = unlimited)"
    )

    # Retrospective
    retrospective_window: int = Field(
        default=10,
        ge=3,
        le=100,
        description="Number of recent retrospective entries to scan for patterns",
    )

    # Execution mode
    dry_run: bool = Field(
        default=False, description="Log actions without executing them"
    )

    # GitHub authentication
    gh_token: str = Field(
        default="",
        description="GitHub token for gh CLI auth (overrides shell GH_TOKEN)",
    )

    model_config = {"arbitrary_types_allowed": True}

    def branch_for_issue(self, issue_number: int) -> str:
        """Return the canonical branch name for a given issue number."""
        return f"agent/issue-{issue_number}"

    def worktree_path_for_issue(self, issue_number: int) -> Path:
        """Return the worktree directory path for a given issue number."""
        return self.worktree_base / f"issue-{issue_number}"

    @model_validator(mode="after")
    def resolve_defaults(self) -> HydraConfig:
        """Resolve paths, repo slug, and apply env var overrides.

        Environment variables (checked when no explicit CLI value is given):
            HYDRA_GITHUB_REPO       → repo
            HYDRA_GITHUB_ASSIGNEE   → (used by slash commands only)
            HYDRA_GH_TOKEN          → gh_token
            HYDRA_GIT_USER_NAME     → git_user_name
            HYDRA_GIT_USER_EMAIL    → git_user_email
            HYDRA_MIN_PLAN_WORDS    → min_plan_words
            HYDRA_LABEL_FIND        → find_label   (discovery stage)
            HYDRA_LABEL_PLAN        → planner_label
            HYDRA_LABEL_READY       → ready_label  (implement stage)
            HYDRA_LABEL_REVIEW      → review_label
            HYDRA_LABEL_HITL        → hitl_label
            HYDRA_LABEL_HITL_ACTIVE → hitl_active_label
            HYDRA_LABEL_FIXED       → fixed_label
            HYDRA_LABEL_IMPROVE     → improve_label
            HYDRA_LABEL_MEMORY      → memory_label
            HYDRA_LABEL_DUP         → dup_label
        """
        # Paths
        if self.repo_root == Path("."):
            self.repo_root = _find_repo_root()
        if self.worktree_base == Path("."):
            self.worktree_base = self.repo_root.parent / "hyrda-worktrees"
        if self.state_file == Path("."):
            self.state_file = self.repo_root / ".hydra" / "state.json"
        if self.event_log_path == Path("."):
            self.event_log_path = self.repo_root / ".hydra" / "events.jsonl"

        # Repo slug: env var → git remote → empty
        if not self.repo:
            self.repo = os.environ.get("HYDRA_GITHUB_REPO", "") or _detect_repo_slug(
                self.repo_root
            )

        # GitHub token: explicit value → HYDRA_GH_TOKEN env var → inherited GH_TOKEN
        if not self.gh_token:
            env_token = os.environ.get("HYDRA_GH_TOKEN", "")
            if env_token:
                object.__setattr__(self, "gh_token", env_token)

        # Git identity: explicit value → HYDRA_GIT_USER_NAME/EMAIL env var
        if not self.git_user_name:
            env_name = os.environ.get("HYDRA_GIT_USER_NAME", "")
            if env_name:
                object.__setattr__(self, "git_user_name", env_name)
        if not self.git_user_email:
            env_email = os.environ.get("HYDRA_GIT_USER_EMAIL", "")
            if env_email:
                object.__setattr__(self, "git_user_email", env_email)

        # Planner env var overrides (only apply when still at the default)
        env_min_words = os.environ.get("HYDRA_MIN_PLAN_WORDS")
        if env_min_words is not None and self.min_plan_words == 200:
            object.__setattr__(self, "min_plan_words", int(env_min_words))

        env_lite_labels = os.environ.get("HYDRA_LITE_PLAN_LABELS")
        if env_lite_labels is not None and self.lite_plan_labels == [
            "bug",
            "typo",
            "docs",
        ]:
            parsed = [lbl.strip() for lbl in env_lite_labels.split(",") if lbl.strip()]
            if parsed:
                object.__setattr__(self, "lite_plan_labels", parsed)

        # Review fix attempts override
        if self.max_review_fix_attempts == 2:  # still at default
            env_review_fix = os.environ.get("HYDRA_MAX_REVIEW_FIX_ATTEMPTS")
            if env_review_fix is not None:
                with contextlib.suppress(ValueError):
                    object.__setattr__(
                        self, "max_review_fix_attempts", int(env_review_fix)
                    )

        # Min review findings override
        if self.min_review_findings == 3:  # still at default
            env_min_findings = os.environ.get("HYDRA_MIN_REVIEW_FINDINGS")
            if env_min_findings is not None:
                with contextlib.suppress(ValueError):
                    object.__setattr__(
                        self, "min_review_findings", int(env_min_findings)
                    )

        # Agent prompt config overrides
        env_test_cmd = os.environ.get("HYDRA_TEST_COMMAND")
        if env_test_cmd is not None and self.test_command == "make test":
            object.__setattr__(self, "test_command", env_test_cmd)

        env_max_body = os.environ.get("HYDRA_MAX_ISSUE_BODY_CHARS")
        if env_max_body is not None and self.max_issue_body_chars == 10_000:
            with contextlib.suppress(ValueError):
                object.__setattr__(self, "max_issue_body_chars", int(env_max_body))

        env_max_diff = os.environ.get("HYDRA_MAX_REVIEW_DIFF_CHARS")
        if env_max_diff is not None and self.max_review_diff_chars == 15_000:
            with contextlib.suppress(ValueError):
                object.__setattr__(self, "max_review_diff_chars", int(env_max_diff))

        # gh retry override
        if self.gh_max_retries == 3:  # still at default
            env_retries = os.environ.get("HYDRA_GH_MAX_RETRIES")
            if env_retries is not None:
                with contextlib.suppress(ValueError):
                    object.__setattr__(self, "gh_max_retries", int(env_retries))

        # issue attempt cap override
        if self.max_issue_attempts == 3:  # still at default
            env_issue_attempts = os.environ.get("HYDRA_MAX_ISSUE_ATTEMPTS")
            if env_issue_attempts is not None:
                with contextlib.suppress(ValueError):
                    object.__setattr__(
                        self, "max_issue_attempts", int(env_issue_attempts)
                    )

        # Memory sync interval override
        if self.memory_sync_interval == 120:  # still at default
            env_mem_sync = os.environ.get("HYDRA_MEMORY_SYNC_INTERVAL")
            if env_mem_sync is not None:
                with contextlib.suppress(ValueError):
                    object.__setattr__(self, "memory_sync_interval", int(env_mem_sync))

        # Metrics sync interval override
        if self.metrics_sync_interval == 300:  # still at default
            env_metrics_sync = os.environ.get("HYDRA_METRICS_SYNC_INTERVAL")
            if env_metrics_sync is not None:
                with contextlib.suppress(ValueError):
                    object.__setattr__(
                        self, "metrics_sync_interval", int(env_metrics_sync)
                    )

        # merge conflict fix attempts override
        if self.max_merge_conflict_fix_attempts == 3:  # still at default
            env_attempts = os.environ.get("HYDRA_MAX_MERGE_CONFLICT_FIX_ATTEMPTS")
            if env_attempts is not None:
                with contextlib.suppress(ValueError):
                    object.__setattr__(
                        self, "max_merge_conflict_fix_attempts", int(env_attempts)
                    )

        # Data poll interval override
        if self.data_poll_interval == 60:  # still at default
            env_data_poll = os.environ.get("HYDRA_DATA_POLL_INTERVAL")
            if env_data_poll is not None:
                with contextlib.suppress(ValueError):
                    object.__setattr__(self, "data_poll_interval", int(env_data_poll))

        # Label env var overrides (only apply when still at the default)
        _ENV_LABEL_MAP: dict[str, tuple[str, list[str]]] = {
            "HYDRA_LABEL_FIND": ("find_label", ["hydra-find"]),
            "HYDRA_LABEL_PLAN": ("planner_label", ["hydra-plan"]),
            "HYDRA_LABEL_READY": ("ready_label", ["hydra-ready"]),
            "HYDRA_LABEL_REVIEW": ("review_label", ["hydra-review"]),
            "HYDRA_LABEL_HITL": ("hitl_label", ["hydra-hitl"]),
            "HYDRA_LABEL_HITL_ACTIVE": ("hitl_active_label", ["hydra-hitl-active"]),
            "HYDRA_LABEL_FIXED": ("fixed_label", ["hydra-fixed"]),
            "HYDRA_LABEL_IMPROVE": ("improve_label", ["hydra-improve"]),
            "HYDRA_LABEL_MEMORY": ("memory_label", ["hydra-memory"]),
            "HYDRA_LABEL_METRICS": ("metrics_label", ["hydra-metrics"]),
            "HYDRA_LABEL_DUP": ("dup_label", ["hydra-dup"]),
        }
        for env_key, (field_name, default_val) in _ENV_LABEL_MAP.items():
            current = getattr(self, field_name)
            env_val = os.environ.get(env_key)
            if env_val is not None and current == default_val:
                # Empty string → empty list (scan-all mode); otherwise split on comma
                labels = (
                    [part.strip() for part in env_val.split(",") if part.strip()]
                    if env_val
                    else []
                )
                object.__setattr__(self, field_name, labels)

        return self


def _find_repo_root() -> Path:
    """Walk up from cwd to find the git repo root."""
    current = Path.cwd().resolve()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return Path.cwd().resolve()


def _detect_repo_slug(repo_root: Path) -> str:
    """Extract ``owner/repo`` from the git remote origin URL.

    Falls back to an empty string if detection fails.
    """
    import subprocess  # noqa: PLC0415

    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        url = result.stdout.strip()
        if not url:
            return ""
        # Handle HTTPS: https://github.com/owner/repo.git
        # Handle SSH:   git@github.com:owner/repo.git
        url = url.removesuffix(".git")
        if "github.com/" in url:
            return url.split("github.com/")[-1]
        if "github.com:" in url:
            return url.split("github.com:")[-1]
        return ""
    except (FileNotFoundError, OSError):
        return ""


def load_config_file(path: Path | None) -> dict[str, Any]:
    """Load a JSON config file and return its contents as a dict.

    Returns an empty dict if the file is missing, unreadable, or invalid.
    """
    if path is None:
        return {}
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            return {}
        return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_config_file(path: Path | None, values: dict[str, Any]) -> None:
    """Save config values to a JSON file, merging with existing contents."""
    if path is None:
        return
    existing: dict[str, Any] = {}
    try:
        existing = json.loads(path.read_text())
        if not isinstance(existing, dict):
            existing = {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    existing.update(values)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(existing, indent=2) + "\n")
    except OSError:
        logger.warning("Failed to write config file %s", path)
