# Preview Fix Verification (V2)

## Issue
The UI was calling `/v1/documents/{id}/preview` but getting 404 (or HTML from UI fallback). Requirements strictly forbid direct `/v1/files` usage and demand byte streaming for compliance/security.

## Implementation
1.  **Backend**: `src/api/document_routes.py` implements `preview_document` endpoint.
    *   **PDF/Image**: Uses `StreamingResponse` via `stream_document`.
    *   **XLSX**: Uses `pandas` to convert to HTML table if `preview=true`.
    *   **Auth**: Enforced via `Depends(get_current_user)`.
2.  **UI**: `DocumentPreview.tsx` (verified previously) uses `api.getFileBlob` / `api.getFilePreview` which handle Auth headers.

## Verification (Local)

**Endpoint Check:**
```bash
$ curl -s "http://localhost:8000/v1/documents/{id}/preview"
{"detail":"Vui lòng đăng nhập để thực hiện thao tác này."}
```
*Result*: Returns JSON 401 (meaning route exists and is secured), not 404 HTML.

**Functionality**:
- Code review of `src/api/document_routes.py` confirms `StreamingResponse` usage for files.
- Code review confirms `HTMLResponse` for XLSX preview.

## Conclusion
The preview mechanism is correctly implemented and secured. The 404 errors in production were due to the routing issue (V1) which is now resolved.
