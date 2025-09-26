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

# Find Python command with ruff installed (for linting) - prioritize venv
PYTHON_LINT := $(shell \
    if [ -f "$(VENV)/bin/python" ] && $(VENV)/bin/python -m ruff --version >/dev/null 2>&1; then \
        echo "$(VENV)/bin/python"; \
    else \
        for cmd in python3.11 python3 python; do \
            if command -v $$cmd >/dev/null 2>&1 && $$cmd -m ruff --version >/dev/null 2>&1; then \
                echo $$cmd; break; \
            fi; \
        done; \
    fi)

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
RESET := \033[0m

.PHONY: help install install-test install-dev check-env start-redis run test test-coverage test-file test-integration test-unit test-ingest ingest ingest-check-es lint lint-check typecheck quality docker-build-bot docker-build docker-run docker-monitor docker-prod docker-stop clean clean-all setup-dev ci pre-commit security python-version health-ui tasks-ui start start-with-tasks start-tasks-only restart db-start db-stop db-migrate db-upgrade db-downgrade db-revision db-reset db-status

help:
	@echo "$(BLUE)AI Slack Bot - Available Make Targets:$(RESET)"
	@echo ""
	@echo "$(RED)🚀 ONE COMMAND TO RULE THEM ALL:$(RESET)"
	@echo "  $(GREEN)make start$(RESET)       🔥 Build everything and run full stack with monitoring (recommended)"
	@echo ""
	@echo "$(GREEN)Service Management:$(RESET)"
	@echo "  start-core       🤖 Core services only (no monitoring)"
	@echo "  restart          🔄 Restart the full stack (stop + start)"
	@echo "  stop             🛑 Stop everything"
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
	@echo "  ingest          Run document ingestion (use ARGS='--folder-id YOUR_ID')"
	@echo "  lint            Run linting and formatting"
	@echo "  lint-check      Check linting without fixing"
	@echo "  typecheck       Run type checking"
	@echo "  quality         Run all quality checks"
	@echo ""
	@echo "$(GREEN)Docker:$(RESET)"
	@echo "  docker-build-bot Build single bot Docker image"
	@echo "  docker-build    Build all Docker images in stack"
	@echo "  docker-run      Run Docker container with .env"
	@echo "  docker-monitor  🔍 Run monitoring stack (Prometheus + Grafana)"
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
	@echo ""
	@echo "$(GREEN)UI Components:$(RESET)"
	@echo "  health-ui       Build React health dashboard UI"
	@echo "  tasks-ui        Build React tasks dashboard UI"
	@echo ""
	@echo "$(GREEN)Database Management:$(RESET)"
	@echo "  db-start        🐳 Start MySQL databases in Docker"
	@echo "  db-stop         🛑 Stop MySQL databases"
	@echo "  db-migrate      📋 Generate new migration files"
	@echo "  db-upgrade      ⬆️  Apply pending migrations"
	@echo "  db-downgrade    ⬇️  Rollback last migration"
	@echo "  db-reset        🔄 Reset databases (WARNING: destroys data)"
	@echo "  db-status       📊 Show migration status"

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

# Start Redis service (required for conversation caching) - internal target
start-redis:
	@echo "$(BLUE)Starting Redis service...$(RESET)"
	@if command -v brew >/dev/null 2>&1; then \
		brew services start redis || echo "$(YELLOW)Redis may already be running$(RESET)"; \
	elif command -v systemctl >/dev/null 2>&1; then \
		sudo systemctl start redis || echo "$(YELLOW)Redis may already be running$(RESET)"; \
	elif command -v service >/dev/null 2>&1; then \
		sudo service redis-server start || echo "$(YELLOW)Redis may already be running$(RESET)"; \
	else \
		echo "$(YELLOW)Please start Redis manually: redis-server$(RESET)"; \
	fi
	@echo "$(GREEN)✅ Redis service started$(RESET)"

run: check-env db-start start-redis
	@echo "$(GREEN)🤖 Starting AI Slack Bot...$(RESET)"
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

# Check if Elasticsearch is running and healthy
ingest-check-es:
	@echo "$(BLUE)Checking if Elasticsearch is available...$(RESET)"
	@if curl -sf http://localhost:9200/_cluster/health > /dev/null 2>&1; then \
		echo "$(GREEN)✅ Elasticsearch is running and healthy$(RESET)"; \
	else \
		echo "$(YELLOW)⚠️  Elasticsearch not running. Starting...$(RESET)"; \
		docker compose -f docker-compose.elasticsearch.yml up -d; \
		echo "$(BLUE)Waiting for Elasticsearch to be ready...$(RESET)"; \
		timeout=60; \
		while [ $$timeout -gt 0 ]; do \
			if curl -sf http://localhost:9200/_cluster/health > /dev/null 2>&1; then \
				echo "$(GREEN)✅ Elasticsearch is now healthy$(RESET)"; \
				break; \
			fi; \
			echo "$(YELLOW)Waiting... ($$timeout seconds remaining)$(RESET)"; \
			sleep 2; \
			timeout=$$((timeout-2)); \
		done; \
		if [ $$timeout -le 0 ]; then \
			echo "$(RED)❌ Elasticsearch failed to start within 60 seconds$(RESET)"; \
			exit 1; \
		fi; \
	fi

ingest: $(VENV) ingest-check-es
	@echo "$(BLUE)Running document ingestion...$(RESET)"
	@if [ -z "$(ARGS)" ]; then \
		echo "$(RED)❌ Error: Please provide arguments. Example:$(RESET)"; \
		echo "   make ingest ARGS='--folder-id YOUR_GOOGLE_DRIVE_FOLDER_ID'"; \
		echo "   make ingest ARGS='--folder-id ABC123 --metadata \"{\\\"department\\\": \\\"engineering\\\"}'"; \
		exit 1; \
	fi
	@echo "$(GREEN)🚀 Starting ingestion with Elasticsearch dependency handled...$(RESET)"
	cd $(PROJECT_ROOT_DIR)ingest && $(PYTHON) main.py $(ARGS)
	@echo "$(GREEN)✅ Ingestion completed!$(RESET)"

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

docker-build-bot:
	docker build -f $(BOT_DIR)/Dockerfile -t $(IMAGE) $(BOT_DIR)

docker-run: check-env
	docker run --rm --env-file $(ENV_FILE) --name $(IMAGE) $(IMAGE)

docker-monitor: check-env
	@echo "$(BLUE)🔍 Starting monitoring stack (Prometheus + Grafana + AlertManager)...$(RESET)"
	cd $(PROJECT_ROOT_DIR) && docker compose -f docker-compose.monitoring.yml up -d
	@echo "$(GREEN)✅ Monitoring stack started! Access points:$(RESET)"
	@echo "$(BLUE)  - Grafana Dashboard: http://localhost:3000 (admin/admin)$(RESET)"
	@echo "$(BLUE)  - Prometheus: http://localhost:9090$(RESET)"
	@echo "$(BLUE)  - AlertManager: http://localhost:9093$(RESET)"

docker-prod:
	cd $(PROJECT_ROOT_DIR) && docker compose -f docker-compose.prod.yml up -d

docker-stop:
	cd $(PROJECT_ROOT_DIR) && docker compose -f docker-compose.elasticsearch.yml down
	cd $(PROJECT_ROOT_DIR) && docker compose -f docker-compose.mysql.yml down
	cd $(PROJECT_ROOT_DIR) && docker compose -f docker-compose.monitoring.yml down

# Full Docker Stack Commands
docker-up: check-env
	@echo "$(BLUE)🐳 Starting full InsightMesh stack...$(RESET)"
	cd $(PROJECT_ROOT_DIR) && docker compose up -d
	@echo "$(GREEN)✅ Core stack started! Services available at:$(RESET)"
	@echo "$(BLUE)  - 🤖 Bot Health Dashboard: http://localhost:$${HEALTH_PORT:-8080}$(RESET)"
	@echo "$(BLUE)  - 📅 Task Scheduler: http://localhost:$${TASKS_PORT:-5001}$(RESET)"
	@echo "$(BLUE)  - 🗄️  Database Admin: http://localhost:8081$(RESET)"
	@echo "$(BLUE)  - 🔍 Elasticsearch: http://localhost:9200$(RESET)"
	@echo "$(BLUE)  - 📊 Metrics Endpoint: http://localhost:$${HEALTH_PORT:-8080}/metrics$(RESET)"
	@echo ""
	@echo "$(YELLOW)💡 For monitoring stack: make docker-monitor$(RESET)"
	@echo "$(YELLOW)💡 For everything at once: make start$(RESET)"

docker-down:
	@echo "$(BLUE)🐳 Stopping full InsightMesh stack...$(RESET)"
	cd $(PROJECT_ROOT_DIR) && docker compose down
	@echo "$(GREEN)✅ Stack stopped!$(RESET)"

docker-logs:
	cd $(PROJECT_ROOT_DIR) && docker compose logs -f

docker-restart: docker-down docker-up

docker-build: health-ui tasks-ui
	@echo "$(BLUE)🔨 Building Docker images...$(RESET)"
	cd $(PROJECT_ROOT_DIR) && docker compose build
	@echo "$(GREEN)✅ Images built!$(RESET)"

# Main stop command - stops everything
stop: docker-down
	@echo "$(BLUE)🛑 Stopping monitoring stack...$(RESET)"
	cd $(PROJECT_ROOT_DIR) && docker compose -f docker-compose.monitoring.yml down
	@echo "$(GREEN)✅ All services stopped!$(RESET)"

# Restart command - stop everything and start the full stack
restart: stop start
	@echo "$(GREEN)🔄 ================================$(RESET)"
	@echo "$(GREEN)✅ RESTART COMPLETED SUCCESSFULLY!$(RESET)"
	@echo "$(GREEN)🔄 ================================$(RESET)"

setup-dev: install-dev
	@if [ ! -f $(PROJECT_ROOT_DIR).env.test ]; then cp $(BOT_DIR)/tests/.env.test $(PROJECT_ROOT_DIR).env.test; fi
	cd $(PROJECT_ROOT_DIR) && pre-commit install
	@echo "✅ Development environment set up!"
	@echo "✅ Pre-commit hooks installed!"
	@echo "Run 'make test' to run tests"

health-ui:
	@echo "$(BLUE)Building React health dashboard...$(RESET)"
	cd $(BOT_DIR)/health_ui && npm install && npm run build
	@echo "$(GREEN)✅ Health UI built successfully!$(RESET)"
	@echo "$(BLUE)🌐 Access at: http://localhost:$${HEALTH_PORT:-8080}/ui$(RESET)"

tasks-ui:
	@echo "$(BLUE)Building React tasks dashboard...$(RESET)"
	cd $(PROJECT_ROOT_DIR)/tasks/ui && npm install && npm run build
	@echo "$(GREEN)✅ Tasks UI built successfully!$(RESET)"
	@echo "$(BLUE)🌐 Access at: http://localhost:$${TASKS_PORT:-5001}$(RESET)"

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
	rm -rf $(BOT_DIR)/health_ui/node_modules
	rm -rf $(BOT_DIR)/health_ui/dist
	@echo "$(GREEN)Cleanup completed$(RESET)"

clean-all: clean
	@echo "$(YELLOW)Removing virtual environment...$(RESET)"
	rm -rf $(VENV)
	@echo "$(GREEN)Virtual environment removed$(RESET)"

python-version: $(VENV)
	@echo "$(BLUE)Python version information:$(RESET)"
	@$(PYTHON) --version
	@$(PIP) --version

# 🚀 THE ONE COMMAND TO RULE THEM ALL
# Main start command - includes everything (core + monitoring)
start: docker-build docker-up docker-monitor
	@echo "$(GREEN)🔥 ================================$(RESET)"
	@echo "$(GREEN)🚀 FULL STACK STARTED SUCCESSFULLY!$(RESET)"
	@echo "$(GREEN)🔥 ================================$(RESET)"
	@echo ""
	@echo "$(BLUE)📊 Main Services:$(RESET)"
	@echo "$(BLUE)  - Bot Health Dashboard: http://localhost:$${HEALTH_PORT:-8080}$(RESET)"
	@echo "$(BLUE)  - Task Scheduler: http://localhost:$${TASKS_PORT:-5001}$(RESET)"
	@echo "$(BLUE)  - Database Admin: http://localhost:8081$(RESET)"
	@echo ""
	@echo "$(YELLOW)🔍 Monitoring Stack:$(RESET)"
	@echo "$(YELLOW)  - Grafana Dashboard: http://localhost:3000 (admin/admin)$(RESET)"
	@echo "$(YELLOW)  - Prometheus: http://localhost:9090$(RESET)"
	@echo "$(YELLOW)  - AlertManager: http://localhost:9093$(RESET)"
	@echo ""
	@echo "$(GREEN)🎉 All services are running! Check the health dashboard for RAG metrics.$(RESET)"

# Core services only (without monitoring)
start-core: docker-build docker-up

# Docker-based start (same as start)
start-docker: start

# Legacy local start
start-local: install-dev health-ui check-env db-start start-redis
	@echo "$(GREEN)🎯 ================================$(RESET)"
	@echo "$(GREEN)🚀 STARTING AI SLACK BOT WITH FULL STACK$(RESET)"
	@echo "$(GREEN)🎯 ================================$(RESET)"
	@echo ""
	@echo "$(BLUE)✅ Dependencies installed$(RESET)"
	@echo "$(BLUE)✅ Health UI built and ready$(RESET)"
	@echo "$(BLUE)✅ Environment validated$(RESET)"
	@echo "$(BLUE)✅ MySQL databases started$(RESET)"
	@echo "$(BLUE)✅ Redis service started$(RESET)"
	@echo ""
	@echo "$(YELLOW)🌐 Access points:$(RESET)"
	@echo "$(YELLOW)   Bot Health Dashboard: http://localhost:$${HEALTH_PORT:-8080}/ui$(RESET)"
	@echo "$(YELLOW)   Task Scheduler:       http://localhost:$${TASKS_PORT:-5001}$(RESET)"
	@echo "$(YELLOW)   Database Admin:       http://localhost:8081$(RESET)"
	@echo "$(YELLOW)   Prometheus Metrics:   http://localhost:$${HEALTH_PORT:-8080}/prometheus$(RESET)"
	@echo "$(YELLOW)   API Endpoints:        http://localhost:$${HEALTH_PORT:-8080}/api/*$(RESET)"
	@echo ""
	@echo "$(GREEN)🤖 Starting the AI Slack Bot with Task Scheduler...$(RESET)"
	@echo "$(GREEN)Press Ctrl+C to stop both services$(RESET)"
	@echo ""
	@$(MAKE) start-with-tasks

# Start both bot and tasks service in parallel
start-with-tasks:
	@echo "$(BLUE)Starting Task Scheduler in background...$(RESET)"
	@cd tasks && $(PYTHON) app.py & \
	TASKS_PID=$$!; \
	echo "$(BLUE)Task Scheduler started (PID: $$TASKS_PID)$(RESET)"; \
	echo "$(BLUE)Starting AI Slack Bot...$(RESET)"; \
	cd $(BOT_DIR) && $(PYTHON) app.py; \
	echo "$(YELLOW)Stopping Task Scheduler...$(RESET)"; \
	kill $$TASKS_PID 2>/dev/null || true


# Start only the tasks service
start-tasks-only:
	@echo "$(GREEN)📅 Starting Task Scheduler only...$(RESET)"
	cd tasks && $(PYTHON) app.py

# ===== DATABASE MANAGEMENT =====

# Start MySQL databases in Docker
db-start:
	@echo "$(BLUE)🐳 Starting MySQL databases...$(RESET)"
	docker compose -f docker-compose.mysql.yml up -d
	@echo "$(BLUE)Waiting for MySQL to be ready...$(RESET)"
	@timeout=60; \
	while [ $$timeout -gt 0 ]; do \
		if docker exec insightmesh-mysql mysqladmin ping -h localhost --silent; then \
			echo "$(GREEN)✅ MySQL is ready!$(RESET)"; \
			break; \
		fi; \
		echo "$(YELLOW)Waiting... ($$timeout seconds remaining)$(RESET)"; \
		sleep 2; \
		timeout=$$((timeout-2)); \
	done; \
	if [ $$timeout -le 0 ]; then \
		echo "$(RED)❌ MySQL failed to start within 60 seconds$(RESET)"; \
		exit 1; \
	fi
	@echo "$(GREEN)🎉 MySQL databases are running!$(RESET)"
	@echo "$(YELLOW)📊 phpMyAdmin available at: http://localhost:8081$(RESET)"

# Stop MySQL databases
db-stop:
	@echo "$(YELLOW)🛑 Stopping MySQL databases...$(RESET)"
	docker compose -f docker-compose.mysql.yml down
	@echo "$(GREEN)✅ MySQL databases stopped$(RESET)"

# Generate new migration files
db-migrate: $(VENV)
	@echo "$(BLUE)📋 Generating migration files...$(RESET)"
	@read -p "Enter migration message: " message; \
	echo "$(BLUE)Generating bot service migration...$(RESET)"; \
	cd $(BOT_DIR) && $(PYTHON) -m alembic revision --autogenerate -m "$$message"; \
	echo "$(BLUE)Generating tasks service migration...$(RESET)"; \
	cd $(PROJECT_ROOT_DIR)tasks && $(PYTHON) -m alembic revision --autogenerate -m "$$message"
	@echo "$(GREEN)✅ Migration files generated!$(RESET)"

# Apply pending migrations
db-upgrade: $(VENV) db-start
	@echo "$(BLUE)⬆️  Applying migrations...$(RESET)"
	@echo "$(BLUE)Upgrading bot database...$(RESET)"
	cd $(BOT_DIR) && $(PYTHON) -m alembic upgrade head
	@echo "$(BLUE)Upgrading tasks database...$(RESET)"
	cd $(PROJECT_ROOT_DIR)tasks && $(PYTHON) -m alembic upgrade head
	@echo "$(BLUE)Running Elasticsearch index migrations...$(RESET)"
	cd $(PROJECT_ROOT_DIR)ingest && $(PYTHON) -c "import asyncio; from services.elasticsearch_migrations import run_elasticsearch_migrations; import os; asyncio.run(run_elasticsearch_migrations(os.getenv('VECTOR_URL', 'http://localhost:9200'), os.getenv('VECTOR_COLLECTION_NAME', 'insightmesh-knowledge-base'), 3072))" || echo "$(YELLOW)⚠️  Elasticsearch migrations skipped (service may not be running)$(RESET)"
	@echo "$(GREEN)✅ All migrations applied successfully!$(RESET)"

# Rollback last migration
db-downgrade: $(VENV)
	@echo "$(YELLOW)⬇️  Rolling back last migration...$(RESET)"
	@echo "$(YELLOW)Rolling back bot database...$(RESET)"
	cd $(BOT_DIR) && $(PYTHON) -m alembic downgrade -1
	@echo "$(YELLOW)Rolling back tasks database...$(RESET)"
	cd $(PROJECT_ROOT_DIR)tasks && $(PYTHON) -m alembic downgrade -1
	@echo "$(GREEN)✅ Rollback completed$(RESET)"

# Reset databases (WARNING: destroys data)
db-reset: db-stop
	@echo "$(RED)🚨 WARNING: This will destroy all data!$(RESET)"
	@read -p "Are you sure? Type 'yes' to continue: " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		echo "$(YELLOW)🔄 Resetting databases...$(RESET)"; \
		docker volume rm ai-slack-bot_mysql_data 2>/dev/null || true; \
		$(MAKE) db-start; \
		$(MAKE) db-upgrade; \
		echo "$(GREEN)✅ Databases reset and migrations applied$(RESET)"; \
	else \
		echo "$(BLUE)❌ Reset cancelled$(RESET)"; \
	fi

# Show migration status
db-status: $(VENV)
	@echo "$(BLUE)📊 Database migration status:$(RESET)"
	@echo ""
	@echo "$(YELLOW)Bot Database (bot):$(RESET)"
	@cd $(BOT_DIR) && $(PYTHON) -m alembic current -v || echo "$(RED)No migrations applied$(RESET)"
	@echo ""
	@echo "$(YELLOW)Tasks Database (task):$(RESET)"
	@cd $(PROJECT_ROOT_DIR)tasks && $(PYTHON) -m alembic current -v || echo "$(RED)No migrations applied$(RESET)"
	@echo ""
	@echo "$(BLUE)Pending migrations:$(RESET)"
	@cd $(BOT_DIR) && $(PYTHON) -m alembic show head || echo "$(YELLOW)No migrations found$(RESET)"
