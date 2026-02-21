"""Shared HITL escalation helper for the Hydra pipeline."""

from __future__ import annotations

from config import HydraConfig
from events import EventBus, HydraEvent
from pr_manager import PRManager
from state import StateTracker


class Escalator:
    """Performs the full HITL escalation sequence.

    Encapsulates the repeated pattern of recording state, swapping labels,
    publishing events, and posting comments that occurs across multiple
    pipeline phases.
    """

    def __init__(
        self,
        config: HydraConfig,
        state: StateTracker,
        prs: PRManager,
        bus: EventBus | None = None,
    ) -> None:
        self._config = config
        self._state = state
        self._prs = prs
        self._bus = bus

    async def escalate_to_hitl(
        self,
        issue_number: int,
        cause: str,
        origin_label: str,
        current_labels: list[str] | None = None,
        pr_number: int | None = None,
        comment: str = "",
        comment_on_pr: bool = False,
        event: HydraEvent | None = None,
    ) -> None:
        """Perform the full HITL escalation sequence.

        1. Post escalation comment (if provided).  When *comment_on_pr* is
           True and *pr_number* is given, the comment is posted on the PR;
           otherwise it falls back to the issue.
        2. Record HITL origin, cause, and escalation counter in state
        3. Remove *current_labels* from issue (and PR if *pr_number* given)
        4. Add HITL label to issue (and PR if *pr_number* given)
        5. Publish event (if provided and bus is set)
        """
        # 1. Post comment
        if comment:
            if comment_on_pr and pr_number is not None:
                await self._prs.post_pr_comment(pr_number, comment)
            else:
                await self._prs.post_comment(issue_number, comment)

        # 2. Record state
        self._state.set_hitl_origin(issue_number, origin_label)
        self._state.set_hitl_cause(issue_number, cause)
        self._state.record_hitl_escalation()

        # 3. Remove current labels from issue (and PR)
        if current_labels:
            for lbl in current_labels:
                await self._prs.remove_label(issue_number, lbl)
                if pr_number is not None:
                    await self._prs.remove_pr_label(pr_number, lbl)

        # 4. Add HITL label to issue (and PR)
        await self._prs.add_labels(issue_number, [self._config.hitl_label[0]])
        if pr_number is not None:
            await self._prs.add_pr_labels(pr_number, [self._config.hitl_label[0]])

        # 5. Publish event
        if event is not None and self._bus is not None:
            await self._bus.publish(event)
