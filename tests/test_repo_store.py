"""Tests for RepoStore repo persistence."""

from __future__ import annotations

from pathlib import Path

from repo_store import RepoRecord, RepoStore


def test_upsert_adds_record_and_normalizes_path(tmp_path: Path) -> None:
    store = RepoStore(tmp_path)
    repo_path = tmp_path / "example"
    repo_path.mkdir()

    record = RepoRecord(slug="acme-repo", repo="acme/repo", path=str(repo_path))
    stored = store.upsert(record)

    assert stored.slug == "acme-repo"
    assert Path(stored.path).resolve() == repo_path.resolve()
    listed = store.list()
    assert len(listed) == 1
    assert listed[0].slug == "acme-repo"


def test_upsert_replaces_existing_slug(tmp_path: Path) -> None:
    store = RepoStore(tmp_path)
    first = RepoRecord(slug="acme-repo", repo="acme/repo", path=str(tmp_path / "first"))
    second = RepoRecord(
        slug="acme-repo", repo="acme/repo", path=str(tmp_path / "second")
    )

    store.upsert(first)
    updated = store.upsert(second)

    assert Path(updated.path).name == "second"
    listed = store.list()
    assert len(listed) == 1
    assert Path(listed[0].path).name == "second"


def test_remove_returns_true_when_record_removed(tmp_path: Path) -> None:
    store = RepoStore(tmp_path)
    record = RepoRecord(slug="acme-repo", repo="acme/repo", path=str(tmp_path / "repo"))
    store.upsert(record)

    assert store.remove("acme-repo") is True
    assert store.list() == []
    assert store.remove("missing") is False
