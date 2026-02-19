# Plan for Issue #33

## Goal

Add direct unit tests for `AgentRunner._count_commits` (agent.py:316) which currently has zero direct test coverage. The method runs `git rev-list --count origin/main..{branch}` via `asyncio.create_subprocess_exec` and handles several error cases.

## Files to Modify

### `tests/test_agent.py`
Add a new `TestCountCommits` test class between `TestVerifyResult` (ends line 564) and `TestSaveTranscript` (starts line 566).

## Implementation Steps

1. **Add `TestCountCommits` class** at line 565 (after the `TestVerifyResult` section, before `TestSaveTranscript`), following the existing file organization pattern with section comment headers.

2. **Write 5 test methods**, all async, all patching `asyncio.create_subprocess_exec` at module level using the existing `_make_proc` helper already defined in the file:

### Tests to Write

| # | Test Name | Setup | Expected |
|---|-----------|-------|----------|
| 1 | `test_count_commits_happy_path` | proc returns `stdout=b"3\n"`, returncode=0 | Returns `3` |
| 2 | `test_count_commits_multi_digit` | proc returns `stdout=b"15\n"`, returncode=0 | Returns `15` |
| 3 | `test_count_commits_non_zero_exit_code` | proc returns returncode=1, stdout=b"" | Returns `0` (ValueError from `int("")`) |
| 4 | `test_count_commits_file_not_found` | `create_subprocess_exec` raises `FileNotFoundError` | Returns `0` |
| 5 | `test_count_commits_empty_stdout` | proc returns `stdout=b""`, returncode=0 | Returns `0` (ValueError from `int("")`) |

3. **Verify the subprocess is called with correct arguments**: In the happy path test, assert that `create_subprocess_exec` was called with `"git", "rev-list", "--count", "origin/main..agent/issue-42"` and proper `cwd`/`stdout`/`stderr` kwargs.

## Testing Strategy

- **Mocking pattern**: Patch `asyncio.create_subprocess_exec` at the module level (matching the existing pattern in `TestVerifyResult`), using the file-local `_make_proc` helper to build mock subprocess objects.
- **Runner instantiation**: Create `AgentRunner(config, event_bus)` inline in each test, matching the existing pattern.
- **Fixtures**: Use `config`, `event_bus`, and `tmp_path` fixtures from conftest.
- **No new imports needed**: All necessary imports (`patch`, `AsyncMock`, `pytest`, `AgentRunner`, `EventBus`) are already at the top of the file.

## Code Structure

```python
# ---------------------------------------------------------------------------
# AgentRunner._count_commits
# ---------------------------------------------------------------------------


class TestCountCommits:
    """Tests for AgentRunner._count_commits."""

    @pytest.mark.asyncio
    async def test_count_commits_returns_parsed_count(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """_count_commits should return the integer from git rev-list output."""
        runner = AgentRunner(config, event_bus)
        mock_proc = _make_proc(returncode=0, stdout=b"3\n")

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
            result = await runner._count_commits(tmp_path, "agent/issue-42")

        assert result == 3

    @pytest.mark.asyncio
    async def test_count_commits_parses_multi_digit(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """_count_commits should correctly parse multi-digit counts."""
        runner = AgentRunner(config, event_bus)
        mock_proc = _make_proc(returncode=0, stdout=b"15\n")

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
            result = await runner._count_commits(tmp_path, "agent/issue-42")

        assert result == 15

    @pytest.mark.asyncio
    async def test_count_commits_returns_zero_on_empty_stdout(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """_count_commits should return 0 when stdout is empty (ValueError)."""
        runner = AgentRunner(config, event_bus)
        mock_proc = _make_proc(returncode=0, stdout=b"")

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
            result = await runner._count_commits(tmp_path, "agent/issue-42")

        assert result == 0

    @pytest.mark.asyncio
    async def test_count_commits_returns_zero_on_nonzero_exit(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """_count_commits should return 0 when git exits with non-zero code."""
        runner = AgentRunner(config, event_bus)
        # Non-zero exit + empty stdout → int("") raises ValueError → returns 0
        mock_proc = _make_proc(returncode=1, stdout=b"")

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
            result = await runner._count_commits(tmp_path, "agent/issue-42")

        assert result == 0

    @pytest.mark.asyncio
    async def test_count_commits_returns_zero_on_file_not_found(
        self, config, event_bus: EventBus, tmp_path: Path
    ) -> None:
        """_count_commits should return 0 when git binary is not found."""
        runner = AgentRunner(config, event_bus)

        with patch(
            "asyncio.create_subprocess_exec", side_effect=FileNotFoundError
        ):
            result = await runner._count_commits(tmp_path, "agent/issue-42")

        assert result == 0
```

## Key Considerations

- **Non-zero exit code behavior**: Looking at `_count_commits` (line 316-331), a non-zero exit code does NOT directly return 0 — the method doesn't check `returncode`. It always tries `int(stdout.decode().strip())`. So if git fails with returncode=1 but stdout is empty, the `int("")` raises `ValueError`, which is caught and returns 0. If git somehow returned valid count text with non-zero exit code, it would still parse it. The test for non-zero exit uses empty stdout to trigger ValueError, which is the realistic scenario.
- **Insertion point**: Insert between line 564 and line 566 of `test_agent.py`, maintaining the section-comment-header convention.
- **Existing `_make_proc` helper**: Already defined in the file — reuse it rather than creating a new helper.
- **`SubprocessMockBuilder` fixture**: Could also be used, but `_make_proc` is simpler and matches the existing `TestVerifyResult` pattern more closely.

---
**Summary:** Add 5 direct async unit tests for `AgentRunner._count_commits` covering happy path, multi-digit, empty stdout, non-zero exit code, and FileNotFoundError.
