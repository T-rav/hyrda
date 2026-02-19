# Plan for Issue #25

## Issue Restatement

Issue #25 identifies that `StateTracker.save()` in `state.py` writes directly to the state file using `Path.write_text()`. If the process crashes mid-write (OOM, SIGKILL, power loss), the file can be left truncated or partially written, causing corrupt JSON. On next load, the corrupt file triggers a fallback to defaults, losing all crash-recovery state — which defeats the purpose of having crash-recovery state.

The fix: use atomic writes via write-to-temp-file + `os.replace()`, which is atomic on POSIX systems.

## Files to Modify

### 1. `state.py` — Modify `save()` method (lines 44-48)

**Current code:**
```python
def save(self) -> None:
    """Flush current state to disk."""
    self._data["last_updated"] = datetime.now(UTC).isoformat()
    self._path.parent.mkdir(parents=True, exist_ok=True)
    self._path.write_text(json.dumps(self._data, indent=2))
```

**New code:**
```python
def save(self) -> None:
    """Flush current state to disk atomically."""
    self._data["last_updated"] = datetime.now(UTC).isoformat()
    self._path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(self._data, indent=2)
    # Write to a temp file in the same directory, fsync, then atomically
    # rename.  os.replace() is atomic on POSIX, so the state file is
    # always either the old version or the new version — never partial.
    fd, tmp = tempfile.mkstemp(
        dir=self._path.parent,
        prefix=".state-",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self._path)
    except BaseException:
        # Clean up the temp file if anything goes wrong
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
```

**New imports needed** at the top of `state.py`:
```python
import contextlib
import os
import tempfile
```

### 2. `tests/test_state.py` — Add new test class `TestAtomicSave`

Add a new test section for verifying atomic write behavior:

**Tests to add:**

1. **`test_save_uses_atomic_replace`** — Mock `os.replace` and `tempfile.mkstemp` to verify the atomic write pattern is followed. Confirm `os.replace` is called with the temp path and the final state file path.

2. **`test_save_cleans_up_temp_on_write_failure`** — Mock `os.fdopen` to raise an `OSError` during write. Verify the temp file is cleaned up (no leftover `.state-*.tmp` files in the directory).

3. **`test_save_cleans_up_temp_on_fsync_failure`** — Similar to above but fail on `os.fsync` specifically.

4. **`test_save_does_not_corrupt_existing_file_on_failure`** — Write valid state, then attempt a save that fails (e.g., mock `os.fdopen` to raise). Verify the original state file is unchanged and still contains valid JSON.

5. **`test_no_temp_files_left_after_successful_save`** — After a normal save, verify no `.state-*.tmp` files remain in the directory.

6. **`test_save_temp_file_in_same_directory`** — Verify the temp file is created in the same directory as the state file (required for atomic `os.replace` — rename across filesystems is not atomic).

## Implementation Steps

1. **Add imports** to `state.py`: `import contextlib`, `import os`, `import tempfile`
2. **Rewrite `save()` method** to use the atomic write pattern (tempfile → fsync → os.replace)
3. **Add tests** in `tests/test_state.py` under a new `TestAtomicSave` class
4. **Run `make quality`** to verify linting, type checking, security, and all tests pass

## Testing Strategy

- **Unit tests with mocking**: Mock `tempfile.mkstemp`, `os.fdopen`, `os.fsync`, `os.replace` to verify the atomic write sequence is followed correctly.
- **Integration tests with real files**: Use `tmp_path` to verify end-to-end behavior — no temp files left behind, original file preserved on failure, successful atomic replacement.
- **Existing tests**: All existing `TestLoadSave` and other persistence tests continue to pass unmodified, since the external behavior is identical — only the write mechanism changes.

## Key Considerations

- **Same-directory temp file**: The temp file MUST be in the same directory as the state file. `os.replace()` is only atomic when source and destination are on the same filesystem.
- **fsync before replace**: Without `os.fsync()`, the OS may reorder writes and the temp file content might not be durable before the rename. The `fsync` ensures data is on disk before the atomic rename.
- **BaseException catch**: Use `BaseException` (not `Exception`) in the cleanup to handle `KeyboardInterrupt` and `SystemExit` as well.
- **`contextlib.suppress(OSError)`**: The cleanup `os.unlink` should suppress errors since the temp file might not exist or might already be cleaned up.
- **No behavioral change**: All existing callers and tests should work identically since the external interface (`save()` writes state to `self._path`) is unchanged.
- **Backward compatibility**: The state file format is unchanged — only the write mechanism is different.

---
**Summary:** Make StateTracker.save() use atomic writes via tempfile + os.fsync + os.replace to prevent state file corruption on crash.
