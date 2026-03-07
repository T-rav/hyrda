"""Tests for repo_registry_store.RepoRegistryStore."""

from __future__ import annotations

from pathlib import Path

from repo_registry_store import RepoEntry, RepoRegistryStore


class TestRepoRegistryStore:
    def test_load_missing_returns_empty(self, tmp_path: Path) -> None:
        store = RepoRegistryStore(tmp_path)
        assert store.load() == []

    def test_add_and_round_trip(self, tmp_path: Path) -> None:
        store = RepoRegistryStore(tmp_path)
        entry = RepoEntry(slug="org-repo", path="/repos/org-repo", auto_start=True)
        store.add(entry)
        loaded = store.load()
        assert len(loaded) == 1
        assert loaded[0].model_dump() == entry.model_dump()

    def test_add_overwrites_existing_slug(self, tmp_path: Path) -> None:
        store = RepoRegistryStore(tmp_path)
        first = RepoEntry(slug="org-repo", path="/repos/one", auto_start=True)
        updated = RepoEntry(slug="org-repo", path="/repos/two", auto_start=False)
        store.add(first)
        store.add(updated)
        loaded = store.load()
        assert len(loaded) == 1
        assert loaded[0].path == "/repos/two"
        assert loaded[0].auto_start is False

    def test_remove_deletes_entry(self, tmp_path: Path) -> None:
        store = RepoRegistryStore(tmp_path)
        store.add(RepoEntry(slug="a", path="/repos/a"))
        store.add(RepoEntry(slug="b", path="/repos/b"))
        assert store.remove("a") is True
        remaining = [entry.slug for entry in store.load()]
        assert remaining == ["b"]

    def test_remove_returns_false_when_missing(self, tmp_path: Path) -> None:
        store = RepoRegistryStore(tmp_path)
        assert store.remove("missing") is False

    def test_corrupt_file_is_quarantined(self, tmp_path: Path) -> None:
        store = RepoRegistryStore(tmp_path)
        store.path.parent.mkdir(parents=True, exist_ok=True)
        store.path.write_text("not-json")
        entries = store.load()
        assert entries == []
        backups = list(store.path.parent.glob("repos.json.corrupt*"))
        assert backups, "Expected corrupt file to be renamed"

    def test_quarantine_increments_counter_when_backup_exists(
        self, tmp_path: Path
    ) -> None:
        store = RepoRegistryStore(tmp_path)
        # Pre-create the first backup name to force counter increment
        first_backup = store.path.with_suffix(store.path.suffix + ".corrupt")
        first_backup.write_text("old")
        store.path.write_text("not-json")
        store.load()
        # Both original and incremented backup should exist
        backups = list(store.path.parent.glob("repos.json.corrupt*"))
        assert len(backups) >= 2  # noqa: PLR2004

    def test_load_skips_invalid_entries(self, tmp_path: Path) -> None:
        store = RepoRegistryStore(tmp_path)
        # slug is required; write a record missing it
        store.path.write_text('[{"path": "/foo"}]\n')
        entries = store.load()
        assert entries == []

    def test_load_skips_non_dict_entries(self, tmp_path: Path) -> None:
        store = RepoRegistryStore(tmp_path)
        store.path.write_text('[{"slug": "a", "path": "/a"}, "not-an-object"]\n')
        entries = store.load()
        assert len(entries) == 1
        assert entries[0].slug == "a"

    def test_load_non_list_json_returns_empty(self, tmp_path: Path) -> None:
        store = RepoRegistryStore(tmp_path)
        store.path.write_text('{"slug": "a"}\n')
        entries = store.load()
        assert entries == []

    def test_load_oserror_returns_empty(self, tmp_path: Path) -> None:
        from unittest.mock import MagicMock, patch

        store = RepoRegistryStore(tmp_path)
        mock_path = MagicMock(spec=Path)
        mock_path.read_text.side_effect = OSError("perm denied")
        mock_path.__truediv__ = lambda self, other: mock_path
        with patch.object(store, "_path", mock_path):
            entries = store.load()
        assert entries == []

    def test_entry_slug_whitespace_trimmed(self) -> None:
        entry = RepoEntry(slug="  org-repo  ")
        assert entry.slug == "org-repo"

    def test_entry_slug_whitespace_only_raises(self) -> None:
        import pytest
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            RepoEntry(slug="   ")

    def test_entry_path_whitespace_trimmed_to_none(self) -> None:
        entry = RepoEntry(slug="a", path="   ")
        assert entry.path is None

    def test_entry_repo_whitespace_trimmed_to_none(self) -> None:
        entry = RepoEntry(slug="a", repo="   ")
        assert entry.repo is None

    def test_entry_path_none_stays_none(self) -> None:
        entry = RepoEntry(slug="a", path=None)
        assert entry.path is None

    def test_entry_repo_none_stays_none(self) -> None:
        entry = RepoEntry(slug="a", repo=None)
        assert entry.repo is None
