
import asyncio
import time
import sys
import os
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import routes
from core.schemas import ReconcileRequest, BankTransaction

# Mock Copilot
class MockCopilot:
    def __init__(self, tenant_id=None, mode=None):
        self.tenant_id = tenant_id

    def process(self, structured_fields, bank_txns=None, ocr_text=None, file_metadata=None, doc_id=None):
        # Simulate blocking work
        time.sleep(0.1)
        return {
            "reconciliation_result": {
                "matched": [],
                "unmatched_invoices": [structured_fields.get("doc_id")],
                "unmatched_bank_txns": []
            }
        }

# Patch the Copilot in routes
routes.ERPXAccountingCopilot = MockCopilot

async def run_benchmark():
    # Setup request
    request = MagicMock()
    request.state.request_id = "test-req-id"
    request.state.tenant_id = "test-tenant"

    # Setup payload
    invoices = [{"doc_id": f"INV-{i}"} for i in range(5)]
    bank_txns = [
        BankTransaction(txn_id=f"TXN-{i}", txn_date="2024-01-01", amount=100.0)
        for i in range(5)
    ]

    reconcile_request = ReconcileRequest(
        invoices=invoices,
        bank_txns=bank_txns,
        tolerance_percent=0.5,
        tolerance_amount=50000,
        date_window_days=7
    )

    print("Starting benchmark with 5 invoices (0.1s delay each)...")
    start_time = time.time()

    response = await routes.reconcile_transactions(request, reconcile_request)

    end_time = time.time()
    duration = end_time - start_time

    print(f"Total duration: {duration:.4f}s")

    # Assertions
    if duration < 0.2:
        print(f"✅ Optimization confirmed: Parallel execution detected ({duration:.4f}s < 0.2s)")
    else:
        print(f"❌ Too slow: {duration:.4f}s (Expected < 0.2s)")

    return duration

if __name__ == "__main__":
    asyncio.run(run_benchmark())
