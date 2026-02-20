"""Crash-recovery state persistence for Hydra."""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from models import StateData

logger = logging.getLogger("hydra.state")


class StateTracker:
    """JSON-file backed state for crash recovery.

    Writes ``<repo_root>/.hydra/state.json`` after every mutation.
    """

    def __init__(self, state_file: Path) -> None:
        self._path = state_file
        self._data: StateData = StateData()
        self.load()

    # --- persistence ---

    def load(self) -> dict[str, Any]:
        """Load state from disk, or initialise defaults."""
        if self._path.exists():
            try:
                loaded = json.loads(self._path.read_text())
                if not isinstance(loaded, dict):
                    raise ValueError("State file must contain a JSON object")
                self._data = StateData.model_validate(loaded)
                logger.info("State loaded from %s", self._path)
            except (json.JSONDecodeError, OSError, ValueError) as exc:
                logger.warning("Corrupt state file, resetting: %s", exc)
                self._data = StateData()
        return self._data.model_dump()

    def save(self) -> None:
        """Flush current state to disk atomically."""
        self._data.last_updated = datetime.now(UTC).isoformat()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = self._data.model_dump_json(indent=2)
        # Write to a temp file in the same directory, fsync, then atomically
        # rename.  os.replace() is atomic on POSIX, so the state file is
        # always either the old version or the new version — never partial.
        fd, tmp = tempfile.mkstemp(
            dir=self._path.parent,
            prefix=".state-",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self._path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise

    # --- issue tracking ---

    def mark_issue(self, issue_number: int, status: str) -> None:
        """Record the processing status for *issue_number*."""
        self._data.processed_issues[str(issue_number)] = status
        self.save()

    def is_processed(self, issue_number: int) -> bool:
        """Return *True* if the issue was successfully processed.

        Failed issues are NOT considered processed so they can be
        retried on the next run.
        """
        return self._data.processed_issues.get(str(issue_number)) == "success"

    def get_issue_status(self, issue_number: int) -> str | None:
        """Return the status string for *issue_number*, or *None*."""
        return self._data.processed_issues.get(str(issue_number))

    # --- worktree tracking ---

    def get_active_worktrees(self) -> dict[int, str]:
        """Return ``{issue_number: worktree_path}`` mapping."""
        return {int(k): v for k, v in self._data.active_worktrees.items()}

    def set_worktree(self, issue_number: int, path: str) -> None:
        self._data.active_worktrees[str(issue_number)] = path
        self.save()

    def remove_worktree(self, issue_number: int) -> None:
        self._data.active_worktrees.pop(str(issue_number), None)
        self.save()

    # --- branch tracking ---

    def set_branch(self, issue_number: int, branch: str) -> None:
        self._data.active_branches[str(issue_number)] = branch
        self.save()

    def get_branch(self, issue_number: int) -> str | None:
        return self._data.active_branches.get(str(issue_number))

    # --- PR tracking ---

    def mark_pr(self, pr_number: int, status: str) -> None:
        self._data.reviewed_prs[str(pr_number)] = status
        self.save()

    def get_pr_status(self, pr_number: int) -> str | None:
        return self._data.reviewed_prs.get(str(pr_number))

    # --- HITL origin tracking ---

    def set_hitl_origin(self, issue_number: int, label: str) -> None:
        """Record the label that was active before HITL escalation."""
        self._data.hitl_origins[str(issue_number)] = label
        self.save()

    def get_hitl_origin(self, issue_number: int) -> str | None:
        """Return the pre-HITL label for *issue_number*, or *None*."""
        return self._data.hitl_origins.get(str(issue_number))

    def remove_hitl_origin(self, issue_number: int) -> None:
        """Clear the HITL origin record for *issue_number*."""
        self._data.hitl_origins.pop(str(issue_number), None)
        self.save()

    # --- HITL cause tracking ---

    def set_hitl_cause(self, issue_number: int, cause: str) -> None:
        """Record the escalation reason for *issue_number*."""
        self._data.hitl_causes[str(issue_number)] = cause
        self.save()

    def get_hitl_cause(self, issue_number: int) -> str | None:
        """Return the escalation reason for *issue_number*, or *None*."""
        return self._data.hitl_causes.get(str(issue_number))

    def remove_hitl_cause(self, issue_number: int) -> None:
        """Clear the escalation reason for *issue_number*."""
        self._data.hitl_causes.pop(str(issue_number), None)
        self.save()

    # --- batch tracking ---

    def get_current_batch(self) -> int:
        return self._data.current_batch

    def increment_batch(self) -> int:
        self._data.current_batch += 1
        self.save()
        return self._data.current_batch

    # --- reset ---

    def reset(self) -> None:
        """Clear all state and persist.  Lifetime stats are preserved."""
        saved_lifetime = self._data.lifetime_stats.model_copy()
        self._data = StateData(lifetime_stats=saved_lifetime)
        self.save()

    def to_dict(self) -> dict[str, Any]:
        """Return a copy of the raw state dict."""
        return self._data.model_dump()

    # --- memory tracking ---

    def update_memory_state(self, issue_ids: list[int], digest_hash: str) -> None:
        """Record the current set of memory issue IDs and digest hash."""
        self._data.memory_issue_ids = issue_ids
        self._data.memory_digest_hash = digest_hash
        self._data.memory_last_synced = datetime.now(UTC).isoformat()
        self.save()

    def get_memory_state(self) -> tuple[list[int], str, str | None]:
        """Return ``(issue_ids, digest_hash, last_synced)``."""
        return (
            list(self._data.memory_issue_ids),
            self._data.memory_digest_hash,
            self._data.memory_last_synced,
        )

    # --- lifetime stats ---

    def record_issue_completed(self) -> None:
        """Increment the all-time issues-completed counter."""
        self._data.lifetime_stats.issues_completed += 1
        self.save()

    def record_pr_merged(self) -> None:
        """Increment the all-time PRs-merged counter."""
        self._data.lifetime_stats.prs_merged += 1
        self.save()

    def record_issue_created(self) -> None:
        """Increment the all-time issues-created counter."""
        self._data.lifetime_stats.issues_created += 1
        self.save()

    def get_lifetime_stats(self) -> dict[str, int]:
        """Return a copy of the lifetime stats counters."""
        return self._data.lifetime_stats.model_dump()
