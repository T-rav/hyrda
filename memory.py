"""Memory digest system for persistent agent learnings."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import tempfile
from datetime import UTC, datetime
from typing import Any

from config import HydraConfig
from events import EventBus, EventType, HydraEvent
from state import StateTracker

logger = logging.getLogger("hydra.memory")


def parse_memory_suggestion(transcript: str) -> dict[str, str] | None:
    """Parse a MEMORY_SUGGESTION block from an agent transcript.

    Returns a dict with ``title``, ``learning``, and ``context`` keys,
    or ``None`` if no block is found.  Only the first block is returned
    (cap at 1 suggestion per agent run).
    """
    pattern = r"MEMORY_SUGGESTION_START\s*\n(.*?)\nMEMORY_SUGGESTION_END"
    match = re.search(pattern, transcript, re.DOTALL)
    if not match:
        return None

    block = match.group(1)
    result: dict[str, str] = {"title": "", "learning": "", "context": ""}

    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith("title:"):
            result["title"] = stripped[len("title:") :].strip()
        elif stripped.startswith("learning:"):
            result["learning"] = stripped[len("learning:") :].strip()
        elif stripped.startswith("context:"):
            result["context"] = stripped[len("context:") :].strip()

    if not result["title"] or not result["learning"]:
        return None

    return result


def build_memory_issue_body(
    learning: str, context: str, source: str, reference: str
) -> str:
    """Format a structured GitHub issue body for a memory suggestion."""
    return (
        f"## Memory Suggestion\n\n"
        f"**Learning:** {learning}\n\n"
        f"**Context:** {context}\n\n"
        f"**Source:** {source} during {reference}\n"
    )


def load_memory_digest(config: HydraConfig) -> str:
    """Read the memory digest from disk if it exists.

    Returns an empty string if the file is missing or empty.
    Content is capped at ``config.max_memory_prompt_chars``.
    """
    digest_path = config.repo_root / ".hydra" / "memory" / "digest.md"
    if not digest_path.is_file():
        return ""
    try:
        content = digest_path.read_text()
    except OSError:
        return ""
    if not content.strip():
        return ""
    max_chars = config.max_memory_prompt_chars
    if len(content) > max_chars:
        content = content[:max_chars] + "\n\n…(truncated)"
    return content


class MemorySyncWorker:
    """Polls ``hydra-memory`` issues and compiles them into a local digest."""

    def __init__(
        self,
        config: HydraConfig,
        state: StateTracker,
        event_bus: EventBus,
    ) -> None:
        self._config = config
        self._state = state
        self._bus = event_bus

    async def sync(self, issues: list[dict[str, Any]]) -> dict[str, Any]:
        """Main sync entry point.

        *issues* is a list of dicts with ``number``, ``title``, ``body``,
        and ``createdAt`` keys (from ``gh issue list --json``).

        Returns stats dict for event publishing.
        """
        current_ids = sorted(i["number"] for i in issues)
        prev_ids, prev_hash, _ = self._state.get_memory_state()

        if not issues:
            self._state.update_memory_state([], prev_hash)
            return {
                "action": "synced",
                "item_count": 0,
                "compacted": False,
                "digest_chars": 0,
            }

        # Check if issue set changed
        if current_ids == sorted(prev_ids):
            # No change — just update timestamp
            self._state.update_memory_state(current_ids, prev_hash)
            digest_path = self._config.repo_root / ".hydra" / "memory" / "digest.md"
            digest_chars = len(digest_path.read_text()) if digest_path.is_file() else 0
            return {
                "action": "synced",
                "item_count": len(issues),
                "compacted": False,
                "digest_chars": digest_chars,
            }

        # Extract learnings and build digest
        learnings: list[tuple[int, str, str]] = []
        for issue in issues:
            learning = self._extract_learning(issue.get("body", ""))
            created = issue.get("createdAt", "")
            if learning:
                learnings.append((issue["number"], learning, created))

        # Sort newest first
        learnings.sort(key=lambda x: x[2], reverse=True)

        # Build digest
        compacted = False
        digest = self._build_digest(learnings)
        max_chars = self._config.max_memory_chars
        if len(digest) > max_chars:
            digest = self._compact_digest(learnings, max_chars)
            compacted = True

        # Write individual items
        items_dir = self._config.repo_root / ".hydra" / "memory" / "items"
        items_dir.mkdir(parents=True, exist_ok=True)
        for num, learning, _ in learnings:
            item_path = items_dir / f"{num}.md"
            item_path.write_text(learning)

        # Atomic write of digest
        self._write_digest(digest)

        # Update state
        digest_hash = hashlib.sha256(digest.encode()).hexdigest()[:16]
        self._state.update_memory_state(current_ids, digest_hash)

        return {
            "action": "synced",
            "item_count": len(learnings),
            "compacted": compacted,
            "digest_chars": len(digest),
        }

    @staticmethod
    def _extract_learning(body: str) -> str:
        """Extract the learning content from an issue body.

        Looks for a ``## Memory Suggestion`` section with a
        ``**Learning:**`` line.  Falls back to the full body.
        """
        if not body or not body.strip():
            return ""

        # Try structured extraction
        learning_match = re.search(
            r"\*\*Learning:\*\*\s*(.+?)(?=\n\*\*|\n##|\Z)",
            body,
            re.DOTALL,
        )
        if learning_match:
            return learning_match.group(1).strip()

        # Fallback: return full body (stripped)
        return body.strip()

    @staticmethod
    def _build_digest(learnings: list[tuple[int, str, str]]) -> str:
        """Build the digest markdown from ``(issue_number, learning, created_at)`` tuples."""
        now = datetime.now(UTC).isoformat()
        header = (
            f"## Accumulated Learnings\n"
            f"*{len(learnings)} learnings — last synced {now}*\n"
        )
        sections = []
        for num, learning, _ in learnings:
            sections.append(f"- **#{num}:** {learning}")
        return header + "\n" + "\n---\n".join(sections) + "\n"

    @staticmethod
    def _compact_digest(learnings: list[tuple[int, str, str]], max_chars: int) -> str:
        """Deduplicate and truncate learnings to fit within *max_chars*.

        Uses keyword overlap for deduplication.  If still over limit
        after dedup, truncates to fit.
        """
        # Deduplicate by keyword overlap
        seen_keywords: list[set[str]] = []
        unique: list[tuple[int, str, str]] = []

        for num, learning, created in learnings:
            words = {
                w.lower() for w in re.findall(r"[a-zA-Z]+", learning) if len(w) >= 4
            }
            is_dup = False
            for existing in seen_keywords:
                if not words or not existing:
                    continue
                overlap = len(words & existing) / max(len(words), 1)
                if overlap > 0.7:
                    is_dup = True
                    break
            if not is_dup:
                unique.append((num, learning, created))
                seen_keywords.append(words)

        # Build with unique learnings
        now = datetime.now(UTC).isoformat()
        header = (
            f"## Accumulated Learnings\n"
            f"*{len(unique)} learnings (compacted) — last synced {now}*\n"
        )
        sections = []
        for num, learning, _ in unique:
            sections.append(f"- **#{num}:** {learning}")

        digest = header + "\n" + "\n---\n".join(sections) + "\n"

        # Truncate if still over limit
        if len(digest) > max_chars:
            digest = digest[:max_chars] + "\n\n…(truncated)"

        return digest

    def _write_digest(self, content: str) -> None:
        """Write digest to disk atomically."""
        digest_dir = self._config.repo_root / ".hydra" / "memory"
        digest_dir.mkdir(parents=True, exist_ok=True)
        digest_path = digest_dir / "digest.md"

        fd, tmp = tempfile.mkstemp(
            dir=digest_dir,
            prefix=".digest-",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, digest_path)
        except BaseException:
            import contextlib

            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise

    async def publish_sync_event(self, stats: dict[str, Any]) -> None:
        """Publish a MEMORY_SYNC event with *stats*."""
        await self._bus.publish(
            HydraEvent(
                type=EventType.MEMORY_SYNC,
                data=stats,
            )
        )
