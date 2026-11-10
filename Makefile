SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

ENV_FILE ?= backend/.env
MODE ?= dev
COMPOSE ?= docker compose --env-file $(ENV_FILE)
PY := uv run --frozen python
MANAGE := $(PY) backend/manage.py
EMPTY_ENV := DATABASE_URL= REDIS_URL= CELERY_BROKER_URL= CELERY_RESULT_BACKEND=

export UV_PROJECT_ENVIRONMENT := $(CURDIR)/.venv

.PHONY: help doctor env sync setup dev dev-lite worker migrate makemigrations \
	shell superuser cleanup check test test-py test-js test-integration \
	infra-up clamav-wait up down clean clean-all logs ps

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n\nTargets:\n"} /^[a-zA-Z_-]+:.*?##/ {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

doctor: ## Check tooling and configuration (MODE=dev|test|prod)
	@ENV_FILE=$(ENV_FILE) ./scripts/doctor.sh $(MODE)

env: ## Create backend/.env and fill blank local-development values
	@./scripts/setup-env.sh $(ENV_FILE)

sync: ## Install the locked Python dependencies
	@uv sync --frozen

setup: ## One-time onboarding: env, dependencies, infrastructure, migrations
	@$(MAKE) env
	@$(MAKE) sync
	@$(MAKE) infra-up
	@$(MAKE) migrate
	@$(MAKE) doctor MODE=dev
	@echo ""
	@echo "Setup complete. Next: add your ImageKit keys to $(ENV_FILE), then run 'make dev'."

run: ## Run Django + Celery on the host with Postgres, Redis and ClamAV in Docker
	@$(MAKE) env
	@./scripts/dev.sh

dev-lite: ## Run Django on SQLite with eager Celery and ClamAV only
	@$(MAKE) env
	@$(COMPOSE) up -d clamav
	@$(MAKE) clamav-wait
	@$(EMPTY_ENV) $(MANAGE) migrate --noinput
	@$(EMPTY_ENV) $(MANAGE) runserver

worker: ## Run a host Celery worker (requires make infra-up)
	@cd backend && uv run --frozen celery -A config worker -l info --concurrency=2

migrate: ## Apply database migrations
	@$(MANAGE) migrate --noinput

makemigrations: ## Create new migrations
	@$(MANAGE) makemigrations

shell: ## Open the Django shell
	@$(MANAGE) shell

superuser: ## Create a Django superuser
	@$(MANAGE) createsuperuser

cleanup: ## Remove expired quarantine files and orphaned records
	@$(MANAGE) cleanup_quarantine

check: ## Run Django checks and verify migrations are committed
	@$(EMPTY_ENV) $(MANAGE) check
	@$(EMPTY_ENV) $(MANAGE) makemigrations --check --dry-run

test: test-py test-js ## Run Python and JavaScript tests

test-py: ## Run Python tests on SQLite with eager Celery
	@$(EMPTY_ENV) $(MANAGE) test videos accounts config.tests

test-js: ## Run the shared validation JavaScript tests
	@node --test backend/videos/tests_js

test-integration: ## Run the real worker/Redis/ClamAV integration test
	@$(MAKE) infra-up
	@DB_PASSWORD="$$(sed -n 's/^DB_PASSWORD=//p' $(ENV_FILE) | head -n1 | sed -E 's/[[:space:]]+#.*$$//' | tr -d '\"')"; \
	DB_PASSWORD="$${DB_PASSWORD:-devpassword}"; \
	DATABASE_URL="postgres://vplatform:$$DB_PASSWORD@127.0.0.1:5432/vplatform" \
	REDIS_URL=redis://127.0.0.1:6379/0 \
	CELERY_BROKER_URL=redis://127.0.0.1:6379/1 \
	CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/2 \
	CLAMAV_HOST=127.0.0.1 \
	CLAMAV_PORT=3310 \
	RUN_INTEGRATION=1 \
	$(MANAGE) test videos.tests_integration

infra-up: ## Start Postgres, Redis and ClamAV and wait for readiness
	@$(COMPOSE) up -d --wait --wait-timeout 120 postgres redis
	@$(COMPOSE) up -d clamav
	@$(MAKE) clamav-wait

clamav-wait: ## Wait until ClamAV responds to ping
	@echo "==> Waiting for ClamAV (first run downloads signatures)..."
	@timeout 900 bash -c 'until $(COMPOSE) exec -T clamav clamdscan --ping 1 >/dev/null 2>&1; do sleep 5; done' \
		|| { echo "ClamAV did not become ready. Check: $(COMPOSE) logs clamav" >&2; exit 1; }

up: ## Build and run the whole stack in Docker (hardened in Phase 2)
	@$(COMPOSE) up -d --build

down: ## Stop and remove containers (volumes are kept)
	@$(COMPOSE) down --remove-orphans

clean: ## Remove containers and locally built images (volumes are kept)
	@$(COMPOSE) down --remove-orphans --rmi local

clean-all: ## Delete containers, images, volumes and local development data
	@printf "This deletes Postgres/Redis/ClamAV volumes, backend/db.sqlite3 and quarantine files.\n"
	@read -r -p "Type 'yes' to continue: " answer && [ "$$answer" = "yes" ]
	@$(COMPOSE) down --remove-orphans --rmi local -v
	@rm -f backend/db.sqlite3
	@find backend/quarantine -mindepth 1 -delete 2>/dev/null || true

logs: ## Follow container logs
	@$(COMPOSE) logs -f --tail=100

ps: ## Show container status
	@$(COMPOSE) ps
