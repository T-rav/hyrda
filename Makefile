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

.PHONY: help install run test lint lint-check ci docker-build start stop restart status clean security db-start db-stop db-migrate db-upgrade db-downgrade db-reset db-status librechat-build

help:
	@echo "$(BLUE)InsightMesh - Essential Commands$(RESET)"
	@echo ""
	@echo "$(RED)🚀 PRIMARY COMMAND:$(RESET)"
	@echo "  $(GREEN)make ci$(RESET)          🔥 Comprehensive validation: lint + test + security + build (USE THIS)"
	@echo ""
	@echo "$(GREEN)Quick Commands:$(RESET)"
	@echo "  make start       Start full Docker stack"
	@echo "  make stop        Stop all containers"
	@echo "  make restart     Restart everything"
	@echo "  make status      Show container status"
	@echo ""
	@echo "$(GREEN)Development:$(RESET)"
	@echo "  make install     Install Python dependencies"
	@echo "  make run         Run bot standalone"
	@echo "  make test        Test all 6 services (unit tests only)"
	@echo "  make lint        Lint and format all services (auto-fix)"
	@echo "  make lint-check  Check linting without fixing"
	@echo ""
	@echo "$(GREEN)Build & Security:$(RESET)"
	@echo "  make docker-build Build all Docker images"
	@echo "  make security     Run security scans (Bandit + Trivy)"
	@echo "  make clean        Remove caches and artifacts"
	@echo ""
	@echo "$(GREEN)Database Management:$(RESET)"
	@echo "  db-start        🐳 Start MySQL databases (main docker-compose.yml)"
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
	@echo "$(BLUE)Installing project dependencies (dev + test)...$(RESET)"
	cd $(BOT_DIR) && $(PIP) install -e .[dev,test]
	@echo "$(GREEN)Dependencies installed successfully$(RESET)"

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
	@echo "$(BLUE)Testing all 6 microservices (unit tests only)...$(RESET)"
	@echo ""
	@echo "$(BLUE)[1/6] Bot...$(RESET)"
	@cd $(BOT_DIR) && PYTHONPATH=. $(PYTHON) -m pytest -m "not integration and not system_flow and not smoke" -q
	@echo ""
	@echo "$(BLUE)[2/6] Agent-service...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)agent-service && PYTHONPATH=. $(PYTHON) -m pytest -q
	@echo ""
	@echo "$(BLUE)[3/6] Control-plane...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)control_plane && PYTHONPATH=. $(PYTHON) -m pytest -q
	@echo ""
	@echo "$(BLUE)[4/6] Tasks...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)tasks && PYTHONPATH=. $(PYTHON) -m pytest -m "not integration and not smoke" -q
	@echo ""
	@echo "$(BLUE)[5/6] Rag-service...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)rag-service && PYTHONPATH=.. $(PYTHON) -m pytest -q
	@echo ""
	@echo "$(BLUE)[6/6] Dashboard-service...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)dashboard-service && PYTHONPATH=.. $(PYTHON) -m pytest -q
	@echo ""
	@echo "$(GREEN)✅ All 6 services tested successfully$(RESET)"

# Ingestion is now handled via scheduled tasks in the tasks service dashboard
# Visit http://localhost:5001 to configure scheduled Google Drive ingestion jobs

lint:
	@echo "$(BLUE)🔍 Running unified linting on all services (using $(PYTHON_LINT))...$(RESET)"
	@if [ -z "$(PYTHON_LINT)" ]; then \
		echo "$(RED)❌ Error: No Python interpreter with ruff found. Please install ruff:$(RESET)"; \
		echo "   python -m pip install ruff pyright bandit"; \
		exit 1; \
	fi
	@echo "$(BLUE)📝 Bot...$(RESET)"
	@$(PYTHON_LINT) -m ruff check $(BOT_DIR) --fix && $(PYTHON_LINT) -m ruff format $(BOT_DIR)
	@echo "$(BLUE)📝 Agent-service...$(RESET)"
	@cd agent-service && $(PYTHON_LINT) -m ruff check . --fix && $(PYTHON_LINT) -m ruff format .
	@echo "$(BLUE)📝 Control-plane...$(RESET)"
	@cd control_plane && $(PYTHON_LINT) -m ruff check . --fix && $(PYTHON_LINT) -m ruff format .
	@echo "$(BLUE)📝 Tasks...$(RESET)"
	@cd tasks && $(PYTHON_LINT) -m ruff check . --fix && $(PYTHON_LINT) -m ruff format .
	@echo "$(BLUE)📝 Rag-service...$(RESET)"
	@cd rag-service && $(PYTHON_LINT) -m ruff check . --fix && $(PYTHON_LINT) -m ruff format .
	@echo "$(BLUE)📝 Dashboard-service...$(RESET)"
	@cd dashboard-service && $(PYTHON_LINT) -m ruff check . --fix && $(PYTHON_LINT) -m ruff format .
	@echo "$(GREEN)✅ All services linted and formatted!$(RESET)"

lint-check:
	@echo "$(BLUE)🔍 Running unified linting checks on all services (using $(PYTHON_LINT))...$(RESET)"
	@if [ -z "$(PYTHON_LINT)" ]; then \
		echo "$(RED)❌ Error: No Python interpreter with ruff found. Please install ruff:$(RESET)"; \
		echo "   python -m pip install ruff pyright bandit"; \
		exit 1; \
	fi
	@echo "$(BLUE)🔍 Bot...$(RESET)"
	@$(PYTHON_LINT) -m ruff check $(BOT_DIR) && $(PYTHON_LINT) -m ruff format $(BOT_DIR) --check
	@echo "$(BLUE)🔍 Agent-service...$(RESET)"
	@cd agent-service && $(PYTHON_LINT) -m ruff check . && $(PYTHON_LINT) -m ruff format . --check
	@echo "$(BLUE)🔍 Control-plane...$(RESET)"
	@cd control_plane && $(PYTHON_LINT) -m ruff check . && $(PYTHON_LINT) -m ruff format . --check
	@echo "$(BLUE)🔍 Tasks...$(RESET)"
	@cd tasks && $(PYTHON_LINT) -m ruff check . && $(PYTHON_LINT) -m ruff format . --check
	@echo "$(BLUE)🔍 Rag-service...$(RESET)"
	@cd rag-service && $(PYTHON_LINT) -m ruff check . && $(PYTHON_LINT) -m ruff format . --check
	@echo "$(BLUE)🔍 Dashboard-service...$(RESET)"
	@cd dashboard-service && $(PYTHON_LINT) -m ruff check . && $(PYTHON_LINT) -m ruff format . --check
	@echo "$(GREEN)✅ All services passed linting checks!$(RESET)"

# Removed redundant targets - use 'make ci' for comprehensive validation

# Removed redundant Docker targets - use start/stop/restart/status instead

docker-build:
	@echo "$(BLUE)🔨 Building all Docker images (main stack + LibreChat)...$(RESET)"
	cd $(PROJECT_ROOT_DIR) && DOCKER_BUILDKIT=0 docker compose build
	cd $(PROJECT_ROOT_DIR) && docker compose -f docker-compose.librechat.yml build
	@echo "$(GREEN)✅ All images built successfully!$(RESET)"

# Start full Docker stack
start: docker-build
	@echo "$(BLUE)🚀 Starting full InsightMesh stack...$(RESET)"
	cd $(PROJECT_ROOT_DIR) && docker compose up -d
	@echo "$(GREEN)✅ InsightMesh services started!$(RESET)"
	@echo "$(BLUE)  - Bot Health: http://localhost:8080$(RESET)"
	@echo "$(BLUE)  - Task Scheduler: http://localhost:5001$(RESET)"
	@echo "$(BLUE)  - Database Admin: http://localhost:8081$(RESET)"

# Stop all containers
stop:
	@echo "$(BLUE)🛑 Stopping InsightMesh stack...$(RESET)"
	cd $(PROJECT_ROOT_DIR) && docker compose down
	@echo "$(GREEN)✅ All services stopped!$(RESET)"

# Restart everything
restart: stop start
	@echo "$(GREEN)✅ Services restarted successfully!$(RESET)"

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

# CI pipeline: lint + test + security + build
ci: lint-check test security docker-build
	@echo "$(GREEN)✅ Comprehensive CI validation passed!$(RESET)"
	@echo "$(GREEN)✅ All services: linted, tested, secured, and built$(RESET)"

security: $(VENV)
	@echo "$(BLUE)🔒 Running security scans (Bandit + Trivy)...$(RESET)"
	@echo "$(BLUE)1/2 Code scanning with Bandit...$(RESET)"
	-cd $(BOT_DIR) && $(PYTHON) -m bandit -r . -f txt --exclude ./.venv,./venv,./node_modules,./build,./dist,./.pytest_cache,./.ruff_cache
	@echo ""
	@echo "$(BLUE)2/2 Docker image scanning with Trivy...$(RESET)"
	@if docker image inspect insightmesh-bot:latest >/dev/null 2>&1; then \
		docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
			aquasec/trivy:latest image --severity HIGH,CRITICAL --format table insightmesh-bot:latest || true; \
	else \
		echo "$(YELLOW)⚠️  Docker images not built yet. Run 'make docker-build' first for full scan.$(RESET)"; \
	fi
	@echo "$(GREEN)✅ Security scans completed (warnings above are non-blocking)$(RESET)"

clean:
	@echo "$(YELLOW)Cleaning up build artifacts and caches...$(RESET)"
	find $(PROJECT_ROOT_DIR) -type f -name "*.pyc" -delete
	find $(PROJECT_ROOT_DIR) -type d -name "__pycache__" -delete
	rm -rf $(PROJECT_ROOT_DIR).coverage $(PROJECT_ROOT_DIR)htmlcov/ $(BOT_DIR)/htmlcov_slack-bot/
	rm -rf $(PROJECT_ROOT_DIR).pytest_cache $(BOT_DIR)/.pytest_cache
	rm -rf $(PROJECT_ROOT_DIR).ruff_cache $(BOT_DIR)/.ruff_cache
	rm -rf $(PROJECT_ROOT_DIR).pyright_cache $(BOT_DIR)/.pyright_cache
	@echo "$(GREEN)Cleanup completed$(RESET)"

# Removed redundant start-* targets - use 'make start' for Docker stack

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

# ===== LIBRECHAT UI =====

# Build custom LibreChat Docker image with InsightMesh UI
librechat-build:
	@echo "$(BLUE)🔨 Building custom LibreChat with InsightMesh UI...$(RESET)"
	docker compose -f docker-compose.librechat.yml build
	@echo "$(GREEN)✅ LibreChat image built successfully!$(RESET)"
	@echo "$(YELLOW)To start: docker compose -f docker-compose.librechat.yml up -d$(RESET)"
	@echo "$(YELLOW)To stop:  docker compose -f docker-compose.librechat.yml down$(RESET)"
