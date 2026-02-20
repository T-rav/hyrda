"""Tests for memory.py — memory digest system."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory import (
    _compile_digest,
    _extract_field,
    file_memory_suggestion,
    load_digest,
    parse_memory_suggestions,
    sync,
)
from models import MemorySuggestion
from tests.helpers import ConfigFactory

# ---------------------------------------------------------------------------
# parse_memory_suggestions
# ---------------------------------------------------------------------------


class TestParseMemorySuggestions:
    """Tests for parse_memory_suggestions()."""

    def test_parses_well_formed_block(self) -> None:
        transcript = """
Some output text here.

MEMORY_SUGGESTION_START
title: Always run make lint before make test
learning: Running make lint first catches formatting issues that cause test failures.
context: Discovered during implementation of issue #42.
MEMORY_SUGGESTION_END

More output.
"""
        result = parse_memory_suggestions(transcript)

        assert len(result) == 1
        assert result[0].title == "Always run make lint before make test"
        assert "make lint first" in result[0].learning
        assert "issue #42" in result[0].context

    def test_returns_empty_for_no_markers(self) -> None:
        transcript = "Just a normal agent output with no memory blocks."
        result = parse_memory_suggestions(transcript)
        assert result == []

    def test_returns_at_most_one_suggestion(self) -> None:
        transcript = """
MEMORY_SUGGESTION_START
title: First suggestion
learning: First learning
context: First context
MEMORY_SUGGESTION_END

MEMORY_SUGGESTION_START
title: Second suggestion
learning: Second learning
context: Second context
MEMORY_SUGGESTION_END
"""
        result = parse_memory_suggestions(transcript)
        assert len(result) == 1
        assert result[0].title == "First suggestion"

    def test_returns_empty_for_missing_title(self) -> None:
        transcript = """
MEMORY_SUGGESTION_START
learning: Some learning without a title
context: Some context
MEMORY_SUGGESTION_END
"""
        result = parse_memory_suggestions(transcript)
        assert result == []

    def test_returns_empty_for_missing_learning(self) -> None:
        transcript = """
MEMORY_SUGGESTION_START
title: Has title but no learning
context: Some context
MEMORY_SUGGESTION_END
"""
        result = parse_memory_suggestions(transcript)
        assert result == []

    def test_handles_missing_context_gracefully(self) -> None:
        transcript = """
MEMORY_SUGGESTION_START
title: No context field
learning: This has a title and learning but no context
MEMORY_SUGGESTION_END
"""
        result = parse_memory_suggestions(transcript)
        assert len(result) == 1
        assert result[0].title == "No context field"
        assert result[0].context == ""

    def test_returns_empty_for_malformed_markers(self) -> None:
        transcript = """
MEMORY_SUGGESTION_STAR
title: Typo in marker
learning: Should not parse
MEMORY_SUGGESTION_EN
"""
        result = parse_memory_suggestions(transcript)
        assert result == []


# ---------------------------------------------------------------------------
# file_memory_suggestion
# ---------------------------------------------------------------------------


class TestFileMemorySuggestion:
    """Tests for file_memory_suggestion()."""

    @pytest.mark.asyncio
    async def test_creates_issue_with_correct_labels_and_body(self) -> None:
        suggestion = MemorySuggestion(
            title="Always run lint first",
            learning="Lint catches formatting issues early.",
            context="Discovered during issue #10",
            source="agent during issue #10",
        )
        config = ConfigFactory.create()
        pr_manager = AsyncMock()
        pr_manager.create_issue = AsyncMock(return_value=99)

        result = await file_memory_suggestion(suggestion, pr_manager, config)

        assert result == 99
        pr_manager.create_issue.assert_called_once()
        call_args = pr_manager.create_issue.call_args
        assert call_args[0][0] == "[Memory] Always run lint first"
        body = call_args[0][1]
        assert "## Memory Suggestion" in body
        assert "**Learning:** Lint catches formatting issues early." in body
        assert "**Context:** Discovered during issue #10" in body
        labels = call_args[0][2]
        assert "hydra-hitl" in labels

    @pytest.mark.asyncio
    async def test_dry_run_skips_filing(self) -> None:
        suggestion = MemorySuggestion(
            title="Test suggestion",
            learning="Test learning",
        )
        config = ConfigFactory.create(dry_run=True)
        pr_manager = AsyncMock()

        result = await file_memory_suggestion(suggestion, pr_manager, config)

        assert result == 0
        pr_manager.create_issue.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_issue_number_from_create(self) -> None:
        suggestion = MemorySuggestion(title="Test", learning="Test learning")
        config = ConfigFactory.create()
        pr_manager = AsyncMock()
        pr_manager.create_issue = AsyncMock(return_value=42)

        result = await file_memory_suggestion(suggestion, pr_manager, config)
        assert result == 42


# ---------------------------------------------------------------------------
# load_digest
# ---------------------------------------------------------------------------


class TestLoadDigest:
    """Tests for load_digest()."""

    def test_returns_file_contents_when_exists(self, tmp_path: Path) -> None:
        digest_path = tmp_path / "memory" / "digest.md"
        digest_path.parent.mkdir(parents=True)
        digest_path.write_text("# Memory\n\nSome learnings")
        config = ConfigFactory.create(repo_root=tmp_path)
        # Override the resolved memory_digest_path
        object.__setattr__(config, "memory_digest_path", digest_path)

        result = load_digest(config)
        assert result == "# Memory\n\nSome learnings"

    def test_returns_empty_string_when_not_exists(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(repo_root=tmp_path)
        object.__setattr__(
            config, "memory_digest_path", tmp_path / "nonexistent" / "digest.md"
        )

        result = load_digest(config)
        assert result == ""


# ---------------------------------------------------------------------------
# _compile_digest
# ---------------------------------------------------------------------------


class TestCompileDigest:
    """Tests for _compile_digest()."""

    def test_formats_issues_into_markdown(self) -> None:
        issues = [
            {
                "number": 100,
                "title": "[Memory] Always run lint first",
                "body": (
                    "## Memory Suggestion\n\n"
                    "**Learning:** Running lint first catches formatting issues.\n\n"
                    "**Context:** Discovered during issue #42\n\n"
                    "**Source:** agent during issue #42\n"
                ),
            },
        ]
        result = _compile_digest(issues, max_entries=50)

        assert "# Hydra Memory Digest" in result
        assert "_Entries: 1_" in result
        assert "## Always run lint first" in result
        assert "**Learning:** Running lint first catches formatting issues." in result
        assert "**Issue:** #100" in result

    def test_respects_max_entries_limit(self) -> None:
        issues = [
            {
                "number": i,
                "title": f"[Memory] Learning {i}",
                "body": f"**Learning:** Info {i}",
            }
            for i in range(10)
        ]
        result = _compile_digest(issues, max_entries=3)

        assert "_Entries: 3_" in result
        # Should include newest (highest numbers) first
        assert "Learning 9" in result
        assert "Learning 8" in result
        assert "Learning 7" in result
        assert "Learning 0" not in result

    def test_handles_empty_issue_list(self) -> None:
        result = _compile_digest([], max_entries=50)

        assert "# Hydra Memory Digest" in result
        assert "_Entries: 0_" in result

    def test_fallback_to_raw_body_when_no_structured_fields(self) -> None:
        issues = [
            {
                "number": 5,
                "title": "Raw learning",
                "body": "Just a plain text learning without structured fields.",
            },
        ]
        result = _compile_digest(issues, max_entries=50)

        assert "Just a plain text learning" in result

    def test_sorts_by_number_descending(self) -> None:
        issues = [
            {"number": 1, "title": "Old", "body": "**Learning:** Old info"},
            {"number": 50, "title": "New", "body": "**Learning:** New info"},
            {"number": 25, "title": "Mid", "body": "**Learning:** Mid info"},
        ]
        result = _compile_digest(issues, max_entries=50)

        # New (50) should appear before Mid (25) which should appear before Old (1)
        new_pos = result.index("New")
        mid_pos = result.index("Mid")
        old_pos = result.index("Old")
        assert new_pos < mid_pos < old_pos


# ---------------------------------------------------------------------------
# _extract_field
# ---------------------------------------------------------------------------


class TestExtractField:
    """Tests for _extract_field()."""

    def test_extracts_learning_field(self) -> None:
        body = "**Learning:** Some text here"
        assert _extract_field(body, "Learning") == "Some text here"

    def test_extracts_context_field(self) -> None:
        body = "**Context:** During issue #42"
        assert _extract_field(body, "Context") == "During issue #42"

    def test_returns_empty_for_missing_field(self) -> None:
        body = "No structured fields here"
        assert _extract_field(body, "Learning") == ""


# ---------------------------------------------------------------------------
# sync
# ---------------------------------------------------------------------------


class TestSync:
    """Tests for sync()."""

    @pytest.mark.asyncio
    async def test_fetches_issues_and_writes_digest(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(repo_root=tmp_path)
        digest_path = tmp_path / ".hydra" / "memory" / "digest.md"
        object.__setattr__(config, "memory_digest_path", digest_path)

        state_file = tmp_path / ".hydra-state.json"
        from state import StateTracker

        state = StateTracker(state_file)
        event_bus = AsyncMock()
        event_bus.publish = AsyncMock()

        mock_issues = [
            AsyncMock(
                number=10,
                title="[Memory] Test learning",
                body="**Learning:** Test info",
            ),
        ]

        with patch("issue_fetcher.IssueFetcher") as MockFetcher:
            mock_fetcher = MockFetcher.return_value
            mock_fetcher.fetch_issues_by_labels = AsyncMock(return_value=mock_issues)

            await sync(config, state, event_bus)

        assert digest_path.exists()
        content = digest_path.read_text()
        assert "# Hydra Memory Digest" in content
        assert "_Entries: 1_" in content
        event_bus.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_rebuild_when_no_changes(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(repo_root=tmp_path)
        digest_path = tmp_path / ".hydra" / "memory" / "digest.md"
        object.__setattr__(config, "memory_digest_path", digest_path)

        state_file = tmp_path / ".hydra-state.json"
        from state import StateTracker

        state = StateTracker(state_file)
        event_bus = AsyncMock()
        event_bus.publish = AsyncMock()

        mock_issues = [
            AsyncMock(
                number=10,
                title="[Memory] Test",
                body="**Learning:** Info",
            ),
        ]

        with patch("issue_fetcher.IssueFetcher") as MockFetcher:
            mock_fetcher = MockFetcher.return_value
            mock_fetcher.fetch_issues_by_labels = AsyncMock(return_value=mock_issues)

            # First sync builds digest
            await sync(config, state, event_bus)
            assert event_bus.publish.call_count == 1

            # Second sync with same issues should skip
            await sync(config, state, event_bus)
            assert event_bus.publish.call_count == 1  # No additional publish

    @pytest.mark.asyncio
    async def test_dry_run_skips_sync(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(dry_run=True, repo_root=tmp_path)
        digest_path = tmp_path / ".hydra" / "memory" / "digest.md"
        object.__setattr__(config, "memory_digest_path", digest_path)

        state_file = tmp_path / ".hydra-state.json"
        from state import StateTracker

        state = StateTracker(state_file)
        event_bus = AsyncMock()
        event_bus.publish = AsyncMock()

        await sync(config, state, event_bus)

        assert not digest_path.exists()
        event_bus.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_no_memory_issues(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(repo_root=tmp_path)
        digest_path = tmp_path / ".hydra" / "memory" / "digest.md"
        object.__setattr__(config, "memory_digest_path", digest_path)

        state_file = tmp_path / ".hydra-state.json"
        from state import StateTracker

        state = StateTracker(state_file)
        event_bus = AsyncMock()
        event_bus.publish = AsyncMock()

        with patch("issue_fetcher.IssueFetcher") as MockFetcher:
            mock_fetcher = MockFetcher.return_value
            mock_fetcher.fetch_issues_by_labels = AsyncMock(return_value=[])

            await sync(config, state, event_bus)

        assert digest_path.exists()
        content = digest_path.read_text()
        assert "_Entries: 0_" in content
