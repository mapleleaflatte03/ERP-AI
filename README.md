# ERPX AI Kế Toán

**Version:** 2.0.0  
**Platform:** AI-powered Accounting for Vietnamese ERP

---

## Overview

ERPX AI Kế Toán là hệ thống kế toán tự động tích hợp AI, được thiết kế cho doanh nghiệp Việt Nam. Hệ thống tự động hóa quy trình từ đọc chứng từ (OCR), trích xuất thông tin, đề xuất hạch toán, đến phê duyệt - tất cả được hỗ trợ bởi AI Copilot thông minh.

---

## Core Features

- **Upload → OCR → Extract → Propose → Approve**: Quy trình tự động từ scan chứng từ đến hạch toán
- **AI Copilot + Agent Hub**: Trợ lý AI chat, hỗ trợ tìm kiếm, phân tích, và thực hiện tác vụ với xác nhận từ user
- **Analyze Module**:
  - Tab "Báo cáo": Pre-built reports (vendor summary, monthly summary...)
  - Tab "Data Analyze": Upload dataset + Natural Language Query (NL2SQL)
- **Document Preview với OCR Overlay**: Xem chứng từ với bounding boxes + bảng thông tin trích xuất
- **Multi-level Approval**: Quy trình duyệt đề xuất theo cấp độ
- **Audit Trail**: Lịch sử thao tác đầy đủ với bằng chứng

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend                             │
│  React + TypeScript + TailwindCSS + TanStack Query          │
│  Port: 3002 (prod) / 3000 (dev)                             │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                     Kong API Gateway                         │
│                       Port: 8080                             │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                           │
│  /v1/documents, /v1/proposals, /v1/approvals                │
│  /v1/copilot, /v1/agent/actions, /v1/analyze                │
│                       Port: 8000                             │
└────────────────────────────┬────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌───────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   PostgreSQL  │  │     MinIO       │  │   Temporal      │
│   + pgvector  │  │   (S3 storage)  │  │   (Workflows)   │
│   Port: 5432  │  │   Port: 9000    │  │   Port: 7233    │
└───────────────┘  └─────────────────┘  └─────────────────┘
```

**Services:**
- **PostgreSQL** + pgvector: Database + vector search
- **MinIO**: Document storage (S3-compatible)
- **Temporal**: Workflow orchestration
- **Redis**: Caching + queue
- **Keycloak**: Authentication (Port 8180)
- **Qdrant**: Vector database cho RAG

---

## Getting Started

### Prerequisites

- Docker + Docker Compose v2
- Node.js >= 18 (for frontend dev)
- Python >= 3.10 (for local backend dev)

### Quick Start (Docker)

```bash
# Clone repo
git clone <repo-url>
cd erp-ai

# Copy environment
cp .env.example .env
# Edit .env với credentials cần thiết

# Start all services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f api ui
```

### Access URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| **UI** | http://localhost:3002 | admin / admin123 |
| **API Docs** | http://localhost:8080/api/docs | - |
| **Keycloak** | http://localhost:8180 | admin / admin |
| **Temporal UI** | http://localhost:8088 | - |
| **Grafana** | http://localhost:3001 | admin / admin |
| **MinIO** | http://localhost:9001 | minioadmin / minioadmin |

### Frontend Development

```bash
cd ui
npm install    # First time only
npm run dev    # Start dev server at :3000
```

### Backend Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run with auto-reload
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Main Routes

| Route | Tên | Mô tả |
|-------|-----|-------|
| `/` | Chứng từ | Danh sách documents, upload, preview |
| `/proposals` | Đề xuất hạch toán | Danh sách journal proposals |
| `/approvals` | Duyệt | Danh sách chờ phê duyệt |
| `/copilot` | Trợ lý AI | Chat với AI Copilot |
| `/analyze` | Phân tích | Reports + Data Analyze (NL2SQL) |
| `/evidence` | Bằng chứng | Lịch sử audit trail |
| `/reconciliation` | Đối soát | Bank reconciliation |

---

## API Endpoints

### Documents
- `GET /v1/documents` - List documents
- `POST /v1/documents/upload` - Upload document
- `GET /v1/documents/{id}` - Get document detail
- `GET /v1/documents/{id}/ocr-boxes` - Get OCR bounding boxes
- `GET /v1/documents/{id}/raw-vs-cleaned` - Get extracted fields

### Proposals & Approvals
- `GET /v1/proposals` - List proposals
- `POST /v1/proposals/{id}/submit` - Submit for approval
- `GET /v1/approvals/pending` - Pending approvals
- `POST /v1/approvals/{id}/approve` - Approve
- `POST /v1/approvals/{id}/reject` - Reject

### Copilot & Agent
- `POST /v1/copilot/chat` - Chat with AI
- `GET /v1/agent/actions/pending` - Pending action proposals
- `POST /v1/agent/actions/{id}/confirm` - Confirm action
- `POST /v1/agent/actions/{id}/cancel` - Cancel action

### Analyze
- `GET /v1/analyze/reports` - List available reports
- `POST /v1/analyze/reports/{id}/run` - Run report
- `GET /v1/analyze/datasets` - List datasets
- `POST /v1/analyze/datasets/upload` - Upload dataset
- `POST /v1/analyze/query` - NL2SQL query

---

## Testing

### Smoke Test

Xem file [TEST_SMOKE_FLOWS.md](TEST_SMOKE_FLOWS.md) để chạy smoke test end-to-end:

1. **Flow 1**: Upload → OCR → Journal Proposal → Approve
2. **Flow 2**: Copilot đọc chứng từ
3. **Flow 3**: Analyze (Reports + Dataset)
4. **Flow 4**: Document Preview OCR Overlay
5. **Flow 5**: Agent Action Hub

### Run Tests

```bash
# Backend unit tests
pytest tests/

# Frontend tests
cd ui && npm test

# E2E tests (Playwright)
cd ui && npm run test:e2e
```

---

## Cleanup & Legacy

Xem [CLEANUP_PLAN.md](CLEANUP_PLAN.md) cho:
- Danh sách files/directories đã chuyển vào `legacy/`
- Danh sách routes/features không còn sử dụng
- Quy trình cleanup an toàn

---

## Release Notes

### v2.0.0 (2026-02-02)

**New Features:**
- ✨ Agent Action Hub - UI confirm/cancel cho Copilot actions
- ✨ Analyze Module - Merge Reports + Data Analyst với NL2SQL
- ✨ OCR Preview Overlay - Bounding boxes + extracted fields panel
- ✨ Document raw vs cleaned comparison

**Improvements:**
- 📦 Cleanup repo - move unused files to `legacy/`
- 📝 Updated documentation (README, TEST_SMOKE_FLOWS, CLEANUP_PLAN)

**Technical:**
- Frontend: React + TypeScript + TailwindCSS + TanStack Query
- Backend: FastAPI + PostgreSQL + Temporal workflows
- AI: DigitalOcean Agent (Qwen3-32B)

---

## Project Structure

```
erp-ai/
├── api/                    # API route handlers
├── src/                    # Backend source code
│   ├── api/               # FastAPI app
│   ├── copilot/           # AI Copilot logic
│   ├── workflows/         # Temporal workflows
│   └── ...
├── services/              # Business logic services
│   ├── ocr/              # OCR & extraction
│   ├── approval/         # Approval workflow
│   ├── ledger/           # Journal entries
│   └── ...
├── ui/                    # React frontend
│   └── src/
│       ├── components/   # Reusable components
│       ├── pages/        # Route pages
│       └── lib/          # Utilities, API client
├── migrations/            # Database migrations
├── configs/               # Configuration files
├── infrastructure/        # Docker, K8s configs
├── tests/                 # Test suites
├── docs/                  # Documentation
├── legacy/                # Deprecated files (cleanup)
├── docker-compose.yml     # Service orchestration
├── Dockerfile             # Backend container
└── Makefile              # Common commands
```

---

## Contributing

1. Create feature branch: `git checkout -b feature/xxx`
2. Make changes and test
3. Run smoke tests (see TEST_SMOKE_FLOWS.md)
4. Create PR with clear description
5. Wait for review and CI checks

---

## License

Proprietary - Internal use only.

---

*Last updated: 2026-02-02 | Version 2.0.0*
