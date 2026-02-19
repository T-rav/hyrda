# Full Repo Code Quality Audit

Run a comprehensive code quality and test quality audit across all services in the repo. Launch one Tier 1 coordinator agent per service, all in parallel and in background. Each agent reviews all `.py` source and test files in its service, then creates GitHub issues for findings (with duplicate checking).

## Instructions

1. Launch ALL of the following Tier 1 agents **in parallel** using `Task` with `run_in_background: true` and `subagent_type: "general-purpose"`.
2. Wait for all agents to complete.
3. After all finish, run `gh issue list --repo 8thlight/insightmesh --label claude-find --state open --limit 200` to show the user a final summary of all issues created.

## Tier 1 Agents to Launch

### Agent 1: bot/ audit
```
You are a code quality auditor for the bot/ service in /Users/travisf/Documents/projects/insightmesh.

## Steps
1. Use Glob to list ALL .py files in bot/ — EXCLUDE .venv/, __pycache__/, node_modules/, *.pyc
2. Separate into SOURCE files and TEST files (tests/ directory)
3. Read each file and review against the checklists below
4. For each finding, check for duplicate GH issues first:
   gh issue list --repo 8thlight/insightmesh --label claude-find --state open --search "<key terms>"
5. Create GH issues for NEW findings only:
   gh issue create --repo 8thlight/insightmesh --assignee T-rav --label claude-find --title "<title>" --body "<details with file paths, line numbers, and what needs to change>"

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

## Test File Checklist
- Tests for happy path, edge cases (empty/None/boundary), and error handling
- Proper assertions (not just assert True)
- Tests isolated with mocks/fixtures
- Arrange-Act-Assert pattern
- Flag complex inline object construction (4+ fields) — suggest builder
- Flag repeated setup across tests — suggest factory

## Exclusions
- Don't review librechat-custom/ files
- Don't review generated/dist files

Return a summary of all findings grouped by category, with GH issue URLs created.
```

### Agent 2: shared/ audit
Same prompt as Agent 1, but targeting `shared/` directory.

### Agent 3: agent-service/ audit
Same prompt as Agent 1, but targeting `agent-service/` directory.

### Agent 4: tasks/ audit
Same prompt as Agent 1, but targeting `tasks/` directory.

### Agent 5: control_plane/ audit
Same prompt as Agent 1, but targeting `control_plane/` directory.

### Agent 6: rag-service/ audit
Same prompt as Agent 1, but targeting `rag-service/` directory.

### Agent 7: Dockerfiles, CSS, HTML audit
```
You are a code quality auditor for Dockerfiles, CSS, and HTML templates in /Users/travisf/Documents/projects/insightmesh.

## Steps
1. Use Glob to find all Dockerfile* files, *.css files, and *.html files across the repo
2. EXCLUDE librechat-custom/, dist/, node_modules/
3. Read each file and review against the checklists below
4. Check for duplicate GH issues before creating new ones
5. Create GH issues for NEW findings only

## Dockerfile Checklist
- Pin base image versions (no latest tags)
- Use multi-stage builds where a build step exists
- Minimize layers — combine related RUN commands with &&
- COPY before RUN for better layer caching (deps before source)
- Run as non-root user (USER appuser)
- Set HEALTHCHECK instruction
- No secrets or credentials in build args or environment
- Use SHELL ["/bin/bash", "-o", "pipefail", "-c"] for safe piping
- Consistency with project patterns (public.ecr.aws mirrors, OCI labels, useradd -m -u 1000 appuser, PYTHONUNBUFFERED=1)

## CSS Checklist
- No inline !important unless overriding third-party styles
- Consistent naming (lowercase-hyphenated BEM-style)
- No hardcoded colors — project uses purple-to-violet gradient: #667eea to #764ba2
- No duplicate selectors or properties
- Use relative units (rem, em) over fixed px for font sizes
- Media queries for responsive design
- Consistency with existing CSS in the same UI

## HTML Template Checklist
- Valid HTML structure (DOCTYPE, html, head, body)
- Proper meta charset and viewport tags
- No inline JavaScript (use separate files or script blocks at end of body)
- Accessible: form labels, alt text, proper heading hierarchy
- Escape user-provided data (Jinja2 auto-escaping)
- Consistency with existing templates in the same service

## Exclusions
- Skip librechat-custom/ files
- Skip generated/dist files
- Dockerfile review only for project Dockerfiles, not base images

Return a summary of all findings grouped by category, with GH issue URLs created.
```

## Important Notes
- Each agent should read files directly (no spawning sub-agents)
- Each agent should check `gh issue list --repo 8thlight/insightmesh --label claude-find --state open --search "<terms>"` before creating any issue to avoid duplicates
- All issues should use label `claude-find` and assignee `T-rav`
- Be pragmatic: focus on real issues, not style nitpicks. Small utility functions don't need builders. Simple dataclass construction doesn't need a factory.
