"""Parse Claude Code ``stream-json`` output into human-readable transcript lines."""

from __future__ import annotations

import json


class StreamParser:
    """Stateful parser for ``claude -p --output-format stream-json``.

    The stream-json format emits one JSON object per line:
    - ``assistant`` events contain a ``message.content`` array with
      ``text`` and ``tool_use`` blocks.  Each event is a *cumulative*
      snapshot — the same content repeats as the turn grows.
    - ``user`` events carry tool results (we show a summary).
    - ``result`` events carry the final output.

    This parser tracks what it has already shown so each call to
    :meth:`parse` returns only *new* display content.
    """

    def __init__(self) -> None:
        self._seen_tool_ids: set[str] = set()
        self._prev_text_len: int = 0
        self._prev_msg_id: str = ""

    def parse(self, raw_line: str) -> tuple[str, str | None]:
        """Parse a single stream-json line.

        Returns ``(display_text, result_text)``:
        - *display_text* is human-readable text for the live transcript.
        - *result_text* is non-None only for the final ``result`` event.
        """
        try:
            event = json.loads(raw_line)
        except (json.JSONDecodeError, TypeError):
            return (raw_line, None)

        event_type = event.get("type", "")

        if event_type == "assistant":
            return self._parse_assistant(event), None

        if event_type == "result":
            return ("", event.get("result", ""))

        if event_type == "user":
            return self._parse_user(event), None

        return ("", None)

    def _parse_assistant(self, event: dict) -> str:  # type: ignore[type-arg]
        """Extract new content from an assistant message event."""
        message = event.get("message", {})
        msg_id = message.get("id", "")
        content = message.get("content", [])

        # Reset text tracking when a new turn starts
        if msg_id != self._prev_msg_id:
            self._prev_text_len = 0
            self._prev_msg_id = msg_id

        parts: list[str] = []

        # Collect text delta and new tool_use blocks
        full_text = ""
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                full_text += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_id = block.get("id", "")
                if tool_id and tool_id not in self._seen_tool_ids:
                    self._seen_tool_ids.add(tool_id)
                    name = block.get("name", "?")
                    tool_input = block.get("input", {})
                    parts.append(f"  → {name}: {_summarize_input(name, tool_input)}")

        # Emit text delta
        if len(full_text) > self._prev_text_len:
            delta = full_text[self._prev_text_len:].strip()
            self._prev_text_len = len(full_text)
            if delta:
                parts.insert(0, delta)

        return "\n".join(parts)

    def _parse_user(self, event: dict) -> str:  # type: ignore[type-arg]
        """Extract a brief summary from a user (tool result) event."""
        message = event.get("message", {})
        content = message.get("content", [])
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                # Show a brief indicator that a tool returned
                tool_id = block.get("tool_use_id", "")
                content_val = block.get("content", "")
                if isinstance(content_val, str) and content_val:
                    preview = content_val[:80].replace("\n", " ")
                    return f"    ← {preview}{'…' if len(content_val) > 80 else ''}"
        return ""


# Stateless convenience function (for tests and simple use cases)
def parse_stream_event(raw_line: str) -> tuple[str, str | None]:
    """Stateless single-event parse — no delta tracking."""
    try:
        event = json.loads(raw_line)
    except (json.JSONDecodeError, TypeError):
        return (raw_line, None)

    event_type = event.get("type", "")

    if event_type == "assistant":
        message = event.get("message", {})
        content = message.get("content", [])
        parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                text = block.get("text", "").strip()
                if text:
                    parts.append(text)
            elif block.get("type") == "tool_use":
                name = block.get("name", "?")
                tool_input = block.get("input", {})
                parts.append(f"  → {name}: {_summarize_input(name, tool_input)}")
        return ("\n".join(parts), None)

    if event_type == "result":
        return ("", event.get("result", ""))

    return ("", None)


def _summarize_input(name: str, tool_input: dict) -> str:  # type: ignore[type-arg]
    """One-line summary of a tool call's input."""
    if name in ("Read", "read"):
        return tool_input.get("file_path", str(tool_input))[:120]
    if name in ("Edit", "edit"):
        return tool_input.get("file_path", "?")[:120]
    if name in ("Write", "write"):
        return tool_input.get("file_path", str(tool_input))[:120]
    if name in ("Glob", "glob"):
        return tool_input.get("pattern", str(tool_input))[:120]
    if name in ("Grep", "grep"):
        pattern = tool_input.get("pattern", "")
        path = tool_input.get("path", ".")
        return f"/{pattern}/ in {path}"[:120]
    if name in ("Bash", "bash"):
        return tool_input.get("command", str(tool_input))[:120]
    if name in ("Task", "task"):
        desc = tool_input.get("description", "")
        agent = tool_input.get("subagent_type", "")
        return f"{agent}: {desc}"[:120] if agent else desc[:120]
    # Generic fallback
    summary = str(tool_input)
    return summary[:120] + ("..." if len(summary) > 120 else "")
