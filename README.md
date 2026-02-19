# Hydra

Multi-agent orchestration system that automates the full GitHub issue lifecycle using Claude Code. Label an issue, Hydra plans it, implements it, opens a PR, reviews it, waits for CI, and auto-merges.

## How It Works

Hydra runs three concurrent async loops that continuously poll for labeled issues:

```
hydra-plan ──> hydra-ready ──> hydra-review ──> hydra-fixed
   │               │                │
   │  Plan agent   │  Impl agent    │  Review agent
   │  explores     │  creates       │  checks quality
   │  codebase,    │  worktree,     │  submits review,
   │  posts plan   │  writes code,  │  waits for CI,
   │  as comment   │  pushes PR     │  auto-merges
   │               │                │
   │               │                └──> hydra-hitl (CI failure)
```

1. **Plan loop** -- Fetches `hydra-plan` issues, runs a read-only Claude agent to explore the codebase and produce an implementation plan, posts it as a comment, swaps label to `hydra-ready`.
2. **Implement loop** -- Fetches `hydra-ready` issues, creates git worktrees, runs implementation agents with TDD prompts, pushes branches, creates PRs, swaps to `hydra-review`.
3. **Review loop** -- Fetches `hydra-review` issues, runs a review agent, submits a formal PR review, waits for CI, and auto-merges. CI failures escalate to `hydra-hitl` for human intervention.

## Prerequisites

- **Python 3.11**
- **[uv](https://docs.astral.sh/uv/)** -- Python package manager
- **[Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code)** -- `claude` must be available on PATH
- **[GitHub CLI](https://cli.github.com/)** -- `gh` must be authenticated (`gh auth login`)
- **Node.js 18+** -- for the dashboard UI (optional)

## Quick Start (Your Own Repo)

### 1. Add Hydra as a git submodule

```bash
cd your-project
git submodule add https://github.com/T-rav/hyrda.git hydra
git submodule update --init
```

### 2. Set up the Python environment

```bash
cd hydra
uv venv venv --python 3.11
uv pip install -e ".[test,dev,dashboard]" --python venv/bin/python
```

### 3. Create GitHub labels

Hydra uses 5 lifecycle labels. Create them in your repo:

```bash
# From the hydra directory (auto-detects your repo from git remote)
make ensure-labels
```

Or set `HYDRA_GITHUB_REPO` to target a different repo:

```bash
HYDRA_GITHUB_REPO=owner/other-repo make ensure-labels
```

### 4. Install the slash commands

Copy Hydra's Claude Code slash commands into your project so you can use `/gh-issue`, `/code-review`, and the audit commands from Claude Code in your own repo:

```bash
# From your project root
mkdir -p .claude/commands

# Copy the commands you want
cp hydra/.claude/commands/gh-issue.md .claude/commands/
cp hydra/.claude/commands/code-review.md .claude/commands/
cp hydra/.claude/commands/audit-code.md .claude/commands/
cp hydra/.claude/commands/audit-integration-tests.md .claude/commands/
cp hydra/.claude/commands/audit-hooks.md .claude/commands/
```

These commands auto-detect your repo from `git remote` and default to the `hydra-plan` label, so created issues feed directly into Hydra's pipeline.

Override the label or repo via environment variables:

```bash
export HYDRA_LABEL_PLAN=hydra-plan        # default
export HYDRA_GITHUB_REPO=owner/repo       # auto-detected if unset
export HYDRA_GITHUB_ASSIGNEE=username     # repo owner if unset
```

### 5. Install Claude Code hooks (optional)

Hydra ships with Claude Code hooks that enforce quality gates during development. To use them in your project:

```bash
# From your project root
mkdir -p .claude/hooks
cp hydra/.claude/hooks/*.sh .claude/hooks/
chmod +x .claude/hooks/*.sh
```

Then merge Hydra's hook configuration into your `.claude/settings.json`. The hooks provide:

| Hook | Trigger | What it does |
|------|---------|--------------|
| `block-destructive-git.sh` | PreToolUse(Bash) | Blocks `git push --force`, `reset --hard`, etc. |
| `validate-tests-before-commit.sh` | PreToolUse(Bash) | Runs lint + tests before `git commit` |
| `scan-secrets-before-commit.sh` | PreToolUse(Bash) | Scans staged files for secrets |
| `enforce-plan-and-explore.sh` | PreToolUse(Write/Edit) | Ensures agent explored before writing code |
| `check-test-counterpart.sh` | PreToolUse(Write) | Warns when writing source without tests |
| `enforce-migrations.sh` | PreToolUse(Write/Edit) | Checks for direct DB schema changes |
| `check-cross-service-impact.sh` | PreToolUse(Edit) | Flags cross-service shared/ changes |
| `track-exploration.sh` | PostToolUse(Read) | Tracks codebase exploration progress |
| `track-code-changes.sh` | PostToolUse(Write/Edit) | Tracks which files were modified |
| `track-planning.sh` | PostToolUse(TaskCreate) | Tracks planning activity |
| `warn-new-file-creation.sh` | PostToolUse(Write) | Warns on new file creation |

### 6. Install git hooks (optional)

```bash
cd hydra
make setup
```

This configures:
- **pre-commit**: Ruff lint check on staged Python files
- **pre-push**: Full quality gate (lint + typecheck + security + tests)

### 7. Run Hydra

```bash
cd hydra

# Start with dashboard (opens http://localhost:5556)
make run

# Or dry-run to see what it would do
make dry-run
```

## Usage

### Creating issues for Hydra

Label a GitHub issue with `hydra-plan` and Hydra picks it up automatically:

```bash
# Via GitHub CLI
gh issue create --label hydra-plan --title "Add retry logic to API client" --body "..."

# Via Claude Code slash command (researches codebase first)
# In Claude Code, type:
/gh-issue add retry logic to the API client
```

### Slash commands

| Command | Description |
|---------|-------------|
| `/gh-issue <description>` | Research codebase and create a well-structured GitHub issue |
| `/code-review` | Run 4 parallel review agents on changed files (tests, clean code, security, migrations) |
| `/audit-code` | Full repo code quality + test audit with parallel agents |
| `/audit-integration-tests` | Integration test coverage gap analysis |
| `/audit-hooks` | Audit Claude Code hooks for correctness and efficiency |

### Label lifecycle

| Label | Meaning | What happens next |
|-------|---------|-------------------|
| `hydra-plan` | Issue needs a plan | Plan agent explores, posts plan comment, swaps to `hydra-ready` |
| `hydra-ready` | Ready for implementation | Impl agent creates worktree, writes code + tests, opens PR, swaps to `hydra-review` |
| `hydra-review` | PR under review | Review agent checks quality, waits for CI, auto-merges, swaps to `hydra-fixed` |
| `hydra-hitl` | Needs human help | CI failed after retries -- human intervention required |
| `hydra-fixed` | Done | PR merged successfully |

Labels can be overridden via CLI flags or environment variables:

```bash
# CLI flags
make run READY_LABEL=custom-ready PLANNER_LABEL=custom-plan

# Environment variables
export HYDRA_LABEL_PLAN=custom-plan
export HYDRA_LABEL_READY=custom-ready
export HYDRA_LABEL_REVIEW=custom-review
export HYDRA_LABEL_HITL=custom-hitl
export HYDRA_LABEL_FIXED=custom-fixed
```

## Configuration

All configuration is via CLI flags or environment variables. Defaults are sensible for most repos.

| Flag | Env var | Default | Description |
|------|---------|---------|-------------|
| `--ready-label` | `HYDRA_LABEL_READY` | `hydra-ready` | Label for implementation queue |
| `--planner-label` | `HYDRA_LABEL_PLAN` | `hydra-plan` | Label for planning queue |
| `--review-label` | `HYDRA_LABEL_REVIEW` | `hydra-review` | Label for review queue |
| `--hitl-label` | `HYDRA_LABEL_HITL` | `hydra-hitl` | Label for human escalation |
| `--fixed-label` | `HYDRA_LABEL_FIXED` | `hydra-fixed` | Label for completed issues |
| `--max-workers` | -- | `2` | Concurrent implementation agents |
| `--model` | -- | `sonnet` | Model for implementation agents |
| `--planner-model` | -- | `opus` | Model for planning agents |
| `--review-model` | -- | `opus` | Model for review agents |
| `--max-budget-usd` | -- | `0` (unlimited) | USD cap per implementation agent |
| `--repo` | `HYDRA_GITHUB_REPO` | auto-detected | GitHub `owner/repo` slug |
| `--dashboard-port` | -- | `5555` | Dashboard API port |
| `--no-dashboard` | -- | -- | Disable the web dashboard |
| `--dry-run` | -- | -- | Log actions without executing |

## Development

```bash
make test           # Run unit tests
make lint           # Auto-fix linting (ruff)
make lint-check     # Check linting without fixing
make typecheck      # Run Pyright type checks
make security       # Run Bandit security scan
make quality        # All of the above
make ensure-labels  # Create Hydra labels in GitHub repo
make setup          # Install git hooks
make ui             # Build React dashboard
make ui-dev         # Start dashboard dev server
make clean          # Remove all worktrees and state
make status         # Show current Hydra state
```

## Architecture

```
cli.py                 CLI entry point
orchestrator.py        Main coordinator (3 async polling loops)
config.py              HydraConfig (Pydantic model)
agent.py               AgentRunner (implementation agent)
planner.py             PlannerRunner (read-only planning agent)
reviewer.py            ReviewRunner (review + CI fix agent)
worktree.py            WorktreeManager (git worktree lifecycle)
pr_manager.py          PRManager (all gh CLI operations + label enforcement)
dashboard.py           FastAPI + WebSocket live dashboard
events.py              EventBus (async pub/sub)
state.py               StateTracker (JSON-backed crash recovery)
models.py              Pydantic data models
stream_parser.py       Claude CLI stream-json parser
ui/                    React dashboard frontend
.claude/commands/      Claude Code slash commands
.claude/hooks/         Claude Code quality gate hooks
.claude/agents/        Claude Code agent definitions
.githooks/             Git pre-commit and pre-push hooks
```

## Tech Stack

- **Python 3.11** with Pydantic, asyncio
- **FastAPI + WebSocket** for the live dashboard
- **React + Vite** for dashboard UI
- **Ruff** for linting/formatting
- **Pyright** for type checking
- **Bandit** for security scanning
- **pytest + pytest-asyncio** for testing
