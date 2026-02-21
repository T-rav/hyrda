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

    # --- review attempt tracking ---

    def get_review_attempts(self, issue_number: int) -> int:
        """Return the current review attempt count for *issue_number* (default 0)."""
        return self._data.review_attempts.get(str(issue_number), 0)

    def increment_review_attempts(self, issue_number: int) -> int:
        """Increment and return the new review attempt count for *issue_number*."""
        key = str(issue_number)
        current = self._data.review_attempts.get(key, 0)
        self._data.review_attempts[key] = current + 1
        self.save()
        return current + 1

    def reset_review_attempts(self, issue_number: int) -> None:
        """Clear the review attempt counter for *issue_number*."""
        self._data.review_attempts.pop(str(issue_number), None)
        self.save()

    # --- review feedback storage ---

    def set_review_feedback(self, issue_number: int, feedback: str) -> None:
        """Store review feedback for *issue_number*."""
        self._data.review_feedback[str(issue_number)] = feedback
        self.save()

    def get_review_feedback(self, issue_number: int) -> str | None:
        """Return stored review feedback for *issue_number*, or *None*."""
        return self._data.review_feedback.get(str(issue_number))

    def clear_review_feedback(self, issue_number: int) -> None:
        """Clear stored review feedback for *issue_number*."""
        self._data.review_feedback.pop(str(issue_number), None)
        self.save()

    # --- issue attempt tracking ---

    def get_issue_attempts(self, issue_number: int) -> int:
        """Return the current implementation attempt count for *issue_number* (default 0)."""
        return self._data.issue_attempts.get(str(issue_number), 0)

    def increment_issue_attempts(self, issue_number: int) -> int:
        """Increment and return the new implementation attempt count for *issue_number*."""
        key = str(issue_number)
        current = self._data.issue_attempts.get(key, 0)
        self._data.issue_attempts[key] = current + 1
        self.save()
        return current + 1

    def reset_issue_attempts(self, issue_number: int) -> None:
        """Clear the implementation attempt counter for *issue_number*."""
        self._data.issue_attempts.pop(str(issue_number), None)
        self.save()

    # --- active issue numbers ---

    def get_active_issue_numbers(self) -> list[int]:
        """Return the persisted list of active issue numbers."""
        return list(self._data.active_issue_numbers)

    def set_active_issue_numbers(self, numbers: list[int]) -> None:
        """Persist the current set of active issue numbers."""
        self._data.active_issue_numbers = numbers
        self.save()

    # --- worker result metadata ---

    def set_worker_result_meta(self, issue_number: int, meta: dict[str, Any]) -> None:
        """Persist worker result metadata for *issue_number*."""
        self._data.worker_result_meta[str(issue_number)] = meta
        self.save()

    def get_worker_result_meta(self, issue_number: int) -> dict[str, Any]:
        """Return worker result metadata for *issue_number*, or empty dict."""
        return self._data.worker_result_meta.get(str(issue_number), {})

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

    def record_quality_fix_rounds(self, count: int) -> None:
        """Accumulate quality fix rounds from an implementation run."""
        self._data.lifetime_stats.total_quality_fix_rounds += count
        self.save()

    def record_ci_fix_rounds(self, count: int) -> None:
        """Accumulate CI fix rounds from a review run."""
        self._data.lifetime_stats.total_ci_fix_rounds += count
        self.save()

    def record_hitl_escalation(self) -> None:
        """Increment the all-time HITL escalation counter."""
        self._data.lifetime_stats.total_hitl_escalations += 1
        self.save()

    def record_review_verdict(self, verdict: str, fixes_made: bool) -> None:
        """Record a review verdict in lifetime stats."""
        if verdict == "approve":
            self._data.lifetime_stats.total_review_approvals += 1
        elif verdict == "request-changes":
            self._data.lifetime_stats.total_review_request_changes += 1
        if fixes_made:
            self._data.lifetime_stats.total_reviewer_fixes += 1
        self.save()

    def record_implementation_duration(self, seconds: float) -> None:
        """Accumulate implementation agent duration."""
        self._data.lifetime_stats.total_implementation_seconds += seconds
        self.save()

    def record_review_duration(self, seconds: float) -> None:
        """Accumulate review agent duration."""
        self._data.lifetime_stats.total_review_seconds += seconds
        self.save()

    def get_lifetime_stats(self) -> dict[str, int | float]:
        """Return a copy of the lifetime stats counters."""
        return self._data.lifetime_stats.model_dump()

    # --- threshold tracking ---

    def get_fired_thresholds(self) -> list[str]:
        """Return list of threshold names that have already been fired."""
        return list(self._data.lifetime_stats.fired_thresholds)

    def mark_threshold_fired(self, name: str) -> None:
        """Record that a threshold proposal has been filed."""
        if name not in self._data.lifetime_stats.fired_thresholds:
            self._data.lifetime_stats.fired_thresholds.append(name)
            self.save()

    def clear_threshold_fired(self, name: str) -> None:
        """Clear a fired threshold when the metric recovers."""
        if name in self._data.lifetime_stats.fired_thresholds:
            self._data.lifetime_stats.fired_thresholds.remove(name)
            self.save()

    def check_thresholds(
        self,
        quality_fix_rate_threshold: float,
        approval_rate_threshold: float,
        hitl_rate_threshold: float,
    ) -> list[dict[str, str | float]]:
        """Check metrics against thresholds, return list of crossed thresholds.

        Returns a list of dicts with keys: name, metric, threshold, value, action.
        Only returns thresholds not already fired.  Clears fired flags for
        thresholds that have recovered.
        """
        stats = self._data.lifetime_stats
        total_issues = stats.issues_completed
        total_reviews = (
            stats.total_review_approvals + stats.total_review_request_changes
        )
        proposals: list[dict[str, str | float]] = []

        # Quality fix rate
        qf_rate = stats.total_quality_fix_rounds / total_issues if total_issues else 0.0
        if qf_rate > quality_fix_rate_threshold and total_issues >= 5:
            if "quality_fix_rate" not in stats.fired_thresholds:
                proposals.append(
                    {
                        "name": "quality_fix_rate",
                        "metric": "quality fix rate",
                        "threshold": quality_fix_rate_threshold,
                        "value": qf_rate,
                        "action": "Review implementation prompts — too many quality fixes needed",
                    }
                )
        elif "quality_fix_rate" in stats.fired_thresholds:
            self.clear_threshold_fired("quality_fix_rate")

        # First-pass approval rate
        approval_rate = (
            stats.total_review_approvals / total_reviews if total_reviews else 1.0
        )
        if approval_rate < approval_rate_threshold and total_reviews >= 5:
            if "approval_rate" not in stats.fired_thresholds:
                proposals.append(
                    {
                        "name": "approval_rate",
                        "metric": "first-pass approval rate",
                        "threshold": approval_rate_threshold,
                        "value": approval_rate,
                        "action": "Review code quality — approval rate is below threshold",
                    }
                )
        elif "approval_rate" in stats.fired_thresholds:
            self.clear_threshold_fired("approval_rate")

        # HITL escalation rate
        hitl_rate = stats.total_hitl_escalations / total_issues if total_issues else 0.0
        if hitl_rate > hitl_rate_threshold and total_issues >= 5:
            if "hitl_rate" not in stats.fired_thresholds:
                proposals.append(
                    {
                        "name": "hitl_rate",
                        "metric": "HITL escalation rate",
                        "threshold": hitl_rate_threshold,
                        "value": hitl_rate,
                        "action": "Investigate HITL escalation causes — too many issues need human intervention",
                    }
                )
        elif "hitl_rate" in stats.fired_thresholds:
            self.clear_threshold_fired("hitl_rate")

        return proposals
