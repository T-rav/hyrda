# Improved Makefile for Insight Mesh Slack Bot
# This Makefile automatically detects the project root and works from any subdirectory

# Determine project root directory (where this Makefile is located)
MAKEFILE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
PROJECT_ROOT_DIR := $(MAKEFILE_DIR)
BOT_DIR := $(PROJECT_ROOT_DIR)bot

# Virtual environment settings
VENV := $(PROJECT_ROOT_DIR)venv
PYTHON := $(VENV)/bin/python3.11
PIP := $(VENV)/bin/pip
ENV_FILE := $(PROJECT_ROOT_DIR).env
IMAGE ?= insight-mesh-slack-bot

# Find Python command with ruff installed (for linting)
PYTHON_LINT := $(shell for cmd in python3.11 python3 python; do \
    if command -v $$cmd >/dev/null 2>&1 && $$cmd -m ruff --version >/dev/null 2>&1; then \
        echo $$cmd; break; \
    fi; \
done)

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
RESET := \033[0m

.PHONY: help install install-test install-dev check-env run test test-coverage test-file test-integration test-unit test-ingest lint lint-check typecheck quality docker-build docker-run docker-monitor docker-prod docker-stop clean clean-all setup-dev ci pre-commit security python-version

help:
	@echo "$(BLUE)AI Slack Bot - Available Make Targets:$(RESET)"
	@echo ""
	@echo "$(GREEN)Environment Setup:$(RESET)"
	@echo "  install         Install Python dependencies in virtual environment"
	@echo "  install-test    Install with test dependencies"
	@echo "  install-dev     Install with dev and test dependencies"
	@echo "  python-version  Show Python and pip versions"
	@echo ""
	@echo "$(GREEN)Development:$(RESET)"
	@echo "  run             Run the bot (standalone)"
	@echo "  test            Run test suite"
	@echo "  test-coverage   Run tests with coverage report"
	@echo "  test-file       Run specific test file (use FILE=filename)"
	@echo "  test-integration Run integration tests only"
	@echo "  test-unit       Run unit tests only"
	@echo "  test-ingest     Run ingestion service tests"
	@echo "  lint            Run linting and formatting"
	@echo "  lint-check      Check linting without fixing"
	@echo "  typecheck       Run type checking"
	@echo "  quality         Run all quality checks"
	@echo ""
	@echo "$(GREEN)Docker:$(RESET)"
	@echo "  docker-build    Build Docker image"
	@echo "  docker-run      Run Docker container with .env"
	@echo "  docker-monitor  Run full monitoring stack"
	@echo "  docker-prod     Run production stack"
	@echo "  docker-stop     Stop all containers"
	@echo ""
	@echo "$(GREEN)Maintenance:$(RESET)"
	@echo "  setup-dev       Setup development environment with pre-commit"
	@echo "  pre-commit      Run pre-commit hooks on all files"
	@echo "  security        Run security scanning with bandit"
	@echo "  ci              Run all CI checks locally"
	@echo "  clean           Remove caches and build artifacts"
	@echo "  clean-all       Remove caches and virtual environment"

$(VENV):
	@echo "$(BLUE)Creating Python 3.11 virtual environment...$(RESET)"
	python3.11 -m venv $(VENV)
	@echo "$(GREEN)Virtual environment created at $(VENV)$(RESET)"

install: $(VENV)
	@echo "$(BLUE)Installing project dependencies...$(RESET)"
	cd $(BOT_DIR) && $(PIP) install -e .
	@echo "$(GREEN)Dependencies installed successfully$(RESET)"

install-test: $(VENV)
	@echo "$(BLUE)Installing project with test dependencies...$(RESET)"
	cd $(BOT_DIR) && $(PIP) install -e .[test]
	@echo "$(GREEN)Test dependencies installed successfully$(RESET)"

install-dev: $(VENV)
	@echo "$(BLUE)Installing project with dev and test dependencies...$(RESET)"
	cd $(BOT_DIR) && $(PIP) install -e .[dev,test]
	@echo "$(GREEN)Development dependencies installed successfully$(RESET)"

check-env:
	@if [ ! -f $(ENV_FILE) ]; then \
		echo "Error: .env not found at $(ENV_FILE)"; \
		echo "Create it with SLACK_BOT_TOKEN, SLACK_APP_TOKEN, LLM_API_URL, LLM_API_KEY"; \
		exit 1; \
	fi

run: check-env
	cd $(BOT_DIR) && $(PYTHON) app.py

test: $(VENV)
	@echo "$(BLUE)Running test suite...$(RESET)"
	cd $(BOT_DIR) && PYTHONPATH=. $(PYTHON) -m pytest -v

test-coverage: $(VENV)
	@echo "$(BLUE)Running tests with coverage...$(RESET)"
	cd $(BOT_DIR) && PYTHONPATH=. $(PYTHON) -m coverage run --source=. --omit="app.py" -m pytest && $(PYTHON) -m coverage report

test-file: $(VENV)
	@echo "$(BLUE)Running specific test file: $(FILE)...$(RESET)"
	cd $(BOT_DIR) && PYTHONPATH=. $(PYTHON) -m pytest -v tests/$(FILE)

test-integration: $(VENV)
	@echo "$(BLUE)Running integration tests...$(RESET)"
	cd $(BOT_DIR) && PYTHONPATH=. $(PYTHON) -m pytest -m integration --maxfail=5 -v

test-unit: $(VENV)
	@echo "$(BLUE)Running unit tests...$(RESET)"
	cd $(BOT_DIR) && PYTHONPATH=. $(PYTHON) -m pytest -m "not integration" -v

test-ingest: $(VENV)
	@echo "$(BLUE)Running ingestion service tests...$(RESET)"
	cd $(PROJECT_ROOT_DIR)ingest && PYTHONPATH=. $(PYTHON) -m pytest -v

lint:
	@echo "$(BLUE)🔍 Running unified linting with ruff (using $(PYTHON_LINT))...$(RESET)"
	@if [ -z "$(PYTHON_LINT)" ]; then \
		echo "$(RED)❌ Error: No Python interpreter with ruff found. Please install ruff:$(RESET)"; \
		echo "   python -m pip install ruff pyright bandit"; \
		exit 1; \
	fi
	@echo "$(BLUE)📝 Running ruff linting with auto-fix...$(RESET)"
	$(PYTHON_LINT) -m ruff check $(BOT_DIR) --fix
	@echo "$(BLUE)🎨 Running ruff formatting...$(RESET)"
	$(PYTHON_LINT) -m ruff format $(BOT_DIR)
	@echo "$(BLUE)🔍 Running type checking...$(RESET)"
	cd $(BOT_DIR) && $(PYTHON_LINT) -m pyright
	@echo "$(BLUE)🔒 Running security checks...$(RESET)"
	cd $(BOT_DIR) && ($(PYTHON_LINT) -m bandit -r . -c ../pyproject.toml -f txt || echo "$(YELLOW)⚠️  Bandit check failed (non-blocking)$(RESET)")
	@echo "$(GREEN)✅ All checks completed with ruff + pyright + bandit!$(RESET)"

lint-check:
	@echo "$(BLUE)🔍 Running unified linting checks (using $(PYTHON_LINT))...$(RESET)"
	@if [ -z "$(PYTHON_LINT)" ]; then \
		echo "$(RED)❌ Error: No Python interpreter with ruff found. Please install ruff:$(RESET)"; \
		echo "   python -m pip install ruff pyright bandit"; \
		exit 1; \
	fi
	@echo "$(BLUE)🔍 Running ruff check (no fixes)...$(RESET)"
	$(PYTHON_LINT) -m ruff check $(BOT_DIR)
	@echo "$(BLUE)🎨 Checking ruff formatting...$(RESET)"
	$(PYTHON_LINT) -m ruff format $(BOT_DIR) --check
	@echo "$(BLUE)🔍 Running type checking...$(RESET)"
	cd $(BOT_DIR) && $(PYTHON_LINT) -m pyright
	@echo "$(BLUE)🔒 Running security checks...$(RESET)"
	cd $(BOT_DIR) && ($(PYTHON_LINT) -m bandit -r . -c ../pyproject.toml -f txt || echo "$(YELLOW)⚠️  Bandit check failed (non-blocking)$(RESET)")
	@echo "$(GREEN)✅ All checks completed with ruff + pyright + bandit!$(RESET)"

typecheck: $(VENV)
	@echo "$(BLUE)Running type checking with pyright...$(RESET)"
	cd $(BOT_DIR) && $(VENV)/bin/pyright || $(PYTHON) -m pyright

quality: lint-check test


docker-build:
	docker build -f $(BOT_DIR)/Dockerfile -t $(IMAGE) $(BOT_DIR)

docker-run: check-env
	docker run --rm --env-file $(ENV_FILE) --name $(IMAGE) $(IMAGE)

docker-monitor:
	cd $(PROJECT_ROOT_DIR) && docker-compose -f docker-compose.monitoring.yml up -d

docker-prod:
	cd $(PROJECT_ROOT_DIR) && docker-compose -f docker-compose.prod.yml up -d

docker-stop:
	cd $(PROJECT_ROOT_DIR) && docker-compose -f docker-compose.monitoring.yml down
	cd $(PROJECT_ROOT_DIR) && docker-compose -f docker-compose.prod.yml down

setup-dev: install-dev
	@if [ ! -f $(PROJECT_ROOT_DIR).env.test ]; then cp $(BOT_DIR)/tests/.env.test $(PROJECT_ROOT_DIR).env.test; fi
	cd $(PROJECT_ROOT_DIR) && pre-commit install
	@echo "✅ Development environment set up!"
	@echo "✅ Pre-commit hooks installed!"
	@echo "Run 'make test' to run tests"

ci: quality test-coverage docker-build
	@echo "✅ All CI checks passed!"

pre-commit:
	cd $(PROJECT_ROOT_DIR) && pre-commit run --all-files

security: $(VENV)
	@echo "$(BLUE)Running security scan with bandit...$(RESET)"
	cd $(BOT_DIR) && $(PYTHON) -m bandit -r . -f json -o $(PROJECT_ROOT_DIR)security-report.json || $(PYTHON) -m bandit -r . -f txt

clean:
	@echo "$(YELLOW)Cleaning up build artifacts and caches...$(RESET)"
	find $(PROJECT_ROOT_DIR) -type f -name "*.pyc" -delete
	find $(PROJECT_ROOT_DIR) -type d -name "__pycache__" -delete
	rm -rf $(PROJECT_ROOT_DIR).coverage $(PROJECT_ROOT_DIR)htmlcov/ $(BOT_DIR)/htmlcov_slack-bot/
	rm -rf $(PROJECT_ROOT_DIR).pytest_cache $(BOT_DIR)/.pytest_cache
	rm -rf $(PROJECT_ROOT_DIR).ruff_cache $(BOT_DIR)/.ruff_cache
	rm -rf $(PROJECT_ROOT_DIR).pyright_cache $(BOT_DIR)/.pyright_cache
	rm -f $(PROJECT_ROOT_DIR)security-report.json
	@echo "$(GREEN)Cleanup completed$(RESET)"

clean-all: clean
	@echo "$(YELLOW)Removing virtual environment...$(RESET)"
	rm -rf $(VENV)
	@echo "$(GREEN)Virtual environment removed$(RESET)"

python-version: $(VENV)
	@echo "$(BLUE)Python version information:$(RESET)"
	@$(PYTHON) --version
	@$(PIP) --version
