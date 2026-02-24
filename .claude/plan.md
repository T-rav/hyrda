PLAN_START

## Issue Summary

Issue #1071 requests extracting repeated mock setup into shared fixtures/helpers in four test files: `test_implement_phase.py`, `test_plan_phase.py`, `test_review_phase_core.py`, and `test_dashboard.py`. Each file has significant repetition of mock configuration that obscures what each test uniquely verifies. The goal is to reduce per-test mock setup from 6-10 lines to 1-2 lines by centralizing common patterns.

## Files to Modify

### 1. `tests/test_review_phase_core.py` (2047 lines)

The most repetitive file. 45+ tests repeat a "standard review mocks" block of 6 lines:
```python
phase._reviewers.review = AsyncMock(return_value=ReviewResultFactory.create())
phase._prs.get_pr_diff = AsyncMock(return_value="diff text")
phase._prs.push_branch = AsyncMock(return_value=True)
phase._prs.merge_pr = AsyncMock(return_value=True)
phase._prs.remove_label = AsyncMock()
phase._prs.add_labels = AsyncMock()
```
Plus 40+ tests repeat the worktree directory creation:
```python
wt = config.worktree_base / "issue-42"
wt.mkdir(parents=True, exist_ok=True)
```

**Changes:**
- Add a `_apply_standard_review_mocks(phase, *, review=None, merge_result=True, diff="diff text")` helper function that applies the 6 standard mock lines to a phase, with optional overrides
- Add a `_ensure_worktree(config, issue_number=42)` helper that creates the worktree directory
- Update 30+ tests in `TestReviewPRs`, `TestReviewUpdateStartEvent`, `TestReviewOneInner`, `TestSkipGuardNoNewCommits`, and other classes to use these helpers instead of repeating the 6-8 line mock setup blocks
- Tests that need non-standard mocks (e.g., merge conflict scenarios, exception tests) keep their explicit mock setup

### 2. `tests/test_dashboard.py` (2532 lines)

74 tests repeat the 3-line dashboard+app+client setup:
```python
dashboard = HydraFlowDashboard(config, event_bus, state)
app = dashboard.create_app()
client = TestClient(app)
```

**Changes:**
- Add a `dashboard_client` pytest fixture at module level that yields a `TestClient` instance
- Add a `_make_dashboard_client(config, event_bus, state, *, orchestrator=None)` helper for tests that need a custom orchestrator
- Update 50+ tests in `TestIndexRoute`, `TestStateRoute`, `TestStatsRoute`, `TestEventsRoute`, `TestPRsRoute`, `TestHumanInputGetRoute`, `TestHumanInputPostRoute`, `TestControlStopEndpoint`, `TestControlStatusEndpoint`, `TestWebSocketEndpoint`, `TestHITLRoute`, `TestStaticDashboardJS`, `TestFallbackTemplateExternalJS`, `TestSPACatchAll` to use the fixture
- Tests in `TestCreateApp` and `TestInit` that test dashboard creation itself, and tests needing custom orchestrators, keep explicit setup

### 3. `tests/test_plan_phase.py` (804 lines)

25+ tests repeat the pattern of:
```python
planners.plan = AsyncMock(return_value=plan_result)
store.get_plannable = lambda _max_count: [issue]
```

**Changes:**
- Add a `_setup_plan(planners, store, *, issues=None, plan_result=None)` helper function that sets `planners.plan` and `store.get_plannable` with sensible defaults (single issue #42, successful PlanResult)
- Update 15-20 tests in `TestPlanPhase`, `TestPlanPhaseAlreadySatisfied`, and `TestPlanPhaseTranscriptSummary` to use the helper
- Tests with custom plan functions (e.g., concurrency test with `fake_plan`, active-during-processing check) keep their explicit setup

### 4. `tests/test_implement_phase.py` (1684 lines)

The `_make_phase()` helper already handles most mock setup well (lines 37-111). After thorough review, the mocks `swap_pipeline_labels`, `post_comment`, and `add_pr_labels` are already configured as defaults on lines 97-99. The implement phase tests are the least repetitive of the four files.

**Changes:**
- No significant changes needed — `_make_phase()` already provides good defaults

### 5. `tests/helpers.py`

**Changes:**
- Add `apply_standard_review_mocks(phase, *, review=None, merge_result=True, diff="diff text", push_result=True)` near `make_review_phase()`
- Add `ensure_worktree(config, issue_number=42)` near `make_review_phase()`
- These sit alongside the existing `make_review_phase()` function since they serve the same test file

## New Files

None

## File Delta

```
MODIFIED: tests/test_review_phase_core.py
MODIFIED: tests/test_dashboard.py
MODIFIED: tests/test_plan_phase.py
MODIFIED: tests/helpers.py
```

## Implementation Steps

1. **Add shared review helpers to `tests/helpers.py`** — Create `apply_standard_review_mocks(phase, *, review=None, merge_result=True, diff="diff text", push_result=True)` that applies the 6 standard review mock lines. Create `ensure_worktree(config, issue_number=42)` that creates and returns the worktree path. These sit next to the existing `make_review_phase()` function.

2. **Refactor `tests/test_review_phase_core.py`** — Import the two new helpers. For each test class that repeats the standard review mock block, replace the 6-8 lines with a call to `apply_standard_review_mocks()`. Replace worktree mkdir patterns with `ensure_worktree()`. Preserve tests that intentionally use non-default mock configurations (merge failures, exception injection, self-review errors, etc.) — these should keep their explicit overrides, possibly calling the helper first and then overriding specific mocks. Target: ~30 tests simplified.

3. **Add `_setup_plan()` helper to `tests/test_plan_phase.py`** — Create a module-level helper `_setup_plan(planners, store, *, issues=None, plan_result=None)` that sets `planners.plan = AsyncMock(return_value=plan_result)` and `store.get_plannable = lambda _max_count: issues`. Default to a single issue #42 and a successful `PlanResult`. Update 15-20 tests in `TestPlanPhase`, `TestPlanPhaseAlreadySatisfied`, and `TestPlanPhaseTranscriptSummary` to use it.

4. **Add `dashboard_client` fixture to `tests/test_dashboard.py`** — Create a module-level `@pytest.fixture` that builds `HydraFlowDashboard(config, event_bus, state)`, calls `create_app()`, and yields `TestClient(app)`. Create a helper `_make_dashboard_client(config, event_bus, state, *, orchestrator=None)` for tests needing custom parameters. Update 50+ tests to use either the fixture or the helper. Keep explicit setup in `TestCreateApp` and `TestInit` classes since those test the construction itself.

5. **Run targeted tests** — Run `make test-fast -- tests/test_review_phase_core.py tests/test_plan_phase.py tests/test_dashboard.py` to verify all modified files pass.

6. **Run full quality check** — Run `make quality` to verify lint, typecheck, security, and full test suite pass.

## Testing Strategy

This is a pure refactoring of test code — no production code changes, no new tests needed. The strategy is verification-based:

- **Per-file verification**: After each file is modified, run `pytest tests/test_<module>.py -x --tb=short` to confirm all tests pass
- **Test count preservation**: Before starting, capture test counts with `pytest --collect-only tests/test_review_phase_core.py tests/test_plan_phase.py tests/test_dashboard.py | grep "tests collected"`. After refactoring, verify counts are unchanged
- **Full suite**: Run `make test` at the end to ensure no cross-file regressions
- **Lint/type check**: `make quality-lite` to verify all static analysis passes
- **Specific test files being verified**: `tests/test_review_phase_core.py`, `tests/test_plan_phase.py`, `tests/test_dashboard.py`, `tests/helpers.py`
- **Behavioral equivalence**: No test assertions change — only setup code is extracted into helpers

## Acceptance Criteria

1. `tests/test_review_phase_core.py`: 30+ tests simplified from 6-8 line mock setup to 1-2 line helper calls
2. `tests/test_dashboard.py`: 50+ tests simplified from 3-line dashboard/app/client setup to a single fixture parameter
3. `tests/test_plan_phase.py`: 15-20 tests simplified from 2-line planner+store setup to a single helper call
4. All existing tests pass — `make test` succeeds
5. No behavioral changes — test assertions are identical before and after
6. Test count for each file is unchanged
7. Lint, typecheck, and security pass — `make quality-lite` succeeds
8. New helpers have clear docstrings explaining defaults and override parameters

## Key Considerations

### Helper design must support overrides without losing clarity
The `apply_standard_review_mocks()` helper must accept keyword overrides (e.g., `merge_result=False`) so tests that need non-default behavior can still use the helper for their "standard" mocks and override only what they test. This keeps the helper broadly useful without forcing tests that need one non-default mock back to the full 6-line manual setup.

### Dashboard fixture interaction with `TestClient` lifecycle
The `TestClient` in FastAPI manages ASGI lifecycle events. A module-level or class-level fixture using `TestClient` must ensure proper cleanup. Using `@pytest.fixture` (function-scoped by default) is safest — each test gets a fresh client. A class-scoped fixture could cause state leaks between tests in the same class. Stick with function scope.

### Some tests intentionally vary mocks for negative testing
Tests like `test_review_merge_conflict_escalates_to_hitl` and `test_review_does_not_merge_rejected_pr` set up mocks that are deliberately different from the standard pattern. These tests should NOT use the shared helper for the mocks they're testing, as that would hide the behavior being verified. Either skip the helper entirely for these tests, or call the helper first then explicitly override the specific mock(s) being tested.

### Plan phase helper should use PlanResultFactory
The `_setup_plan()` helper should leverage the existing `PlanResultFactory.create()` for its default plan result rather than constructing `PlanResult` directly. This keeps test data consistent with the factory patterns already established in `conftest.py`.

### `test_implement_phase.py` is already well-factored
After thorough review, the implement phase test file already has an effective `_make_phase()` helper that centralizes mock setup. The issue description mentions it "takes 6 optional parameters but callers still have to manually set up" certain mocks, but inspection shows those mocks (`swap_pipeline_labels`, `post_comment`, `add_pr_labels`) are already set as defaults on lines 97-99. No changes needed for this file.

### Pre-Mortem — Top 3 Risks

1. **Over-extracting makes tests harder to understand** — If the helper hides too much setup, readers can't tell what mocks are active in a given test. **Mitigation**: Keep helpers focused on the "standard happy path" setup. Any mock that a test specifically asserts on should be set explicitly in that test's body, even if it matches the default.

2. **Dashboard fixture doesn't work with custom orchestrator tests** — About 15 dashboard tests pass a custom `orchestrator` to `HydraFlowDashboard`. A simple fixture can't serve these tests. **Mitigation**: Provide both a fixture (for the ~50 tests that use default config) and a helper function `_make_dashboard_client(...)` (for the ~15 tests needing custom orchestrators).

3. **Accidentally breaking mock assertion tests** — Some tests assert that certain mocks were NOT called (e.g., `assert_not_awaited()`). If the helper pre-configures a mock that a test then checks wasn't called, and the test doesn't realize the mock was set up by the helper, the assertion may become vacuously true or false. **Mitigation**: The `apply_standard_review_mocks()` helper should only set mocks that are part of the standard happy-path flow. Don't pre-set mocks for `post_pr_comment`, `submit_review`, `swap_pipeline_labels` since those are checked in various assertion patterns.

PLAN_END

SUMMARY: Extract repeated mock setup into shared helpers in test_review_phase_core.py (45+ tests), test_dashboard.py (74 tests), and test_plan_phase.py (25+ tests), centralizing 6-10 line setup blocks into 1-2 line helper/fixture calls.
