"""Tests for the memory digest system."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from memory import (
    MemorySyncWorker,
    build_memory_issue_body,
    load_memory_digest,
    parse_memory_suggestion,
)
from tests.helpers import ConfigFactory

# --- parse_memory_suggestion tests ---


class TestParseMemorySuggestion:
    """Tests for parsing MEMORY_SUGGESTION blocks from transcripts."""

    def test_valid_block(self) -> None:
        transcript = (
            "Some output here\n"
            "MEMORY_SUGGESTION_START\n"
            "title: Always run make lint before make test\n"
            "learning: Running make lint first catches formatting issues.\n"
            "context: Discovered during implementation of issue #42.\n"
            "MEMORY_SUGGESTION_END\n"
            "More output"
        )
        result = parse_memory_suggestion(transcript)
        assert result is not None
        assert result["title"] == "Always run make lint before make test"
        assert (
            result["learning"] == "Running make lint first catches formatting issues."
        )
        assert result["context"] == "Discovered during implementation of issue #42."

    def test_no_block_returns_none(self) -> None:
        transcript = "Just regular output with no suggestion"
        result = parse_memory_suggestion(transcript)
        assert result is None

    def test_multiple_blocks_returns_first(self) -> None:
        transcript = (
            "MEMORY_SUGGESTION_START\n"
            "title: First suggestion\n"
            "learning: First learning\n"
            "context: First context\n"
            "MEMORY_SUGGESTION_END\n"
            "MEMORY_SUGGESTION_START\n"
            "title: Second suggestion\n"
            "learning: Second learning\n"
            "context: Second context\n"
            "MEMORY_SUGGESTION_END\n"
        )
        result = parse_memory_suggestion(transcript)
        assert result is not None
        assert result["title"] == "First suggestion"

    def test_missing_title_returns_none(self) -> None:
        transcript = (
            "MEMORY_SUGGESTION_START\n"
            "learning: Some learning\n"
            "context: Some context\n"
            "MEMORY_SUGGESTION_END\n"
        )
        result = parse_memory_suggestion(transcript)
        assert result is None

    def test_missing_learning_returns_none(self) -> None:
        transcript = (
            "MEMORY_SUGGESTION_START\n"
            "title: Some title\n"
            "context: Some context\n"
            "MEMORY_SUGGESTION_END\n"
        )
        result = parse_memory_suggestion(transcript)
        assert result is None

    def test_empty_fields_returns_none(self) -> None:
        transcript = (
            "MEMORY_SUGGESTION_START\n"
            "title: \n"
            "learning: \n"
            "context: \n"
            "MEMORY_SUGGESTION_END\n"
        )
        result = parse_memory_suggestion(transcript)
        assert result is None

    def test_empty_context_still_valid(self) -> None:
        transcript = (
            "MEMORY_SUGGESTION_START\n"
            "title: Some title\n"
            "learning: Some learning\n"
            "context: \n"
            "MEMORY_SUGGESTION_END\n"
        )
        result = parse_memory_suggestion(transcript)
        assert result is not None
        assert result["context"] == ""


# --- build_memory_issue_body tests ---


class TestBuildMemoryIssueBody:
    """Tests for building GitHub issue bodies for memory suggestions."""

    def test_structured_output(self) -> None:
        body = build_memory_issue_body(
            learning="Always run lint first",
            context="Found during issue #42",
            source="planner",
            reference="issue #42",
        )
        assert "## Memory Suggestion" in body
        assert "**Learning:** Always run lint first" in body
        assert "**Context:** Found during issue #42" in body
        assert "**Source:** planner during issue #42" in body

    def test_includes_source_and_reference(self) -> None:
        body = build_memory_issue_body(
            learning="Test learning",
            context="Test context",
            source="reviewer",
            reference="PR #99",
        )
        assert "reviewer during PR #99" in body


# --- load_memory_digest tests ---


class TestLoadMemoryDigest:
    """Tests for loading the memory digest from disk."""

    def test_reads_existing_file(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(repo_root=tmp_path)
        digest_dir = tmp_path / ".hydra" / "memory"
        digest_dir.mkdir(parents=True)
        digest_file = digest_dir / "digest.md"
        digest_file.write_text("## Learnings\n\nSome content here")

        result = load_memory_digest(config)
        assert "Some content here" in result

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(repo_root=tmp_path)
        result = load_memory_digest(config)
        assert result == ""

    def test_empty_file_returns_empty(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(repo_root=tmp_path)
        digest_dir = tmp_path / ".hydra" / "memory"
        digest_dir.mkdir(parents=True)
        (digest_dir / "digest.md").write_text("   \n  ")

        result = load_memory_digest(config)
        assert result == ""

    def test_caps_at_max_chars(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(repo_root=tmp_path)
        digest_dir = tmp_path / ".hydra" / "memory"
        digest_dir.mkdir(parents=True)
        # Write content longer than max_memory_prompt_chars (4000)
        long_content = "x" * 5000
        (digest_dir / "digest.md").write_text(long_content)

        result = load_memory_digest(config)
        assert len(result) < 5000
        assert "truncated" in result


# --- MemorySyncWorker tests ---


class TestMemorySyncWorkerExtractLearning:
    """Tests for learning extraction from issue bodies."""

    def test_structured_body(self) -> None:
        body = (
            "## Memory Suggestion\n\n"
            "**Learning:** Always use atomic writes for state files\n\n"
            "**Context:** Found during testing\n"
        )
        result = MemorySyncWorker._extract_learning(body)
        assert result == "Always use atomic writes for state files"

    def test_unstructured_fallback(self) -> None:
        body = "This is just a plain issue body with some text about a learning."
        result = MemorySyncWorker._extract_learning(body)
        assert result == body.strip()

    def test_empty_body(self) -> None:
        result = MemorySyncWorker._extract_learning("")
        assert result == ""

    def test_whitespace_body(self) -> None:
        result = MemorySyncWorker._extract_learning("   \n  ")
        assert result == ""


class TestMemorySyncWorkerBuildDigest:
    """Tests for digest building."""

    def test_sorts_newest_first(self) -> None:
        learnings = [
            (1, "Old learning", "2024-01-01T00:00:00"),
            (2, "New learning", "2024-06-01T00:00:00"),
        ]
        # Pre-sorted newest-first (caller's responsibility)
        learnings_sorted = sorted(learnings, key=lambda x: x[2], reverse=True)
        digest = MemorySyncWorker._build_digest(learnings_sorted)
        # New learning should come before old
        pos_new = digest.index("New learning")
        pos_old = digest.index("Old learning")
        assert pos_new < pos_old

    def test_formats_with_separators(self) -> None:
        learnings = [
            (1, "Learning one", "2024-01-01"),
            (2, "Learning two", "2024-01-02"),
        ]
        digest = MemorySyncWorker._build_digest(learnings)
        assert "---" in digest

    def test_header_includes_count(self) -> None:
        learnings = [
            (1, "Learning one", "2024-01-01"),
            (2, "Learning two", "2024-01-02"),
            (3, "Learning three", "2024-01-03"),
        ]
        digest = MemorySyncWorker._build_digest(learnings)
        assert "3 learnings" in digest


class TestMemorySyncWorkerCompactDigest:
    """Tests for digest compaction."""

    @pytest.mark.asyncio
    async def test_under_limit_no_truncation(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(repo_root=tmp_path)
        worker = MemorySyncWorker(config, MagicMock(), MagicMock())
        learnings = [
            (1, "Short learning", "2024-01-01"),
        ]
        result = await worker._compact_digest(learnings, max_chars=10000)
        assert "truncated" not in result

    @pytest.mark.asyncio
    async def test_dedup_removes_near_duplicates(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(repo_root=tmp_path)
        worker = MemorySyncWorker(config, MagicMock(), MagicMock())
        learnings = [
            (
                1,
                "Always run make lint before make test to catch formatting",
                "2024-01-01",
            ),
            (2, "Always run make lint before make test to catch issues", "2024-01-02"),
            (3, "Use atomic writes for state persistence", "2024-01-03"),
        ]
        result = await worker._compact_digest(learnings, max_chars=10000)
        # Should have deduped the similar lint learnings
        assert "compacted" in result

    @pytest.mark.asyncio
    async def test_over_limit_calls_model(self, tmp_path: Path) -> None:
        """When dedup isn't enough, the worker calls a cheap model for summarisation."""
        config = ConfigFactory.create(repo_root=tmp_path)
        worker = MemorySyncWorker(config, MagicMock(), MagicMock())
        learnings = [
            (
                i,
                f"A very long learning about topic number {i} " * 10,
                f"2024-01-{i:02d}",
            )
            for i in range(1, 20)
        ]
        # Mock the model call to return a short summary
        worker._summarise_with_model = AsyncMock(  # type: ignore[method-assign]
            return_value="## Accumulated Learnings\n*Summarised*\n\n- Condensed.\n"
        )
        result = await worker._compact_digest(learnings, max_chars=500)
        worker._summarise_with_model.assert_called_once()
        assert "Condensed" in result

    @pytest.mark.asyncio
    async def test_over_limit_model_failure_falls_back_to_truncation(
        self, tmp_path: Path
    ) -> None:
        """If the model call fails, fall back to truncation."""
        config = ConfigFactory.create(repo_root=tmp_path)
        worker = MemorySyncWorker(config, MagicMock(), MagicMock())
        learnings = [
            (
                i,
                f"A very long learning about topic number {i} " * 10,
                f"2024-01-{i:02d}",
            )
            for i in range(1, 20)
        ]
        # Mock the model call to return None (failure)
        worker._summarise_with_model = AsyncMock(return_value=None)  # type: ignore[method-assign]
        result = await worker._compact_digest(learnings, max_chars=500)
        assert len(result) <= 520  # 500 + truncation marker
        assert "truncated" in result


class TestMemorySyncWorkerSync:
    """Tests for the full sync method."""

    @pytest.mark.asyncio
    async def test_no_issues_returns_zero_count(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(repo_root=tmp_path)
        state = MagicMock()
        state.get_memory_state.return_value = ([], "", None)
        bus = MagicMock()

        worker = MemorySyncWorker(config, state, bus)
        stats = await worker.sync([])

        assert stats["item_count"] == 0
        state.update_memory_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_builds_digest_from_issues(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(repo_root=tmp_path)
        state = MagicMock()
        state.get_memory_state.return_value = ([], "", None)
        bus = MagicMock()

        worker = MemorySyncWorker(config, state, bus)
        issues = [
            {
                "number": 10,
                "title": "[Memory] Test learning",
                "body": "## Memory Suggestion\n\n**Learning:** Always test first\n\n**Context:** Found in testing",
                "createdAt": "2024-06-01T00:00:00Z",
            },
            {
                "number": 20,
                "title": "[Memory] Another learning",
                "body": "## Memory Suggestion\n\n**Learning:** Use type hints\n\n**Context:** Code review",
                "createdAt": "2024-05-01T00:00:00Z",
            },
        ]
        stats = await worker.sync(issues)

        assert stats["item_count"] == 2
        assert stats["action"] == "synced"
        # Digest file should exist
        digest_path = tmp_path / ".hydra" / "memory" / "digest.md"
        assert digest_path.exists()
        content = digest_path.read_text()
        assert "Always test first" in content
        assert "Use type hints" in content

    @pytest.mark.asyncio
    async def test_skips_compaction_when_no_change(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(repo_root=tmp_path)
        state = MagicMock()
        state.get_memory_state.return_value = ([10, 20], "somehash", "2024-06-01")
        bus = MagicMock()

        # Write a digest so the read works
        digest_dir = tmp_path / ".hydra" / "memory"
        digest_dir.mkdir(parents=True)
        (digest_dir / "digest.md").write_text("existing digest")

        worker = MemorySyncWorker(config, state, bus)
        issues = [
            {"number": 10, "title": "A", "body": "B", "createdAt": ""},
            {"number": 20, "title": "C", "body": "D", "createdAt": ""},
        ]
        stats = await worker.sync(issues)

        assert stats["compacted"] is False
        assert stats["item_count"] == 2

    @pytest.mark.asyncio
    async def test_detects_new_issues_and_rebuilds(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(repo_root=tmp_path)
        state = MagicMock()
        state.get_memory_state.return_value = ([10], "oldhash", "2024-05-01")
        bus = MagicMock()

        worker = MemorySyncWorker(config, state, bus)
        issues = [
            {
                "number": 10,
                "title": "A",
                "body": "**Learning:** Old thing",
                "createdAt": "2024-05-01",
            },
            {
                "number": 30,
                "title": "B",
                "body": "**Learning:** New thing",
                "createdAt": "2024-06-01",
            },
        ]
        stats = await worker.sync(issues)

        assert stats["item_count"] == 2
        # State should be updated with new IDs
        state.update_memory_state.assert_called()
        call_args = state.update_memory_state.call_args
        assert 30 in call_args[0][0]

    @pytest.mark.asyncio
    async def test_updates_state(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(repo_root=tmp_path)
        state = MagicMock()
        state.get_memory_state.return_value = ([], "", None)
        bus = MagicMock()

        worker = MemorySyncWorker(config, state, bus)
        issues = [
            {
                "number": 5,
                "title": "T",
                "body": "**Learning:** Something",
                "createdAt": "",
            },
        ]
        await worker.sync(issues)

        state.update_memory_state.assert_called()
        call_args = state.update_memory_state.call_args[0]
        assert call_args[0] == [5]  # issue IDs
        assert isinstance(call_args[1], str)  # digest hash

    @pytest.mark.asyncio
    async def test_publish_sync_event(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(repo_root=tmp_path)
        state = MagicMock()
        bus = MagicMock()
        bus.publish = AsyncMock()

        worker = MemorySyncWorker(config, state, bus)
        stats = {
            "action": "synced",
            "item_count": 3,
            "compacted": False,
            "digest_chars": 100,
        }
        await worker.publish_sync_event(stats)

        bus.publish.assert_called_once()
        event = bus.publish.call_args[0][0]
        assert event.type.value == "memory_sync"
        assert event.data["item_count"] == 3


# --- State tracking tests ---


class TestMemoryState:
    """Tests for memory state persistence in StateTracker."""

    def test_update_and_get_memory_state(self, tmp_path: Path) -> None:
        from state import StateTracker

        state_file = tmp_path / "state.json"
        tracker = StateTracker(state_file)

        tracker.update_memory_state([1, 2, 3], "abc123")

        ids, hash_val, last_synced = tracker.get_memory_state()
        assert ids == [1, 2, 3]
        assert hash_val == "abc123"
        assert last_synced is not None

    def test_get_memory_state_defaults(self, tmp_path: Path) -> None:
        from state import StateTracker

        state_file = tmp_path / "state.json"
        tracker = StateTracker(state_file)

        ids, hash_val, last_synced = tracker.get_memory_state()
        assert ids == []
        assert hash_val == ""
        assert last_synced is None

    def test_memory_state_persists_to_disk(self, tmp_path: Path) -> None:
        from state import StateTracker

        state_file = tmp_path / "state.json"
        tracker = StateTracker(state_file)
        tracker.update_memory_state([10, 20], "hash1")

        # Reload from disk
        tracker2 = StateTracker(state_file)
        ids, hash_val, last_synced = tracker2.get_memory_state()
        assert ids == [10, 20]
        assert hash_val == "hash1"
        assert last_synced is not None


# --- Config tests ---


class TestMemoryConfig:
    """Tests for memory-related config fields."""

    def test_memory_label_default(self) -> None:
        from config import HydraConfig

        config = HydraConfig(repo="test/repo")
        assert config.memory_label == ["hydra-memory"]

    def test_memory_label_custom(self) -> None:
        config = ConfigFactory.create(memory_label=["custom-memory"])
        assert config.memory_label == ["custom-memory"]

    def test_memory_sync_interval_default(self) -> None:
        from config import HydraConfig

        config = HydraConfig(repo="test/repo")
        assert config.memory_sync_interval == 3600

    def test_max_memory_chars_default(self) -> None:
        from config import HydraConfig

        config = HydraConfig(repo="test/repo")
        assert config.max_memory_chars == 4000

    def test_max_memory_prompt_chars_default(self) -> None:
        from config import HydraConfig

        config = HydraConfig(repo="test/repo")
        assert config.max_memory_prompt_chars == 4000

    def test_memory_label_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from config import HydraConfig

        monkeypatch.setenv("HYDRA_LABEL_MEMORY", "my-memory-label")
        config = HydraConfig(repo="test/repo")
        assert config.memory_label == ["my-memory-label"]

    def test_memory_sync_interval_env_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from config import HydraConfig

        monkeypatch.setenv("HYDRA_MEMORY_SYNC_INTERVAL", "60")
        config = HydraConfig(repo="test/repo")
        assert config.memory_sync_interval == 60


# --- CLI tests ---


class TestMemoryCLI:
    """Tests for memory-related CLI arguments."""

    def test_memory_label_arg_parsed(self) -> None:
        from cli import build_config, parse_args

        args = parse_args(["--memory-label", "custom-mem"])
        config = build_config(args)
        assert config.memory_label == ["custom-mem"]

    def test_memory_sync_interval_arg_parsed(self) -> None:
        from cli import build_config, parse_args

        args = parse_args(["--memory-sync-interval", "60"])
        config = build_config(args)
        assert config.memory_sync_interval == 60


# --- Models tests ---


class TestMemoryModels:
    """Tests for memory-related model fields."""

    def test_state_data_memory_fields_default(self) -> None:
        from models import StateData

        data = StateData()
        assert data.memory_issue_ids == []
        assert data.memory_digest_hash == ""
        assert data.memory_last_synced is None

    def test_control_status_config_memory_label(self) -> None:
        from models import ControlStatusConfig

        cfg = ControlStatusConfig(memory_label=["hydra-memory"])
        assert cfg.memory_label == ["hydra-memory"]

    def test_github_issue_created_at_from_camel_case(self) -> None:
        from models import GitHubIssue

        issue = GitHubIssue.model_validate(
            {
                "number": 42,
                "title": "Test",
                "createdAt": "2024-06-15T12:00:00Z",
            }
        )
        assert issue.created_at == "2024-06-15T12:00:00Z"

    def test_github_issue_created_at_default_empty(self) -> None:
        from models import GitHubIssue

        issue = GitHubIssue(number=1, title="Test")
        assert issue.created_at == ""

    def test_github_issue_created_at_snake_case(self) -> None:
        from models import GitHubIssue

        issue = GitHubIssue(number=1, title="Test", created_at="2024-01-01")
        assert issue.created_at == "2024-01-01"


# --- Config: memory_compaction_model tests ---


class TestMemoryCompactionModelConfig:
    """Tests for the memory_compaction_model config field."""

    def test_default_is_haiku(self) -> None:
        from config import HydraConfig

        config = HydraConfig(repo="test/repo")
        assert config.memory_compaction_model == "haiku"

    def test_custom_model(self) -> None:
        config = ConfigFactory.create(memory_compaction_model="sonnet")
        assert config.memory_compaction_model == "sonnet"


# --- Model-based summarisation tests ---


class TestSummariseWithModel:
    """Tests for _summarise_with_model."""

    @pytest.mark.asyncio
    async def test_success_returns_wrapped_summary(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(
            repo_root=tmp_path, memory_compaction_model="haiku"
        )
        worker = MemorySyncWorker(config, MagicMock(), MagicMock())

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(
            return_value=(b"- Condensed learning one\n- Condensed learning two\n", b"")
        )

        import asyncio as _asyncio

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                _asyncio, "create_subprocess_exec", AsyncMock(return_value=mock_proc)
            )
            result = await worker._summarise_with_model("long content", 4000)

        assert result is not None
        assert "Accumulated Learnings" in result
        assert "Summarised" in result
        assert "Condensed learning one" in result

    @pytest.mark.asyncio
    async def test_nonzero_returncode_returns_none(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(repo_root=tmp_path)
        worker = MemorySyncWorker(config, MagicMock(), MagicMock())

        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"error"))

        import asyncio as _asyncio

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                _asyncio, "create_subprocess_exec", AsyncMock(return_value=mock_proc)
            )
            result = await worker._summarise_with_model("content", 4000)

        assert result is None

    @pytest.mark.asyncio
    async def test_timeout_returns_none(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(repo_root=tmp_path)
        worker = MemorySyncWorker(config, MagicMock(), MagicMock())

        import asyncio as _asyncio

        async def _raise_timeout(*a, **kw):  # noqa: ANN002, ANN003
            raise TimeoutError

        mock_proc = AsyncMock()
        mock_proc.communicate = _raise_timeout

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                _asyncio, "create_subprocess_exec", AsyncMock(return_value=mock_proc)
            )
            result = await worker._summarise_with_model("content", 4000)

        assert result is None

    @pytest.mark.asyncio
    async def test_file_not_found_returns_none(self, tmp_path: Path) -> None:
        config = ConfigFactory.create(repo_root=tmp_path)
        worker = MemorySyncWorker(config, MagicMock(), MagicMock())

        import asyncio as _asyncio

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                _asyncio,
                "create_subprocess_exec",
                AsyncMock(side_effect=FileNotFoundError("claude not found")),
            )
            result = await worker._summarise_with_model("content", 4000)

        assert result is None


# --- PR Manager tests ---


class TestMemoryPRManager:
    """Tests for memory label in PR manager."""

    def test_hydra_labels_includes_memory(self) -> None:
        from pr_manager import PRManager

        label_fields = [entry[0] for entry in PRManager._HYDRA_LABELS]
        assert "memory_label" in label_fields

    def test_memory_label_color(self) -> None:
        from pr_manager import PRManager

        for field, color, _ in PRManager._HYDRA_LABELS:
            if field == "memory_label":
                assert color == "1d76db"
                return
        pytest.fail("memory_label not found in _HYDRA_LABELS")


# --- Orchestrator tests ---


class TestMemorySyncLoop:
    """Tests for memory sync loop registration in orchestrator."""

    def test_memory_sync_in_loop_factories(self) -> None:
        """Verify memory_sync loop is registered in _supervise_loops."""
        # Read the source to check the loop is registered
        import inspect

        from orchestrator import HydraOrchestrator

        source = inspect.getsource(HydraOrchestrator._supervise_loops)
        assert "memory_sync" in source
        assert "_memory_sync_loop" in source
