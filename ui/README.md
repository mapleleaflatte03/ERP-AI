# ERPX Agent Console UI

Modern React dashboard for testing and monitoring the ERPX AI Agent system.

## Features

- **Dashboard** - System health, counters, and quick links to external tools
- **Jobs** - Upload documents and track processing through the pipeline
- **Approvals** - Review and approve/reject pending invoice proposals
- **Forecasts** - Generate and visualize cashflow forecasts (PR20)
- **Simulations** - Run what-if scenarios with adjustable parameters (PR20)
- **Insights** - AI-powered CFO insights and recommendations (PR21)
- **Evidence** - Verify tool integrations (Postgres, MinIO, Qdrant, Temporal, Jaeger, MLflow)

## Tech Stack

- **Vite** - Fast build tool and dev server
- **React 19** - UI framework with hooks
- **TypeScript** - Type safety
- **Tailwind CSS v4** - Utility-first styling
- **React Router** - Client-side routing
- **React Query** - Data fetching and caching
- **Recharts** - Charts and visualizations
- **Lucide React** - Beautiful icons
- **Axios** - HTTP client

## Development

```bash
# Install dependencies
cd ui
npm install

# Start dev server (http://localhost:3000)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Docker

The UI is included in the main docker-compose stack:

```bash
# Build and run with the stack
docker compose up -d ui

# Or run standalone
docker build -t erpx-ui ./ui
docker run -p 3000:80 erpx-ui
```

## Environment Variables

Create `.env` for custom configuration:

```env
# API base URL (default: /api proxied to backend)
VITE_API_BASE_URL=/api

# Keycloak URL for authentication
VITE_KEYCLOAK_URL=http://localhost:8180
```

## API Proxy

In development, Vite proxies `/api/*` to `http://localhost:8080/*`.

In production (Docker), nginx proxies `/api/*` to `http://api:8080/*`.

## Pages

### Dashboard
- Health status indicator
- Database counters (documents, invoices, proposals, etc.)
- Quick links to Temporal, Jaeger, MinIO, Qdrant, MLflow, Keycloak

### Jobs
- Drag-and-drop file upload (PDF, PNG, XLSX)
- Real-time job status with auto-polling
- Full pipeline visibility: document → invoice → proposal → approval → ledger

### Approvals
- List of pending approvals
- One-click approve/reject
- Audit trail with user IDs

### Forecasts
- Configure window (7-90 days)
- Trigger async forecast generation
- Line chart: daily net cashflow + cumulative
- Summary: inflow, outflow, net position

### Simulations
- Input parameters: revenue multiplier, cost multiplier, payment delay
- Bar chart: baseline vs projected comparison
- Delta analysis with percent change

### Insights
- Generate AI-powered CFO insights
- Polling status for async processing
- Top findings with severity indicators
- Actionable recommendations with priorities
- Source references

### Evidence
- Real-time tool health verification
- Postgres: table row counts
- MinIO: sample object keys
- Qdrant: vector point count
- Temporal: completed workflow count
- Jaeger: traced services list
- MLflow: experiment run count

## Architecture

```
ui/
├── src/
│   ├── components/
│   │   ├── Layout.tsx      # Main layout with sidebar
│   │   └── LoginModal.tsx  # Keycloak auth
│   ├── lib/
│   │   └── api.ts          # API client
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── Jobs.tsx
│   │   ├── Approvals.tsx
│   │   ├── Forecasts.tsx
│   │   ├── Simulations.tsx
│   │   ├── Insights.tsx
│   │   └── Evidence.tsx
│   ├── types/
│   │   └── index.ts        # TypeScript interfaces
│   ├── App.tsx             # Router setup
│   ├── main.tsx            # Entry point
│   └── index.css           # Tailwind imports
├── Dockerfile              # Multi-stage build
├── nginx.conf              # Production config
├── vite.config.ts          # Build config
└── package.json
```

## PR22 Deliverables

1. ✅ `scripts/full_system_verify.sh` - Full system test runner
2. ✅ ERPX Agent Console UI with all pages
3. ✅ Docker integration via docker-compose
4. ✅ Backend endpoints for UI (evidence, forecasts, simulations list)

## Testing

```bash
# Run full system verification
cd /root/erp-ai
bash scripts/full_system_verify.sh

# Access UI
open http://localhost:3000
```
