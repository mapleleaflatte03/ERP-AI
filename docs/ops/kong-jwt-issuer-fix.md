# Kong JWT Issuer Configuration Guide

## Problem: "No credentials found for given 'iss'"

When Kong returns a 401 error with this message:
```json
{"message":"No credentials found for given 'iss'"}
```

This means the JWT `iss` (issuer) claim doesn't match any `key` in Kong's `jwt_secrets`.

## Root Cause

Kong's JWT plugin uses `key_claim_name: iss` (default) to look up credentials.
The lookup process:
1. Extract `iss` claim from JWT token
2. Search `jwt_secrets` for a matching `key`
3. If no match → 401 "No credentials found for given 'iss'"

### Common Scenario: HTTP → HTTPS Migration

When Keycloak's issuer changes from:
- `http://auth.welliam.codes/realms/erpx` 
- to `https://auth.welliam.codes/realms/erpx`

Existing tokens and new tokens will have different `iss` values. Kong must have credentials for both.

## Solution

### 1. Add new jwt_secret in kong.yml

Edit `infrastructure/kong/kong.yml`:

```yaml
consumers:
  - username: keycloak-users
    custom_id: keycloak-erpx
    jwt_secrets:
      # Production HTTPS issuer (current)
      - key: https://auth.welliam.codes/realms/erpx
        algorithm: RS256
        rsa_public_key: |
          -----BEGIN PUBLIC KEY-----
          <public key from Keycloak JWKS>
          -----END PUBLIC KEY-----
      # Legacy HTTP issuer (backward compatibility)  
      - key: http://auth.welliam.codes/realms/erpx
        algorithm: RS256
        rsa_public_key: |
          -----BEGIN PUBLIC KEY-----
          <same public key>
          -----END PUBLIC KEY-----
```

### 2. Get Keycloak Public Key

```bash
# From JWKS endpoint
curl -s https://auth.welliam.codes/realms/erpx/protocol/openid-connect/certs \
  | jq -r '.keys[] | select(.use=="sig" and .kty=="RSA") | .x5c[0]' \
  | head -1 \
  | base64 -d \
  | openssl x509 -pubkey -noout
```

### 3. Reload Kong

Since Kong runs in DB-less mode:
```bash
docker restart erpx-kong
```

### 4. Verify

Use the verification script:
```bash
export ERPX_USER=admin
export ERPX_PASS=admin123
./scripts/verify_kong_jwt.sh
```

## Key Points

1. **jwt_secret key MUST exactly match token's iss claim** (including http/https)
2. **Keep old keys** for backward compatibility during migration
3. **rsa_public_key is safe to commit** (it's public)
4. **Reload Kong** after config changes (DB-less requires restart)

## Keycloak Configuration

To ensure Keycloak issues tokens with HTTPS issuer:

```yaml
# docker-compose.yml
keycloak:
  command:
    - start-dev
    - --proxy-headers=xforwarded
    - --hostname=auth.welliam.codes
```

Verify issuer:
```bash
curl -s https://auth.welliam.codes/realms/erpx/.well-known/openid-configuration | jq -r '.issuer'
# Should return: https://auth.welliam.codes/realms/erpx
```

## Troubleshooting

### Check current JWT secrets
```bash
grep -A10 "jwt_secrets" infrastructure/kong/kong.yml
```

### Decode token to see iss
```bash
TOKEN="eyJ..."
echo "$TOKEN" | cut -d'.' -f2 | tr '_-' '/+' | base64 -d | jq -r '.iss'
```

### Kong logs
```bash
docker logs erpx-kong --tail 50
```
