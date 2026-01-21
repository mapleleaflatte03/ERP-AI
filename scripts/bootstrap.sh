#!/bin/bash
# ERPX AI Accounting - Bootstrap Script
# =====================================
# Setup and run the full stack
#
# IMPORTANT: Uses DO Agent qwen3-32b ONLY - NO LOCAL LLM

set -e

echo "=========================================="
echo "ERPX AI Accounting - Bootstrap"
echo "DO Agent qwen3-32b ONLY"
echo "=========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="/root/erp-ai"
cd "$PROJECT_DIR"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}ERROR: Docker not installed${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}ERROR: Docker Compose not installed${NC}"
    exit 1
fi

# Check .env file
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env file from example...${NC}"
    cp .env.example .env 2>/dev/null || cat > .env << 'ENVEOF'
# ERPX AI Accounting - Environment Variables
# ==========================================

# LLM Configuration - DO Agent ONLY (NO LOCAL LLM)
LLM_PROVIDER=do_agent
DO_AGENT_URL=https://gdfyu2bkvuq4idxkb6x2xkpe.agents.do-ai.run
DO_AGENT_KEY=J0DmNnkcjIOlB6n3tUKkZ-2OSW2ZOE_C
DO_AGENT_MODEL=qwen3-32b
DISABLE_LOCAL_LLM=1

# Telegram Bot (optional - set your bot token)
TELEGRAM_BOT_TOKEN=

# Database
DATABASE_URL=postgresql://erpx:erpx_secret@postgres:5432/erpx

# MinIO
MINIO_ACCESS_KEY=erpx_minio
MINIO_SECRET_KEY=erpx_minio_secret

# Environment
ENV=production
ENVEOF
fi

echo -e "${GREEN}✓ Environment configured${NC}"

# Create required directories
echo "Creating directories..."
mkdir -p data/uploads data/kb data/sample_invoices logs
mkdir -p infrastructure/grafana/provisioning/dashboards
mkdir -p infrastructure/grafana/provisioning/datasources

# Create Grafana datasource config
cat > infrastructure/grafana/provisioning/datasources/datasources.yml << 'DSEOF'
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
  - name: Jaeger
    type: jaeger
    access: proxy
    url: http://jaeger:16686
DSEOF

echo -e "${GREEN}✓ Directories created${NC}"

# Pull images
echo "Pulling Docker images..."
docker compose pull --quiet || true

# Build application images
echo "Building application images..."
docker compose build --quiet

echo -e "${GREEN}✓ Images ready${NC}"

# Start services
echo "Starting services..."
docker compose up -d

# Wait for services
echo "Waiting for services to be healthy..."
sleep 30

# Check service health
check_service() {
    local name=$1
    local url=$2
    if curl -sf "$url" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓ $name${NC}"
        return 0
    else
        echo -e "  ${YELLOW}○ $name (starting...)${NC}"
        return 1
    fi
}

echo ""
echo "Service Status:"
check_service "API" "http://localhost:8000/health"
check_service "Web UI" "http://localhost:3000"
check_service "Postgres" "localhost:5432" || true
check_service "Qdrant" "http://localhost:6333"
check_service "MinIO" "http://localhost:9000/minio/health/live"
check_service "Jaeger" "http://localhost:16686"
check_service "Prometheus" "http://localhost:9090"
check_service "Grafana" "http://localhost:3001"
check_service "Temporal UI" "http://localhost:8088"
check_service "Kong" "http://localhost:8001"
check_service "OPA" "http://localhost:8181"

echo ""
echo "=========================================="
echo -e "${GREEN}ERPX AI Accounting is running!${NC}"
echo "=========================================="
echo ""
echo "Access Points:"
echo "  📊 Web UI:        http://localhost:3000"
echo "  🔌 API:           http://localhost:8000"
echo "  📈 Grafana:       http://localhost:3001 (admin/admin)"
echo "  🔍 Jaeger:        http://localhost:16686"
echo "  ⚙️  Temporal UI:   http://localhost:8088"
echo "  📦 MinIO Console: http://localhost:9001 (erpx_minio/erpx_minio_secret)"
echo "  🏛️  Kong Admin:    http://localhost:8001"
echo "  📜 OPA:           http://localhost:8181"
echo ""
echo "LLM Provider: DO Agent qwen3-32b"
echo ""
echo "Quick Test:"
echo "  curl http://localhost:8000/health"
echo ""
