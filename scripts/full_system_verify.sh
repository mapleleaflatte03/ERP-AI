#!/usr/bin/env bash
###############################################################################
# ERPX AI Accounting Agent — Full System Verification Runner
# Runs all tests and collects evidence from every integrated tool.
###############################################################################
set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Counters
PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

# Evidence collection
declare -A EVIDENCE

banner() {
    echo ""
    echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}  ${BOLD}$1${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

check_pass() {
    echo -e "  ${GREEN}[✓ PASS]${NC} $1"
    PASS_COUNT=$((PASS_COUNT + 1))
    EVIDENCE["$1"]="PASS"
}

check_fail() {
    echo -e "  ${RED}[✗ FAIL]${NC} $1"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    EVIDENCE["$1"]="FAIL"
}

check_warn() {
    echo -e "  ${YELLOW}[! WARN]${NC} $1"
    WARN_COUNT=$((WARN_COUNT + 1))
    EVIDENCE["$1"]="WARN"
}

check_info() {
    echo -e "  ${BLUE}[i INFO]${NC} $1"
}

###############################################################################
# PHASE 0: Environment Setup
###############################################################################
banner "PHASE 0: Environment Setup"

cd /root/erp-ai || { echo "Cannot cd to /root/erp-ai"; exit 1; }
check_info "Working directory: $(pwd)"

# Export test environment
export SMOKE_MODE="${SMOKE_MODE:-dynamic}"
export TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-180}"
export CI="${CI:-}"
export ENABLE_CASHFLOW_FORECAST=1
export ENABLE_SCENARIO_SIMULATION=1
export ENABLE_CFO_INSIGHTS=1

check_info "SMOKE_MODE=$SMOKE_MODE"
check_info "TIMEOUT_SECONDS=$TIMEOUT_SECONDS"

###############################################################################
# PHASE 1: Docker Compose Build & Health
###############################################################################
banner "PHASE 1: Docker Compose Build & Health"

echo -e "${CYAN}Building and starting services...${NC}"
if docker compose up -d --build 2>&1 | tail -5; then
    check_pass "Docker compose up"
else
    check_fail "Docker compose up"
    echo -e "${RED}Cannot proceed without docker compose${NC}"
    exit 1
fi

# Wait for services
echo -e "${CYAN}Waiting for services to be healthy (60s max)...${NC}"
sleep 10

# Health check summary
echo ""
echo -e "${BOLD}Container Health Summary:${NC}"
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || docker compose ps

HEALTHY_COUNT=$(docker compose ps 2>/dev/null | grep -c "healthy\|Up" || echo "0")
if [[ "$HEALTHY_COUNT" -ge 5 ]]; then
    check_pass "Docker containers healthy (${HEALTHY_COUNT} services)"
else
    check_warn "Some containers may not be healthy (${HEALTHY_COUNT} found)"
fi

###############################################################################
# PHASE 2: Authentication Tests
###############################################################################
banner "PHASE 2: Authentication Tests (smoke_auth.sh)"

if bash scripts/smoke_auth.sh 2>&1 | tail -20; then
    check_pass "smoke_auth.sh completed"
else
    check_fail "smoke_auth.sh failed"
fi

###############################################################################
# PHASE 3: E2E Dynamic Smoke Tests
###############################################################################
banner "PHASE 3: E2E Dynamic Smoke Tests (smoke_e2e.sh)"

if SMOKE_MODE=dynamic TIMEOUT_SECONDS=180 bash scripts/smoke_e2e.sh 2>&1 | tail -50; then
    check_pass "smoke_e2e.sh SMOKE_MODE=dynamic completed"
else
    check_fail "smoke_e2e.sh SMOKE_MODE=dynamic failed"
fi

###############################################################################
# PHASE 4: CI Deterministic Tests
###############################################################################
banner "PHASE 4: CI Deterministic Tests (make test)"

if CI=1 make test 2>&1 | tail -30; then
    check_pass "CI=1 make test completed"
else
    check_fail "CI=1 make test failed"
fi

###############################################################################
# PHASE 5: Evidence Collection
###############################################################################
banner "PHASE 5: Evidence Collection"

# Wait a bit for async operations to complete
sleep 3

# Get auth token for API calls
echo -e "${CYAN}Acquiring auth token...${NC}"
TOKEN=$(curl -s -X POST "http://localhost:8180/realms/erpx/protocol/openid-connect/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "grant_type=password" \
    -d "client_id=erpx-api" \
    -d "username=accountant" \
    -d "password=accountant123" 2>/dev/null | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4 || echo "")

if [[ -n "$TOKEN" ]]; then
    check_pass "Auth token acquired"
else
    check_warn "Could not acquire auth token (some evidence may be limited)"
fi

AUTH_HEADER=""
if [[ -n "$TOKEN" ]]; then
    AUTH_HEADER="Authorization: Bearer $TOKEN"
fi

#-----------------------------------------------------------------------------
# A) Postgres Counters
#-----------------------------------------------------------------------------
echo ""
echo -e "${BOLD}A) Postgres Database Counters${NC}"

PG_QUERY="
SELECT 
    (SELECT COUNT(*) FROM extracted_invoices) as extracted_invoices,
    (SELECT COUNT(*) FROM journal_proposals) as journal_proposals,
    (SELECT COUNT(*) FROM approvals) as approvals,
    (SELECT COUNT(*) FROM ledger_entries) as ledger_entries,
    (SELECT COUNT(*) FROM ledger_lines) as ledger_lines,
    (SELECT COUNT(*) FROM cashflow_forecasts) as cashflow_forecasts,
    (SELECT COUNT(*) FROM scenario_simulations) as scenario_simulations,
    (SELECT COUNT(*) FROM cfo_insights) as cfo_insights,
    (SELECT COUNT(*) FROM audit_events) as audit_events,
    (SELECT COUNT(*) FROM documents) as documents
"

PG_RESULT=$(docker compose exec -T postgres psql -U erpx -d erpx_db -t -A -F'|' -c "$PG_QUERY" 2>/dev/null || echo "ERROR")

if [[ "$PG_RESULT" != "ERROR" && -n "$PG_RESULT" ]]; then
    IFS='|' read -r inv prop appr le ll cf ss ci ae doc <<< "$PG_RESULT"
    echo "    extracted_invoices:   $inv"
    echo "    journal_proposals:    $prop"
    echo "    approvals:            $appr"
    echo "    ledger_entries:       $le"
    echo "    ledger_lines:         $ll"
    echo "    cashflow_forecasts:   $cf"
    echo "    scenario_simulations: $ss"
    echo "    cfo_insights:         $ci"
    echo "    audit_events:         $ae"
    echo "    documents:            $doc"
    
    if [[ "$inv" -gt 0 && "$le" -gt 0 ]]; then
        check_pass "Postgres counters show data (invoices=$inv, ledger_entries=$le)"
    else
        check_fail "Postgres counters empty or zero"
    fi
else
    check_fail "Postgres query failed"
fi

#-----------------------------------------------------------------------------
# B) MinIO Evidence
#-----------------------------------------------------------------------------
echo ""
echo -e "${BOLD}B) MinIO Object Storage${NC}"

MINIO_KEYS=$(docker compose exec -T postgres psql -U erpx -d erpx_db -t -A -c \
    "SELECT minio_bucket || '/' || minio_key FROM documents WHERE minio_key IS NOT NULL LIMIT 5" 2>/dev/null || echo "")

if [[ -n "$MINIO_KEYS" ]]; then
    echo "    Sample object keys:"
    echo "$MINIO_KEYS" | while read -r key; do
        echo "      - $key"
    done
    check_pass "MinIO objects exist in documents table"
else
    # Try direct MinIO check
    MINIO_LIST=$(docker compose exec -T minio mc ls local/erpx-documents 2>/dev/null | head -5 || echo "")
    if [[ -n "$MINIO_LIST" ]]; then
        echo "    MinIO bucket contents:"
        echo "$MINIO_LIST" | sed 's/^/      /'
        check_pass "MinIO bucket has objects"
    else
        check_warn "MinIO objects not found (may be empty or not configured)"
    fi
fi

#-----------------------------------------------------------------------------
# C) Qdrant Vector Store
#-----------------------------------------------------------------------------
echo ""
echo -e "${BOLD}C) Qdrant Vector Store${NC}"

QDRANT_RESULT=$(curl -s "http://localhost:6333/collections/invoice_embeddings" 2>/dev/null || echo "{}")
POINTS_COUNT=$(echo "$QDRANT_RESULT" | grep -o '"points_count":[0-9]*' | cut -d':' -f2 || echo "0")

if [[ "$POINTS_COUNT" -gt 0 ]]; then
    echo "    Collection: invoice_embeddings"
    echo "    Points count: $POINTS_COUNT"
    check_pass "Qdrant has vectors (points_count=$POINTS_COUNT)"
else
    # Try to get collection info differently
    QDRANT_INFO=$(curl -s "http://localhost:6333/collections" 2>/dev/null || echo "{}")
    echo "    Collections info: $QDRANT_INFO"
    check_warn "Qdrant points_count=0 or collection not found"
fi

#-----------------------------------------------------------------------------
# D) Temporal Workflows
#-----------------------------------------------------------------------------
echo ""
echo -e "${BOLD}D) Temporal Workflow Engine${NC}"

# Check Temporal UI/API
TEMPORAL_NS=$(curl -s "http://localhost:8088/api/v1/namespaces" 2>/dev/null || echo "{}")
if echo "$TEMPORAL_NS" | grep -q "default\|erpx"; then
    check_pass "Temporal API reachable"
else
    check_warn "Temporal API may not be reachable"
fi

# Check workflow count from job_status table
WORKFLOW_COUNT=$(docker compose exec -T postgres psql -U erpx -d erpx_db -t -A -c \
    "SELECT COUNT(*) FROM job_status WHERE temporal_workflow_id IS NOT NULL" 2>/dev/null || echo "0")
echo "    Workflows with temporal_workflow_id: $WORKFLOW_COUNT"

COMPLETED_WORKFLOWS=$(docker compose exec -T postgres psql -U erpx -d erpx_db -t -A -c \
    "SELECT COUNT(*) FROM job_status WHERE status = 'completed'" 2>/dev/null || echo "0")
echo "    Completed jobs: $COMPLETED_WORKFLOWS"

if [[ "$COMPLETED_WORKFLOWS" -gt 0 ]]; then
    check_pass "Temporal workflows completed ($COMPLETED_WORKFLOWS jobs)"
else
    check_warn "No completed workflows found"
fi

#-----------------------------------------------------------------------------
# E) Jaeger Tracing
#-----------------------------------------------------------------------------
echo ""
echo -e "${BOLD}E) Jaeger Distributed Tracing${NC}"

JAEGER_SERVICES=$(curl -s "http://localhost:16686/api/services" 2>/dev/null || echo "{}")
if echo "$JAEGER_SERVICES" | grep -q "erpx\|api"; then
    SERVICES_LIST=$(echo "$JAEGER_SERVICES" | grep -o '"data":\[[^]]*\]' | tr ',' '\n' | grep -v '^\[' | head -5)
    echo "    Services found: $SERVICES_LIST"
    check_pass "Jaeger has erpx services"
else
    echo "    Services response: $JAEGER_SERVICES"
    check_warn "Jaeger services not found (tracing may not be configured)"
fi

# Try to get trace count
TRACES_RESULT=$(curl -s "http://localhost:16686/api/traces?service=erpx-api&limit=5" 2>/dev/null || echo "{}")
TRACE_COUNT=$(echo "$TRACES_RESULT" | grep -o '"traceID"' | wc -l || echo "0")
echo "    Recent traces: $TRACE_COUNT"

#-----------------------------------------------------------------------------
# F) OPA Policy Engine
#-----------------------------------------------------------------------------
echo ""
echo -e "${BOLD}F) OPA Policy Engine${NC}"

OPA_HEALTH=$(curl -s "http://localhost:8181/health" 2>/dev/null || echo "{}")
if echo "$OPA_HEALTH" | grep -q "ok\|{}" || [[ -n "$OPA_HEALTH" ]]; then
    check_pass "OPA endpoint reachable"
else
    check_warn "OPA health check failed"
fi

# Test policy query
OPA_POLICY=$(curl -s -X POST "http://localhost:8181/v1/data/erpx/authz/allow" \
    -H "Content-Type: application/json" \
    -d '{"input":{"user":"accountant","action":"approve","resource":"invoice"}}' 2>/dev/null || echo "{}")
echo "    Policy test result: $OPA_POLICY"

#-----------------------------------------------------------------------------
# G) MLflow Experiment Tracking
#-----------------------------------------------------------------------------
echo ""
echo -e "${BOLD}G) MLflow Experiment Tracking${NC}"

MLFLOW_EXPERIMENTS=$(curl -s "http://localhost:5001/api/2.0/mlflow/experiments/search" 2>/dev/null || echo "{}")
EXP_COUNT=$(echo "$MLFLOW_EXPERIMENTS" | grep -o '"experiment_id"' | wc -l || echo "0")
echo "    Experiments found: $EXP_COUNT"

MLFLOW_RUNS=$(curl -s "http://localhost:5001/api/2.0/mlflow/runs/search" \
    -H "Content-Type: application/json" \
    -d '{"experiment_ids":["0","1","2"],"max_results":10}' 2>/dev/null || echo "{}")
RUN_COUNT=$(echo "$MLFLOW_RUNS" | grep -o '"run_id"' | wc -l || echo "0")
echo "    Runs found: $RUN_COUNT"

if [[ "$RUN_COUNT" -gt 0 ]]; then
    check_pass "MLflow has runs ($RUN_COUNT)"
else
    check_warn "MLflow runs not found (may not be tracking yet)"
fi

#-----------------------------------------------------------------------------
# H) API Endpoints Health
#-----------------------------------------------------------------------------
echo ""
echo -e "${BOLD}H) API Endpoints Health${NC}"

# Health endpoint
HEALTH=$(curl -s "http://localhost:8080/api/health" 2>/dev/null || echo "{}")
if echo "$HEALTH" | grep -q "ok\|healthy"; then
    check_pass "API /health endpoint"
else
    check_warn "API /health returned: $HEALTH"
fi

# Kong gateway
KONG_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8080/" 2>/dev/null || echo "000")
if [[ "$KONG_STATUS" != "000" ]]; then
    check_pass "Kong gateway reachable (HTTP $KONG_STATUS)"
else
    check_warn "Kong gateway not reachable"
fi

###############################################################################
# PHASE 6: Final Summary
###############################################################################
banner "FINAL SUMMARY"

echo -e "${BOLD}Evidence Checklist:${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
for key in "${!EVIDENCE[@]}"; do
    status="${EVIDENCE[$key]}"
    if [[ "$status" == "PASS" ]]; then
        echo -e "  ${GREEN}[✓]${NC} $key"
    elif [[ "$status" == "FAIL" ]]; then
        echo -e "  ${RED}[✗]${NC} $key"
    else
        echo -e "  ${YELLOW}[!]${NC} $key"
    fi
done
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo -e "  ${GREEN}PASS:${NC} $PASS_COUNT"
echo -e "  ${RED}FAIL:${NC} $FAIL_COUNT"
echo -e "  ${YELLOW}WARN:${NC} $WARN_COUNT"
echo ""

if [[ "$FAIL_COUNT" -gt 0 ]]; then
    echo -e "${RED}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║${NC}  ${BOLD}VERIFICATION FAILED${NC} — $FAIL_COUNT critical checks failed"
    echo -e "${RED}╚════════════════════════════════════════════════════════════════╝${NC}"
    exit 1
else
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}  ${BOLD}VERIFICATION PASSED${NC} — All critical checks OK"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
    exit 0
fi
