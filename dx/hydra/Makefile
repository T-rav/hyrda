# Makefile for Hydra — Parallel Claude Code Issue Processor

HYDRA_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
PROJECT_ROOT := $(abspath $(HYDRA_DIR)../..)
VENV := $(PROJECT_ROOT)/venv
UV := VIRTUAL_ENV=$(VENV) uv run --active

# CLI argument passthrough
LABEL ?= ready
WORKERS ?= 5
MODEL ?= sonnet
REVIEW_MODEL ?= opus
BATCH_SIZE ?= 15
BUDGET ?= 5.0
REVIEW_BUDGET ?= 3.0
PORT ?= 5555

# Colors
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
RESET := \033[0m

.PHONY: help run dry-run clean test lint lint-check quality install status ui ui-dev ui-clean

help:
	@echo "$(BLUE)Hydra — Parallel Claude Code Issue Processor$(RESET)"
	@echo ""
	@echo "$(GREEN)Commands:$(RESET)"
	@echo "  make run            Run Hydra (processes issues with agents)"
	@echo "  make dry-run        Dry run (log actions without executing)"
	@echo "  make clean          Remove all worktrees and state"
	@echo "  make status         Show current Hydra state"
	@echo "  make test           Run unit tests"
	@echo "  make lint           Auto-fix linting"
	@echo "  make lint-check     Check linting (no fix)"
	@echo "  make quality        Lint + test"
	@echo "  make install        Install dashboard dependencies"
	@echo "  make ui             Build React dashboard (ui/dist/)"
	@echo "  make ui-dev         Start React dashboard dev server"
	@echo "  make ui-clean       Remove ui/dist and node_modules"
	@echo ""
	@echo "$(GREEN)Options (override with make run LABEL=bug WORKERS=3):$(RESET)"
	@echo "  LABEL          GitHub issue label (default: ready)"
	@echo "  WORKERS        Max concurrent agents (default: 5)"
	@echo "  MODEL          Implementation model (default: sonnet)"
	@echo "  REVIEW_MODEL   Review model (default: opus)"
	@echo "  BATCH_SIZE     Issues per batch (default: 15)"
	@echo "  BUDGET         USD per impl agent (default: 5.0)"
	@echo "  REVIEW_BUDGET  USD per review agent (default: 3.0)"
	@echo "  PORT           Dashboard port (default: 5555)"

run:
	@echo "$(BLUE)Starting Hydra — label=$(LABEL) workers=$(WORKERS) model=$(MODEL)$(RESET)"
	@cd $(HYDRA_DIR) && $(UV) python cli.py \
		--label $(LABEL) \
		--max-workers $(WORKERS) \
		--model $(MODEL) \
		--review-model $(REVIEW_MODEL) \
		--batch-size $(BATCH_SIZE) \
		--max-budget-usd $(BUDGET) \
		--review-budget-usd $(REVIEW_BUDGET) \
		--dashboard-port $(PORT)
	@echo "$(GREEN)Hydra complete$(RESET)"

dry-run:
	@echo "$(BLUE)Hydra dry run — label=$(LABEL)$(RESET)"
	@cd $(HYDRA_DIR) && $(UV) python cli.py \
		--label $(LABEL) \
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
	@if [ -f $(PROJECT_ROOT)/.hydra-state.json ]; then \
		cat $(PROJECT_ROOT)/.hydra-state.json | python -m json.tool; \
	else \
		echo "$(YELLOW)No state file found (Hydra has not run yet)$(RESET)"; \
	fi

test:
	@echo "$(BLUE)Running Hydra unit tests...$(RESET)"
	@cd $(HYDRA_DIR) && PYTHONPATH=. $(UV) pytest tests/ -v
	@echo "$(GREEN)All tests passed$(RESET)"

lint:
	@echo "$(BLUE)Linting Hydra (auto-fix)...$(RESET)"
	@cd $(HYDRA_DIR) && $(UV) ruff check . --fix && $(UV) ruff format .
	@echo "$(GREEN)Linting complete$(RESET)"

lint-check:
	@echo "$(BLUE)Checking Hydra linting...$(RESET)"
	@cd $(HYDRA_DIR) && $(UV) ruff check . && $(UV) ruff format . --check
	@echo "$(GREEN)Lint check passed$(RESET)"

quality: lint-check test
	@echo "$(GREEN)Hydra quality pipeline passed$(RESET)"

install:
	@echo "$(BLUE)Installing Hydra dashboard dependencies...$(RESET)"
	@VIRTUAL_ENV=$(VENV) uv pip install fastapi uvicorn websockets
	@echo "$(GREEN)Dashboard dependencies installed$(RESET)"

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
