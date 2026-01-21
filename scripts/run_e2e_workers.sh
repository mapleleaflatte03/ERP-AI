#!/bin/bash
# ==============================================================================
# ERPX E2E Worker Startup Script
# Starts the Pipeline Worker + Outbox Dispatcher
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "============================================================"
echo "ERPX E2E Workers Startup"
echo "============================================================"

# Activate virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "Virtual environment activated"
fi

# Create required directories
mkdir -p data/uploads data/processed logs

# Export environment variables
export POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
export POSTGRES_PORT="${POSTGRES_PORT:-5432}"
export POSTGRES_USER="${POSTGRES_USER:-erp_user}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-erp_secret_2024}"
export POSTGRES_DB="${POSTGRES_DB:-erp_ai}"
export QDRANT_HOST="${QDRANT_HOST:-localhost}"
export QDRANT_PORT="${QDRANT_PORT:-6333}"
export WORKER_POLL_INTERVAL="${WORKER_POLL_INTERVAL:-5}"
export DISPATCHER_POLL_INTERVAL="${DISPATCHER_POLL_INTERVAL:-2}"

echo ""
echo "Configuration:"
echo "  POSTGRES: $POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB"
echo "  QDRANT: $QDRANT_HOST:$QDRANT_PORT"
echo "  Worker Poll: ${WORKER_POLL_INTERVAL}s"
echo "  Dispatcher Poll: ${DISPATCHER_POLL_INTERVAL}s"
echo ""

MODE="${1:-all}"

case "$MODE" in
    pipeline)
        echo "Starting Pipeline Worker only..."
        python -m apps.workers.pipeline_worker
        ;;
    dispatcher)
        echo "Starting Outbox Dispatcher only..."
        python -m apps.workers.outbox_dispatcher
        ;;
    all|*)
        echo "Starting both workers in background..."
        echo "  - Pipeline Worker (PID in logs/pipeline_worker.pid)"
        echo "  - Outbox Dispatcher (PID in logs/outbox_dispatcher.pid)"
        echo ""
        
        # Start dispatcher in background
        python -m apps.workers.outbox_dispatcher &
        echo $! > logs/outbox_dispatcher.pid
        echo "Outbox Dispatcher started (PID: $(cat logs/outbox_dispatcher.pid))"
        
        # Start pipeline worker in foreground
        python -m apps.workers.pipeline_worker
        ;;
esac
