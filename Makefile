# Makefile for Hydra — Intent in. Software out.

HYDRA_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
PROJECT_ROOT := $(abspath $(HYDRA_DIR))

# Load .env if present (export all variables)
-include $(PROJECT_ROOT)/.env
export
VENV := $(PROJECT_ROOT)/venv
UV := VIRTUAL_ENV=$(VENV) uv run --active

# CLI argument passthrough
READY_LABEL ?= hydra-ready
WORKERS ?= 3
MODEL ?= opus
REVIEW_MODEL ?= opus
BATCH_SIZE ?= 15
BUDGET ?= 0
REVIEW_BUDGET ?= 0
PLANNER_LABEL ?= hydra-plan
PLANNER_MODEL ?= opus
PLANNER_BUDGET ?= 0
REVIEWERS ?= 5
HITL_WORKERS ?= 1
PORT ?= 5555
LOG_DIR ?= $(PROJECT_ROOT)/.hydra/logs

# Colors
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
RESET := \033[0m

.PHONY: help run dev dry-run clean test lint lint-check typecheck security quality install setup status ui ui-dev ui-clean ensure-labels

help:
	@echo "$(BLUE)Hydra — Intent in. Software out.$(RESET)"
	@echo ""
	@echo "$(GREEN)Commands:$(RESET)"
	@echo "  make dev            Start backend + Vite frontend dev server"
	@echo "  make run            Run Hydra (processes issues with agents)"
	@echo "  make dry-run        Dry run (log actions without executing)"
	@echo "  make clean          Remove all worktrees and state"
	@echo "  make status         Show current Hydra state"
	@echo "  make test           Run unit tests"
	@echo "  make lint           Auto-fix linting"
	@echo "  make lint-check     Check linting (no fix)"
	@echo "  make typecheck      Run Pyright type checks"
	@echo "  make security       Run Bandit security scan"
	@echo "  make quality        Lint + typecheck + security + test"
	@echo "  make ensure-labels  Create Hydra labels in GitHub repo"
	@echo "  make setup          Install git hooks (pre-commit, pre-push)"
	@echo "  make install        Install dashboard dependencies"
	@echo "  make ui             Build React dashboard (ui/dist/)"
	@echo "  make ui-dev         Start React dashboard dev server"
	@echo "  make ui-clean       Remove ui/dist and node_modules"
	@echo ""
	@echo "$(GREEN)Options (override with make run LABEL=bug WORKERS=3):$(RESET)"
	@echo "  READY_LABEL      GitHub issue label (default: hydra-ready)"
	@echo "  WORKERS          Max concurrent agents (default: 2)"
	@echo "  MODEL            Implementation model (default: sonnet)"
	@echo "  REVIEW_MODEL     Review model (default: opus)"
	@echo "  BATCH_SIZE       Issues per batch (default: 15)"
	@echo "  BUDGET           USD per impl agent (default: 0 = unlimited)"
	@echo "  REVIEW_BUDGET    USD per review agent (default: 0 = unlimited)"
	@echo "  PLANNER_LABEL    Planner issue label (default: hydra-plan)"
	@echo "  PLANNER_MODEL    Planner model (default: opus)"
	@echo "  PLANNER_BUDGET   USD per planner agent (default: 0 = unlimited)"
	@echo "  HITL_WORKERS     Max concurrent HITL agents (default: 1)"
	@echo "  PORT             Dashboard port (default: 5555)"
	@echo "  LOG_DIR          Log directory (default: .hydra/logs)"

run:
	@mkdir -p $(LOG_DIR)
	@echo "$(BLUE)Starting Hydra — backend :$(PORT) + frontend :5556$(RESET)"
	@echo "$(GREEN)Open http://localhost:5556 to use the dashboard$(RESET)"
	@trap 'kill 0' EXIT; \
	cd $(HYDRA_DIR)ui && npm install --silent 2>/dev/null && npm run dev 2>&1 | tee $(LOG_DIR)/vite.log & \
	cd $(HYDRA_DIR) && $(UV) python cli.py \
		--ready-label $(READY_LABEL) \
		--max-workers $(WORKERS) \
		--model $(MODEL) \
		--review-model $(REVIEW_MODEL) \
		--batch-size $(BATCH_SIZE) \
		--max-budget-usd $(BUDGET) \
		--review-budget-usd $(REVIEW_BUDGET) \
		--planner-label $(PLANNER_LABEL) \
		--planner-model $(PLANNER_MODEL) \
		--planner-budget-usd $(PLANNER_BUDGET) \
		--max-reviewers $(REVIEWERS) \
		--max-hitl-workers $(HITL_WORKERS) \
		--dashboard-port $(PORT) & \
	wait

dev: run

dry-run:
	@echo "$(BLUE)Hydra dry run — label=$(READY_LABEL)$(RESET)"
	@cd $(HYDRA_DIR) && $(UV) python cli.py \
		--ready-label $(READY_LABEL) \
		--max-workers $(WORKERS) \
		--batch-size $(BATCH_SIZE) \
		--dry-run --verbose
	@echo "$(GREEN)Dry run complete$(RESET)"

clean:
	@echo "$(YELLOW)Cleaning up Hydra worktrees and state...$(RESET)"
	@cd $(HYDRA_DIR) && $(UV) python cli.py --clean
	@echo "$(GREEN)Cleanup complete$(RESET)"

status:
	@echo "$(BLUE)Hydra State:$(RESET)"
	@if [ -f $(PROJECT_ROOT)/.hydra/state.json ]; then \
		cat $(PROJECT_ROOT)/.hydra/state.json | python -m json.tool; \
	else \
		echo "$(YELLOW)No state file found (Hydra has not run yet)$(RESET)"; \
	fi

test:
	@echo "$(BLUE)Running Hydra unit tests...$(RESET)"
	@cd $(HYDRA_DIR) && PYTHONPATH=. $(UV) pytest tests/ -v
	@echo "$(GREEN)All tests passed$(RESET)"

test-fast:
	@cd $(HYDRA_DIR) && PYTHONPATH=. $(UV) pytest tests/ -x -q --tb=short

lint:
	@echo "$(BLUE)Linting Hydra (auto-fix)...$(RESET)"
	@cd $(HYDRA_DIR) && $(UV) ruff check . --fix && $(UV) ruff format .
	@echo "$(GREEN)Linting complete$(RESET)"

lint-check:
	@echo "$(BLUE)Checking Hydra linting...$(RESET)"
	@cd $(HYDRA_DIR) && $(UV) ruff check . && $(UV) ruff format . --check
	@echo "$(GREEN)Lint check passed$(RESET)"

typecheck:
	@echo "$(BLUE)Running Pyright type checks...$(RESET)"
	@cd $(HYDRA_DIR) && $(UV) pyright
	@echo "$(GREEN)Type check passed$(RESET)"

security:
	@echo "$(BLUE)Running Bandit security scan...$(RESET)"
	@cd $(HYDRA_DIR) && $(UV) bandit -c pyproject.toml -r . --severity-level medium
	@echo "$(GREEN)Security scan passed$(RESET)"

quality: lint-check typecheck security test
	@echo "$(GREEN)Hydra quality pipeline passed$(RESET)"

install:
	@echo "$(BLUE)Installing Hydra dashboard dependencies...$(RESET)"
	@VIRTUAL_ENV=$(VENV) uv pip install fastapi uvicorn websockets
	@echo "$(GREEN)Dashboard dependencies installed$(RESET)"

setup:
	@if ! command -v gh >/dev/null 2>&1; then \
		echo "$(BLUE)Installing gh CLI...$(RESET)"; \
		if command -v brew >/dev/null 2>&1; then \
			brew install gh; \
		elif command -v apt-get >/dev/null 2>&1; then \
			sudo apt-get update && sudo apt-get install -y gh; \
		elif command -v dnf >/dev/null 2>&1; then \
			sudo dnf install -y gh; \
		else \
			echo "$(RED)Error: Could not install gh CLI automatically. Install it manually: https://cli.github.com$(RESET)"; \
			exit 1; \
		fi; \
	fi
	@echo "  gh CLI: $$(gh --version | head -1)"
	@if ! gh auth status >/dev/null 2>&1; then \
		echo "$(YELLOW)gh CLI is not authenticated. Starting login...$(RESET)"; \
		gh auth login; \
	fi
	@echo "  gh user: $$(gh api user --jq .login)"
	@echo "$(BLUE)Setting up git hooks...$(RESET)"
	@git config core.hooksPath .githooks
	@echo "$(GREEN)Setup complete$(RESET)"
	@echo "  pre-commit: lint check on staged Python files"
	@echo "  pre-push:   full quality gate (lint + typecheck + security + tests)"

REPO_SLUG := $(shell git remote get-url origin 2>/dev/null | sed 's|.*github\.com[:/]||;s|\.git$$||')

ensure-labels:
	@echo "$(BLUE)Ensuring Hydra labels exist in $(REPO_SLUG)...$(RESET)"
	@gh label create "$(PLANNER_LABEL)" --repo "$(REPO_SLUG)" --color c5def5 --description "Issue needs planning before implementation" --force 2>/dev/null || true
	@gh label create "$(READY_LABEL)" --repo "$(REPO_SLUG)" --color 0e8a16 --description "Issue ready for implementation" --force 2>/dev/null || true
	@gh label create "hydra-review" --repo "$(REPO_SLUG)" --color fbca04 --description "Issue/PR under review" --force 2>/dev/null || true
	@gh label create "hydra-hitl" --repo "$(REPO_SLUG)" --color d93f0b --description "Escalated to human-in-the-loop" --force 2>/dev/null || true
	@gh label create "hydra-hitl-active" --repo "$(REPO_SLUG)" --color e99695 --description "Being processed by HITL correction agent" --force 2>/dev/null || true
	@gh label create "hydra-fixed" --repo "$(REPO_SLUG)" --color 0075ca --description "PR merged — issue completed" --force 2>/dev/null || true
	@echo "$(GREEN)All Hydra labels ensured$(RESET)"

ui:
	@echo "$(BLUE)Building Hydra React dashboard...$(RESET)"
	@cd $(HYDRA_DIR)ui && npm install && npm run build
	@echo "$(GREEN)Dashboard built → ui/dist/$(RESET)"

ui-dev:
	@echo "$(BLUE)Starting Hydra dashboard dev server...$(RESET)"
	@cd $(HYDRA_DIR)ui && npm install && npm run dev

ui-clean:
	@echo "$(YELLOW)Cleaning dashboard build artifacts...$(RESET)"
	@rm -rf $(HYDRA_DIR)ui/dist $(HYDRA_DIR)ui/node_modules
	@echo "$(GREEN)Dashboard cleaned$(RESET)"
