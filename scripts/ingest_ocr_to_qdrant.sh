#!/bin/bash
# Qdrant Init + Ingest OCR to Qdrant
# Usage: ./ingest_ocr_to_qdrant.sh

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ERP_AI_DIR="/root/erp-ai"
VENV_DIR="$ERP_AI_DIR/venv"
PROCESSED_DIR="$ERP_AI_DIR/data/processed"

echo "=============================================="
echo "  ERP AI - Qdrant Ingestion Script"
echo "=============================================="

# Check Qdrant is running
echo -e "${YELLOW}Checking Qdrant connection...${NC}"
if ! curl -fsS http://localhost:6333/readyz > /dev/null 2>&1; then
    echo -e "${RED}Error: Qdrant is not running or not accessible${NC}"
    exit 1
fi
echo -e "${GREEN}Qdrant is ready${NC}"

# Check JSON files exist
JSON_COUNT=$(ls -1 "$PROCESSED_DIR"/*.json 2>/dev/null | wc -l)
if [ "$JSON_COUNT" -eq 0 ]; then
    echo -e "${RED}Error: No JSON files found in $PROCESSED_DIR${NC}"
    exit 1
fi
echo -e "${GREEN}Found $JSON_COUNT JSON file(s) to ingest${NC}"

# Activate venv and run ingestion
echo ""
echo "----------------------------------------------"
echo "Starting ingestion..."
echo "----------------------------------------------"

cd "$ERP_AI_DIR"
source "$VENV_DIR/bin/activate"

# Force CPU
export CUDA_VISIBLE_DEVICES=""

# Run embedding service on processed directory
python -m services.rag.embedding_service "$PROCESSED_DIR"

# Get final stats
echo ""
echo "----------------------------------------------"
echo "Collection Status:"
echo "----------------------------------------------"
curl -s http://localhost:6333/collections/erp_ai_docs | python3 -m json.tool 2>/dev/null || curl -s http://localhost:6333/collections/erp_ai_docs

echo ""
echo -e "${GREEN}Ingestion completed!${NC}"
echo "=============================================="
