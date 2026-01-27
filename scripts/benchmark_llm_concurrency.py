import asyncio

# import httpx
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("benchmark")

# Config
N_REQUESTS = 10
LATENCY = 0.2  # 200ms

# ==============================================================================
# Simulation of Current State (Blocking)
# ==============================================================================


class BlockingLLMClient:
    def generate(self):
        # Simulate network delay with blocking sleep
        time.sleep(LATENCY)
        return "response"


async def run_blocking_benchmark():
    print(f"--- Benchmarking BLOCKING Sync Calls (N={N_REQUESTS}, Latency={LATENCY}s) ---")
    client = BlockingLLMClient()

    async def task():
        # In current code, async functions call the sync generate() directly
        client.generate()

    start = time.time()
    # This will run sequentially because the event loop is blocked by time.sleep
    await asyncio.gather(*[task() for _ in range(N_REQUESTS)])
    end = time.time()

    duration = end - start
    print(f"Total Time: {duration:.4f}s")
    print(f"Throughput: {N_REQUESTS / duration:.2f} req/s")
    if duration >= N_REQUESTS * LATENCY * 0.9:
        print("RESULT: BLOCKED (Serialized execution confirmed)")
    else:
        print("RESULT: UNEXPECTED (Did not block?)")
    return duration


# ==============================================================================
# Simulation of Optimized State (Async)
# ==============================================================================


class AsyncLLMClient:
    async def generate(self):
        # Simulate network delay with non-blocking sleep
        await asyncio.sleep(LATENCY)
        return "response"


async def run_async_benchmark():
    print(f"\n--- Benchmarking NON-BLOCKING Async Calls (N={N_REQUESTS}, Latency={LATENCY}s) ---")
    client = AsyncLLMClient()

    async def task():
        await client.generate()

    start = time.time()
    # This should run concurrently
    await asyncio.gather(*[task() for _ in range(N_REQUESTS)])
    end = time.time()

    duration = end - start
    print(f"Total Time: {duration:.4f}s")
    print(f"Throughput: {N_REQUESTS / duration:.2f} req/s")

    if duration < (LATENCY * 1.5):
        print("RESULT: CONCURRENT (Optimization verified)")
    else:
        print(f"RESULT: SLOW (Took longer than expected: {duration:.4f}s)")
    return duration


if __name__ == "__main__":
    print(f"Simulating {N_REQUESTS} concurrent LLM requests...")

    blocking_duration = asyncio.run(run_blocking_benchmark())
    async_duration = asyncio.run(run_async_benchmark())

    print("\nSummary:")
    print(f"Blocking: {blocking_duration:.4f}s")
    print(f"Async:    {async_duration:.4f}s")
    if async_duration > 0:
        speedup = blocking_duration / async_duration
        print(f"Speedup:  {speedup:.2f}x")
