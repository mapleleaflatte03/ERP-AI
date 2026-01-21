# ERPX E2E Production Runbook

## Overview

This runbook provides instructions for deploying and operating the ERPX E2E system in production.

## Prerequisites

- Docker & Docker Compose v2+
- Minimum 8GB RAM, 4 vCPU
- 100GB disk space
- PostgreSQL 15+
- Network access to ports: 5432, 6333, 8000, 9000

## Production Deployment

### 1. Configure Environment

Create `/root/erp-ai/.env`:

```bash
# Database
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_USER=erp_user
POSTGRES_PASSWORD=<STRONG_PASSWORD>
POSTGRES_DB=erp_ai

# MinIO
MINIO_ROOT_USER=minio_admin
MINIO_ROOT_PASSWORD=<STRONG_PASSWORD>

# API
API_HOST=0.0.0.0
API_PORT=8000

# Workers
WORKER_POLL_INTERVAL=5
DISPATCHER_POLL_INTERVAL=2
```

### 2. Deploy with Docker Compose

```bash
cd /root/erp-ai/infra

# Pull images
docker compose pull

# Start all services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f
```

### 3. Verify Deployment

```bash
# Health check
curl http://localhost:8000/health

# Expected response:
# {
#   "status": "healthy",
#   "version": "1.0.0-e2e",
#   "components": {
#     "postgres": "healthy",
#     "qdrant": "healthy"
#   }
# }
```

---

## Service URLs

| Service | URL | Description |
|---------|-----|-------------|
| Gateway API | http://localhost:8000 | Main API endpoint |
| API Docs | http://localhost:8000/docs | Swagger UI |
| Health | http://localhost:8000/health | Health check |
| Metrics | http://localhost:8000/health/metrics | Metrics endpoint |
| MinIO Console | http://localhost:9001 | Object storage UI |
| MLflow | http://localhost:5000 | Model registry |

---

## Monitoring

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Readiness
curl http://localhost:8000/health/ready

# Liveness
curl http://localhost:8000/health/live
```

### Metrics

```bash
# Get metrics
curl http://localhost:8000/health/metrics

# Response includes:
# - requests_total
# - requests_by_endpoint
# - requests_by_tenant
# - errors_total
# - avg_response_time_ms
# - uptime_seconds
```

### Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f gateway-api
docker compose logs -f pipeline-worker
docker compose logs -f outbox-dispatcher

# Host logs
tail -f /root/erp-ai/logs/gateway_api.log
tail -f /root/erp-ai/logs/pipeline_worker.log
tail -f /root/erp-ai/logs/outbox_dispatcher.log
tail -f /root/erp-ai/logs/orchestrator.log
```

---

## Database Operations

### Check Database Status

```bash
# Connect to database
docker compose exec postgres psql -U erp_user -d erp_ai

# Check E2E tables
\dt e2e_*

# Check invoice counts by status
SELECT status, COUNT(*) FROM e2e_invoices GROUP BY status;

# Check outbox events
SELECT event_type, status, COUNT(*) 
FROM e2e_outbox_events 
GROUP BY event_type, status;

# Check recent audit events
SELECT action, entity_type, created_at 
FROM e2e_audit_events 
ORDER BY created_at DESC 
LIMIT 20;
```

### Database Backup

```bash
# Backup
docker compose exec postgres pg_dump -U erp_user erp_ai > backup_$(date +%Y%m%d).sql

# Restore
docker compose exec -T postgres psql -U erp_user erp_ai < backup_20260119.sql
```

---

## Scaling

### Horizontal Scaling

```bash
# Scale pipeline workers
docker compose up -d --scale pipeline-worker=3

# Scale outbox dispatchers
docker compose up -d --scale outbox-dispatcher=2
```

### Resource Limits

Edit `docker-compose.yml` to add:

```yaml
services:
  gateway-api:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

---

## Troubleshooting

### Service Not Starting

```bash
# Check logs
docker compose logs <service>

# Restart service
docker compose restart <service>

# Rebuild
docker compose build --no-cache <service>
docker compose up -d <service>
```

### Database Connection Issues

```bash
# Check PostgreSQL
docker compose exec postgres pg_isready -U erp_user -d erp_ai

# Check connection from API
docker compose exec gateway-api python -c "
from apps.gateway_api.deps import get_engine
engine = get_engine()
with engine.connect() as conn:
    print('Connected:', conn.execute('SELECT 1').fetchone())
"
```

### Stuck Invoices

```bash
# Find stuck invoices
docker compose exec postgres psql -U erp_user -d erp_ai -c "
SELECT id, status, created_at, updated_at 
FROM e2e_invoices 
WHERE status IN ('UPLOADED', 'PROCESSING')
AND updated_at < NOW() - INTERVAL '30 minutes';
"

# Reset stuck invoices
docker compose exec postgres psql -U erp_user -d erp_ai -c "
UPDATE e2e_invoices 
SET status = 'UPLOADED', updated_at = NOW()
WHERE status = 'PROCESSING'
AND updated_at < NOW() - INTERVAL '30 minutes';
"
```

### Failed Outbox Events

```bash
# Check failed events
docker compose exec postgres psql -U erp_user -d erp_ai -c "
SELECT id, event_type, error_message, retry_count, created_at
FROM e2e_outbox_events
WHERE status = 'FAILED'
ORDER BY created_at DESC
LIMIT 10;
"

# Retry failed events
docker compose exec postgres psql -U erp_user -d erp_ai -c "
UPDATE e2e_outbox_events
SET status = 'PENDING', retry_count = 0
WHERE status = 'FAILED';
"
```

---

## Maintenance

### Daily Tasks

1. Check health endpoints
2. Review error logs
3. Monitor disk usage
4. Check outbox queue depth

### Weekly Tasks

1. Database vacuum and analyze
2. Clean old audit logs
3. Review metrics trends
4. Backup database

### Monthly Tasks

1. Update dependencies
2. Security patches
3. Performance review
4. Capacity planning

---

## Security Checklist

- [ ] Change default passwords
- [ ] Enable TLS/HTTPS
- [ ] Configure firewall
- [ ] Set up API rate limiting
- [ ] Enable audit logging
- [ ] Configure backup encryption
- [ ] Review access controls
- [ ] Update API keys

---

## Contact

For production support, contact the infrastructure team.
