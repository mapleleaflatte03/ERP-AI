#!/bin/bash
# =============================================================================
# test_local.sh - Local Test Runner for Module-Agent + Quantum UI
# 
# Usage:
#   ./test_local.sh          # Run all tests
#   ./test_local.sh backend  # Run backend tests only
#   ./test_local.sh frontend # Run frontend tests only
#   ./test_local.sh e2e      # Run Playwright E2E tests only
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  ERP-AI Module-Agent + Quantum UI - Local Test Runner          ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Track test results
BACKEND_RESULT=0
FRONTEND_RESULT=0
E2E_RESULT=0

# Function to run backend tests
run_backend_tests() {
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}  Running Backend Tests (pytest)                               ${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    # Activate virtual environment if it exists
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    elif [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    fi
    
    # Install test dependencies
    echo -e "${BLUE}Installing test dependencies...${NC}"
    pip install -q pytest pytest-asyncio pytest-cov aiohttp || true
    
    # Run pytest with coverage
    echo -e "${BLUE}Running pytest...${NC}"
    python -m pytest tests/test_action_proposals.py \
        -v \
        --tb=short \
        --cov=src/services \
        --cov-report=term-missing \
        --cov-fail-under=70 \
        || BACKEND_RESULT=$?
    
    if [ $BACKEND_RESULT -eq 0 ]; then
        echo -e "${GREEN}✓ Backend tests PASSED${NC}"
    else
        echo -e "${RED}✗ Backend tests FAILED${NC}"
    fi
    echo ""
}

# Function to run frontend tests
run_frontend_tests() {
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}  Running Frontend Tests (vitest)                              ${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    cd ui
    
    # Install dependencies if needed
    if [ ! -d "node_modules" ]; then
        echo -e "${BLUE}Installing npm dependencies...${NC}"
        npm install
    fi
    
    # Run vitest
    echo -e "${BLUE}Running vitest...${NC}"
    npm run test -- --run \
        --reporter=verbose \
        --coverage \
        || FRONTEND_RESULT=$?
    
    cd ..
    
    if [ $FRONTEND_RESULT -eq 0 ]; then
        echo -e "${GREEN}✓ Frontend tests PASSED${NC}"
    else
        echo -e "${RED}✗ Frontend tests FAILED${NC}"
    fi
    echo ""
}

# Function to run E2E tests
run_e2e_tests() {
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}  Running E2E Tests (Playwright)                               ${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    cd ui
    
    # Install Playwright browsers if needed
    if [ ! -d "node_modules/.cache/ms-playwright" ]; then
        echo -e "${BLUE}Installing Playwright browsers...${NC}"
        npx playwright install chromium
    fi
    
    # Check if services are running
    echo -e "${BLUE}Checking if services are running...${NC}"
    
    if ! curl -s http://localhost:3000 > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠ Frontend not running on localhost:3000${NC}"
        echo -e "${YELLOW}  Starting frontend dev server...${NC}"
        npm run dev &
        FRONTEND_PID=$!
        sleep 10  # Wait for server to start
    fi
    
    if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠ Backend not running on localhost:8000${NC}"
        echo -e "${YELLOW}  Please start backend manually or use docker-compose${NC}"
        E2E_RESULT=1
        cd ..
        return
    fi
    
    # Run Playwright tests
    echo -e "${BLUE}Running Playwright E2E tests...${NC}"
    npx playwright test e2e/module-agent-flow.spec.ts \
        --reporter=html \
        --project=chromium \
        || E2E_RESULT=$?
    
    # Kill frontend if we started it
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    
    cd ..
    
    if [ $E2E_RESULT -eq 0 ]; then
        echo -e "${GREEN}✓ E2E tests PASSED${NC}"
    else
        echo -e "${RED}✗ E2E tests FAILED${NC}"
    fi
    echo ""
}

# Function to print summary
print_summary() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  TEST SUMMARY                                                  ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    local total_failed=0
    
    if [ $BACKEND_RESULT -eq 0 ]; then
        echo -e "  ${GREEN}✓${NC} Backend Tests:   PASSED"
    else
        echo -e "  ${RED}✗${NC} Backend Tests:   FAILED"
        ((total_failed++))
    fi
    
    if [ $FRONTEND_RESULT -eq 0 ]; then
        echo -e "  ${GREEN}✓${NC} Frontend Tests:  PASSED"
    else
        echo -e "  ${RED}✗${NC} Frontend Tests:  FAILED"
        ((total_failed++))
    fi
    
    if [ $E2E_RESULT -eq 0 ]; then
        echo -e "  ${GREEN}✓${NC} E2E Tests:       PASSED"
    else
        echo -e "  ${RED}✗${NC} E2E Tests:       FAILED"
        ((total_failed++))
    fi
    
    echo ""
    
    if [ $total_failed -eq 0 ]; then
        echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
        echo -e "${GREEN}  ALL TESTS PASSED! ✓                                          ${NC}"
        echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
        return 0
    else
        echo -e "${RED}════════════════════════════════════════════════════════════════${NC}"
        echo -e "${RED}  $total_failed TEST SUITE(S) FAILED ✗                          ${NC}"
        echo -e "${RED}════════════════════════════════════════════════════════════════${NC}"
        return 1
    fi
}

# Main execution
case "${1:-all}" in
    backend)
        run_backend_tests
        ;;
    frontend)
        run_frontend_tests
        ;;
    e2e)
        run_e2e_tests
        ;;
    all)
        run_backend_tests
        run_frontend_tests
        run_e2e_tests
        print_summary
        ;;
    *)
        echo "Usage: $0 [backend|frontend|e2e|all]"
        exit 1
        ;;
esac

# Exit with appropriate code
if [ $BACKEND_RESULT -ne 0 ] || [ $FRONTEND_RESULT -ne 0 ] || [ $E2E_RESULT -ne 0 ]; then
    exit 1
fi
exit 0
