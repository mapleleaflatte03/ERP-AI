#!/bin/bash
# ============================================================
# AI Agent Kế toán - Doctor Script
# Kiểm tra sức khỏe toàn bộ hệ thống
# ============================================================

# Don't exit on errors - we want to check everything
set +e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
PASS=0
FAIL=0
WARN=0

# Helper functions
check() {
    local name="$1"
    local result="$2"
    local expected="${3:-0}"
    
    if [ "$result" -eq "$expected" ] 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $name"
        ((PASS++))
        return 0
    else
        echo -e "  ${RED}✗${NC} $name"
        ((FAIL++))
        return 1
    fi
}

warn() {
    local name="$1"
    echo -e "  ${YELLOW}⚠${NC} $name"
    ((WARN++))
}

section() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}▶ $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

echo ""
echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       AI AGENT KẾ TOÁN - SYSTEM HEALTH CHECK              ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"

# ============================================================
section "1. Docker Containers"
# ============================================================

echo "  Checking container status..."

# Core services
containers=(
    "erpx-api:FastAPI Backend"
    "erpx-worker:Temporal Worker"
    "erpx-temporal:Temporal Server"
    "erpx-postgres:PostgreSQL"
    "erpx-redis:Redis"
    "erpx-minio:MinIO Object Storage"
    "erpx-qdrant:Qdrant Vector DB"
    "erpx-keycloak:Keycloak Auth"
    "erpx-kong:Kong Gateway"
    "erpx-ui:Accounting UI"
)

for container_info in "${containers[@]}"; do
    IFS=':' read -r container name <<< "$container_info"
    status=$(docker inspect -f '{{.State.Health.Status}}' "$container" 2>/dev/null || echo "missing")
    if [ "$status" = "healthy" ]; then
        check "$name ($container)" 0
    elif [ "$status" = "starting" ]; then
        warn "$name ($container) - starting"
    else
        check "$name ($container) - $status" 1
    fi
done

# ============================================================
section "2. Network Endpoints"
# ============================================================

# API Health
echo "  Testing API endpoints..."
api_health=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || echo "000")
check "Backend API /health (8000)" $([ "$api_health" = "200" ] && echo 0 || echo 1)

# Kong Gateway - check direct endpoint (unauthorized is OK, means Kong is routing)
kong_health=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/health 2>/dev/null || echo "000")
if [ "$kong_health" = "200" ] || [ "$kong_health" = "401" ]; then
    check "Kong Gateway routing (8080)" 0
else
    check "Kong Gateway routing (8080)" 1
fi

# Keycloak OIDC
kc_health=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8180/realms/erpx/.well-known/openid-configuration 2>/dev/null || echo "000")
check "Keycloak OIDC Endpoint (8180)" $([ "$kc_health" = "200" ] && echo 0 || echo 1)

# UI
ui_health=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3002/ 2>/dev/null || echo "000")
check "Accounting UI (3002)" $([ "$ui_health" = "200" ] && echo 0 || echo 1)

# Temporal UI
temporal_ui=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8088/ 2>/dev/null || echo "000")
check "Temporal UI (8088)" $([ "$temporal_ui" = "200" ] || [ "$temporal_ui" = "302" ] && echo 0 || echo 1)

# ============================================================
section "3. Database Connectivity"
# ============================================================

# PostgreSQL - use correct user
pg_check=$(docker exec erpx-postgres psql -U erpx -d erpx -c "SELECT 1" 2>/dev/null | grep -c "1 row" || echo "0")
check "PostgreSQL connection" $([ "$pg_check" -gt 0 ] && echo 0 || echo 1)

# Check tables
tables=$(docker exec erpx-postgres psql -U erpx -d erpx -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'" 2>/dev/null | tr -d ' ' || echo "0")
tables=${tables:-0}
if [ "$tables" -gt 5 ] 2>/dev/null; then
    check "Database tables exist ($tables tables)" 0
else
    check "Database tables exist ($tables tables)" 1
fi

# Redis
redis_ping=$(docker exec erpx-redis redis-cli ping 2>/dev/null || echo "FAIL")
check "Redis PING" $([ "$redis_ping" = "PONG" ] && echo 0 || echo 1)

# ============================================================
section "4. Object Storage (MinIO)"
# ============================================================

# MinIO health
minio_health=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:9000/minio/health/live 2>/dev/null || echo "000")
check "MinIO health endpoint" $([ "$minio_health" = "200" ] && echo 0 || echo 1)

# Check buckets
buckets=$(docker exec erpx-minio mc ls local/ 2>/dev/null | wc -l || echo "0")
if [ "$buckets" -gt 0 ] 2>/dev/null; then
    check "MinIO buckets exist ($buckets buckets)" 0
else
    warn "MinIO: No buckets found"
fi

# ============================================================
section "5. Message Queue (Temporal)"
# ============================================================

# Temporal - check via grpcurl or API
temporal_health=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8088/api/v1/namespaces" 2>/dev/null || echo "000")
check "Temporal API (8088)" $([ "$temporal_health" = "200" ] && echo 0 || echo 1)

# Check default namespace via docker exec
ns_check=$(docker exec erpx-temporal temporal operator namespace list 2>/dev/null | grep -c "default" || echo "0")
if [ "$ns_check" -gt 0 ] 2>/dev/null; then
    check "Temporal default namespace" 0
else
    warn "Temporal default namespace - may need init"
fi

# ============================================================
section "6. Vector Database (Qdrant)"
# ============================================================

# Qdrant health - check for "passed"
qdrant_health=$(curl -s http://localhost:6333/healthz 2>/dev/null | grep -c "passed" || echo "0")
check "Qdrant health" $([ "$qdrant_health" -gt 0 ] && echo 0 || echo 1)

# Collections
collections=$(curl -s http://localhost:6333/collections 2>/dev/null | grep -c "collections" || echo "0")
check "Qdrant API accessible" $([ "$collections" -gt 0 ] && echo 0 || echo 1)

# ============================================================
section "7. Authentication (Keycloak)"
# ============================================================

# Get admin token
admin_token=$(curl -s -X POST "http://localhost:8180/realms/master/protocol/openid-connect/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=admin" \
    -d "password=admin_secret" \
    -d "grant_type=password" \
    -d "client_id=admin-cli" 2>/dev/null | grep -o '"access_token":"[^"]*"' | wc -c || echo "0")

check "Keycloak admin login" $([ "$admin_token" -gt 50 ] && echo 0 || echo 1)

# Check realm exists
realm_check=$(curl -s "http://localhost:8180/realms/erpx" 2>/dev/null | grep -c "erpx" || echo "0")
check "Keycloak 'erpx' realm" $([ "$realm_check" -gt 0 ] && echo 0 || echo 1)

# ============================================================
section "8. LLM Service"
# ============================================================

# Check DO Agent endpoint (LLM) from env
llm_configured=$(grep -r "LLM_BASE_URL\|OPENAI_API\|AGENT_API" /root/erp-ai/.env* 2>/dev/null | head -1 || echo "")
if [ -n "$llm_configured" ]; then
    check "LLM Service configured" 0
else
    warn "LLM Service not configured in .env"
fi

# ============================================================
section "9. API Endpoints (Functional Tests)"
# ============================================================

# Jobs endpoint (works without auth)
jobs_check=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/v1/jobs?limit=5" 2>/dev/null || echo "000")
check "GET /v1/jobs" $([ "$jobs_check" = "200" ] && echo 0 || echo 1)

# Approvals endpoint  
approvals_check=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/v1/approvals 2>/dev/null || echo "000")
check "GET /v1/approvals" $([ "$approvals_check" = "200" ] && echo 0 || echo 1)

# Upload endpoint exists (should return 405 for GET)
upload_check=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/v1/upload 2>/dev/null || echo "000")
check "POST /v1/upload exists" $([ "$upload_check" = "405" ] || [ "$upload_check" = "200" ] && echo 0 || echo 1)

# Health endpoint
health_check=$(curl -s http://localhost:8000/health 2>/dev/null | grep -c "ok\|healthy\|status" || echo "0")
check "Health endpoint responds" $([ "$health_check" -gt 0 ] && echo 0 || echo 1)

# ============================================================
section "10. UI Application"
# ============================================================

# Check UI static files
ui_js=$(curl -s http://localhost:3002/ 2>/dev/null | grep -c "script" || echo "0")
check "UI serves JavaScript" $([ "$ui_js" -gt 0 ] && echo 0 || echo 1)

# Check UI routing
ui_docs=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3002/documents 2>/dev/null || echo "000")
check "UI /documents route" $([ "$ui_docs" = "200" ] && echo 0 || echo 1)

# ============================================================
# SUMMARY
# ============================================================
echo ""
echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                      SUMMARY                              ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${GREEN}✓ Passed:${NC}  $PASS"
echo -e "  ${YELLOW}⚠ Warnings:${NC} $WARN"
echo -e "  ${RED}✗ Failed:${NC}  $FAIL"
echo ""

TOTAL=$((PASS + FAIL))
if [ "$FAIL" -eq 0 ]; then
    echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}   🎉 ALL CHECKS PASSED! System is healthy.                    ${NC}"
    echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
    exit 0
elif [ "$FAIL" -lt 3 ]; then
    echo -e "${YELLOW}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}   ⚠️  Some checks failed. System may still be usable.         ${NC}"
    echo -e "${YELLOW}══════════════════════════════════════════════════════════════${NC}"
    exit 1
else
    echo -e "${RED}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}   ❌ Multiple failures detected. Please investigate.          ${NC}"
    echo -e "${RED}══════════════════════════════════════════════════════════════${NC}"
    exit 2
fi
