"""Memory digest system — persistent agent learnings across runs."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import tempfile
from contextlib import suppress
from datetime import UTC, datetime

from config import HydraConfig
from events import EventBus, EventType, HydraEvent
from models import MemorySuggestion
from pr_manager import PRManager
from state import StateTracker

logger = logging.getLogger("hydra.memory")

# Regex for MEMORY_SUGGESTION blocks in transcripts.
_SUGGESTION_RE = re.compile(
    r"MEMORY_SUGGESTION_START\s*\n(.*?)\nMEMORY_SUGGESTION_END",
    re.DOTALL,
)


def parse_memory_suggestions(transcript: str) -> list[MemorySuggestion]:
    """Parse ``MEMORY_SUGGESTION`` blocks from an agent transcript.

    Returns at most one suggestion (capped to prevent spam).
    """
    match = _SUGGESTION_RE.search(transcript)
    if not match:
        return []

    block = match.group(1)
    title = ""
    learning = ""
    context = ""

    for line in block.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("title:"):
            title = stripped[len("title:") :].strip()
        elif stripped.lower().startswith("learning:"):
            learning = stripped[len("learning:") :].strip()
        elif stripped.lower().startswith("context:"):
            context = stripped[len("context:") :].strip()

    if not title or not learning:
        return []

    return [MemorySuggestion(title=title, learning=learning, context=context)]


async def file_memory_suggestion(
    suggestion: MemorySuggestion,
    pr_manager: PRManager,
    config: HydraConfig,
) -> int:
    """File a memory suggestion as a GitHub issue.

    The issue is created with ``hydra-improve`` + ``hydra-hitl`` labels
    so it surfaces in the HITL tab for human review.

    Returns the issue number (0 in dry-run mode or on failure).
    """
    if config.dry_run:
        logger.info("[dry-run] Would file memory suggestion: %s", suggestion.title)
        return 0

    title = f"[Memory] {suggestion.title}"
    body = (
        f"## Memory Suggestion\n\n"
        f"**Learning:** {suggestion.learning}\n\n"
        f"**Context:** {suggestion.context}\n\n"
        f"**Source:** {suggestion.source}\n"
    )
    labels = [config.hitl_label[0]]
    if config.improve_label:
        labels.append(config.improve_label[0])

    return await pr_manager.create_issue(title, body, labels)


def load_digest(config: HydraConfig) -> str:
    """Read the memory digest file, returning empty string if absent."""
    try:
        if config.memory_digest_path.is_file():
            return config.memory_digest_path.read_text()
    except OSError:
        logger.warning("Could not read memory digest at %s", config.memory_digest_path)
    return ""


def _compile_digest(
    issues: list[dict[str, str | int]],
    max_entries: int,
) -> str:
    """Format memory issues into a markdown digest.

    Each issue dict must have ``number``, ``title``, and ``body`` keys.
    Issues are sorted by number descending (newest first) and capped
    at *max_entries*.
    """
    if not issues:
        now = datetime.now(UTC).isoformat()
        return f"# Hydra Memory Digest\n\n_Last updated: {now}_\n_Entries: 0_\n"

    # Sort by issue number descending (newest first)
    sorted_issues = sorted(
        issues, key=lambda x: int(str(x.get("number", 0))), reverse=True
    )
    capped = sorted_issues[:max_entries]

    entries: list[str] = []
    for issue in capped:
        title = str(issue.get("title", ""))
        body = str(issue.get("body", ""))

        # Strip "[Memory] " prefix from title if present
        if title.startswith("[Memory] "):
            title = title[len("[Memory] ") :]

        # Extract learning from structured body
        learning = _extract_field(body, "Learning")
        context = _extract_field(body, "Context")
        source_field = _extract_field(body, "Source")

        entry = f"## {title}\n"
        if learning:
            entry += f"**Learning:** {learning}\n"
        elif body:
            # Fallback: use first 500 chars of body
            entry += f"{body[:500]}\n"
        if context:
            entry += f"**Context:** {context}\n"
        if source_field:
            entry += f"**Source:** {source_field}\n"
        entry += f"**Issue:** #{issue.get('number', '?')}"
        entries.append(entry)

    now = datetime.now(UTC).isoformat()
    header = (
        f"# Hydra Memory Digest\n\n_Last updated: {now}_\n_Entries: {len(entries)}_\n"
    )
    body_text = "\n\n---\n\n".join(entries)
    return f"{header}\n---\n\n{body_text}\n"


def _extract_field(body: str, field_name: str) -> str:
    """Extract a ``**FieldName:** value`` line from markdown body."""
    pattern = rf"\*\*{re.escape(field_name)}:\*\*\s*(.+)"
    match = re.search(pattern, body)
    if match:
        return match.group(1).strip()
    return ""


async def sync(
    config: HydraConfig,
    state: StateTracker,
    event_bus: EventBus,
) -> None:
    """Poll ``hydra-memory`` issues and rebuild the local digest.

    Skips compaction when the set of memory issue numbers hasn't changed
    (hash-based detection via :class:`StateTracker`).
    """
    if config.dry_run:
        logger.info("[dry-run] Would sync memory digest")
        return

    # Fetch memory-labeled issues
    from issue_fetcher import IssueFetcher  # noqa: PLC0415

    fetcher = IssueFetcher(config)
    issues_raw = await fetcher.fetch_issues_by_labels(
        config.memory_label,
        config.memory_max_digest_entries * 2,  # fetch extra in case of churn
    )

    # Convert to dicts for digest compilation
    issues = [
        {
            "number": issue.number,
            "title": issue.title,
            "body": issue.body,
        }
        for issue in issues_raw
    ]

    current_ids = sorted(issue.number for issue in issues_raw)

    # Check if anything changed
    prev_ids, prev_hash, _ = state.get_memory_state()
    ids_hash = hashlib.sha256(str(current_ids).encode()).hexdigest()[:16]

    if current_ids == sorted(prev_ids) and ids_hash == prev_hash:
        logger.debug("Memory digest unchanged — skipping rebuild")
        return

    # Build and write digest atomically
    digest_text = _compile_digest(issues, config.memory_max_digest_entries)

    config.memory_digest_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=config.memory_digest_path.parent,
        prefix=".digest-",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w") as f:
            f.write(digest_text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, config.memory_digest_path)
    except BaseException:
        with suppress(OSError):
            os.unlink(tmp)
        raise

    # Update state
    state.update_memory_state(current_ids, ids_hash)

    # Publish event
    await event_bus.publish(
        HydraEvent(
            type=EventType.MEMORY_UPDATE,
            data={
                "action": "synced",
                "item_count": len(issues),
                "digest_chars": len(digest_text),
            },
        )
    )
    logger.info(
        "Memory digest rebuilt — %d entries, %d chars",
        len(issues),
        len(digest_text),
    )
