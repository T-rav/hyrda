"""Tests for dx/hydra/events.py - EventType, HydraEvent, and EventBus."""

from __future__ import annotations

import asyncio

import pytest

from events import EventBus, EventType, HydraEvent

# ---------------------------------------------------------------------------
# EventType enum
# ---------------------------------------------------------------------------


class TestEventTypeEnum:
    def test_all_expected_values_exist(self) -> None:
        expected = {
            "BATCH_START",
            "PHASE_CHANGE",
            "WORKER_UPDATE",
            "TRANSCRIPT_LINE",
            "PR_CREATED",
            "REVIEW_UPDATE",
            "TRIAGE_UPDATE",
            "PLANNER_UPDATE",
            "MERGE_UPDATE",
            "CI_CHECK",
            "HITL_ESCALATION",
            "ISSUE_CREATED",
            "BATCH_COMPLETE",
            "HITL_UPDATE",
            "ORCHESTRATOR_STATUS",
            "ERROR",
            "MEMORY_SYNC",
            "RETROSPECTIVE",
            "METRICS_UPDATE",
            "REVIEW_INSIGHT",
            "BACKGROUND_WORKER_STATUS",
        }
        actual = {member.name for member in EventType}
        assert expected == actual

    def test_string_values(self) -> None:
        assert EventType.BATCH_START == "batch_start"
        assert EventType.PHASE_CHANGE == "phase_change"
        assert EventType.WORKER_UPDATE == "worker_update"
        assert EventType.TRANSCRIPT_LINE == "transcript_line"
        assert EventType.PR_CREATED == "pr_created"
        assert EventType.REVIEW_UPDATE == "review_update"
        assert EventType.TRIAGE_UPDATE == "triage_update"
        assert EventType.PLANNER_UPDATE == "planner_update"
        assert EventType.MERGE_UPDATE == "merge_update"
        assert EventType.ISSUE_CREATED == "issue_created"
        assert EventType.BATCH_COMPLETE == "batch_complete"
        assert EventType.HITL_UPDATE == "hitl_update"
        assert EventType.ORCHESTRATOR_STATUS == "orchestrator_status"
        assert EventType.ERROR == "error"

    def test_is_str_enum(self) -> None:
        """EventType values should be strings (subclass of str)."""
        for member in EventType:
            assert isinstance(member, str)

    def test_enum_comparison_with_string(self) -> None:
        assert EventType.ERROR == "error"
        assert EventType.ERROR == "error"


# ---------------------------------------------------------------------------
# HydraEvent
# ---------------------------------------------------------------------------


class TestHydraEvent:
    def test_creation_with_explicit_values(self) -> None:
        event = HydraEvent(
            type=EventType.BATCH_START,
            timestamp="2024-01-01T00:00:00+00:00",
            data={"batch": 1},
        )
        assert event.type == EventType.BATCH_START
        assert event.timestamp == "2024-01-01T00:00:00+00:00"
        assert event.data == {"batch": 1}

    def test_auto_timestamp_generated_when_omitted(self) -> None:
        event = HydraEvent(type=EventType.ERROR)
        assert event.timestamp is not None
        assert "T" in event.timestamp  # ISO 8601 contains 'T'

    def test_auto_timestamp_is_utc_iso_format(self) -> None:
        event = HydraEvent(type=EventType.ERROR)
        # UTC ISO strings end with '+00:00' or 'Z'
        assert "+" in event.timestamp or event.timestamp.endswith("Z")

    def test_data_defaults_to_empty_dict(self) -> None:
        event = HydraEvent(type=EventType.PHASE_CHANGE)
        assert event.data == {}

    def test_data_accepts_arbitrary_keys(self) -> None:
        payload = {"issue": 42, "phase": "review", "nested": {"key": "value"}}
        event = HydraEvent(type=EventType.PHASE_CHANGE, data=payload)
        assert event.data["issue"] == 42
        assert event.data["nested"]["key"] == "value"

    def test_two_events_have_independent_data(self) -> None:
        e1 = HydraEvent(type=EventType.WORKER_UPDATE, data={"id": 1})
        e2 = HydraEvent(type=EventType.WORKER_UPDATE, data={"id": 2})
        assert e1.data["id"] == 1
        assert e2.data["id"] == 2


# ---------------------------------------------------------------------------
# HydraEvent ID
# ---------------------------------------------------------------------------


class TestHydraEventId:
    def test_event_id_auto_generated(self) -> None:
        event = HydraEvent(type=EventType.BATCH_START)
        assert isinstance(event.id, int)

    def test_event_ids_are_unique(self) -> None:
        events = [HydraEvent(type=EventType.BATCH_START) for _ in range(10)]
        ids = [e.id for e in events]
        assert len(set(ids)) == 10

    def test_event_ids_are_monotonically_increasing(self) -> None:
        events = [HydraEvent(type=EventType.BATCH_START) for _ in range(5)]
        for i in range(1, len(events)):
            assert events[i].id > events[i - 1].id

    def test_event_id_included_in_serialization(self) -> None:
        event = HydraEvent(type=EventType.BATCH_START, data={"batch": 1})
        dumped = event.model_dump()
        assert "id" in dumped
        assert isinstance(dumped["id"], int)

        json_str = event.model_dump_json()
        assert '"id"' in json_str

    def test_explicit_event_id_preserved(self) -> None:
        event = HydraEvent(id=999, type=EventType.BATCH_START)
        assert event.id == 999


# ---------------------------------------------------------------------------
# EventBus - publish / subscribe
# ---------------------------------------------------------------------------


class TestEventBusPublishSubscribe:
    @pytest.mark.asyncio
    async def test_subscriber_receives_published_event(self) -> None:
        bus = EventBus()
        queue = bus.subscribe()

        event = HydraEvent(type=EventType.BATCH_START, data={"batch": 1})
        await bus.publish(event)

        received = queue.get_nowait()
        assert received is event

    @pytest.mark.asyncio
    async def test_multiple_subscribers_all_receive_event(self) -> None:
        bus = EventBus()
        q1 = bus.subscribe()
        q2 = bus.subscribe()
        q3 = bus.subscribe()

        event = HydraEvent(type=EventType.PR_CREATED, data={"pr": 42})
        await bus.publish(event)

        assert q1.get_nowait() is event
        assert q2.get_nowait() is event
        assert q3.get_nowait() is event

    @pytest.mark.asyncio
    async def test_publish_multiple_events_in_order(self) -> None:
        bus = EventBus()
        queue = bus.subscribe()

        e1 = HydraEvent(type=EventType.PHASE_CHANGE, data={"phase": "start"})
        e2 = HydraEvent(type=EventType.PHASE_CHANGE, data={"phase": "end"})
        await bus.publish(e1)
        await bus.publish(e2)

        assert queue.get_nowait() is e1
        assert queue.get_nowait() is e2

    @pytest.mark.asyncio
    async def test_subscribe_returns_asyncio_queue(self) -> None:
        bus = EventBus()
        queue = bus.subscribe()
        assert isinstance(queue, asyncio.Queue)

    @pytest.mark.asyncio
    async def test_no_subscribers_publish_does_not_raise(self) -> None:
        bus = EventBus()
        event = HydraEvent(type=EventType.BATCH_COMPLETE)
        await bus.publish(event)  # should not raise

    @pytest.mark.asyncio
    async def test_subscribe_with_custom_max_queue(self) -> None:
        bus = EventBus()
        queue = bus.subscribe(max_queue=10)
        assert queue.maxsize == 10


# ---------------------------------------------------------------------------
# Unsubscribe
# ---------------------------------------------------------------------------


class TestEventBusUnsubscribe:
    @pytest.mark.asyncio
    async def test_unsubscribed_queue_receives_no_further_events(self) -> None:
        bus = EventBus()
        queue = bus.subscribe()
        bus.unsubscribe(queue)

        await bus.publish(HydraEvent(type=EventType.ERROR))

        assert queue.empty()

    @pytest.mark.asyncio
    async def test_unsubscribe_only_removes_target_queue(self) -> None:
        bus = EventBus()
        q1 = bus.subscribe()
        q2 = bus.subscribe()
        bus.unsubscribe(q1)

        event = HydraEvent(type=EventType.MERGE_UPDATE)
        await bus.publish(event)

        assert q1.empty()
        assert q2.get_nowait() is event

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent_queue_is_noop(self) -> None:
        bus = EventBus()
        orphan: asyncio.Queue[HydraEvent] = asyncio.Queue()
        # Should not raise
        bus.unsubscribe(orphan)

    @pytest.mark.asyncio
    async def test_unsubscribe_same_queue_twice_is_noop(self) -> None:
        bus = EventBus()
        queue = bus.subscribe()
        bus.unsubscribe(queue)
        bus.unsubscribe(queue)  # second call should not raise


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


class TestEventBusHistory:
    @pytest.mark.asyncio
    async def test_get_history_returns_published_events(self) -> None:
        bus = EventBus()
        e1 = HydraEvent(type=EventType.BATCH_START)
        e2 = HydraEvent(type=EventType.BATCH_COMPLETE)
        await bus.publish(e1)
        await bus.publish(e2)

        history = bus.get_history()
        assert e1 in history
        assert e2 in history

    @pytest.mark.asyncio
    async def test_get_history_preserves_order(self) -> None:
        bus = EventBus()
        events = [
            HydraEvent(type=EventType.WORKER_UPDATE, data={"n": i}) for i in range(5)
        ]
        for event in events:
            await bus.publish(event)

        history = bus.get_history()
        assert history == events

    @pytest.mark.asyncio
    async def test_get_history_returns_copy(self) -> None:
        """Mutating the returned list must not affect internal history."""
        bus = EventBus()
        await bus.publish(HydraEvent(type=EventType.PHASE_CHANGE))

        history = bus.get_history()
        history.clear()

        assert len(bus.get_history()) == 1

    @pytest.mark.asyncio
    async def test_history_accumulates_across_publishes(self) -> None:
        bus = EventBus()
        for i in range(10):
            await bus.publish(HydraEvent(type=EventType.TRANSCRIPT_LINE, data={"i": i}))
        assert len(bus.get_history()) == 10

    @pytest.mark.asyncio
    async def test_empty_history_on_new_bus(self) -> None:
        bus = EventBus()
        assert bus.get_history() == []


# ---------------------------------------------------------------------------
# History cap (max_history)
# ---------------------------------------------------------------------------


class TestEventBusHistoryCap:
    @pytest.mark.asyncio
    async def test_history_capped_at_max_history(self) -> None:
        bus = EventBus(max_history=5)
        for i in range(10):
            await bus.publish(HydraEvent(type=EventType.TRANSCRIPT_LINE, data={"i": i}))

        history = bus.get_history()
        assert len(history) == 5

    @pytest.mark.asyncio
    async def test_history_retains_most_recent_events_when_capped(self) -> None:
        bus = EventBus(max_history=3)
        events = [
            HydraEvent(type=EventType.WORKER_UPDATE, data={"n": i}) for i in range(6)
        ]
        for event in events:
            await bus.publish(event)

        history = bus.get_history()
        # Should keep the last 3
        assert history == events[-3:]

    @pytest.mark.asyncio
    async def test_max_history_one_keeps_latest(self) -> None:
        bus = EventBus(max_history=1)
        e1 = HydraEvent(type=EventType.BATCH_START)
        e2 = HydraEvent(type=EventType.BATCH_COMPLETE)
        await bus.publish(e1)
        await bus.publish(e2)

        history = bus.get_history()
        assert len(history) == 1
        assert history[0] is e2

    @pytest.mark.asyncio
    async def test_history_not_exceeded_by_one(self) -> None:
        limit = 100
        bus = EventBus(max_history=limit)
        for _ in range(limit + 1):
            await bus.publish(HydraEvent(type=EventType.TRANSCRIPT_LINE))
        assert len(bus.get_history()) == limit


# ---------------------------------------------------------------------------
# Clear
# ---------------------------------------------------------------------------


class TestEventBusClear:
    @pytest.mark.asyncio
    async def test_clear_removes_history(self) -> None:
        bus = EventBus()
        await bus.publish(HydraEvent(type=EventType.BATCH_START))
        bus.clear()
        assert bus.get_history() == []

    @pytest.mark.asyncio
    async def test_clear_removes_subscribers(self) -> None:
        bus = EventBus()
        queue = bus.subscribe()
        bus.clear()

        # After clearing, publishing should not deliver to the old queue
        await bus.publish(HydraEvent(type=EventType.BATCH_COMPLETE))
        assert queue.empty()

    @pytest.mark.asyncio
    async def test_clear_on_empty_bus_does_not_raise(self) -> None:
        bus = EventBus()
        bus.clear()  # should not raise

    @pytest.mark.asyncio
    async def test_bus_usable_after_clear(self) -> None:
        bus = EventBus()
        await bus.publish(HydraEvent(type=EventType.BATCH_START))
        bus.clear()

        queue = bus.subscribe()
        event = HydraEvent(type=EventType.BATCH_COMPLETE)
        await bus.publish(event)

        assert queue.get_nowait() is event
        assert len(bus.get_history()) == 1


# ---------------------------------------------------------------------------
# Slow subscriber (queue full → drop oldest)
# ---------------------------------------------------------------------------


class TestEventBusSlowSubscriber:
    @pytest.mark.asyncio
    async def test_full_queue_does_not_block_publish(self) -> None:
        """Publishing to a full subscriber queue should not raise or block."""
        bus = EventBus()
        queue = bus.subscribe(max_queue=2)

        # Fill the queue
        for i in range(5):
            await bus.publish(HydraEvent(type=EventType.TRANSCRIPT_LINE, data={"i": i}))

        # Queue should still have exactly max_queue items
        assert queue.qsize() == 2

    @pytest.mark.asyncio
    async def test_full_queue_drops_oldest_and_keeps_newest(self) -> None:
        """When a subscriber's queue is full, the oldest event is dropped."""
        bus = EventBus()
        queue = bus.subscribe(max_queue=2)

        events = [
            HydraEvent(type=EventType.WORKER_UPDATE, data={"n": i}) for i in range(4)
        ]
        for event in events:
            await bus.publish(event)

        # We published 4 events into a queue of size 2.
        # The bus drops the oldest to make room for the newest, so we expect
        # the two most-recently delivered events.
        items = [queue.get_nowait(), queue.get_nowait()]
        assert len(items) == 2
        # The last event published must be present
        assert events[-1] in items

    @pytest.mark.asyncio
    async def test_slow_subscriber_does_not_affect_other_subscribers(self) -> None:
        """A full slow subscriber must not prevent a normal subscriber from receiving."""
        bus = EventBus()
        bus.subscribe(max_queue=1)
        fast_queue = bus.subscribe(max_queue=100)

        # Overflow the slow queue
        events = [
            HydraEvent(type=EventType.PHASE_CHANGE, data={"n": i}) for i in range(5)
        ]
        for event in events:
            await bus.publish(event)

        # Fast queue should have received all 5 events
        assert fast_queue.qsize() == 5

    @pytest.mark.asyncio
    async def test_history_unaffected_by_slow_subscriber(self) -> None:
        """Dropped events in a subscriber queue do not affect the history."""
        bus = EventBus()
        bus.subscribe(max_queue=1)  # tiny queue - will drop

        for i in range(10):
            await bus.publish(HydraEvent(type=EventType.TRANSCRIPT_LINE, data={"i": i}))

        # History should contain all 10, regardless of subscriber drops
        assert len(bus.get_history()) == 10


# ---------------------------------------------------------------------------
# Subscription context manager
# ---------------------------------------------------------------------------


class TestEventBusSubscription:
    async def test_subscription_yields_queue_that_receives_events(self) -> None:
        bus = EventBus()
        async with bus.subscription() as queue:
            event = HydraEvent(type=EventType.BATCH_START, data={"batch": 1})
            await bus.publish(event)
            received = queue.get_nowait()
            assert received is event

    async def test_subscription_unsubscribes_on_exit(self) -> None:
        bus = EventBus()
        async with bus.subscription() as queue:
            pass  # immediately exit

        # After exiting, queue should no longer receive events
        await bus.publish(HydraEvent(type=EventType.ERROR))
        assert queue.empty()
        assert len(bus._subscribers) == 0

    async def test_subscription_unsubscribes_on_exception(self) -> None:
        bus = EventBus()
        with __import__("contextlib").suppress(RuntimeError):
            async with bus.subscription():
                raise RuntimeError("boom")

        # Cleanup must have happened despite the exception
        assert len(bus._subscribers) == 0

    async def test_subscription_respects_max_queue(self) -> None:
        bus = EventBus()
        async with bus.subscription(max_queue=42) as queue:
            assert queue.maxsize == 42

    async def test_multiple_concurrent_subscriptions(self) -> None:
        bus = EventBus()
        async with bus.subscription() as q1:
            async with bus.subscription() as q2:
                event1 = HydraEvent(type=EventType.PHASE_CHANGE, data={"n": 1})
                await bus.publish(event1)
                assert q1.get_nowait() is event1
                assert q2.get_nowait() is event1

            # q2's context has exited; only q1 remains
            event2 = HydraEvent(type=EventType.PHASE_CHANGE, data={"n": 2})
            await bus.publish(event2)
            assert q1.get_nowait() is event2
            assert q2.empty()
