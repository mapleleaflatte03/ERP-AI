#!/bin/bash
# ==============================================================================
# PHASE E Verification Script
# Verifies: LangGraph, E2E Demo, Output schema, Guardrails
# ==============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ERP_AI_DIR="/root/erp-ai"
VENV_DIR="$ERP_AI_DIR/venv"

echo ""
echo -e "${BLUE}=============================================="
echo "  PHASE E VERIFICATION"
echo "==============================================${NC}"
echo ""

cd "$ERP_AI_DIR"
source "$VENV_DIR/bin/activate"
export CUDA_VISIBLE_DEVICES=""

PASS=0
FAIL=0

# ==============================================================================
# Test 1: LangGraph import
# ==============================================================================
echo -e "${YELLOW}[Test 1] LangGraph import...${NC}"
if timeout 10 python -c "import langgraph; print('LangGraph imported')" 2>/dev/null; then
    echo -e "${GREEN}✓ LangGraph import OK${NC}"
    PASS=$((PASS+1))
else
    echo -e "${RED}✗ LangGraph import FAILED${NC}"
    FAIL=$((FAIL+1))
fi

# ==============================================================================
# Test 2: Workflow graph import
# ==============================================================================
echo ""
echo -e "${YELLOW}[Test 2] Workflow graph import...${NC}"
if timeout 30 python -c "from agents.orchestrator.workflow_graph import build_graph; print('Graph builds OK')" 2>/dev/null; then
    echo -e "${GREEN}✓ Workflow graph import OK${NC}"
    PASS=$((PASS+1))
else
    echo -e "${RED}✗ Workflow graph import FAILED${NC}"
    FAIL=$((FAIL+1))
fi

# ==============================================================================
# Test 3: E2E Demo run (use existing OCR JSON to save time)
# ==============================================================================
echo ""
echo -e "${YELLOW}[Test 3] E2E Demo (with existing invoice)...${NC}"

# Check if sample invoice exists
SAMPLE_INVOICE="$ERP_AI_DIR/data/uploads/sample_invoice.png"
if [ ! -f "$SAMPLE_INVOICE" ]; then
    echo -e "${RED}✗ Sample invoice not found: $SAMPLE_INVOICE${NC}"
    FAIL=$((FAIL+1))
else
    # Run E2E demo with timeout
    if timeout 240 bash "$ERP_AI_DIR/scripts/run_e2e_demo.sh" "$SAMPLE_INVOICE" > /tmp/e2e_output.txt 2>&1; then
        echo -e "${GREEN}✓ E2E Demo completed successfully${NC}"
        PASS=$((PASS+1))
    else
        echo -e "${RED}✗ E2E Demo FAILED${NC}"
        cat /tmp/e2e_output.txt | tail -20
        FAIL=$((FAIL+1))
    fi
fi

# ==============================================================================
# Test 4: Output JSON schema validation
# ==============================================================================
echo ""
echo -e "${YELLOW}[Test 4] Output schema validation...${NC}"

LATEST_CODING=$(ls -t "$ERP_AI_DIR/data/processed/coding_"*.json 2>/dev/null | head -1)

if [ -n "$LATEST_CODING" ]; then
    SCHEMA_CHECK=$(timeout 10 python3 << EOF
import json
try:
    with open('$LATEST_CODING') as f:
        d = json.load(f)
    
    # Check required fields
    entries = d.get('suggested_entries', [])
    evidence = d.get('evidence', [])
    
    has_entries = len(entries) >= 2
    has_evidence = len(evidence) >= 1
    has_invoice = bool(d.get('invoice_no'))
    
    if has_entries and has_evidence and has_invoice:
        print('OK')
    else:
        print(f'FAIL:entries={len(entries)},evidence={len(evidence)},invoice={d.get("invoice_no")}')
except Exception as e:
    print(f'ERROR:{e}')
EOF
)
    
    if [ "$SCHEMA_CHECK" == "OK" ]; then
        echo -e "${GREEN}✓ Output schema valid (entries>=2, evidence>=1)${NC}"
        PASS=$((PASS+1))
    else
        echo -e "${RED}✗ Output schema invalid: $SCHEMA_CHECK${NC}"
        FAIL=$((FAIL+1))
    fi
else
    echo -e "${RED}✗ No coding output JSON found${NC}"
    FAIL=$((FAIL+1))
fi

# ==============================================================================
# Test 5: Guardrails validation (511=TOTAL, 3331=VAT)
# ==============================================================================
echo ""
echo -e "${YELLOW}[Test 5] Guardrails validation...${NC}"

if [ -n "$LATEST_CODING" ]; then
    GUARDRAILS_CHECK=$(timeout 10 python3 << EOF
import json
try:
    with open('$LATEST_CODING') as f:
        d = json.load(f)
    
    total = d.get('total', 0) or 0
    vat = d.get('vat', 0) or 0
    entries = d.get('suggested_entries', [])
    
    sum_511 = sum(e.get('amount', 0) for e in entries if str(e.get('credit_account')) == '511')
    sum_3331 = sum(e.get('amount', 0) for e in entries if str(e.get('credit_account')) == '3331')
    
    ok_511 = (sum_511 == total) if total > 0 else True
    ok_3331 = (sum_3331 == vat) if vat > 0 else True
    
    if ok_511 and ok_3331:
        print(f'OK:511={sum_511},3331={sum_3331}')
    else:
        print(f'FAIL:511={sum_511}(expect={total}),3331={sum_3331}(expect={vat})')
except Exception as e:
    print(f'ERROR:{e}')
EOF
)
    
    if [[ "$GUARDRAILS_CHECK" == OK* ]]; then
        echo -e "${GREEN}✓ Guardrails valid: $GUARDRAILS_CHECK${NC}"
        PASS=$((PASS+1))
    else
        echo -e "${RED}✗ Guardrails invalid: $GUARDRAILS_CHECK${NC}"
        FAIL=$((FAIL+1))
    fi
else
    echo -e "${RED}✗ No coding output JSON found${NC}"
    FAIL=$((FAIL+1))
fi

# ==============================================================================
# Test 6: Log file exists and has content
# ==============================================================================
echo ""
echo -e "${YELLOW}[Test 6] Orchestrator log file...${NC}"

LOG_FILE="$ERP_AI_DIR/logs/orchestrator.log"
if [ -f "$LOG_FILE" ] && [ -s "$LOG_FILE" ]; then
    LOG_LINES=$(wc -l < "$LOG_FILE")
    echo -e "${GREEN}✓ Log file exists ($LOG_LINES lines)${NC}"
    PASS=$((PASS+1))
else
    echo -e "${RED}✗ Log file missing or empty${NC}"
    FAIL=$((FAIL+1))
fi

# ==============================================================================
# SUMMARY
# ==============================================================================
echo ""
echo -e "${BLUE}=============================================="
echo "  VERIFICATION SUMMARY"
echo "==============================================${NC}"
echo -e "Passed: ${GREEN}$PASS${NC}"
echo -e "Failed: ${RED}$FAIL${NC}"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}✓ PHASE E VERIFIED OK${NC}"
    echo ""
    echo -e "${BLUE}=============================================="
    echo "  PHASE E FINAL STATS"
    echo "==============================================${NC}"
    
    if [ -n "$LATEST_CODING" ]; then
        echo ""
        echo "Latest Coding Output: $LATEST_CODING"
        echo ""
        timeout 10 python3 << EOF
import json
with open('$LATEST_CODING') as f:
    d = json.load(f)

entries = d.get('suggested_entries', [])
evidence = d.get('evidence', [])

sum_511 = sum(e.get('amount', 0) for e in entries if str(e.get('credit_account')) == '511')
sum_3331 = sum(e.get('amount', 0) for e in entries if str(e.get('credit_account')) == '3331')

print(f"Invoice: {d.get('invoice_no', 'N/A')}")
print(f"Entries count: {len(entries)}")
print(f"  Revenue (511): {sum_511:,.0f} VND")
print(f"  VAT (3331): {sum_3331:,.0f} VND")
print(f"Evidence chunks: {len(evidence)}")
print(f"Corrections: {len(d.get('corrections', []))}")
print(f"Model: {d.get('model', 'N/A')}")
EOF
    fi
    
    exit 0
else
    echo -e "${RED}✗ PHASE E VERIFICATION FAILED${NC}"
    exit 1
fi
