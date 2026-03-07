"""Persistent registry of repos managed by the dashboard server."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class RepoRecord:
    """Description of a registered repository."""

    slug: str
    repo: str
    path: str


class RepoStore:
    """Loads and saves repo registrations under ``repos.json``."""

    def __init__(self, data_root: Path) -> None:
        self._path = data_root / "repos.json"
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def list(self) -> list[RepoRecord]:
        with self._lock:
            payload = self._load()
        repos = payload.get("repos", [])
        results: list[RepoRecord] = []
        for entry in repos:
            slug = str(entry.get("slug", "")).strip()
            repo = str(entry.get("repo", "")).strip()
            path = str(entry.get("path", "")).strip()
            if not slug or not path:
                continue
            results.append(RepoRecord(slug=slug, repo=repo, path=path))
        return results

    def upsert(self, record: RepoRecord) -> RepoRecord:
        with self._lock:
            payload = self._load()
            repos: list[dict[str, Any]] = payload.setdefault("repos", [])
            replaced = False
            normalized_path = str(Path(record.path).expanduser().resolve())
            for existing in repos:
                if (
                    existing.get("slug") == record.slug
                    or existing.get("path") == normalized_path
                ):
                    existing.update(asdict(record))
                    existing["path"] = normalized_path
                    replaced = True
                    break
            if not replaced:
                entry = asdict(record)
                entry["path"] = normalized_path
                repos.append(entry)
            self._save(payload)
        return RepoRecord(slug=record.slug, repo=record.repo, path=normalized_path)

    def remove(self, slug: str) -> bool:
        slug = slug.strip()
        if not slug:
            return False
        with self._lock:
            payload = self._load()
            repos: list[dict[str, Any]] = payload.setdefault("repos", [])
            new_repos = [repo for repo in repos if repo.get("slug") != slug]
            if len(new_repos) == len(repos):
                return False
            payload["repos"] = new_repos
            self._save(payload)
        return True

    def get(self, slug: str) -> RepoRecord | None:
        slug = slug.strip()
        if not slug:
            return None
        for record in self.list():
            if record.slug == slug:
                return record
        return None

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {"repos": []}
        try:
            return json.loads(self._path.read_text())
        except json.JSONDecodeError:
            return {"repos": []}

    def _save(self, payload: dict[str, Any]) -> None:
        self._path.write_text(json.dumps(payload, indent=2))
