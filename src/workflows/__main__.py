"""
ERPX AI Accounting - Workflows Package Entry Point
===================================================
Entry point for running the Temporal worker.
"""

import asyncio
import logging
import sys

sys.path.insert(0, "/root/erp-ai")

logging.basicConfig(level=logging.INFO)

from src.workflows.document_workflow import run_worker

if __name__ == "__main__":
    asyncio.run(run_worker())
