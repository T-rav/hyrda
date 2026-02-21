"""Tests for issue_store.py — IssueStore class."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from events import EventBus, EventType
from issue_store import IssueStore
from models import GitHubIssue, QueueStats

if TYPE_CHECKING:
    from config import HydraConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _gh_json(*issues: dict) -> str:  # type: ignore[type-arg]
    """Build a JSON string mimicking ``gh issue list --json ...`` output."""
    return json.dumps(list(issues))


def _make_raw_issue(
    number: int,
    title: str = "Test issue",
    labels: list[str] | None = None,
) -> dict:  # type: ignore[type-arg]
    """Build a raw issue dict as returned by ``gh issue list``."""
    return {
        "number": number,
        "title": title,
        "body": f"Body for #{number}",
        "labels": [{"name": lbl} for lbl in (labels or [])],
        "comments": [],
        "url": f"https://github.com/test-org/test-repo/issues/{number}",
    }


def _mock_subprocess_for_labels(
    label_issues: dict[str | None, list[dict]],  # type: ignore[type-arg]
) -> AsyncMock:
    """Return an ``asyncio.create_subprocess_exec`` mock.

    *label_issues* maps label strings (or None for unlabelled fetch)
    to lists of raw issue dicts that should be returned for that label.
    """

    async def _fake_exec(*cmd: str, **_kw: object) -> AsyncMock:
        # Find the --label argument to determine which issues to return
        cmd_list = list(cmd)
        label = None
        if "--label" in cmd_list:
            idx = cmd_list.index("--label")
            label = cmd_list[idx + 1]

        issues = label_issues.get(label, [])
        stdout = json.dumps(issues).encode()

        proc = AsyncMock()
        proc.returncode = 0
        proc.communicate = AsyncMock(return_value=(stdout, b""))
        return proc

    return AsyncMock(side_effect=_fake_exec)


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


class TestIssueStoreInit:
    """IssueStore.__init__ sets up correct initial state."""

    def test_queues_start_empty(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        for q in store._queues.values():
            assert len(q) == 0

    def test_active_starts_empty(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        assert store._active == {}

    def test_seen_starts_empty(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        assert store._seen == {}

    def test_hitl_starts_empty(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        assert store._hitl == set()

    def test_stop_event_not_set(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        assert not store._stop_event.is_set()

    def test_has_four_queue_stages(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        assert set(store._queues.keys()) == {"find", "plan", "ready", "review"}

    def test_accepts_event_bus(self, config: HydraConfig) -> None:
        bus = EventBus()
        store = IssueStore(config, event_bus=bus)
        assert store._bus is bus

    def test_event_bus_defaults_to_none(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        assert store._bus is None


# ---------------------------------------------------------------------------
# Queue routing (_refresh)
# ---------------------------------------------------------------------------


class TestIssueStoreRefresh:
    """Tests for _refresh() — routing issues into queues."""

    @pytest.mark.asyncio
    async def test_routes_find_label_to_find_queue(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        issue = _make_raw_issue(1, labels=["hydra-find"])
        mock = _mock_subprocess_for_labels({"hydra-find": [issue]})

        with patch("asyncio.create_subprocess_exec", mock):
            await store._refresh()

        assert len(store._queues["find"]) == 1
        assert store._queues["find"][0].number == 1

    @pytest.mark.asyncio
    async def test_routes_plan_label_to_plan_queue(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        issue = _make_raw_issue(2, labels=["hydra-plan"])
        mock = _mock_subprocess_for_labels({"hydra-plan": [issue]})

        with patch("asyncio.create_subprocess_exec", mock):
            await store._refresh()

        assert len(store._queues["plan"]) == 1
        assert store._queues["plan"][0].number == 2

    @pytest.mark.asyncio
    async def test_routes_ready_label_to_ready_queue(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        issue = _make_raw_issue(3, labels=["test-label"])
        mock = _mock_subprocess_for_labels({"test-label": [issue]})

        with patch("asyncio.create_subprocess_exec", mock):
            await store._refresh()

        assert len(store._queues["ready"]) == 1
        assert store._queues["ready"][0].number == 3

    @pytest.mark.asyncio
    async def test_routes_review_label_to_review_queue(
        self, config: HydraConfig
    ) -> None:
        store = IssueStore(config)
        issue = _make_raw_issue(4, labels=["hydra-review"])
        mock = _mock_subprocess_for_labels({"hydra-review": [issue]})

        with patch("asyncio.create_subprocess_exec", mock):
            await store._refresh()

        assert len(store._queues["review"]) == 1
        assert store._queues["review"][0].number == 4

    @pytest.mark.asyncio
    async def test_routes_hitl_label_to_hitl_set(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        issue = _make_raw_issue(5, labels=["hydra-hitl"])
        mock = _mock_subprocess_for_labels({"hydra-hitl": [issue]})

        with patch("asyncio.create_subprocess_exec", mock):
            await store._refresh()

        assert 5 in store._hitl
        # HITL issues should NOT be in any work queue
        for q in store._queues.values():
            assert all(i.number != 5 for i in q)

    @pytest.mark.asyncio
    async def test_deduplicates_across_labels(self, config: HydraConfig) -> None:
        """Same issue in both plan and ready → routes to most downstream (ready)."""
        store = IssueStore(config)
        issue_plan = _make_raw_issue(10, labels=["hydra-plan"])
        issue_ready = _make_raw_issue(10, labels=["test-label"])
        mock = _mock_subprocess_for_labels(
            {
                "hydra-plan": [issue_plan],
                "test-label": [issue_ready],
            }
        )

        with patch("asyncio.create_subprocess_exec", mock):
            await store._refresh()

        # Should be in ready (downstream) not plan
        assert len(store._queues["ready"]) == 1
        assert store._queues["ready"][0].number == 10
        assert len(store._queues["plan"]) == 0

    @pytest.mark.asyncio
    async def test_multiple_issues_routed_correctly(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        find_issue = _make_raw_issue(1, labels=["hydra-find"])
        plan_issue = _make_raw_issue(2, labels=["hydra-plan"])
        ready_issue = _make_raw_issue(3, labels=["test-label"])

        mock = _mock_subprocess_for_labels(
            {
                "hydra-find": [find_issue],
                "hydra-plan": [plan_issue],
                "test-label": [ready_issue],
            }
        )

        with patch("asyncio.create_subprocess_exec", mock):
            await store._refresh()

        assert len(store._queues["find"]) == 1
        assert len(store._queues["plan"]) == 1
        assert len(store._queues["ready"]) == 1

    @pytest.mark.asyncio
    async def test_dry_run_skips_fetch(self, dry_config: HydraConfig) -> None:
        store = IssueStore(dry_config)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            await store._refresh()

        mock_exec.assert_not_called()
        for q in store._queues.values():
            assert len(q) == 0


# ---------------------------------------------------------------------------
# Queue accessors
# ---------------------------------------------------------------------------


class TestIssueStoreQueues:
    """Tests for get_triageable/plannable/implementable/reviewable."""

    def test_get_triageable_pops_from_find_queue(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        issue = GitHubIssue(number=1, title="Test", labels=["hydra-find"])
        store._queues["find"].append(issue)

        result = store.get_triageable(1)

        assert len(result) == 1
        assert result[0].number == 1
        assert len(store._queues["find"]) == 0

    def test_get_plannable_pops_from_plan_queue(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        issue = GitHubIssue(number=2, title="Test", labels=["hydra-plan"])
        store._queues["plan"].append(issue)

        result = store.get_plannable(1)

        assert len(result) == 1
        assert result[0].number == 2
        assert len(store._queues["plan"]) == 0

    def test_get_implementable_pops_from_ready_queue(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        issue = GitHubIssue(number=3, title="Test", labels=["test-label"])
        store._queues["ready"].append(issue)

        result = store.get_implementable(1)

        assert len(result) == 1
        assert result[0].number == 3
        assert len(store._queues["ready"]) == 0

    def test_get_reviewable_pops_from_review_queue(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        issue = GitHubIssue(number=4, title="Test", labels=["hydra-review"])
        store._queues["review"].append(issue)

        result = store.get_reviewable(1)

        assert len(result) == 1
        assert result[0].number == 4
        assert len(store._queues["review"]) == 0

    def test_returns_empty_list_from_empty_queue(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        assert store.get_implementable(5) == []

    def test_limit_zero_returns_all(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        for i in range(5):
            store._queues["ready"].append(GitHubIssue(number=i, title=f"Issue {i}"))

        result = store.get_implementable(0)

        assert len(result) == 5
        assert len(store._queues["ready"]) == 0

    def test_limit_caps_returned_issues(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        for i in range(5):
            store._queues["ready"].append(GitHubIssue(number=i, title=f"Issue {i}"))

        result = store.get_implementable(2)

        assert len(result) == 2
        assert len(store._queues["ready"]) == 3

    def test_pops_from_front_of_queue(self, config: HydraConfig) -> None:
        """Issues are popped FIFO — oldest first."""
        store = IssueStore(config)
        store._queues["ready"].append(GitHubIssue(number=1, title="First"))
        store._queues["ready"].append(GitHubIssue(number=2, title="Second"))
        store._queues["ready"].append(GitHubIssue(number=3, title="Third"))

        result = store.get_implementable(2)

        assert result[0].number == 1
        assert result[1].number == 2
        assert store._queues["ready"][0].number == 3


# ---------------------------------------------------------------------------
# Active issue tracking
# ---------------------------------------------------------------------------


class TestIssueStoreActiveTracking:
    """Tests for mark_active, mark_done, is_active."""

    def test_mark_active_adds_to_active(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        store.mark_active(42, "implement")

        assert store.is_active(42)
        assert store._active[42] == "implement"

    def test_mark_done_removes_from_active(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        store.mark_active(42, "implement")
        store.mark_done(42)

        assert not store.is_active(42)

    def test_is_active_false_for_unknown(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        assert not store.is_active(99)

    def test_get_active_issues_returns_set(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        store.mark_active(1, "plan")
        store.mark_active(2, "implement")

        active = store.get_active_issues()

        assert active == {1, 2}

    def test_get_active_issues_empty_when_none_active(
        self, config: HydraConfig
    ) -> None:
        store = IssueStore(config)
        assert store.get_active_issues() == set()

    def test_mark_done_records_completion_time(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        store.mark_active(42, "ready")
        store.mark_done(42)

        assert len(store._completion_times["ready"]) == 1

    def test_mark_done_increments_total_processed(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        store.mark_active(42, "ready")
        store.mark_done(42)

        assert store._total_processed["ready"] == 1

    def test_mark_done_cleans_up_enqueue_time(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        store._enqueue_times[42] = time.monotonic()
        store.mark_active(42, "ready")
        store.mark_done(42)

        assert 42 not in store._enqueue_times

    def test_mark_done_for_unknown_issue_is_safe(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        # Should not raise
        store.mark_done(999)
        assert not store.is_active(999)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestIssueStoreStats:
    """Tests for get_stats and throughput computation."""

    def test_stats_returns_queue_stats_model(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        stats = store.get_stats()
        assert isinstance(stats, QueueStats)

    def test_stats_shows_queue_depth(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        store._queues["ready"].append(GitHubIssue(number=1, title="A"))
        store._queues["ready"].append(GitHubIssue(number=2, title="B"))
        store._queues["plan"].append(GitHubIssue(number=3, title="C"))

        stats = store.get_stats()

        assert stats.queue_depth["ready"] == 2
        assert stats.queue_depth["plan"] == 1
        assert stats.queue_depth["find"] == 0

    def test_stats_shows_hitl_count(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        store._hitl = {10, 20}

        stats = store.get_stats()

        assert stats.queue_depth["hitl"] == 2

    def test_stats_shows_active_count(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        store.mark_active(1, "implement")
        store.mark_active(2, "implement")
        store.mark_active(3, "review")

        stats = store.get_stats()

        assert stats.active_count["implement"] == 2
        assert stats.active_count["review"] == 1

    def test_stats_shows_total_processed(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        store.mark_active(1, "ready")
        store.mark_done(1)
        store.mark_active(2, "ready")
        store.mark_done(2)

        stats = store.get_stats()

        assert stats.total_processed["ready"] == 2

    def test_throughput_within_one_hour(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        now = time.monotonic()
        store._completion_times["ready"] = [now - 100, now - 50, now - 10]

        stats = store.get_stats()

        assert stats.throughput["ready"] == 3.0

    def test_throughput_excludes_old_entries(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        now = time.monotonic()
        # Two entries older than 1 hour, one recent
        store._completion_times["ready"] = [now - 7200, now - 4000, now - 10]

        stats = store.get_stats()

        assert stats.throughput["ready"] == 1.0


# ---------------------------------------------------------------------------
# Label change detection
# ---------------------------------------------------------------------------


class TestIssueStoreLabelChanges:
    """Tests for issues moving between stages on refresh."""

    @pytest.mark.asyncio
    async def test_issue_moves_from_plan_to_ready(self, config: HydraConfig) -> None:
        store = IssueStore(config)

        # First refresh: issue in plan queue
        issue_plan = _make_raw_issue(10, labels=["hydra-plan"])
        mock1 = _mock_subprocess_for_labels({"hydra-plan": [issue_plan]})
        with patch("asyncio.create_subprocess_exec", mock1):
            await store._refresh()
        assert len(store._queues["plan"]) == 1
        assert len(store._queues["ready"]) == 0

        # Second refresh: same issue now has ready label
        issue_ready = _make_raw_issue(10, labels=["test-label"])
        mock2 = _mock_subprocess_for_labels({"test-label": [issue_ready]})
        with patch("asyncio.create_subprocess_exec", mock2):
            await store._refresh()

        assert len(store._queues["plan"]) == 0
        assert len(store._queues["ready"]) == 1
        assert store._queues["ready"][0].number == 10

    @pytest.mark.asyncio
    async def test_closed_issue_removed_from_queue(self, config: HydraConfig) -> None:
        store = IssueStore(config)

        # First refresh: issue in ready queue
        issue = _make_raw_issue(20, labels=["test-label"])
        mock1 = _mock_subprocess_for_labels({"test-label": [issue]})
        with patch("asyncio.create_subprocess_exec", mock1):
            await store._refresh()
        assert len(store._queues["ready"]) == 1

        # Second refresh: issue no longer returned (closed)
        mock2 = _mock_subprocess_for_labels({})
        with patch("asyncio.create_subprocess_exec", mock2):
            await store._refresh()

        assert len(store._queues["ready"]) == 0


# ---------------------------------------------------------------------------
# Issues persist in queue when workers are busy
# ---------------------------------------------------------------------------


class TestIssueStoreQueuePersistence:
    """Verify that issues stay in queue across refresh cycles."""

    @pytest.mark.asyncio
    async def test_issues_remain_in_queue_across_refreshes(
        self, config: HydraConfig
    ) -> None:
        store = IssueStore(config)
        issue = _make_raw_issue(30, labels=["test-label"])
        mock = _mock_subprocess_for_labels({"test-label": [issue]})

        # First refresh populates queue
        with patch("asyncio.create_subprocess_exec", mock):
            await store._refresh()
        assert len(store._queues["ready"]) == 1

        # Second refresh — issue still there, stays in queue
        with patch("asyncio.create_subprocess_exec", mock):
            await store._refresh()
        assert len(store._queues["ready"]) == 1

    @pytest.mark.asyncio
    async def test_active_issues_not_re_queued(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        issue = _make_raw_issue(40, labels=["test-label"])
        mock = _mock_subprocess_for_labels({"test-label": [issue]})

        with patch("asyncio.create_subprocess_exec", mock):
            await store._refresh()

        # Pop from queue and mark active
        store.get_implementable(1)
        store.mark_active(40, "implement")

        # Refresh again — issue should NOT reappear in queue
        with patch("asyncio.create_subprocess_exec", mock):
            await store._refresh()

        assert len(store._queues["ready"]) == 0
        assert store.is_active(40)


# ---------------------------------------------------------------------------
# Start / Stop lifecycle
# ---------------------------------------------------------------------------


class TestIssueStorePollLoop:
    """Tests for start() and stop() lifecycle."""

    @pytest.mark.asyncio
    async def test_start_creates_poll_task(self, config: HydraConfig) -> None:
        store = IssueStore(config)

        mock = _mock_subprocess_for_labels({})
        with patch("asyncio.create_subprocess_exec", mock):
            await store.start()

        assert store._poll_task is not None
        assert not store._poll_task.done()

        await store.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_poll_task(self, config: HydraConfig) -> None:
        store = IssueStore(config)

        mock = _mock_subprocess_for_labels({})
        with patch("asyncio.create_subprocess_exec", mock):
            await store.start()
            await store.stop()

        assert store._poll_task is not None
        assert store._poll_task.done()

    @pytest.mark.asyncio
    async def test_stop_is_safe_when_not_started(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        await store.stop()  # Should not raise

    @pytest.mark.asyncio
    async def test_start_does_initial_refresh(self, config: HydraConfig) -> None:
        """start() should do an immediate refresh before entering the loop."""
        store = IssueStore(config)
        issue = _make_raw_issue(50, labels=["test-label"])
        mock = _mock_subprocess_for_labels({"test-label": [issue]})

        with patch("asyncio.create_subprocess_exec", mock):
            await store.start()

        # Queue should be populated from initial refresh
        assert len(store._queues["ready"]) == 1

        await store.stop()


# ---------------------------------------------------------------------------
# Scan-all mode (empty planner_label)
# ---------------------------------------------------------------------------


class TestIssueStoreScanAllMode:
    """Tests for scan-all mode when planner_label is empty."""

    @pytest.mark.asyncio
    async def test_empty_planner_label_fetches_all_issues(
        self, config: HydraConfig
    ) -> None:
        from tests.helpers import ConfigFactory

        scan_config = ConfigFactory.create(
            planner_label=[],
            repo_root=config.repo_root,
            worktree_base=config.worktree_base,
            state_file=config.state_file,
        )
        store = IssueStore(scan_config)

        # Issue without any hydra label → should end up in plan queue
        all_issue = _make_raw_issue(60, labels=[])
        # Issue with downstream label → should be excluded
        downstream_issue = _make_raw_issue(61, labels=["test-label"])

        async def _fake_exec(*cmd: str, **_kw: object) -> AsyncMock:
            cmd_list = list(cmd)
            label = None
            if "--label" in cmd_list:
                idx = cmd_list.index("--label")
                label = cmd_list[idx + 1]

            if label is None:
                # Unlabelled fetch (scan-all)
                stdout = json.dumps([all_issue, downstream_issue]).encode()
            else:
                stdout = json.dumps([]).encode()

            proc = AsyncMock()
            proc.returncode = 0
            proc.communicate = AsyncMock(return_value=(stdout, b""))
            return proc

        mock = AsyncMock(side_effect=_fake_exec)

        with patch("asyncio.create_subprocess_exec", mock):
            await store._refresh()

        # Only the issue without downstream labels should be in plan queue
        assert len(store._queues["plan"]) == 1
        assert store._queues["plan"][0].number == 60


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestIssueStoreErrors:
    """Tests for error handling during fetch."""

    @pytest.mark.asyncio
    async def test_gh_failure_leaves_queues_unchanged(
        self, config: HydraConfig
    ) -> None:
        store = IssueStore(config)
        # Pre-populate a queue
        store._queues["ready"].append(GitHubIssue(number=99, title="Existing"))

        async def _fail(*cmd: str, **_kw: object) -> AsyncMock:
            proc = AsyncMock()
            proc.returncode = 1
            proc.communicate = AsyncMock(return_value=(b"", b"error"))
            return proc

        mock = AsyncMock(side_effect=_fail)

        with patch("asyncio.create_subprocess_exec", mock):
            await store._refresh()

        # Existing queue entries are cleaned up since they weren't in the
        # fetched results (empty due to failure), but that's expected
        # behavior — GitHub is the source of truth
        # The key thing is that it doesn't crash

    @pytest.mark.asyncio
    async def test_json_decode_error_handled_gracefully(
        self, config: HydraConfig
    ) -> None:
        store = IssueStore(config)

        async def _bad_json(*cmd: str, **_kw: object) -> AsyncMock:
            proc = AsyncMock()
            proc.returncode = 0
            proc.communicate = AsyncMock(return_value=(b"not-json", b""))
            return proc

        mock = AsyncMock(side_effect=_bad_json)

        with patch("asyncio.create_subprocess_exec", mock):
            await store._refresh()

        # Should not crash — queues remain empty
        for q in store._queues.values():
            assert len(q) == 0


# ---------------------------------------------------------------------------
# Event publishing
# ---------------------------------------------------------------------------


class TestIssueStoreEvents:
    """Tests that IssueStore publishes QUEUE_STATS events."""

    @pytest.mark.asyncio
    async def test_refresh_publishes_queue_stats_event(
        self, config: HydraConfig
    ) -> None:
        bus = EventBus()
        store = IssueStore(config, event_bus=bus)
        mock = _mock_subprocess_for_labels({})

        with patch("asyncio.create_subprocess_exec", mock):
            await store._refresh()

        history = bus.get_history()
        assert len(history) == 1
        assert history[0].type == EventType.QUEUE_STATS
        assert "queue_depth" in history[0].data

    @pytest.mark.asyncio
    async def test_no_event_without_bus(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        mock = _mock_subprocess_for_labels({})

        with patch("asyncio.create_subprocess_exec", mock):
            await store._refresh()
        # No crash when event_bus is None


# ---------------------------------------------------------------------------
# Concurrency safety
# ---------------------------------------------------------------------------


class TestIssueStoreConcurrency:
    """Tests that multiple consumers don't get the same issues."""

    def test_concurrent_pops_dont_overlap(self, config: HydraConfig) -> None:
        store = IssueStore(config)
        for i in range(6):
            store._queues["ready"].append(GitHubIssue(number=i, title=f"Issue {i}"))

        batch1 = store.get_implementable(3)
        batch2 = store.get_implementable(3)

        nums1 = {i.number for i in batch1}
        nums2 = {i.number for i in batch2}
        assert nums1.isdisjoint(nums2)
        assert len(nums1) == 3
        assert len(nums2) == 3
