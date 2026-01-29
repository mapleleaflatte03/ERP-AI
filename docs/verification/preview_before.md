# Preview Mechanism Baseline (Before Fix)

## Date
- **Verification Date**: 2026-01-29T17:19:00Z

## Current Preview Implementation

### Backend Endpoint
```
GET /v1/documents/{document_id}/preview
```
- Returns file stream for PDF/Image
- Returns HTML table for XLSX when `?preview=true`

### UI Component (DocumentPreview.tsx)

**XLSX Preview (lines 65-75)**:
```typescript
if (isExcel) {
    const previewUrl = effectiveUrl.includes('?') ? `${effectiveUrl}&preview=true` : `${effectiveUrl}?preview=true`;
    const htmlString = await api.getFilePreview(previewUrl);  // ✅ Uses public method
    if (active) {
        setBlobUrl(htmlString);  // HTML string for rendering
    }
    return;
}
```

**PDF/Image Preview (lines 77-84)**:
```typescript
const blob = await api.getFileBlob(effectiveUrl);  // ✅ Uses public method with auth
const objectUrl = URL.createObjectURL(blob);       // ✅ Creates blob URL
if (active) {
    setBlobUrl(objectUrl);
}
```

## Auth-Safe Verification ✅

| Aspect | Status | Evidence |
|--------|--------|----------|
| Uses `api.getFilePreview()` for XLSX | ✅ | Line 68 |
| Uses `api.getFileBlob()` for PDF/Image | ✅ | Line 78 |
| Creates blob URL | ✅ | Line 79 |
| Does NOT use direct `/v1/files/` URLs | ✅ | No direct URL usage |
| Auth headers included via ApiClient | ✅ | ApiClient interceptor adds Authorization |

## Previous Issue

The previous issue (TS2341 error) was fixed in commit `140e953`:
- Changed `api.client.get()` to `api.getFilePreview()` (private → public method)

## Remaining Issue

The production routing problem (identified in M1) means:
- `/v1/*` routes were NOT forwarded to backend
- Even correct UI code would fail because nginx returned index.html for API calls

This has been fixed in `ui/nginx.conf` by adding `/v1/` location block.

## Status: ✅ Preview Code is Correct

The preview mechanism is properly implemented. The issue was the nginx routing, not the preview code itself.
