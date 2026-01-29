# Production Version Baseline (Before Fix)

## Date
- **Verification Date**: 2026-01-29T17:16:00Z

## Git SHA
```bash
$ git rev-parse HEAD
ac2785777224c31bf004113fdaa07b69d29a1e30

$ git ls-remote origin main | head -1
ac2785777224c31bf004113fdaa07b69d29a1e30  refs/heads/main
```
**Status**: Local and remote SHA match ✅

---

## Production Web Check

### Homepage Headers
```bash
$ curl -sS -D - https://app.welliam.codes/ -o /tmp/index.html | head -n 40
```
```
HTTP/2 200 
alt-svc: h3=":443"; ma=2592000
cache-control: no-store
content-type: text/html
date: Thu, 29 Jan 2026 17:15:42 GMT
etag: W/"697b92aa-1c1"
last-modified: Thu, 29 Jan 2026 17:02:34 GMT
server: Caddy
server: nginx/1.29.4
x-erp-build: 232313e
```

**Observations**:
- `x-erp-build: 232313e` ← **MISMATCH** with current SHA `ac27857`
- Served by Caddy + nginx

### Bundle File
```bash
$ grep -oE "assets/index-[A-Za-z0-9_-]+\.js" /tmp/index.html
assets/index-BW4sEHJI.js
```

### /v1/version Endpoint (Production)
```bash
$ curl -s https://app.welliam.codes/v1/version | head -20
```
```html
<!doctype html>
<html lang="en">
  <head>...
```
**Status**: ❌ Returns index.html, NOT JSON
**Root Cause**: Reverse proxy NOT routing `/v1/*` to backend API

### /v1/health Endpoint (Production)
```bash
$ curl -sI https://app.welliam.codes/v1/health
```
```
HTTP/2 200 
content-type: text/html  ← WRONG! Should be application/json
```
**Status**: ❌ Same issue - API routes not reaching backend

---

## Local API Check (Control)
```bash
$ curl -s http://localhost:8000/v1/version
{"commit":"unknown","build_time":"2026-01-30T00:16:13.345648","status":"active"}
```
**Status**: ✅ Local backend works correctly

---

## Diagnosis

| Issue | Description |
|-------|-------------|
| **ROOT CAUSE** | Production reverse proxy (Caddy → nginx) not forwarding `/v1/*` to backend API |
| **Symptom 1** | `/v1/version` returns HTML instead of JSON |
| **Symptom 2** | `x-erp-build` header shows old SHA `232313e` instead of current `ac27857` |
| **Impact** | All API calls from production UI fail (return 404/HTML) |

## Required Fixes

1. Fix reverse proxy configuration to route `/v1/*` → backend API
2. Inject `GIT_COMMIT` env var during Docker build
3. Create `/version.json` for UI version exposure
