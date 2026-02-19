# Full Repo Code Quality Audit

Run a comprehensive code quality and test quality audit across the entire repo. Dynamically discovers the project structure, splits work across parallel agents, and creates GitHub issues for findings.

## Instructions

1. **Resolve configuration** before doing anything else:
   - Run `echo "$HYDRA_GITHUB_REPO"` — if set, use it as the target repo (e.g., `owner/repo`). If empty, run `git remote get-url origin` and extract the `owner/repo` slug (strip `https://github.com/` prefix and `.git` suffix).
   - Run `echo "$HYDRA_GITHUB_ASSIGNEE"` — if set, use it as the issue assignee. If empty, extract the owner from the repo slug (the part before `/`).
   - Run `echo "$HYDRA_LABEL_PLAN"` — if set, use it as the label for created issues. If empty, default to `hydra-plan`.
   - Store resolved values as `$REPO`, `$ASSIGNEE`, `$LABEL`.

2. **Discover project structure:**
   - Use Glob to find all `*.py` source files, excluding `.venv/`, `venv/`, `__pycache__/`, `node_modules/`, `dist/`, `build/`, `*.pyc`.
   - Separate into SOURCE files and TEST files (any file under a `tests/` or `test/` directory, or matching `test_*.py`).
   - Count the files. If >20 source files, split them into 2-3 roughly equal groups for parallel agents.

3. **Launch agents in parallel** using `Task` with `run_in_background: true` and `subagent_type: "general-purpose"`:
   - **Agent 1: Source code audit** — Reviews all (or first half of) source files against the Source File Checklist.
   - **Agent 2: Source code audit (overflow)** — If >20 source files, reviews the second half. Otherwise skip this agent.
   - **Agent 3: Test quality audit** — Reviews all test files against the Test File Checklist.
   - **Agent 4: Non-Python audit** — Reviews Dockerfiles, CSS, HTML, JSX/TSX, YAML against their respective checklists.

4. Wait for all agents to complete.
5. After all finish, run `gh issue list --repo $REPO --label $LABEL --state open --limit 200` to show the user a final summary of all issues created.

## Agent Prompt Template — Source Code Audit

```
You are a code quality auditor for the project at {repo_root}.

## Configuration
- GitHub repo: {REPO}
- Assignee: {ASSIGNEE}
- Label: {LABEL}

## Your Scope
Audit these source files:
{file_list}

## Steps
1. Read each file listed above
2. Review against the checklist below
3. For each finding, check for duplicate GH issues first:
   gh issue list --repo {REPO} --label {LABEL} --state open --search "<key terms>"
4. Create GH issues for NEW findings only:
   gh issue create --repo {REPO} --assignee {ASSIGNEE} --label {LABEL} --title "<title>" --body "<details with file paths, line numbers, and what needs to change>"

## Source File Checklist
- Type hints on all function signatures (params + return)
- dataclass/Pydantic for data containers instead of raw dicts
- Context managers for resource management
- Enum for fixed value sets instead of string constants
- logging over print()
- Function names are verbs, variable names descriptive, class names nouns
- Functions do ONE thing, flag any >25 lines
- Flag 3+ levels of nesting
- Flag functions with >4 parameters
- Flag classes mixing concerns (SRP)
- Files >200 lines — consider splitting
- Read 2-3 neighboring files for pattern consistency

## Be Pragmatic
- Focus on real issues, not style nitpicks
- Small utility functions don't need to be flagged
- Don't flag things that are already well-structured
- Focus on maintainability and correctness issues

Return a summary of all findings grouped by category, with GH issue URLs created.
```

## Agent Prompt Template — Test Quality Audit

```
You are a test quality auditor for the project at {repo_root}.

## Configuration
- GitHub repo: {REPO}
- Assignee: {ASSIGNEE}
- Label: {LABEL}

## Your Scope
Audit these test files:
{test_file_list}

Also reference these shared test utilities:
{helper_files}

## Steps
1. Read each test file
2. For each corresponding source file, check if tests cover:
   - Happy path (normal operation)
   - Edge cases (empty inputs, None values, boundary conditions)
   - Error handling (invalid inputs, failures)
   - All public functions/methods
3. Review test quality against the checklist below
4. For each finding, check for duplicate GH issues first:
   gh issue list --repo {REPO} --label {LABEL} --state open --search "<key terms>"
5. Create GH issues for NEW findings only:
   gh issue create --repo {REPO} --assignee {ASSIGNEE} --label {LABEL} --title "<title>" --body "<details with file paths, line numbers, and what's missing>"

## Test Quality Checklist
- Tests for happy path, edge cases (empty/None/boundary), and error handling
- Proper assertions (not just assert True)
- Tests isolated with mocks/fixtures
- Arrange-Act-Assert (3As) pattern with clear separation
- Flag tests with more than one logical assertion group
- Flag complex inline object construction (4+ fields) — suggest builder
- Flag repeated setup across tests — suggest factory
- Do tests cover all public functions in the source file?
- Are error messages tested (checking exception types and messages)?

## Be Pragmatic
- Not every function needs exhaustive edge case tests
- Focus on functions handling user input or external data
- Focus on functions with conditional logic or error handling paths
- Small utility functions don't need builders
- Simple dataclass construction doesn't need a factory

Return a summary of all findings grouped by category, with GH issue URLs created.
```

## Agent Prompt Template — Non-Python Audit

```
You are a code quality auditor for non-Python files in the project at {repo_root}.

## Configuration
- GitHub repo: {REPO}
- Assignee: {ASSIGNEE}
- Label: {LABEL}

## Steps
1. Use Glob to find all Dockerfile*, *.css, *.html, *.jsx, *.tsx, *.ts (exclude node_modules/, dist/, .venv/, venv/, build/)
2. Read each file and review against the checklists below
3. For each finding, check for duplicate GH issues first:
   gh issue list --repo {REPO} --label {LABEL} --state open --search "<key terms>"
4. Create GH issues for NEW findings only:
   gh issue create --repo {REPO} --assignee {ASSIGNEE} --label {LABEL} --title "<title>" --body "<details>"

## Dockerfile Checklist
- Pin base image versions (no latest tags)
- Multi-stage builds where applicable
- Run as non-root user
- Set HEALTHCHECK instruction
- No secrets in build args or environment

## CSS Checklist
- No inline !important unless overriding third-party
- Consistent naming
- No hardcoded colors that should be variables
- Use relative units (rem, em) over fixed px for font sizes

## HTML Template Checklist
- Valid HTML structure
- Proper meta charset and viewport tags
- Accessible: form labels, alt text, heading hierarchy
- No inline JavaScript where avoidable

## React/JSX/TSX Checklist
- Functional components only
- Proper hooks usage (useMemo/useCallback where needed)
- Props destructuring
- Components focused — flag >100 lines of JSX
- Event handlers named handleX
- No inline object/array literals in JSX props (causes re-renders)

## Be Pragmatic
- Focus on real issues, not perfection
- Dashboard UIs don't need the same rigor as production user-facing apps

Return a summary of all findings grouped by category, with GH issue URLs created.
```

## Important Notes
- Each agent should read files directly (no spawning sub-agents)
- Each agent should check `gh issue list` before creating any issue to avoid duplicates
- All issues should use the resolved `$REPO`, `$ASSIGNEE`, and `$LABEL`
- Be pragmatic: focus on real issues, not style nitpicks
