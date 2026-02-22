"""Tests for triage.py — TriageRunner issue readiness evaluation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from events import EventBus, EventType
from models import TriageResult
from tests.conftest import IssueFactory
from triage import TriageRunner


@pytest.fixture
def runner(event_bus: EventBus) -> TriageRunner:
    from tests.helpers import ConfigFactory

    config = ConfigFactory.create()
    return TriageRunner(config, event_bus)


# ---------------------------------------------------------------------------
# Readiness evaluation
# ---------------------------------------------------------------------------


class TestEvaluateReadiness:
    """Tests for TriageRunner.evaluate readiness checks."""

    @pytest.mark.asyncio
    async def test_ready_when_title_and_body_sufficient(
        self, runner: TriageRunner
    ) -> None:
        issue = IssueFactory.create(
            number=1,
            title="Implement feature X for module Y",
            body="Detailed description of what needs to happen. " * 3,
            labels=[],
            url="",
        )
        result = await runner.evaluate(issue)
        assert result.ready is True
        assert result.reasons == []

    @pytest.mark.asyncio
    async def test_not_ready_when_body_empty(self, runner: TriageRunner) -> None:
        issue = IssueFactory.create(
            number=1, title="A good descriptive title", body="", labels=[], url=""
        )
        result = await runner.evaluate(issue)
        assert result.ready is False
        assert any("Body" in r for r in result.reasons)

    @pytest.mark.asyncio
    async def test_not_ready_when_body_too_short(self, runner: TriageRunner) -> None:
        issue = IssueFactory.create(
            number=1, title="A good descriptive title", body="Fix it", labels=[], url=""
        )
        result = await runner.evaluate(issue)
        assert result.ready is False
        assert any("Body" in r for r in result.reasons)

    @pytest.mark.asyncio
    async def test_not_ready_when_title_too_short(self, runner: TriageRunner) -> None:
        issue = IssueFactory.create(
            number=1, title="Fix", body="A" * 100, labels=[], url=""
        )
        result = await runner.evaluate(issue)
        assert result.ready is False
        assert any("Title" in r for r in result.reasons)

    @pytest.mark.asyncio
    async def test_not_ready_when_both_insufficient(self, runner: TriageRunner) -> None:
        issue = IssueFactory.create(
            number=1, title="Bug", body="short", labels=[], url=""
        )
        result = await runner.evaluate(issue)
        assert result.ready is False
        assert len(result.reasons) == 2

    @pytest.mark.asyncio
    async def test_returns_triage_result_type(self, runner: TriageRunner) -> None:
        issue = IssueFactory.create(
            number=1, title="A descriptive title", body="A" * 100, labels=[], url=""
        )
        result = await runner.evaluate(issue)
        assert isinstance(result, TriageResult)
        assert result.issue_number == 1


# ---------------------------------------------------------------------------
# Event publishing
# ---------------------------------------------------------------------------


class TestTriageEvents:
    """Tests for TRIAGE_UPDATE event emission."""

    @pytest.mark.asyncio
    async def test_evaluate_publishes_evaluating_and_done_events(
        self, runner: TriageRunner, event_bus: EventBus
    ) -> None:
        issue = IssueFactory.create(
            number=1, title="A descriptive title", body="A" * 100, labels=[], url=""
        )
        received: list = []
        queue = event_bus.subscribe()

        await runner.evaluate(issue)

        # Drain events
        while not queue.empty():
            received.append(await queue.get())

        triage_events = [e for e in received if e.type == EventType.TRIAGE_UPDATE]
        assert len(triage_events) == 2
        assert triage_events[0].data["status"] == "evaluating"
        assert triage_events[0].data["role"] == "triage"
        assert triage_events[1].data["status"] == "done"

    @pytest.mark.asyncio
    async def test_evaluate_events_carry_issue_number(
        self, runner: TriageRunner, event_bus: EventBus
    ) -> None:
        issue = IssueFactory.create(
            number=99, title="A descriptive title", body="A" * 100, labels=[], url=""
        )
        received: list = []
        queue = event_bus.subscribe()

        await runner.evaluate(issue)

        while not queue.empty():
            received.append(await queue.get())

        triage_events = [e for e in received if e.type == EventType.TRIAGE_UPDATE]
        assert all(e.data["issue"] == 99 for e in triage_events)

    @pytest.mark.asyncio
    async def test_evaluate_emits_transcript_lines(
        self, runner: TriageRunner, event_bus: EventBus
    ) -> None:
        issue = IssueFactory.create(
            number=42,
            title="Implement feature X for module Y",
            body="Detailed description of what needs to happen. " * 3,
            labels=[],
            url="",
        )
        received: list = []
        queue = event_bus.subscribe()

        await runner.evaluate(issue)

        while not queue.empty():
            received.append(await queue.get())

        transcript_events = [e for e in received if e.type == EventType.TRANSCRIPT_LINE]
        assert len(transcript_events) >= 2
        assert transcript_events[0].data["source"] == "triage"
        assert transcript_events[0].data["issue"] == 42
        assert "Evaluating" in transcript_events[0].data["line"]

    @pytest.mark.asyncio
    async def test_not_ready_transcript_shows_reasons(
        self, runner: TriageRunner, event_bus: EventBus
    ) -> None:
        issue = IssueFactory.create(
            number=7, title="Bug", body="short", labels=[], url=""
        )
        received: list = []
        queue = event_bus.subscribe()

        await runner.evaluate(issue)

        while not queue.empty():
            received.append(await queue.get())

        transcript_events = [e for e in received if e.type == EventType.TRANSCRIPT_LINE]
        lines = [e.data["line"] for e in transcript_events]
        assert any("needs more information" in line for line in lines)


# ---------------------------------------------------------------------------
# Dry-run mode
# ---------------------------------------------------------------------------


class TestTriageDryRun:
    """Tests for dry-run mode in TriageRunner."""

    @pytest.mark.asyncio
    async def test_dry_run_returns_ready_true(self, event_bus: EventBus) -> None:
        from tests.helpers import ConfigFactory

        config = ConfigFactory.create(dry_run=True)
        runner = TriageRunner(config, event_bus)
        issue = IssueFactory.create(number=1, title="Bug", body="", labels=[], url="")

        result = await runner.evaluate(issue)
        assert result.ready is True
        assert result.reasons == []
