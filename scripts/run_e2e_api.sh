#!/bin/bash
# ==============================================================================
# ERPX E2E API Startup Script
# Starts the Gateway API + Workers for E2E flow
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "============================================================"
echo "ERPX E2E API Startup"
echo "============================================================"

# Activate virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "Virtual environment activated"
fi

# Create required directories
mkdir -p data/uploads data/processed logs

# Install E2E dependencies if needed
pip install -q -r requirements-e2e.txt 2>/dev/null || true

# Export environment variables
export POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
export POSTGRES_PORT="${POSTGRES_PORT:-5432}"
export POSTGRES_USER="${POSTGRES_USER:-erp_user}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-erp_secret_2024}"
export POSTGRES_DB="${POSTGRES_DB:-erp_ai}"
export QDRANT_HOST="${QDRANT_HOST:-localhost}"
export QDRANT_PORT="${QDRANT_PORT:-6333}"
export API_HOST="${API_HOST:-0.0.0.0}"
export API_PORT="${API_PORT:-8000}"

echo ""
echo "Configuration:"
echo "  POSTGRES: $POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB"
echo "  QDRANT: $QDRANT_HOST:$QDRANT_PORT"
echo "  API: $API_HOST:$API_PORT"
echo ""

# Check if infrastructure is running
echo "Checking infrastructure..."

# Check Postgres
if ! pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -q 2>/dev/null; then
    echo "WARNING: PostgreSQL is not responding. Start it with:"
    echo "  cd infra && docker compose up -d postgres"
fi

# Check Qdrant
if ! curl -s "http://$QDRANT_HOST:$QDRANT_PORT/collections" > /dev/null 2>&1; then
    echo "WARNING: Qdrant is not responding. Start it with:"
    echo "  cd infra && docker compose up -d qdrant"
fi

echo ""
echo "Starting Gateway API..."
echo "  API docs: http://localhost:$API_PORT/docs"
echo "  Health: http://localhost:$API_PORT/health"
echo ""

# Start the API
python -m uvicorn apps.gateway_api.main:app --host "$API_HOST" --port "$API_PORT" --reload
