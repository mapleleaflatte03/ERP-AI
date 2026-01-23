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

# =============================================================================
# PR13.6: Helper functions for 2-path governance testing
# =============================================================================

# DB query helper
db_count() {
    docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT count(*) FROM $1" 2>/dev/null | tr -d ' \n'
}

db_query() {
    docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -c "$1" 2>/dev/null | tr -d ' \n'
}

# Save current policy rules config for restore
save_policy_config() {
    SAVED_THRESHOLD=$(db_query "SELECT config->>'max_amount' FROM policy_rules WHERE name='auto_approve_threshold'")
    echo "  Saved threshold config: $SAVED_THRESHOLD"
}

# Restore policy rules to default
restore_policy_config() {
    echo "  Restoring policy rules to default..."
    docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "
        UPDATE policy_rules SET config = '{\"max_amount\": 10000000}'::jsonb WHERE name = 'auto_approve_threshold';
    " >/dev/null 2>&1
    echo "  ✓ Policy rules restored"
}

# Set threshold for deterministic test outcomes
set_threshold() {
    local amount=$1
    docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "
        UPDATE policy_rules SET config = '{\"max_amount\": $amount}'::jsonb WHERE name = 'auto_approve_threshold';
    " >/dev/null 2>&1
    echo "  ✓ Threshold set to: $amount"
}

# Get job state from DB
get_job_state() {
    local job_id=$1
    db_query "SELECT current_state FROM job_processing_state WHERE job_id = '$job_id'"
}

# Get approval status for job
get_approval_status() {
    local job_id=$1
    db_query "SELECT status FROM approvals WHERE job_id = '$job_id' ORDER BY created_at DESC LIMIT 1"
}

# =============================================================================
# PR17: Token and approval helpers
# =============================================================================

KONG_URL="${KONG_URL:-http://localhost:8080}"
KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:8180}"
KEYCLOAK_REALM="${KEYCLOAK_REALM:-erpx}"
KEYCLOAK_CLIENT="${KEYCLOAK_CLIENT:-admin-cli}"
KEYCLOAK_USER="${KEYCLOAK_USER:-admin}"
KEYCLOAK_PASS="${KEYCLOAK_PASS:-admin123}"
AUTH_TOKEN=""

# Get JWT token from Keycloak
get_auth_token() {
    TOKEN_RESPONSE=$(curl -s -X POST "$KEYCLOAK_URL/realms/$KEYCLOAK_REALM/protocol/openid-connect/token" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "grant_type=password" \
        -d "client_id=$KEYCLOAK_CLIENT" \
        -d "username=$KEYCLOAK_USER" \
        -d "password=$KEYCLOAK_PASS" 2>/dev/null || echo '{"error":"connection_failed"}')
    
    AUTH_TOKEN=$(echo "$TOKEN_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))" 2>/dev/null || echo "")
    
    if [ -n "$AUTH_TOKEN" ] && [ "$AUTH_TOKEN" != "" ]; then
        return 0
    else
        return 1
    fi
}

# Call approve endpoint via Kong (PR17)
approve_job_via_kong() {
    local job_id=$1
    
    if [ -z "$AUTH_TOKEN" ]; then
        if ! get_auth_token; then
            echo "  ${RED}✗${NC} Failed to get auth token"
            return 1
        fi
    fi
    
    local RESPONSE=$(curl -s -X POST "$KONG_URL/api/v1/approvals/by-job/$job_id/approve" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        -H "Content-Type: application/json" \
        2>/dev/null)
    
    local HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$KONG_URL/api/v1/approvals/by-job/$job_id/approve" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        -H "Content-Type: application/json" \
        2>/dev/null || echo "000")
    
    echo "$RESPONSE"
    
    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "202" ]; then
        return 0
    else
        return 1
    fi
}

# Poll job until completed after approval
poll_until_completed() {
    local job_id=$1
    local max_wait=${2:-60}
    local start_time=$(date +%s)
    
    while true; do
        local elapsed=$(($(date +%s) - start_time))
        
        if [ $elapsed -gt $max_wait ]; then
            echo "  ${RED}✗${NC} Timeout waiting for completion"
            return 1
        fi
        
        local status=$(curl -s "$API_URL/v1/jobs/$job_id" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unknown")
        
        if [ "$status" = "completed" ]; then
            return 0
        elif [ "$status" = "failed" ] || [ "$status" = "rejected" ]; then
            echo "  Job ended with status: $status"
            return 1
        fi
        
        sleep 2
    done
}

# Check if approval has non-null job_id (critical invariant)
check_approval_job_id() {
    local job_id=$1
    local null_count=$(db_query "SELECT count(*) FROM approvals WHERE job_id = '$job_id' AND job_id IS NULL")
    if [ "$null_count" != "0" ]; then
        echo -e "${RED}❌ CRITICAL: approval.job_id is NULL!${NC}"
        return 1
    fi
    return 0
}

# Check audit events for job
get_audit_events() {
    local job_id=$1
    docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -c "
        SELECT event_type FROM audit_events WHERE job_id = '$job_id' ORDER BY created_at
    " 2>/dev/null | tr -d ' ' | tr '\n' ',' | sed 's/,$//'
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
        
        # PR14 Evidence: Show MinIO and Qdrant status
        echo ""
        echo -e "${CYAN}📊 PR14 Evidence (Durable Ingestion):${NC}"
        
        # MinIO evidence
        MINIO_DOCS=$(db_query "SELECT count(*) FROM documents WHERE minio_bucket IS NOT NULL AND minio_key IS NOT NULL")
        if [ "$MINIO_DOCS" != "0" ] && [ -n "$MINIO_DOCS" ]; then
            echo -e "  ${GREEN}✓${NC} MinIO: $MINIO_DOCS documents with minio_bucket/minio_key"
        else
            echo -e "  ${YELLOW}⚠${NC} MinIO: 0 documents (ENABLE_MINIO may be off)"
        fi
        
        # Qdrant evidence
        QDRANT_POINTS=$(curl -s http://localhost:6333/collections/documents_ingested 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('result',{}).get('points_count',0))" 2>/dev/null || echo "0")
        if [ "$QDRANT_POINTS" != "0" ] && [ -n "$QDRANT_POINTS" ]; then
            echo -e "  ${GREEN}✓${NC} Qdrant: $QDRANT_POINTS points in documents_ingested"
        else
            echo -e "  ${YELLOW}⚠${NC} Qdrant: 0 points (ENABLE_QDRANT may be off)"
        fi
        
        exit 0
    else
        echo -e "${RED}❌ SMOKE_E2E FAILED: Missing baseline data${NC}"
        exit 1
    fi
fi

# ============================================================
# DYNAMIC MODE: Full E2E with 2-path governance testing (PR13.6)
# ============================================================

# Upload and poll job - returns job_id in LAST_JOB_ID, final status in LAST_JOB_STATUS
# Returns 0 on terminal state, 1 on hard fail, 2 on flaky fail
upload_and_poll() {
    local test_name=$1
    local expected_state=$2  # "completed" or "waiting_for_approval"
    
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}🚀 Upload document: $test_name${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    # Verify test file exists
    if [ ! -f "$TEST_FILE" ]; then
        echo -e "${RED}❌ FAIL: Test file not found: $TEST_FILE${NC}"
        return 1
    fi

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
        return 1
    fi

    JOB_ID=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('job_id', d.get('id', '')))" 2>/dev/null || echo "")

    if [ -z "$JOB_ID" ] || [ "$JOB_ID" = "" ]; then
        echo -e "${RED}❌ FAIL: No job_id returned${NC}"
        echo "  Response: $BODY"
        return 1
    fi

    echo -e "  ${GREEN}✓${NC} Job created: $JOB_ID"
    export LAST_JOB_ID="$JOB_ID"

    # PR16 Evidence: Check upload response status and Temporal workflow
    local UPLOAD_STATUS=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status', 'unknown'))" 2>/dev/null || echo "unknown")
    echo ""
    echo -e "${CYAN}📊 PR16 Evidence (Temporal Workflow):${NC}"
    echo "  Upload response status: $UPLOAD_STATUS"
    if [ "$UPLOAD_STATUS" = "queued" ]; then
        echo -e "  ${GREEN}✓${NC} Temporal workflow started (status=queued)"
        # Query Temporal for workflow info
        local TEMPORAL_WF=$(docker exec erpx-temporal temporal workflow describe --workflow-id "$JOB_ID" 2>/dev/null | head -10 || echo "  (Temporal query failed)")
        echo "  Workflow ID: $JOB_ID"
        echo "$TEMPORAL_WF" | grep -E "Status|Type|TaskQueue" | head -3 || true
    else
        echo -e "  ${YELLOW}⚠${NC} Fallback async processing (status=$UPLOAD_STATUS, ENABLE_TEMPORAL may be off)"
    fi

    echo ""
    echo -e "${YELLOW}⏳ Polling job until terminal state (max ${TIMEOUT_SECONDS}s)${NC}"

    START_TIME=$(date +%s)
    JOB_STATUS="pending"

    while true; do
        ELAPSED=$(($(date +%s) - START_TIME))
        
        if [ $ELAPSED -gt $TIMEOUT_SECONDS ]; then
            echo ""
            echo -e "${RED}❌ FAIL: Job timed out after ${TIMEOUT_SECONDS}s${NC}"
            return 1
        fi
        
        STATUS_RESPONSE=$(curl -s "$API_URL/v1/jobs/$JOB_ID" 2>/dev/null || echo '{"status":"unknown"}')
        JOB_STATUS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unknown")
        
        printf "\r  Status: %-20s (%ds elapsed)" "$JOB_STATUS" "$ELAPSED"
        
        case "$JOB_STATUS" in
            "completed"|"waiting_for_approval")
                echo ""
                echo -e "  ${GREEN}✓${NC} Job reached terminal state: $JOB_STATUS"
                export LAST_JOB_STATUS="$JOB_STATUS"
                break
                ;;
            "failed"|"error")
                echo ""
                local error_msg=$(get_job_error "$JOB_ID")
                echo -e "${RED}Job failed: $error_msg${NC}"
                
                if is_flaky_llm_error "$error_msg"; then
                    echo -e "${YELLOW}⚠️ Detected flaky LLM JSON error - eligible for retry${NC}"
                    return 2
                else
                    echo -e "${RED}❌ FAIL: Job status = $JOB_STATUS (non-retryable)${NC}"
                    print_diagnostics "$JOB_ID"
                    return 1
                fi
                ;;
            *)
                sleep 3
                ;;
        esac
    done

    # Wait for DB writes
    sleep 2
    return 0
}

# Verify governance outcome for a job
# Args: job_id, expected_state, expected_approval_status, expected_ledger_delta, expected_outbox_delta
verify_governance_outcome() {
    local job_id=$1
    local expected_state=$2
    local expected_approval=$3
    local expected_ledger=$4
    local expected_outbox=$5
    local ledger_before=$6
    local outbox_before=$7
    
    echo ""
    echo -e "${YELLOW}📋 Verifying governance outcome...${NC}"
    
    local PASS=true
    
    # 1. Check job state in DB
    local actual_state=$(get_job_state "$job_id")
    if [ "$actual_state" = "$expected_state" ]; then
        echo -e "  ${GREEN}✓${NC} Job state: $actual_state (expected: $expected_state)"
    else
        echo -e "  ${RED}✗${NC} Job state: $actual_state (expected: $expected_state)"
        PASS=false
    fi
    
    # 2. Check approval status
    local actual_approval=$(get_approval_status "$job_id")
    if [ "$actual_approval" = "$expected_approval" ]; then
        echo -e "  ${GREEN}✓${NC} Approval status: $actual_approval (expected: $expected_approval)"
    else
        echo -e "  ${RED}✗${NC} Approval status: $actual_approval (expected: $expected_approval)"
        PASS=false
    fi
    
    # 3. Check approval.job_id NOT NULL (critical invariant)
    local approval_count=$(db_query "SELECT count(*) FROM approvals WHERE job_id = '$job_id'")
    if [ "$approval_count" -ge "1" ]; then
        echo -e "  ${GREEN}✓${NC} Approval record exists with job_id (count: $approval_count)"
    else
        echo -e "  ${RED}✗${NC} No approval record found for job_id"
        PASS=false
    fi
    
    # 4. Check ledger delta
    local ledger_after=$(db_count "ledger_entries")
    local ledger_delta=$((ledger_after - ledger_before))
    if [ "$ledger_delta" = "$expected_ledger" ]; then
        echo -e "  ${GREEN}✓${NC} Ledger delta: +$ledger_delta (expected: +$expected_ledger)"
    else
        echo -e "  ${RED}✗${NC} Ledger delta: +$ledger_delta (expected: +$expected_ledger)"
        PASS=false
    fi
    
    # 5. Check outbox delta
    local outbox_after=$(db_count "outbox_events")
    local outbox_delta=$((outbox_after - outbox_before))
    if [ "$outbox_delta" = "$expected_outbox" ]; then
        echo -e "  ${GREEN}✓${NC} Outbox delta: +$outbox_delta (expected: +$expected_outbox)"
    else
        echo -e "  ${RED}✗${NC} Outbox delta: +$outbox_delta (expected: +$expected_outbox)"
        PASS=false
    fi
    
    # 6. Check audit events
    local audit_events=$(get_audit_events "$job_id")
    echo -e "  ${CYAN}ℹ${NC}  Audit events: $audit_events"
    
    # 7. PR14 Evidence: MinIO bucket/key populated
    local minio_bucket=$(db_query "SELECT minio_bucket FROM documents WHERE job_id = '$job_id' LIMIT 1")
    local minio_key=$(db_query "SELECT minio_key FROM documents WHERE job_id = '$job_id' LIMIT 1")
    if [ -n "$minio_bucket" ] && [ -n "$minio_key" ]; then
        echo -e "  ${GREEN}✓${NC} MinIO: s3://$minio_bucket/$minio_key"
    else
        echo -e "  ${YELLOW}⚠${NC} MinIO: not populated (ENABLE_MINIO may be off)"
    fi
    
    if [ "$PASS" = true ]; then
        return 0
    else
        return 1
    fi
}

# Main E2E function with 2-path testing
run_e2e_attempt() {
    local attempt=$1
    
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}📊 PR13.6: Two-Path Governance Testing${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    # Save current config for restore
    save_policy_config
    
    local CASE_A_PASS=false
    local CASE_B_PASS=false
    
    # ================================================================
    # CASE A: Force AUTO_APPROVED (high threshold)
    # Expected: state=completed, approval=approved, ledger+1, outbox+1
    # ================================================================
    echo ""
    echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}🅰️  CASE A: AUTO_APPROVED Path${NC}"
    echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
    
    # Set threshold high to force auto-approval
    set_threshold 100000000  # 100M
    
    # Capture BEFORE counts
    local ledger_before_a=$(db_count "ledger_entries")
    local outbox_before_a=$(db_count "outbox_events")
    local approvals_before_a=$(db_count "approvals")
    echo "  Before: ledger=$ledger_before_a, outbox=$outbox_before_a, approvals=$approvals_before_a"
    
    # Upload and poll
    set +e
    upload_and_poll "Case A (auto_approved)" "completed"
    local upload_result=$?
    set -e
    
    if [ $upload_result -eq 0 ]; then
        # Verify outcome
        set +e
        verify_governance_outcome "$LAST_JOB_ID" "completed" "approved" "1" "1" "$ledger_before_a" "$outbox_before_a"
        if [ $? -eq 0 ]; then
            echo -e "  ${GREEN}✅ CASE A PASSED${NC}"
            CASE_A_PASS=true
        else
            echo -e "  ${RED}❌ CASE A FAILED: Outcome mismatch${NC}"
        fi
        set -e
    elif [ $upload_result -eq 2 ]; then
        echo -e "  ${YELLOW}⚠️ CASE A: Flaky error, will retry${NC}"
        restore_policy_config
        return 2
    else
        echo -e "  ${RED}❌ CASE A FAILED: Upload/poll error${NC}"
        restore_policy_config
        return 1
    fi
    
    # PR17: Get auth token for approval endpoint calls
    echo ""
    echo -e "${CYAN}🔑 Acquiring auth token for approval API...${NC}"
    get_auth_token
    if [ -z "$AUTH_TOKEN" ]; then
        echo -e "  ${YELLOW}⚠️ Could not get auth token, will try approval without auth${NC}"
    else
        echo -e "  ${GREEN}✓${NC} Auth token acquired"
    fi
    
    # ================================================================
    # CASE B: Force NEEDS_APPROVAL (low threshold)
    # PR17: Then approve via API and verify completion
    # Expected flow: waiting_for_approval → approve → completed
    # ================================================================
    echo ""
    echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}🅱️  CASE B: NEEDS_APPROVAL → Manual Approval Path (PR17)${NC}"
    echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
    
    # Set threshold to 1 to force needs_approval
    set_threshold 1
    
    # Capture BEFORE counts
    local ledger_before_b=$(db_count "ledger_entries")
    local outbox_before_b=$(db_count "outbox_events")
    local approvals_before_b=$(db_count "approvals")
    echo "  Before: ledger=$ledger_before_b, outbox=$outbox_before_b, approvals=$approvals_before_b"
    
    # Upload and poll until waiting_for_approval
    set +e
    upload_and_poll "Case B (needs_approval)" "waiting_for_approval"
    upload_result=$?
    set -e
    
    if [ $upload_result -eq 0 ]; then
        # First verify waiting_for_approval state
        set +e
        verify_governance_outcome "$LAST_JOB_ID" "waiting_for_approval" "pending" "0" "0" "$ledger_before_b" "$outbox_before_b"
        local verify_result=$?
        set -e
        
        if [ $verify_result -ne 0 ]; then
            echo -e "  ${RED}❌ CASE B FAILED: Initial outcome mismatch${NC}"
            restore_policy_config
            return 1
        fi
        
        echo ""
        echo -e "${CYAN}📊 PR17 Evidence (Manual Approval Flow):${NC}"
        
        # PR17: Approve via Kong API
        echo "  Calling approve endpoint via Kong..."
        set +e
        APPROVE_RESPONSE=$(approve_job_via_kong "$LAST_JOB_ID")
        APPROVE_RESULT=$?
        set -e
        
        local APPROVAL_STATUS=$(echo "$APPROVE_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('approval_status','unknown'))" 2>/dev/null || echo "unknown")
        local TEMPORAL_SIGNALED=$(echo "$APPROVE_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('temporal_signaled', False))" 2>/dev/null || echo "false")
        
        echo "  Approval response status: $APPROVAL_STATUS"
        echo "  Temporal signaled: $TEMPORAL_SIGNALED"
        
        if [ "$APPROVAL_STATUS" = "approved" ]; then
            echo -e "  ${GREEN}✓${NC} Approval API succeeded"
        else
            echo -e "  ${RED}✗${NC} Approval API failed (status: $APPROVAL_STATUS)"
            echo "  Response: $APPROVE_RESPONSE"
            restore_policy_config
            return 1
        fi
        
        # Wait for workflow to complete
        echo "  Waiting for workflow to complete..."
        set +e
        poll_until_completed "$LAST_JOB_ID" 60
        POLL_RESULT=$?
        set -e
        
        if [ $POLL_RESULT -eq 0 ]; then
            echo -e "  ${GREEN}✓${NC} Job completed after approval"
            
            # Verify final outcome
            local final_state=$(get_job_state "$LAST_JOB_ID")
            local final_approval=$(get_approval_status "$LAST_JOB_ID")
            local ledger_after_b=$(db_count "ledger_entries")
            local outbox_after_b=$(db_count "outbox_events")
            local ledger_delta_b=$((ledger_after_b - ledger_before_b))
            local outbox_delta_b=$((outbox_after_b - outbox_before_b))
            local audit_events=$(get_audit_events "$LAST_JOB_ID")
            
            echo ""
            echo -e "${YELLOW}📋 Verifying post-approval outcome...${NC}"
            
            local PASS_B=true
            
            # Check final state
            if [ "$final_state" = "completed" ]; then
                echo -e "  ${GREEN}✓${NC} Job state: completed"
            else
                echo -e "  ${RED}✗${NC} Job state: $final_state (expected: completed)"
                PASS_B=false
            fi
            
            # Check approval status
            if [ "$final_approval" = "approved" ]; then
                echo -e "  ${GREEN}✓${NC} Approval status: approved"
            else
                echo -e "  ${RED}✗${NC} Approval status: $final_approval (expected: approved)"
                PASS_B=false
            fi
            
            # Check ledger delta (should be +1 after approval)
            if [ "$ledger_delta_b" = "1" ]; then
                echo -e "  ${GREEN}✓${NC} Ledger delta: +$ledger_delta_b"
            else
                echo -e "  ${RED}✗${NC} Ledger delta: +$ledger_delta_b (expected: +1)"
                PASS_B=false
            fi
            
            # Check outbox delta
            if [ "$outbox_delta_b" = "1" ]; then
                echo -e "  ${GREEN}✓${NC} Outbox delta: +$outbox_delta_b"
            else
                echo -e "  ${RED}✗${NC} Outbox delta: +$outbox_delta_b (expected: +1)"
                PASS_B=false
            fi
            
            # Show audit events
            echo -e "  ${CYAN}ℹ${NC}  Audit events: $audit_events"
            
            if [ "$PASS_B" = true ]; then
                echo -e "  ${GREEN}✅ CASE B PASSED (Manual Approval)${NC}"
                CASE_B_PASS=true
            else
                echo -e "  ${RED}❌ CASE B FAILED: Post-approval outcome mismatch${NC}"
            fi
        else
            echo -e "  ${RED}❌ CASE B FAILED: Job did not complete after approval${NC}"
        fi
    elif [ $upload_result -eq 2 ]; then
        echo -e "  ${YELLOW}⚠️ CASE B: Flaky error, will retry${NC}"
        restore_policy_config
        return 2
    else
        echo -e "  ${RED}❌ CASE B FAILED: Upload/poll error${NC}"
        restore_policy_config
        return 1
    fi
    
    # Restore policy config
    restore_policy_config
    
    # Final result
    if [ "$CASE_A_PASS" = true ] && [ "$CASE_B_PASS" = true ]; then
        return 0
    else
        return 1
    fi
}

# ============================================================
# DYNAMIC MODE: Main retry loop
# ============================================================
ATTEMPT=1
LAST_JOB_ID=""
LAST_JOB_STATUS=""

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
            echo -e "${GREEN}✅ SMOKE_E2E PASSED (DYNAMIC - 2-Path Governance)${NC}"
            echo "   ✓ Case A: AUTO_APPROVED path verified"
            echo "   ✓ Case B: NEEDS_APPROVAL path verified"
            if [ $ATTEMPT -gt 1 ]; then
                echo -e "   - ${YELLOW}Succeeded after $ATTEMPT attempts (flaky LLM recovered)${NC}"
            fi
            echo ""
            echo "📋 Summary:"
            docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t << 'EOF'
SELECT '  Total invoices: ' || count(*) FROM extracted_invoices;
SELECT '  Total approvals: ' || count(*) || ' (approved=' || count(*) FILTER (WHERE status='approved') || ', pending=' || count(*) FILTER (WHERE status='pending') || ')' FROM approvals;
SELECT '  Total ledger entries: ' || count(*) FROM ledger_entries;
SELECT '  Total outbox events: ' || count(*) FROM outbox_events;
SELECT '  PR14 MinIO docs: ' || count(*) FROM documents WHERE minio_bucket IS NOT NULL;
EOF
            # PR14 Qdrant evidence
            QDRANT_POINTS=$(curl -s http://localhost:6333/collections/documents_ingested 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('result',{}).get('points_count',0))" 2>/dev/null || echo "0")
            echo "  PR14 Qdrant points: $QDRANT_POINTS"
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
