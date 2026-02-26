"""Hexagonal architecture port interfaces for HydraFlow.

Defines the formal boundaries between domain logic (phases, runners) and
infrastructure (GitHub API, git CLI, agent subprocesses).

## Port map

::

    Domain (phases)
        │
        ├─► TaskSource / TaskTransitioner  (task_source.py — already formal)
        ├─► PRPort                          (GitHub PR / label / CI operations)
        └─► WorktreePort                   (git worktree lifecycle)

Concrete adapters:
  - PRPort      → pr_manager.PRManager
  - WorktreePort → worktree.WorktreeManager

Both concrete classes satisfy their respective protocols via structural
subtyping (typing.runtime_checkable).  No changes to the concrete classes
are required.

Usage in tests — replace concrete classes with AsyncMock / stub::

    from unittest.mock import AsyncMock
    from ports import PRPort

    prs: PRPort = AsyncMock(spec=PRPort)  # type: ignore[assignment]
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, runtime_checkable

from typing_extensions import Protocol

from models import HITLItem, PRInfo

__all__ = ["PRPort", "WorktreePort"]


@runtime_checkable
class PRPort(Protocol):
    """Port for GitHub PR, label, and CI operations.

    Implemented by: ``pr_manager.PRManager``
    """

    # --- Branch / PR lifecycle ---

    async def push_branch(self, worktree_path: Path, branch: str) -> bool:
        """Push *branch* from *worktree_path* to origin. Returns True on success."""
        ...

    async def create_pr(
        self,
        issue_number: int,
        branch: str,
        worktree_path: Path,
        *args: Any,
        **kwargs: Any,
    ) -> PRInfo | None:
        """Create a pull request for *issue_number* on *branch*.

        Returns the created :class:`~models.PRInfo` or ``None`` on failure.
        """
        ...

    async def merge_pr(self, pr_number: int) -> bool:
        """Attempt to merge *pr_number*. Returns True if merged."""
        ...

    async def get_pr_diff(self, pr_number: int) -> str:
        """Return the unified diff for *pr_number* as a string."""
        ...

    async def wait_for_ci(
        self,
        pr_number: int,
        *args: Any,
        **kwargs: Any,
    ) -> tuple[bool, str]:
        """Poll CI checks for *pr_number* until done or timeout.

        Returns ``(passed, summary_message)``.
        """
        ...

    # --- Label management ---

    async def add_labels(self, issue_number: int, labels: list[str]) -> None:
        """Add *labels* to *issue_number*."""
        ...

    async def remove_label(self, issue_number: int, label: str) -> None:
        """Remove *label* from *issue_number* (no-op if absent)."""
        ...

    async def swap_pipeline_labels(
        self,
        issue_number: int,
        new_label: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Atomically replace the current pipeline label with *new_label*."""
        ...

    # --- Comments / review ---

    async def post_comment(self, task_id: int, body: str) -> None:
        """Post *body* as a comment on issue *task_id*."""
        ...

    async def submit_review(
        self,
        pr_number: int,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Submit a formal PR review (approve / request changes / comment)."""
        ...

    # --- CI / checks ---

    async def fetch_ci_failure_logs(self, pr_number: int) -> str:
        """Return aggregated CI failure logs for *pr_number*."""
        ...

    # --- Issue management ---

    async def close_issue(self, issue_number: int) -> None:
        """Close GitHub issue *issue_number*."""
        ...

    async def create_issue(
        self,
        title: str,
        body: str,
        *args: Any,
        **kwargs: Any,
    ) -> int:
        """Create a new GitHub issue. Returns the new issue number."""
        ...

    # --- HITL ---

    async def list_hitl_items(self, hitl_labels: list[str]) -> list[HITLItem]:
        """Return open issues carrying any of *hitl_labels*."""
        ...

    # --- TaskTransitioner compatibility ---
    # PRManager satisfies TaskTransitioner (post_comment, close_task,
    # transition, create_task) — those methods are defined on PRPort via the
    # shared post_comment above.  The remaining transition methods are
    # intentionally omitted here to keep PRPort focused on infrastructure
    # concerns; use TaskTransitioner from task_source for domain transitions.


@runtime_checkable
class WorktreePort(Protocol):
    """Port for git worktree lifecycle operations.

    Implemented by: ``worktree.WorktreeManager``
    """

    async def create(self, issue_number: int, branch: str) -> Path:
        """Create an isolated git worktree for *issue_number* on *branch*.

        Returns the path to the new worktree.
        """
        ...

    async def destroy(self, issue_number: int) -> None:
        """Remove the worktree for *issue_number* and clean up the branch."""
        ...

    async def destroy_all(self) -> None:
        """Remove all managed worktrees (used by ``make clean``)."""
        ...

    async def merge_main(self, worktree_path: Path, branch: str) -> bool:
        """Merge the main branch into the worktree. Returns True on success."""
        ...

    async def get_conflicting_files(self, worktree_path: Path) -> list[str]:
        """Return a list of files with merge conflicts in *worktree_path*."""
        ...
