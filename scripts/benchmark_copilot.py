#!/usr/bin/env python3
"""
Benchmark for ERPXAccountingCopilot Instantiation
=================================================
Measures the performance impact of creating a new service instance per request
vs using a cached factory.

Usage:
    python scripts/benchmark_copilot.py
"""

import time
import sys
from functools import lru_cache
from unittest.mock import MagicMock

# -----------------------------------------------------------------------------
# Setup Mocks for Missing Dependencies
# -----------------------------------------------------------------------------

# Mock the ERPXAccountingCopilot class in sys.modules so api.routes can import it
mock_copilot_module = MagicMock()
class MockERPXAccountingCopilot:
    def __init__(self, mode: str = "STRICT", tenant_id: str | None = None):
        # Simulate expensive initialization (e.g., loading config, DB connection)
        time.sleep(0.05)
        self.mode = mode
        self.tenant_id = tenant_id

    def process(self, *args, **kwargs):
        # Simulate processing
        return {"status": "success", "mode": self.mode, "tenant": self.tenant_id}

mock_copilot_module.ERPXAccountingCopilot = MockERPXAccountingCopilot
sys.modules["agents.accounting_coding.erpx_copilot"] = mock_copilot_module

# Now import the actual code to test
try:
    import api.routes
except ImportError:
    # If imports fail due to other deps, we fall back to local definition for demo
    print("Warning: Could not import api.routes, running in simulation mode")
    api = None

# -----------------------------------------------------------------------------
# Approach 1: Current Implementation Simulation (New Instance Per Request)
# -----------------------------------------------------------------------------

def process_request_current(mode: str, tenant_id: str):
    # Mimic old logic: copilot = ERPXAccountingCopilot(...)
    copilot = MockERPXAccountingCopilot(mode=mode, tenant_id=tenant_id)
    return copilot.process()

# -----------------------------------------------------------------------------
# Approach 2: Optimized Implementation (Actual Code)
# -----------------------------------------------------------------------------

def process_request_optimized(mode: str, tenant_id: str):
    if api:
        # Use the actual factory from the code
        copilot = api.routes.get_copilot_instance(mode=mode, tenant_id=tenant_id)
        return copilot.process()
    else:
        # Fallback simulation
        return process_request_current(mode, tenant_id)

# -----------------------------------------------------------------------------
# Benchmark Runner
# -----------------------------------------------------------------------------

def run_benchmark():
    ITERATIONS = 50
    TENANTS = ["tenant_a", "tenant_b", "tenant_c"]
    MODES = ["STRICT", "RELAXED"]

    print(f"Running benchmark with {ITERATIONS} iterations per tenant/mode combination...")
    print(f"Simulated Init Latency: 50ms")
    print("-" * 60)

    # Measure Current Approach
    start_time = time.time()
    for i in range(ITERATIONS):
        for tenant in TENANTS:
            for mode in MODES:
                process_request_current(mode, tenant)
    end_time = time.time()
    total_time_current = end_time - start_time
    avg_time_current = (total_time_current / (ITERATIONS * len(TENANTS) * len(MODES))) * 1000

    print(f"Current Approach (New Instance):")
    print(f"  Total Time: {total_time_current:.4f}s")
    print(f"  Avg Latency per Request: {avg_time_current:.2f}ms")

    # Measure Optimized Approach
    if api:
        # Warmup cache
        api.routes.get_copilot_instance.cache_clear()

    start_time = time.time()
    for i in range(ITERATIONS):
        for tenant in TENANTS:
            for mode in MODES:
                process_request_optimized(mode, tenant)
    end_time = time.time()
    total_time_optimized = end_time - start_time
    avg_time_optimized = (total_time_optimized / (ITERATIONS * len(TENANTS) * len(MODES))) * 1000

    print("-" * 60)
    print(f"Optimized Approach (Cached Factory):")
    print(f"  Total Time: {total_time_optimized:.4f}s")
    print(f"  Avg Latency per Request: {avg_time_optimized:.2f}ms")

    # Calculate Improvement
    if total_time_optimized > 0:
        speedup = total_time_current / total_time_optimized
        print("-" * 60)
        print(f"SPEEDUP: {speedup:.2f}x")

    print("-" * 60)

if __name__ == "__main__":
    run_benchmark()
