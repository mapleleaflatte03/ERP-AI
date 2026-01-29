# UI Build Verification (After Fix)

## Environment
- **Date**: 2026-01-29T16:58:00Z

## Changes Made

### File 1: `ui/src/lib/api.ts`
Added public method `getFilePreview()`:
```typescript
// Lấy preview dạng text/HTML (dùng cho XLSX preview)
async getFilePreview(url: string): Promise<string> {
  const response = await this.client.get(url, { responseType: 'text' });
  return response.data as string;
}
```

### File 2: `ui/src/components/DocumentPreview.tsx`
Changed line 68:
```diff
- const response = await api.client.get(previewUrl);
+ const htmlString = await api.getFilePreview(previewUrl);
```

Changed line 71:
```diff
- setBlobUrl(response.data);
+ setBlobUrl(htmlString);
```

## Build Command
```bash
cd /root/erp-ai/ui && npm run build
```

## Build Output (SUCCESS)
```
> ui@0.0.0 build
> tsc -b && vite build

vite v7.3.1 building client environment for production...
✓ 2530 modules transformed.                 
dist/index.html                   0.45 kB │ gzip:   0.29 kB
dist/assets/index-ChfgIKUQ.css   56.02 kB │ gzip:   9.72 kB
dist/assets/index-BW4sEHJI.js   864.56 kB │ gzip: 261.94 kB
✓ built in 5.22s
```

## Status: ✅ PASS

- No TS2341 error
- TypeScript compilation successful
- Vite build completed
- Output bundle: `dist/assets/index-BW4sEHJI.js`
