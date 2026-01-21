#!/bin/bash
# ==============================================================================
# MVP AI Kế toán GĐ01 - Smoke Test (Full Verification)
# ==============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

ERP_AI_DIR="/root/erp-ai"
VENV_DIR="$ERP_AI_DIR/venv"

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗"
echo -e "║      MVP AI Kế toán GĐ01 - SMOKE TEST                        ║"
echo -e "╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

cd "$ERP_AI_DIR"
source "$VENV_DIR/bin/activate"
export CUDA_VISIBLE_DEVICES=""

PASS=0
FAIL=0

# ==============================================================================
# INFRA HEALTH CHECKS
# ==============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  INFRASTRUCTURE HEALTH${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Test 1: PostgreSQL
echo -e "${YELLOW}[1/10] PostgreSQL...${NC}"
PG_STATUS=$(docker exec erp-postgres pg_isready -U erp_user 2>/dev/null | grep -c "accepting connections" || echo "0")
if [ "$PG_STATUS" -ge 1 ]; then
    echo -e "${GREEN}  ✓ PostgreSQL ready${NC}"
    PASS=$((PASS+1))
else
    echo -e "${RED}  ✗ PostgreSQL not ready${NC}"
    FAIL=$((FAIL+1))
fi

# Test 2: Qdrant
echo -e "${YELLOW}[2/10] Qdrant...${NC}"
QDRANT_STATUS=$(curl -s --max-time 5 http://localhost:6333/readyz 2>/dev/null || echo "FAIL")
if [ "$QDRANT_STATUS" == "all shards are ready" ]; then
    echo -e "${GREEN}  ✓ Qdrant ready${NC}"
    PASS=$((PASS+1))
else
    echo -e "${RED}  ✗ Qdrant not ready ($QDRANT_STATUS)${NC}"
    FAIL=$((FAIL+1))
fi

# Test 3: MinIO
echo -e "${YELLOW}[3/10] MinIO...${NC}"
MINIO_STATUS=$(curl -s --max-time 5 -o /dev/null -w "%{http_code}" http://localhost:9000/minio/health/live 2>/dev/null || echo "000")
if [ "$MINIO_STATUS" == "200" ]; then
    echo -e "${GREEN}  ✓ MinIO ready${NC}"
    PASS=$((PASS+1))
else
    echo -e "${RED}  ✗ MinIO not ready (HTTP $MINIO_STATUS)${NC}"
    FAIL=$((FAIL+1))
fi

# Test 4: MLflow
echo -e "${YELLOW}[4/10] MLflow...${NC}"
MLFLOW_STATUS=$(curl -s --max-time 5 http://localhost:5000/health 2>/dev/null | grep -c "OK" || echo "0")
if [ "$MLFLOW_STATUS" -ge 1 ]; then
    echo -e "${GREEN}  ✓ MLflow ready${NC}"
    PASS=$((PASS+1))
else
    echo -e "${RED}  ✗ MLflow not ready${NC}"
    FAIL=$((FAIL+1))
fi

# ==============================================================================
# OCR TEST
# ==============================================================================
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  OCR PIPELINE${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo -e "${YELLOW}[5/10] OCR creates JSON with blocks...${NC}"
OCR_RESULT=$(timeout 60 python3 << 'EOF'
import sys
sys.path.insert(0, '/root/erp-ai')
from services.ocr.ocr_pipeline import OCRPipeline
ocr = OCRPipeline()
result = ocr.process_file('/root/erp-ai/data/uploads/sample_invoice.png')
blocks = result.get('blocks', [])
output = result.get('output_file', '')
if blocks and output:
    print(f"OK:{len(blocks)}")
else:
    print("FAIL")
EOF
2>/dev/null)

if [[ "$OCR_RESULT" == OK* ]]; then
    BLOCKS_COUNT=$(echo "$OCR_RESULT" | cut -d: -f2)
    echo -e "${GREEN}  ✓ OCR OK ($BLOCKS_COUNT blocks)${NC}"
    PASS=$((PASS+1))
else
    echo -e "${RED}  ✗ OCR failed${NC}"
    FAIL=$((FAIL+1))
fi

# ==============================================================================
# QDRANT COLLECTION TEST
# ==============================================================================
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  VECTOR DATABASE${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo -e "${YELLOW}[6/10] Qdrant collection exists with points...${NC}"
POINTS_COUNT=$(curl -s http://localhost:6333/collections/erp_ai_docs 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('result',{}).get('points_count',0))" 2>/dev/null || echo "0")
if [ "$POINTS_COUNT" -gt 0 ]; then
    echo -e "${GREEN}  ✓ Qdrant collection OK ($POINTS_COUNT points)${NC}"
    PASS=$((PASS+1))
else
    echo -e "${RED}  ✗ Qdrant collection empty or missing${NC}"
    FAIL=$((FAIL+1))
fi

# ==============================================================================
# CODING AGENT TEST
# ==============================================================================
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  CODING AGENT${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo -e "${YELLOW}[7/10] Coding agent creates JSON...${NC}"
# Find latest OCR JSON
LATEST_OCR=$(ls -t "$ERP_AI_DIR/data/processed/sample_invoice"*.json 2>/dev/null | head -1)

if [ -n "$LATEST_OCR" ]; then
    CODING_RESULT=$(timeout 120 python3 << EOF
import sys
sys.path.insert(0, '/root/erp-ai')
from agents.accounting_coding.coding_agent import AccountingCodingAgent
agent = AccountingCodingAgent(use_llm=True)
result = agent.process('$LATEST_OCR')
entries = result.get('suggested_entries', [])
output = result.get('output_file', '')
if entries and output:
    print(f"OK:{len(entries)}")
else:
    print("FAIL")
EOF
2>/dev/null)
    
    if [[ "$CODING_RESULT" == OK* ]]; then
        ENTRIES_COUNT=$(echo "$CODING_RESULT" | cut -d: -f2)
        echo -e "${GREEN}  ✓ Coding agent OK ($ENTRIES_COUNT entries)${NC}"
        PASS=$((PASS+1))
    else
        echo -e "${RED}  ✗ Coding agent failed${NC}"
        FAIL=$((FAIL+1))
    fi
else
    echo -e "${RED}  ✗ No OCR JSON found${NC}"
    FAIL=$((FAIL+1))
fi

# ==============================================================================
# GUARDRAILS TEST
# ==============================================================================
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  FINANCIAL GUARDRAILS${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

LATEST_CODING=$(ls -t "$ERP_AI_DIR/data/processed/coding_"*.json 2>/dev/null | head -1)

echo -e "${YELLOW}[8/10] Guardrail: 511 == TOTAL...${NC}"
if [ -n "$LATEST_CODING" ]; then
    CHECK_511=$(timeout 10 python3 << EOF
import json
with open('$LATEST_CODING') as f:
    d = json.load(f)
total = d.get('total', 0) or 0
entries = d.get('suggested_entries', [])
sum_511 = sum(e.get('amount', 0) for e in entries if str(e.get('credit_account')) == '511')
if total > 0 and sum_511 == total:
    print(f"OK:{sum_511}")
elif total == 0:
    print(f"OK:{sum_511}")
else:
    print(f"FAIL:{sum_511}!={total}")
EOF
2>/dev/null)
    
    if [[ "$CHECK_511" == OK* ]]; then
        AMT_511=$(echo "$CHECK_511" | cut -d: -f2)
        echo -e "${GREEN}  ✓ 511 = TOTAL (${AMT_511})${NC}"
        PASS=$((PASS+1))
    else
        echo -e "${RED}  ✗ 511 != TOTAL ($CHECK_511)${NC}"
        FAIL=$((FAIL+1))
    fi
else
    echo -e "${RED}  ✗ No coding JSON found${NC}"
    FAIL=$((FAIL+1))
fi

echo -e "${YELLOW}[9/10] Guardrail: 3331 == VAT...${NC}"
if [ -n "$LATEST_CODING" ]; then
    CHECK_3331=$(timeout 10 python3 << EOF
import json
with open('$LATEST_CODING') as f:
    d = json.load(f)
vat = d.get('vat', 0) or 0
entries = d.get('suggested_entries', [])
sum_3331 = sum(e.get('amount', 0) for e in entries if str(e.get('credit_account')) == '3331')
if vat > 0 and sum_3331 == vat:
    print(f"OK:{sum_3331}")
elif vat == 0:
    print(f"OK:{sum_3331}")
else:
    print(f"FAIL:{sum_3331}!={vat}")
EOF
2>/dev/null)
    
    if [[ "$CHECK_3331" == OK* ]]; then
        AMT_3331=$(echo "$CHECK_3331" | cut -d: -f2)
        echo -e "${GREEN}  ✓ 3331 = VAT (${AMT_3331})${NC}"
        PASS=$((PASS+1))
    else
        echo -e "${RED}  ✗ 3331 != VAT ($CHECK_3331)${NC}"
        FAIL=$((FAIL+1))
    fi
else
    echo -e "${RED}  ✗ No coding JSON found${NC}"
    FAIL=$((FAIL+1))
fi

# ==============================================================================
# ORCHESTRATOR TEST
# ==============================================================================
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  ORCHESTRATOR${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo -e "${YELLOW}[10/10] LangGraph orchestrator E2E...${NC}"
ORCH_RESULT=$(timeout 300 bash "$ERP_AI_DIR/scripts/run_e2e_demo.sh" "$ERP_AI_DIR/data/uploads/sample_invoice.png" > /tmp/orch_out.txt 2>&1 && echo "OK" || echo "FAIL")

if [ "$ORCH_RESULT" == "OK" ]; then
    echo -e "${GREEN}  ✓ Orchestrator E2E OK${NC}"
    PASS=$((PASS+1))
else
    echo -e "${RED}  ✗ Orchestrator E2E failed${NC}"
    FAIL=$((FAIL+1))
fi

# ==============================================================================
# SUMMARY
# ==============================================================================
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗"
echo -e "║                    VERIFICATION SUMMARY                      ║"
echo -e "╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Passed: ${GREEN}$PASS${NC} / 10"
echo -e "  Failed: ${RED}$FAIL${NC} / 10"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗"
    echo -e "║          ✓ MVP SMOKE TEST PASSED - ALL OK                   ║"
    echo -e "╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    # Final summary
    FINAL_CODING=$(ls -t "$ERP_AI_DIR/data/processed/coding_"*.json 2>/dev/null | head -1)
    if [ -n "$FINAL_CODING" ]; then
        echo -e "${YELLOW}Latest Output:${NC} $FINAL_CODING"
        echo ""
        python3 << EOF
import json
with open('$FINAL_CODING') as f:
    d = json.load(f)
entries = d.get('suggested_entries', [])
sum_511 = sum(e.get('amount', 0) for e in entries if str(e.get('credit_account')) == '511')
sum_3331 = sum(e.get('amount', 0) for e in entries if str(e.get('credit_account')) == '3331')
print(f"  Invoice:     {d.get('invoice_no', 'N/A')}")
print(f"  Entries:     {len(entries)}")
print(f"  Revenue:     {sum_511:,.0f} VND")
print(f"  VAT:         {sum_3331:,.0f} VND")
print(f"  Evidence:    {len(d.get('evidence', []))}")
print(f"  Corrections: {len(d.get('corrections', []))}")
EOF
    fi
    
    exit 0
else
    echo -e "${RED}╔══════════════════════════════════════════════════════════════╗"
    echo -e "║          ✗ MVP SMOKE TEST FAILED                            ║"
    echo -e "╚══════════════════════════════════════════════════════════════╝${NC}"
    exit 1
fi
