"""Crash-recovery state persistence for Hydra."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("hydra.state")


class StateTracker:
    """JSON-file backed state for crash recovery.

    Writes ``<repo_root>/.hydra-state.json`` after every mutation.
    """

    def __init__(self, state_file: Path) -> None:
        self._path = state_file
        self._data: dict[str, Any] = self._defaults()
        self.load()

    # --- persistence ---

    def load(self) -> dict[str, Any]:
        """Load state from disk, or initialise defaults."""
        if self._path.exists():
            try:
                loaded = json.loads(self._path.read_text())
                if not isinstance(loaded, dict):
                    raise ValueError("State file must contain a JSON object")
                self._data = loaded
                logger.info("State loaded from %s", self._path)
            except (json.JSONDecodeError, OSError, ValueError) as exc:
                logger.warning("Corrupt state file, resetting: %s", exc)
                self._data = self._defaults()
        return self._data

    def save(self) -> None:
        """Flush current state to disk."""
        self._data["last_updated"] = datetime.now(UTC).isoformat()
        self._path.write_text(json.dumps(self._data, indent=2))

    # --- issue tracking ---

    def mark_issue(self, issue_number: int, status: str) -> None:
        """Record the processing status for *issue_number*."""
        self._data["processed_issues"][str(issue_number)] = status
        self.save()

    def is_processed(self, issue_number: int) -> bool:
        """Return *True* if the issue has been processed (success or failed)."""
        status = self._data["processed_issues"].get(str(issue_number))
        return status in ("success", "failed")

    def get_issue_status(self, issue_number: int) -> str | None:
        """Return the status string for *issue_number*, or *None*."""
        return self._data["processed_issues"].get(str(issue_number))

    # --- worktree tracking ---

    def get_active_worktrees(self) -> dict[int, str]:
        """Return ``{issue_number: worktree_path}`` mapping."""
        return {int(k): v for k, v in self._data["active_worktrees"].items()}

    def set_worktree(self, issue_number: int, path: str) -> None:
        self._data["active_worktrees"][str(issue_number)] = path
        self.save()

    def remove_worktree(self, issue_number: int) -> None:
        self._data["active_worktrees"].pop(str(issue_number), None)
        self.save()

    # --- branch tracking ---

    def set_branch(self, issue_number: int, branch: str) -> None:
        self._data["active_branches"][str(issue_number)] = branch
        self.save()

    def get_branch(self, issue_number: int) -> str | None:
        return self._data["active_branches"].get(str(issue_number))

    # --- PR tracking ---

    def mark_pr(self, pr_number: int, status: str) -> None:
        self._data["reviewed_prs"][str(pr_number)] = status
        self.save()

    def get_pr_status(self, pr_number: int) -> str | None:
        return self._data["reviewed_prs"].get(str(pr_number))

    # --- batch tracking ---

    def get_current_batch(self) -> int:
        return int(self._data.get("current_batch", 0))

    def increment_batch(self) -> int:
        self._data["current_batch"] = self.get_current_batch() + 1
        self.save()
        return self._data["current_batch"]

    # --- reset ---

    def reset(self) -> None:
        """Clear all state and persist."""
        self._data = self._defaults()
        self.save()

    def to_dict(self) -> dict[str, Any]:
        """Return a copy of the raw state dict."""
        return dict(self._data)

    # --- internals ---

    @staticmethod
    def _defaults() -> dict[str, Any]:
        return {
            "current_batch": 0,
            "processed_issues": {},
            "active_worktrees": {},
            "active_branches": {},
            "reviewed_prs": {},
            "last_updated": None,
        }
