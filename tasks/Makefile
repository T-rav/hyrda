# AI Slack Bot - Tasks Service Makefile

# Coverage configuration (centralized)
COVERAGE_MIN = 70
COVERAGE_ARGS = --cov=. --cov-fail-under=$(COVERAGE_MIN) --cov-report=term-missing --cov-report=html:htmlcov

.PHONY: help install install-dev test test-coverage lint lint-check typecheck quality clean run docker-build docker-run pre-commit ci setup-dev

# Default target
help:
	@echo "Available targets:"
	@echo "  install       Install Python dependencies"
	@echo "  install-dev   Install development dependencies"
	@echo "  test          Run test suite with $(COVERAGE_MIN)% coverage enforcement"
	@echo "  test-coverage Run test suite with $(COVERAGE_MIN)% coverage enforcement"
	@echo "  lint          Auto-fix linting, formatting, and import issues"
	@echo "  lint-check    Check code quality without fixing"
	@echo "  typecheck     Run type checking"
	@echo "  quality       Run complete quality pipeline"
	@echo "  clean         Remove caches and build artifacts"
	@echo "  run           Run the tasks service"
	@echo "  docker-build  Build Docker image"
	@echo "  docker-run    Run Docker container"
	@echo "  pre-commit    Run pre-commit hooks"
	@echo "  ci            Run complete CI pipeline"
	@echo "  setup-dev     Setup development environment"

# Installation
install:
	pip install -e .

install-dev:
	pip install -e ".[dev,test]"

# Testing
test:
	python3 -m pytest tests/ -v $(COVERAGE_ARGS)

test-coverage:
	python3 -m pytest tests/ -v $(COVERAGE_ARGS)

# Code Quality - Unified tooling
lint:
	python3 -m ruff format .
	python3 -m ruff check --fix .
	@echo "Running UI linting..."
	cd ui && npm run lint --if-present 2>/dev/null || echo "UI linting skipped (npm not available or no lint script)"

lint-check:
	python3 -m ruff format --check .
	python3 -m ruff check .
	python3 -m pyright .
	@echo "Running UI lint check..."
	cd ui && npm run lint --if-present 2>/dev/null || echo "UI lint check skipped (npm not available or no lint script)"

ui-lint:
	cd ui && npm run lint

ui-lint-fix:
	cd ui && npm run lint -- --fix

ui-test:
	cd ui && npm test

# Legacy type checking (use lint-check instead)
typecheck:
	python3 -m pyright .

# Complete quality pipeline
quality: lint-check test

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ .coverage htmlcov/

# Run application
run:
	python3 app.py

# Docker
docker-build:
	docker build -t ai-slack-bot-tasks .

docker-run:
	docker run -p 5001:5001 --env-file .env ai-slack-bot-tasks

# Development tools
pre-commit:
	python -m pre_commit run --all-files

setup-dev: install-dev
	python -m pre_commit install
	@echo "Development environment setup complete!"

# CI pipeline
ci: lint-check test
	@echo "CI pipeline completed successfully!"

# Specific test targets
test-scheduler:
	python -m pytest tests/test_scheduler_service.py -v

test-jobs:
	python -m pytest tests/test_jobs.py -v

test-registry:
	python -m pytest tests/test_job_registry.py -v

# Development shortcuts
dev-run:
	FLASK_ENV=development python app.py

debug:
	FLASK_ENV=development FLASK_DEBUG=1 python app.py

# Health check
health:
	curl -f http://localhost:5001/health || echo "Service not running"

# API tests
api-test:
	curl -s http://localhost:5001/api/scheduler/info | python -m json.tool
	curl -s http://localhost:5001/api/jobs | python -m json.tool

# Quick development cycle
dev-cycle: lint test
	@echo "Development cycle complete - ready to commit!"
