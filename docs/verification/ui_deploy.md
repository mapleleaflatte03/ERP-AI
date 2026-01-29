# UI Deployment Verification

## Deployment Details
- **Date**: 2026-01-29T17:00:00Z
- **Git SHA**: `140e9533a96f2eac07c203da15c280c9e8772261`
- **Commit Message**: `fix(ui): stop accessing private api client in DocumentPreview`

---

## Docker Container Verification

### Container Status
```bash
$ docker ps | grep erpx-ui
b065410a7d9b   erp-ai-ui   "/docker-entrypoint.…"   Up 10 seconds (healthy)   0.0.0.0:3002->80/tcp   erpx-ui
```
**Status**: ✅ Running & Healthy

### Container Image
```bash
$ docker inspect erpx-ui --format '{{.Image}}'
sha256:d5b37ef59d974de2d9fa0095525e2f65bd8d8789b524e47d4d7da1e4963dd887
```

### Docker Build Output
```
✓ 2530 modules transformed.                 
dist/index.html                   0.45 kB │ gzip:   0.29 kB
dist/assets/index-ChfgIKUQ.css   56.02 kB │ gzip:   9.72 kB
dist/assets/index-BW4sEHJI.js   864.56 kB │ gzip: 261.94 kB
✓ built in 6.29s
```

---

## Git SHA Verification

| Location | SHA |
|----------|-----|
| Local HEAD | `140e9533a96f2eac07c203da15c280c9e8772261` |
| Remote main | `140e9533a96f2eac07c203da15c280c9e8772261` |

**Status**: ✅ Consistent

---

## Web Version Hash

> [!NOTE]
> Web version hash not exposed via UI meta tag or version.json. 
> Container verified via Docker image digest instead.

If version hash is needed, consider adding a `version.json` or meta tag in future builds.

---

## Summary

| Verification | Status |
|--------------|--------|
| npm run build | ✅ PASS |
| docker compose build ui | ✅ PASS |
| Container running new image | ✅ PASS |
| Git SHA consistent | ✅ PASS |
| TS2341 Error | ✅ FIXED |

## Overall Status: ✅ PASS
