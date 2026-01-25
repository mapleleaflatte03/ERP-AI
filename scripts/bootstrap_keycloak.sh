#!/bin/bash
# Bootstrap Keycloak - Ensure realm and users exist
# =================================================

set -e

KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:8180}"
REALM="erpx"
ADMIN_USER="admin"
ADMIN_PASS="admin_secret"

echo "🔐 Bootstrapping Keycloak..."

# Wait for Keycloak to be ready
for i in {1..30}; do
    if curl -s "$KEYCLOAK_URL/realms/master" >/dev/null 2>&1; then
        echo "✅ Keycloak is ready"
        break
    fi
    echo "⏳ Waiting for Keycloak... ($i/30)"
    sleep 2
done

# Get admin token
echo "🔑 Getting admin token..."
ADMIN_TOKEN=$(curl -s -X POST "$KEYCLOAK_URL/realms/master/protocol/openid-connect/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=$ADMIN_USER" \
    -d "password=$ADMIN_PASS" \
    -d "grant_type=password" \
    -d "client_id=admin-cli" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)

if [ -z "$ADMIN_TOKEN" ]; then
    echo "❌ Failed to get admin token"
    exit 1
fi

# Check if realm exists
REALM_EXISTS=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    "$KEYCLOAK_URL/admin/realms/$REALM")

if [ "$REALM_EXISTS" != "200" ]; then
    echo "📦 Creating realm: $REALM"
    curl -s -X POST "$KEYCLOAK_URL/admin/realms" \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        -H "Content-Type: application/json" \
        -d '{
            "realm": "'"$REALM"'",
            "enabled": true,
            "registrationAllowed": false,
            "loginWithEmailAllowed": true,
            "duplicateEmailsAllowed": false,
            "resetPasswordAllowed": true,
            "editUsernameAllowed": false,
            "bruteForceProtected": true
        }'
    echo "✅ Realm created"
else
    echo "✅ Realm $REALM already exists"
fi

# Create/update erpx-web client (for UI - public with PKCE)
echo "🔧 Configuring erpx-web client..."
curl -s -X POST "$KEYCLOAK_URL/admin/realms/$REALM/clients" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "clientId": "erpx-web",
        "name": "ERPX Web UI",
        "enabled": true,
        "publicClient": true,
        "standardFlowEnabled": true,
        "directAccessGrantsEnabled": true,
        "redirectUris": ["http://localhost:3002/*", "http://localhost:3000/*"],
        "webOrigins": ["http://localhost:3002", "http://localhost:3000", "*"],
        "attributes": {
            "pkce.code.challenge.method": "S256"
        }
    }' 2>/dev/null || true

# Create/update erpx-api client (for API - bearer only)
echo "🔧 Configuring erpx-api client..."
curl -s -X POST "$KEYCLOAK_URL/admin/realms/$REALM/clients" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "clientId": "erpx-api",
        "name": "ERPX API",
        "enabled": true,
        "publicClient": true,
        "standardFlowEnabled": false,
        "directAccessGrantsEnabled": true,
        "bearerOnly": false
    }' 2>/dev/null || true

# Function to create user
create_user() {
    local username=$1
    local password=$2
    local email="${username}@erpx.local"
    
    echo "👤 Creating user: $username"
    
    # Create user
    curl -s -X POST "$KEYCLOAK_URL/admin/realms/$REALM/users" \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        -H "Content-Type: application/json" \
        -d '{
            "username": "'"$username"'",
            "email": "'"$email"'",
            "enabled": true,
            "emailVerified": true,
            "credentials": [{
                "type": "password",
                "value": "'"$password"'",
                "temporary": false
            }]
        }' 2>/dev/null || true
}

# Create demo users
create_user "admin" "admin123"
create_user "accountant" "accountant123"
create_user "manager" "admin123"
create_user "viewer" "admin123"

echo ""
echo "✅ Keycloak bootstrap complete!"
echo ""
echo "Demo users:"
echo "  - admin / admin123"
echo "  - accountant / accountant123"
echo "  - manager / admin123"
