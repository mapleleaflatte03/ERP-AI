#!/bin/bash
# ==============================================================================
# ERP AI - End-to-End Demo Script
# Runs complete workflow: Input → OCR → Embed → Coding → Output
# ==============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ERP_AI_DIR="/root/erp-ai"
VENV_DIR="$ERP_AI_DIR/venv"

# ==============================================================================
# FUNCTIONS
# ==============================================================================

show_usage() {
    echo "Usage: $0 <invoice_file>"
    echo ""
    echo "Arguments:"
    echo "  invoice_file    Path to invoice file (PDF, PNG, JPG)"
    echo ""
    echo "Examples:"
    echo "  $0 /root/erp-ai/data/uploads/sample_invoice.png"
    echo "  $0 ./invoice.pdf"
}

# ==============================================================================
# MAIN
# ==============================================================================

echo ""
echo -e "${BLUE}=============================================="
echo "  ERP AI - End-to-End Orchestrator Demo"
echo "==============================================${NC}"
echo ""

# Check args
if [ -z "$1" ]; then
    echo -e "${RED}Error: No input file specified${NC}"
    show_usage
    exit 1
fi

INPUT_FILE="$1"

# Make path absolute if relative
if [[ ! "$INPUT_FILE" = /* ]]; then
    INPUT_FILE="$(pwd)/$INPUT_FILE"
fi

# Check file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo -e "${RED}Error: File not found: $INPUT_FILE${NC}"
    exit 1
fi

echo -e "${YELLOW}Input File:${NC} $INPUT_FILE"
echo ""

# Activate venv
cd "$ERP_AI_DIR"
source "$VENV_DIR/bin/activate"

# Force CPU mode
export CUDA_VISIBLE_DEVICES=""
export FLAGS_use_cuda="0"

# Run orchestrator
echo -e "${YELLOW}----------------------------------------------"
echo "Running Orchestrator Workflow..."
echo "----------------------------------------------${NC}"
echo ""

python -m agents.orchestrator.workflow_graph "$INPUT_FILE"
EXIT_CODE=$?

echo ""

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}=============================================="
    echo "  END-TO-END DEMO COMPLETED SUCCESSFULLY"
    echo "==============================================${NC}"
    echo ""
    
    # Show latest output files
    echo -e "${YELLOW}Latest Output Files:${NC}"
    echo ""
    
    # OCR JSON
    LATEST_OCR=$(ls -t "$ERP_AI_DIR/data/processed/sample_invoice"*.json 2>/dev/null | head -1)
    if [ -n "$LATEST_OCR" ]; then
        echo -e "  OCR JSON: ${GREEN}$LATEST_OCR${NC}"
    fi
    
    # Coding JSON
    LATEST_CODING=$(ls -t "$ERP_AI_DIR/data/processed/coding_"*.json 2>/dev/null | head -1)
    if [ -n "$LATEST_CODING" ]; then
        echo -e "  Coding JSON: ${GREEN}$LATEST_CODING${NC}"
    fi
    
    echo ""
    exit 0
else
    echo -e "${RED}=============================================="
    echo "  END-TO-END DEMO FAILED"
    echo "==============================================${NC}"
    echo ""
    echo "Check logs: $ERP_AI_DIR/logs/orchestrator.log"
    exit 1
fi
