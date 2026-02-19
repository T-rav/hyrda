# Plan for Issue #21

## Goal

Extract the duplicated async subprocess helper (`_run` / `_gh_run`) from `worktree.py`, `pr_manager.py`, and `orchestrator.py` into a shared utility function. Replace the inline subprocess calls in `dashboard.py` with the shared function as well.

## New File

### `subprocess_util.py`

Create a new module at the project root containing a single async helper function:

```python
async def run_subprocess(
    *cmd: str,
    cwd: Path | None = None,
    gh_token: str = "",
) -> str:
```

**Behavior** (identical to existing `_run` methods):
1. Copy `os.environ`, remove `CLAUDECODE` key
2. If `gh_token` is non-empty, set `GH_TOKEN` in env
3. Call `asyncio.create_subprocess_exec` with `stdout=PIPE`, `stderr=PIPE`, optional `cwd`
4. Await `proc.communicate()`
5. On non-zero returncode, raise `RuntimeError` with the same message format: `f"Command {cmd!r} failed (rc={proc.returncode}): {stderr.decode().strip()}"`
6. Return `stdout.decode().strip()`

## Files to Modify

### 1. `worktree.py`
- **Delete** the `_run` method (lines 244-268)
- **Import** `run_subprocess` from `subprocess_util`
- **Replace** all `await self._run(...)` calls (≈12 call sites) with `await run_subprocess(..., gh_token=self._config.gh_token)`
- The `cwd=` keyword is already used at every call site, so the signature change is compatible

### 2. `pr_manager.py`
- **Delete** the `_run` method (lines 649-668)
- **Import** `run_subprocess` from `subprocess_util`
- **Replace** all `await self._run(...)` calls (≈13 call sites) with `await run_subprocess(..., gh_token=self._config.gh_token)`
- Same `cwd=` pattern as worktree

### 3. `orchestrator.py`
- **Delete** the `_gh_run` method (lines 535-553)
- **Import** `run_subprocess` from `subprocess_util`
- **Replace** `await self._gh_run(...)` calls (2 call sites at lines 267 and 501) with `await run_subprocess(..., gh_token=self._config.gh_token)`
- These calls don't pass `cwd`, which is fine since `cwd` defaults to `None`

### 4. `dashboard.py`
- **Import** `run_subprocess` from `subprocess_util`
- **Replace** the 3 inline `create_subprocess_exec` blocks (lines ~120, ~181, ~211) with calls to `run_subprocess`
- Dashboard currently swallows errors (continues on non-zero exit). Wrap calls in `try/except RuntimeError` to preserve that behavior, parsing the stdout from the function's return value
- Note: dashboard does NOT set `GH_TOKEN` currently, but it should — this is a minor improvement. If the dashboard has access to `self._config.gh_token`, pass it; otherwise just omit it (empty string default)

## Implementation Steps

1. **Create `subprocess_util.py`** with the `run_subprocess` function
2. **Create `tests/test_subprocess_util.py`** with unit tests (see testing strategy below)
3. **Update `worktree.py`** — remove `_run`, import and use `run_subprocess`
4. **Update `pr_manager.py`** — remove `_run`, import and use `run_subprocess`
5. **Update `orchestrator.py`** — remove `_gh_run`, import and use `run_subprocess`
6. **Update `dashboard.py`** — replace inline subprocess calls with `run_subprocess` wrapped in try/except
7. **Run `make quality`** to verify lint, types, security, and all tests pass

## Testing Strategy

### New tests: `tests/test_subprocess_util.py`

Test the shared `run_subprocess` function directly:

1. **`test_returns_stdout_on_success`** — Mock `create_subprocess_exec`, verify stdout returned stripped
2. **`test_raises_runtime_error_on_nonzero_exit`** — Mock a failed process, verify `RuntimeError` is raised with correct message including the command and stderr
3. **`test_strips_claudecode_from_env`** — Verify the env dict passed to `create_subprocess_exec` does not contain `CLAUDECODE`
4. **`test_sets_gh_token_when_provided`** — Verify `GH_TOKEN` is set in env when `gh_token` param is non-empty
5. **`test_no_gh_token_when_empty`** — Verify `GH_TOKEN` is not injected when `gh_token=""` (or uses whatever was already in the env)
6. **`test_passes_cwd_when_provided`** — Verify `cwd` is passed to `create_subprocess_exec`
7. **`test_no_cwd_when_none`** — Verify `cwd` is not passed (or passed as None) when omitted

### Existing tests

The existing tests in `test_worktree.py`, `test_pr_manager.py`, `test_orchestrator.py`, and `test_dashboard.py` all mock `asyncio.create_subprocess_exec` at the module level. Since we're replacing the private `_run` methods with a call to the shared function (which still calls `asyncio.create_subprocess_exec` internally), these tests should continue to work **if** the mock target is updated:

- Tests currently patching `asyncio.create_subprocess_exec` will still work since `subprocess_util.run_subprocess` calls the same function
- The patch target in each test file may need to change from `"asyncio.create_subprocess_exec"` to `"subprocess_util.run_subprocess"` for tests that were testing through the `_run` wrapper — but since most tests mock at the `asyncio` level, they should continue to work as-is. Verify by running `make test` after each file change.

## Key Considerations

1. **Backward compatibility**: The public API of all classes remains unchanged. Only private methods are being removed and replaced with a module-level function.

2. **Error message format**: Keep the exact same `RuntimeError` message format so any existing error handling/logging that parses these messages continues to work.

3. **Dashboard error handling**: The dashboard currently silently ignores subprocess failures. When switching to `run_subprocess`, wrap each call in `try/except RuntimeError` to preserve this behavior.

4. **No `cwd` for orchestrator**: The orchestrator's `_gh_run` doesn't pass `cwd`. The shared function should accept `cwd: Path | None = None` and only pass it to `create_subprocess_exec` when not None. (Actually, passing `cwd=None` to `create_subprocess_exec` is valid and means "use current directory", so this is fine either way.)

5. **GH_TOKEN in dashboard**: Dashboard inline calls currently don't set `GH_TOKEN`. The dashboard has `self._config` available, so we should pass `gh_token=self._config.gh_token` for consistency. This is a minor correctness improvement.

6. **Import path for mock targets**: Since the new function lives in `subprocess_util`, tests that need to mock the subprocess layer can either mock `asyncio.create_subprocess_exec` globally (as they do now) or mock `subprocess_util.run_subprocess` at a higher level. The existing approach should continue working.

---
**Summary:** Extract duplicated `_run`/`_gh_run` async subprocess helpers from worktree.py, pr_manager.py, orchestrator.py, and dashboard.py into a shared `run_subprocess` function in a new `subprocess_util.py` module.
