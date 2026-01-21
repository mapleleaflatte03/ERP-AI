#!/bin/bash
# Accounting Coding Agent Demo Script
# Usage: ./run_coding_demo.sh <invoice_json_path>

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ERP_AI_DIR="/root/erp-ai"
VENV_DIR="$ERP_AI_DIR/venv"

echo "=============================================="
echo "  ERP AI - Accounting Coding Agent Demo"
echo "=============================================="

# Check argument
if [ -z "$1" ]; then
    echo -e "${RED}Error: No invoice JSON file provided${NC}"
    echo ""
    echo "Usage: $0 <invoice_json_path>"
    echo ""
    echo "Example:"
    echo "  $0 /root/erp-ai/data/processed/sample_invoice_20260116_180920.json"
    exit 1
fi

INVOICE_JSON="$1"

# Check file exists
if [ ! -f "$INVOICE_JSON" ]; then
    echo -e "${RED}Error: File not found: $INVOICE_JSON${NC}"
    exit 1
fi

echo -e "${YELLOW}Invoice JSON: $INVOICE_JSON${NC}"

# Activate venv
cd "$ERP_AI_DIR"
source "$VENV_DIR/bin/activate"

# Force CPU
export CUDA_VISIBLE_DEVICES=""

# Check if we should use LLM or fallback
USE_LLM_FLAG=""
if [ "$2" == "--no_llm" ]; then
    USE_LLM_FLAG="--no_llm"
    echo -e "${YELLOW}Mode: Rule-based fallback (no LLM)${NC}"
else
    echo -e "${YELLOW}Mode: LLM + RAG (may take 1-2 minutes on CPU)${NC}"
fi

echo ""
echo "----------------------------------------------"
echo "Running Accounting Coding Agent..."
echo "----------------------------------------------"

# Run agent
python -m agents.accounting_coding.coding_agent --invoice_json "$INVOICE_JSON" --top_k 5 $USE_LLM_FLAG

# List output files
echo ""
echo "----------------------------------------------"
echo "Output files:"
echo "----------------------------------------------"
ls -lah "$ERP_AI_DIR/data/processed/coding_"*.json 2>/dev/null | tail -5 || echo "No coding output files found"

echo ""
echo -e "${GREEN}Demo completed!${NC}"
echo "=============================================="
