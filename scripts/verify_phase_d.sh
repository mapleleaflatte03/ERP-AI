#!/bin/bash
# PHASE D Verification Script
# Verifies: LLM load, Qdrant query, Demo run, Output schema

# Note: Don't use set -e as ((var++)) returns 1 when var is 0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ERP_AI_DIR="/root/erp-ai"
VENV_DIR="$ERP_AI_DIR/venv"

echo "=============================================="
echo "  PHASE D VERIFICATION"
echo "=============================================="

cd "$ERP_AI_DIR"
source "$VENV_DIR/bin/activate"
export CUDA_VISIBLE_DEVICES=""

PASS=0
FAIL=0

# Test 1: LLM imports OK (with timeout)
echo ""
echo -e "${YELLOW}[Test 1] LLM imports (timeout 30s)...${NC}"
if timeout 30 python -c "import torch; import transformers; print('torch:', torch.__version__); print('transformers:', transformers.__version__)" 2>/dev/null; then
    echo -e "${GREEN}✓ LLM imports OK${NC}"
    ((PASS++))
else
    echo -e "${RED}✗ LLM imports FAILED or timeout${NC}"
    ((FAIL++))
fi

# Test 2: CPU-only (no CUDA) - with timeout
echo ""
echo -e "${YELLOW}[Test 2] CPU-only mode (timeout 10s)...${NC}"
CUDA_STATUS=$(timeout 10 python -c "import torch; print('NO_CUDA' if not torch.cuda.is_available() else 'HAS_CUDA')" 2>/dev/null || echo "TIMEOUT")
if [ "$CUDA_STATUS" == "NO_CUDA" ]; then
    echo -e "${GREEN}✓ CPU-only mode confirmed${NC}"
    ((PASS++))
elif [ "$CUDA_STATUS" == "TIMEOUT" ]; then
    echo -e "${RED}✗ CPU check timeout${NC}"
    ((FAIL++))
else
    echo -e "${RED}✗ CUDA detected (should be CPU-only)${NC}"
    ((FAIL++))
fi

# Test 3: Qdrant connection
echo ""
echo -e "${YELLOW}[Test 3] Qdrant connection...${NC}"
QDRANT_STATUS=$(curl -s --max-time 5 http://localhost:6333/readyz 2>/dev/null || echo "FAIL")
if [ "$QDRANT_STATUS" == "all shards are ready" ]; then
    echo -e "${GREEN}✓ Qdrant is ready${NC}"
    ((PASS++))
else
    echo -e "${RED}✗ Qdrant not ready${NC}"
    ((FAIL++))
fi

# Test 4: Coding Agent import (with timeout)
echo ""
echo -e "${YELLOW}[Test 4] Coding Agent import (timeout 30s)...${NC}"
if timeout 30 python -c "from agents.accounting_coding import AccountingCodingAgent; print('OK')" 2>/dev/null; then
    echo -e "${GREEN}✓ Coding Agent import OK${NC}"
    ((PASS++))
else
    echo -e "${RED}✗ Coding Agent import FAILED or timeout${NC}"
    ((FAIL++))
fi

# Test 5: Demo output exists and valid
echo ""
echo -e "${YELLOW}[Test 5] Demo output validation...${NC}"
LATEST_OUTPUT=$(ls -t "$ERP_AI_DIR/data/processed/coding_"*.json 2>/dev/null | head -1)

if [ -n "$LATEST_OUTPUT" ]; then
    # Check schema with timeout
    SCHEMA_CHECK=$(timeout 10 python3 -c "
import json
d=json.load(open('$LATEST_OUTPUT'))
has_entries = bool(d.get('suggested_entries'))
has_explanation = bool(d.get('explanation'))
has_evidence = bool(d.get('evidence'))
# Check guardrail amounts
total = d.get('total', 0) or 0
vat = d.get('vat', 0) or 0
sum_511 = sum(e.get('amount', 0) for e in d.get('suggested_entries', []) if str(e.get('credit_account')) == '511')
sum_3331 = sum(e.get('amount', 0) for e in d.get('suggested_entries', []) if str(e.get('credit_account')) == '3331')
amounts_ok = (sum_511 == total or total == 0) and (sum_3331 == vat or vat == 0)
print('OK' if has_entries and has_explanation and has_evidence and amounts_ok else 'FAIL')
" 2>/dev/null || echo "TIMEOUT")
    
    if [ "$SCHEMA_CHECK" == "OK" ]; then
        echo -e "${GREEN}✓ Output schema and guardrails valid${NC}"
        ((PASS++))
    else
        echo -e "${RED}✗ Output schema/guardrails invalid ($SCHEMA_CHECK)${NC}"
        ((FAIL++))
    fi
else
    echo -e "${RED}✗ No demo output found${NC}"
    ((FAIL++))
fi

# Summary
echo ""
echo "=============================================="
echo "  VERIFICATION SUMMARY"
echo "=============================================="
echo -e "Passed: ${GREEN}$PASS${NC}"
echo -e "Failed: ${RED}$FAIL${NC}"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}✓ PHASE D VERIFIED OK${NC}"
    echo ""
    echo "=============================================="
    echo "  PHASE D FINAL STATS"
    echo "=============================================="
    
    # Model info
    echo "Model: $(grep QWEN_MODEL $ERP_AI_DIR/configs/llm.env | cut -d= -f2)"
    
    # Latest output summary
    if [ -n "$LATEST_OUTPUT" ]; then
        echo ""
        echo "Latest Output: $LATEST_OUTPUT"
        echo ""
        timeout 10 python3 << EOF
import json
with open('$LATEST_OUTPUT') as f:
    d = json.load(f)
print(f"Invoice: {d.get('invoice_no', 'N/A')}")
print(f"Grand Total: {d.get('grand_total', 0):,.0f} VND")
print(f"Entries: {len(d.get('suggested_entries', []))}")
for i, e in enumerate(d.get('suggested_entries', []), 1):
    print(f"  {i}. Dr {e.get('debit_account')} / Cr {e.get('credit_account')} - {e.get('amount', 0):,.0f}")
print(f"Evidence chunks: {len(d.get('evidence', []))}")
print(f"Corrections: {len(d.get('corrections', []))}")
print(f"LLM used: {d.get('llm_used', False)}")
print(f"Model: {d.get('model', 'N/A')}")
EOF
    fi
    
    exit 0
else
    echo -e "${RED}✗ PHASE D VERIFICATION FAILED${NC}"
    exit 1
fi
