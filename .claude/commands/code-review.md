# On-Demand Code Review

Run all 4 code review checks (test quality, clean code/SRP, security, migrations) on changed files. This replaces the old Stop hook agents — invoke manually with `/code-review` when you want a review before committing.

## Instructions

1. Run `git diff --cached --name-only` and `git diff --name-only` to find all changed files.
2. If no source files were changed, report "No source files changed — nothing to review." and stop.
3. Launch ALL 4 review agents **in parallel** using `Task` with `run_in_background: true` and `subagent_type: "general-purpose"`.
4. Wait for all agents to complete.
5. Summarize the findings from each agent.

## Agent 1: Test Quality Review

```
You are a test quality reviewer. Review changed test files for completeness and quality.

Steps:
1. Run `git diff --cached --name-only` and `git diff --name-only` to find changed files
2. If no Python, TypeScript/JavaScript, or Dockerfile files were changed, return {"ok": true}
3. For each changed source file, find corresponding test files
4. Read the test files and evaluate them against these criteria:

**Test Completeness (all languages):**
- Are there tests for the happy path (normal operation)?
- Are there tests for edge cases (empty inputs, None/null/undefined values, boundary conditions, large inputs)?
- Are there tests for exception/error handling (invalid inputs, network failures, missing data)?
- Do tests cover all public functions/methods/components in the changed source files?

**Python Test Quality:**
- Do tests use proper assertions (not just `assert True`)?
- Are error messages tested (checking exception types and messages)?
- Are tests isolated (using mocks/fixtures appropriately)?

**React/TypeScript Test Quality:**
- Are components tested with Testing Library (`@testing-library/react`)?
- Do tests use `screen` queries and prefer accessible queries (`getByRole`, `getByLabelText`, `getByText`) over `getByTestId`?
- Are user interactions tested with `userEvent` instead of `fireEvent`?
- Are async operations tested with `waitFor`?
- Do tests verify rendered output and behavior, not internal state?
- Are error states and loading states tested?
- Don't flag librechat-custom files — that's an upstream fork
- Don't flag generated/dist files

**Dockerfile Test Coverage:**
- If a Dockerfile was changed, check that any new COPY, RUN, or ENTRYPOINT logic has corresponding integration or smoke tests
- Don't require test coverage for CSS or HTML template changes — these are presentation-only

If tests are missing edge cases or exception handling:
1. Before creating an issue, check for duplicates by running:
   gh issue list --repo 8thlight/insightmesh --label claude-find --state open --search "<key terms from title>"
   If a matching open issue already exists for the same file and finding, skip it.
2. Create a GitHub issue for each distinct NEW finding by running:
   gh issue create --repo 8thlight/insightmesh --assignee T-rav --label claude-find --title "<concise title>" --body "<details with file paths, line numbers, and what's missing>"
3. Return {"ok": false, "reason": "Tests for [file] are missing: [specific list]. GitHub issue(s) created."}

If tests are adequate, return {"ok": true}

Be practical - not every function needs exhaustive edge case tests. Focus on:
- Functions/components that handle user input or external data
- Functions with conditional logic or error handling paths
- Functions that could receive None/null/undefined, empty, or malformed data
```

## Agent 2: Clean Code, SRP & Test Patterns Review

```
You are a code quality reviewer for a project with Python microservices, React/TypeScript UIs, Docker containers, and server-rendered HTML templates. Review changed files for language best practices, clean code, and test patterns.

Steps:
1. Run `git diff --cached --name-only` and `git diff --name-only` to find changed files
2. If no Python, TypeScript/JavaScript, Dockerfile, CSS, HTML, Markdown, or YAML (.yml/.yaml) files were changed, return {"ok": true}
3. Read each changed file and evaluate against the criteria below (use the Python section for .py files, the React/TypeScript section for .ts/.tsx/.js/.jsx files)

---

## Consistency with Existing Codebase Patterns (ALL languages)

- Before flagging, read 2-3 neighboring files in the same service/package to understand established patterns
- Does the new code follow the same patterns used elsewhere? (e.g., error handling style, class/component structure, dependency injection, config access, state management)
- Are imports organized the same way as other files in the service?
- Does it use the same abstractions/base classes/hooks that sibling modules use?
- Flag deviations from established patterns — consistency matters more than theoretical best practice

---

## Python Clean Code Review

For each changed Python SOURCE file (not tests), check:

**Python Best Practices:**
- Use type hints on all function signatures (parameters and return types)
- Use `dataclass` or `Pydantic BaseModel` for data containers instead of raw dicts
- Prefer `pathlib.Path` over `os.path` for file operations
- Use context managers (`with`) for resource management (files, connections, locks)
- Use `Enum` for fixed sets of values instead of string constants
- Use list/dict/set comprehensions where they improve readability over loops
- Prefer `logging` module over `print()` for output
- Use `__all__` in public modules to define the public API
- Async functions should use `async/await` consistently — don't mix sync and async I/O

**Naming:**
- Are function/method names verbs that describe what they do? (e.g., `process_message`, not `handler2`)
- Are variable names descriptive? No single-letter names except loop counters
- Are class names nouns that describe what they are?

**Function length & complexity:**
- Functions should do ONE thing. Flag any function longer than ~25 lines
- Flag deeply nested code (3+ levels of indentation) — suggest extracting helper functions
- Flag functions with more than 3-4 parameters — suggest a config object or builder

**Single Responsibility Principle:**
- Does each class/module have ONE clear reason to change?
- Flag classes that mix concerns (e.g., a service class that also does formatting, or a handler that also does database queries)
- Flag functions that do multiple unrelated things (e.g., validate + transform + persist in one function)
- If a file has grown beyond ~200 lines, consider whether it should be split

---

## React/TypeScript Clean Code Review

For each changed .ts/.tsx/.js/.jsx SOURCE file (not tests), check:

**TypeScript Best Practices:**
- Use explicit TypeScript types/interfaces for props, state, and function signatures — no `any`
- Use `interface` for object shapes and component props, `type` for unions/intersections
- Use `const` by default, `let` only when reassignment is needed, never `var`
- Use optional chaining (`?.`) and nullish coalescing (`??`) instead of manual null checks
- Use template literals over string concatenation
- Prefer `unknown` over `any` when the type is truly unknown
- Export types/interfaces that are used across files

**React Best Practices:**
- Functional components only (no class components)
- Use proper hooks: `useMemo`/`useCallback` for expensive computations and stable references passed as props
- Custom hooks for reusable stateful logic — extract when logic is shared across 2+ components
- Props destructuring in function signature
- Use React.FC or explicit return types for components
- Keep components focused — if a component renders multiple distinct sections, extract child components
- Event handlers named `handleX` (e.g., `handleClick`, `handleSubmit`)
- Avoid inline object/array literals in JSX props (causes unnecessary re-renders)

**Component Structure:**
- Components should do ONE thing. Flag components longer than ~100 lines of JSX
- Separate data fetching from presentation (container/presenter or custom hooks)
- Flag components mixing API calls with rendering logic — extract to custom hooks
- Co-locate related files (component, tests, styles, types) in the same directory

---

## Python Test Pattern Review

For each changed Python TEST file, check:

**Test Data Builders (fluent syntax):**
This project uses builder pattern with fluent `.with_*()` syntax for test data. Example:
```python
agent = (
    MockAgentBuilder()
    .with_name("research")
    .with_display_name("Research Agent")
    .with_aliases(["researcher"])
    .as_system_agent()
    .build()
)
```
- Flag tests that construct complex objects inline with many raw keyword arguments — suggest a builder instead
- Builders should live in conftest.py or a shared test utilities module
- Builders MUST return `self` from `.with_*()` methods for chaining
- Builders MUST have a `.build()` method that returns the final object

**Test Factory Methods:**
This project uses factory classes with static methods for common fixtures. Example:
```python
class AgentFixtureFactory:
    @staticmethod
    def help_agent() -> MagicMock:
        return MockAgentBuilder().with_name("help").build()
```
- Flag repeated test setup code that creates similar objects — suggest a factory method
- Factories should group related creation methods in a class
- Factories belong in conftest.py for shared access

**Test Structure:**
- Tests should follow Arrange-Act-Assert (3As) pattern with clear separation
- Flag tests with more than one logical assertion group (test should test ONE behavior)
- Flag tests where setup/arrangement dominates — push setup into builders/factories

## React Test Pattern Review

For each changed React/TS TEST file (.spec.tsx, .test.tsx, .spec.ts, .test.ts), check:

**Testing Library Best Practices:**
- Use `screen` queries (not destructured from `render`)
- Prefer `getByRole`, `getByLabelText`, `getByText` over `getByTestId` — test like a user
- Use `userEvent` over `fireEvent` for user interactions
- Use `waitFor` for async assertions, not manual timeouts
- Test behavior and output, not implementation details (don't test state directly)

**Test Structure:**
- Same Arrange-Act-Assert pattern as Python tests
- Flag tests that test implementation details (checking internal state, spying on private methods)
- Flag missing cleanup or act() warnings

---

## Dockerfile, CSS, HTML, Markdown, CI/CD

- Dockerfile: Pin base image versions, multi-stage builds, non-root user, HEALTHCHECK, no secrets
- CSS: No `!important`, consistent naming, no hardcoded colors, relative units
- HTML: Valid structure, accessible, escaped user data
- Markdown: Accurate commands/paths, language tags on code blocks, consistent formatting
- CI/CD YAML: Matrix strategies, pinned action versions, timeouts, coverage thresholds

---

## Response Format

If issues are found:
1. Before creating an issue, check for duplicates by running:
   gh issue list --repo 8thlight/insightmesh --label claude-find --state open --search "<key terms from title>"
   If a matching open issue already exists for the same file and finding, skip it.
2. Create a GitHub issue for each distinct NEW finding by running:
   gh issue create --repo 8thlight/insightmesh --assignee T-rav --label claude-find --title "<concise title>" --body "<details with file paths, line numbers, and what needs to change>"
3. Return {"ok": false, "reason": "<concise list of issues with file paths and line numbers>. GitHub issue(s) created."}

If code is clean, return {"ok": true}

Be pragmatic:
- Small utility functions don't need builders
- Simple dataclass construction doesn't need a factory
- Focus on complex objects with 4+ fields or objects reused across 3+ tests
- Don't flag code that wasn't changed in this session
- Don't flag librechat-custom files — that's an upstream fork
- Don't flag generated/dist files
```

## Agent 3: Security Review

```
You are a security reviewer. Review changed files for common security vulnerabilities.

Steps:
1. Run `git diff --cached --name-only` and `git diff --name-only` to find changed files
2. If no source files (.py, .ts, .tsx, .js, .jsx, .html, .yml, .yaml, Dockerfile) were changed, return {"ok": true}
3. Read each changed file and check for:

**Python Security:**
- Hardcoded secrets, API keys, tokens, passwords
- SQL injection (string formatting in queries)
- Command injection (`os.system()`, `subprocess` with `shell=True`)
- Unsafe deserialization (`pickle.loads()`, `yaml.load()`, `eval()`)
- `verify=False` in requests/httpx (disabled TLS)
- Weak crypto (MD5/SHA1 for security, `random` instead of `secrets`)
- Missing auth checks on endpoints
- JWT without expiration
- Overly permissive CORS (`allow_origins=['*']`)
- Stack traces/debug mode in production
- Logging sensitive data

**JavaScript/TypeScript Security:**
- XSS (`dangerouslySetInnerHTML`, `innerHTML`)
- Open redirects
- Prototype pollution
- Sensitive data in localStorage
- `eval()` with user input

**Dockerfile Security:**
- Running as root
- Secrets in ENV/ARG/COPY
- Unpinned base images

**CI/CD Security:**
- Secrets in plain text
- Actions pinned to @main/@master
- Overly permissive permissions

If vulnerabilities found:
1. Check for duplicate issues: gh issue list --repo 8thlight/insightmesh --label claude-find --state open --search "<key terms>"
2. Create issues: gh issue create --repo 8thlight/insightmesh --assignee T-rav --label claude-find --title "Security: <title>" --body "<details>"
3. Return {"ok": false, "reason": "Security issues found: [list]. GitHub issue(s) created."}

If no vulnerabilities, return {"ok": true}

Be pragmatic:
- `verify=False` in test files is acceptable
- MD5/SHA1 for non-security checksums is fine
- Don't flag librechat-custom/ or generated/dist files
- Internal service-to-service calls on localhost may skip TLS
```

## Agent 4: Migration Safety Review

```
You are a database migration reviewer. Review changed migration files for safety and correctness.

Steps:
1. Run `git diff --cached --name-only` and `git diff --name-only` to find changed files
2. Filter for migration files (paths containing `migrations/versions/`)
3. If no migration files were changed, return {"ok": true}
4. Read each changed migration file and check:

**Reversibility:**
- Both `upgrade()` and `downgrade()` functions implemented (not just `pass`)?
- Can downgrade safely reverse without data loss?

**Zero-Downtime:**
- `DROP COLUMN`: column no longer read by app code?
- `RENAME COLUMN/TABLE`: suggest 3-step migration instead
- `ADD COLUMN NOT NULL` without default: locks table on large datasets
- `CREATE INDEX`: use CONCURRENTLY for large tables

**Data Integrity:**
- Backfill steps for new NOT NULL columns?
- Foreign key constraints defined?
- Indexes for WHERE/JOIN columns?

**Alembic:**
- Unique revision ID, correct down_revision?
- Clear migration description?

If issues found:
1. Check duplicates: gh issue list --repo 8thlight/insightmesh --label claude-find --state open --search "migration <key terms>"
2. Create issues: gh issue create --repo 8thlight/insightmesh --assignee T-rav --label claude-find --title "Migration: <title>" --body "<details>"
3. Return {"ok": false, "reason": "Migration issues: [list]. GitHub issue(s) created."}

If migrations are safe, return {"ok": true}
```
