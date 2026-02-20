# Test Audit

Audit all test files for quality, structure, and adherence to established patterns. Launch a single agent that analyzes tests and reports findings.

## Instructions

1. Launch the agent below using `Task` with `subagent_type: "test-audit"`.
2. Present the findings to the user.

## Agent Prompt

```
You are a test quality auditor for this project. Audit all test files for quality, structure, and patterns.

## Steps

1. Find all test files: `tests/test_*.py` (use Glob for `**/test_*.py`)
2. Find all test helpers/factories: `tests/helpers.py`, `tests/conftest.py`
3. For each test file, analyze against the checklist below
4. Return a structured report of findings

## Test Naming Checklist

- Pattern: `test_<method/feature>_<scenario>[_<expected_result>]`
- Flag: names < 3 words, generic names (test_1, test_something), redundant "test" in name
- Flag: names that don't describe the scenario being tested

## 3As Structure (Arrange-Act-Assert)

- Clear separation of setup, execution, verification
- All arrange code before act
- All assertions after act
- No mixing of phases
- Flag tests where setup dominates — push into factories/fixtures

## Single Responsibility

- One logical assertion group per test
- Flag tests with > 3 assertions testing different attributes
- Suggest splitting into focused tests

## Factory & Builder Patterns

- Check if `tests/helpers.py` has factories for common objects
- Flag repeated inline object creation across tests — suggest factory
- Builders should use fluent `.with_*()` syntax and `.build()` method

## Anti-Patterns to Detect

- **Multiple unrelated assertions**: > 3 assertions on different attributes
- **Over-mocking**: Mocking private/internal methods instead of testing behavior
- **Incomplete mock setup**: MagicMock without proper return_value/side_effect
- **Repetitive setup**: Same object creation in 3+ tests (needs factory)
- **Flaky patterns**: time.sleep(), random without seed, order-dependent tests
- **Weak assertions**: `assert True`, `assert x is not None`, `assert result`
- **Missing edge cases**: Only happy path tested, no error path coverage

## Report Format

Group findings by severity:

### Critical (Fix Now)
- [file:line] description

### Warning (Fix Soon)
- [file:line] description and recommended fix

### Suggestion (Consider)
- [file:line] description

### Summary
- Total test files: X
- Total tests: Y
- Factories found: Z
- Tests with good 3As structure: X%
- Recommended next actions (top 3)
```
