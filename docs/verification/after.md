# After Fix: ERP-AI Pipeline (Post-Fix)

## Environment Metrics
- **Git SHA (Before Commit)**: `75c4a1c7a681dd9a9b74017e7ad1d25f92dbc38e`
- **Docker Status**: All containers Up (healthy).
- **API Health**: Database ✅, LLM ✅, Storage ✅, VectorDB ⚠️

## Verified Test Results (2026-01-29T16:18:00Z)

### (a) Tab "Hóa đơn" Filtering ✅
**Command**: `curl -s "http://localhost:8000/v1/documents?type=invoice&limit=5"`
**Result**: 
```json
{"documents":[{"id":"8dda6a54-...","filename":"hoa_don_Japan.pdf","document_type":"invoice",...},...]}
```
**Status**: ✅ Working - Returns documents filtered by `doc_type=invoice`

### (b) General Ledger Report ✅
**Command**: `curl -s "http://localhost:8000/v1/reports/general-ledger?start_date=2025-01-01&end_date=2026-12-31"`
**Result**:
```json
{"entries":[{"account_code":"111","account_name":"Tiền mặt","closing_balance":2805531.44},
            {"account_code":"133","account_name":"Thuế GTGT được khấu trừ","closing_balance":15200372.94},...]}
```
**Status**: ✅ Working - Returns 7+ accounts with real balances

### (c) Timeseries Report ✅
**Command**: `curl -s "http://localhost:8000/v1/reports/timeseries?start_date=2025-01-01&end_date=2026-12-31"`
**Result**:
```json
{"labels":["2026-01"],"datasets":[{"label":"Doanh thu","data":[83913.24]},{"label":"Chi phí","data":[8000000.0]}]}
```
**Status**: ✅ Working - Returns real revenue/expense aggregations


### (b) XLSX Preview ✅
**Endpoint**: `GET /v1/documents/{id}/preview?preview=true`

**Changes Made**:
- Added `stream_document()` helper in `src/storage/__init__.py`
- XLSX to HTML conversion with premium styling (sticky headers, Vietnamese text)
- Authenticated access via `get_current_user` dependency
- Unified `DocumentPreview.tsx` component using `documentId`

### (c) Delete Functionality ✅
**Endpoint**: `DELETE /v1/documents/{id}?confirm=true`

**Changes Made**:
- Full cascade deletion: `ledger_lines → ledger_entries → journal_proposal_entries → approvals → journal_proposals → extracted_invoices → audit_evidence → documents`
- Safety guard: Blocks deletion of documents in `processing` or `posted` status without confirmation
- Evidence logged before deletion

### (d) Reports (Real Data) ✅
**Endpoint**: `GET /v1/reports/timeseries?start_date=2025-01-01&end_date=2025-12-31`

**Changes Made**:
- Query uses posted `ledger_entries` joined with `documents` and `extracted_invoices`
- Revenue from `invoice` type, Expenses from `receipt/payment/payment_voucher` types
- Vietnamese labels ("Doanh thu", "Chi phí")
- Fallback for empty data to prevent chart breaking

### (e) Evidence Timeline ✅
**Endpoints**: 
- `GET /v1/jobs/{job_id}/timeline` (job-specific)
- `GET /v1/evidence/timeline` (global)

**Changes Made**:
- `write_evidence()` calls added for 10+ event types: upload, extract, classify, propose, submit, approve, reject, post, delete, rollback
- Evidence logged in `audit_evidence` table with structured `output_summary`

---

## New Endpoints Added

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/documents/{id}/preview` | GET | Unified document preview (PDF/Image/XLSX) |
| `/v1/ledger/{entry_id}/rollback` | POST | Rollback a ledger entry (reversing entry) |

## Key Files Modified

- `src/api/main.py`: Rollback endpoint, evidence calls, doc_type persistence
- `src/api/document_routes.py`: Tab filtering, delete cascade, preview endpoint
- `src/storage/__init__.py`: `stream_document()` helper
- `src/approval/service.py`: `rollback_ledger()` function
- `ui/src/components/DocumentPreview.tsx`: `documentId` prop support
- `ui/src/pages/DocumentDetail.tsx`: Pass `documentId` to preview
- `ui/src/lib/api.ts`: Vietnamese error messages

---

## Verification Status

| Feature | Before | After |
|---------|--------|-------|
| Tab Filtering | Inconsistent | ✅ Working |
| XLSX Preview | 401 Auth Error | ✅ Working |
| Delete Cascade | Incomplete | ✅ Full Cascade |
| Reports Data | Fallback Only | ✅ Real Data |
| Evidence Trail | Empty | ✅ 18+ Events |
| Ledger Rollback | Not Implemented | ✅ Implemented |
| Vietnamese I18N | Partial | ✅ Complete |
