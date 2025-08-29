# Improved Makefile for Insight Mesh Slack Bot

PYTHON ?= python3
PIP ?= pip3
PROJECT_ROOT := $(CURDIR)/src
ENV_FILE := $(CURDIR)/.env
IMAGE ?= insight-mesh-slack-bot

.PHONY: help install install-test install-dev check-env run test test-coverage test-file test-integration test-unit lint lint-check typecheck quality migrate-status migrate migrate-rollback docker-build docker-run docker-monitor docker-prod docker-stop clean setup-dev ci pre-commit security

help:
	@echo "Available targets:"
	@echo "  install         Install Python dependencies"
	@echo "  install-test    Install test dependencies"
	@echo "  install-dev     Install all dependencies (dev + test)"
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
	@echo "  migrate-status  Show database migration status"
	@echo "  migrate         Apply database migrations"
	@echo "  migrate-rollback Rollback migration (use VERSION=001)"
	@echo "  docker-build    Build Docker image"
	@echo "  docker-run      Run Docker container with .env"
	@echo "  docker-monitor  Run full monitoring stack"
	@echo "  docker-prod     Run production stack"
	@echo "  docker-stop     Stop all containers"
	@echo "  setup-dev       Setup development environment with pre-commit"
	@echo "  pre-commit      Run pre-commit hooks on all files"
	@echo "  security        Run security scanning with bandit"
	@echo "  ci              Run all CI checks locally"
	@echo "  clean           Remove caches and build artifacts"

install:
	$(PIP) install -r $(PROJECT_ROOT)/requirements.txt

install-test:
	$(PIP) install -r $(PROJECT_ROOT)/requirements-test.txt

install-dev: install install-test
	$(PIP) install ruff black isort pyright pre-commit bandit[toml]

check-env:
	@if [ ! -f $(ENV_FILE) ]; then \
		echo "Error: .env not found at $(ENV_FILE)"; \
		echo "Create it with SLACK_BOT_TOKEN, SLACK_APP_TOKEN, LLM_API_URL, LLM_API_KEY"; \
		exit 1; \
	fi

run: check-env
	cd $(PROJECT_ROOT) && $(PYTHON) app.py

test:
	cd $(PROJECT_ROOT) && PYTHONPATH=. ../venv/bin/pytest -v

test-coverage:
	cd $(PROJECT_ROOT) && PYTHONPATH=. ../venv/bin/pytest --cov=. --cov-report=term-missing --cov-report=html:../htmlcov --cov-report=xml:../htmlcov/coverage.xml --cov-fail-under=75 --maxfail=10

test-file:
	cd $(PROJECT_ROOT) && PYTHONPATH=. ../venv/bin/pytest -v tests/$(FILE)

test-integration:
	cd $(PROJECT_ROOT) && PYTHONPATH=. ../venv/bin/pytest -m integration --maxfail=5 -v

test-unit:
	cd $(PROJECT_ROOT) && PYTHONPATH=. ../venv/bin/pytest -m "not integration" -v

lint:
	cd $(PROJECT_ROOT) && ../venv/bin/ruff check . --fix
	cd $(PROJECT_ROOT) && ../venv/bin/black .
	cd $(PROJECT_ROOT) && ../venv/bin/isort .

lint-check:
	cd $(PROJECT_ROOT) && ../venv/bin/ruff check .
	cd $(PROJECT_ROOT) && ../venv/bin/black --check .
	cd $(PROJECT_ROOT) && ../venv/bin/isort --check-only .

typecheck:
	cd $(PROJECT_ROOT) && ../venv/bin/pyright

quality: lint-check typecheck test

migrate-status:
	cd $(PROJECT_ROOT) && $(PYTHON) migrate.py status

migrate:
	cd $(PROJECT_ROOT) && $(PYTHON) migrate.py migrate

migrate-rollback:
	cd $(PROJECT_ROOT) && $(PYTHON) migrate.py rollback $(VERSION)

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
	venv/bin/pre-commit run --all-files

security:
	cd $(PROJECT_ROOT) && ../venv/bin/bandit -r . -f json -o ../security-report.json || ../venv/bin/bandit -r . -f txt

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .coverage htmlcov/ $(PROJECT_ROOT)/htmlcov_slack-bot/
	rm -rf .pytest_cache $(PROJECT_ROOT)/.pytest_cache
	rm -rf .ruff_cache $(PROJECT_ROOT)/.ruff_cache
	rm -rf .pyright_cache $(PROJECT_ROOT)/.pyright_cache
	rm -f security-report.json
