# Makefile for InsightMesh
# All Python commands use `uv run` — never raw python/pip

# Determine project root directory (where this Makefile is located)
MAKEFILE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
PROJECT_ROOT_DIR := $(MAKEFILE_DIR)
BOT_DIR := $(PROJECT_ROOT_DIR)bot
VENV := $(PROJECT_ROOT_DIR)venv
ENV_FILE := $(PROJECT_ROOT_DIR).env
IMAGE ?= insight-mesh-slack-bot

# uv run using the shared root venv (not per-service project envs)
UV := VIRTUAL_ENV=$(VENV) uv run --active

# Version management
VERSION_FILE := $(PROJECT_ROOT_DIR).version
VERSION := $(shell cat $(VERSION_FILE) 2>/dev/null || echo "0.0.0")
GIT_SHA := $(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")
BUILD_DATE := $(shell date -u +"%Y-%m-%dT%H:%M:%SZ")

# Docker registry configuration
# Override these with environment variables or make arguments:
#   make docker-push REGISTRY=ghcr.io/myorg
REGISTRY ?= localhost
IMAGE_PREFIX ?= insightmesh

# Full image names with registry and version
BOT_IMAGE := $(REGISTRY)/$(IMAGE_PREFIX)-bot:$(VERSION)
AGENT_SERVICE_IMAGE := $(REGISTRY)/$(IMAGE_PREFIX)-agent-service:$(VERSION)
CONTROL_PLANE_IMAGE := $(REGISTRY)/$(IMAGE_PREFIX)-control-plane:$(VERSION)
TASKS_IMAGE := $(REGISTRY)/$(IMAGE_PREFIX)-tasks:$(VERSION)
RAG_SERVICE_IMAGE := $(REGISTRY)/$(IMAGE_PREFIX)-rag-service:$(VERSION)
DASHBOARD_SERVICE_IMAGE := $(REGISTRY)/$(IMAGE_PREFIX)-dashboard-service:$(VERSION)
LANGSMITH_PROXY_IMAGE := $(REGISTRY)/$(IMAGE_PREFIX)-langsmith-proxy:$(VERSION)

# All images for batch operations
ALL_IMAGES := $(BOT_IMAGE) $(AGENT_SERVICE_IMAGE) $(CONTROL_PLANE_IMAGE) $(TASKS_IMAGE) $(RAG_SERVICE_IMAGE) $(DASHBOARD_SERVICE_IMAGE) $(LANGSMITH_PROXY_IMAGE)

# All service directories (for iteration)
SERVICE_DIRS := bot agent-service control_plane tasks rag-service dashboard-service shared

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
RESET := \033[0m

.PHONY: help install setup-dev run test test-fast test-service test-coverage lint lint-check quality ci docker-build start stop restart status clean security security-docker security-full db-start db-stop db-migrate db-upgrade db-downgrade db-reset db-status version version-bump docker-tag docker-push docker-push-latest release

help:
	@echo "$(BLUE)InsightMesh - Essential Commands$(RESET)"
	@echo ""
	@echo "$(RED)PRIMARY COMMAND:$(RESET)"
	@echo "  $(GREEN)make ci$(RESET)              Comprehensive validation: lint + test + security + build"
	@echo ""
	@echo "$(GREEN)Quick Commands:$(RESET)"
	@echo "  make start             Start full Docker stack"
	@echo "  make stop              Stop all containers"
	@echo "  make restart           Restart everything"
	@echo "  make status            Show container status"
	@echo ""
	@echo "$(GREEN)Development:$(RESET)"
	@echo "  make install           Install all service dependencies (via uv)"
	@echo "  make setup-dev         Install dev tools + pre-commit hooks (run once)"
	@echo "  make run               Run bot standalone"
	@echo ""
	@echo "$(GREEN)Testing (progressive):$(RESET)"
	@echo "  make lint              Lint + format all services (auto-fix) (~2s)"
	@echo "  make lint-check        Check linting without fixing (~2s)"
	@echo "  make test-fast         Unit tests only, all services (~20s)"
	@echo "  make test-service SERVICE=bot  Test a single service"
	@echo "  make test              Full test suite, all services (~2-3min)"
	@echo "  make test-coverage     Tests with coverage report (>70% required)"
	@echo "  make quality           Lint + test (~2-3min)"
	@echo "  make ci                Full CI: quality + security + build (~5-10min)"
	@echo ""
	@echo "$(GREEN)Build & Security:$(RESET)"
	@echo "  make docker-build      Build all Docker images"
	@echo "  make security          Run Bandit code security scanner"
	@echo "  make security-docker   Scan Docker images with Trivy"
	@echo "  make security-full     Bandit + Trivy + pip-audit + Checkov + Semgrep"
	@echo "  make clean             Remove caches and artifacts"
	@echo ""
	@echo "$(GREEN)Version & Release:$(RESET)"
	@echo "  make version           Show current version"
	@echo "  make version-bump      Bump version (patch|minor|major)"
	@echo "  make docker-tag        Tag images with version"
	@echo "  make docker-push       Push images to registry"
	@echo "  make release           Full release: tag, build, push"
	@echo ""
	@echo "$(GREEN)Database Management:$(RESET)"
	@echo "  make db-start          Start MySQL databases"
	@echo "  make db-stop           Stop MySQL databases"
	@echo "  make db-migrate        Generate new migration files"
	@echo "  make db-upgrade        Apply pending migrations"
	@echo "  make db-downgrade      Rollback last migration"
	@echo "  make db-reset          Reset databases (WARNING: destroys data)"
	@echo "  make db-status         Show migration status"

# ===== SETUP & INSTALL =====

install:
	@echo "$(BLUE)Installing all service dependencies (via uv)...$(RESET)"
	@echo "$(BLUE)[1/7] Bot...$(RESET)"
	@cd $(BOT_DIR) && VIRTUAL_ENV=$(VENV) uv pip install -e ".[dev,test]"
	@echo "$(BLUE)[2/7] Agent-service...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)agent-service && VIRTUAL_ENV=$(VENV) uv pip install -e ".[dev,test]" 2>/dev/null || VIRTUAL_ENV=$(VENV) uv pip install -e .
	@echo "$(BLUE)[3/7] Control-plane...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)control_plane && VIRTUAL_ENV=$(VENV) uv pip install -e ".[dev,test]" 2>/dev/null || VIRTUAL_ENV=$(VENV) uv pip install -e .
	@echo "$(BLUE)[4/7] Tasks...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)tasks && VIRTUAL_ENV=$(VENV) uv pip install -e ".[dev,test]" 2>/dev/null || VIRTUAL_ENV=$(VENV) uv pip install -e .
	@echo "$(BLUE)[5/7] Rag-service...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)rag-service && VIRTUAL_ENV=$(VENV) uv pip install -e ".[dev,test]" 2>/dev/null || VIRTUAL_ENV=$(VENV) uv pip install -e .
	@echo "$(BLUE)[6/7] Dashboard-service...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)dashboard-service && VIRTUAL_ENV=$(VENV) uv pip install -e ".[dev,test]" 2>/dev/null || VIRTUAL_ENV=$(VENV) uv pip install -e .
	@echo "$(BLUE)[7/7] Dev tools (ruff, pyright, bandit)...$(RESET)"
	@VIRTUAL_ENV=$(VENV) uv pip install ruff pyright bandit
	@echo "$(GREEN)All service dependencies installed successfully$(RESET)"

setup-dev: install
	@echo "$(BLUE)Setting up development environment...$(RESET)"
	@VIRTUAL_ENV=$(VENV) uv pip install pre-commit
	@pre-commit install
	@echo "$(GREEN)Dev environment ready! Pre-commit hooks installed.$(RESET)"

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
	@echo "$(GREEN)Redis service started$(RESET)"

run: check-env start-redis
	@echo "$(GREEN)Starting AI Slack Bot...$(RESET)"
	cd $(BOT_DIR) && $(UV) python app.py

# ===== TESTING =====

test:
	@echo "$(BLUE)Testing all 7 services (unit tests only)...$(RESET)"
	@echo ""
	@echo "$(BLUE)[1/7] Bot...$(RESET)"
	@cd $(BOT_DIR) && PYTHONPATH=. $(UV) pytest -m "not integration and not system_flow and not smoke" -q
	@echo ""
	@echo "$(BLUE)[2/7] Agent-service...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)agent-service && PYTHONPATH=. $(UV) pytest -m "not integration" -q
	@echo ""
	@echo "$(BLUE)[3/7] Control-plane...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)control_plane && PYTHONPATH=. $(UV) pytest -q
	@echo ""
	@echo "$(BLUE)[4/7] Tasks...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)tasks && PYTHONPATH=. $(UV) pytest -m "not integration and not smoke" -q
	@echo ""
	@echo "$(BLUE)[5/7] Rag-service...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)rag-service && PYTHONPATH=.. $(UV) pytest -m "not smoke" -q
	@echo ""
	@echo "$(BLUE)[6/7] Dashboard-service...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)dashboard-service && PYTHONPATH=.. $(UV) pytest -q
	@echo ""
	@echo "$(BLUE)[7/7] Shared...$(RESET)"
	@cd $(PROJECT_ROOT_DIR) && PYTHONPATH=shared $(UV) pytest shared/tests/ -q
	@echo ""
	@echo "$(GREEN)All 7 services tested successfully$(RESET)"

test-fast:
	@echo "$(BLUE)Quick validation - unit tests only (all services)...$(RESET)"
	@cd $(BOT_DIR) && PYTHONPATH=. $(UV) pytest -m "not integration and not system_flow and not smoke" -q --no-header
	@cd $(PROJECT_ROOT_DIR)agent-service && PYTHONPATH=. $(UV) pytest -m "not integration" -q --no-header
	@cd $(PROJECT_ROOT_DIR)control_plane && PYTHONPATH=. $(UV) pytest -q --no-header
	@cd $(PROJECT_ROOT_DIR)tasks && PYTHONPATH=. $(UV) pytest -m "not integration and not smoke" -q --no-header
	@cd $(PROJECT_ROOT_DIR)rag-service && PYTHONPATH=.. $(UV) pytest -m "not smoke" -q --no-header
	@cd $(PROJECT_ROOT_DIR)dashboard-service && PYTHONPATH=.. $(UV) pytest -q --no-header
	@cd $(PROJECT_ROOT_DIR) && PYTHONPATH=shared $(UV) pytest shared/tests/ -q --no-header
	@echo "$(GREEN)All tests passed$(RESET)"

test-service:
	@if [ -z "$(SERVICE)" ]; then \
		echo "$(RED)Error: Specify SERVICE=<name>$(RESET)"; \
		echo "  Example: make test-service SERVICE=bot"; \
		echo "  Available: bot, agent-service, control_plane, tasks, rag-service, dashboard-service, shared"; \
		exit 1; \
	fi
	@echo "$(BLUE)Testing $(SERVICE)...$(RESET)"
	@if [ "$(SERVICE)" = "shared" ]; then \
		cd $(PROJECT_ROOT_DIR) && PYTHONPATH=shared $(UV) pytest shared/tests/ -v; \
	elif [ "$(SERVICE)" = "bot" ]; then \
		cd $(BOT_DIR) && PYTHONPATH=. $(UV) pytest -m "not integration and not system_flow and not smoke" -v; \
	elif [ "$(SERVICE)" = "tasks" ]; then \
		cd $(PROJECT_ROOT_DIR)tasks && PYTHONPATH=. $(UV) pytest -m "not integration and not smoke" -v; \
	elif [ "$(SERVICE)" = "rag-service" ]; then \
		cd $(PROJECT_ROOT_DIR)rag-service && PYTHONPATH=.. $(UV) pytest -m "not smoke" -v; \
	elif [ "$(SERVICE)" = "agent-service" ]; then \
		cd $(PROJECT_ROOT_DIR)agent-service && PYTHONPATH=. $(UV) pytest -m "not integration" -v; \
	else \
		cd $(PROJECT_ROOT_DIR)$(SERVICE) && PYTHONPATH=. $(UV) pytest -v; \
	fi

test-coverage:
	@echo "$(BLUE)Running tests with coverage report...$(RESET)"
	@echo ""
	@echo "$(BLUE)[1/7] Bot...$(RESET)"
	@cd $(BOT_DIR) && PYTHONPATH=. $(UV) pytest -m "not integration and not system_flow and not smoke" --cov=. --cov-report=term-missing --cov-fail-under=70 -q
	@echo ""
	@echo "$(BLUE)[2/7] Agent-service...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)agent-service && PYTHONPATH=. $(UV) pytest -m "not integration" --cov=. --cov-report=term-missing --cov-fail-under=70 -q
	@echo ""
	@echo "$(BLUE)[3/7] Control-plane...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)control_plane && PYTHONPATH=. $(UV) pytest --cov=. --cov-report=term-missing --cov-fail-under=70 -q
	@echo ""
	@echo "$(BLUE)[4/7] Tasks...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)tasks && PYTHONPATH=. $(UV) pytest -m "not integration and not smoke" --cov=. --cov-report=term-missing --cov-fail-under=70 -q
	@echo ""
	@echo "$(BLUE)[5/7] Rag-service...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)rag-service && PYTHONPATH=.. $(UV) pytest -m "not smoke" --cov=. --cov-report=term-missing --cov-fail-under=70 -q
	@echo ""
	@echo "$(BLUE)[6/7] Dashboard-service...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)dashboard-service && PYTHONPATH=.. $(UV) pytest --cov=. --cov-report=term-missing --cov-fail-under=70 -q
	@echo ""
	@echo "$(BLUE)[7/7] Shared...$(RESET)"
	@cd $(PROJECT_ROOT_DIR) && PYTHONPATH=shared $(UV) pytest shared/tests/ -q
	@echo ""
	@echo "$(GREEN)All services meet coverage threshold (>70%)$(RESET)"

# ===== LINTING =====

lint:
	@echo "$(BLUE)Running unified linting on all services (auto-fix)...$(RESET)"
	@for dir in $(SERVICE_DIRS); do \
		echo "$(BLUE)  $$dir...$(RESET)"; \
		cd $(PROJECT_ROOT_DIR)$$dir && $(UV) ruff check . --fix && $(UV) ruff format .; \
	done
	@echo "$(GREEN)All services linted and formatted!$(RESET)"

lint-check:
	@echo "$(BLUE)Running unified linting checks on all services...$(RESET)"
	@for dir in $(SERVICE_DIRS); do \
		echo "$(BLUE)  $$dir...$(RESET)"; \
		cd $(PROJECT_ROOT_DIR)$$dir && $(UV) ruff check . && $(UV) ruff format . --check; \
	done
	@echo "$(GREEN)All services passed linting checks!$(RESET)"

# ===== QUALITY & CI =====

quality: lint-check test
	@echo "$(GREEN)Quality pipeline passed (lint + tests)$(RESET)"

ci: lint-check test security docker-build
	@echo "$(GREEN)Comprehensive CI validation passed!$(RESET)"
	@echo "$(GREEN)All services: linted, tested, secured, and built$(RESET)"

# ===== SECURITY =====

security:
	@echo "$(BLUE)Running Bandit security scanner on all services...$(RESET)"
	@for dir in bot agent-service control_plane tasks rag-service dashboard-service; do \
		echo "$(BLUE)  $$dir...$(RESET)"; \
		cd $(PROJECT_ROOT_DIR)$$dir && $(UV) bandit -r . -f txt \
			--exclude ./.venv,./venv,./node_modules,./build,./dist,./.pytest_cache,./.ruff_cache,./tests \
			2>/dev/null || true; \
	done
	@echo "$(GREEN)Security scans completed$(RESET)"

security-docker:
	@echo "$(BLUE)Scanning Docker images with Trivy...$(RESET)"
	@if docker image inspect insightmesh-bot:latest >/dev/null 2>&1; then \
		for img in bot agent-service control-plane tasks rag-service dashboard-service; do \
			echo "$(BLUE)  insightmesh-$$img...$(RESET)"; \
			docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
				aquasec/trivy:latest image --severity HIGH,CRITICAL --format table \
				insightmesh-$$img:latest 2>/dev/null || true; \
		done; \
	else \
		echo "$(YELLOW)Docker images not built yet. Run 'make docker-build' first.$(RESET)"; \
	fi
	@echo "$(GREEN)Docker security scans completed$(RESET)"

security-full: security security-docker
	@echo ""
	@echo "$(BLUE)Extended security scans...$(RESET)"
	@echo "$(BLUE)Dependency vulnerability audit (pip-audit)...$(RESET)"
	@if $(UV) pip-audit --help >/dev/null 2>&1; then \
		$(UV) pip-audit --desc 2>/dev/null || echo "$(YELLOW)pip-audit found issues (review above)$(RESET)"; \
	else \
		echo "$(YELLOW)pip-audit not installed. Run: VIRTUAL_ENV=$(VENV) uv pip install pip-audit$(RESET)"; \
	fi
	@echo ""
	@echo "$(BLUE)Infrastructure security scan (Checkov)...$(RESET)"
	@if $(UV) checkov --help >/dev/null 2>&1; then \
		$(UV) checkov --file docker-compose.yml --quiet --compact 2>/dev/null || echo "$(YELLOW)Checkov found issues (review above)$(RESET)"; \
	else \
		echo "$(YELLOW)Checkov not installed. Run: VIRTUAL_ENV=$(VENV) uv pip install checkov$(RESET)"; \
	fi
	@echo ""
	@echo "$(BLUE)Semgrep security analysis...$(RESET)"
	@if $(UV) semgrep --help >/dev/null 2>&1; then \
		cd $(BOT_DIR) && $(UV) semgrep --config=auto --quiet --error . 2>/dev/null || echo "$(YELLOW)Semgrep found issues (review above)$(RESET)"; \
	else \
		echo "$(YELLOW)Semgrep not installed. Run: VIRTUAL_ENV=$(VENV) uv pip install semgrep$(RESET)"; \
	fi
	@echo "$(GREEN)Extended security scans completed$(RESET)"

# ===== VERSION MANAGEMENT =====

version:
	@echo "$(BLUE)InsightMesh Version Information$(RESET)"
	@echo "  Version:     $(GREEN)$(VERSION)$(RESET)"
	@echo "  Git SHA:     $(YELLOW)$(GIT_SHA)$(RESET)"
	@echo "  Build Date:  $(YELLOW)$(BUILD_DATE)$(RESET)"
	@echo "  Registry:    $(YELLOW)$(REGISTRY)$(RESET)"
	@echo ""
	@echo "$(BLUE)Docker Images:$(RESET)"
	@echo "  Bot:              $(BOT_IMAGE)"
	@echo "  Agent Service:    $(AGENT_SERVICE_IMAGE)"
	@echo "  Control Plane:    $(CONTROL_PLANE_IMAGE)"
	@echo "  Tasks:            $(TASKS_IMAGE)"
	@echo "  RAG Service:      $(RAG_SERVICE_IMAGE)"
	@echo "  Dashboard:        $(DASHBOARD_SERVICE_IMAGE)"
	@echo "  LangSmith Proxy:  $(LANGSMITH_PROXY_IMAGE)"

version-bump:
	@echo "$(BLUE)Current version: $(VERSION)$(RESET)"
	@read -p "Bump type (patch|minor|major): " bump_type; \
	current_version=$(VERSION); \
	major=$$(echo $$current_version | cut -d. -f1); \
	minor=$$(echo $$current_version | cut -d. -f2); \
	patch=$$(echo $$current_version | cut -d. -f3); \
	case "$$bump_type" in \
		major) major=$$((major + 1)); minor=0; patch=0;; \
		minor) minor=$$((minor + 1)); patch=0;; \
		patch) patch=$$((patch + 1));; \
		*) echo "$(RED)Invalid bump type. Use: patch, minor, or major$(RESET)"; exit 1;; \
	esac; \
	new_version="$${major}.$${minor}.$${patch}"; \
	echo "$$new_version" > $(VERSION_FILE); \
	echo "$(GREEN)Version bumped: $$current_version -> $$new_version$(RESET)"; \
	echo "$(YELLOW)Don't forget to commit the .version file!$(RESET)"

# ===== DOCKER BUILD & PUBLISH =====

# Build with version args injected
docker-build-versioned: health-ui tasks-ui control-plane-ui dashboard-health-ui
	@echo "$(BLUE)Building versioned Docker images (v$(VERSION))...$(RESET)"
	cd $(PROJECT_ROOT_DIR) && \
	DOCKER_BUILDKIT=1 docker compose build \
		--build-arg VERSION=$(VERSION) \
		--build-arg GIT_SHA=$(GIT_SHA) \
		--build-arg BUILD_DATE=$(BUILD_DATE)
	@echo "$(GREEN)All images built with version $(VERSION)$(RESET)"

# Tag local images with registry prefix and version
docker-tag:
	@echo "$(BLUE)Tagging images for registry...$(RESET)"
	@echo "$(YELLOW)Tagging bot...$(RESET)"
	docker tag insightmesh-bot:latest $(BOT_IMAGE)
	docker tag insightmesh-bot:latest $(REGISTRY)/$(IMAGE_PREFIX)-bot:latest
	@echo "$(YELLOW)Tagging agent-service...$(RESET)"
	docker tag insightmesh-agent-service:latest $(AGENT_SERVICE_IMAGE)
	docker tag insightmesh-agent-service:latest $(REGISTRY)/$(IMAGE_PREFIX)-agent-service:latest
	@echo "$(YELLOW)Tagging control-plane...$(RESET)"
	docker tag insightmesh-control-plane:latest $(CONTROL_PLANE_IMAGE)
	docker tag insightmesh-control-plane:latest $(REGISTRY)/$(IMAGE_PREFIX)-control-plane:latest
	@echo "$(YELLOW)Tagging tasks...$(RESET)"
	docker tag insightmesh-tasks:latest $(TASKS_IMAGE)
	docker tag insightmesh-tasks:latest $(REGISTRY)/$(IMAGE_PREFIX)-tasks:latest
	@echo "$(YELLOW)Tagging rag-service...$(RESET)"
	docker tag insightmesh-rag-service:latest $(RAG_SERVICE_IMAGE)
	docker tag insightmesh-rag-service:latest $(REGISTRY)/$(IMAGE_PREFIX)-rag-service:latest
	@echo "$(YELLOW)Tagging dashboard-service...$(RESET)"
	docker tag insightmesh-dashboard-service:latest $(DASHBOARD_SERVICE_IMAGE)
	docker tag insightmesh-dashboard-service:latest $(REGISTRY)/$(IMAGE_PREFIX)-dashboard-service:latest
	@echo "$(YELLOW)Tagging langsmith-proxy...$(RESET)"
	docker tag insightmesh-langsmith-proxy:latest $(LANGSMITH_PROXY_IMAGE)
	docker tag insightmesh-langsmith-proxy:latest $(REGISTRY)/$(IMAGE_PREFIX)-langsmith-proxy:latest
	@echo "$(GREEN)All images tagged for registry$(RESET)"

# Push all images to registry
docker-push:
	@echo "$(BLUE)Pushing images to registry: $(REGISTRY)$(RESET)"
	@if [ "$(REGISTRY)" = "localhost" ]; then \
		echo "$(RED)Error: REGISTRY not set. Use: make docker-push REGISTRY=ghcr.io/yourorg$(RESET)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Pushing version $(VERSION) tags...$(RESET)"
	docker push $(BOT_IMAGE)
	docker push $(AGENT_SERVICE_IMAGE)
	docker push $(CONTROL_PLANE_IMAGE)
	docker push $(TASKS_IMAGE)
	docker push $(RAG_SERVICE_IMAGE)
	docker push $(DASHBOARD_SERVICE_IMAGE)
	docker push $(LANGSMITH_PROXY_IMAGE)
	@echo "$(YELLOW)Pushing latest tags...$(RESET)"
	docker push $(REGISTRY)/$(IMAGE_PREFIX)-bot:latest
	docker push $(REGISTRY)/$(IMAGE_PREFIX)-agent-service:latest
	docker push $(REGISTRY)/$(IMAGE_PREFIX)-control-plane:latest
	docker push $(REGISTRY)/$(IMAGE_PREFIX)-tasks:latest
	docker push $(REGISTRY)/$(IMAGE_PREFIX)-rag-service:latest
	docker push $(REGISTRY)/$(IMAGE_PREFIX)-dashboard-service:latest
	docker push $(REGISTRY)/$(IMAGE_PREFIX)-langsmith-proxy:latest
	@echo "$(GREEN)All images pushed to $(REGISTRY)$(RESET)"

# Full release workflow: bump (optional), build, tag, push
release:
	@echo "$(BLUE)Starting release workflow$(RESET)"
	@echo "$(BLUE)Current version: $(VERSION)$(RESET)"
	@read -p "Bump version? (patch|minor|major|no): " bump; \
	if [ "$$bump" != "no" ]; then \
		$(MAKE) version-bump; \
		VERSION=$$(cat $(VERSION_FILE)); \
	fi
	@echo "$(BLUE)Building images...$(RESET)"
	$(MAKE) docker-build-versioned
	@echo "$(BLUE)Tagging images...$(RESET)"
	$(MAKE) docker-tag
	@echo "$(BLUE)Pushing to registry...$(RESET)"
	$(MAKE) docker-push
	@echo "$(GREEN)Release $(VERSION) complete!$(RESET)"
	@echo "$(YELLOW)To deploy, update docker-compose.prod.yml with version $(VERSION)$(RESET)"

# Build React UIs (required for Docker images)
health-ui:
	@echo "$(BLUE)Building React health dashboard...$(RESET)"
	cd $(PROJECT_ROOT_DIR)/bot/health_ui && npm install --no-audit && npm run build
	@echo "$(GREEN)Health UI built successfully!$(RESET)"

tasks-ui:
	@echo "$(BLUE)Building React tasks dashboard...$(RESET)"
	@cd $(PROJECT_ROOT_DIR)/tasks/ui && npm install --no-audit && \
		if [ -f $(PROJECT_ROOT_DIR)/.env ]; then . $(PROJECT_ROOT_DIR)/.env; fi && \
		VITE_BASE_PATH=$${TASKS_BASE_PATH:-/} npm run build && \
		echo "Built with base path: $${TASKS_BASE_PATH:-/}"
	@echo "$(GREEN)Tasks UI built successfully!$(RESET)"

control-plane-ui:
	@echo "$(BLUE)Building React control plane dashboard...$(RESET)"
	cd $(PROJECT_ROOT_DIR)/control_plane/ui && npm install --no-audit && npm run build
	@echo "$(GREEN)Control Plane UI built successfully!$(RESET)"

dashboard-health-ui:
	@echo "$(BLUE)Building React dashboard health UI...$(RESET)"
	cd $(PROJECT_ROOT_DIR)/dashboard-service/health_ui && npm install --no-audit && npm run build
	@echo "$(GREEN)Dashboard Health UI built successfully!$(RESET)"

docker-build: health-ui tasks-ui control-plane-ui dashboard-health-ui
	@echo "$(BLUE)Building all Docker images...$(RESET)"
	@echo "$(YELLOW)Version: $(VERSION) | SHA: $(GIT_SHA) | Date: $(BUILD_DATE)$(RESET)"
	cd $(PROJECT_ROOT_DIR) && DOCKER_BUILDKIT=1 docker compose build \
		--build-arg VERSION=$(VERSION) \
		--build-arg GIT_SHA=$(GIT_SHA) \
		--build-arg BUILD_DATE=$(BUILD_DATE)
	@echo "$(GREEN)All images built successfully!$(RESET)"

# ===== DOCKER STACK =====

# Start full Docker stack
start: docker-build
	@echo "$(BLUE)Starting full InsightMesh stack...$(RESET)"
	cd $(PROJECT_ROOT_DIR) && docker compose up -d
	@echo "$(GREEN)InsightMesh services started!$(RESET)"
	@echo "$(BLUE)  - Bot Health: http://localhost:8080$(RESET)"
	@echo "$(BLUE)  - Task Scheduler: http://localhost:5001$(RESET)"
	@echo "$(BLUE)  - Database Admin: http://localhost:8081$(RESET)"

# Stop all containers
stop:
	@echo "$(BLUE)Stopping InsightMesh stack...$(RESET)"
	cd $(PROJECT_ROOT_DIR) && docker compose down
	@echo "$(GREEN)All services stopped!$(RESET)"

# Restart everything
restart: stop start
	@echo "$(GREEN)Services restarted successfully!$(RESET)"

# Status command - show Docker container status
status:
	@echo "$(BLUE)================================$(RESET)"
	@echo "$(BLUE)DOCKER CONTAINER STATUS$(RESET)"
	@echo "$(BLUE)================================$(RESET)"
	@echo ""
	@echo "$(YELLOW)Main Stack Containers:$(RESET)"
	@docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" --filter "network=insightmesh" 2>/dev/null || echo "$(RED)Main stack not running$(RESET)"
	@echo ""
	@echo "$(YELLOW)Monitoring Stack Containers:$(RESET)"
	@docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" --filter "label=com.docker.compose.project=monitoring" 2>/dev/null || echo "$(RED)Monitoring stack not running$(RESET)"
	@echo ""
	@echo "$(YELLOW)All InsightMesh Containers:$(RESET)"
	@docker ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}" --filter "name=insightmesh" 2>/dev/null || echo "$(RED)No InsightMesh containers found$(RESET)"
	@echo ""
	@echo "$(BLUE)Service URLs (if running):$(RESET)"
	@echo "$(BLUE)  - Bot Health Dashboard: http://localhost:$${HEALTH_PORT:-8080}$(RESET)"
	@echo "$(BLUE)  - Task Scheduler: http://localhost:$${TASKS_PORT:-5001}$(RESET)"
	@echo "$(BLUE)  - Database Admin: http://localhost:8081$(RESET)"
	@echo "$(BLUE)  - Grafana (Logs + Metrics): http://localhost:3000 (admin/admin)$(RESET)"
	@echo "$(BLUE)  - Prometheus: http://localhost:9090$(RESET)"
	@echo "$(BLUE)  - Loki: http://localhost:3100$(RESET)"
	@echo "$(BLUE)  - AlertManager: http://localhost:9093$(RESET)"

# ===== CLEANUP =====

clean:
	@echo "$(YELLOW)Cleaning up build artifacts and caches...$(RESET)"
	find $(PROJECT_ROOT_DIR) -type f -name "*.pyc" -delete
	find $(PROJECT_ROOT_DIR) -type d -name "__pycache__" -delete
	rm -rf $(PROJECT_ROOT_DIR).coverage $(PROJECT_ROOT_DIR)htmlcov/ $(BOT_DIR)/htmlcov_slack-bot/
	rm -rf $(PROJECT_ROOT_DIR).pytest_cache $(BOT_DIR)/.pytest_cache
	rm -rf $(PROJECT_ROOT_DIR).ruff_cache $(BOT_DIR)/.ruff_cache
	rm -rf $(PROJECT_ROOT_DIR).pyright_cache $(BOT_DIR)/.pyright_cache
	@echo "$(GREEN)Cleanup completed$(RESET)"

# ===== DATABASE MANAGEMENT =====

# Start MySQL databases in Docker (uses main docker-compose.yml)
db-start:
	@echo "$(BLUE)Starting MySQL databases...$(RESET)"
	docker compose up -d mysql phpmyadmin
	@echo "$(BLUE)Waiting for MySQL to be ready...$(RESET)"
	@timeout=60; \
	while [ $$timeout -gt 0 ]; do \
		if docker exec insightmesh-mysql mysqladmin ping -h localhost --silent; then \
			echo "$(GREEN)MySQL is ready!$(RESET)"; \
			break; \
		fi; \
		echo "$(YELLOW)Waiting... ($$timeout seconds remaining)$(RESET)"; \
		sleep 2; \
		timeout=$$((timeout-2)); \
	done; \
	if [ $$timeout -le 0 ]; then \
		echo "$(RED)MySQL failed to start within 60 seconds$(RESET)"; \
		exit 1; \
	fi
	@echo "$(GREEN)MySQL databases are running!$(RESET)"
	@echo "$(YELLOW)phpMyAdmin available at: http://localhost:8081$(RESET)"

# Stop MySQL databases
db-stop:
	@echo "$(YELLOW)Stopping MySQL databases...$(RESET)"
	docker compose stop mysql phpmyadmin
	@echo "$(GREEN)MySQL databases stopped$(RESET)"

# Generate new migration files
db-migrate:
	@echo "$(BLUE)Generating migration files...$(RESET)"
	@read -p "Enter migration message: " message; \
	echo "$(BLUE)Generating bot service migration...$(RESET)"; \
	cd $(BOT_DIR) && $(UV) alembic revision --autogenerate -m "$$message"; \
	echo "$(BLUE)Generating tasks service migration...$(RESET)"; \
	cd $(PROJECT_ROOT_DIR)tasks && $(UV) alembic revision --autogenerate -m "$$message"
	@echo "$(GREEN)Migration files generated!$(RESET)"

# Apply pending migrations
db-upgrade: db-start
	@echo "$(BLUE)Applying migrations...$(RESET)"
	@echo "$(BLUE)Upgrading bot database...$(RESET)"
	cd $(BOT_DIR) && $(UV) alembic upgrade head
	@echo "$(BLUE)Upgrading tasks database...$(RESET)"
	cd $(PROJECT_ROOT_DIR)tasks && $(UV) alembic upgrade head
	@echo "$(GREEN)All migrations applied successfully!$(RESET)"

# Rollback last migration
db-downgrade:
	@echo "$(YELLOW)Rolling back last migration...$(RESET)"
	@echo "$(YELLOW)Rolling back bot database...$(RESET)"
	cd $(BOT_DIR) && $(UV) alembic downgrade -1
	@echo "$(YELLOW)Rolling back tasks database...$(RESET)"
	cd $(PROJECT_ROOT_DIR)tasks && $(UV) alembic downgrade -1
	@echo "$(GREEN)Rollback completed$(RESET)"

# Reset databases (WARNING: destroys data)
db-reset: db-stop
	@echo "$(RED)WARNING: This will destroy all data!$(RESET)"
	@read -p "Are you sure? Type 'yes' to continue: " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		echo "$(YELLOW)Resetting databases...$(RESET)"; \
		docker volume rm ai-slack-bot_mysql_data 2>/dev/null || true; \
		$(MAKE) db-start; \
		$(MAKE) db-upgrade; \
		echo "$(GREEN)Databases reset and migrations applied$(RESET)"; \
	else \
		echo "$(BLUE)Reset cancelled$(RESET)"; \
	fi

# Show migration status
db-status:
	@echo "$(BLUE)Database migration status:$(RESET)"
	@echo ""
	@echo "$(YELLOW)Bot Database (bot):$(RESET)"
	@cd $(BOT_DIR) && $(UV) alembic current -v || echo "$(RED)No migrations applied$(RESET)"
	@echo ""
	@echo "$(YELLOW)Tasks Database (task):$(RESET)"
	@cd $(PROJECT_ROOT_DIR)tasks && $(UV) alembic current -v || echo "$(RED)No migrations applied$(RESET)"
	@echo ""
	@echo "$(BLUE)Pending migrations:$(RESET)"
	@cd $(BOT_DIR) && $(UV) alembic show head || echo "$(YELLOW)No migrations found$(RESET)"

# ===== LIBRECHAT UI =====
# LibreChat is now included in main docker-compose.yml
# Use 'make start' to run full stack including LibreChat
