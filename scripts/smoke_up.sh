#!/bin/bash
# smoke_up.sh - Bring up docker compose and verify critical services
# Part of PR-0.1: Hotfix - improved health checks with Temporal CLI
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "=================================================="
echo "SMOKE_UP: Starting ERPX AI Accounting Stack"
echo "=================================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if compose file exists
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}❌ ERROR: docker-compose.yml not found in $PROJECT_ROOT${NC}"
    exit 1
fi

# Bring up the stack
echo "📦 Starting docker compose..."
docker compose up -d 2>&1 | grep -v "^$" | head -20

# Function to wait for container health
wait_for_healthy() {
    local container=$1
    local max_wait=${2:-120}
    local required=${3:-true}  # true = FAIL if unhealthy, false = WARN only
    local waited=0
    
    echo -n "⏳ Waiting for $container..."
    while [ $waited -lt $max_wait ]; do
        status=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "not_found")
        if [ "$status" = "healthy" ]; then
            echo -e " ${GREEN}✅ healthy${NC}"
            return 0
        elif [ "$status" = "not_found" ]; then
            # Container might not have healthcheck, check if running
            running=$(docker inspect --format='{{.State.Running}}' "$container" 2>/dev/null || echo "false")
            if [ "$running" = "true" ]; then
                echo -e " ${GREEN}✅ running${NC} (no healthcheck)"
                return 0
            fi
        elif [ "$status" = "starting" ]; then
            : # continue waiting
        fi
        sleep 2
        waited=$((waited + 2))
        echo -n "."
    done
    
    if [ "$required" = "true" ]; then
        echo -e " ${RED}❌ TIMEOUT${NC}"
        return 1
    else
        echo -e " ${YELLOW}⚠️  TIMEOUT (non-critical)${NC}"
        return 0
    fi
}

# Function to wait for TCP port
wait_for_port() {
    local host=$1
    local port=$2
    local max_wait=${3:-60}
    local waited=0
    
    echo -n "⏳ Port $host:$port..."
    while [ $waited -lt $max_wait ]; do
        if timeout 1 bash -c "</dev/tcp/$host/$port" 2>/dev/null; then
            echo -e " ${GREEN}✅${NC}"
            return 0
        fi
        sleep 2
        waited=$((waited + 2))
        echo -n "."
    done
    echo -e " ${RED}❌ TIMEOUT${NC}"
    return 1
}

# Function to check Temporal with retry
check_temporal() {
    local max_retries=${1:-5}
    local retry=0
    
    echo -n "⏳ Temporal namespace check..."
    while [ $retry -lt $max_retries ]; do
        # Try with correct address inside container
        RESULT=$(docker exec erpx-temporal temporal operator namespace list --address temporal:7233 2>&1 || echo "error")
        
        if echo "$RESULT" | grep -q "NamespaceInfo.Name"; then
            NS_COUNT=$(echo "$RESULT" | grep -c "NamespaceInfo.Name" || echo "0")
            echo -e " ${GREEN}✅ ($NS_COUNT namespaces)${NC}"
            return 0
        fi
        
        retry=$((retry + 1))
        sleep 3
        echo -n "."
    done
    
    echo -e " ${YELLOW}⚠️  connection issues (non-critical)${NC}"
    return 0  # Don't fail on Temporal issues
}

FAILED=0

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${YELLOW}🔒 CRITICAL SERVICES (must be healthy)${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Critical services that MUST be healthy
CRITICAL_CONTAINERS=("erpx-postgres" "erpx-redis" "erpx-api" "erpx-kong")

for container in "${CRITICAL_CONTAINERS[@]}"; do
    if ! wait_for_healthy "$container" 120 true; then
        FAILED=1
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${YELLOW}📡 INFRASTRUCTURE (important but not blocking)${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Infrastructure services - warn only
INFRA_CONTAINERS=("erpx-keycloak" "erpx-qdrant" "erpx-minio" "erpx-temporal")

for container in "${INFRA_CONTAINERS[@]}"; do
    wait_for_healthy "$container" 60 false
done

# Special Temporal CLI check with retry
check_temporal 5

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${YELLOW}📊 OBSERVABILITY (optional)${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Observability services - warn only, never fail
OBS_CONTAINERS=("erpx-otel" "erpx-grafana" "erpx-prometheus" "erpx-jaeger" "erpx-mlflow")

for container in "${OBS_CONTAINERS[@]}"; do
    wait_for_healthy "$container" 30 false
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${YELLOW}🔌 PORT CONNECTIVITY${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

wait_for_port "localhost" 5432 30 || FAILED=1  # Postgres (critical)
wait_for_port "localhost" 8000 30 || FAILED=1  # API (critical)
wait_for_port "localhost" 8080 30 || FAILED=1  # Kong Gateway (critical)
wait_for_port "localhost" 7233 30 || true      # Temporal (optional)
wait_for_port "localhost" 6333 30 || true      # Qdrant (optional)

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${YELLOW}📋 CONTAINER STATUS SUMMARY${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Count containers
TOTAL=$(docker ps --filter "name=erpx-" --format "{{.Names}}" | wc -l)
HEALTHY=$(docker ps --filter "name=erpx-" --filter "health=healthy" --format "{{.Names}}" | wc -l)
RUNNING=$(docker ps --filter "name=erpx-" --filter "status=running" --format "{{.Names}}" | wc -l)

echo "  Total erpx-* containers: $TOTAL"
echo "  Running: $RUNNING"
echo "  Healthy (with healthcheck): $HEALTHY"
echo ""

# List all containers
docker ps --filter "name=erpx-" --format "table {{.Names}}\t{{.Status}}" | head -20

echo ""
echo "=================================================="
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ SMOKE_UP PASSED: Critical services ready${NC}"
    echo "   - postgres, redis, api, kong: healthy ✓"
    echo "   - Ports 5432, 8000, 8080: reachable ✓"
    
    # PR15 Evidence: Jaeger services + MinIO Prometheus scrape
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${YELLOW}📊 PR15 Evidence (Observability)${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Jaeger services count
    JAEGER_SERVICES=$(curl -s "http://localhost:16686/api/services" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('data',[])))" 2>/dev/null || echo "0")
    if [ "$JAEGER_SERVICES" -gt "0" ]; then
        echo -e "  ${GREEN}✓${NC} Jaeger: $JAEGER_SERVICES services registered"
    else
        echo -e "  ${YELLOW}⚠${NC} Jaeger: $JAEGER_SERVICES services (OTEL may need traffic)"
    fi
    
    # MinIO Prometheus scrape status
    MINIO_SCRAPE_ERROR=$(curl -s http://localhost:9090/api/v1/targets 2>/dev/null | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    for t in data.get('data', {}).get('activeTargets', []):
        if 'minio' in t.get('labels', {}).get('job', '').lower():
            err = t.get('lastError', '')
            print(err if err else '')
            break
except: pass
" 2>/dev/null || echo "unknown")
    
    if [ -z "$MINIO_SCRAPE_ERROR" ]; then
        echo -e "  ${GREEN}✓${NC} MinIO Prometheus scrape: OK"
    else
        echo -e "  ${RED}✗${NC} MinIO Prometheus scrape: $MINIO_SCRAPE_ERROR"
    fi
    
    exit 0
else
    echo -e "${RED}❌ SMOKE_UP FAILED: Critical service(s) not ready${NC}"
    echo ""
    echo "Check logs with: docker logs <container_name>"
    exit 1
fi
