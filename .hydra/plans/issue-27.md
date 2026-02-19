# Plan for Issue #27

## Issue Summary

Add missing edge-case tests for `_fetch_plan_issues` and `_plan_issues` in the `TestPlanPhase` class. Currently, `_fetch_plan_issues` has no direct unit tests (only exercised indirectly), and `_plan_issues` is missing tests for semaphore concurrency, failure-result propagation, and the default-labels fallback for new issues.

## Files to Modify

**`tests/test_orchestrator.py`** — Add a new `TestFetchPlanIssues` class and additional tests in `TestPlanPhase`.

## Implementation Steps

### 1. Add `TestFetchPlanIssues` class (new class, insert before `TestPlanPhase`)

Mirror the pattern from `TestFetchReadyIssues` (lines 247-431), but call `orch._fetch_plan_issues()` instead. Add these tests:

**a. `test_returns_parsed_issues_from_gh_output`**
- Mock `asyncio.create_subprocess_exec` to return valid JSON with a plan-labeled issue
- Call `_fetch_plan_issues()`, assert it returns the parsed issue

**b. `test_returns_empty_list_when_gh_fails`**
- Mock subprocess with `returncode=1`
- Assert returns `[]`

**c. `test_returns_empty_list_on_json_decode_error`**
- Mock subprocess returning invalid JSON (`b"not-json"`)
- Assert returns `[]`

**d. `test_returns_empty_list_when_gh_not_found`**
- Mock `asyncio.create_subprocess_exec` raising `FileNotFoundError`
- Assert returns `[]`

**e. `test_respects_batch_size_limit`**
- Create 9 issues in mock output, with `batch_size=3`
- Assert result length ≤ `config.batch_size`

**f. `test_dry_run_returns_empty_list`**
- Use dry-run config, assert returns `[]` and subprocess not called

**Note on active issue filtering:** `_fetch_plan_issues` does NOT filter `_active_issues` (unlike `_fetch_ready_issues` at line 472). This is an intentional difference — plan issues don't get added to `_active_issues`. We should NOT add a test for filtering that doesn't exist. Instead, file a discovery issue if this is a gap.

### 2. Add missing tests to `TestPlanPhase`

**a. `test_plan_issues_semaphore_limits_concurrency`**
- Mirror the pattern from `TestImplementBatch.test_semaphore_limits_concurrency` (line 485)
- Use a concurrency counter in a fake `_planners.plan` to track peak concurrent calls
- Create 5 issues, with `max_planners=1` (default from ConfigFactory)
- Assert `peak <= config.max_planners`

**b. `test_plan_issues_failure_returns_result_with_error`**
- Plan fails with `success=False, error="Agent crashed"`
- Assert the returned `PlanResult` list contains the failure result
- Assert `result.success is False` and `result.error == "Agent crashed"`

**c. `test_plan_issues_new_issues_use_default_planner_label_when_no_labels`**
- Create a `PlanResult` with `new_issues=[NewIssueSpec(title="X", body="Y")]` (empty labels list)
- Assert `create_issue` is called with `labels=[config.planner_label[0]]` (the fallback at line 423-426)

**d. `test_plan_issues_stop_event_cancels_remaining`**
- Set `_stop_event` after first plan call
- Assert remaining issues are not planned (tasks cancelled)

## Testing Strategy

All tests follow the existing patterns:
- Use `pytest.mark.asyncio`
- Use `AsyncMock` for subprocess and PRManager methods
- Use `make_issue()` helper for issue construction
- Use `PlanResult` directly for plan results
- Use `SubprocessMockBuilder` from conftest where appropriate
- Use `patch("asyncio.create_subprocess_exec", ...)` for `_fetch_plan_issues` tests
- Mock `_fetch_plan_issues` as `AsyncMock(return_value=...)` for `_plan_issues` tests

## Key Considerations

1. **`_fetch_plan_issues` has no `_active_issues` filtering** — Unlike `_fetch_ready_issues`, plan fetching doesn't skip active issues. This may be intentional (planning is fast/read-only) or a gap. The tests should reflect actual behavior, not assumed behavior.

2. **`_fetch_plan_issues` has two code paths** — When `planner_label` is empty, it fetches all open issues excluding downstream labels. When `planner_label` is set, it fetches by that label directly. The `TestFetchPlanIssues` tests should cover both paths (add a test with `planner_label=[]` config).

3. **Semaphore test needs `asyncio.sleep(0)`** — To actually test concurrency, the fake plan function must yield control with `await asyncio.sleep(0)` so tasks can overlap.

4. **RAW_ISSUE_JSON uses `"ready"` label** — For plan-phase tests, create a plan-specific JSON fixture with `"hydra-plan"` label for clarity, or reuse the existing one since `_fetch_plan_issues` doesn't filter by label content (that's done by `gh`).

---
**Summary:** Add ~10 new unit tests: a `TestFetchPlanIssues` class (6 tests mirroring `TestFetchReadyIssues`) and 4 new edge-case tests in `TestPlanPhase` (semaphore concurrency, failure result propagation, default labels fallback, stop-event cancellation).
