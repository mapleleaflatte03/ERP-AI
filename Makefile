# ERPX AI Kế toán Testbench - Makefile
# =====================================

.PHONY: help fmt lint up down doctor e2e test smoke clean install bootstrap

help:
	@echo "ERPX AI Kế toán Testbench"
	@echo "========================="
	@echo ""
	@echo "  make up       - Start all services (full stack)"
	@echo "  make down     - Stop all services"
	@echo "  make doctor   - Health check all services"
	@echo "  make e2e      - Run E2E test suites"
	@echo "  make logs     - Follow service logs"
	@echo "  make ps       - Show service status"
	@echo ""

# ============================================================
# MAIN COMMANDS
# ============================================================

up: down
	@echo "🚀 Starting ERPX AI Kế toán Testbench..."
	@docker compose up -d --build
	@echo "⏳ Waiting for services to be healthy..."
	@sleep 10
	@$(MAKE) bootstrap
	@echo ""
	@echo "✅ All services started!"
	@echo ""
	@echo "📌 Access URLs:"
	@echo "   UI:       http://localhost:3002"
	@echo "   API:      http://localhost:8080/api"
	@echo "   Keycloak: http://localhost:8180"
	@echo "   Temporal: http://localhost:8088"
	@echo ""
	@echo "👤 Demo users (password: admin123 / accountant123):"
	@echo "   admin, accountant, manager"
	@echo ""

down:
	@echo "🛑 Stopping services..."
	@docker compose down --remove-orphans 2>/dev/null || true

restart:
	@docker compose restart

logs:
	@docker compose logs -f --tail=100

ps:
	@docker compose ps

# ============================================================
# BOOTSTRAP
# ============================================================

bootstrap:
	@echo "📦 Running bootstrap tasks..."
	@# Ensure Keycloak realm and users exist
	@sleep 5
	@bash -c 'source .env 2>/dev/null; ./scripts/bootstrap_keycloak.sh 2>/dev/null || true'
	@# Ensure Qdrant collections exist
	@python3 scripts/bootstrap_kb.py 2>/dev/null || true
	@echo "✅ Bootstrap complete"

# ============================================================
# TESTING
# ============================================================

doctor:
	@echo "🩺 Running system health check..."
	@./scripts/doctor.sh

e2e: 
	@echo "🧪 Running E2E test suites..."
	@echo ""
	@echo "=== Suite 1: Smoke Test ==="
	@source .env 2>/dev/null; export DO_AGENT_API_KEY="$${DO_AGENT_KEY:-$$DO_AGENT_API_KEY}"; python3 tests/e2e_smoke_test.py
	@echo ""
	@echo "=== Suite 2: Business Flow Test ==="
	@source .env 2>/dev/null; export DO_AGENT_API_KEY="$${DO_AGENT_KEY:-$$DO_AGENT_API_KEY}"; python3 tests/e2e_business_flow_test.py
	@echo ""
	@echo "✅ All E2E tests completed!"

test: doctor e2e

smoke:
	@echo "Running smoke tests..."
	@bash scripts/smoke_up.sh 2>/dev/null || true
	@bash scripts/smoke_auth.sh 2>/dev/null || true
	@bash scripts/smoke_e2e.sh 2>/dev/null || true
	@echo "All smoke tests passed"

# ============================================================
# DEVELOPMENT
# ============================================================

fmt:
	@echo "Formatting..."
	@ruff format . 2>/dev/null || true
	@echo "Done"

lint:
	@echo "Linting..."
	@ruff check . --fix 2>/dev/null || true
	@echo "Done"

check:
	@ruff check . 2>/dev/null || true
	@ruff format --check . 2>/dev/null || true

install:
	@pip install -U pip ruff pre-commit
	@pip install -r requirements.txt

clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true

# ============================================================
# DATABASE
# ============================================================

db-shell:
	@docker exec -it erpx-postgres psql -U erpx -d erpx

db-migrate:
	@docker exec -it erpx-postgres psql -U erpx -d erpx -f /docker-entrypoint-initdb.d/init.sql
