"""Tests for dx/hydra/stream_parser.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from stream_parser import StreamParser, parse_stream_event

# ===========================================================================
# Stateless parse_stream_event
# ===========================================================================


def test_plain_text_passes_through():
    display, result = parse_stream_event("Hello world")
    assert display == "Hello world"
    assert result is None


def test_empty_string():
    display, result = parse_stream_event("")
    assert display == ""
    assert result is None


def test_invalid_json_passes_through():
    display, result = parse_stream_event("{not valid json")
    assert display == "{not valid json"
    assert result is None


def test_assistant_text_content():
    event = {
        "type": "assistant",
        "message": {
            "id": "msg_1",
            "content": [{"type": "text", "text": "Let me explore the codebase."}],
        },
    }
    display, result = parse_stream_event(json.dumps(event))
    assert display == "Let me explore the codebase."
    assert result is None


def test_assistant_whitespace_only_text():
    event = {
        "type": "assistant",
        "message": {"id": "msg_1", "content": [{"type": "text", "text": "   \n\n"}]},
    }
    display, _ = parse_stream_event(json.dumps(event))
    assert display.strip() == ""


def test_assistant_tool_use_in_content():
    """Tool use blocks in message.content are displayed."""
    event = {
        "type": "assistant",
        "message": {
            "id": "msg_1",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "Read",
                    "input": {"file_path": "/src/models.py"},
                },
            ],
        },
    }
    display, _ = parse_stream_event(json.dumps(event))
    assert "Read" in display
    assert "/src/models.py" in display


def test_assistant_tool_use_grep():
    event = {
        "type": "assistant",
        "message": {
            "id": "msg_1",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_2",
                    "name": "Grep",
                    "input": {"pattern": "class Foo", "path": "/src"},
                },
            ],
        },
    }
    display, _ = parse_stream_event(json.dumps(event))
    assert "Grep" in display
    assert "class Foo" in display


def test_assistant_tool_use_bash():
    event = {
        "type": "assistant",
        "message": {
            "id": "msg_1",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_3",
                    "name": "Bash",
                    "input": {"command": "make test"},
                },
            ],
        },
    }
    display, _ = parse_stream_event(json.dumps(event))
    assert "Bash" in display
    assert "make test" in display


def test_assistant_mixed_text_and_tool():
    event = {
        "type": "assistant",
        "message": {
            "id": "msg_1",
            "content": [
                {"type": "text", "text": "Looking at the file."},
                {
                    "type": "tool_use",
                    "id": "toolu_4",
                    "name": "Read",
                    "input": {"file_path": "/a.py"},
                },
            ],
        },
    }
    display, _ = parse_stream_event(json.dumps(event))
    assert "Looking at the file." in display
    assert "Read" in display


def test_assistant_task_tool_shows_agent_type():
    event = {
        "type": "assistant",
        "message": {
            "id": "msg_1",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_5",
                    "name": "Task",
                    "input": {
                        "description": "Explore code",
                        "subagent_type": "Explore",
                    },
                },
            ],
        },
    }
    display, _ = parse_stream_event(json.dumps(event))
    assert "Task" in display
    assert "Explore" in display


def test_result_event():
    event = {
        "type": "result",
        "subtype": "success",
        "result": "PLAN_START\nStep 1\nPLAN_END\nSUMMARY: done",
    }
    display, result = parse_stream_event(json.dumps(event))
    assert display == ""
    assert result == "PLAN_START\nStep 1\nPLAN_END\nSUMMARY: done"


def test_result_event_empty():
    event = {"type": "result", "result": ""}
    display, result = parse_stream_event(json.dumps(event))
    assert display == ""
    assert result == ""


def test_system_event_skipped():
    event = {"type": "system", "subtype": "init", "session_id": "abc"}
    display, result = parse_stream_event(json.dumps(event))
    assert display == ""
    assert result is None


def test_unknown_event_skipped():
    event = {"type": "something_else", "data": 123}
    display, result = parse_stream_event(json.dumps(event))
    assert display == ""
    assert result is None


# ===========================================================================
# StreamParser (stateful) — delta tracking
# ===========================================================================


class TestStreamParserDelta:
    """StreamParser deduplicates cumulative assistant message events."""

    def test_first_message_returns_text(self):
        parser = StreamParser()
        event = {
            "type": "assistant",
            "message": {
                "id": "msg_1",
                "content": [{"type": "text", "text": "Hello"}],
            },
        }
        display, _ = parser.parse(json.dumps(event))
        assert display == "Hello"

    def test_cumulative_message_returns_only_delta(self):
        parser = StreamParser()
        e1 = {
            "type": "assistant",
            "message": {
                "id": "msg_1",
                "content": [{"type": "text", "text": "Hello"}],
            },
        }
        e2 = {
            "type": "assistant",
            "message": {
                "id": "msg_1",
                "content": [{"type": "text", "text": "Hello world"}],
            },
        }
        parser.parse(json.dumps(e1))
        display, _ = parser.parse(json.dumps(e2))
        assert display == "world"

    def test_same_text_returns_empty(self):
        parser = StreamParser()
        event = {
            "type": "assistant",
            "message": {
                "id": "msg_1",
                "content": [{"type": "text", "text": "Hello"}],
            },
        }
        parser.parse(json.dumps(event))
        display, _ = parser.parse(json.dumps(event))
        assert display == ""

    def test_new_turn_resets_text_tracking(self):
        parser = StreamParser()
        e1 = {
            "type": "assistant",
            "message": {
                "id": "msg_1",
                "content": [{"type": "text", "text": "Turn 1 text"}],
            },
        }
        e2 = {
            "type": "assistant",
            "message": {
                "id": "msg_2",
                "content": [{"type": "text", "text": "Turn 2 text"}],
            },
        }
        parser.parse(json.dumps(e1))
        display, _ = parser.parse(json.dumps(e2))
        assert display == "Turn 2 text"

    def test_tool_use_shown_once(self):
        parser = StreamParser()
        event = {
            "type": "assistant",
            "message": {
                "id": "msg_1",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "Read",
                        "input": {"file_path": "/a.py"},
                    },
                ],
            },
        }
        d1, _ = parser.parse(json.dumps(event))
        d2, _ = parser.parse(json.dumps(event))
        assert "Read" in d1
        assert d2 == ""  # already seen this tool_id

    def test_cumulative_message_with_new_tool(self):
        """Second snapshot adds a tool_use — only the tool is new."""
        parser = StreamParser()
        e1 = {
            "type": "assistant",
            "message": {
                "id": "msg_1",
                "content": [{"type": "text", "text": "Let me look"}],
            },
        }
        e2 = {
            "type": "assistant",
            "message": {
                "id": "msg_1",
                "content": [
                    {"type": "text", "text": "Let me look"},
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "Glob",
                        "input": {"pattern": "**/*.py"},
                    },
                ],
            },
        }
        parser.parse(json.dumps(e1))
        display, _ = parser.parse(json.dumps(e2))
        assert "Glob" in display
        assert "Let me look" not in display  # text unchanged

    def test_result_event_still_captured(self):
        parser = StreamParser()
        event = {"type": "result", "result": "Final output"}
        display, result = parser.parse(json.dumps(event))
        assert display == ""
        assert result == "Final output"

    def test_plain_text_passes_through(self):
        parser = StreamParser()
        display, result = parser.parse("not json")
        assert display == "not json"
        assert result is None

    def test_user_tool_result_shown(self):
        parser = StreamParser()
        event = {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_1",
                        "content": "File contents here...",
                    },
                ],
            },
        }
        display, _ = parser.parse(json.dumps(event))
        assert "File contents here" in display
