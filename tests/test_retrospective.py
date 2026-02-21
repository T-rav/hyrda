"""Tests for retrospective.py - RetrospectiveCollector class."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config import HydraConfig

from models import ReviewResult, ReviewVerdict
from retrospective import RetrospectiveCollector, RetrospectiveEntry, StatusCallback
from state import StateTracker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_collector(
    config: HydraConfig,
    *,
    diff_names: list[str] | None = None,
    create_issue_return: int = 0,
    status_callback: StatusCallback | None = None,
) -> tuple[RetrospectiveCollector, AsyncMock, StateTracker]:
    """Build a RetrospectiveCollector with mocked PRManager."""
    state = StateTracker(config.state_file)
    mock_prs = AsyncMock()
    mock_prs.get_pr_diff_names = AsyncMock(return_value=diff_names or [])
    mock_prs.create_issue = AsyncMock(return_value=create_issue_return)

    collector = RetrospectiveCollector(
        config, state, mock_prs, status_callback=status_callback
    )
    return collector, mock_prs, state


def _make_review_result(
    pr_number: int = 101,
    issue_number: int = 42,
    verdict: ReviewVerdict = ReviewVerdict.APPROVE,
    fixes_made: bool = False,
    ci_fix_attempts: int = 0,
) -> ReviewResult:
    return ReviewResult(
        pr_number=pr_number,
        issue_number=issue_number,
        verdict=verdict,
        summary="Looks good.",
        fixes_made=fixes_made,
        ci_fix_attempts=ci_fix_attempts,
        merged=True,
    )


def _write_plan(config: HydraConfig, issue_number: int, content: str) -> None:
    """Write a plan file for the given issue."""
    plan_dir = config.repo_root / ".hydra" / "plans"
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / f"issue-{issue_number}.md").write_text(content)


def _write_retro_entries(
    config: HydraConfig, entries: list[RetrospectiveEntry]
) -> None:
    """Write retrospective entries to the JSONL file."""
    retro_path = config.repo_root / ".hydra" / "memory" / "retrospectives.jsonl"
    retro_path.parent.mkdir(parents=True, exist_ok=True)
    with retro_path.open("w") as f:
        for entry in entries:
            f.write(entry.model_dump_json() + "\n")


# ---------------------------------------------------------------------------
# Plan parser tests
# ---------------------------------------------------------------------------


class TestParsePlannedFiles:
    def test_parses_backtick_paths(self, config: HydraConfig) -> None:
        collector, _, _ = _make_collector(config)
        plan = (
            "## Files to Modify\n\n"
            "### 1. `src/foo.py`\n"
            "### 2. `tests/test_foo.py`\n"
            "\n## New Files\n\n"
            "### 1. `src/bar.py` (NEW)\n"
        )
        result = collector._parse_planned_files(plan)
        assert result == ["src/bar.py", "src/foo.py", "tests/test_foo.py"]

    def test_parses_bold_paths(self, config: HydraConfig) -> None:
        collector, _, _ = _make_collector(config)
        plan = (
            "## Files to Modify\n\n"
            "- **src/foo.py** — update logic\n"
            "- **src/bar.py** — add feature\n"
        )
        result = collector._parse_planned_files(plan)
        assert result == ["src/bar.py", "src/foo.py"]

    def test_parses_bare_list_items(self, config: HydraConfig) -> None:
        collector, _, _ = _make_collector(config)
        plan = "## Files to Modify\n\n- src/foo.py\n- src/bar.py\n"
        result = collector._parse_planned_files(plan)
        assert result == ["src/bar.py", "src/foo.py"]

    def test_stops_at_next_heading(self, config: HydraConfig) -> None:
        collector, _, _ = _make_collector(config)
        plan = (
            "## Files to Modify\n\n"
            "- `src/foo.py`\n"
            "\n## Implementation Steps\n\n"
            "- `src/not_a_file.py`\n"
        )
        result = collector._parse_planned_files(plan)
        assert result == ["src/foo.py"]

    def test_returns_empty_for_no_plan(self, config: HydraConfig) -> None:
        collector, _, _ = _make_collector(config)
        result = collector._parse_planned_files("")
        assert result == []

    def test_returns_empty_for_plan_without_file_sections(
        self, config: HydraConfig
    ) -> None:
        collector, _, _ = _make_collector(config)
        plan = "## Summary\n\nThis is a plan.\n\n## Steps\n\n1. Do stuff\n"
        result = collector._parse_planned_files(plan)
        assert result == []

    def test_deduplicates_files(self, config: HydraConfig) -> None:
        collector, _, _ = _make_collector(config)
        plan = (
            "## Files to Modify\n\n- `src/foo.py`\n\n## New Files\n\n- `src/foo.py`\n"
        )
        result = collector._parse_planned_files(plan)
        assert result == ["src/foo.py"]


# ---------------------------------------------------------------------------
# Accuracy computation tests
# ---------------------------------------------------------------------------


class TestComputeAccuracy:
    def test_perfect_match(self) -> None:
        accuracy, unplanned, missed = RetrospectiveCollector._compute_accuracy(
            ["src/foo.py", "src/bar.py"],
            ["src/foo.py", "src/bar.py"],
        )
        assert accuracy == 100.0
        assert unplanned == []
        assert missed == []

    def test_partial_overlap(self) -> None:
        accuracy, unplanned, missed = RetrospectiveCollector._compute_accuracy(
            ["src/foo.py", "src/bar.py"],
            ["src/foo.py", "src/baz.py"],
        )
        assert accuracy == 50.0
        assert unplanned == ["src/baz.py"]
        assert missed == ["src/bar.py"]

    def test_no_overlap(self) -> None:
        accuracy, unplanned, missed = RetrospectiveCollector._compute_accuracy(
            ["src/foo.py"],
            ["src/bar.py"],
        )
        assert accuracy == 0.0
        assert unplanned == ["src/bar.py"]
        assert missed == ["src/foo.py"]

    def test_empty_planned_list(self) -> None:
        accuracy, unplanned, missed = RetrospectiveCollector._compute_accuracy(
            [],
            ["src/bar.py"],
        )
        assert accuracy == 0.0
        assert unplanned == ["src/bar.py"]
        assert missed == []

    def test_empty_actual_list(self) -> None:
        accuracy, unplanned, missed = RetrospectiveCollector._compute_accuracy(
            ["src/foo.py"],
            [],
        )
        assert accuracy == 0.0
        assert unplanned == []
        assert missed == ["src/foo.py"]

    def test_both_empty(self) -> None:
        accuracy, unplanned, missed = RetrospectiveCollector._compute_accuracy([], [])
        assert accuracy == 0.0
        assert unplanned == []
        assert missed == []


# ---------------------------------------------------------------------------
# JSONL storage tests
# ---------------------------------------------------------------------------


class TestJSONLStorage:
    def test_append_creates_directory_and_file(self, config: HydraConfig) -> None:
        collector, _, _ = _make_collector(config)
        entry = RetrospectiveEntry(
            issue_number=42,
            pr_number=101,
            timestamp="2026-02-20T10:30:00Z",
        )
        collector._append_entry(entry)

        retro_path = config.repo_root / ".hydra" / "memory" / "retrospectives.jsonl"
        assert retro_path.exists()

    def test_append_writes_valid_jsonl(self, config: HydraConfig) -> None:
        collector, _, _ = _make_collector(config)
        entry = RetrospectiveEntry(
            issue_number=42,
            pr_number=101,
            timestamp="2026-02-20T10:30:00Z",
            plan_accuracy_pct=85.0,
        )
        collector._append_entry(entry)

        retro_path = config.repo_root / ".hydra" / "memory" / "retrospectives.jsonl"
        lines = retro_path.read_text().strip().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["issue_number"] == 42
        assert data["plan_accuracy_pct"] == 85.0

    def test_append_to_existing_file(self, config: HydraConfig) -> None:
        collector, _, _ = _make_collector(config)
        for i in range(3):
            entry = RetrospectiveEntry(
                issue_number=i,
                pr_number=100 + i,
                timestamp="2026-02-20T10:30:00Z",
            )
            collector._append_entry(entry)

        retro_path = config.repo_root / ".hydra" / "memory" / "retrospectives.jsonl"
        lines = retro_path.read_text().strip().splitlines()
        assert len(lines) == 3

    def test_load_recent_returns_correct_count(self, config: HydraConfig) -> None:
        collector, _, _ = _make_collector(config)
        entries = [
            RetrospectiveEntry(
                issue_number=i,
                pr_number=100 + i,
                timestamp="2026-02-20T10:30:00Z",
            )
            for i in range(5)
        ]
        _write_retro_entries(config, entries)

        result = collector._load_recent(3)
        assert len(result) == 3
        assert result[0].issue_number == 2  # last 3 entries

    def test_load_recent_with_fewer_entries(self, config: HydraConfig) -> None:
        collector, _, _ = _make_collector(config)
        entries = [
            RetrospectiveEntry(
                issue_number=1,
                pr_number=101,
                timestamp="2026-02-20T10:30:00Z",
            )
        ]
        _write_retro_entries(config, entries)

        result = collector._load_recent(10)
        assert len(result) == 1

    def test_load_recent_with_missing_file(self, config: HydraConfig) -> None:
        collector, _, _ = _make_collector(config)
        result = collector._load_recent(10)
        assert result == []


# ---------------------------------------------------------------------------
# Record integration tests
# ---------------------------------------------------------------------------


class TestRecord:
    @pytest.mark.asyncio
    async def test_full_record_flow(self, config: HydraConfig) -> None:
        """Full record flow: plan exists, diff available, metadata in state."""
        collector, mock_prs, state = _make_collector(
            config, diff_names=["src/foo.py", "tests/test_foo.py", "src/bar.py"]
        )

        _write_plan(
            config,
            42,
            "## Files to Modify\n\n- `src/foo.py`\n- `tests/test_foo.py`\n",
        )
        state.set_worker_result_meta(
            42,
            {
                "quality_fix_attempts": 1,
                "duration_seconds": 120.5,
                "error": None,
            },
        )

        review = _make_review_result(fixes_made=False, ci_fix_attempts=0)
        await collector.record(42, 101, review)

        retro_path = config.repo_root / ".hydra" / "memory" / "retrospectives.jsonl"
        assert retro_path.exists()
        lines = retro_path.read_text().strip().splitlines()
        assert len(lines) == 1

        data = json.loads(lines[0])
        assert data["issue_number"] == 42
        assert data["pr_number"] == 101
        assert data["planned_files"] == ["src/foo.py", "tests/test_foo.py"]
        assert sorted(data["actual_files"]) == [
            "src/bar.py",
            "src/foo.py",
            "tests/test_foo.py",
        ]
        assert data["unplanned_files"] == ["src/bar.py"]
        assert data["missed_files"] == []
        assert data["plan_accuracy_pct"] == 100.0
        assert data["quality_fix_rounds"] == 1
        assert data["review_verdict"] == "approve"
        assert data["reviewer_fixes_made"] is False

    @pytest.mark.asyncio
    async def test_record_when_plan_missing(self, config: HydraConfig) -> None:
        """When plan file doesn't exist, should still record with empty planned_files."""
        collector, _, _ = _make_collector(config, diff_names=["src/foo.py"])

        review = _make_review_result()
        await collector.record(42, 101, review)

        retro_path = config.repo_root / ".hydra" / "memory" / "retrospectives.jsonl"
        lines = retro_path.read_text().strip().splitlines()
        data = json.loads(lines[0])
        assert data["planned_files"] == []
        assert data["plan_accuracy_pct"] == 0.0

    @pytest.mark.asyncio
    async def test_record_when_diff_fails(self, config: HydraConfig) -> None:
        """When gh pr diff fails, should record with empty actual_files."""
        collector, _, _ = _make_collector(config, diff_names=[])

        _write_plan(config, 42, "## Files to Modify\n\n- `src/foo.py`\n")
        review = _make_review_result()
        await collector.record(42, 101, review)

        retro_path = config.repo_root / ".hydra" / "memory" / "retrospectives.jsonl"
        lines = retro_path.read_text().strip().splitlines()
        data = json.loads(lines[0])
        assert data["actual_files"] == []
        assert data["missed_files"] == ["src/foo.py"]

    @pytest.mark.asyncio
    async def test_record_when_worker_metadata_missing(
        self, config: HydraConfig
    ) -> None:
        """When worker metadata not in state, should use defaults."""
        collector, _, _ = _make_collector(config, diff_names=["src/foo.py"])

        review = _make_review_result()
        await collector.record(42, 101, review)

        retro_path = config.repo_root / ".hydra" / "memory" / "retrospectives.jsonl"
        lines = retro_path.read_text().strip().splitlines()
        data = json.loads(lines[0])
        assert data["quality_fix_rounds"] == 0
        assert data["duration_seconds"] == 0.0

    @pytest.mark.asyncio
    async def test_record_failure_is_non_blocking(self, config: HydraConfig) -> None:
        """If retrospective fails, it should not raise."""
        collector, mock_prs, _ = _make_collector(config)
        mock_prs.get_pr_diff_names = AsyncMock(
            side_effect=RuntimeError("network error")
        )

        review = _make_review_result()
        # Should not raise
        await collector.record(42, 101, review)


# ---------------------------------------------------------------------------
# Pattern detection tests
# ---------------------------------------------------------------------------


class TestPatternDetection:
    @pytest.mark.asyncio
    async def test_quality_fix_pattern_detected(self, config: HydraConfig) -> None:
        """When >50% of entries need quality fixes, pattern should be detected."""
        collector, mock_prs, _ = _make_collector(config)
        entries = [
            RetrospectiveEntry(
                issue_number=i,
                pr_number=100 + i,
                timestamp="2026-02-20T10:30:00Z",
                quality_fix_rounds=1 if i < 6 else 0,  # 6/10 = 60%
                plan_accuracy_pct=90,
            )
            for i in range(10)
        ]

        await collector._detect_patterns(entries)

        mock_prs.create_issue.assert_awaited_once()
        title = mock_prs.create_issue.call_args[0][0]
        assert "quality fix" in title.lower()

    @pytest.mark.asyncio
    async def test_quality_fix_pattern_not_detected_when_below_threshold(
        self, config: HydraConfig
    ) -> None:
        """When <=50% of entries need quality fixes, no pattern."""
        collector, mock_prs, _ = _make_collector(config)
        entries = [
            RetrospectiveEntry(
                issue_number=i,
                pr_number=100 + i,
                timestamp="2026-02-20T10:30:00Z",
                quality_fix_rounds=1 if i < 4 else 0,  # 4/10 = 40%
                plan_accuracy_pct=90,
            )
            for i in range(10)
        ]

        await collector._detect_patterns(entries)

        mock_prs.create_issue.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_plan_accuracy_pattern_detected(self, config: HydraConfig) -> None:
        """When average accuracy drops below 70%, pattern should be detected."""
        collector, mock_prs, _ = _make_collector(config)
        entries = [
            RetrospectiveEntry(
                issue_number=i,
                pr_number=100 + i,
                timestamp="2026-02-20T10:30:00Z",
                plan_accuracy_pct=60,
            )
            for i in range(10)
        ]

        await collector._detect_patterns(entries)

        mock_prs.create_issue.assert_awaited_once()
        title = mock_prs.create_issue.call_args[0][0]
        assert "plan accuracy" in title.lower()

    @pytest.mark.asyncio
    async def test_reviewer_fix_pattern_detected(self, config: HydraConfig) -> None:
        """When >40% of entries have reviewer fixes, pattern should be detected."""
        collector, mock_prs, _ = _make_collector(config)
        entries = [
            RetrospectiveEntry(
                issue_number=i,
                pr_number=100 + i,
                timestamp="2026-02-20T10:30:00Z",
                reviewer_fixes_made=i < 5,  # 5/10 = 50%
                plan_accuracy_pct=90,
            )
            for i in range(10)
        ]

        await collector._detect_patterns(entries)

        mock_prs.create_issue.assert_awaited_once()
        title = mock_prs.create_issue.call_args[0][0]
        assert "reviewer" in title.lower()

    @pytest.mark.asyncio
    async def test_unplanned_file_pattern_detected(self, config: HydraConfig) -> None:
        """When same file appears unplanned in >30% of entries."""
        collector, mock_prs, _ = _make_collector(config)
        entries = [
            RetrospectiveEntry(
                issue_number=i,
                pr_number=100 + i,
                timestamp="2026-02-20T10:30:00Z",
                unplanned_files=["src/common.py"] if i < 4 else [],  # 4/10 = 40%
                plan_accuracy_pct=90,
            )
            for i in range(10)
        ]

        await collector._detect_patterns(entries)

        mock_prs.create_issue.assert_awaited_once()
        title = mock_prs.create_issue.call_args[0][0]
        assert "src/common.py" in title

    @pytest.mark.asyncio
    async def test_no_patterns_on_healthy_data(self, config: HydraConfig) -> None:
        """No patterns should be detected on healthy data."""
        collector, mock_prs, _ = _make_collector(config)
        entries = [
            RetrospectiveEntry(
                issue_number=i,
                pr_number=100 + i,
                timestamp="2026-02-20T10:30:00Z",
                plan_accuracy_pct=90,
                quality_fix_rounds=0,
                reviewer_fixes_made=False,
                unplanned_files=[],
            )
            for i in range(10)
        ]

        await collector._detect_patterns(entries)

        mock_prs.create_issue.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_pattern_detection_skips_with_few_entries(
        self, config: HydraConfig
    ) -> None:
        """Pattern detection should skip when fewer than 3 entries."""
        collector, mock_prs, _ = _make_collector(config)
        entries = [
            RetrospectiveEntry(
                issue_number=1,
                pr_number=101,
                timestamp="2026-02-20T10:30:00Z",
                quality_fix_rounds=1,
                plan_accuracy_pct=10,
            )
        ]

        await collector._detect_patterns(entries)

        mock_prs.create_issue.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_duplicate_pattern_not_filed(self, config: HydraConfig) -> None:
        """Same pattern should not be filed twice."""
        collector, mock_prs, _ = _make_collector(config)

        # Pre-populate filed patterns
        filed_path = config.repo_root / ".hydra" / "memory" / "filed_patterns.json"
        filed_path.parent.mkdir(parents=True, exist_ok=True)
        filed_path.write_text(json.dumps(["quality_fix"]))

        entries = [
            RetrospectiveEntry(
                issue_number=i,
                pr_number=100 + i,
                timestamp="2026-02-20T10:30:00Z",
                quality_fix_rounds=1,  # 100% need quality fixes
                plan_accuracy_pct=90,
            )
            for i in range(10)
        ]

        await collector._detect_patterns(entries)

        # Should not file again since quality_fix is already in filed patterns
        mock_prs.create_issue.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_caps_at_one_proposal_per_run(self, config: HydraConfig) -> None:
        """At most 1 pattern proposal per retrospective run."""
        collector, mock_prs, _ = _make_collector(config)
        entries = [
            RetrospectiveEntry(
                issue_number=i,
                pr_number=100 + i,
                timestamp="2026-02-20T10:30:00Z",
                quality_fix_rounds=1,  # >50% quality fixes
                plan_accuracy_pct=50,  # <70% accuracy
                reviewer_fixes_made=True,  # >40% reviewer fixes
            )
            for i in range(10)
        ]

        await collector._detect_patterns(entries)

        # Only 1 issue filed despite multiple patterns matching
        mock_prs.create_issue.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_improvement_issue_has_correct_labels(
        self, config: HydraConfig
    ) -> None:
        """Filed improvement issue should have hydra-improve + hydra-hitl labels."""
        collector, mock_prs, _ = _make_collector(config)
        entries = [
            RetrospectiveEntry(
                issue_number=i,
                pr_number=100 + i,
                timestamp="2026-02-20T10:30:00Z",
                quality_fix_rounds=1,
                plan_accuracy_pct=90,
            )
            for i in range(10)
        ]

        await collector._detect_patterns(entries)

        labels = mock_prs.create_issue.call_args[0][2]
        assert "hydra-improve" in labels
        assert "hydra-hitl" in labels


# ---------------------------------------------------------------------------
# Filed patterns persistence
# ---------------------------------------------------------------------------


class TestFiledPatterns:
    def test_load_empty_when_no_file(self, config: HydraConfig) -> None:
        collector, _, _ = _make_collector(config)
        result = collector._load_filed_patterns()
        assert result == set()

    def test_save_and_load_round_trip(self, config: HydraConfig) -> None:
        collector, _, _ = _make_collector(config)
        patterns = {"quality_fix", "plan_accuracy"}
        collector._save_filed_patterns(patterns)
        result = collector._load_filed_patterns()
        assert result == patterns

    def test_load_handles_corrupt_file(self, config: HydraConfig) -> None:
        collector, _, _ = _make_collector(config)
        filed_path = config.repo_root / ".hydra" / "memory" / "filed_patterns.json"
        filed_path.parent.mkdir(parents=True, exist_ok=True)
        filed_path.write_text("not valid json")
        result = collector._load_filed_patterns()
        assert result == set()


# ---------------------------------------------------------------------------
# RetrospectiveEntry model tests
# ---------------------------------------------------------------------------


class TestRetrospectiveEntry:
    def test_defaults(self) -> None:
        entry = RetrospectiveEntry(
            issue_number=42,
            pr_number=101,
            timestamp="2026-02-20T10:30:00Z",
        )
        assert entry.plan_accuracy_pct == 0.0
        assert entry.planned_files == []
        assert entry.actual_files == []
        assert entry.unplanned_files == []
        assert entry.missed_files == []
        assert entry.quality_fix_rounds == 0
        assert entry.ci_fix_rounds == 0
        assert entry.duration_seconds == 0.0

    def test_json_round_trip(self) -> None:
        entry = RetrospectiveEntry(
            issue_number=42,
            pr_number=101,
            timestamp="2026-02-20T10:30:00Z",
            plan_accuracy_pct=85.0,
            planned_files=["src/foo.py"],
            actual_files=["src/foo.py", "src/bar.py"],
            unplanned_files=["src/bar.py"],
            missed_files=[],
            quality_fix_rounds=1,
            review_verdict="approve",
            reviewer_fixes_made=False,
            ci_fix_rounds=0,
            duration_seconds=340.5,
        )
        json_str = entry.model_dump_json()
        restored = RetrospectiveEntry.model_validate_json(json_str)
        assert restored == entry


# ---------------------------------------------------------------------------
# Time-based loading tests
# ---------------------------------------------------------------------------


class TestLoadSince:
    def test_loads_entries_within_window(self, config: HydraConfig) -> None:
        collector, _, _ = _make_collector(config)
        now = datetime.now(UTC)
        entries = [
            RetrospectiveEntry(
                issue_number=i,
                pr_number=100 + i,
                timestamp=(now - timedelta(hours=i)).isoformat(),
            )
            for i in range(10)
        ]
        _write_retro_entries(config, entries)

        result = collector._load_since(5)
        # Entries at hours 0, 1, 2, 3, 4 are within 5 hours
        assert len(result) == 5
        assert result[0].issue_number == 0

    def test_returns_empty_when_no_entries_in_window(self, config: HydraConfig) -> None:
        collector, _, _ = _make_collector(config)
        old_time = (datetime.now(UTC) - timedelta(hours=24)).isoformat()
        entries = [
            RetrospectiveEntry(
                issue_number=1,
                pr_number=101,
                timestamp=old_time,
            )
        ]
        _write_retro_entries(config, entries)

        result = collector._load_since(6)
        assert result == []

    def test_returns_empty_when_no_file(self, config: HydraConfig) -> None:
        collector, _, _ = _make_collector(config)
        result = collector._load_since(6)
        assert result == []

    def test_handles_entries_without_timezone(self, config: HydraConfig) -> None:
        collector, _, _ = _make_collector(config)
        now = datetime.now(UTC)
        # Timestamp without timezone info
        naive_ts = now.replace(tzinfo=None).isoformat()
        entries = [
            RetrospectiveEntry(
                issue_number=1,
                pr_number=101,
                timestamp=naive_ts,
            )
        ]
        _write_retro_entries(config, entries)

        result = collector._load_since(1)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Stats computation tests
# ---------------------------------------------------------------------------


class TestComputeStats:
    def test_empty_entries(self) -> None:
        stats = RetrospectiveCollector.compute_stats([], window_hours=6)
        assert stats["entry_count"] == 0
        assert stats["plan_accuracy"] == 0.0
        assert stats["quality_fix_rate"] == 0.0
        assert stats["review_pass_rate"] == 0.0
        assert stats["avg_implementation_seconds"] == 0.0
        assert stats["ci_stability"] == 0.0

    def test_perfect_stats(self) -> None:
        entries = [
            RetrospectiveEntry(
                issue_number=i,
                pr_number=100 + i,
                timestamp="2026-02-20T10:30:00Z",
                plan_accuracy_pct=100.0,
                quality_fix_rounds=0,
                review_verdict="approve",
                ci_fix_rounds=0,
                duration_seconds=120.0,
            )
            for i in range(5)
        ]
        stats = RetrospectiveCollector.compute_stats(entries, window_hours=6)
        assert stats["entry_count"] == 5
        assert stats["plan_accuracy"] == 100.0
        assert stats["quality_fix_rate"] == 0.0
        assert stats["review_pass_rate"] == 100.0
        assert stats["ci_stability"] == 100.0
        assert stats["avg_implementation_seconds"] == 120.0

    def test_mixed_stats(self) -> None:
        entries = [
            RetrospectiveEntry(
                issue_number=1,
                pr_number=101,
                timestamp="2026-02-20T10:30:00Z",
                plan_accuracy_pct=80.0,
                quality_fix_rounds=1,
                review_verdict="approve",
                ci_fix_rounds=0,
                duration_seconds=200.0,
            ),
            RetrospectiveEntry(
                issue_number=2,
                pr_number=102,
                timestamp="2026-02-20T11:30:00Z",
                plan_accuracy_pct=60.0,
                quality_fix_rounds=0,
                review_verdict="request-changes",
                ci_fix_rounds=2,
                duration_seconds=400.0,
            ),
        ]
        stats = RetrospectiveCollector.compute_stats(entries, window_hours=6)
        assert stats["entry_count"] == 2
        assert stats["plan_accuracy"] == 70.0  # (80+60)/2
        assert stats["quality_fix_rate"] == 50.0  # 1/2
        assert stats["review_pass_rate"] == 50.0  # 1/2
        assert stats["ci_stability"] == 50.0  # 1/2
        assert stats["avg_implementation_seconds"] == 300.0  # (200+400)/2

    def test_window_hours_in_output(self) -> None:
        stats = RetrospectiveCollector.compute_stats([], window_hours=12)
        assert stats["window_hours"] == 12


# ---------------------------------------------------------------------------
# Trend detection tests
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_stats_with_trends(self, config: HydraConfig) -> None:
        collector, _, _ = _make_collector(config)
        now = datetime.now(UTC)

        # Previous window (6-12 hours ago): low accuracy
        prev_entries = [
            RetrospectiveEntry(
                issue_number=i,
                pr_number=100 + i,
                timestamp=(now - timedelta(hours=9 - i)).isoformat(),
                plan_accuracy_pct=40.0,
                quality_fix_rounds=1,
                review_verdict="request-changes",
                ci_fix_rounds=1,
                duration_seconds=500.0,
            )
            for i in range(3)
        ]
        # Current window (0-6 hours ago): better accuracy
        current_entries = [
            RetrospectiveEntry(
                issue_number=10 + i,
                pr_number=200 + i,
                timestamp=(now - timedelta(hours=3 - i)).isoformat(),
                plan_accuracy_pct=80.0,
                quality_fix_rounds=0,
                review_verdict="approve",
                ci_fix_rounds=0,
                duration_seconds=200.0,
            )
            for i in range(3)
        ]
        _write_retro_entries(config, prev_entries + current_entries)

        stats = collector.get_stats()
        assert stats["entry_count"] == 3
        assert stats["plan_accuracy"] == 80.0
        # Trends should show improvement
        trends = stats["trends"]
        assert isinstance(trends, dict)
        assert trends["plan_accuracy"] == 40.0  # 80 - 40

    def test_stats_without_previous_window(self, config: HydraConfig) -> None:
        collector, _, _ = _make_collector(config)
        now = datetime.now(UTC)

        entries = [
            RetrospectiveEntry(
                issue_number=i,
                pr_number=100 + i,
                timestamp=(now - timedelta(hours=i)).isoformat(),
                plan_accuracy_pct=75.0,
            )
            for i in range(3)
        ]
        _write_retro_entries(config, entries)

        stats = collector.get_stats()
        assert stats["entry_count"] == 3
        assert stats["plan_accuracy"] == 75.0
        # No previous window data, so trends should be empty
        assert stats["trends"] == {}

    def test_stats_empty_log(self, config: HydraConfig) -> None:
        collector, _, _ = _make_collector(config)
        stats = collector.get_stats()
        assert stats["entry_count"] == 0


# ---------------------------------------------------------------------------
# Load window tests
# ---------------------------------------------------------------------------


class TestLoadWindow:
    def test_loads_entries_in_range(self, config: HydraConfig) -> None:
        collector, _, _ = _make_collector(config)
        now = datetime.now(UTC)
        entries = [
            RetrospectiveEntry(
                issue_number=i,
                pr_number=100 + i,
                timestamp=(now - timedelta(hours=i)).isoformat(),
            )
            for i in range(15)
        ]
        _write_retro_entries(config, entries)

        # Load entries from 12 to 6 hours ago
        result = collector._load_window(12, 6)
        for entry in result:
            ts = datetime.fromisoformat(entry.timestamp)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            hours_ago = (now - ts).total_seconds() / 3600
            assert 6 <= hours_ago <= 12

    def test_empty_when_no_file(self, config: HydraConfig) -> None:
        collector, _, _ = _make_collector(config)
        result = collector._load_window(12, 6)
        assert result == []


# ---------------------------------------------------------------------------
# Status callback tests
# ---------------------------------------------------------------------------


class TestStatusCallback:
    @pytest.mark.asyncio
    async def test_reports_ok_on_success(self, config: HydraConfig) -> None:
        calls: list[tuple[str, str, dict]] = []

        def capture_callback(name: str, status: str, details: dict) -> None:
            calls.append((name, status, details))

        collector, _, state = _make_collector(
            config,
            diff_names=["src/foo.py"],
            status_callback=capture_callback,
        )
        _write_plan(config, 42, "## Files to Modify\n\n- `src/foo.py`\n")

        review = _make_review_result()
        await collector.record(42, 101, review)

        assert len(calls) == 1
        assert calls[0][0] == "retrospective"
        assert calls[0][1] == "ok"
        assert calls[0][2]["last_issue"] == 42

    @pytest.mark.asyncio
    async def test_reports_error_on_failure(self, config: HydraConfig) -> None:
        calls: list[tuple[str, str, dict]] = []

        def capture_callback(name: str, status: str, details: dict) -> None:
            calls.append((name, status, details))

        collector, mock_prs, _ = _make_collector(
            config,
            status_callback=capture_callback,
        )
        mock_prs.get_pr_diff_names = AsyncMock(
            side_effect=RuntimeError("network error")
        )

        review = _make_review_result()
        await collector.record(42, 101, review)

        assert len(calls) == 1
        assert calls[0][0] == "retrospective"
        assert calls[0][1] == "error"

    @pytest.mark.asyncio
    async def test_no_callback_no_error(self, config: HydraConfig) -> None:
        """When no callback is set, record should still work."""
        collector, _, _ = _make_collector(config, diff_names=["src/foo.py"])
        review = _make_review_result()
        # Should not raise
        await collector.record(42, 101, review)


# ---------------------------------------------------------------------------
# RetrospectiveStats model tests
# ---------------------------------------------------------------------------


class TestRetrospectiveStatsModel:
    def test_defaults(self) -> None:
        from models import RetrospectiveStats

        stats = RetrospectiveStats()
        assert stats.window_hours == 6
        assert stats.entry_count == 0
        assert stats.plan_accuracy == 0.0
        assert stats.quality_fix_rate == 0.0
        assert stats.review_pass_rate == 0.0
        assert stats.avg_implementation_seconds == 0.0
        assert stats.ci_stability == 0.0
        assert stats.trends == {}

    def test_with_trends(self) -> None:
        from models import RetrospectiveStats

        stats = RetrospectiveStats(
            entry_count=5,
            plan_accuracy=75.0,
            trends={"plan_accuracy": 10.0, "ci_stability": -5.0},
        )
        assert stats.trends["plan_accuracy"] == 10.0
        assert stats.trends["ci_stability"] == -5.0
