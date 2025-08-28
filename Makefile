# Simple Makefile for Insight Mesh Slack Bot

PYTHON ?= python3
PIP ?= pip3
PROJECT_ROOT := $(CURDIR)/src
ENV_FILE := $(CURDIR)/.env
IMAGE ?= insight-mesh-slack-bot

.PHONY: help install check-env run test docker-build docker-run clean

help:
	@echo "Targets:"
	@echo "  install       Install Python dependencies"
	@echo "  run           Run the bot (standalone)"
	@echo "  test          Run test suite"
	@echo "  docker-build  Build Docker image"
	@echo "  docker-run    Run Docker container with .env"
	@echo "  clean         Remove caches and build artifacts"

install:
	$(PIP) install -r $(PROJECT_ROOT)/requirements.txt

check-env:
	@if [ ! -f $(ENV_FILE) ]; then \
		echo "Error: .env not found at $(ENV_FILE)"; \
		echo "Create it with SLACK_BOT_TOKEN, SLACK_APP_TOKEN, LLM_API_URL, LLM_API_KEY, LLM_MODEL"; \
		exit 1; \
	fi

run: check-env
	cd $(PROJECT_ROOT) && $(PYTHON) app.py

test:
	PYTHONPATH=$(PROJECT_ROOT) pytest -q $(PROJECT_ROOT)/tests

docker-build:
	docker build -f $(PROJECT_ROOT)/Dockerfile -t $(IMAGE) $(PROJECT_ROOT)

docker-run: check-env
	docker run --rm --env-file $(ENV_FILE) --name $(IMAGE) $(IMAGE)

clean:
	rm -rf $(PROJECT_ROOT)/__pycache__ $(PROJECT_ROOT)/*/__pycache__
	rm -rf $(PROJECT_ROOT)/.pytest_cache $(PROJECT_ROOT)/htmlcov_slack-bot
