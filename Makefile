# Prism — Build & Deploy
# Usage: make <target>    or    nat prism <command>

COMPOSE       = docker compose
COMPOSE_PROD  = $(COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml
PRISM_IMAGE   = prism:latest
FRONT_IMAGE   = prism-frontend:latest

# ── Local Development ────────────────────────────────────────────────────────

.PHONY: dev
dev:                           ## Start backend + frontend in dev mode
	$(COMPOSE) up --build

.PHONY: dev-backend
dev-backend:                   ## Start only the backend (API + hot-reload)
	$(COMPOSE) up --build prism

.PHONY: dev-frontend
dev-frontend:                  ## Start only the frontend (Next.js dev)
	$(COMPOSE) up --build frontend

.PHONY: down
down:                          ## Stop all dev services
	$(COMPOSE) down

.PHONY: logs
logs:                          ## Tail logs from all services
	$(COMPOSE) logs -f

.PHONY: logs-backend
logs-backend:                  ## Tail backend logs only
	$(COMPOSE) logs -f prism

.PHONY: logs-frontend
logs-frontend:                 ## Tail frontend logs only
	$(COMPOSE) logs -f frontend

# ── Build ────────────────────────────────────────────────────────────────────

.PHONY: build
build:                         ## Build all Docker images
	$(COMPOSE_PROD) build

.PHONY: build-backend
build-backend:                 ## Build backend image only
	docker build -t $(PRISM_IMAGE) .

.PHONY: build-frontend
build-frontend:                ## Build frontend image only
	docker build -t $(FRONT_IMAGE) ./frontend

# ── Production (local) ───────────────────────────────────────────────────────

.PHONY: prod
prod:                          ## Start production stack locally
	$(COMPOSE_PROD) up -d

.PHONY: prod-down
prod-down:                     ## Stop production stack
	$(COMPOSE_PROD) down

.PHONY: prod-logs
prod-logs:                     ## Tail production logs
	$(COMPOSE_PROD) logs -f

.PHONY: prod-status
prod-status:                   ## Show running containers and health
	$(COMPOSE_PROD) ps

.PHONY: prod-restart
prod-restart:                  ## Rebuild and restart production stack
	$(COMPOSE_PROD) up -d --build

# ── Cloud Deploy ─────────────────────────────────────────────────────────────

DEPLOY_HOST  ?= $(PRISM_DEPLOY_HOST)
DEPLOY_DIR   ?= ~/prism

.PHONY: cloud-push
cloud-push:                    ## Build images and push to remote host
	@test -n "$(DEPLOY_HOST)" || { echo "  Set DEPLOY_HOST or PRISM_DEPLOY_HOST"; exit 1; }
	@echo "  Building images..."
	$(COMPOSE_PROD) build
	@echo "  Saving images..."
	docker save $(PRISM_IMAGE) $(FRONT_IMAGE) | gzip > /tmp/prism-images.tar.gz
	@echo "  Pushing to $(DEPLOY_HOST)..."
	rsync -azP /tmp/prism-images.tar.gz $(DEPLOY_HOST):$(DEPLOY_DIR)/
	rsync -az docker-compose.yml docker-compose.prod.yml $(DEPLOY_HOST):$(DEPLOY_DIR)/
	@rm -f /tmp/prism-images.tar.gz
	@echo "  Done. Run 'make cloud-up' to start."

.PHONY: cloud-load
cloud-load:                    ## Load images on remote host
	@test -n "$(DEPLOY_HOST)" || { echo "  Set DEPLOY_HOST or PRISM_DEPLOY_HOST"; exit 1; }
	ssh $(DEPLOY_HOST) 'cd $(DEPLOY_DIR) && gunzip -c prism-images.tar.gz | docker load'

.PHONY: cloud-up
cloud-up:                      ## Start production stack on remote host
	@test -n "$(DEPLOY_HOST)" || { echo "  Set DEPLOY_HOST or PRISM_DEPLOY_HOST"; exit 1; }
	ssh $(DEPLOY_HOST) 'cd $(DEPLOY_DIR) && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d'

.PHONY: cloud-down
cloud-down:                    ## Stop production stack on remote host
	@test -n "$(DEPLOY_HOST)" || { echo "  Set DEPLOY_HOST or PRISM_DEPLOY_HOST"; exit 1; }
	ssh $(DEPLOY_HOST) 'cd $(DEPLOY_DIR) && docker compose -f docker-compose.yml -f docker-compose.prod.yml down'

.PHONY: cloud-status
cloud-status:                  ## Show remote container status and health
	@test -n "$(DEPLOY_HOST)" || { echo "  Set DEPLOY_HOST or PRISM_DEPLOY_HOST"; exit 1; }
	ssh $(DEPLOY_HOST) 'cd $(DEPLOY_DIR) && docker compose -f docker-compose.yml -f docker-compose.prod.yml ps'

.PHONY: cloud-logs
cloud-logs:                    ## Tail remote logs
	@test -n "$(DEPLOY_HOST)" || { echo "  Set DEPLOY_HOST or PRISM_DEPLOY_HOST"; exit 1; }
	ssh $(DEPLOY_HOST) 'cd $(DEPLOY_DIR) && docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f'

.PHONY: cloud-deploy
cloud-deploy: cloud-push cloud-load cloud-up  ## Full deploy: build → push → load → start

# ── Testing ──────────────────────────────────────────────────────────────────

.PHONY: test
test:                          ## Run all tests (backend + frontend)
	cd frontend && npm test
	pytest tests/

.PHONY: test-frontend
test-frontend:                 ## Run frontend tests only
	cd frontend && npm test

.PHONY: test-backend
test-backend:                  ## Run backend tests only
	pytest tests/

# ── Utilities ────────────────────────────────────────────────────────────────

.PHONY: clean
clean:                         ## Remove build artifacts and stopped containers
	$(COMPOSE) down --rmi local --volumes --remove-orphans 2>/dev/null || true
	rm -rf frontend/.next frontend/node_modules/.cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

.PHONY: shell-backend
shell-backend:                 ## Open shell in backend container
	$(COMPOSE) exec prism bash

.PHONY: shell-frontend
shell-frontend:                ## Open shell in frontend container
	$(COMPOSE) exec frontend sh

.PHONY: db-migrate
db-migrate:                    ## Run Alembic migrations
	$(COMPOSE) exec prism alembic upgrade head

.PHONY: help
help:                          ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
