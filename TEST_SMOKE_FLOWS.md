# TEST_SMOKE_FLOWS.md - ERPX AI Kế Toán

**Version tested:** v2.0.0  
**Date:** 2026-02-02  
**Tester:** QA Automated  
**Branch:** fix/qa-v2.0.0

---

## Môi trường Test

| Service | URL | Status |
|---------|-----|--------|
| UI (Production) | http://localhost:3002 | ✅ Running |
| API (Direct) | http://localhost:8000 | ✅ Healthy (degraded - vector_db) |
| PostgreSQL | localhost:5432 | ✅ Healthy |
| Temporal Worker | erpx-worker | ✅ Running |
| Keycloak | http://localhost:8180 | ✅ Healthy |

---

## Bugs Fixed in QA Session

| # | Area | Issue | Root Cause | Fix |
|---|------|-------|------------|-----|
| 1 | Worker | `No module named 'api.agent_routes'` | Container missing files | Rebuilt worker container |
| 2 | Timeline | Payload rendered as characters | JSON string not parsed | Added `json.loads()` in API |
| 3 | Approvals | `/v1/approvals/pending` returns 500 | Route conflict with `/{id}` | Added explicit `/pending` route before `/{id}` |
| 4 | Copilot | `approve_proposal` returns error | Called deprecated function | Direct DB update in chat handler |

---

## Flow 1 – Upload → OCR → Journal Proposal → Approve

### API Test Results

```bash
# Upload
curl -X POST "http://localhost:8000/v1/upload" \
  -F "file=@test.png" -F "tenant_id=00000000-0000-0000-0000-000000000001"
# Response: {"job_id": "...", "status": "queued"} ✅

# Check document
curl "http://localhost:8000/v1/documents?limit=1"
# Response: {status: "processed", filename: "test.png"} ✅
```

### Results

| Bước | Status | Ghi chú |
|------|--------|---------|
| Upload | ✅ PASS | job_id returned |
| OCR Processing | ✅ PASS | status: processed |
| Journal Proposal | ✅ PASS | proposal created with AI reasoning |
| Approval Created | ✅ PASS | approval linked to proposal |

**Kết luận Flow 1:** ✅ PASS

---

## Flow 2 – Evidence Timeline

### API Test Results

```bash
curl "http://localhost:8000/v1/evidence/timeline?limit=2"
# Response: {events: [{payload: {object}}, ...]} ✅
```

### Results

| Chức năng | Status | Ghi chú |
|-----------|--------|---------|
| Timeline endpoint | ✅ PASS | Returns events |
| Payload parsing | ✅ PASS | Returns dict, not string |
| Event data | ✅ PASS | Includes doc_type, latency |

**Kết luận Flow 2:** ✅ PASS

---

## Flow 3 – Pending Approvals

### API Test Results

```bash
curl "http://localhost:8000/v1/approvals/pending?limit=3"
# Response: {success: true, data: [...], count: 3} ✅
```

### Results

| Chức năng | Status | Ghi chú |
|-----------|--------|---------|
| /pending route | ✅ PASS | No longer conflicts with /{id} |
| Pending list | ✅ PASS | Returns vendor, amount, filename |
| Filter by status | ✅ PASS | Only status=pending returned |

**Kết luận Flow 3:** ✅ PASS

---

## Flow 4 – Copilot Chat + Actions

### API Test Results

```bash
# List pending
curl -X POST "http://localhost:8000/v1/copilot/chat" \
  -d '{"session_id":"test","message":"Liệt kê chứng từ chờ duyệt"}'
# Response: {response: "**Danh sách chờ duyệt:**..."} ✅

# Request approval (returns action button)
curl -X POST "http://localhost:8000/v1/copilot/chat" \
  -d '{"message":"Duyệt chứng từ dc0de337..."}'
# Response: {actions: [{label: "Duyệt chứng từ...", tool: "approve_proposal"}]} ✅

# Confirm action
curl -X POST "http://localhost:8000/v1/copilot/chat" \
  -d '{"context":{"confirmed_action":{"tool":"approve_proposal","params":{"id":"..."}}}}'
# Response: {response: "✅ Đã duyệt chứng từ..."} ✅
```

### Results

| Chức năng | Status | Ghi chú |
|-----------|--------|---------|
| List pending | ✅ PASS | LLM calls tool, formats response |
| Request approval | ✅ PASS | Returns action button for UI |
| Confirm action | ✅ PASS | Updates DB, creates audit log |
| Statistics | ✅ PASS | pending/approved/rejected counts |

**Kết luận Flow 4:** ✅ PASS

---

## Flow 5 – Agent Action Hub

### API Test Results

```bash
# Approve flow works via Copilot confirmed_action
# DB verification:
# SELECT status, approver_name FROM approvals WHERE id = '...'
# => status: approved, approver_name: Copilot ✅
```

### Results

| Chức năng | Status | Ghi chú |
|-----------|--------|---------|
| Action proposal | ✅ PASS | Copilot returns action object |
| UI card display | ✅ PASS | FE renders action buttons |
| Confirm action | ✅ PASS | Updates approval + proposal status |
| Audit logging | ✅ PASS | audit_events created |

**Kết luận Flow 5:** ✅ PASS

---

## Tổng kết Test

| Flow | Tên | Status |
|------|-----|--------|
| 1 | Upload → OCR → Proposal → Approve | ✅ PASS |
| 2 | Evidence Timeline | ✅ PASS |
| 3 | Pending Approvals | ✅ PASS |
| 4 | Copilot Chat + Actions | ✅ PASS |
| 5 | Agent Action Hub | ✅ PASS |

**Tổng:** 5/5 PASS | 0/5 PENDING | 0/5 FAIL

---

## Files Modified

| File | Change |
|------|--------|
| `src/api/main.py` | Added `import json`, fixed timeline payload parsing, fixed Copilot confirmed_action handler |
| `api/approval_routes.py` | Added explicit `/pending` route before `/{approval_id}` |

---

## Hướng dẫn chạy test

### Yêu cầu
- Docker + docker compose đang chạy
- Services healthy (chạy `docker compose ps`)

### Bước 1: Khởi động môi trường
```bash
cd /root/erp-ai
docker compose up -d
docker compose ps
```

### Bước 2: Run smoke tests
```bash
# Upload test
curl -X POST "http://localhost:8000/v1/upload" \
  -F "file=@test.png" -F "tenant_id=00000000-0000-0000-0000-000000000001"

# Check documents
curl "http://localhost:8000/v1/documents?limit=5"

# Check pending approvals
curl "http://localhost:8000/v1/approvals/pending?limit=5"

# Test Copilot
curl -X POST "http://localhost:8000/v1/copilot/chat" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"test","message":"Liệt kê chứng từ chờ duyệt"}'
```

---

*Last updated: 2026-02-02 (QA v2.0.0)*
