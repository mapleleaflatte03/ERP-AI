# DevOps Audit & Fix Report - ERP-AI v1.0.3+

**Date:** 2026-02-01  
**Auditor:** Agent DevOps  
**Target:** Production deployment gap for PR #34

---

## 1. ROOT CAUSE ANALYSIS

### Vì sao web chưa đổi?

| Evidence | Finding |
|----------|---------|
| `git log de8660da -1` | Tag `v1.0.3` points to commit `de8660da` (PR #33), NOT `6687f30` (PR #34) |
| CD workflow runs | **0 runs** - workflow never triggered |
| CD trigger config (old) | Only `push tags v*` or `workflow_dispatch` |
| Production test | `/api/v1/approvals` ✅ (PR #33), `/api/v1/analyst/*` ❌ 404 (PR #34 not deployed) |

**Root Cause:** CD workflow only triggers on tag push. Tag `v1.0.3` was created BEFORE PR #34 merge, so new code was never built/deployed.

---

## 2. FILES CHANGED

| File | Change |
|------|--------|
| `.github/workflows/cd.yml` | Complete rewrite - added push to main trigger, workflow_dispatch with ref input, SHA-based image tags, smoke tests |
| `Dockerfile` | Added `ARG/ENV GIT_SHA, BUILD_TIME, VERSION` for version tracking |
| `api/main.py` | Added `/version` endpoint returning `{git_sha, build_time, api_version}` |
| `api/config_routes.py` | Fixed router prefix from `/config` → `/config/settings` path |
| `scripts/deploy_prod.sh` | **NEW** - Idempotent production deploy script |

---

## 3. CD WORKFLOW IMPROVEMENTS

### Triggers (NEW)
```yaml
on:
  push:
    branches: [main]  # NEW - deploy on main push
    tags: ['v*']      # Keep backward compat
  workflow_dispatch:
    inputs:
      ref:            # NEW - deploy any ref
        default: 'main'
      environment:
        options: [staging, production]
      skip_staging:   # NEW - hotfix bypass
```

### Image Tagging Strategy
- **Primary:** `ghcr.io/mapleleaflatte03/erp-ai/api:<full-sha>` (immutable)
- **Secondary:** `api:<short-sha>`, `api:main` (mutable)
- **Release:** `api:v1.0.4`, `api:latest` (on tag push)

### Security & Control
- `concurrency: deploy-production` prevents parallel deploys
- `environment: production` requires approval (configure in GitHub Settings > Environments)
- Preflight job checks for missing secrets and fails early

---

## 4. HOW TO DEPLOY (NO TAG REQUIRED)

### Option A: Trigger from GitHub UI
1. Go to **Actions** > **CD** workflow
2. Click **Run workflow**
3. Select:
   - `ref`: `main` (or specific SHA like `6687f30`)
   - `environment`: `production`
   - `skip_staging`: `false`
4. Click **Run workflow**

### Option B: Push to main
- Any push to `main` branch triggers CD
- Requires approval via `production` environment protection

### Option C: CLI (GitHub CLI)
```bash
gh workflow run cd.yml -f ref=main -f environment=production
```

---

## 5. REQUIRED SECRETS

Configure in **Settings > Secrets and variables > Actions**:

| Secret | Description | Example |
|--------|-------------|---------|
| `PROD_HOST` | Production server IP/hostname | `app.welliam.codes` |
| `PROD_USER` | SSH username | `deploy` |
| `PROD_SSH_KEY` | Private SSH key (base64 or raw) | `-----BEGIN OPENSSH...` |
| `STAGING_HOST` | (Optional) Staging server | |
| `STAGING_USER` | (Optional) SSH user | |
| `STAGING_SSH_KEY` | (Optional) SSH key | |

---

## 6. ACCEPTANCE CRITERIA

After successful deployment:

| Test | Expected Result |
|------|-----------------|
| `curl https://app.welliam.codes/api/version` | `{"git_sha":"6687f30...", "api_version":"1.0.0", ...}` |
| `curl https://app.welliam.codes/api/v1/config/settings` | `200 OK` with config JSON |
| `curl https://app.welliam.codes/api/v1/analyst/history` | `200 OK` or `401 Unauthorized` (NOT `404`) |
| `curl -I https://app.welliam.codes/api/openapi.json` | `Content-Type: application/json` |

---

## 7. ENDPOINT MAPPING (PR #34)

| Endpoint | Router | File |
|----------|--------|------|
| `GET /v1/config/settings` | config_router | `api/config_routes.py:29` |
| `GET /v1/config/import/server/list` | config_router | `api/config_routes.py:70` |
| `POST /v1/config/import/server` | config_router | `api/config_routes.py:179` |
| `POST /v1/analyst/query` | analyst_router | `api/analyst_routes.py:246` |
| `GET /v1/analyst/history` | analyst_router | `api/analyst_routes.py:304` |
| `POST /v1/reconciliation/*` | reconciliation_router | `api/reconciliation_routes.py` |

---

## 8. DEPLOY SCRIPT USAGE

On production server (`/opt/erp-ai`):

```bash
# Deploy specific SHA
IMAGE_TAG=6687f3094e1a40398a53f2186acf1db5266163b3 ./scripts/deploy_prod.sh

# Deploy main tag
IMAGE_TAG=main ./scripts/deploy_prod.sh

# With GHCR token (for private images)
GITHUB_TOKEN=ghp_xxx ./scripts/deploy_prod.sh
```

---

## 9. POST-DEPLOYMENT VERIFICATION

```bash
# 1. Check version
curl -s https://app.welliam.codes/api/version | jq

# 2. Check health
curl -s https://app.welliam.codes/api/health | jq '.status'

# 3. Check PR #34 endpoints exist
curl -s -o /dev/null -w "%{http_code}" https://app.welliam.codes/api/v1/analyst/history
curl -s -o /dev/null -w "%{http_code}" https://app.welliam.codes/api/v1/config/settings

# 4. Check OpenAPI not swallowed by SPA
curl -s -o /dev/null -w "%{content_type}" https://app.welliam.codes/api/openapi.json
```

---

**Status:** ✅ Ready for commit and deployment
