
import asyncio
import time
import sys
from unittest.mock import MagicMock

# --- MOCKS START ---
# (Same mocks as before)
sys.modules["fastapi"] = MagicMock()
sys.modules["fastapi.middleware.cors"] = MagicMock()
sys.modules["fastapi.responses"] = MagicMock()
sys.modules["pydantic"] = MagicMock()
sys.modules["uvicorn"] = MagicMock()
sys.modules["asyncpg"] = MagicMock()
sys.modules["opentelemetry"] = MagicMock()
sys.modules["opentelemetry.trace"] = MagicMock()
sys.modules["opentelemetry.exporter.otlp.proto.grpc.trace_exporter"] = MagicMock()
sys.modules["opentelemetry.instrumentation.fastapi"] = MagicMock()
sys.modules["opentelemetry.instrumentation.httpx"] = MagicMock()
sys.modules["opentelemetry.sdk.resources"] = MagicMock()
sys.modules["opentelemetry.sdk.trace"] = MagicMock()
sys.modules["opentelemetry.sdk.trace.export"] = MagicMock()

sys.modules["src.api.document_routes"] = MagicMock()
sys.modules["src.api.logging_config"] = MagicMock()
sys.modules["src.api.middleware"] = MagicMock()
sys.modules["src.approval.service"] = MagicMock()
sys.modules["src.audit.store"] = MagicMock()
sys.modules["src.core"] = MagicMock()
sys.modules["src.core.config"] = MagicMock()
sys.modules["src.datazones"] = MagicMock()
sys.modules["src.observability"] = MagicMock()
sys.modules["src.outbox"] = MagicMock()
sys.modules["src.policy.engine"] = MagicMock()
sys.modules["src.schemas.llm_output"] = MagicMock()
sys.modules["src.storage"] = MagicMock()
sys.modules["src.workflows.temporal_client"] = MagicMock()
sys.modules["src.llm"] = MagicMock()
sys.modules["src.rag"] = MagicMock()
sys.modules["src.db"] = MagicMock()
sys.modules["src.notifications"] = MagicMock()
sys.modules["src.processing"] = MagicMock()

class MockBaseModel:
    pass
sys.modules["pydantic"].BaseModel = MockBaseModel

class MockFastAPI:
    def __init__(self, **kwargs):
        pass
    def add_middleware(self, *args, **kwargs):
        pass
    def include_router(self, *args, **kwargs):
        pass
    def get(self, *args, **kwargs):
        return lambda x: x
    def post(self, *args, **kwargs):
        return lambda x: x
sys.modules["fastapi"].FastAPI = MockFastAPI

mock_pdfplumber = MagicMock()
mock_pdf = MagicMock()
mock_page = MagicMock()

def blocking_extract(*args, **kwargs):
    time.sleep(1.0)
    return "extracted text " * 10

mock_page.extract_text.side_effect = blocking_extract
mock_pdf.pages = [mock_page]
mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

sys.modules["pdfplumber"] = mock_pdfplumber
sys.modules["pytesseract"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["pandas"] = MagicMock()

# --- MOCKS END ---

sys.path.insert(0, ".")

try:
    from src.api.main import extract_pdf
    print("Successfully imported extract_pdf from src.api.main")
except ImportError as e:
    print(f"Failed to import: {e}")
    sys.exit(1)

heartbeat_start_time = 0

async def monitor_heartbeat():
    """Monitor event loop lag"""
    global heartbeat_start_time
    heartbeat_start_time = time.time()
    print(f"Heartbeat started at {heartbeat_start_time}")

    last_time = heartbeat_start_time
    lags = []
    # Monitor for 2 seconds
    for _ in range(20):
        await asyncio.sleep(0.1)
        now = time.time()
        lag = now - last_time - 0.1
        lags.append(lag)
        last_time = now

    max_lag = max(lags) if lags else 0
    print(f"Heartbeat finished. Max lag: {max_lag:.4f}s")
    return max_lag

async def run_test():
    print("Starting blocking test...")
    # Give the task a moment to be scheduled if we wanted, but create_task schedules it.
    # However, it won't run until we await something that yields.
    # extract_pdf is async, so `await extract_pdf` yields initially,
    # but if it doesn't await anything internally before doing blocking work, it will block.

    task_created_time = time.time()
    heartbeat_task = asyncio.create_task(monitor_heartbeat())

    # Run extraction
    print(f"Calling extract_pdf at {time.time()}")
    text = await extract_pdf("dummy.pdf")
    extract_end_time = time.time()
    print(f"Extraction finished at {extract_end_time}")

    # Wait for heartbeat to finish (it might be still running if we slept longer)
    # But for this test, we just check start time.

    # If heartbeat started AFTER extraction finished (or very close to it), it was blocked.
    # If it started BEFORE extraction finished, then they ran concurrently.

    # Actually, `create_task` schedules execution. The loop runs the task when it gets control.
    # When `await extract_pdf` is called, `extract_pdf` starts.
    # If `extract_pdf` is fully blocking, it won't yield to the loop until it's done.
    # So `monitor_heartbeat` will only start AFTER `extract_pdf` returns.

    if heartbeat_start_time == 0:
        # Heartbeat hasn't even started yet!
        # Let's await it to let it run
        await heartbeat_task

    # Now check timing
    print(f"Task created at: {task_created_time}")
    print(f"Heartbeat started at: {heartbeat_start_time}")
    print(f"Extraction finished at: {extract_end_time}")

    startup_delay = heartbeat_start_time - task_created_time
    print(f"Heartbeat startup delay: {startup_delay:.4f}s")

    if startup_delay > 0.5:
         print("FAIL: Event loop was blocked! Heartbeat couldn't start until extraction was done.")
    else:
         print("SUCCESS: Heartbeat started immediately.")

if __name__ == "__main__":
    asyncio.run(run_test())
