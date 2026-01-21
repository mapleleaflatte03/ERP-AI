#!/bin/bash
# PHASE C Verification Script
# Checks: BGE-M3 model, Qdrant collection, points, search

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ERP_AI_DIR="/root/erp-ai"
VENV_DIR="$ERP_AI_DIR/venv"

echo "=============================================="
echo "  PHASE C VERIFICATION"
echo "=============================================="

PASS=0
FAIL=0

# Test 1: BGE-M3 Model Load
echo ""
echo -e "${YELLOW}[Test 1] BGE-M3 Model Load...${NC}"
cd "$ERP_AI_DIR"
source "$VENV_DIR/bin/activate"
export CUDA_VISIBLE_DEVICES=""

if python -c "from FlagEmbedding import BGEM3FlagModel; print('OK')" 2>/dev/null; then
    echo -e "${GREEN}✓ BGE-M3 import OK${NC}"
    ((PASS++))
else
    echo -e "${RED}✗ BGE-M3 import FAILED${NC}"
    ((FAIL++))
fi

# Test 2: Collection Exists
echo ""
echo -e "${YELLOW}[Test 2] Qdrant Collection Exists...${NC}"
COLLECTION_STATUS=$(curl -s http://localhost:6333/collections/erp_ai_docs | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','error'))" 2>/dev/null)

if [ "$COLLECTION_STATUS" == "ok" ]; then
    echo -e "${GREEN}✓ Collection erp_ai_docs exists${NC}"
    ((PASS++))
else
    echo -e "${RED}✗ Collection not found${NC}"
    ((FAIL++))
fi

# Test 3: Point Count > 0
echo ""
echo -e "${YELLOW}[Test 3] Point Count > 0...${NC}"
POINT_COUNT=$(curl -s http://localhost:6333/collections/erp_ai_docs | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('result',{}).get('points_count',0))" 2>/dev/null)

if [ "$POINT_COUNT" -gt 0 ] 2>/dev/null; then
    echo -e "${GREEN}✓ Point count: $POINT_COUNT${NC}"
    ((PASS++))
else
    echo -e "${RED}✗ Point count is 0 or error${NC}"
    ((FAIL++))
fi

# Test 4: Search Returns Results
echo ""
echo -e "${YELLOW}[Test 4] Search Query Returns Results...${NC}"
SEARCH_RESULT=$(python scripts/query_qdrant_demo.py "invoice" 2>&1 | grep -c "Result 1" || true)

if [ "$SEARCH_RESULT" -gt 0 ]; then
    echo -e "${GREEN}✓ Search returns results${NC}"
    ((PASS++))
else
    echo -e "${RED}✗ Search returned no results${NC}"
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
    echo -e "${GREEN}✓ PHASE C VERIFIED OK${NC}"
    echo ""
    echo "=============================================="
    echo "  FINAL STATS"
    echo "=============================================="
    echo "Point Count: $POINT_COUNT"
    echo ""
    echo "Collection Info:"
    curl -s http://localhost:6333/collections/erp_ai_docs | python3 -m json.tool | head -20
    exit 0
else
    echo -e "${RED}✗ PHASE C VERIFICATION FAILED${NC}"
    exit 1
fi
