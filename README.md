# ERPX AI Accounting System

> **Hệ thống Kế toán AI cho ERP Việt Nam** - Complete AI-powered accounting automation with Vietnamese compliance

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🎯 Overview

ERPX AI Accounting is a complete AI-powered accounting automation system designed for Vietnamese ERP integration. It processes invoices, receipts, bank statements, and expense reports using LLM-powered extraction with strict guardrails to ensure accuracy and compliance.

### Key Features

- **🔒 9 Hard Rules (R1-R9)** - Scope Lock, No Hallucination, Amount/Date Integrity, Doc-Type Truth, Evidence First, Approval Gate, Fixed Schema, Reproducible, Security
- **🔄 LangGraph Workflow** - A(Ingest) → B(Classify) → C(Extract) → D(Validate) → E(Reconcile) → F(Decision)
- **📊 Vietnamese Accounting Compliance** - VAT rates (0%, 5%, 8%, 10%), Vietnamese number formats, Circular 78 compliance
- **🏦 Bank Reconciliation** - Automatic matching with configurable tolerances
- **✅ Approval Workflow** - Configurable thresholds with escalation paths
- **📝 Full Audit Trail** - Evidence storage, audit logs, and compliance exports

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ERPX AI Accounting                          │
├─────────────────────────────────────────────────────────────────────┤
│  API Layer (FastAPI)                                                │
│  ├── /v1/accounting/coding     - Document processing                │
│  ├── /v1/accounting/reconcile  - Bank reconciliation               │
│  ├── /v1/accounting/batch      - Batch processing                  │
│  └── /health                   - Health check                      │
├─────────────────────────────────────────────────────────────────────┤
│  Orchestrator (LangGraph)                                           │
│  ├── Step A: Ingest     - Document intake & validation             │
│  ├── Step B: Classify   - Document type detection                  │
│  ├── Step C: Extract    - LLM-powered field extraction             │
│  ├── Step D: Validate   - Guardrails & integrity checks            │
│  ├── Step E: Reconcile  - Bank matching                            │
│  └── Step F: Decision   - Approval routing                         │
├─────────────────────────────────────────────────────────────────────┤
│  Guardrails                                                         │
│  ├── Input Validator    - R1 Scope Lock, injection prevention      │
│  ├── Output Validator   - R2 No Hallucination, R3 Integrity        │
│  └── Policy Checker     - R6 Approval Gate, VAT compliance         │
├─────────────────────────────────────────────────────────────────────┤
│  Data Layer                                                         │
│  ├── PostgreSQL         - Transactions, audit logs, approvals      │
│  ├── Qdrant             - RAG for VN accounting laws & SOPs        │
│  └── MinIO              - Document storage (raw/processed/archive) │
├─────────────────────────────────────────────────────────────────────┤
│  Governance                                                         │
│  ├── Audit Store        - Who • What • When • Why                  │
│  ├── Evidence Store     - R5 Evidence First                        │
│  └── Approval Inbox     - R6 Approval Gate workflow                │
└─────────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Docker & Docker Compose (for full stack)
- LLM API Key (OpenAI, Azure OpenAI, or compatible)

### 1. Clone and Setup

```bash
# Clone repository
cd /root/erp-ai

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your LLM API key
```

### 2. Start with Docker Compose (Recommended)

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f api
```

Services will be available at:
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **MinIO Console**: http://localhost:9001
- **MLflow**: http://localhost:5000
- **Jaeger (Tracing)**: http://localhost:16686
- **Qdrant Dashboard**: http://localhost:6333/dashboard

### 3. Run with Mock Data (Local Development)

```bash
# Activate virtual environment
source venv/bin/activate

# Generate mock data
python -c "from mock_data.generator import generate_benchmark_dataset; generate_benchmark_dataset('data/mock_documents', 50)"

# Run API server
uvicorn api.main:create_app --factory --reload --host 0.0.0.0 --port 8000

# Run demo script
python scripts/demo_e2e.py
```

## 📖 API Usage

### Process a Document

```bash
curl -X POST "http://localhost:8000/v1/accounting/coding" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: demo-tenant-001" \
  -d '{
    "doc_id": "INV-001",
    "content": "HÓA ĐƠN GTGT\nSố: HD001\nNgày: 15/01/2024\nTổng tiền: 1,100,000 VND\nVAT 10%: 100,000 VND",
    "doc_type": "invoice",
    "mode": "STRICT"
  }'
```

### Bank Reconciliation

```bash
curl -X POST "http://localhost:8000/v1/accounting/reconcile" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: demo-tenant-001" \
  -d '{
    "period_start": "2024-01-01",
    "period_end": "2024-01-31",
    "bank_account": "1020123456789"
  }'
```

### Batch Processing

```bash
curl -X POST "http://localhost:8000/v1/accounting/batch" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: demo-tenant-001" \
  -d '{
    "documents": [
      {"doc_id": "INV-001", "content": "...", "doc_type": "invoice"},
      {"doc_id": "REC-001", "content": "...", "doc_type": "receipt"}
    ]
  }'
```

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/unit/test_core.py -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

## 📁 Project Structure

```
erp-ai/
├── api/                    # FastAPI application
│   ├── main.py            # App factory
│   ├── routes.py          # API endpoints
│   └── middleware.py      # Custom middleware
├── core/                   # Core modules
│   ├── schemas.py         # Pydantic models (Fixed Output Schema)
│   ├── constants.py       # System constants
│   └── exceptions.py      # Custom exceptions
├── orchestrator/           # LangGraph workflow
│   ├── workflow.py        # Main workflow class
│   └── states.py          # State definitions
├── data_layer/            # Data access
│   ├── postgres_mock.py   # PostgreSQL mock
│   ├── qdrant_mock.py     # Qdrant mock (RAG)
│   └── minio_mock.py      # MinIO mock
├── guardrails/            # Validation & policy
│   ├── input_validator.py
│   ├── output_validator.py
│   └── policy_checker.py
├── governance/            # Audit & approval
│   ├── audit_store.py
│   ├── evidence_store.py
│   └── approval_inbox.py
├── observability/         # Logging & tracing
│   ├── logging_config.py
│   ├── otel_hooks.py
│   └── mlflow_tracking.py
├── mock_data/             # Test data generation
│   └── generator.py
├── tests/                 # Unit & integration tests
│   └── unit/
├── scripts/               # Utility scripts
│   ├── init_db.sql
│   └── demo_e2e.py
├── docker-compose.yml     # Docker services
├── Dockerfile             # API container
├── requirements.txt       # Python dependencies
└── .env.example          # Environment template
```

## ⚙️ Configuration

### Processing Modes

| Mode | Behavior |
|------|----------|
| `STRICT` | All rules enforced, VAT invoice required for amounts > 20M VND |
| `RELAXED` | Warnings only, allows processing with missing data |

### Approval Thresholds

| Amount (VND) | Approval |
|--------------|----------|
| < 10,000,000 | Auto-approve |
| 10M - 100M | Accountant |
| > 100,000,000 | Chief Accountant |

### VAT Rates (Vietnam)

- 0% - Export, specific services
- 5% - Essential goods
- 8% - Reduced rate (2024)
- 10% - Standard rate

## 🔐 Security

- Tenant isolation via `X-Tenant-ID` header
- Rate limiting per tenant
- Input sanitization (SQL/prompt injection prevention)
- Audit logging for all operations
- JWT authentication (configurable)

## 📊 Observability

- **Structured Logging**: JSON format with correlation IDs
- **OpenTelemetry**: Distributed tracing via Jaeger
- **MLflow**: Experiment tracking and model versioning
- **Health Checks**: `/health` endpoint for monitoring

## 🔄 Hard Rules (R1-R9)

| Rule | Description |
|------|-------------|
| R1 | **Scope Lock** - Only accounting tasks, reject others |
| R2 | **No Hallucination** - All data must come from source |
| R3 | **Amount/Date Integrity** - Exact preservation |
| R4 | **Doc-Type Truth** - Classification is immutable |
| R5 | **Evidence First** - Every field has source reference |
| R6 | **Approval Gate** - Human review for thresholds |
| R7 | **Fixed Output Schema** - Consistent JSON structure |
| R8 | **Reproducible** - Same input = same output |
| R9 | **Security/Access** - Tenant isolation |

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request

## 📝 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- Vietnamese accounting standards (Circular 78/200)
- LangGraph for workflow orchestration
- FastAPI for high-performance API
- Qdrant for vector search
