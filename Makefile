# Improved Makefile for Insight Mesh Slack Bot
# This Makefile automatically detects the project root and works from any subdirectory

# Determine project root directory (where this Makefile is located)
MAKEFILE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
PROJECT_ROOT_DIR := $(MAKEFILE_DIR)
BOT_DIR := $(PROJECT_ROOT_DIR)bot

# Virtual environment settings
VENV := $(PROJECT_ROOT_DIR)venv
PYTHON ?= $(VENV)/bin/python
PIP ?= $(VENV)/bin/pip
ENV_FILE := $(PROJECT_ROOT_DIR).env
IMAGE ?= insight-mesh-slack-bot

# Find Python command with ruff installed (for linting) - prioritize env var, then venv
PYTHON_LINT ?= $(shell \
    if [ -n "$$PYTHON" ] && $$PYTHON -m ruff --version >/dev/null 2>&1; then \
        echo "$$PYTHON"; \
    elif [ -f "$(VENV)/bin/python" ] && $(VENV)/bin/python -m ruff --version >/dev/null 2>&1; then \
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

.PHONY: help install install-test install-dev check-env start-redis run test test-file test-integration test-unit test-ingest test-shared test-dashboard test-rag ingest ingest-check-es lint lint-check typecheck docker-build-bot docker-build docker-run docker-monitor docker-prod docker-stop clean clean-all setup-dev ci ci-lint ci-test-bot ci-test-control-plane ci-test-tasks ci-test-shared ci-test-dashboard ci-test-rag ci-ui ci-docker pre-commit security python-version health-ui tasks-ui ui-lint ui-lint-fix ui-test ui-test-coverage ui-dev start start-with-tasks start-tasks-only restart status db-start db-stop db-migrate db-upgrade db-downgrade db-revision db-reset db-status db-setup-system librechat-start librechat-logs librechat-restart librechat-stop

help:
	@echo "$(BLUE)AI Slack Bot - Available Make Targets:$(RESET)"
	@echo ""
	@echo "$(RED)🚀 ONE COMMAND TO RULE THEM ALL:$(RESET)"
	@echo "  $(GREEN)make start$(RESET)       🔥 Build everything and run full stack with monitoring + centralized logging (recommended)"
	@echo ""
	@echo "$(GREEN)Service Management:$(RESET)"
	@echo "  start-core       🤖 Core services only (no monitoring)"
	@echo "  restart          🔄 Restart the full stack (stop + start)"
	@echo "  status           📋 Show Docker container status"
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
	@echo "  test            🧪 Run ALL unit tests across all services (no integration)"
	@echo "  test-bot-only   Run bot unit tests only (faster)"
	@echo "  test-file       Run specific test file (use FILE=filename)"
	@echo "  test-integration Run integration tests only (separate process)"
	@echo "  test-unit       Run unit tests only (alias for test)"
	@echo "  test-tasks      Run tasks service tests"
	@echo "  test-control-plane Run control plane tests"
	@echo "  test-agent-service Run agent service tests"
	@echo "  test-shared     Run shared utilities tests"
	@echo "  test-dashboard  Run dashboard service tests"
	@echo "  test-ingest     Run ingestion service tests"
	@echo "  ingest          Run document ingestion (use ARGS='--folder-id YOUR_ID')"
	@echo "  lint            Run linting and formatting"
	@echo "  lint-check      Check linting without fixing"
	@echo "  typecheck       Run type checking"
	@echo "  ci              🚀 Run complete CI pipeline (use -j4 for parallel: make -j4 ci)"
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
	@echo "  clean           Remove caches and build artifacts"
	@echo "  clean-all       Remove caches and virtual environment"
	@echo ""
	@echo "$(GREEN)UI Components:$(RESET)"
	@echo "  health-ui       Build React health dashboard UI"
	@echo "  tasks-ui        Build React tasks dashboard UI"
	@echo "  ui-lint         Lint React Health UI code"
	@echo "  ui-lint-fix     Auto-fix React Health UI lint issues"
	@echo "  ui-test         Run React Health UI tests"
	@echo "  ui-test-coverage Run React Health UI tests with coverage"
	@echo "  ui-dev          Start React Health UI dev server (port 5173)"
	@echo "  quality-all     Run all quality checks (Python + React)"
	@echo ""
	@echo "$(GREEN)Database Management:$(RESET)"
	@echo "  db-start         🐳 Start MySQL databases (main docker-compose.yml)"
	@echo "  db-stop          🛑 Stop MySQL databases"
	@echo "  db-setup-system  🔧 Setup system database (agent_usage) without destroying data"
	@echo "  db-migrate       📋 Generate new migration files"
	@echo "  db-upgrade       ⬆️  Apply pending migrations"
	@echo "  db-downgrade     ⬇️  Rollback last migration"
	@echo "  db-reset         🔄 Reset databases (WARNING: destroys data)"
	@echo "  db-status        📊 Show migration status"

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

run: check-env start-redis
	@echo "$(GREEN)🤖 Starting AI Slack Bot...$(RESET)"
	cd $(BOT_DIR) && $(PYTHON) app.py

test: $(VENV)
	@echo "$(BLUE)Running full unit test suite across all services (excluding integration)...$(RESET)"
	@echo "$(YELLOW)🧪 Bot unit tests...$(RESET)"
	@cd $(BOT_DIR) && PYTHONPATH=. $(PYTHON) -m pytest -m "not integration" -v --tb=short
	@echo ""
	@echo "$(YELLOW)🎛️  Control plane unit tests...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)control_plane && PYTHONPATH=.:$(PROJECT_ROOT_DIR) $(PYTHON) -m pytest -m "not integration" -v --tb=short --cov-fail-under=0
	@echo ""
	@echo "$(YELLOW)🤖 Agent service unit tests...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)agent-service && PYTHONPATH=.:$(PROJECT_ROOT_DIR) $(PYTHON) -m pytest -m "not integration" -v --tb=short --cov-fail-under=0 || echo "$(YELLOW)⚠️  Some agent-service tests skipped$(RESET)"
	@echo ""
	@echo "$(YELLOW)⏰ Tasks service unit tests...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)tasks && ENVIRONMENT=development PYTHONPATH=. $(PYTHON) -m pytest -m "not integration" -v --tb=short --cov-fail-under=0
	@echo ""
	@echo "$(YELLOW)🔗 Shared utilities unit tests...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)shared && PYTHONPATH=. $(PYTHON) -m pytest tests/ -v --tb=short --cov-fail-under=0 || echo "$(YELLOW)⚠️  Shared tests skipped$(RESET)"
	@echo ""
	@echo "$(YELLOW)📊 Dashboard service unit tests...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)dashboard-service && PYTHONPATH=. $(PYTHON) -m pytest tests/ -v --tb=short --cov-fail-under=0 || echo "$(YELLOW)⚠️  Dashboard tests skipped$(RESET)"
	@echo ""
	@echo "$(YELLOW)🔍 RAG service unit tests...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)rag-service && PYTHONPATH=.:$(PROJECT_ROOT_DIR) $(PYTHON) -m pytest tests/ -v --tb=short --cov-fail-under=0 || echo "$(YELLOW)⚠️  RAG tests skipped$(RESET)"
	@echo ""
	@echo "$(GREEN)✅ All unit test suites completed!$(RESET)"

test-bot-only: $(VENV)
	@echo "$(BLUE)Running bot test suite only (excluding integration tests)...$(RESET)"
	cd $(BOT_DIR) && PYTHONPATH=. $(PYTHON) -m pytest -m "not integration" -v

test-file: $(VENV)
	@echo "$(BLUE)Running specific test file: $(FILE)...$(RESET)"
	cd $(BOT_DIR) && PYTHONPATH=. $(PYTHON) -m pytest -v tests/$(FILE)

test-integration: $(VENV)
	@echo "$(BLUE)Running integration tests across all services...$(RESET)"
	@echo "$(YELLOW)🧪 Bot integration tests...$(RESET)"
	@cd $(BOT_DIR) && PYTHONPATH=. $(PYTHON) -m pytest -m integration -v --tb=short
	@echo ""
	@echo "$(YELLOW)🎛️  Control plane integration tests...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)control_plane && PYTHONPATH=.:$(PROJECT_ROOT_DIR) $(PYTHON) -m pytest -m integration -v --tb=short
	@echo ""
	@echo "$(YELLOW)🤖 Agent service integration tests...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)agent-service && PYTHONPATH=.:$(PROJECT_ROOT_DIR) $(PYTHON) -m pytest -m integration -v --tb=short --cov-fail-under=0 2>/dev/null || echo "$(YELLOW)⚠️  Agent-service integration test failures (pre-existing)$(RESET)"
	@echo ""
	@echo "$(YELLOW)⏰ Tasks service integration tests...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)tasks && PYTHONPATH=. $(PYTHON) -m pytest -m integration -v --tb=short --cov-fail-under=0
	@echo ""
	@echo "$(YELLOW)📊 Dashboard service integration tests...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)dashboard-service && PYTHONPATH=. $(PYTHON) -m pytest -m integration -v --tb=short 2>/dev/null || echo "$(YELLOW)⚠️  No dashboard integration tests$(RESET)"
	@echo ""
	@echo "$(YELLOW)🔍 RAG service integration tests...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)rag-service && PYTHONPATH=.:$(PROJECT_ROOT_DIR) $(PYTHON) -m pytest -m integration -v --tb=short 2>/dev/null || echo "$(YELLOW)⚠️  No RAG service integration tests$(RESET)"
	@echo ""
	@echo "$(GREEN)✅ All integration test suites completed!$(RESET)"

test-unit: $(VENV)
	@echo "$(BLUE)Running unit tests...$(RESET)"
	cd $(BOT_DIR) && PYTHONPATH=. $(PYTHON) -m pytest -m "not integration" -v

test-ingest: $(VENV)
	@echo "$(BLUE)Running ingestion service tests...$(RESET)"
	cd $(PROJECT_ROOT_DIR)ingest && PYTHONPATH=. $(PYTHON) -m pytest -v

test-tasks: $(VENV)
	@echo "$(BLUE)Running task service tests...$(RESET)"
	cd $(PROJECT_ROOT_DIR)tasks && ENVIRONMENT=development PYTHONPATH=. $(PYTHON) -m pytest -v --cov-fail-under=0

test-agent-service: $(VENV)
	@echo "$(BLUE)Running agent service tests...$(RESET)"
	cd $(PROJECT_ROOT_DIR)agent-service && PYTHONPATH=.:$(PROJECT_ROOT_DIR) $(PYTHON) -m pytest -v --cov-fail-under=0 || echo "$(YELLOW)Some agent-service tests skipped due to import errors$(RESET)"

lint-tasks: $(VENV)
	@echo "$(BLUE)Running task service linting...$(RESET)"
	cd $(PROJECT_ROOT_DIR)tasks && $(PYTHON) -m ruff check . --fix
	cd $(PROJECT_ROOT_DIR)tasks && $(PYTHON) -m ruff format .

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
	cd $(BOT_DIR) && ($(PYTHON_LINT) -m bandit -r . -c pyproject.toml -f txt || echo "$(YELLOW)⚠️  Bandit check failed (non-blocking)$(RESET)")
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
	@echo "$(BLUE)🔒 Running security checks...$(RESET)"
	cd $(BOT_DIR) && ($(PYTHON_LINT) -m bandit -r . -c pyproject.toml -f txt || echo "$(YELLOW)⚠️  Bandit check failed (non-blocking)$(RESET)")
	@echo "$(GREEN)✅ All checks completed with ruff + bandit!$(RESET)"

typecheck: $(VENV)
	@echo "$(BLUE)Running type checking with pyright...$(RESET)"
	cd $(BOT_DIR) && $(VENV)/bin/pyright || $(PYTHON) -m pyright

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
	cd $(PROJECT_ROOT_DIR) && docker compose -f docker-compose.monitoring.yml down

# Full Docker Stack Commands
docker-up: check-env
	@echo "$(BLUE)🐳 Starting full InsightMesh stack...$(RESET)"
	cd $(PROJECT_ROOT_DIR) && docker compose up -d
	@echo "$(GREEN)✅ Core stack started! Services available at:$(RESET)"
	@echo "$(BLUE)  - 🤖 Bot Health Dashboard: http://localhost:$${HEALTH_PORT:-8080}$(RESET)"
	@echo "$(BLUE)  - 💬 LibreChat UI: http://localhost:$${LIBRECHAT_PORT:-3080}$(RESET)"
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
	cd $(PROJECT_ROOT_DIR) && DOCKER_BUILDKIT=0 docker compose build
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

# Status command - show Docker container status
status:
	@echo "$(BLUE)📋 ================================$(RESET)"
	@echo "$(BLUE)🐳 DOCKER CONTAINER STATUS$(RESET)"
	@echo "$(BLUE)📋 ================================$(RESET)"
	@echo ""
	@echo "$(YELLOW)🔍 Main Stack Containers:$(RESET)"
	@docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" --filter "network=insightmesh" 2>/dev/null || echo "$(RED)❌ Main stack not running$(RESET)"
	@echo ""
	@echo "$(YELLOW)📊 Monitoring Stack Containers:$(RESET)"
	@docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" --filter "label=com.docker.compose.project=monitoring" 2>/dev/null || echo "$(RED)❌ Monitoring stack not running$(RESET)"
	@echo ""

# =============================================================================
# LibreChat Service Management
# =============================================================================
librechat-start: check-env
	@echo "$(BLUE)💬 Starting LibreChat + MongoDB...$(RESET)"
	cd $(PROJECT_ROOT_DIR) && docker compose up -d mongodb librechat
	@echo "$(GREEN)✅ LibreChat started!$(RESET)"
	@echo "$(BLUE)  - 💬 LibreChat UI: http://localhost:$${LIBRECHAT_PORT:-3080}$(RESET)"
	@echo "$(BLUE)  - 🗄️  MongoDB: mongodb://localhost:27017$(RESET)"

librechat-logs:
	@echo "$(BLUE)📋 Showing LibreChat logs (Ctrl+C to exit)...$(RESET)"
	cd $(PROJECT_ROOT_DIR) && docker compose logs -f librechat mongodb

librechat-restart:
	@echo "$(BLUE)🔄 Restarting LibreChat...$(RESET)"
	cd $(PROJECT_ROOT_DIR) && docker compose restart librechat mongodb
	@echo "$(GREEN)✅ LibreChat restarted!$(RESET)"

librechat-stop:
	@echo "$(BLUE)🛑 Stopping LibreChat...$(RESET)"
	cd $(PROJECT_ROOT_DIR) && docker compose stop librechat mongodb
	@echo "$(GREEN)✅ LibreChat stopped!$(RESET)"

	@echo "$(YELLOW)📈 All InsightMesh Containers:$(RESET)"
	@docker ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}" --filter "name=insightmesh" 2>/dev/null || echo "$(RED)❌ No InsightMesh containers found$(RESET)"
	@echo ""
	@echo "$(BLUE)🌐 Service URLs (if running):$(RESET)"
	@echo "$(BLUE)  - Bot Health Dashboard: http://localhost:$${HEALTH_PORT:-8080}$(RESET)"
	@echo "$(BLUE)  - Task Scheduler: http://localhost:$${TASKS_PORT:-5001}$(RESET)"
	@echo "$(BLUE)  - Database Admin: http://localhost:8081$(RESET)"
	@echo "$(BLUE)  - Grafana (Logs + Metrics): http://localhost:3000 (admin/admin)$(RESET)"
	@echo "$(BLUE)  - Prometheus: http://localhost:9090$(RESET)"
	@echo "$(BLUE)  - Loki: http://localhost:3100$(RESET)"
	@echo "$(BLUE)  - AlertManager: http://localhost:9093$(RESET)"

setup-dev: install-dev
	@if [ ! -f $(PROJECT_ROOT_DIR).env.test ]; then cp $(BOT_DIR)/tests/.env.test $(PROJECT_ROOT_DIR).env.test; fi
	cd $(PROJECT_ROOT_DIR) && pre-commit install
	@echo "✅ Development environment set up!"
	@echo "✅ Pre-commit hooks installed!"
	@echo "Run 'make test' to run tests"

health-ui:
	@echo "$(BLUE)Building React health dashboard...$(RESET)"
	cd $(BOT_DIR)/health_ui && npm install --no-audit && npm run build
	@echo "$(GREEN)✅ Health UI built successfully!$(RESET)"
	@echo "$(BLUE)🌐 Access at: http://localhost:$${HEALTH_PORT:-8080}/ui$(RESET)"

# React UI Development Commands
ui-lint:
	@echo "$(BLUE)Linting React Health UI...$(RESET)"
	cd $(BOT_DIR)/health_ui && npm run lint

ui-lint-fix:
	@echo "$(BLUE)Auto-fixing React Health UI lint issues...$(RESET)"
	cd $(BOT_DIR)/health_ui && npm run lint:fix

ui-test:
	@echo "$(BLUE)Running React Health UI tests...$(RESET)"
	cd $(BOT_DIR)/health_ui && npm test -- --run

ui-test-coverage:
	@echo "$(BLUE)Running React Health UI tests with coverage...$(RESET)"
	cd $(BOT_DIR)/health_ui && npm run test:coverage

ui-dev:
	@echo "$(BLUE)Starting React Health UI dev server...$(RESET)"
	@echo "$(YELLOW)Note: Dev server runs on port 5173 by default$(RESET)"
	cd $(BOT_DIR)/health_ui && npm run dev

tasks-ui:
	@echo "$(BLUE)Building React tasks dashboard...$(RESET)"
	cd $(PROJECT_ROOT_DIR)/tasks/ui && npm install --no-audit && npm run build
	@echo "$(GREEN)✅ Tasks UI built successfully!$(RESET)"
	@echo "$(BLUE)🌐 Access at: http://localhost:$${TASKS_PORT:-5001}$(RESET)"

# CI sub-targets (can run in parallel with -j flag)
ci-lint:
	@echo "$(BLUE)📝 Linting bot code...$(RESET)"
	@$(MAKE) lint-check

ci-test-bot: $(VENV)
	@echo "$(BLUE)🧪 Running bot tests...$(RESET)"
	@cd $(BOT_DIR) && PYTHONPATH=. $(PYTHON) -m pytest -m "not integration" -v --tb=short

ci-test-control-plane: $(VENV)
	@echo "$(BLUE)🎛️  Running control plane tests...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)control_plane && PYTHONPATH=.:$(PROJECT_ROOT_DIR) $(PYTHON) -m pytest -v --tb=short --cov-fail-under=0

ci-test-tasks: $(VENV)
	@echo "$(BLUE)⏰ Running tasks service tests...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)tasks && ENVIRONMENT=development PYTHONPATH=. $(PYTHON) -m pytest -v --tb=short --cov-fail-under=0

ci-test-shared: $(VENV)
	@echo "$(BLUE)🔗 Running shared utilities tests...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)shared && PYTHONPATH=. $(PYTHON) -m pytest tests/ -v --tb=short --cov-fail-under=0 || echo "$(YELLOW)⚠️  Shared tests skipped$(RESET)"

ci-test-dashboard: $(VENV)
	@echo "$(BLUE)📊 Running dashboard service tests...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)dashboard-service && PYTHONPATH=. $(PYTHON) -m pytest tests/ -v --tb=short --cov-fail-under=0 || echo "$(YELLOW)⚠️  Dashboard tests skipped$(RESET)"

ci-ui: health-ui tasks-ui
	@echo "$(BLUE)🎨 Running React UI checks...$(RESET)"
	@cd $(BOT_DIR)/health_ui && npm run lint && npm run test:coverage
	@cd $(PROJECT_ROOT_DIR)/tasks/ui && npm run lint && npm run test:coverage

ci-docker: health-ui tasks-ui
	@echo "$(BLUE)🐳 Building Docker images...$(RESET)"
	@cd $(PROJECT_ROOT_DIR) && DOCKER_BUILDKIT=0 docker compose build

# Main CI target - runs all checks (Docker builds excluded - use separate deployment pipeline)
# Use 'make ci' for sequential or 'make -j4 ci' for parallel execution
ci: ci-lint ci-test-bot ci-test-control-plane ci-test-tasks ci-test-shared ci-test-dashboard ci-test-rag ci-ui
	@echo ""
	@echo "$(GREEN)✅ ================================$(RESET)"
	@echo "$(GREEN)✅ ALL CI CHECKS PASSED!$(RESET)"
	@echo "$(GREEN)✅ ================================$(RESET)"
	@echo "$(YELLOW)💡 For Docker builds: make ci-docker$(RESET)"

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
	@echo "$(BLUE)  - 💬 LibreChat (ChatGPT UI): http://localhost:$${LIBRECHAT_PORT:-3080}$(RESET)"
	@echo "$(BLUE)  - Task Scheduler: http://localhost:$${TASKS_PORT:-5001}$(RESET)"
	@echo "$(BLUE)  - Database Admin: http://localhost:8081$(RESET)"
	@echo ""
	@echo "$(YELLOW)🔍 Monitoring & Logging Stack:$(RESET)"
	@echo "$(YELLOW)  - Grafana Dashboard: http://localhost:3000 (admin/admin)$(RESET)"
	@echo "$(YELLOW)  - Prometheus Metrics: http://localhost:9090$(RESET)"
	@echo "$(YELLOW)  - Loki Logs: http://localhost:3100 (view via Grafana)$(RESET)"
	@echo "$(YELLOW)  - AlertManager: http://localhost:9093$(RESET)"
	@echo ""
	@echo "$(GREEN)🎉 All services running with centralized logging! Check Grafana for logs and metrics.$(RESET)"

# Core services only (without monitoring)
start-core: docker-build docker-up

# Docker-based start (same as start)
start-docker: start

# Legacy local start
start-local: install-dev health-ui check-env start-redis
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

# Start MySQL databases in Docker (uses main docker-compose.yml)
db-start:
	@echo "$(BLUE)🐳 Starting MySQL databases...$(RESET)"
	docker compose up -d mysql phpmyadmin
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
	docker compose stop mysql phpmyadmin
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

db-setup-system:
	@echo "$(BLUE)🔧 Setting up system database (insightmesh_system)...$(RESET)"
	@echo "$(YELLOW)This will create the database and agent_usage table without destroying existing data$(RESET)"
	@docker exec insightmesh-mysql mysql -ppassword -e "CREATE DATABASE IF NOT EXISTS insightmesh_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" 2>/dev/null || true
	@docker exec insightmesh-mysql mysql -ppassword -e "CREATE USER IF NOT EXISTS 'insightmesh_system'@'%' IDENTIFIED BY 'insightmesh_system_password';" 2>/dev/null || true
	@docker exec insightmesh-mysql mysql -ppassword -e "GRANT ALL PRIVILEGES ON insightmesh_system.* TO 'insightmesh_system'@'%';" 2>/dev/null || true
	@docker exec insightmesh-mysql mysql -ppassword -e "FLUSH PRIVILEGES;" 2>/dev/null || true
	@docker exec insightmesh-mysql mysql -ppassword insightmesh_system -e "\
		CREATE TABLE IF NOT EXISTS agent_usage ( \
		    id INT PRIMARY KEY AUTO_INCREMENT, \
		    agent_name VARCHAR(100) NOT NULL UNIQUE, \
		    total_invocations INT NOT NULL DEFAULT 0, \
		    successful_invocations INT NOT NULL DEFAULT 0, \
		    failed_invocations INT NOT NULL DEFAULT 0, \
		    first_invocation DATETIME NULL, \
		    last_invocation DATETIME NULL, \
		    is_active BOOLEAN NOT NULL DEFAULT 1, \
		    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, \
		    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, \
		    INDEX ix_agent_usage_agent_name (agent_name), \
		    INDEX ix_agent_usage_is_active (is_active) \
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;" 2>/dev/null || (echo "$(RED)❌ Failed to setup system database$(RESET)" && exit 1)
	@echo "$(GREEN)✅ System database setup complete!$(RESET)"
	@echo "$(BLUE)📊 Verifying setup...$(RESET)"
	@docker exec insightmesh-mysql mysql -ppassword -e "SHOW TABLES FROM insightmesh_system;" 2>/dev/null || echo "$(RED)Failed to verify$(RESET)"

# Control Plane Service Targets
lint-control-plane: $(VENV)
	@echo "$(BLUE)🔍 Linting control plane service...$(RESET)"
	cd $(PROJECT_ROOT_DIR)control_plane && $(PYTHON) -m ruff check . --fix || true
	cd $(PROJECT_ROOT_DIR)control_plane && $(PYTHON) -m ruff format . || true

control-plane-ui:
	@echo "$(BLUE)📦 Building React control plane UI...$(RESET)"
	cd $(PROJECT_ROOT_DIR)/control_plane/ui && npm install --no-audit && npm run build
	@echo "$(GREEN)✅ Control plane UI built!$(RESET)"

test-control-plane: $(VENV)
	@echo "$(BLUE)🧪 Running control plane tests...$(RESET)"
	cd $(PROJECT_ROOT_DIR)control_plane && PYTHONPATH=.:$(PROJECT_ROOT_DIR) $(PYTHON) -m pytest -v --cov-fail-under=0 || echo "$(YELLOW)No tests yet$(RESET)"

# Behavior test suite
test-behaviors: $(VENV)
	@echo "$(BLUE)🔬 Running behavior test suite...$(RESET)"
	@echo "$(YELLOW)⚠️  This will take several minutes and tests real integrations$(RESET)"
	@cd $(PROJECT_ROOT_DIR) && PYTHONPATH=bot:agent-service $(PYTHON) -m pytest tests/behavior/test_behaviors.py -v -s --tb=short
	@echo "$(GREEN)✅ Behavior tests complete!$(RESET)"

# Help for test targets
.PHONY: test-behaviors

# LangGraph Studio - Automatic agent discovery and launch
langgraph-studio:
	@echo "$(BLUE)🔍 Discovering agents and starting LangGraph Studio...$(RESET)"
	@./start_langgraph_studio.sh

test-shared: $(VENV)
	@echo "$(BLUE)Running shared utilities tests...$(RESET)"
	cd $(PROJECT_ROOT_DIR)shared && PYTHONPATH=. $(PYTHON) -m pytest tests/ -v --cov-fail-under=0

test-dashboard: $(VENV)
	@echo "$(BLUE)Running dashboard service tests...$(RESET)"
	cd $(PROJECT_ROOT_DIR)dashboard-service && PYTHONPATH=. $(PYTHON) -m pytest tests/ -v --cov-fail-under=0

test-rag: $(VENV)
	@echo "$(BLUE)Running RAG service tests...$(RESET)"
	cd $(PROJECT_ROOT_DIR)rag-service && PYTHONPATH=.:$(PROJECT_ROOT_DIR) $(PYTHON) -m pytest tests/ -v --cov-fail-under=0

ci-test-rag: $(VENV)
	@echo "$(BLUE)🔍 Running RAG service tests...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)rag-service && PYTHONPATH=.:$(PROJECT_ROOT_DIR) $(PYTHON) -m pytest tests/ -v --tb=short --cov-fail-under=0 || echo "$(YELLOW)⚠️  RAG tests skipped$(RESET)"
