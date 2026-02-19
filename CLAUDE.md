# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Hydra** is a parallel Claude Code issue processor — a multi-agent orchestration system that automates the full GitHub issue lifecycle via git issues and labels.

## Architecture

Hydra runs three concurrent async loops:

1. **Plan loop**: Fetches issues labeled `hydra-plan`, runs a read-only Claude agent to explore the codebase and produce an implementation plan, posts the plan as a comment, then swaps the label to `hydra-ready`.
2. **Implement loop**: Fetches issues labeled `hydra-ready`, creates git worktrees, runs implementation agents with TDD prompts, pushes branches, creates PRs, then swaps to `hydra-review`.
3. **Review loop**: Fetches issues labeled `hydra-review`, runs a review agent to check quality and optionally fix issues, submits a formal PR review, waits for CI, and auto-merges approved PRs. CI failures escalate to `hydra-hitl` for human intervention.

### Key Files

- `cli.py` — CLI entry point
- `orchestrator.py` — Main coordinator (three async polling loops)
- `config.py` — `HydraConfig` Pydantic model
- `agent.py` — `AgentRunner` (implementation agent)
- `planner.py` — `PlannerRunner` (read-only planning agent)
- `reviewer.py` — `ReviewRunner` (review + CI fix agent)
- `worktree.py` — `WorktreeManager` (git worktree lifecycle)
- `pr_manager.py` — `PRManager` (all `gh` CLI operations)
- `dashboard.py` — FastAPI + WebSocket live dashboard
- `events.py` — `EventBus` async pub/sub
- `state.py` — `StateTracker` (JSON-backed crash recovery)
- `models.py` — Pydantic data models
- `stream_parser.py` — Claude CLI stream-json parser
- `ui/` — React dashboard frontend

## Testing is Mandatory

**ALWAYS write unit tests for code changes before committing.** Every new function, class, or feature modification MUST include comprehensive tests.

- New features: Write tests BEFORE committing
- Bug fixes: Add regression tests that reproduce the bug
- Refactoring: Ensure existing tests pass, add tests for new paths
- Never commit untested code

## Never Skip Commit Hooks

**NEVER** use `git commit --no-verify` or `--no-hooks` flags. Always fix code issues first.

## Development Commands

```bash
make run            # Start backend + Vite frontend dev server
make dry-run        # Dry run (log actions without executing)
make clean          # Remove all worktrees and state
make status         # Show current Hydra state
make test           # Run unit tests
make lint           # Auto-fix linting
make lint-check     # Check linting (no fix)
make typecheck      # Run Pyright type checks
make security       # Run Bandit security scan
make quality        # Lint + typecheck + security + test
make setup          # Install git hooks (pre-commit, pre-push)
make ui             # Build React dashboard
make ui-dev         # Start React dashboard dev server
```

### Quick Validation

```bash
# After small changes
make lint && make test

# Before committing
make quality
```

## Tech Stack

- **Python 3.11** with Pydantic, asyncio
- **FastAPI + WebSocket** for dashboard
- **React + Vite** for dashboard UI
- **Ruff** for linting/formatting
- **Pyright** for type checking
- **Bandit** for security scanning
- **pytest + pytest-asyncio** for testing
