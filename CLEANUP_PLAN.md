# CLEANUP_PLAN.md - ERPX AI Kế Toán

**Version:** v2.0.0  
**Date:** 2026-02-02  
**Branch:** feature/agent-analyze-hub

---

## Section 1: Dirs/Files có thể xoá hoặc chuyển vào `legacy/`

| Path | Lý do | Bằng chứng |
|------|-------|------------|
| `debug_db.py` | Script debug 1 lần, không được import | `grep -r "debug_db" src/ api/` = 0 results |
| `mock_data/` | Generator mock data, không được dùng runtime | `grep -r "mock_data\|generator.py" src/ api/ ui/src/` = 0 results |
| `zyte/` | Scrapy project cho ASOFT, không tích hợp vào hệ thống | `grep -r "zyte\|asoft_zyte" docker-compose.yml src/` = 0 results |
| `data/batch_temp/` | Thư mục temp rỗng (chỉ có .gitkeep) | Không được reference trong code |
| `data/pilot_temp/` | Thư mục temp rỗng (chỉ có .gitkeep) | Không được reference trong code |
| `data/sandbox_temp/` | Thư mục temp rỗng (chỉ có .gitkeep) | Không được reference trong code |
| `data/mock_documents/` | Test fixtures cũ, không được dùng | `grep -r "mock_documents" src/ api/ tests/` = 0 results |

---

## Section 2: Dirs/Files nghi vấn - CẦN REVIEW

| Path | Lý do nghi vấn | Hành động đề xuất |
|------|----------------|-------------------|
| `data_layer/` | Có thể là layer cũ, cần kiểm tra import | Review trước khi move |
| `domain/` | Domain models cũ? | Kiểm tra có được import không |
| `governance/` | Governance rules? | Kiểm tra usage |
| `guardrails/` | AI guardrails? | Kiểm tra usage |
| `orchestrator/` | Có thể được Temporal dùng | Kiểm tra docker-compose + imports |
| `infra/` | Infrastructure scripts | Giữ lại |
| `reports/` | Pre-built reports | Giữ lại (cần cho Analyze module) |

---

## Section 3: Dead Flows / Routes không hoạt động

| Route/Feature | Mô tả | Status |
|---------------|-------|--------|
| `/analyst` (cũ) | Data Analyst page cũ | ✅ Đã merge vào `/analyze` |
| `/reports` (cũ) | Reports page cũ | ✅ Đã merge vào `/analyze` |

**Lưu ý:** Các route cũ có thể vẫn tồn tại trong App.tsx nhưng UI đã redirect hoặc không hiển thị trong menu.

---

## Section 4: Build Artifacts / Cache (An toàn để xoá)

| Path | Loại | Hành động |
|------|------|-----------|
| `ui/dist/` | Vite build output | Giữ (được .gitignore) |
| `ui/node_modules/` | NPM packages | Giữ (được .gitignore) |
| `**/__pycache__/` | Python cache | Giữ (được .gitignore) |
| `.pytest_cache/` | Pytest cache | Giữ (được .gitignore) |

---

## Quy trình thực hiện Cleanup

### Bước 1: Tạo thư mục legacy/
```bash
mkdir -p /root/erp-ai/legacy
```

### Bước 2: Di chuyển các items từ Section 1
```bash
cd /root/erp-ai

# Debug script
mv debug_db.py legacy/

# Mock data generator
mv mock_data/ legacy/

# Zyte scrapy (ASOFT)
mv zyte/ legacy/

# Temp directories trong data/ - chỉ xoá nội dung, giữ .gitkeep
# (Không cần làm gì vì đã rỗng)

# Mock documents
mv data/mock_documents/ legacy/
```

### Bước 3: Test lại sau cleanup
```bash
# Rebuild và test
docker compose up -d --build api ui

# Chờ healthy
docker compose ps

# Test 1 flow cơ bản từ UI
```

### Bước 4: Commit
```bash
git add -A
git commit -m "chore(cleanup): move unused files to legacy/"
```

---

## Những thứ KHÔNG ĐƯỢC XOÁ

| Path | Lý do |
|------|-------|
| `src/` | Core backend code |
| `api/` | API routes |
| `ui/src/` | Frontend code |
| `services/` | Business logic services |
| `migrations/` | Database migrations |
| `configs/` | Configuration files |
| `scripts/` | Deploy/utility scripts |
| `docker-compose.yml` | Orchestration |
| `Dockerfile` | Container build |
| `infrastructure/` | Infra configs |
| `tests/` | Test suites |
| `docs/` | Documentation |
| `.github/` | CI/CD workflows |

---

## Kiểm tra bổ sung cần làm

### Kiểm tra Section 2 items:

```bash
# data_layer/
grep -r "from data_layer\|import data_layer" src/ api/ services/

# domain/
grep -r "from domain\|import domain" src/ api/ services/

# governance/
grep -r "from governance\|import governance" src/ api/ services/

# guardrails/
grep -r "from guardrails\|import guardrails" src/ api/ services/

# orchestrator/
grep -r "from orchestrator\|import orchestrator" src/ api/ services/
```

Nếu tất cả = 0 results → có thể move vào legacy/

---

*Last updated: 2026-02-02*
