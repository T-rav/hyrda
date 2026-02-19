# Plan for Issue #38

## Issue Summary

Add comprehensive tests for `HydraOrchestrator._fetch_reviewable_prs()` (orchestrator.py:474). Currently only two tests exist in `TestFetchReviewablePrsSkipLogic` covering active-issue skipping and previously-reviewed-issue pickup. The method needs tests for: happy-path PR parsing, gh CLI failure, JSON decode error, draft PR filtering, issues with no matching PR, FileNotFoundError, and dry-run mode.

## Files to Modify

- **tests/test_orchestrator.py** — Add 7 new test methods to the `TestFetchReviewablePrsSkipLogic` class (or rename the class to `TestFetchReviewablePrs` to reflect broader scope)

No new files needed.

## Method Under Test — Key Behaviors (orchestrator.py:474-527)

```
_fetch_reviewable_prs() -> tuple[list[PRInfo], list[GitHubIssue]]
```

1. Calls `_fetch_issues_by_labels(review_label, batch_size)` to get issues
2. Filters out issues in `_active_issues` set
3. Returns `([], [])` if no issues remain
4. For each issue, constructs branch `agent/issue-{number}` and calls `_gh_run("gh", "pr", "list", ...)` requesting JSON fields `number,url,isDraft`
5. Parses JSON response → creates `PRInfo` objects
6. Catches `(RuntimeError, json.JSONDecodeError, KeyError)` per-issue — logs warning, skips that issue
7. Filters out draft PRs and PRs with `number <= 0`
8. Returns `(non_draft_prs, issues)`

Note: `_fetch_issues_by_labels` handles dry-run internally (returns `[]`), so `_fetch_reviewable_prs` will return `([], [])` in dry-run mode without needing its own dry-run check.

## Implementation Steps

### Step 1: Rename the test class for broader scope
Rename `TestFetchReviewablePrsSkipLogic` → `TestFetchReviewablePrs` to reflect that it now covers more than skip logic. Update the docstring accordingly.

### Step 2: Add test — happy path parses PR JSON into PRInfo objects

**`test_parses_pr_json_into_pr_info`**

- Set up `_gh_run` fake: first call (issue fetch) returns `RAW_ISSUE_JSON`, second call (PR lookup) returns valid PR JSON `[{"number": 200, "url": "https://...", "isDraft": false}]`
- Assert returns `([PRInfo(number=200, issue_number=42, branch="agent/issue-42", url="...", draft=False)], [issue])`
- Assert PRInfo fields match expected values

Pattern: Follow `test_picks_up_previously_reviewed_issues` which already uses `orch._gh_run = fake_gh_run` pattern.

### Step 3: Add test — gh CLI failure returns empty PRs but preserves issues list

**`test_gh_cli_failure_skips_pr_for_that_issue`**

- Set up `_gh_run` fake: issue fetch returns `RAW_ISSUE_JSON`, PR lookup raises `RuntimeError("Command ... failed")`
- Assert returns `([], [issue_42])` — empty PR list but issues list still populated
- Verifies the `except (RuntimeError, ...)` handler at line 522

### Step 4: Add test — JSON decode error skips that PR

**`test_json_decode_error_skips_pr_for_that_issue`**

- Set up `_gh_run` fake: issue fetch returns `RAW_ISSUE_JSON`, PR lookup returns `"not-valid-json"`
- Assert returns `([], [issue_42])` — empty PR list, issues preserved

### Step 5: Add test — draft PRs are excluded from returned list

**`test_draft_prs_excluded_from_results`**

- Set up `_gh_run` fake: issue fetch returns `RAW_ISSUE_JSON`, PR lookup returns `[{"number": 200, "url": "...", "isDraft": true}]`
- Assert returns `([], [issue_42])` — draft PR filtered out at line 525
- This validates the `not p.draft` filter

### Step 6: Add test — issue with no matching PR (empty JSON array)

**`test_no_matching_pr_returns_empty_pr_list`**

- Set up `_gh_run` fake: issue fetch returns `RAW_ISSUE_JSON`, PR lookup returns `"[]"` (empty JSON array)
- Assert returns `([], [issue_42])` — no PRInfo created but issue still in list
- This validates the `if prs_json:` check at line 511

### Step 7: Add test — FileNotFoundError when gh is not installed

**`test_file_not_found_error_when_gh_missing`**

- Note: `FileNotFoundError` is NOT in the catch clause of `_fetch_reviewable_prs` (line 522 catches `RuntimeError, json.JSONDecodeError, KeyError`). It IS caught in `_fetch_issues_by_labels` (line 264).
- So if `_fetch_issues_by_labels` catches `FileNotFoundError` → returns empty list → `_fetch_reviewable_prs` returns `([], [])`  early at the "if not issues" check.
- If `_gh_run` raises `FileNotFoundError` during the PR lookup loop, it will propagate uncaught!
- **Test approach**: Set up `_gh_run` fake where issue fetch works but PR lookup raises `FileNotFoundError`. Verify the exception propagates (this documents current behavior — the method does NOT handle `FileNotFoundError` in its PR lookup try/except).
- **Alternative**: If we want to also test the case where `_fetch_issues_by_labels` fails (gh not installed), mock `create_subprocess_exec` to raise `FileNotFoundError` → the method returns `([], [])`.

Actually, re-reading the code: `_fetch_issues_by_labels` catches `FileNotFoundError` internally (line 264), so the issue-fetch step will just return `[]` → `_fetch_reviewable_prs` returns `([], [])` early. For the PR lookup step, `_gh_run` calls `create_subprocess_exec` which could raise `FileNotFoundError`, and this is NOT caught by the `except` on line 522. This is a **discovered bug** — `FileNotFoundError` should be added to the except clause on line 522.

**Test**: Mock `_gh_run` to raise `FileNotFoundError` during PR lookup → assert it propagates as an unhandled exception (documenting the bug). Then a separate fix issue can address it.

**Revised approach**: Since the issue specifically lists "FileNotFoundError when gh is not installed" as a test case, write a test using `patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError(...))` which will affect the `_fetch_issues_by_labels` call → returns `[]` → method returns `([], [])`. This tests the end-to-end behavior when gh isn't installed.

### Step 8: Add test — dry-run mode returns empty

**`test_dry_run_returns_empty_tuple`**

- Create `HydraConfig` with `dry_run=True`
- Call `_fetch_reviewable_prs()`
- Assert returns `([], [])`
- Assert `create_subprocess_exec` was not called (dry-run short-circuits in `_fetch_issues_by_labels`)

## Testing Strategy

All tests follow the existing patterns in the file:
- Use `@pytest.mark.asyncio` decorator
- Accept `config: HydraConfig` fixture from conftest
- Create `HydraOrchestrator(config)` instance
- Mock `_gh_run` via direct assignment (`orch._gh_run = fake`) following the pattern in `test_picks_up_previously_reviewed_issues`
- For dry-run and FileNotFoundError tests, use `patch("asyncio.create_subprocess_exec", ...)`
- Use existing helpers: `RAW_ISSUE_JSON`, `make_issue()`, `make_pr_info()`
- Assert both elements of the returned tuple `(prs, issues)`

### What to Verify per Test

| Test | prs | issues | Key assertion |
|------|-----|--------|---------------|
| happy path | 1 PRInfo with correct fields | 1 issue | PRInfo fields match JSON |
| gh CLI failure | [] | [issue] | RuntimeError caught, PR skipped |
| JSON decode error | [] | [issue] | JSONDecodeError caught, PR skipped |
| draft PR excluded | [] | [issue] | draft=True filtered at line 525 |
| no matching PR | [] | [issue] | empty JSON array → no PRInfo |
| gh not installed | [] | [] | FileNotFoundError in _fetch_issues_by_labels → early return |
| dry-run | [] | [] | No subprocess calls made |

## Key Considerations

1. **Per-issue error isolation**: The try/except in the PR lookup loop (line 522) catches errors per-issue, so one failing issue shouldn't affect others. The gh CLI failure and JSON decode error tests verify this isolation by checking that `issues` is still populated even though `prs` is empty.

2. **Draft filtering**: Line 525 filters `not p.draft and p.number > 0`. The draft test covers `draft=True` being excluded. The `number > 0` condition is an edge case that could be tested but is low priority.

3. **Discovered bug — FileNotFoundError not caught in PR lookup**: The except clause on line 522 does not include `FileNotFoundError`. If `create_subprocess_exec` raises `FileNotFoundError` during a PR lookup (after issues were successfully fetched), it will propagate unhandled. This should be filed as a separate issue.

4. **`_gh_run` mock pattern**: The existing test `test_picks_up_previously_reviewed_issues` uses `orch._gh_run = fake_gh_run` which is the cleanest approach since `_fetch_reviewable_prs` calls both `_fetch_issues_by_labels` (which calls `_gh_run` internally) and `_gh_run` directly for PR lookups. The fake function differentiates calls by checking if `"issue"` is in args.

---
**Summary:** Add 7 tests to TestFetchReviewablePrs covering happy path PR parsing, gh CLI failure, JSON decode error, draft filtering, no matching PR, FileNotFoundError, and dry-run mode.
