#!/bin/bash
# Health check script for ERP AI infrastructure
# Usage: ./verify_infra.sh

set -e

echo "=============================================="
echo "ERP AI Infrastructure Health Check"
echo "=============================================="

PASS=0
FAIL=0

check_service() {
    local name=$1
    local check_cmd=$2
    
    if eval "$check_cmd" > /dev/null 2>&1; then
        echo "✅ $name: OK"
        ((PASS++))
    else
        echo "❌ $name: FAILED"
        ((FAIL++))
    fi
}

echo ""
echo "--- Docker Containers ---"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "erp-"

echo ""
echo "--- Service Health Checks ---"

# PostgreSQL
check_service "PostgreSQL" "docker exec erp-postgres pg_isready -U erp_user -d erp_ai"

# Qdrant
check_service "Qdrant" "curl -sf http://localhost:6333/collections"

# MinIO
check_service "MinIO" "curl -sf http://localhost:9000/minio/health/live"

# MLflow  
check_service "MLflow" "curl -sf http://localhost:5000/health"

echo ""
echo "--- Database Tables ---"
TABLE_COUNT=$(docker exec erp-postgres psql -U erp_user -d erp_ai -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" | tr -d ' ')
echo "PostgreSQL tables: $TABLE_COUNT"

echo ""
echo "--- MinIO Buckets ---"
docker exec erp-minio mc ls local 2>/dev/null | grep -E "^\[" | awk '{print $NF}' || echo "Unable to list"

echo ""
echo "--- Qdrant Collections ---"
curl -s http://localhost:6333/collections | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Collections: {len(d[\"result\"][\"collections\"])}')" 2>/dev/null || echo "Collections: 0"

echo ""
echo "=============================================="
echo "Summary: $PASS passed, $FAIL failed"
echo "=============================================="

if [ $FAIL -gt 0 ]; then
    exit 1
else
    echo "✅ All infrastructure services are healthy!"
    exit 0
fi
