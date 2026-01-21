#!/bin/bash
# smoke_auth.sh - Verify Kong gateway auth enforcement
# Part of PR-0: Baseline Freeze + Golden Tests
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "=================================================="
echo "SMOKE_AUTH: Testing Kong JWT Authentication"
echo "=================================================="

KONG_URL="${KONG_URL:-http://localhost:8080}"
KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:8180}"
KEYCLOAK_REALM="${KEYCLOAK_REALM:-erpx}"
KEYCLOAK_CLIENT="${KEYCLOAK_CLIENT:-admin-cli}"
KEYCLOAK_USER="${KEYCLOAK_USER:-admin}"
KEYCLOAK_PASS="${KEYCLOAK_PASS:-admin123}"

FAILED=0

echo ""
echo "🔐 TEST 1: Request without token should return 401"
echo "Command: curl -s -o /dev/null -w '%{http_code}' $KONG_URL/api/health"
HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' "$KONG_URL/api/health" 2>/dev/null || echo "000")
echo "Response: HTTP $HTTP_CODE"
if [ "$HTTP_CODE" = "401" ]; then
    echo "✅ PASS: Received 401 Unauthorized (auth enforced)"
else
    echo "❌ FAIL: Expected 401, got $HTTP_CODE"
    FAILED=1
fi

echo ""
echo "🔑 TEST 2: Get token from Keycloak"
echo "Endpoint: $KEYCLOAK_URL/realms/$KEYCLOAK_REALM/protocol/openid-connect/token"
TOKEN_RESPONSE=$(curl -s -X POST "$KEYCLOAK_URL/realms/$KEYCLOAK_REALM/protocol/openid-connect/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "grant_type=password" \
    -d "client_id=$KEYCLOAK_CLIENT" \
    -d "username=$KEYCLOAK_USER" \
    -d "password=$KEYCLOAK_PASS" 2>/dev/null || echo '{"error":"connection_failed"}')

TOKEN=$(echo "$TOKEN_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))" 2>/dev/null || echo "")

if [ -n "$TOKEN" ] && [ "$TOKEN" != "" ]; then
    TOKEN_LEN=${#TOKEN}
    echo "✅ PASS: Got token (length: $TOKEN_LEN chars)"
else
    ERROR=$(echo "$TOKEN_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('error','unknown'))" 2>/dev/null || echo "parse_error")
    echo "❌ FAIL: Could not get token. Error: $ERROR"
    echo "Response: $TOKEN_RESPONSE"
    FAILED=1
fi

echo ""
echo "🔓 TEST 3: Request with valid token should return 200"
if [ -n "$TOKEN" ] && [ "$TOKEN" != "" ]; then
    HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $TOKEN" "$KONG_URL/api/health" 2>/dev/null || echo "000")
    echo "Response: HTTP $HTTP_CODE"
    if [ "$HTTP_CODE" = "200" ]; then
        echo "✅ PASS: Received 200 OK (authenticated)"
    else
        echo "❌ FAIL: Expected 200, got $HTTP_CODE"
        FAILED=1
    fi
else
    echo "⚠️  SKIP: No token available for test"
    FAILED=1
fi

echo ""
echo "=================================================="
if [ $FAILED -eq 0 ]; then
    echo "✅ SMOKE_AUTH PASSED: Kong auth enforcement verified"
    echo "   - No token → 401 ✓"
    echo "   - With token → 200 ✓"
    exit 0
else
    echo "❌ SMOKE_AUTH FAILED: Auth enforcement issues detected"
    exit 1
fi
