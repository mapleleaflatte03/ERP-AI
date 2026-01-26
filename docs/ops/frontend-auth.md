# Frontend Authentication Guide

## Overview

The UI must send a Bearer token for all `/api/*` requests. Kong Gateway requires JWT authentication.

## Authentication Flow

1. **Login**: User enters credentials in LoginModal
2. **Token Request**: UI calls Keycloak token endpoint (password grant)
3. **Token Storage**: Access token stored in `localStorage.erpx_token`
4. **API Calls**: Axios interceptor auto-attaches `Authorization: Bearer <token>`
5. **Logout**: Token cleared from memory and localStorage

## Key Files

| File | Purpose |
|------|---------|
| `src/lib/api.ts` | Central API client with axios interceptor |
| `src/components/Layout.tsx` | Auth guard - shows LoginModal if not authenticated |
| `src/components/LoginModal.tsx` | Login form with Keycloak integration |

## How Auth Works

### Token Interceptor (api.ts)

```typescript
this.client.interceptors.request.use((config) => {
  if (this.token) {
    config.headers.Authorization = `Bearer ${this.token}`;
  }
  return config;
});
```

### Auth Guard (Layout.tsx)

```typescript
const [isAuthenticated, setIsAuthenticated] = useState(() => api.isAuthenticated());

if (!isAuthenticated) {
  return <LoginModal onSuccess={handleLoginSuccess} />;
}
```

## Testing Authentication

### 1. Browser DevTools Test

1. Open https://app.welliam.codes in incognito mode
2. Login modal should appear
3. Enter credentials (e.g., `accountant / accountant123`)
4. After login, open DevTools → Network tab
5. Find request to `/api/v1/documents`
6. **Verify**: Request Headers should contain `Authorization: Bearer eyJ...`
7. **Verify**: Response should NOT be 401

### 2. Manual curl Test

```bash
# Get token
TOKEN=$(curl -s -X POST "https://auth.welliam.codes/realms/erpx/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=erpx-api" \
  -d "username=accountant" \
  -d "password=accountant123" | jq -r '.access_token')

# Test API
curl -s "https://app.welliam.codes/api/v1/documents" \
  -H "Authorization: Bearer $TOKEN" | jq '.total'
```

### 3. Check localStorage

In browser console after login:
```javascript
localStorage.getItem('erpx_token')  // Should return JWT string starting with "eyJ..."
```

## Troubleshooting

### 401 Unauthorized (Missing Token)

**Symptom**: Network tab shows no `Authorization` header

**Cause**: User not logged in, or token not saved

**Fix**: 
- Clear localStorage and reload
- Check LoginModal is showing
- Verify api.setToken() is called after login

### 401 Unauthorized (Invalid Token)

**Symptom**: Request has `Authorization` header but still 401

**Possible Causes**:
1. Token expired
2. Kong issuer mismatch (see kong-jwt-issuer-fix.md)
3. Invalid signature

**Fix**: Logout and login again to get fresh token

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE_URL` | `/api` | Base URL for API calls |
| `VITE_KEYCLOAK_URL` | `http://localhost:8180` | Keycloak server URL |

Production values in `ui/.env.production` (DO NOT COMMIT):
```
VITE_API_BASE_URL=/api
VITE_KEYCLOAK_URL=https://auth.welliam.codes
```

## Default Test Credentials

| Username | Password | Roles |
|----------|----------|-------|
| admin | admin123 | admin, accountant, manager |
| accountant | accountant123 | accountant |
| manager | manager123 | manager |
| viewer | viewer123 | viewer |
