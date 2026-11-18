# =============================================================================
# RAG Platform — Root Makefile
# =============================================================================
# Prerequisites: Docker, Docker Compose v2, Python 3.11+, Node.js 20+
#
# Targets:
#   make up       — start infrastructure containers (Postgres, Redis, Qdrant)
#   make down     — stop and remove infrastructure containers
#   make migrate  — run Alembic migrations against the running Postgres
#   make test     — run all service unit tests
#   make lint     — run ruff linter across all Python services
#   make format   — run ruff formatter across all Python services
#   make logs     — tail logs from all infrastructure containers
#   make ps       — show container status
#   make shell-db — open a psql shell inside the Postgres container
# =============================================================================

.PHONY: up down migrate test lint format logs ps shell-db help

# ---- Config ------------------------------------------------------------------
COMPOSE_FILE := docker-compose.dev.yml
ENV_FILE     := .env
PYTHON       := python3

# Load .env if it exists so Make targets can reference vars
ifneq (,$(wildcard $(ENV_FILE)))
  include $(ENV_FILE)
  export
endif

# ---- Infrastructure ----------------------------------------------------------

## up: Start infrastructure containers (Postgres, Redis, Qdrant)
up:
	@echo "▶  Starting RAG Platform infrastructure..."
	@if [ ! -f $(ENV_FILE) ]; then \
		echo "ERROR: $(ENV_FILE) not found. Run: cp .env.example .env and fill in values."; \
		exit 1; \
	fi
	docker compose -f $(COMPOSE_FILE) up -d
	@echo "✓  Containers started. Run 'make ps' to check status."

## down: Stop and remove infrastructure containers (volumes preserved)
down:
	@echo "▶  Stopping RAG Platform infrastructure..."
	docker compose -f $(COMPOSE_FILE) down
	@echo "✓  Containers stopped."

## down-v: Stop containers AND remove all volumes (DESTRUCTIVE)
down-v:
	@echo "⚠  WARNING: This will destroy all persistent data."
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	docker compose -f $(COMPOSE_FILE) down -v
	@echo "✓  Containers and volumes removed."

## ps: Show status of infrastructure containers
ps:
	docker compose -f $(COMPOSE_FILE) ps

## logs: Tail logs from all infrastructure containers
logs:
	docker compose -f $(COMPOSE_FILE) logs -f

# ---- Database ----------------------------------------------------------------

## migrate: Run Alembic database migrations
migrate:
	@echo "▶  Running Alembic migrations..."
	@if ! docker compose -f $(COMPOSE_FILE) ps postgres | grep -q "healthy"; then \
		echo "ERROR: Postgres container is not healthy. Run 'make up' first."; \
		exit 1; \
	fi
	cd data/postgres && $(PYTHON) -m alembic upgrade head
	@echo "✓  Migrations applied."

## migrate-create: Create a new Alembic migration (MSG=<message>)
migrate-create:
	@if [ -z "$(MSG)" ]; then echo "ERROR: Set MSG=<migration message>"; exit 1; fi
	cd data/postgres && $(PYTHON) -m alembic revision --autogenerate -m "$(MSG)"

## shell-db: Open a psql shell inside the Postgres container
shell-db:
	docker compose -f $(COMPOSE_FILE) exec postgres \
		psql -U $(POSTGRES_USER) -d $(POSTGRES_DB)

# ---- Testing -----------------------------------------------------------------

## test: Run all service unit tests
test:
	@echo "▶  Running unit tests across all services..."
	@FAILED=0; \
	for service in services/gateway services/auth-service services/admin-config-service \
	               services/ingestion-service services/retrieval-service \
	               services/llm-orchestrator-service services/chat-service \
	               services/notification-service; do \
		if [ -f "$$service/pyproject.toml" ] || [ -f "$$service/setup.py" ]; then \
			echo "  Testing $$service ..."; \
			(cd $$service && $(PYTHON) -m pytest tests/ -q --tb=short) || FAILED=1; \
		fi; \
	done; \
	for lib in shared-libs/schemas shared-libs/auth-middleware shared-libs/observability; do \
		if [ -f "$$lib/pyproject.toml" ] || [ -f "$$lib/setup.py" ]; then \
			echo "  Testing $$lib ..."; \
			(cd $$lib && $(PYTHON) -m pytest tests/ -q --tb=short) || FAILED=1; \
		fi; \
	done; \
	for pkg in ai-core/parsing ai-core/chunking ai-core/embedding ai-core/reranking ai-core/llm_router; do \
		if [ -f "$$pkg/pyproject.toml" ] || [ -f "$$pkg/setup.py" ]; then \
			echo "  Testing $$pkg ..."; \
			(cd $$pkg && $(PYTHON) -m pytest tests/ -q --tb=short) || FAILED=1; \
		fi; \
	done; \
	if [ $$FAILED -ne 0 ]; then echo "✗  Some tests failed."; exit 1; fi; \
	echo "✓  All tests passed."

# ---- Code Quality ------------------------------------------------------------

## lint: Run ruff linter across all Python source
lint:
	@echo "▶  Linting Python sources with ruff..."
	ruff check services/ ai-core/ shared-libs/ data/
	@echo "✓  Lint complete."

## format: Auto-format Python sources with ruff
format:
	@echo "▶  Formatting Python sources with ruff..."
	ruff format services/ ai-core/ shared-libs/ data/
	@echo "✓  Formatting complete."

# ---- Help --------------------------------------------------------------------

## help: Print this help message
help:
	@echo ""
	@echo "RAG Platform — Available Make Targets"
	@echo "======================================"
	@grep -E '^## ' Makefile | sed 's/## /  /'
	@echo ""
