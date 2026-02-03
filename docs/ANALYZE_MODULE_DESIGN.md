# ERP-AI Analyze Module v2 - Architecture Design

## 🎯 Vision
Build an AI-powered Financial Analysis Assistant that integrates with open-source data engineering and BI tools.

---

## 📐 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ANALYZE MODULE v2                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐ │
│  │   AI Assistant  │    │  Analysis Engine │    │   BI Platform   │ │
│  │  (Chat + Tools) │────│  (dbt + Prophet) │────│   (Metabase)    │ │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘ │
│           │                      │                      │          │
│           ▼                      ▼                      ▼          │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                    UNIFIED DATA LAYER                           ││
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌────────────┐ ││
│  │  │ PostgreSQL  │ │   Datasets  │ │  dbt Models │ │  Metrics   │ ││
│  │  │ (invoices,  │ │ (uploaded   │ │ (mart_*,    │ │ (KPIs,     │ ││
│  │  │ journal,..) │ │ CSV/Excel)  │ │ stg_*, ..)  │ │ forecasts) │ ││
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └────────────┘ ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                    DATA QUALITY LAYER                           ││
│  │  ┌─────────────────────────────────────────────────────────────┐││
│  │  │         Great Expectations (Data Validation)                │││
│  │  └─────────────────────────────────────────────────────────────┘││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🧩 Module Structure

```
src/
├── analytics/                    # New analytics module
│   ├── __init__.py
│   │
│   ├── core/                     # Core components
│   │   ├── __init__.py
│   │   ├── config.py             # Analytics config
│   │   ├── registry.py           # Tool/connector registry
│   │   └── exceptions.py         # Custom exceptions
│   │
│   ├── connectors/               # Data source connectors
│   │   ├── __init__.py
│   │   ├── base.py               # Base connector interface
│   │   ├── postgres.py           # PostgreSQL connector
│   │   ├── dataset.py            # Dataset (CSV/Excel) connector
│   │   └── external.py           # External API connectors (future)
│   │
│   ├── engine/                   # Analysis engine
│   │   ├── __init__.py
│   │   ├── nl2sql.py             # Natural Language to SQL
│   │   ├── dbt_runner.py         # dbt model execution
│   │   ├── forecaster.py         # Prophet/sklearn forecasting
│   │   └── aggregator.py         # Metric aggregations
│   │
│   ├── assistant/                # AI Assistant
│   │   ├── __init__.py
│   │   ├── agent.py              # Main agent orchestrator
│   │   ├── tools.py              # Available tools
│   │   ├── prompts.py            # System prompts
│   │   └── memory.py             # Conversation memory
│   │
│   ├── quality/                  # Data quality (Great Expectations)
│   │   ├── __init__.py
│   │   ├── validator.py          # Data validation
│   │   └── expectations.py       # Pre-defined expectations
│   │
│   ├── reports/                  # Report generation
│   │   ├── __init__.py
│   │   ├── templates.py          # Report templates
│   │   └── generator.py          # Report generator
│   │
│   └── bi/                       # BI integration
│       ├── __init__.py
│       ├── metabase.py           # Metabase API client
│       └── dashboards.py         # Dashboard management
│
├── api/
│   └── analytics_routes.py       # New unified analytics API
│
└── dbt/                          # dbt project
    ├── dbt_project.yml
    ├── profiles.yml
    ├── models/
    │   ├── staging/              # Raw data cleaning
    │   │   ├── stg_invoices.sql
    │   │   ├── stg_journal_entries.sql
    │   │   └── stg_vendors.sql
    │   ├── intermediate/         # Business logic
    │   │   ├── int_monthly_summary.sql
    │   │   └── int_vendor_metrics.sql
    │   └── marts/                # Final reporting models
    │       ├── mart_balance_sheet.sql
    │       ├── mart_pnl.sql
    │       └── mart_cashflow.sql
    └── tests/                    # dbt tests
```

---

## 🔌 API Endpoints

### Assistant (Chat Interface)
```
POST /v1/analytics/chat
  Request:  { "message": "string", "session_id": "optional" }
  Response: { "response": "string", "tool_calls": [...], "visualizations": [...] }

GET  /v1/analytics/sessions
GET  /v1/analytics/sessions/{id}/history
```

### Data & Queries
```
POST /v1/analytics/query          # Execute SQL/NL query
GET  /v1/analytics/schema         # Get available tables/columns
POST /v1/analytics/datasets       # Upload dataset
GET  /v1/analytics/datasets
DELETE /v1/analytics/datasets/{id}
```

### Analysis
```
POST /v1/analytics/forecast       # Run forecasting
  { "metric": "revenue", "periods": 30, "model": "prophet" }

POST /v1/analytics/aggregate      # Run aggregations
  { "metrics": ["sum", "avg"], "group_by": [...], "filters": [...] }

GET  /v1/analytics/kpis           # Get KPI dashboard data
```

### Reports
```
GET  /v1/analytics/reports                    # List templates
POST /v1/analytics/reports/{template}/run     # Run report
POST /v1/analytics/reports/custom             # Custom report
GET  /v1/analytics/reports/exports/{id}       # Download export
```

### dbt
```
POST /v1/analytics/dbt/run        # Run dbt models
GET  /v1/analytics/dbt/models     # List available models
GET  /v1/analytics/dbt/docs       # Get model documentation
```

### BI Integration
```
GET  /v1/analytics/bi/dashboards  # List Metabase dashboards
POST /v1/analytics/bi/embed/{id}  # Get embed URL for dashboard
```

---

## 🤖 AI Assistant Tools

The assistant has access to these tools:

| Tool | Description |
|------|-------------|
| `query_data` | Execute SQL or natural language queries |
| `run_forecast` | Generate forecasts (30/60/90 days) |
| `get_kpis` | Retrieve KPI metrics |
| `list_tables` | Show available data tables |
| `describe_table` | Get table schema and sample data |
| `create_chart` | Generate visualization configs |
| `run_report` | Execute pre-built reports |
| `calculate_metric` | Compute custom metrics |
| `validate_data` | Run data quality checks |
| `export_data` | Export results to CSV/Excel |

---

## 📊 dbt Models

### Staging Layer (stg_*)
- `stg_invoices` - Cleaned invoice data
- `stg_journal_entries` - Cleaned journal entries
- `stg_accounts` - Chart of accounts
- `stg_vendors` - Vendor master data

### Intermediate Layer (int_*)
- `int_monthly_totals` - Monthly aggregations
- `int_vendor_metrics` - Vendor-level metrics
- `int_account_balances` - Account balance calculations

### Marts Layer (mart_*)
- `mart_balance_sheet` - Balance sheet report
- `mart_pnl` - Profit & Loss statement
- `mart_cashflow` - Cash flow statement
- `mart_aged_receivables` - AR aging
- `mart_aged_payables` - AP aging

---

## 📈 Forecasting Models

Using Prophet and scikit-learn:

```python
# Revenue forecast
POST /v1/analytics/forecast
{
  "target": "revenue",
  "horizon": 90,      # days
  "granularity": "daily",
  "include_components": true  # trend, seasonality
}

# Cash flow forecast  
POST /v1/analytics/forecast
{
  "target": "cash_balance",
  "horizon": 30,
  "model": "prophet",
  "regressors": ["ar_amount", "ap_amount"]  # optional external regressors
}
```

---

## 🔒 Data Quality (Great Expectations)

Pre-defined expectations:
- `expect_invoices_positive_amounts` - Invoice amounts > 0
- `expect_valid_tax_rates` - Tax rates 0-50%
- `expect_balanced_entries` - Debit = Credit in journals
- `expect_no_future_dates` - No future invoice dates

---

## 🖥️ UI Components

### New Analyze Page Tabs

1. **Chat** (AI Assistant)
   - Chat interface with AI
   - Tool execution visualization
   - Chart/table rendering

2. **Explorer**
   - Schema browser
   - SQL editor with autocomplete
   - Results table

3. **Dashboards**
   - Embedded Metabase dashboards
   - KPI cards
   - Custom charts

4. **Reports**
   - Pre-built financial reports
   - Export options (PDF, Excel)

5. **Forecasts**
   - Forecast configuration
   - Visualization with confidence intervals

6. **Datasets**
   - Upload/manage datasets
   - Preview data
   - Data profiling

---

## 🚀 Implementation Plan

### Phase 1: Core Infrastructure (Week 1)
- [ ] Create module structure
- [ ] Implement connectors (postgres, dataset)
- [ ] Build NL2SQL engine
- [ ] Create basic API endpoints

### Phase 2: AI Assistant (Week 2)
- [ ] Build tool definitions
- [ ] Implement agent orchestrator
- [ ] Add conversation memory
- [ ] Build chat UI

### Phase 3: Analysis Engine (Week 3)
- [ ] Setup dbt project
- [ ] Create staging/mart models
- [ ] Implement forecasting (Prophet)
- [ ] Add data quality (Great Expectations)

### Phase 4: BI & Polish (Week 4)
- [ ] Integrate Metabase
- [ ] Build dashboards
- [ ] Enhance UI
- [ ] Testing & documentation

---

## 📦 Dependencies

```python
# requirements.txt additions
dbt-postgres>=1.7.0
prophet>=1.1.0
scikit-learn>=1.3.0
great-expectations>=0.18.0
pandas>=2.0.0
sqlalchemy>=2.0.0
```

```yaml
# docker-compose additions
metabase:
  image: metabase/metabase:latest
  ports:
    - "3003:3000"
  environment:
    - MB_DB_TYPE=postgres
    - MB_DB_DBNAME=metabase
    - MB_DB_PORT=5432
    - MB_DB_USER=${POSTGRES_USER}
    - MB_DB_PASS=${POSTGRES_PASSWORD}
    - MB_DB_HOST=postgres
```

---

## 🔗 Integration Points

### With Documents Module
- Extract data from invoices → analytics pipeline
- Validate extracted data quality

### With Proposals Module  
- Journal entry aggregations
- Account balance tracking

### With Approvals Module
- Workflow metrics
- Approval time analysis

---

*Document created: 2026-02-03*
*Version: 2.0.0*
