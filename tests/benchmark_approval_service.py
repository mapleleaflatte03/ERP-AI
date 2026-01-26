import asyncio
import time
import uuid
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.approval.service import post_to_ledger

# Configure logging to avoid polluting output
logging.basicConfig(level=logging.CRITICAL)

class MockRecord(dict):
    """Mocks an asyncpg Record object"""
    def __getattr__(self, name):
        if name in self:
            return self[name]
        raise AttributeError(f"MockRecord has no attribute {name}")

class MockConnection:
    def __init__(self, latency=0.001):
        self.latency = latency
        self.execute_count = 0
        self.executemany_count = 0
        self.fetch_count = 0
        self.fetchrow_count = 0
        self.executed_queries = []
        self.entries_to_return = []

    async def fetchrow(self, query, *args):
        self.fetchrow_count += 1
        await asyncio.sleep(self.latency)

        # Mocking specific queries based on content
        if "SELECT id FROM ledger_entries" in query:
            return None # Ledger entry does not exist

        if "SELECT jp.*" in query:
            return MockRecord({
                "tenant_id": uuid.uuid4(),
                "invoice_number": "INV-001",
                "vendor_name": "Test Vendor",
                "total_amount": 1000.00,
                "currency": "USD"
            })

        return None

    async def fetch(self, query, *args):
        self.fetch_count += 1
        await asyncio.sleep(self.latency)

        if "SELECT * FROM journal_proposal_entries" in query:
            # We will set the entries count dynamically in the test runner
            return self.entries_to_return

        return []

    async def execute(self, query, *args):
        self.execute_count += 1
        self.executed_queries.append((query, args))
        await asyncio.sleep(self.latency)

    async def executemany(self, query, args):
        self.executemany_count += 1
        self.executed_queries.append((query, args))
        await asyncio.sleep(self.latency)

async def run_benchmark(num_lines):
    conn = MockConnection(latency=0.001) # 1ms latency

    # Generate mock entries
    entries = []
    for i in range(num_lines):
        entries.append(MockRecord({
            "account_code": f"ACC-{i}",
            "account_name": f"Account {i}",
            "debit_amount": 100.0,
            "credit_amount": 0.0,
            "line_order": i
        }))

    conn.entries_to_return = entries

    start_time = time.time()
    await post_to_ledger(
        conn,
        proposal_id=str(uuid.uuid4()),
        approval_id=str(uuid.uuid4()),
        posted_by="benchmark_user"
    )
    end_time = time.time()

    duration = end_time - start_time
    print(f"Lines: {num_lines:<4} | Duration: {duration:.4f}s | Execute calls: {conn.execute_count:<4} | Executemany calls: {conn.executemany_count}")
    return duration, conn.execute_count, conn.executemany_count

async def main():
    print("--- Benchmark Start (Baseline) ---")
    await run_benchmark(50)
    await run_benchmark(200)
    print("--- Benchmark End ---")

if __name__ == "__main__":
    asyncio.run(main())
