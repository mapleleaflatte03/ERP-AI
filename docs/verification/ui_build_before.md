# UI Build Baseline (Before Fix)

## Environment
- **Git SHA**: `72c97f8960b0a15fdc51a4664f8f037036c54207`
- **Node**: v20.20.0
- **npm**: 10.8.2
- **Date**: 2026-01-29T16:56:00Z

## Build Command
```bash
cd /root/erp-ai/ui && npm run build
```

## Build Output (ERROR)
```
> ui@0.0.0 build
> tsc -b && vite build

src/components/DocumentPreview.tsx(68,48): error TS2341: Property 'client' is private and only accessible within class 'ApiClient'.
```

## Root Cause
- `DocumentPreview.tsx` line 68 accesses `api.client.get(...)` directly
- `client` is declared as `private` in `ApiClient` class
- TypeScript enforces private access → build FAIL

## Status: ❌ FAIL
