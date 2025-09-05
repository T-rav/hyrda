# Improved Makefile for Insight Mesh Slack Bot

# Virtual environment settings
VENV := $(CURDIR)/venv
PYTHON := $(VENV)/bin/python3.11
PIP := $(VENV)/bin/pip
PROJECT_ROOT := $(CURDIR)/bot
ENV_FILE := $(CURDIR)/.env
IMAGE ?= insight-mesh-slack-bot

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
RESET := \033[0m

.PHONY: help install install-test install-dev check-env run test test-coverage test-file test-integration test-unit lint lint-check typecheck quality docker-build docker-run docker-monitor docker-prod docker-stop clean clean-all setup-dev ci pre-commit security python-version

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
	cd $(PROJECT_ROOT) && $(PIP) install -e .
	@echo "$(GREEN)Dependencies installed successfully$(RESET)"

install-test: $(VENV)
	@echo "$(BLUE)Installing project with test dependencies...$(RESET)"
	cd $(PROJECT_ROOT) && $(PIP) install -e .[test]
	@echo "$(GREEN)Test dependencies installed successfully$(RESET)"

install-dev: $(VENV)
	@echo "$(BLUE)Installing project with dev and test dependencies...$(RESET)"
	cd $(PROJECT_ROOT) && $(PIP) install -e .[dev,test]
	@echo "$(GREEN)Development dependencies installed successfully$(RESET)"

check-env:
	@if [ ! -f $(ENV_FILE) ]; then \
		echo "Error: .env not found at $(ENV_FILE)"; \
		echo "Create it with SLACK_BOT_TOKEN, SLACK_APP_TOKEN, LLM_API_URL, LLM_API_KEY"; \
		exit 1; \
	fi

run: check-env
	cd $(PROJECT_ROOT) && $(PYTHON) app.py

test: $(VENV)
	@echo "$(BLUE)Running test suite...$(RESET)"
	cd $(PROJECT_ROOT) && PYTHONPATH=. $(PYTHON) -m pytest -v

test-coverage: $(VENV)
	@echo "$(BLUE)Running tests with coverage...$(RESET)"
	cd $(PROJECT_ROOT) && PYTHONPATH=. $(PYTHON) -m coverage run --source=. --omit="app.py" -m pytest && $(PYTHON) -m coverage report

test-file: $(VENV)
	@echo "$(BLUE)Running specific test file: $(FILE)...$(RESET)"
	cd $(PROJECT_ROOT) && PYTHONPATH=. $(PYTHON) -m pytest -v tests/$(FILE)

test-integration: $(VENV)
	@echo "$(BLUE)Running integration tests...$(RESET)"
	cd $(PROJECT_ROOT) && PYTHONPATH=. $(PYTHON) -m pytest -m integration --maxfail=5 -v

test-unit: $(VENV)
	@echo "$(BLUE)Running unit tests...$(RESET)"
	cd $(PROJECT_ROOT) && PYTHONPATH=. $(PYTHON) -m pytest -m "not integration" -v

lint:
	./scripts/lint.sh --fix

lint-check:
	./scripts/lint.sh

typecheck: $(VENV)
	@echo "$(BLUE)Running type checking with pyright...$(RESET)"
	cd $(PROJECT_ROOT) && $(VENV)/bin/pyright || $(PYTHON) -m pyright

quality: lint-check test


docker-build:
	docker build -f $(PROJECT_ROOT)/Dockerfile -t $(IMAGE) $(PROJECT_ROOT)

docker-run: check-env
	docker run --rm --env-file $(ENV_FILE) --name $(IMAGE) $(IMAGE)

docker-monitor:
	docker-compose -f docker-compose.monitoring.yml up -d

docker-prod:
	docker-compose -f docker-compose.prod.yml up -d

docker-stop:
	docker-compose -f docker-compose.monitoring.yml down
	docker-compose -f docker-compose.prod.yml down

setup-dev: install-dev
	@if [ ! -f .env.test ]; then cp $(PROJECT_ROOT)/tests/.env.test .env.test; fi
	pre-commit install
	@echo "✅ Development environment set up!"
	@echo "✅ Pre-commit hooks installed!"
	@echo "Run 'make test' to run tests"

ci: quality test-coverage docker-build
	@echo "✅ All CI checks passed!"

pre-commit:
	pre-commit run --all-files

security: $(VENV)
	@echo "$(BLUE)Running security scan with bandit...$(RESET)"
	cd $(PROJECT_ROOT) && $(PYTHON) -m bandit -r . -f json -o ../security-report.json || $(PYTHON) -m bandit -r . -f txt

clean:
	@echo "$(YELLOW)Cleaning up build artifacts and caches...$(RESET)"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .coverage htmlcov/ $(PROJECT_ROOT)/htmlcov_slack-bot/
	rm -rf .pytest_cache $(PROJECT_ROOT)/.pytest_cache
	rm -rf .ruff_cache $(PROJECT_ROOT)/.ruff_cache
	rm -rf .pyright_cache $(PROJECT_ROOT)/.pyright_cache
	rm -f security-report.json
	@echo "$(GREEN)Cleanup completed$(RESET)"

clean-all: clean
	@echo "$(YELLOW)Removing virtual environment...$(RESET)"
	rm -rf $(VENV)
	@echo "$(GREEN)Virtual environment removed$(RESET)"

python-version: $(VENV)
	@echo "$(BLUE)Python version information:$(RESET)"
	@$(PYTHON) --version
	@$(PIP) --version
