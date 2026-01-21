# ERPX AI Accounting - Runtime Baseline

> **Part of PR-0: Baseline Freeze + Golden Tests**  
> Last updated: 2026-01-21

This document captures the current runtime configuration that MUST be preserved during cleanup.

## Container Services

| Container Name | Port(s) | Purpose | Healthcheck |
|----------------|---------|---------|-------------|
| `erpx-postgres` | 5432 | PostgreSQL database | ✅ healthy |
| `erpx-redis` | 6379 | Cache & session store | ✅ healthy |
| `erpx-minio` | 9000, 9001 | Object storage (S3-compatible) | ✅ healthy |
| `erpx-qdrant` | 6333, 6334 | Vector database (embeddings) | ✅ healthy |
| `erpx-temporal` | 7233 | Workflow engine | Running |
| `erpx-temporal-ui` | 8088 | Temporal Web UI | Running |
| `erpx-keycloak` | 8180→8080 | Identity & Access Management | ✅ healthy |
| `erpx-kong` | 8080→8000, 8001, 8443 | API Gateway (JWT auth) | ✅ healthy |
| `erpx-opa` | 8181 | Policy engine (RBAC) | Running |
| `erpx-api` | 8000 | FastAPI backend | ✅ healthy |
| `erpx-worker` | - | Temporal worker | ✅ healthy |
| `erpx-bot` | - | Telegram bot | ✅ healthy |
| `erpx-mlflow` | 5000 | ML experiment tracking | Running |
| `erpx-grafana` | 3001→3000 | Monitoring dashboard | Running |
| `erpx-prometheus` | 9090 | Metrics collection | Running |
| `erpx-jaeger` | 16686, 4317, 4318 | Distributed tracing | Running |

## Database Schema (Golden Tables)

These tables are part of the Golden Flow and **MUST NOT** be modified:

| Table | Purpose | Min Records |
|-------|---------|-------------|
| `extracted_invoices` | OCR/AI extraction results | ≥1 |
| `journal_proposals` | AI-generated journal entries | ≥1 |
| `journal_proposal_entries` | Debit/Credit lines for proposals | ≥2 |
| `approvals` | Approval workflow records | ≥1 |
| `ledger_entries` | Posted ledger entries | ≥1 |
| `ledger_lines` | Debit/Credit lines in ledger | ≥2 |

## Qdrant Collections

| Collection | Dimension | Purpose |
|------------|-----------|---------|
| `accounting_kb` | 1024 | VAS accounting knowledge base |
| `document_chunks` | 1024 | Document text embeddings |

**⚠️ DO NOT change embedding dimension (1024) - uses BGE-M3 model**

## Volume Mounts

| Volume/Path | Container | Purpose |
|-------------|-----------|---------|
| `postgres_data` | erpx-postgres | Database persistence |
| `minio_data` | erpx-minio | Object storage |
| `qdrant_data` | erpx-qdrant | Vector store |
| `temporal_data` | erpx-temporal | Workflow history |
| `./data/uploads` | erpx-api | Upload staging |
| `./data/processed` | erpx-api | Processed documents |
| `./logs` | erpx-api | Application logs |

## External Endpoints

| Service | URL | Auth |
|---------|-----|------|
| Kong Gateway | http://localhost:8080 | JWT required |
| API Direct | http://localhost:8000 | None (internal) |
| Keycloak | http://localhost:8180 | - |
| Temporal UI | http://localhost:8088 | - |
| Grafana | http://localhost:3001 | admin/admin |
| Jaeger | http://localhost:16686 | - |

## Keycloak Configuration

- **Realm**: `erpx`
- **Client**: `admin-cli` (public)
- **Test Users**:
  - admin / admin123
  - accountant / accountant123
  - manager / manager123
  - viewer / viewer123

## Golden Flow

```
Upload Document
    ↓
OCR/Extraction (PaddleOCR + pdfplumber)
    ↓
AI Journal Proposal (DO Agent qwen3-32b)
    ↓
Approval Workflow
    ↓
Ledger Entry (Posted to GL)
```

## Verification Commands

```bash
# 1. Stack health
bash scripts/smoke_up.sh

# 2. Auth enforcement
bash scripts/smoke_auth.sh

# 3. Golden Flow data
bash scripts/smoke_e2e.sh

# 4. Full DB verification
docker exec -i erpx-postgres psql -U erpx -d erpx < scripts/verify_db.sql
```

## Critical Constraints (DO NOT CHANGE)

1. **Service names** in docker-compose must remain as `erpx-*`
2. **Temporal namespace**: `default`
3. **Temporal workflow**: `erpx-document-processing`
4. **Qdrant dimension**: 1024 (BGE-M3)
5. **Kong routes** must enforce JWT auth
6. **Database schema** for golden tables is frozen
