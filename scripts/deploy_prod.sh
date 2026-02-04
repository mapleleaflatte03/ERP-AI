#!/bin/bash
# ============================================================================
# ERP-AI Production Deploy Script (Idempotent)
# ============================================================================
# Usage: ./scripts/deploy_prod.sh [IMAGE_TAG]
# 
# Environment variables (set by CD workflow or .env):
#   IMAGE_TAG   - Docker image tag to deploy (default: main)
#   REGISTRY    - Container registry (default: ghcr.io)
#   REPO        - Repository name (default: mapleleaflatte03/erp-ai)
#
# This script:
#   1. Logs into GHCR (if GITHUB_TOKEN set)
#   2. Pulls new images
#   3. Restarts containers with docker compose
#   4. Runs health check
# ============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[DEPLOY]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Configuration
IMAGE_TAG="${IMAGE_TAG:-main}"
REGISTRY="${REGISTRY:-ghcr.io}"
REPO="${REPO:-mapleleaflatte03/erp-ai}"
DEPLOY_DIR="${DEPLOY_DIR:-/root/erp-ai}"
COMPOSE_FILE="${DEPLOY_DIR}/docker-compose.yml"

# Derived
API_IMAGE="${REGISTRY}/${REPO}/api:${IMAGE_TAG}"
UI_IMAGE="${REGISTRY}/${REPO}/ui:${IMAGE_TAG}"

log "============================================"
log "ERP-AI Production Deploy"
log "============================================"
log "Image Tag: ${IMAGE_TAG}"
log "API Image: ${API_IMAGE}"
log "UI Image:  ${UI_IMAGE}"
log "Deploy Dir: ${DEPLOY_DIR}"
log "============================================"

# Check prerequisites
if [[ ! -f "${COMPOSE_FILE}" ]]; then
    error "docker-compose.yml not found at ${COMPOSE_FILE}"
    exit 1
fi

cd "${DEPLOY_DIR}"

# Login to GHCR (if token available)
if [[ -n "${GITHUB_TOKEN:-}" ]]; then
    log "Logging into GHCR..."
    echo "${GITHUB_TOKEN}" | docker login ghcr.io -u "${GITHUB_USER:-deploy}" --password-stdin
elif [[ -f ~/.docker/config.json ]] && grep -q "ghcr.io" ~/.docker/config.json; then
    log "Using existing GHCR credentials"
else
    warn "No GITHUB_TOKEN set and no existing GHCR login. Pull may fail for private images."
fi

# Update .env with new image tags
log "Updating .env with image tags..."
if [[ -f .env ]]; then
    # Remove old image tag entries
    grep -v "^API_IMAGE=" .env | grep -v "^UI_IMAGE=" | grep -v "^IMAGE_TAG=" > .env.tmp || true
    mv .env.tmp .env
fi
echo "IMAGE_TAG=${IMAGE_TAG}" >> .env
echo "API_IMAGE=${API_IMAGE}" >> .env
echo "UI_IMAGE=${UI_IMAGE}" >> .env

# Pull images
log "Pulling images..."
docker compose pull api ui 2>/dev/null || docker compose pull 2>/dev/null || {
    error "Failed to pull images. Check GHCR authentication."
    exit 1
}

# Restart services
log "Restarting services..."
docker compose up -d --remove-orphans api ui

# Wait for startup
log "Waiting for services to start (15s)..."
sleep 15

# Health check
log "Running health check..."
HEALTH_URL="http://localhost:8000/health"
MAX_RETRIES=5
RETRY_COUNT=0

while [[ $RETRY_COUNT -lt $MAX_RETRIES ]]; do
    HEALTH_STATUS=$(curl -sf "${HEALTH_URL}" 2>/dev/null | jq -r '.status' 2>/dev/null || echo "failed")
    
    if [[ "$HEALTH_STATUS" == "ok" || "$HEALTH_STATUS" == "degraded" ]]; then
        log "✅ Health check passed (status: ${HEALTH_STATUS})"
        break
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    warn "Health check attempt ${RETRY_COUNT}/${MAX_RETRIES} failed, retrying in 5s..."
    sleep 5
done

if [[ $RETRY_COUNT -ge $MAX_RETRIES ]]; then
    error "Health check failed after ${MAX_RETRIES} attempts"
    error "Check logs: docker compose logs api"
    exit 1
fi

# Version check (if endpoint exists)
VERSION_RESP=$(curl -sf "http://localhost:8000/version" 2>/dev/null || echo '{}')
DEPLOYED_SHA=$(echo "$VERSION_RESP" | jq -r '.git_sha // "unknown"' 2>/dev/null || echo "unknown")
log "Deployed SHA: ${DEPLOYED_SHA}"

log "============================================"
log "✅ Deployment complete!"
log "============================================"
