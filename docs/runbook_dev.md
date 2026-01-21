# ERPX E2E Development Runbook

## Overview

This runbook provides step-by-step instructions to run the ERPX E2E system in development mode.

## Prerequisites

- Python 3.10+
- Docker & Docker Compose
- PostgreSQL client (psql, pg_isready)
- curl for testing

## Quick Start

### 1. Start Infrastructure

```bash
cd /root/erp-ai/infra

# Start all infrastructure services
docker compose up -d postgres qdrant

# Wait for services to be healthy
docker compose ps

# Verify PostgreSQL
docker compose exec postgres pg_isready -U erp_user -d erp_ai

# Verify Qdrant
curl http://localhost:6333/collections
```

### 2. Initialize E2E Schema

```bash
# Apply E2E schema (if not auto-applied)
docker compose exec postgres psql -U erp_user -d erp_ai -f /docker-entrypoint-initdb.d/02-e2e-schema.sql
```

### 3. Start Gateway API (Terminal 1)

```bash
cd /root/erp-ai

# Activate virtual environment
source venv/bin/activate

# Install E2E dependencies
pip install -r requirements-e2e.txt

# Start API
bash scripts/run_e2e_api.sh
```

API will be available at:
- **Docs**: http://localhost:8000/docs
- **Health**: http://localhost:8000/health

### 4. Start Workers (Terminal 2)

```bash
cd /root/erp-ai
source venv/bin/activate

# Start both workers
bash scripts/run_e2e_workers.sh
```

### 5. Test E2E Flow

See [Demo Commands](#demo-commands) section below.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     ERPX E2E Architecture                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐     ┌───────────────┐     ┌────────────────┐  │
│  │ Gateway API  │────▶│ Outbox Events │────▶│ Pipeline Worker│  │
│  │ (FastAPI)    │     │   (Postgres)  │     │ (OCR/Embed/LLM)│  │
│  └──────┬───────┘     └───────────────┘     └───────┬────────┘  │
│         │                                           │           │
│         ▼                                           ▼           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    PostgreSQL (ERP DB)                    │   │
│  │  ┌─────────────┬─────────────┬───────────┬────────────┐  │   │
│  │  │  Invoices   │  Proposals  │  Ledger   │   Audit    │  │   │
│  │  │ (RAW Zone)  │(Proposal Z) │(Ledger Z) │ (Evidence) │  │   │
│  │  └─────────────┴─────────────┴───────────┴────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────┐     ┌───────────────┐                         │
│  │    Qdrant    │     │    MinIO      │                         │
│  │ (Vector DB)  │     │ (Object Store)│                         │
│  └──────────────┘     └───────────────┘                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Demo Commands

### Authentication Headers

All API calls require:
```
X-Tenant-Id: demo-tenant
X-API-Key: erp-demo-key-2024
```

### 1. Upload Invoice

```bash
# Upload a sample invoice
curl -X POST "http://localhost:8000/v1/invoices/upload" \
  -H "X-Tenant-Id: demo-tenant" \
  -H "X-API-Key: erp-demo-key-2024" \
  -F "file=@/root/erp-ai/data/raw/sample_invoice.png"

# Response:
# {
#   "invoice_id": "uuid...",
#   "status": "UPLOADED",
#   "trace_id": "uuid...",
#   "message": "Invoice uploaded successfully..."
# }
```

### 2. Check Invoice Status

```bash
# Replace {invoice_id} with actual ID from upload response
curl "http://localhost:8000/v1/invoices/{invoice_id}" \
  -H "X-Tenant-Id: demo-tenant" \
  -H "X-API-Key: erp-demo-key-2024"

# Expected status progression:
# UPLOADED → PROCESSING → PROPOSED
```

### 3. Get Proposal

```bash
curl "http://localhost:8000/v1/proposals/{invoice_id}" \
  -H "X-Tenant-Id: demo-tenant" \
  -H "X-API-Key: erp-demo-key-2024"

# Response includes suggested_entries and evidence
```

### 4. Approve Proposal

```bash
curl -X POST "http://localhost:8000/v1/approvals/{invoice_id}/approve" \
  -H "X-Tenant-Id: demo-tenant" \
  -H "X-API-Key: erp-demo-key-2024" \
  -H "Content-Type: application/json" \
  -d '{
    "approved": true,
    "approved_by": "accountant@company.com"
  }'

# Response includes ledger_entries_created count
```

### 5. Check Ledger Entries

```bash
curl "http://localhost:8000/v1/ledger/entries" \
  -H "X-Tenant-Id: demo-tenant" \
  -H "X-API-Key: erp-demo-key-2024"
```

### 6. View Audit Trail

```bash
curl "http://localhost:8000/v1/audit/invoice/{invoice_id}" \
  -H "X-Tenant-Id: demo-tenant" \
  -H "X-API-Key: erp-demo-key-2024"
```

### 7. Health Check

```bash
curl http://localhost:8000/health
```

---

## Troubleshooting

### PostgreSQL Connection Issues

```bash
# Check if PostgreSQL is running
docker compose -f infra/docker-compose.yml ps postgres

# Check logs
docker compose -f infra/docker-compose.yml logs postgres

# Restart
docker compose -f infra/docker-compose.yml restart postgres
```

### Qdrant Connection Issues

```bash
# Check if Qdrant is running
curl http://localhost:6333/collections

# Check logs
docker compose -f infra/docker-compose.yml logs qdrant
```

### Worker Not Processing

```bash
# Check worker logs
tail -f logs/pipeline_worker.log

# Check outbox events
docker compose exec postgres psql -U erp_user -d erp_ai -c \
  "SELECT * FROM e2e_outbox_events ORDER BY created_at DESC LIMIT 10;"
```

### API Errors

```bash
# Check API logs
tail -f logs/gateway_api.log

# Check audit events for errors
docker compose exec postgres psql -U erp_user -d erp_ai -c \
  "SELECT * FROM e2e_audit_events WHERE action = 'ERROR' ORDER BY created_at DESC LIMIT 10;"
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| POSTGRES_HOST | localhost | PostgreSQL host |
| POSTGRES_PORT | 5432 | PostgreSQL port |
| POSTGRES_USER | erp_user | PostgreSQL user |
| POSTGRES_PASSWORD | *** | PostgreSQL password |
| POSTGRES_DB | erp_ai | PostgreSQL database |
| QDRANT_HOST | localhost | Qdrant host |
| QDRANT_PORT | 6333 | Qdrant port |
| API_HOST | 0.0.0.0 | API bind host |
| API_PORT | 8000 | API port |
| WORKER_POLL_INTERVAL | 5 | Worker poll interval (seconds) |
| DISPATCHER_POLL_INTERVAL | 2 | Dispatcher poll interval (seconds) |

---

## Stopping Services

```bash
# Stop API (Ctrl+C in terminal)

# Stop workers
pkill -f "pipeline_worker"
pkill -f "outbox_dispatcher"

# Stop infrastructure
cd infra && docker compose down
```
