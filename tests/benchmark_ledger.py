
import asyncio
import time
import uuid
import sys
import os
from unittest.mock import MagicMock, AsyncMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db import post_ledger_entry

# Configuration
NUM_ENTRIES = 1000
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
        await asyncio.sleep(LATENCY_MS / 1000) # Bulk also takes one round trip (roughly)
        return "INSERT 0 1"

    async def fetchrow(self, query, *args):
        await asyncio.sleep(LATENCY_MS / 1000)
        return None

    async def fetch(self, query, *args):
        await asyncio.sleep(LATENCY_MS / 1000)
        return []

    def transaction(self):
        return MagicMock(__aenter__=AsyncMock(), __aexit__=AsyncMock())

class MockPool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return MagicMock(__aenter__=AsyncMock(return_value=self.conn), __aexit__=AsyncMock())

async def run_benchmark():
    print(f"Benchmark: Inserting {NUM_ENTRIES} ledger entries")
    print(f"Simulated DB Latency: {LATENCY_MS}ms per call")

    # Generate test data
    entries = []
    for i in range(NUM_ENTRIES):
        entries.append({
            "account_code": "111",
            "account_name": "Cash",
            "debit": 10.0,
            "credit": 0.0,
            "description": f"Test entry {i}"
        })
    # Add balancing entry (though logic checks it, we mock execution so it might not matter,
    # but let's be safe if logic checks sums before DB)
    # The current logic checks sum inside post_ledger_entry:
    # total_debit = sum(e.get("debit", 0) for e in entries)
    # total_credit = sum(e.get("credit", 0) for e in entries)
    # So I need to make sure it's balanced or I disable the check.
    # Actually, let's just make it balanced.

    entries = []
    for i in range(NUM_ENTRIES // 2):
        entries.append({
            "account_code": "111",
            "debit": 100.0,
            "credit": 0.0,
            "description": f"Debit {i}"
        })
        entries.append({
            "account_code": "222",
            "debit": 0.0,
            "credit": 100.0,
            "description": f"Credit {i}"
        })

    mock_conn = MockConnection()

    # We need to mock get_connection.
    # src.db.get_connection is an asynccontextmanager.

    start_time = time.time()

    with patch("src.db.get_connection") as mock_get_conn:
        # Configure the mock to behave like an async context manager that yields mock_conn
        mock_ctx = MagicMock()
        mock_ctx.__aenter__.return_value = mock_conn
        mock_ctx.__aexit__.return_value = None
        mock_get_conn.return_value = mock_ctx

        await post_ledger_entry(
            job_id="job-123",
            proposal_id="prop-123",
            entries=entries,
            description="Benchmark Transaction"
        )

    end_time = time.time()
    duration = end_time - start_time

    print(f"\nResults:")
    print(f"  Time taken: {duration:.4f} seconds")
    print(f"  Execute calls: {mock_conn.execute_count}")
    print(f"  Executemany calls: {mock_conn.executemany_count}")
    print(f"  Throughput: {NUM_ENTRIES / duration:.2f} lines/sec")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
