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

from tests.helpers import ConfigFactory  # noqa: E402

if TYPE_CHECKING:
    from typing import Any

    from config import HydraConfig
    from models import (
        GitHubIssue,
        PlanResult,
        PRInfo,
        ReviewResult,
        ReviewVerdict,
        WorkerResult,
    )
    from orchestrator import HydraOrchestrator


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


# --- Config Fixtures ---


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


# --- Plan Result Factory ---


class PlanResultFactory:
    """Factory for PlanResult instances."""

    @staticmethod
    def create(
        *,
        issue_number: int = 42,
        success: bool = True,
        plan: str = "## Plan\n\n1. Do the thing\n2. Test the thing",
        summary: str = "Plan to implement the feature",
        error: str | None = None,
        transcript: str = "PLAN_START\n## Plan\n\n1. Do the thing\nPLAN_END\nSUMMARY: Plan to implement the feature",
        duration_seconds: float = 10.0,
    ):
        from models import PlanResult

        return PlanResult(
            issue_number=issue_number,
            success=success,
            plan=plan,
            summary=summary,
            error=error,
            transcript=transcript,
            duration_seconds=duration_seconds,
        )


@pytest.fixture
def plan_result() -> PlanResult:
    return PlanResultFactory.create()


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


# --- Review Mock Builder ---


class ReviewMockBuilder:
    """Fluent builder for _review_prs test mocks."""

    def __init__(self, orch: HydraOrchestrator, config: HydraConfig) -> None:
        self._orch = orch
        self._config = config
        self._verdict: ReviewVerdict | None = None
        self._review_result: ReviewResult | None = None
        self._review_side_effect: Any = None
        self._merge_return: bool = True
        self._diff_text: str = "diff text"
        self._issue_number: int = 42
        self._pr_methods: dict[str, Any] = {}

    def with_verdict(self, verdict: ReviewVerdict) -> ReviewMockBuilder:
        self._verdict = verdict
        return self

    def with_review_result(self, result: ReviewResult) -> ReviewMockBuilder:
        self._review_result = result
        return self

    def with_review_side_effect(self, side_effect: Any) -> ReviewMockBuilder:
        self._review_side_effect = side_effect
        return self

    def with_merge_return(self, value: bool) -> ReviewMockBuilder:
        self._merge_return = value
        return self

    def with_issue_number(self, number: int) -> ReviewMockBuilder:
        self._issue_number = number
        return self

    def with_pr_method(self, name: str, mock: Any) -> ReviewMockBuilder:
        """Override a specific mock_prs method."""
        self._pr_methods[name] = mock
        return self

    def build(self) -> tuple[AsyncMock, AsyncMock, AsyncMock]:
        """Wire mocks into orch and return (mock_reviewers, mock_prs, mock_wt)."""
        from models import ReviewResult as RR
        from models import ReviewVerdict as RV

        # Reviewer mock
        mock_reviewers = AsyncMock()
        if self._review_side_effect:
            mock_reviewers.review = self._review_side_effect
        else:
            verdict = self._verdict if self._verdict is not None else RV.APPROVE
            result = self._review_result or RR(
                pr_number=101,
                issue_number=self._issue_number,
                verdict=verdict,
                summary="Looks good.",
                fixes_made=False,
            )
            mock_reviewers.review = AsyncMock(return_value=result)
        self._orch._reviewers = mock_reviewers

        # PR manager mock
        mock_prs = AsyncMock()
        mock_prs.get_pr_diff = AsyncMock(return_value=self._diff_text)
        mock_prs.push_branch = AsyncMock(return_value=True)
        mock_prs.merge_pr = AsyncMock(return_value=self._merge_return)
        mock_prs.remove_label = AsyncMock()
        mock_prs.add_labels = AsyncMock()
        mock_prs.post_pr_comment = AsyncMock()
        mock_prs.submit_review = AsyncMock(return_value=True)
        mock_prs.pull_main = AsyncMock()
        for name, mock in self._pr_methods.items():
            setattr(mock_prs, name, mock)
        self._orch._prs = mock_prs

        # Worktree mock
        mock_wt = AsyncMock()
        mock_wt.destroy = AsyncMock()
        self._orch._worktrees = mock_wt

        # Create worktree directory
        wt = self._config.worktree_base / f"issue-{self._issue_number}"
        wt.mkdir(parents=True, exist_ok=True)

        return mock_reviewers, mock_prs, mock_wt
