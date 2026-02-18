"""Shared fixtures and factories for Hydra tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

# Ensure hydra package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

if TYPE_CHECKING:
    from config import HydraConfig
    from models import GitHubIssue, PRInfo, WorkerResult


# --- Session-scoped environment setup ---


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set minimal env vars and prevent real subprocess calls."""
    test_env = {
        "HOME": "/tmp/hydra-test",
        "GH_TOKEN": "test-token",
    }
    with patch.dict(os.environ, test_env, clear=False):
        yield


# --- Config Factory ---


class ConfigFactory:
    """Factory for HydraConfig instances."""

    @staticmethod
    def create(
        *,
        label: str = "test-label",
        batch_size: int = 3,
        max_workers: int = 2,
        max_budget_usd: float = 1.0,
        model: str = "sonnet",
        review_model: str = "opus",
        review_budget_usd: float = 1.0,
        repo: str = "test-org/test-repo",
        dry_run: bool = False,
        dashboard_enabled: bool = False,
        dashboard_port: int = 15555,
        repo_root: Path | None = None,
        worktree_base: Path | None = None,
        state_file: Path | None = None,
    ):
        """Create a HydraConfig with test-friendly defaults."""
        from config import HydraConfig

        root = repo_root or Path("/tmp/hydra-test-repo")
        return HydraConfig(
            label=label,
            batch_size=batch_size,
            max_workers=max_workers,
            max_budget_usd=max_budget_usd,
            model=model,
            review_model=review_model,
            review_budget_usd=review_budget_usd,
            repo=repo,
            dry_run=dry_run,
            dashboard_enabled=dashboard_enabled,
            dashboard_port=dashboard_port,
            repo_root=root,
            worktree_base=worktree_base or root.parent / "test-worktrees",
            state_file=state_file or root / ".hydra-state.json",
        )


@pytest.fixture
def config(tmp_path: Path) -> HydraConfig:
    """A HydraConfig using tmp_path for all file operations."""

    return ConfigFactory.create(
        repo_root=tmp_path / "repo",
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )


@pytest.fixture
def dry_config(tmp_path: Path) -> HydraConfig:
    """A HydraConfig in dry-run mode."""
    return ConfigFactory.create(
        dry_run=True,
        repo_root=tmp_path / "repo",
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )


# --- Issue Factory ---


class IssueFactory:
    """Factory for GitHubIssue instances."""

    @staticmethod
    def create(
        *,
        number: int = 42,
        title: str = "Fix the frobnicator",
        body: str = "The frobnicator is broken. Please fix it.",
        labels: list[str] | None = None,
        comments: list[str] | None = None,
        url: str = "",
    ):
        from models import GitHubIssue

        return GitHubIssue(
            number=number,
            title=title,
            body=body,
            labels=labels or ["ready"],
            comments=comments or [],
            url=url or f"https://github.com/test-org/test-repo/issues/{number}",
        )


@pytest.fixture
def issue() -> GitHubIssue:
    return IssueFactory.create()


# --- Worker Result Factory ---


class WorkerResultFactory:
    """Factory for WorkerResult instances."""

    @staticmethod
    def create(
        *,
        issue_number: int = 42,
        branch: str = "agent/issue-42",
        success: bool = True,
        transcript: str = "Implemented the feature.",
        commits: int = 1,
        worktree_path: str = "/tmp/worktrees/issue-42",
    ):
        from models import WorkerResult

        return WorkerResult(
            issue_number=issue_number,
            branch=branch,
            success=success,
            transcript=transcript,
            commits=commits,
            worktree_path=worktree_path,
        )


@pytest.fixture
def worker_result() -> WorkerResult:
    return WorkerResultFactory.create()


# --- PR Info Factory ---


class PRInfoFactory:
    """Factory for PRInfo instances."""

    @staticmethod
    def create(
        *,
        number: int = 101,
        issue_number: int = 42,
        branch: str = "agent/issue-42",
        url: str = "https://github.com/test-org/test-repo/pull/101",
        draft: bool = False,
    ):
        from models import PRInfo

        return PRInfo(
            number=number,
            issue_number=issue_number,
            branch=branch,
            url=url,
            draft=draft,
        )


@pytest.fixture
def pr_info() -> PRInfo:
    return PRInfoFactory.create()


# --- Event Bus Fixture ---


@pytest.fixture
def event_bus():
    from events import EventBus

    return EventBus()


# --- Subprocess Mock ---


class SubprocessMockBuilder:
    """Fluent builder for mocking asyncio.create_subprocess_exec."""

    def __init__(self) -> None:
        self._returncode = 0
        self._stdout = b""
        self._stderr = b""

    def with_returncode(self, code: int) -> SubprocessMockBuilder:
        self._returncode = code
        return self

    def with_stdout(self, data: str | bytes) -> SubprocessMockBuilder:
        self._stdout = data.encode() if isinstance(data, str) else data
        return self

    def with_stderr(self, data: str | bytes) -> SubprocessMockBuilder:
        self._stderr = data.encode() if isinstance(data, str) else data
        return self

    def build(self) -> AsyncMock:
        """Build a mock for asyncio.create_subprocess_exec."""
        mock_proc = AsyncMock()
        mock_proc.returncode = self._returncode
        mock_proc.communicate = AsyncMock(return_value=(self._stdout, self._stderr))
        mock_proc.wait = AsyncMock(return_value=self._returncode)

        mock_create = AsyncMock(return_value=mock_proc)
        return mock_create


@pytest.fixture
def subprocess_mock() -> SubprocessMockBuilder:
    """Return a builder for subprocess mocks."""
    return SubprocessMockBuilder()
