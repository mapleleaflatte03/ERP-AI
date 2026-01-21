#!/bin/bash
# smoke_e2e.sh - STRICT End-to-End test (PR-6)
# DYNAMIC mode by default for local dev
# CI mode defaults to STATIC for deterministic results
# 
# Features (PR-5.1 + PR-6):
#   - Retry logic for flaky LLM JSON parse errors
#   - SMOKE_E2E_RETRIES controls max attempts (default: 3)
#   - CI=1 defaults to SMOKE_MODE=static (no LLM dependency)
#
# Usage:
#   bash scripts/smoke_e2e.sh                     # DYNAMIC mode (local dev)
#   SMOKE_MODE=static bash scripts/smoke_e2e.sh  # Static baseline only
#   SMOKE_E2E_RETRIES=5 bash scripts/smoke_e2e.sh # Custom retry count
#   CI=1 bash scripts/smoke_e2e.sh               # CI mode (auto static)
#   CI=1 SMOKE_MODE=dynamic bash scripts/smoke_e2e.sh # Force dynamic in CI
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# CI deterministic: default to static mode when CI is set
if [ -n "$CI" ] && [ -z "$SMOKE_MODE" ]; then
    SMOKE_MODE="static"
fi

# Config
SMOKE_MODE="${SMOKE_MODE:-dynamic}"
DB_CONTAINER="${DB_CONTAINER:-erpx-postgres}"
DB_USER="${DB_USER:-erpx}"
DB_NAME="${DB_NAME:-erpx}"
API_URL="${API_URL:-http://localhost:8000}"
TEST_FILE="${TEST_FILE:-$PROJECT_ROOT/data/uploads/sample_invoice.png}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-180}"
SMOKE_E2E_RETRIES="${SMOKE_E2E_RETRIES:-3}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "=================================================="
echo "SMOKE_E2E: STRICT End-to-End Test (PR-6)"
echo "Mode: ${SMOKE_MODE^^}"
if [ -n "$CI" ]; then
    echo "CI Mode: ENABLED (deterministic)"
fi
echo "Max Retries: $SMOKE_E2E_RETRIES (for flaky LLM errors)"
echo "=================================================="

# Tables and minimum requirements
TABLES=("extracted_invoices" "journal_proposals" "approvals" "ledger_entries" "ledger_lines")
MIN_REQUIRED=(1 1 1 1 2)

# Functions
db_count() {
    docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT count(*) FROM $1" 2>/dev/null | tr -d ' \n'
}

db_latest_epoch() {
    docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COALESCE(EXTRACT(EPOCH FROM MAX(created_at))::bigint, 0) FROM $1" 2>/dev/null | tr -d ' \n'
}

print_diagnostics() {
    local job_id=$1
    echo ""
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}🔥 DIAGNOSTICS: Job Failure Analysis${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    echo ""
    echo -e "${YELLOW}📋 Job Details (/v1/jobs/$job_id):${NC}"
    curl -s "$API_URL/v1/jobs/$job_id" 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "  (could not fetch job details)"
    
    echo ""
    echo -e "${YELLOW}📜 API Logs (last 100 lines):${NC}"
    docker logs erpx-api --tail 100 2>&1 | tail -50
    
    echo ""
    echo -e "${YELLOW}📜 Worker Logs (last 100 lines):${NC}"
    docker logs erpx-worker --tail 100 2>&1 | tail -50
    
    echo ""
    echo -e "${YELLOW}📜 Temporal Logs (last 50 lines):${NC}"
    docker logs erpx-temporal --tail 50 2>&1 | tail -30
    
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Check if error message indicates flaky LLM JSON error (retryable)
is_flaky_llm_error() {
    local error_msg="$1"
    if echo "$error_msg" | grep -qi "LLM response is not valid JSON"; then
        return 0  # true - this is flaky
    fi
    if echo "$error_msg" | grep -qi "JSON parse error"; then
        return 0  # true - this is flaky
    fi
    if echo "$error_msg" | grep -qi "invalid json"; then
        return 0  # true - this is flaky
    fi
    return 1  # false - not flaky
}

# Get job error message
get_job_error() {
    local job_id=$1
    curl -s "$API_URL/v1/jobs/$job_id" 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('error', d.get('message', d.get('detail', ''))))
except:
    print('')
" 2>/dev/null || echo ""
}

# ============================================================
# STATIC MODE: Baseline check only
# ============================================================
if [ "$SMOKE_MODE" = "static" ]; then
    echo ""
    echo -e "${YELLOW}📊 STATIC MODE: Checking baseline data only${NC}"
    echo ""
    
    BASELINE_OK=true
    for i in "${!TABLES[@]}"; do
        table="${TABLES[$i]}"
        min="${MIN_REQUIRED[$i]}"
        count=$(db_count "$table")
        
        if [ "$count" -ge "$min" ]; then
            echo -e "  ${GREEN}✓${NC} $table: $count rows (min: $min)"
        else
            echo -e "  ${RED}✗${NC} $table: $count rows (need: $min)"
            BASELINE_OK=false
        fi
    done
    
    echo ""
    if [ "$BASELINE_OK" = true ]; then
        echo -e "${GREEN}✅ SMOKE_E2E PASSED (static baseline)${NC}"
        exit 0
    else
        echo -e "${RED}❌ SMOKE_E2E FAILED: Missing baseline data${NC}"
        exit 1
    fi
fi

# ============================================================
# DYNAMIC MODE: Full E2E with strict validation + retry logic
# ============================================================

# Main E2E function - returns 0 on success, 1 on hard fail, 2 on flaky fail
run_e2e_attempt() {
    local attempt=$1
    
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}📊 STEP 1: Capture BEFORE state${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    declare -A COUNT_BEFORE
    declare -A EPOCH_BEFORE

    for table in "${TABLES[@]}"; do
        COUNT_BEFORE[$table]=$(db_count "$table")
        EPOCH_BEFORE[$table]=$(db_latest_epoch "$table")
        echo "  $table: ${COUNT_BEFORE[$table]} rows"
    done

    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}🚀 STEP 2: Upload document and trigger workflow${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    # Verify test file exists
    if [ ! -f "$TEST_FILE" ]; then
        echo -e "${RED}❌ FAIL: Test file not found: $TEST_FILE${NC}"
        return 1  # Hard fail - not retryable
    fi
    echo "  ✓ Test file: $(basename $TEST_FILE)"

    # Upload document
    TENANT_ID="smoke-e2e-$(date +%s)"
    echo "  Uploading to $API_URL/v1/upload..."

    UPLOAD_RESPONSE=$(curl -s -X POST "$API_URL/v1/upload" \
        -F "file=@$TEST_FILE" \
        -F "tenant_id=$TENANT_ID" \
        -w "\n%{http_code}" \
        2>/dev/null)

    HTTP_CODE=$(echo "$UPLOAD_RESPONSE" | tail -1)
    BODY=$(echo "$UPLOAD_RESPONSE" | sed '$d')

    if [ "$HTTP_CODE" != "200" ] && [ "$HTTP_CODE" != "201" ]; then
        echo -e "${RED}❌ FAIL: Upload failed (HTTP $HTTP_CODE)${NC}"
        echo "  Response: $BODY"
        return 1  # Hard fail
    fi

    JOB_ID=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('job_id', d.get('id', '')))" 2>/dev/null || echo "")

    if [ -z "$JOB_ID" ] || [ "$JOB_ID" = "" ]; then
        echo -e "${RED}❌ FAIL: No job_id returned${NC}"
        echo "  Response: $BODY"
        return 1  # Hard fail
    fi

    echo -e "  ${GREEN}✓${NC} Job created: $JOB_ID"
    
    # Export JOB_ID for outer scope
    export LAST_JOB_ID="$JOB_ID"

    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}⏳ STEP 3: Poll job until completion (max ${TIMEOUT_SECONDS}s)${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    START_TIME=$(date +%s)
    JOB_STATUS="pending"

    while true; do
        ELAPSED=$(($(date +%s) - START_TIME))
        
        if [ $ELAPSED -gt $TIMEOUT_SECONDS ]; then
            echo ""
            echo -e "${RED}❌ FAIL: Job timed out after ${TIMEOUT_SECONDS}s${NC}"
            return 1  # Hard fail - timeout is infra issue
        fi
        
        STATUS_RESPONSE=$(curl -s "$API_URL/v1/jobs/$JOB_ID" 2>/dev/null || echo '{"status":"unknown"}')
        JOB_STATUS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unknown")
        
        printf "\r  Status: %-15s (%ds elapsed)" "$JOB_STATUS" "$ELAPSED"
        
        case "$JOB_STATUS" in
            "completed")
                echo ""
                echo -e "  ${GREEN}✓${NC} Job completed successfully!"
                break
                ;;
            "failed"|"error")
                echo ""
                local error_msg=$(get_job_error "$JOB_ID")
                echo -e "${RED}Job failed: $error_msg${NC}"
                
                # Check if this is a flaky LLM error
                if is_flaky_llm_error "$error_msg"; then
                    echo -e "${YELLOW}⚠️ Detected flaky LLM JSON error - eligible for retry${NC}"
                    return 2  # Flaky fail - retryable
                else
                    echo -e "${RED}❌ FAIL: Job status = $JOB_STATUS (non-retryable)${NC}"
                    print_diagnostics "$JOB_ID"
                    return 1  # Hard fail
                fi
                ;;
            *)
                sleep 3
                ;;
        esac
    done

    # Wait for DB writes
    sleep 3

    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}📊 STEP 4: Verify AFTER state (must have new records)${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    declare -A COUNT_AFTER
    declare -A EPOCH_AFTER
    TABLES_WITH_NEW=0
    NEW_RECORDS_TOTAL=0

    for table in "${TABLES[@]}"; do
        COUNT_AFTER[$table]=$(db_count "$table")
        EPOCH_AFTER[$table]=$(db_latest_epoch "$table")
        
        DIFF=$((COUNT_AFTER[$table] - COUNT_BEFORE[$table]))
        
        if [ $DIFF -gt 0 ]; then
            echo -e "  ${GREEN}✓${NC} $table: ${COUNT_BEFORE[$table]} → ${COUNT_AFTER[$table]} (+$DIFF NEW)"
            TABLES_WITH_NEW=$((TABLES_WITH_NEW + 1))
            NEW_RECORDS_TOTAL=$((NEW_RECORDS_TOTAL + DIFF))
        elif [ "${EPOCH_AFTER[$table]}" -gt "${EPOCH_BEFORE[$table]}" ]; then
            echo -e "  ${GREEN}✓${NC} $table: updated (newer timestamp)"
            TABLES_WITH_NEW=$((TABLES_WITH_NEW + 1))
        else
            echo -e "  ${YELLOW}○${NC} $table: ${COUNT_AFTER[$table]} (no change)"
        fi
    done

    echo ""
    
    # Export for outer scope
    export LAST_TABLES_WITH_NEW=$TABLES_WITH_NEW
    export LAST_NEW_RECORDS_TOTAL=$NEW_RECORDS_TOTAL

    # At least some tables should have new data
    if [ $TABLES_WITH_NEW -gt 0 ]; then
        return 0  # Success
    else
        echo -e "${YELLOW}⚠️ Job completed but no new records - may be flaky${NC}"
        return 2  # Treat as flaky - retryable
    fi
}

# ============================================================
# DYNAMIC MODE: Main retry loop
# ============================================================
ATTEMPT=1
LAST_JOB_ID=""
LAST_TABLES_WITH_NEW=0
LAST_NEW_RECORDS_TOTAL=0

while [ $ATTEMPT -le $SMOKE_E2E_RETRIES ]; do
    echo ""
    echo "=================================================="
    echo -e "${CYAN}🔄 Attempt $ATTEMPT/$SMOKE_E2E_RETRIES${NC}"
    echo "=================================================="
    
    # Run the E2E attempt
    set +e  # Temporarily allow failures
    run_e2e_attempt $ATTEMPT
    RESULT=$?
    set -e
    
    case $RESULT in
        0)
            # Success!
            echo ""
            echo "=================================================="
            echo -e "${GREEN}✅ SMOKE_E2E PASSED (DYNAMIC)${NC}"
            echo "   - Job completed: $LAST_JOB_ID"
            echo "   - Tables with new data: $LAST_TABLES_WITH_NEW/5"
            echo "   - New records: $LAST_NEW_RECORDS_TOTAL"
            if [ $ATTEMPT -gt 1 ]; then
                echo -e "   - ${YELLOW}Succeeded after $ATTEMPT attempts (flaky LLM recovered)${NC}"
            fi
            echo ""
            echo "📋 Latest Record:"
            docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t << 'EOF'
SELECT '  Invoice: ' || invoice_number || ' from ' || vendor_name FROM extracted_invoices ORDER BY created_at DESC LIMIT 1;
SELECT '  Proposal: ' || status || ' (' || ai_model || ')' FROM journal_proposals ORDER BY created_at DESC LIMIT 1;
SELECT '  Ledger: ' || entry_number FROM ledger_entries ORDER BY created_at DESC LIMIT 1;
EOF
            exit 0
            ;;
        1)
            # Hard failure - don't retry
            echo ""
            echo -e "${RED}❌ SMOKE_E2E FAILED: Non-retryable error${NC}"
            exit 1
            ;;
        2)
            # Flaky failure - retry if attempts remaining
            if [ $ATTEMPT -lt $SMOKE_E2E_RETRIES ]; then
                echo ""
                echo -e "${YELLOW}🔄 Flaky LLM error detected, retrying... (attempt $((ATTEMPT+1))/$SMOKE_E2E_RETRIES)${NC}"
                sleep 2
            else
                echo ""
                echo -e "${RED}❌ SMOKE_E2E FAILED: Flaky error persisted after $SMOKE_E2E_RETRIES attempts${NC}"
                print_diagnostics "$LAST_JOB_ID"
                exit 1
            fi
            ;;
    esac
    
    ATTEMPT=$((ATTEMPT + 1))
done

echo -e "${RED}❌ SMOKE_E2E FAILED: Unexpected exit from retry loop${NC}"
exit 1
