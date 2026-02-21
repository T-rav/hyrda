"""Tests for escalation.py — Escalator class."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config import HydraConfig

from escalation import Escalator
from events import EventBus, EventType, HydraEvent
from state import StateTracker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_escalator(
    config: HydraConfig,
    *,
    bus: EventBus | None = None,
) -> tuple[Escalator, StateTracker, AsyncMock, EventBus | None]:
    """Build an Escalator with a real StateTracker and mocked PRManager."""
    state = StateTracker(config.state_file)
    mock_prs = AsyncMock()
    escalator = Escalator(config, state, mock_prs, bus)
    return escalator, state, mock_prs, bus


# ---------------------------------------------------------------------------
# State recording
# ---------------------------------------------------------------------------


class TestStateRecording:
    """Verify that escalate_to_hitl records the correct state."""

    @pytest.mark.asyncio
    async def test_escalate_sets_hitl_origin(self, config: HydraConfig) -> None:
        escalator, state, _, _ = _make_escalator(config)

        await escalator.escalate_to_hitl(
            issue_number=42,
            cause="Test cause",
            origin_label="hydra-review",
        )

        assert state.get_hitl_origin(42) == "hydra-review"

    @pytest.mark.asyncio
    async def test_escalate_sets_hitl_cause(self, config: HydraConfig) -> None:
        escalator, state, _, _ = _make_escalator(config)

        await escalator.escalate_to_hitl(
            issue_number=42,
            cause="Merge conflict with main branch",
            origin_label="hydra-review",
        )

        assert state.get_hitl_cause(42) == "Merge conflict with main branch"

    @pytest.mark.asyncio
    async def test_escalate_records_hitl_counter(self, config: HydraConfig) -> None:
        escalator, state, _, _ = _make_escalator(config)

        await escalator.escalate_to_hitl(
            issue_number=42,
            cause="Test cause",
            origin_label="hydra-review",
        )

        stats = state.get_lifetime_stats()
        assert stats["total_hitl_escalations"] == 1


# ---------------------------------------------------------------------------
# Label operations
# ---------------------------------------------------------------------------


class TestLabelOperations:
    """Verify label add/remove operations on issues and PRs."""

    @pytest.mark.asyncio
    async def test_escalate_removes_current_labels_from_issue(
        self, config: HydraConfig
    ) -> None:
        escalator, _, mock_prs, _ = _make_escalator(config)

        await escalator.escalate_to_hitl(
            issue_number=42,
            cause="Test",
            origin_label="hydra-review",
            current_labels=["hydra-review"],
        )

        mock_prs.remove_label.assert_awaited_once_with(42, "hydra-review")

    @pytest.mark.asyncio
    async def test_escalate_adds_hitl_label_to_issue(self, config: HydraConfig) -> None:
        escalator, _, mock_prs, _ = _make_escalator(config)

        await escalator.escalate_to_hitl(
            issue_number=42,
            cause="Test",
            origin_label="hydra-review",
        )

        mock_prs.add_labels.assert_awaited_once_with(42, [config.hitl_label[0]])

    @pytest.mark.asyncio
    async def test_escalate_adds_labels_to_pr_when_pr_number_provided(
        self, config: HydraConfig
    ) -> None:
        escalator, _, mock_prs, _ = _make_escalator(config)

        await escalator.escalate_to_hitl(
            issue_number=42,
            cause="Test",
            origin_label="hydra-review",
            current_labels=["hydra-review"],
            pr_number=101,
        )

        mock_prs.add_pr_labels.assert_awaited_once_with(101, [config.hitl_label[0]])

    @pytest.mark.asyncio
    async def test_escalate_removes_labels_from_pr_when_pr_number_provided(
        self, config: HydraConfig
    ) -> None:
        escalator, _, mock_prs, _ = _make_escalator(config)

        await escalator.escalate_to_hitl(
            issue_number=42,
            cause="Test",
            origin_label="hydra-review",
            current_labels=["hydra-review"],
            pr_number=101,
        )

        mock_prs.remove_pr_label.assert_awaited_once_with(101, "hydra-review")

    @pytest.mark.asyncio
    async def test_escalate_skips_pr_operations_when_no_pr_number(
        self, config: HydraConfig
    ) -> None:
        escalator, _, mock_prs, _ = _make_escalator(config)

        await escalator.escalate_to_hitl(
            issue_number=42,
            cause="Test",
            origin_label="hydra-review",
            current_labels=["hydra-review"],
        )

        mock_prs.add_pr_labels.assert_not_awaited()
        mock_prs.remove_pr_label.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_escalate_skips_label_removal_when_no_current_labels(
        self, config: HydraConfig
    ) -> None:
        escalator, _, mock_prs, _ = _make_escalator(config)

        await escalator.escalate_to_hitl(
            issue_number=42,
            cause="Test",
            origin_label="hydra-find",
        )

        mock_prs.remove_label.assert_not_awaited()
        # HITL label should still be added
        mock_prs.add_labels.assert_awaited_once_with(42, [config.hitl_label[0]])


# ---------------------------------------------------------------------------
# Event publishing
# ---------------------------------------------------------------------------


class TestEventPublishing:
    """Verify event bus interactions."""

    @pytest.mark.asyncio
    async def test_escalate_publishes_event_when_provided(
        self, config: HydraConfig
    ) -> None:
        bus = EventBus()
        escalator, _, _, _ = _make_escalator(config, bus=bus)

        event = HydraEvent(
            type=EventType.HITL_ESCALATION,
            data={"issue": 42, "pr": 101, "cause": "merge_conflict"},
        )
        await escalator.escalate_to_hitl(
            issue_number=42,
            cause="Merge conflict",
            origin_label="hydra-review",
            event=event,
        )

        history = bus.get_history()
        escalation_events = [e for e in history if e.type == EventType.HITL_ESCALATION]
        assert len(escalation_events) == 1
        assert escalation_events[0].data["issue"] == 42

    @pytest.mark.asyncio
    async def test_escalate_skips_event_when_none(self, config: HydraConfig) -> None:
        bus = EventBus()
        escalator, _, _, _ = _make_escalator(config, bus=bus)

        await escalator.escalate_to_hitl(
            issue_number=42,
            cause="Test",
            origin_label="hydra-review",
        )

        history = bus.get_history()
        assert len(history) == 0

    @pytest.mark.asyncio
    async def test_escalate_skips_event_when_no_bus(self, config: HydraConfig) -> None:
        escalator, _, _, _ = _make_escalator(config, bus=None)

        event = HydraEvent(
            type=EventType.HITL_ESCALATION,
            data={"issue": 42},
        )
        # Should not raise even though bus is None
        await escalator.escalate_to_hitl(
            issue_number=42,
            cause="Test",
            origin_label="hydra-review",
            event=event,
        )


# ---------------------------------------------------------------------------
# Comment posting
# ---------------------------------------------------------------------------


class TestCommentPosting:
    """Verify comment posting to issues and PRs."""

    @pytest.mark.asyncio
    async def test_escalate_posts_comment_to_issue(self, config: HydraConfig) -> None:
        escalator, _, mock_prs, _ = _make_escalator(config)

        await escalator.escalate_to_hitl(
            issue_number=42,
            cause="Test",
            origin_label="hydra-review",
            comment="Escalating to human review.",
        )

        mock_prs.post_comment.assert_awaited_once_with(
            42, "Escalating to human review."
        )
        mock_prs.post_pr_comment.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_escalate_posts_comment_to_pr(self, config: HydraConfig) -> None:
        escalator, _, mock_prs, _ = _make_escalator(config)

        await escalator.escalate_to_hitl(
            issue_number=42,
            cause="Test",
            origin_label="hydra-review",
            pr_number=101,
            comment="CI failed — escalating.",
            comment_on_pr=True,
        )

        mock_prs.post_pr_comment.assert_awaited_once_with(
            101, "CI failed — escalating."
        )
        mock_prs.post_comment.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_escalate_posts_comment_to_issue_when_comment_on_pr_but_no_pr_number(
        self, config: HydraConfig
    ) -> None:
        """comment_on_pr=True without pr_number falls back to issue comment."""
        escalator, _, mock_prs, _ = _make_escalator(config)

        await escalator.escalate_to_hitl(
            issue_number=42,
            cause="Test",
            origin_label="hydra-review",
            comment="Escalating to human review.",
            comment_on_pr=True,
            # pr_number intentionally omitted
        )

        mock_prs.post_comment.assert_awaited_once_with(
            42, "Escalating to human review."
        )
        mock_prs.post_pr_comment.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_escalate_skips_comment_when_empty(self, config: HydraConfig) -> None:
        escalator, _, mock_prs, _ = _make_escalator(config)

        await escalator.escalate_to_hitl(
            issue_number=42,
            cause="Test",
            origin_label="hydra-review",
            comment="",
        )

        mock_prs.post_comment.assert_not_awaited()
        mock_prs.post_pr_comment.assert_not_awaited()
