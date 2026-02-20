"""Tests for dx/hydra/stream_parser.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from stream_parser import StreamParser, _summarize_input, parse_stream_event

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


def test_assistant_tool_use_edit():
    """Edit tool displays file_path only, not old/new text."""
    event = {
        "type": "assistant",
        "message": {
            "id": "msg_1",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_edit",
                    "name": "Edit",
                    "input": {
                        "file_path": "/src/models.py",
                        "old_text": "old code here",
                        "new_text": "new code here",
                    },
                },
            ],
        },
    }
    display, _ = parse_stream_event(json.dumps(event))
    assert "Edit" in display
    assert "/src/models.py" in display
    assert "old code here" not in display
    assert "new code here" not in display


def test_assistant_tool_use_write():
    """Write tool displays file_path only, not content."""
    event = {
        "type": "assistant",
        "message": {
            "id": "msg_1",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_write",
                    "name": "Write",
                    "input": {
                        "file_path": "/src/new_file.py",
                        "content": "print('hello world')",
                    },
                },
            ],
        },
    }
    display, _ = parse_stream_event(json.dumps(event))
    assert "Write" in display
    assert "/src/new_file.py" in display
    assert "print" not in display


def test_assistant_tool_use_glob():
    """Glob tool displays the pattern."""
    event = {
        "type": "assistant",
        "message": {
            "id": "msg_1",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_glob",
                    "name": "Glob",
                    "input": {"pattern": "**/*.py"},
                },
            ],
        },
    }
    display, _ = parse_stream_event(json.dumps(event))
    assert "Glob" in display
    assert "**/*.py" in display


def test_assistant_tool_use_notebookedit_fallback():
    """NotebookEdit has no special handler; falls through to generic fallback."""
    event = {
        "type": "assistant",
        "message": {
            "id": "msg_1",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_nb",
                    "name": "NotebookEdit",
                    "input": {"notebook_path": "/nb.ipynb", "cell_index": 3},
                },
            ],
        },
    }
    display, _ = parse_stream_event(json.dumps(event))
    assert "NotebookEdit" in display


def test_assistant_tool_use_unknown_tool_fallback():
    """Unknown tool names use the generic str(input)[:120] fallback."""
    event = {
        "type": "assistant",
        "message": {
            "id": "msg_1",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_unk",
                    "name": "SomeUnknownTool",
                    "input": {"foo": "bar"},
                },
            ],
        },
    }
    display, _ = parse_stream_event(json.dumps(event))
    assert "SomeUnknownTool" in display
    assert "foo" in display


def test_assistant_task_tool_without_subagent_type():
    """Task tool with only description and no subagent_type."""
    event = {
        "type": "assistant",
        "message": {
            "id": "msg_1",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_task2",
                    "name": "Task",
                    "input": {"description": "Search for patterns"},
                },
            ],
        },
    }
    display, _ = parse_stream_event(json.dumps(event))
    assert "Task" in display
    assert "Search for patterns" in display
    # Should NOT have a leading ": " from empty agent type
    assert "→ Task: Search for patterns" in display


def test_assistant_empty_content_list():
    """Assistant event with empty content list produces empty display."""
    event = {
        "type": "assistant",
        "message": {"id": "msg_1", "content": []},
    }
    display, result = parse_stream_event(json.dumps(event))
    assert display == ""
    assert result is None


def test_assistant_content_non_dict_blocks_skipped():
    """Non-dict items in content are skipped; only valid blocks are processed."""
    event = {
        "type": "assistant",
        "message": {
            "id": "msg_1",
            "content": [42, "string", None, {"type": "text", "text": "real"}],
        },
    }
    display, _ = parse_stream_event(json.dumps(event))
    assert display == "real"


def test_result_event_non_string_result():
    """Result event with non-string result returns the value as-is."""
    event = {"type": "result", "result": {"key": "value"}}
    display, result = parse_stream_event(json.dumps(event))
    assert display == ""
    assert result == {"key": "value"}


# ===========================================================================
# _summarize_input — direct unit tests
# ===========================================================================


def test_summarize_input_bash_truncation():
    """Bash command longer than 120 chars is truncated to 120."""
    long_cmd = "x" * 200
    result = _summarize_input("Bash", {"command": long_cmd})
    assert len(result) == 120
    assert result == long_cmd[:120]


def test_summarize_input_generic_fallback_truncation():
    """Generic fallback with input > 120 chars adds '...' suffix."""
    long_val = "a" * 200
    result = _summarize_input("UnknownTool", {"data": long_val})
    assert result.endswith("...")
    assert len(result) == 123  # 120 + "..."


def test_summarize_input_generic_fallback_no_truncation():
    """Generic fallback with short input does not add '...' suffix."""
    result = _summarize_input("UnknownTool", {"x": 1})
    assert not result.endswith("...")


def test_summarize_input_task_truncation():
    """Task description longer than 120 chars is truncated."""
    long_desc = "d" * 200
    result = _summarize_input("Task", {"description": long_desc})
    assert len(result) == 120


def test_summarize_input_task_with_agent_truncation():
    """Task with agent and long description is truncated to 120 total."""
    long_desc = "d" * 200
    result = _summarize_input(
        "Task", {"description": long_desc, "subagent_type": "Explore"}
    )
    assert len(result) == 120
    assert result.startswith("Explore: ")


def test_summarize_input_edit_shows_only_file_path():
    """Edit summary shows only file_path, not old/new text."""
    result = _summarize_input(
        "Edit",
        {
            "file_path": "/src/foo.py",
            "old_text": "old stuff",
            "new_text": "new stuff",
        },
    )
    assert result == "/src/foo.py"


def test_summarize_input_write_shows_only_file_path():
    """Write summary shows only file_path, not content."""
    result = _summarize_input(
        "Write",
        {
            "file_path": "/src/bar.py",
            "content": "lots of code",
        },
    )
    assert result == "/src/bar.py"


def test_summarize_input_glob_shows_pattern():
    """Glob summary shows the pattern."""
    result = _summarize_input("Glob", {"pattern": "**/*.ts"})
    assert result == "**/*.ts"


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

    def test_user_message_multiple_tool_results(self):
        """Only the first tool_result's preview appears (early return)."""
        parser = StreamParser()
        event = {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_1",
                        "content": "First result",
                    },
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_2",
                        "content": "Second result",
                    },
                ],
            },
        }
        display, _ = parser.parse(json.dumps(event))
        assert "First result" in display
        assert "Second result" not in display

    def test_user_message_non_tool_result_content(self):
        """User event with only text content (no tool_result) returns empty."""
        parser = StreamParser()
        event = {
            "type": "user",
            "message": {
                "content": [
                    {"type": "text", "text": "Some user text"},
                ],
            },
        }
        display, _ = parser.parse(json.dumps(event))
        assert display == ""

    def test_user_message_empty_content(self):
        """User event with empty content list returns empty."""
        parser = StreamParser()
        event = {
            "type": "user",
            "message": {"content": []},
        }
        display, _ = parser.parse(json.dumps(event))
        assert display == ""

    def test_user_tool_result_long_content_truncated(self):
        """User tool_result content > 80 chars is truncated with ellipsis."""
        parser = StreamParser()
        long_content = "x" * 100
        event = {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_1",
                        "content": long_content,
                    },
                ],
            },
        }
        display, _ = parser.parse(json.dumps(event))
        assert "…" in display
        # The preview part (after "    ← ") should be 80 chars + ellipsis
        preview = display.replace("    ← ", "")
        assert len(preview) == 81  # 80 chars + "…"
