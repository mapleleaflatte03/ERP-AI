#!/bin/bash
# =============================================================================
# verify_kong_jwt.sh - Test Keycloak JWT authentication through Kong Gateway
# =============================================================================
# Usage:
#   export ERPX_USER=your_username
#   export ERPX_PASS=your_password
#   ./scripts/verify_kong_jwt.sh
#
# Optional environment variables:
#   KEYCLOAK_URL   - default: https://auth.welliam.codes
#   REALM          - default: erpx  
#   CLIENT_ID      - default: erpx-api
#   API_BASE_URL   - default: https://app.welliam.codes
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration with defaults
KEYCLOAK_URL="${KEYCLOAK_URL:-https://auth.welliam.codes}"
REALM="${REALM:-erpx}"
CLIENT_ID="${CLIENT_ID:-erpx-api}"
API_BASE_URL="${API_BASE_URL:-https://app.welliam.codes}"

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE} Kong JWT Authentication Verification Tool ${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check required environment variables
if [[ -z "$ERPX_USER" || -z "$ERPX_PASS" ]]; then
    echo -e "${RED}ERROR: Missing required environment variables${NC}"
    echo ""
    echo "Please set the following environment variables:"
    echo "  export ERPX_USER=<keycloak_username>"
    echo "  export ERPX_PASS=<keycloak_password>"
    echo ""
    echo "Example:"
    echo "  export ERPX_USER=erpx_test"
    echo "  export ERPX_PASS=Test@123456"
    echo "  ./scripts/verify_kong_jwt.sh"
    exit 1
fi

echo -e "${YELLOW}Configuration:${NC}"
echo "  Keycloak URL: $KEYCLOAK_URL"
echo "  Realm:        $REALM"
echo "  Client ID:    $CLIENT_ID"
echo "  API Base URL: $API_BASE_URL"
echo "  Username:     $ERPX_USER"
echo ""

# Step 1: Get token from Keycloak
echo -e "${YELLOW}[1/3] Requesting access token from Keycloak...${NC}"
TOKEN_ENDPOINT="${KEYCLOAK_URL}/realms/${REALM}/protocol/openid-connect/token"

TOKEN_RESPONSE=$(curl -s -X POST "$TOKEN_ENDPOINT" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "grant_type=password" \
    -d "client_id=${CLIENT_ID}" \
    -d "username=${ERPX_USER}" \
    -d "password=${ERPX_PASS}" \
    2>&1)

# Check if token request was successful
if echo "$TOKEN_RESPONSE" | grep -q '"access_token"'; then
    ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.access_token')
    echo -e "${GREEN}✓ Token obtained successfully${NC}"
else
    echo -e "${RED}✗ Failed to obtain token${NC}"
    echo "Response: $TOKEN_RESPONSE"
    exit 1
fi

# Step 2: Decode and display token info
echo ""
echo -e "${YELLOW}[2/3] Decoding JWT token...${NC}"

# Decode JWT payload (base64 decode the middle part)
JWT_PAYLOAD=$(echo "$ACCESS_TOKEN" | cut -d'.' -f2 | base64 -d 2>/dev/null || echo "$ACCESS_TOKEN" | cut -d'.' -f2 | tr '_-' '/+' | base64 -d 2>/dev/null)

if [[ -n "$JWT_PAYLOAD" ]]; then
    ISS=$(echo "$JWT_PAYLOAD" | jq -r '.iss // "N/A"')
    SUB=$(echo "$JWT_PAYLOAD" | jq -r '.sub // "N/A"')
    EXP=$(echo "$JWT_PAYLOAD" | jq -r '.exp // "N/A"')
    AZP=$(echo "$JWT_PAYLOAD" | jq -r '.azp // "N/A"')
    
    echo -e "${GREEN}✓ Token decoded successfully${NC}"
    echo ""
    echo -e "${BLUE}Token Claims:${NC}"
    echo "  iss (Issuer):           $ISS"
    echo "  sub (Subject):          $SUB"
    echo "  azp (Authorized Party): $AZP"
    if [[ "$EXP" != "N/A" ]]; then
        EXP_DATE=$(date -d "@$EXP" 2>/dev/null || date -r "$EXP" 2>/dev/null || echo "N/A")
        echo "  exp (Expires):          $EXP_DATE"
    fi
else
    echo -e "${RED}✗ Failed to decode token payload${NC}"
fi

# Step 3: Call API through Kong
echo ""
echo -e "${YELLOW}[3/3] Testing API call through Kong...${NC}"
API_ENDPOINT="${API_BASE_URL}/api/v1/documents"
echo "  Endpoint: $API_ENDPOINT"
echo ""

API_RESPONSE=$(curl -s -w "\n%{http_code}" -X GET "$API_ENDPOINT" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "Content-Type: application/json" \
    2>&1)

HTTP_CODE=$(echo "$API_RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$API_RESPONSE" | sed '$d')

echo -e "${BLUE}API Response:${NC}"
echo "  HTTP Status: $HTTP_CODE"
echo ""

# Evaluate result
if [[ "$HTTP_CODE" == "200" ]]; then
    echo -e "${GREEN}✓ SUCCESS: API returned 200 OK${NC}"
    echo "  Response body (truncated):"
    echo "$RESPONSE_BODY" | jq '.' 2>/dev/null | head -20 || echo "$RESPONSE_BODY" | head -20
elif [[ "$HTTP_CODE" == "401" ]]; then
    if echo "$RESPONSE_BODY" | grep -q "No credentials found for given 'iss'"; then
        echo -e "${RED}✗ FAILED: Kong JWT issuer mismatch${NC}"
        echo "  This means Kong's jwt_secrets key doesn't match the token's 'iss' claim."
        echo "  Token iss: $ISS"
        echo "  Fix: Add jwt_secret with key='$ISS' in kong.yml"
    else
        echo -e "${YELLOW}⚠ Got 401 but NOT issuer mismatch (may be permission issue)${NC}"
    fi
    echo "  Response: $RESPONSE_BODY"
elif [[ "$HTTP_CODE" == "403" ]]; then
    echo -e "${YELLOW}⚠ Got 403 Forbidden (auth worked, but permission denied)${NC}"
    echo "  This indicates JWT validation passed but user lacks required permissions."
    echo "  Response: $RESPONSE_BODY"
else
    echo -e "${YELLOW}⚠ Unexpected HTTP status: $HTTP_CODE${NC}"
    echo "  Response: $RESPONSE_BODY"
fi

echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE} Verification Complete ${NC}"
echo -e "${BLUE}============================================${NC}"
