"""Structural conformance tests for hexagonal port interfaces.

These tests assert that the concrete infrastructure adapters satisfy their
respective port protocols via runtime_checkable isinstance checks.

They do NOT test behaviour — that lives in the per-class test modules.
Their purpose is to catch regressions where a refactor silently removes a
method that the domain relies on through the port interface.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ports import PRPort, WorktreePort

# ---------------------------------------------------------------------------
# PRPort
# ---------------------------------------------------------------------------


class TestPRPortConformance:
    """PRManager must satisfy the PRPort protocol."""

    def test_pr_manager_satisfies_pr_port(self) -> None:
        """PRManager is a structural subtype of PRPort."""
        from pr_manager import PRManager

        # Build minimal PRManager without hitting GitHub
        config = MagicMock()
        config.repo = "org/repo"
        config.gh_token = None
        config.dry_run = False
        event_bus = MagicMock()

        mgr = PRManager(config, event_bus)
        assert isinstance(mgr, PRPort), (
            "PRManager no longer satisfies the PRPort protocol. "
            "Check that all methods declared in PRPort exist on PRManager."
        )

    def test_async_mock_satisfies_pr_port(self) -> None:
        """An AsyncMock spec'd to PRPort is accepted as PRPort (test helper check)."""
        mock: PRPort = AsyncMock(spec=PRPort)  # type: ignore[assignment]
        assert isinstance(mock, PRPort)


# ---------------------------------------------------------------------------
# WorktreePort
# ---------------------------------------------------------------------------


class TestWorktreePortConformance:
    """WorktreeManager must satisfy the WorktreePort protocol."""

    def test_worktree_manager_satisfies_worktree_port(self) -> None:
        """WorktreeManager is a structural subtype of WorktreePort."""
        from worktree import WorktreeManager

        config = MagicMock()
        config.worktree_base = Path("/tmp/wt")
        config.repo_root = Path("/tmp/repo")
        config.main_branch = "main"
        config.git_command_timeout = 30

        mgr = WorktreeManager(config)
        assert isinstance(mgr, WorktreePort), (
            "WorktreeManager no longer satisfies the WorktreePort protocol. "
            "Check that all methods declared in WorktreePort exist on WorktreeManager."
        )

    def test_async_mock_satisfies_worktree_port(self) -> None:
        """An AsyncMock spec'd to WorktreePort is accepted as WorktreePort."""
        mock: WorktreePort = AsyncMock(spec=WorktreePort)  # type: ignore[assignment]
        assert isinstance(mock, WorktreePort)


# ---------------------------------------------------------------------------
# Port method coverage
# ---------------------------------------------------------------------------


class TestPRPortMethods:
    """All methods declared in PRPort exist on the concrete PRManager."""

    _REQUIRED_METHODS = [
        "push_branch",
        "create_pr",
        "merge_pr",
        "get_pr_diff",
        "wait_for_ci",
        "add_labels",
        "remove_label",
        "swap_pipeline_labels",
        "post_comment",
        "submit_review",
        "fetch_ci_failure_logs",
        "close_issue",
        "create_issue",
        "list_hitl_items",
    ]

    @pytest.mark.parametrize("method", _REQUIRED_METHODS)
    def test_method_exists_on_pr_manager(self, method: str) -> None:
        from pr_manager import PRManager

        assert hasattr(PRManager, method), (
            f"PRManager is missing '{method}' which is declared in PRPort"
        )


class TestWorktreePortMethods:
    """All methods declared in WorktreePort exist on the concrete WorktreeManager."""

    _REQUIRED_METHODS = [
        "create",
        "destroy",
        "destroy_all",
        "merge_main",
        "get_conflicting_files",
    ]

    @pytest.mark.parametrize("method", _REQUIRED_METHODS)
    def test_method_exists_on_worktree_manager(self, method: str) -> None:
        from worktree import WorktreeManager

        assert hasattr(WorktreeManager, method), (
            f"WorktreeManager is missing '{method}' which is declared in WorktreePort"
        )
