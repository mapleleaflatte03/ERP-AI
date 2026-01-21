#!/bin/bash
# ==============================================================================
# MVP AI Kế toán GĐ01 - Demo Script
# Single command to run end-to-end workflow
# ==============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

ERP_AI_DIR="/root/erp-ai"
VENV_DIR="$ERP_AI_DIR/venv"

# Default input file
DEFAULT_INPUT="$ERP_AI_DIR/data/uploads/sample_invoice.png"

# ==============================================================================
# HEADER
# ==============================================================================

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗"
echo -e "║                                                              ║"
echo -e "║       MVP AI Kế toán - Giai đoạn 01 (CPU-only)             ║"
echo -e "║                                                              ║"
echo -e "╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ==============================================================================
# INPUT HANDLING
# ==============================================================================

INPUT_FILE="${1:-$DEFAULT_INPUT}"

# Make path absolute if relative
if [[ ! "$INPUT_FILE" = /* ]]; then
    INPUT_FILE="$(pwd)/$INPUT_FILE"
fi

echo -e "${YELLOW}Input:${NC} $INPUT_FILE"
echo ""

# Check file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo -e "${RED}Error: File not found: $INPUT_FILE${NC}"
    echo ""
    echo "Usage: $0 [invoice_file]"
    echo "Default: $DEFAULT_INPUT"
    exit 1
fi

# ==============================================================================
# RUN ORCHESTRATOR
# ==============================================================================

echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Running End-to-End Orchestrator...${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
echo ""

# Run the e2e demo
bash "$ERP_AI_DIR/scripts/run_e2e_demo.sh" "$INPUT_FILE"
E2E_EXIT=$?

if [ $E2E_EXIT -ne 0 ]; then
    echo -e "${RED}E2E Demo failed with exit code $E2E_EXIT${NC}"
    exit $E2E_EXIT
fi

# ==============================================================================
# FINAL SUMMARY
# ==============================================================================

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗"
echo -e "║                    MVP DEMO SUMMARY                          ║"
echo -e "╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Get latest output files
LATEST_OCR=$(ls -t "$ERP_AI_DIR/data/processed/sample_invoice"*.json 2>/dev/null | head -1)
LATEST_CODING=$(ls -t "$ERP_AI_DIR/data/processed/coding_"*.json 2>/dev/null | head -1)

echo -e "${GREEN}OUTPUT FILES:${NC}"
echo -e "  OCR JSON:    ${YELLOW}$LATEST_OCR${NC}"
echo -e "  Coding JSON: ${YELLOW}$LATEST_CODING${NC}"
echo ""

# Parse and display summary
if [ -n "$LATEST_CODING" ]; then
    cd "$ERP_AI_DIR"
    source "$VENV_DIR/bin/activate"
    
    echo -e "${GREEN}ACCOUNTING ENTRIES:${NC}"
    python3 << EOF
import json
with open('$LATEST_CODING') as f:
    d = json.load(f)

entries = d.get('suggested_entries', [])
evidence = d.get('evidence', [])
corrections = d.get('corrections', [])

sum_511 = sum(e.get('amount', 0) for e in entries if str(e.get('credit_account')) == '511')
sum_3331 = sum(e.get('amount', 0) for e in entries if str(e.get('credit_account')) == '3331')

print(f"  Invoice No:      {d.get('invoice_no', 'N/A')}")
print(f"  Entries count:   {len(entries)}")
print(f"  Revenue (511):   {sum_511:>15,.0f} VND")
print(f"  VAT (3331):      {sum_3331:>15,.0f} VND")
print(f"  Evidence count:  {len(evidence)}")
print(f"  Corrections:     {len(corrections)}")
print()
print("  Entries detail:")
for i, e in enumerate(entries, 1):
    print(f"    {i}. Dr {e.get('debit_account')} / Cr {e.get('credit_account')} = {e.get('amount', 0):,.0f} VND")
EOF
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗"
echo -e "║              ✓ MVP DEMO COMPLETED SUCCESSFULLY              ║"
echo -e "╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

exit 0
