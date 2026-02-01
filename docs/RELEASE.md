# Release Guide - ERP-AI v1.0.3+

## Quick Release Checklist

```bash
# 1. Ensure you're on main with latest changes
git checkout main
git pull origin main

# 2. Run local tests
make test
cd ui && npm test && npm run build

# 3. Create and push tag
git tag -a v1.0.3 -m "Release v1.0.3: CI/CD, approval fixes, preview improvements"
git push origin v1.0.3

# 4. CI/CD will automatically:
#    - Run tests
#    - Build Docker images
#    - Deploy to staging
#    - Wait for manual approval for production
```

## Rollback Procedures

### Option 1: Quick Rollback via Git Tag
```bash
# Deploy previous version
git checkout v1.0.2
docker compose build
docker compose up -d
```

### Option 2: Rollback Docker Images
```bash
# Pull and deploy previous image version
docker pull ghcr.io/mapleleaflatte03/erp-ai/api:v1.0.2
docker pull ghcr.io/mapleleaflatte03/erp-ai/ui:v1.0.2

# Update docker-compose to use specific tags, then:
docker compose up -d
```

### Option 3: Database Rollback (if migrations were applied)
```bash
# Check current migration state
docker exec erpx-postgres psql -U erpx -d erpx -c "SELECT * FROM schema_migrations ORDER BY version DESC LIMIT 5;"

# Restore from backup (recommended)
docker exec -i erpx-postgres psql -U erpx -d erpx < backup_before_v103.sql

# Or revert specific migration (if available)
docker exec erpx-postgres psql -U erpx -d erpx -f /migrations/rollback_v103.sql
```

### Option 4: Full System Restore
```bash
# Stop all services
docker compose down

# Restore volumes from backup
docker volume rm erpx-postgres-data
docker volume create erpx-postgres-data
docker run --rm -v erpx-postgres-data:/data -v /backup:/backup alpine tar xzf /backup/postgres_backup.tar.gz -C /data

# Checkout previous version and restart
git checkout v1.0.2
docker compose up -d
```

## Pre-Release Backup Script

```bash
#!/bin/bash
# Run before any release
BACKUP_DIR="/backup/$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR

# Backup database
docker exec erpx-postgres pg_dump -U erpx erpx > $BACKUP_DIR/erpx_db.sql

# Backup volumes
docker run --rm -v erpx-postgres-data:/data -v $BACKUP_DIR:/backup alpine tar czf /backup/postgres_data.tar.gz /data

# Save current version
git rev-parse HEAD > $BACKUP_DIR/git_sha.txt

echo "Backup completed: $BACKUP_DIR"
```

## CI/CD Pipeline Overview

### CI Pipeline (`.github/workflows/ci.yml`)
Runs on every push/PR to main:
- **Backend**: Python lint (ruff), tests (pytest)
- **Frontend**: TypeScript check, lint, tests, build
- **Security**: pip-audit, npm audit
- **Docker**: Build verification

### CD Pipeline (`.github/workflows/cd.yml`)
Runs on version tags (v*):
1. Build & push Docker images to GHCR
2. Auto-deploy to staging
3. **Manual approval required** for production
4. Create GitHub Release

## Environment Configuration

### Required Secrets (GitHub Repository Settings)
```
STAGING_SSH_KEY     - SSH key for staging server
STAGING_HOST        - Staging server hostname
STAGING_USER        - SSH user for staging

PROD_SSH_KEY        - SSH key for production server  
PROD_HOST           - Production server hostname
PROD_USER           - SSH user for production

KEYCLOAK_URL        - Keycloak auth URL for UI build
```

### Environment Protection Rules
- **staging**: No approval required, auto-deploy
- **production**: Requires 1 reviewer approval

## Version History

| Version | Date | Key Changes |
|---------|------|-------------|
| v1.0.3 | 2026-02-01 | CI/CD pipeline, approval fixes, preview improvements |
| v1.0.2 | 2026-01-30 | Keycloak auth fix, UI build improvements |
| v1.0.1 | 2026-01-25 | Initial stable release |
