# ERPX E2E Architecture Mapping

## Overview

This document maps the implemented components to the ERPX End-to-End Architecture blocks.

## Architecture Mapping Table

| # | ERPX Block | Status | Evidence Path | Notes |
|---|------------|--------|---------------|-------|
| **AI Gateway & Orchestration** |
| 1 | AI Gateway API (RBAC/Tenant/Quota) | ✅ IMPLEMENTED | `apps/gateway_api/` | FastAPI with X-Tenant-Id, X-API-Key headers |
| 2 | AI Orchestrator (LangGraph StateGraph) | ✅ IMPLEMENTED | `agents/orchestrator/workflow_graph.py` | Existing MVP, integrated via worker |
| 3 | Policy & Guardrails (Threshold/Approval) | ⚡ PARTIAL | `services/approval/approval_service.py` | Basic approve/reject, no auto-threshold |
| **Data Zones** |
| 4 | RAW/Staging Zone | ✅ IMPLEMENTED | `apps/gateway_api/routers/invoices.py` | Upload to `data/uploads/`, DB record |
| 5 | Proposal Zone | ✅ IMPLEMENTED | `domain/models.py::Proposal` | DB table + JSON artifacts |
| 6 | Ledger Zone / ERP Official DB | ✅ IMPLEMENTED | `services/ledger/ledger_writer.py` | `e2e_ledger_entries` table |
| 7 | Audit & Evidence Store | ✅ IMPLEMENTED | `services/audit/audit_logger.py` | `e2e_audit_events` table |
| **Event Bus** |
| 8 | Event Bus / Outbox Pattern | ✅ IMPLEMENTED | `services/outbox/outbox_repo.py` | `e2e_outbox_events` table |
| 9 | Outbox Dispatcher | ✅ IMPLEMENTED | `apps/workers/outbox_dispatcher.py` | Polls and dispatches events |
| **Knowledge & Memory** |
| 10 | Accounting Knowledge Base | ⚡ PARTIAL | `infra/init-scripts/01-init-schema.sql` | Schema exists, needs seeding |
| 11 | Embedding/Rerank (BGE-M3) | ✅ IMPLEMENTED | `services/rag/embedding_service.py` | 1024-dim vectors |
| 12 | Vector DB (Qdrant) | ✅ IMPLEMENTED | `docker-compose.yml` | localhost:6333 |
| 13 | Long-term Memory | ❌ NOT IMPLEMENTED | - | Planned for Phase 3 |
| **Model Serving** |
| 14 | Document AI/OCR (PaddleOCR) | ✅ IMPLEMENTED | `services/ocr/ocr_pipeline.py` | PaddleOCR 2.8.1 |
| 15 | LLM Core (Qwen2.5) | ✅ IMPLEMENTED | `agents/accounting_coding/coding_agent.py` | Qwen2.5-0.5B-Instruct |
| 16 | ML Models (LightGBM/XGBoost/IF) | ❌ NOT IMPLEMENTED | - | Planned for Phase 3 |
| 17 | Time Series (Cashflow Forecast) | ❌ NOT IMPLEMENTED | - | Planned for Phase 3 |
| **Agents** |
| 18 | Invoice Ingestion Agent | ⚡ PARTIAL | `apps/workers/pipeline_worker.py` | OCR only, no full extraction |
| 19 | Accounting Coding Agent | ✅ IMPLEMENTED | `agents/accounting_coding/coding_agent.py` | RAG + LLM suggestions |
| 20 | Payment/Bank Agent | ❌ NOT IMPLEMENTED | - | Planned for Phase 2+ |
| 21 | Reconciliation Agent | ❌ NOT IMPLEMENTED | - | Planned for Phase 2+ |
| 22 | Risk/Anomaly Agent | ❌ NOT IMPLEMENTED | - | Planned for Phase 3 |
| 23 | Finance Copilot Agent | ❌ NOT IMPLEMENTED | - | Planned for Phase 3 |
| 24 | Tax/VAT Agent | ❌ NOT IMPLEMENTED | - | Planned for Phase 2+ |
| 25 | Policy Compliance Agent | ❌ NOT IMPLEMENTED | - | Planned for Phase 2+ |
| 26 | Auto Posting Agent | ❌ NOT IMPLEMENTED | - | Planned for Phase 2+ |
| 27 | Data Quality Agent | ❌ NOT IMPLEMENTED | - | Planned for Phase 3 |
| 28 | Cashflow Forecast Agent | ❌ NOT IMPLEMENTED | - | Planned for Phase 3 |
| 29 | Scenario Simulation Agent | ❌ NOT IMPLEMENTED | - | Planned for Phase 3 |
| 30 | AI CFO/Controller Agent | ❌ NOT IMPLEMENTED | - | Planned for Phase 3 |
| **Approval & UI** |
| 31 | Approval Inbox (Approve Yes/No) | ✅ IMPLEMENTED | `apps/gateway_api/routers/approvals.py` | API endpoint |
| 32 | ERP UI / Workflow | ❌ NOT IMPLEMENTED | - | Out of scope (API only) |
| **Observability** |
| 33 | Structured Logs | ✅ IMPLEMENTED | `apps/gateway_api/main.py` | JSON logging |
| 34 | Metrics Endpoint | ✅ IMPLEMENTED | `apps/gateway_api/routers/health.py` | /health/metrics |
| 35 | Traces (E2E trace_id) | ✅ IMPLEMENTED | All services | X-Trace-Id header |
| **MLOps** |
| 36 | Model & Prompt Registry (MLflow) | ⚡ PARTIAL | `docker-compose.yml` | Service configured, not integrated |
| 37 | Evaluation/Drift/QA | ❌ NOT IMPLEMENTED | - | Planned for Phase 3 |

## Status Summary

| Status | Count | Percentage |
|--------|-------|------------|
| ✅ IMPLEMENTED | 19 | 51% |
| ⚡ PARTIAL | 5 | 14% |
| ❌ NOT IMPLEMENTED | 13 | 35% |

## E2E Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ERPX E2E Flow                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. UPLOAD                    2. PROCESS                                │
│  ┌─────────────┐             ┌─────────────────────────────────────┐    │
│  │ POST /v1/   │   Outbox    │         Pipeline Worker             │    │
│  │ invoices/   │───Event────▶│  OCR ──▶ Embed ──▶ LLM Coding      │    │
│  │ upload      │             │  (PaddleOCR) (BGE-M3)  (Qwen2.5)    │    │
│  └─────────────┘             └──────────────┬──────────────────────┘    │
│        │                                     │                          │
│        ▼                                     ▼                          │
│  ┌─────────────┐             ┌─────────────────────────────────────┐    │
│  │  Invoice    │             │           Proposal                  │    │
│  │  Record     │             │  - suggested_entries                │    │
│  │  (UPLOADED) │             │  - evidence (RAG sources)           │    │
│  └─────────────┘             │  - model_version, confidence        │    │
│                               └──────────────┬──────────────────────┘    │
│                                              │                          │
│  3. APPROVE                                  ▼                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    Approval Inbox                               │    │
│  │  POST /v1/approvals/{id}/approve                                │    │
│  │  { "approved": true, "approved_by": "accountant@..." }          │    │
│  └──────────────────────────────┬──────────────────────────────────┘    │
│                                  │                                      │
│  4. POST TO LEDGER              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    Ledger Writer                                │    │
│  │  - Creates e2e_ledger_entries (DEBIT/CREDIT)                    │    │
│  │  - Generates journal_number (JV-YYYYMMDD-NNNN)                  │    │
│  │  - Updates invoice status to POSTED                             │    │
│  └──────────────────────────────┬──────────────────────────────────┘    │
│                                  │                                      │
│  5. AUDIT TRAIL                 ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    Audit Events                                 │    │
│  │  Every step recorded with:                                      │    │
│  │  - who (actor), what (action), when (timestamp)                 │    │
│  │  - old_state, new_state, evidence                               │    │
│  │  - trace_id (E2E observability)                                 │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Database Tables

### E2E Tables Created

| Table | Zone | Purpose |
|-------|------|---------|
| e2e_invoices | RAW/Staging | Uploaded documents |
| e2e_proposals | Proposal Zone | AI suggestions |
| e2e_ledger_entries | Ledger Zone | Official accounting entries |
| e2e_outbox_events | Event Bus | Outbox pattern events |
| e2e_audit_events | Audit Store | All state transitions |
| e2e_tenant_api_keys | Gateway | RBAC/Quota |

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | /v1/invoices/upload | Upload invoice (RAW/Staging) |
| GET | /v1/invoices/{id} | Get invoice status |
| GET | /v1/invoices | List invoices |
| GET | /v1/proposals/{invoice_id} | Get AI proposal |
| GET | /v1/proposals | List proposals (Approval Inbox) |
| POST | /v1/approvals/{id}/approve | Approve/reject |
| GET | /v1/ledger/entries | List ledger entries |
| GET | /v1/ledger/journal/{num} | Get journal entries |
| GET | /v1/audit/invoice/{id} | Get audit trail |
| GET | /health | Health check |
| GET | /health/metrics | Metrics |

## Phase Roadmap

### Phase 1 (Current - COMPLETED)
- ✅ AI Gateway API with RBAC/Tenant/Quota
- ✅ Event Bus / Outbox pattern
- ✅ Approval Inbox
- ✅ Ledger Zone write
- ✅ Audit & Evidence Store
- ✅ Observability (logs, metrics, traces)
- ✅ Orchestrator integration

### Phase 2 (Next)
- Payment/Bank Agent
- Tax/VAT Agent
- Reconciliation Agent
- Policy Compliance Agent
- Auto Posting Agent
- MLflow integration

### Phase 3 (Future)
- Risk/Anomaly Agent
- Finance Copilot
- AI CFO/Controller
- Cashflow Forecast
- Scenario Simulation
- ML Models (anomaly detection)
- Evaluation/Drift/QA
