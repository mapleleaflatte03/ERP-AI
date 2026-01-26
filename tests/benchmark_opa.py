import asyncio
import time
import sys
import os
from unittest.mock import MagicMock, patch
import logging

# Configure logging to suppress output during benchmark
logging.basicConfig(level=logging.ERROR)

# Add repo root to path
sys.path.append(os.getcwd())

from src.orchestrator import pipeline

async def benchmark():
    # Patch dependencies
    with patch("src.processing.process_document") as mock_process, \
         patch("src.storage.download_document") as mock_download, \
         patch("src.rag.search_accounting_context") as mock_search, \
         patch("src.llm.get_llm_client") as mock_get_llm, \
         patch("httpx.AsyncClient") as mock_httpx_async_client: # Changed to AsyncClient

        # Setup fast mocks
        mock_download.return_value = b"fake content"

        mock_process_result = MagicMock()
        mock_process_result.success = True
        mock_process_result.document_text = "fake text"
        mock_process_result.key_fields = {}
        mock_process_result.tables = []
        mock_process.return_value = mock_process_result

        mock_search.return_value = []

        mock_llm = MagicMock()
        mock_llm_response = MagicMock()
        mock_llm_response.content = '{"invoice_summary": {}, "journal_entries": []}'
        mock_llm_response.latency_ms = 10
        mock_llm_response.request_id = "req-1"
        mock_llm.generate_sync.return_value = mock_llm_response
        mock_get_llm.return_value = mock_llm

        # Setup slow OPA mock (async)
        async def async_post(*args, **kwargs):
            await asyncio.sleep(0.5) # Non-blocking sleep
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"result": {"allow": True}}
            return resp

        # Mock the async context manager
        mock_client_instance = mock_httpx_async_client.return_value.__aenter__.return_value
        mock_client_instance.post.side_effect = async_post

        print(f"Running benchmark with 5 concurrent requests...")
        start_time = time.time()

        tasks = []
        for i in range(5):
            tasks.append(pipeline.process_document_pipeline(f"job-{i}", "comp-1", "doc-1"))

        await asyncio.gather(*tasks)

        end_time = time.time()
        duration = end_time - start_time
        print(f"Total time: {duration:.4f}s")

        # With blocking calls, 5 * 0.5s = 2.5s minimum
        # With async calls, should be closer to 0.5s (plus overhead)
        if duration > 2.0:
            print("Result: BLOCKING (Slow)")
        else:
            print("Result: NON-BLOCKING (Fast)")

if __name__ == "__main__":
    asyncio.run(benchmark())
