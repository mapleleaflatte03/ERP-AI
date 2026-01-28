import asyncio
import os
import sys
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock dependencies that might cause import issues or runtime errors
sys.modules["src.workflows.temporal_client"] = MagicMock()
sys.modules["src.storage"] = MagicMock()
sys.modules["src.rag"] = MagicMock()
sys.modules["src.llm"] = MagicMock()

# Now import the target function
from src.api.main import persist_to_db_with_conn

# Configuration
NUM_ENTRIES = 100
LATENCY_MS = 0.5  # Simulated network latency per DB call


class MockConnection:
    def __init__(self):
        self.execute_count = 0
        self.executemany_count = 0

    async def execute(self, query, *args):
        self.execute_count += 1
        await asyncio.sleep(LATENCY_MS / 1000)
        return "INSERT 0 1"

    async def executemany(self, query, args):
        self.executemany_count += 1
        await asyncio.sleep(LATENCY_MS / 1000)
        return "INSERT 0 100"

    async def fetchrow(self, query, *args):
        await asyncio.sleep(LATENCY_MS / 1000)
        # Mock tenant check or existing ledger check
        if "FROM tenants" in query:
            return {"id": uuid.uuid4()}
        if "FROM ledger_entries" in query:
            return None  # No existing ledger
        return None

    async def fetch(self, query, *args):
        await asyncio.sleep(LATENCY_MS / 1000)
        return []

    def transaction(self):
        return MagicMock(__aenter__=AsyncMock(), __aexit__=AsyncMock())


async def run_benchmark():
    print(f"Benchmark: Persisting proposal with {NUM_ENTRIES} entries")
    print(f"Simulated DB Latency: {LATENCY_MS}ms per call")

    job_id = str(uuid.uuid4())
    file_info = {"filename": "test.pdf", "tenant_id": "test_tenant"}

    entries = []
    for i in range(NUM_ENTRIES):
        entries.append(
            {
                "account_code": f"111{i}",
                "account_name": "Cash",
                "debit": 10.0,
                "credit": 0.0,
                "description": f"Entry {i}",
            }
        )

    proposal = {
        "invoice_date": "2023-01-01",
        "vendor": "Test Vendor",
        "invoice_no": "INV-123",
        "total_amount": 1000.0,
        "confidence": 0.9,
        "entries": entries,
    }

    mock_conn = MockConnection()

    start_time = time.time()

    # We pass the mock connection directly
    result = await persist_to_db_with_conn(
        conn=mock_conn,
        job_id=job_id,
        file_info=file_info,
        proposal=proposal,
        tenant_id_str="test_tenant",
        request_id="req-123",
    )

    end_time = time.time()
    duration = end_time - start_time

    print("\nResults:")
    print(f"  Time taken: {duration:.4f} seconds")
    print(f"  Execute calls: {mock_conn.execute_count}")
    print(f"  Executemany calls: {mock_conn.executemany_count}")

    # Expected calls:
    # 1. Tenant check (fetchrow) -> not execute
    # 2. Insert Document (execute)
    # 3. Insert Invoice (execute)
    # 4. Insert Proposal (execute)
    # 5. Insert Entries (loop -> NUM_ENTRIES * execute)
    # 6. Insert Approval (execute)
    # 7. Update Proposal Status (execute)
    # 8. Insert Ledger Entry (execute)
    # 9. Insert Ledger Lines (loop -> NUM_ENTRIES * execute)

    # Total expected execute = 1 + 1 + 1 + N + 1 + 1 + 1 + N = 6 + 2N
    # With N=100 -> 206 calls

    expected = 6 + 2 * NUM_ENTRIES
    print(f"  Expected baseline execute count: ~{expected}")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
