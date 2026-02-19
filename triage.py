"""Triage agent — evaluates issue readiness before promoting to planning."""

from __future__ import annotations

import logging

from config import HydraConfig
from events import EventBus, EventType, HydraEvent
from models import GitHubIssue, TriageResult, TriageStatus

logger = logging.getLogger("hydra.triage")

# Minimum thresholds for issue readiness
_MIN_TITLE_LENGTH = 10
_MIN_BODY_LENGTH = 50


class TriageRunner:
    """Evaluates whether a GitHub issue has enough context for planning.

    Publishes ``TRIAGE_UPDATE`` events so the dashboard can show an
    active worker in the FIND column.
    """

    def __init__(self, config: HydraConfig, event_bus: EventBus) -> None:
        self._config = config
        self._bus = event_bus

    async def evaluate(
        self,
        issue: GitHubIssue,
        worker_id: int = 0,
    ) -> TriageResult:
        """Evaluate *issue* for readiness.

        Returns a :class:`TriageResult` indicating whether the issue
        has enough information to proceed to planning.
        """
        await self._emit_status(issue.number, worker_id, TriageStatus.EVALUATING)

        if self._config.dry_run:
            logger.info("[dry-run] Would evaluate issue #%d", issue.number)
            await self._emit_status(issue.number, worker_id, TriageStatus.DONE)
            return TriageResult(issue_number=issue.number, ready=True)

        reasons: list[str] = []

        if not issue.title or len(issue.title.strip()) < _MIN_TITLE_LENGTH:
            reasons.append(
                f"Title is too short (minimum {_MIN_TITLE_LENGTH} characters)"
            )
        if not issue.body or len(issue.body.strip()) < _MIN_BODY_LENGTH:
            reasons.append(
                f"Body is too short or empty "
                f"(minimum {_MIN_BODY_LENGTH} characters of description)"
            )

        ready = len(reasons) == 0
        result = TriageResult(issue_number=issue.number, ready=ready, reasons=reasons)

        await self._emit_status(issue.number, worker_id, TriageStatus.DONE)
        logger.info(
            "Issue #%d evaluated: ready=%s reasons=%s",
            issue.number,
            ready,
            reasons or "none",
        )
        return result

    async def _emit_status(
        self, issue_number: int, worker_id: int, status: TriageStatus
    ) -> None:
        """Publish a triage status event."""
        await self._bus.publish(
            HydraEvent(
                type=EventType.TRIAGE_UPDATE,
                data={
                    "issue": issue_number,
                    "worker": worker_id,
                    "status": status.value,
                    "role": "triage",
                },
            )
        )
