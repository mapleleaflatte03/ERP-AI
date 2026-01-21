# ERPX AI Makefile
.PHONY: help fmt lint up down test smoke clean install

help:
	@echo "ERPX AI: make fmt|lint|up|down|test"

fmt:
	@echo "Formatting..."
	@ruff format .
	@echo "Done"

lint:
	@echo "Linting..."
	@ruff check . --fix
	@echo "Done"

check:
	@ruff check .
	@ruff format --check .

up:
	@docker compose up -d

down:
	@docker compose down

restart:
	@docker compose restart

logs:
	@docker compose logs -f --tail=100

ps:
	@docker compose ps

test: smoke

smoke:
	@echo "Running smoke tests..."
	@bash scripts/smoke_up.sh
	@bash scripts/smoke_auth.sh
	@bash scripts/smoke_e2e.sh
	@echo "All tests passed"

smoke-up:
	@bash scripts/smoke_up.sh

smoke-auth:
	@bash scripts/smoke_auth.sh

smoke-e2e:
	@bash scripts/smoke_e2e.sh

install:
	@pip install -U pip ruff pre-commit
	@pip install -r requirements.txt

clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true

db-shell:
	@docker exec -it erpx-postgres psql -U erpx -d erpx
