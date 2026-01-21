#!/bin/bash
# ==============================================================================
# MVP AI Kế toán GĐ01 - Clean Shutdown
# Stops all services to save costs
# ==============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

ERP_AI_DIR="/root/erp-ai"

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗"
echo -e "║      MVP AI Kế toán GĐ01 - CLEAN SHUTDOWN                   ║"
echo -e "╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ==============================================================================
# STOP DOCKER SERVICES
# ==============================================================================

echo -e "${YELLOW}Stopping Docker services...${NC}"
echo ""

cd "$ERP_AI_DIR/infra"

# Stop with docker compose
docker compose down

echo ""
echo -e "${GREEN}Docker services stopped.${NC}"
echo ""

# ==============================================================================
# VERIFY NO CONTAINERS RUNNING
# ==============================================================================

echo -e "${YELLOW}Verifying containers stopped...${NC}"
echo ""

RUNNING=$(docker ps --filter "name=erp-" --format "{{.Names}}" 2>/dev/null)

if [ -z "$RUNNING" ]; then
    echo -e "${GREEN}✓ No ERP containers running${NC}"
else
    echo -e "${RED}✗ Some containers still running:${NC}"
    echo "$RUNNING"
fi

echo ""

# ==============================================================================
# SHOW DOCKER STATUS
# ==============================================================================

echo -e "${YELLOW}Current Docker status:${NC}"
echo ""
docker ps -a --filter "name=erp-" --format "table {{.Names}}\t{{.Status}}"

echo ""

# ==============================================================================
# DATA PRESERVED
# ==============================================================================

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  DATA STATUS${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${GREEN}✓ Data preserved in:${NC}"
echo "  - $ERP_AI_DIR/data/uploads/"
echo "  - $ERP_AI_DIR/data/processed/"
echo "  - $ERP_AI_DIR/logs/"
echo "  - Docker volumes (postgres, qdrant, minio)"
echo ""

# ==============================================================================
# RESTART INSTRUCTIONS
# ==============================================================================

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  TO RESTART LATER${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  cd ~/erp-ai/infra && docker compose up -d"
echo ""

# ==============================================================================
# COST SAVING REMINDER
# ==============================================================================

echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗"
echo -e "║                    💰 COST SAVING TIP                        ║"
echo -e "╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Nếu muốn tiết kiệm chi phí:"
echo ""
echo -e "  ${YELLOW}1. Destroy droplet trong DigitalOcean UI:${NC}"
echo "     https://cloud.digitalocean.com/droplets"
echo ""
echo -e "  ${YELLOW}2. Hoặc tạo snapshot trước khi destroy:${NC}"
echo "     Droplets → More → Create Snapshot"
echo ""
echo -e "  ${GREEN}Lưu ý: Snapshot có phí lưu trữ nhỏ (~\$0.05/GB/month)${NC}"
echo ""

echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗"
echo -e "║              ✓ SHUTDOWN COMPLETED                           ║"
echo -e "╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
