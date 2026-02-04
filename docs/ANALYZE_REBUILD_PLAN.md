# Agent Analytics Module - Rebuild Plan

## Status: ✅ COMPLETED (fix/agent-analytics-v3)

## 1. Hiện trạng trước rebuild (as-is)

### Frontend (`ui/src/pages/Analytics.tsx`)
- ❌ Có tab "AI Chat" riêng trong Analytics page → Thừa với ModuleChatDock
- ❌ Buttons "Xem dữ liệu", "Export", "Xóa" trong DatasetsTab không hoạt động
- ❌ API paths sử dụng `/v1/analytics/*` không đúng với backend routes `/v1/analyze/*`
- ❌ Không có Clean data functionality

### Backend (`api/analyze_routes.py`)
- ✅ Upload dataset hoạt động (POST /analyze/datasets/upload)
- ✅ List datasets hoạt động (GET /analyze/datasets)
- ✅ Get dataset details hoạt động (GET /analyze/datasets/{id})
- ✅ Delete dataset hoạt động (DELETE /analyze/datasets/{id})
- ❌ Thiếu endpoint preview (GET /analyze/datasets/{id}/preview)
- ❌ Thiếu endpoint clean (POST /analyze/datasets/{id}/clean)
- ❌ Thiếu endpoint export (GET /analyze/datasets/{id}/export)

### Evidence Page (`ui/src/pages/Evidence.tsx`)
- ❌ Sử dụng Tailwind cơ bản, không đồng bộ với Quantum UI design system

---

## 2. Vấn đề chính cần giải quyết

1. **AI Chat tab thừa**: ModuleChatDock đã cung cấp chat functionality, không cần tab riêng
2. **Buttons không hoạt động**: Dataset management buttons (Preview, Clean, Export, Delete) chỉ có UI, không có logic
3. **API path mismatch**: Frontend gọi `/v1/analytics/*` nhưng backend expose `/v1/analyze/*`
4. **Missing backend endpoints**: Preview, Clean, Export endpoints chưa có
5. **UI inconsistency**: Evidence page chưa follow Quantum design system

---

## 3. Design To-be (Julius-style)

### Analytics Page Tabs
| Tab | Mô tả |
|-----|-------|
| Dashboard | Canvas hiển thị Analysis Results Feed (charts, tables, insights) |
| Explorer | SQL query interface cho datasets |
| Dự báo | Forecast form với dataset/time_col/value_col selection |
| Datasets | Upload + CRUD datasets với Preview/Clean/Export/Delete |

**Đã xóa**: Tab "AI Chat" (chat đi qua ModuleChatDock floating button)

### API Architecture
```
/v1/analyze/
├── datasets/
│   ├── upload      POST  - Upload CSV/XLSX
│   ├── {id}        GET   - Dataset details
│   ├── {id}        DELETE - Delete dataset
│   ├── {id}/preview GET  - Preview rows (limit=200)
│   ├── {id}/clean   POST  - Clean data pipeline
│   └── {id}/export  GET   - Download CSV
├── query           POST  - NL2SQL query
├── reports         GET   - Pre-built report templates
└── reports/{id}/run POST - Execute report
```

---

## 4. File Changes Summary

### Commit 1: `feat(ui): apply Quantum UI to Evidence page + remove AI Chat tab`
| File | Changes |
|------|---------|
| `ui/src/pages/Evidence.tsx` | +Quantum header, tabs, stats, cards; +ModuleChatDock |
| `ui/src/pages/Analytics.tsx` | -AI Chat tab, -ChatTab/MessageBubble/ToolResultCard components, -unused imports |

### Commit 2: `feat(analytics): add preview/clean/export endpoints + fix FE buttons`
| File | Changes |
|------|---------|
| `api/analyze_routes.py` | +preview_dataset(), +clean_dataset(), +export_dataset() |
| `ui/src/pages/Analytics.tsx` | +previewMutation, +cleanMutation, +deleteMutation, +handleExport, +Preview modal |

---

## 5. Verification Checklist

### Build & Test
- [x] `npm run lint` - ESLint pass (warnings only, no errors)
- [x] `npm run build` - Vite build success in 5.71s
- [x] `python -m compileall -q api/ core/ services/` - No syntax errors
- [x] `pytest tests/ -v` - 62 passed, 25 skipped

### CI/CD
- [x] `.github/workflows/ci.yml` - Triggers on `fix/**` branches
- [x] `.github/workflows/cd.yml` - Deploy on main push + tags

### Manual Acceptance (to verify after merge)
- [ ] /evidence: Quantum UI header/tabs/stats visible
- [ ] /analyze → Datasets: Upload CSV works
- [ ] /analyze → Datasets: Preview modal shows data
- [ ] /analyze → Datasets: Clean button changes status
- [ ] /analyze → Datasets: Export downloads CSV
- [ ] /analyze → Datasets: Delete removes dataset
- [ ] ModuleChatDock: Chat floats at bottom-right

---

## 6. Branch & Release

- **Branch**: `fix/agent-analytics-v3`
- **Base**: `main` (v3.0.0)
- **Commits**: 2
- **PR**: https://github.com/mapleleaflatte03/ERP-AI/pull/new/fix/agent-analytics-v3

### Tag v3.0.0
Already tagged on `main` at commit `cda5f0f`. New features on `fix/agent-analytics-v3` will become v3.0.1 or v3.1.0 after merge.

---

## 7. Nguyên tắc R0: Analytics TÁCH BIỆT chứng từ

| Shared (OK) | Separated (Required) |
|-------------|---------------------|
| Layout/Sidebar | Dataset storage (`datasets` table, not documents) |
| Quantum CSS classes | API routes (`/analyze/*`, not `/documents/*`) |
| Auth/Session | Business logic (no proposal/approval deps) |
| Core API client | ModuleChatDock moduleKey="analyze" |
| Infra (DB, Storage) | No import from `services/ocr*`, `services/extraction*` |

---

*Document updated: 2026-02-04*
