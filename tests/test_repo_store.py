"""Tests for repo_store.py persistence helpers."""

from __future__ import annotations

from pathlib import Path

from repo_store import RepoRecord, RepoRegistryStore


class TestRepoRegistryStore:
    def test_load_missing_file_returns_empty(self, tmp_path: Path) -> None:
        store = RepoRegistryStore(tmp_path)
        assert store.load() == []

    def test_upsert_and_load_round_trip(self, tmp_path: Path) -> None:
        store = RepoRegistryStore(tmp_path)
        repo_path = tmp_path / "my-repo"
        repo_path.mkdir()
        record = RepoRecord(
            slug="org-repo",
            repo="org/repo",
            path=str(repo_path),
            auto_registered=True,
        )

        stored = store.upsert(record)
        assert stored.auto_registered is True

        loaded = store.load()
        assert len(loaded) == 1
        assert loaded[0].slug == "org-repo"
        assert loaded[0].repo == "org/repo"
        assert loaded[0].auto_registered is True
        assert loaded[0].path == str(repo_path.resolve())

    def test_update_overrides_merges_values(self, tmp_path: Path) -> None:
        store = RepoRegistryStore(tmp_path)
        repo_path = tmp_path / "my-repo"
        repo_path.mkdir()
        store.upsert(
            RepoRecord(slug="org-repo", repo="org/repo", path=str(repo_path)),
        )

        assert store.update_overrides("org-repo", {"max_workers": 3}) is True
        loaded = store.load()
        assert loaded[0].overrides["max_workers"] == 3

        # Second update merges into existing overrides
        store.update_overrides("org-repo", {"model": "opus"})
        loaded = store.load()
        assert loaded[0].overrides == {"max_workers": 3, "model": "opus"}
