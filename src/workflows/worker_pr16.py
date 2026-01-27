"""
ERPX AI - Temporal Worker (PR16)
=================================
Runs the Temporal worker for document processing.
"""

import asyncio
import logging
import sys

sys.path.insert(0, "/root/erp-ai")

from temporalio.worker import Worker

from src.core import config
from src.workflows.activities_pr16 import process_job_activity
from src.workflows.document_workflow_pr16 import DocumentWorkflowPR16
from src.workflows.temporal_client import get_temporal_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("erpx.worker.pr16")


async def run_worker():
    """Run the Temporal worker."""
    logger.info("=" * 60)
    logger.info("ERPX AI - Temporal Worker (PR16) starting...")
    logger.info(f"  TEMPORAL_ADDRESS: {config.TEMPORAL_ADDRESS}")
    logger.info(f"  TEMPORAL_NAMESPACE: {config.TEMPORAL_NAMESPACE}")
    logger.info(f"  TEMPORAL_TASK_QUEUE: {config.TEMPORAL_TASK_QUEUE}")
    logger.info("=" * 60)

    # Connect to Temporal
    client = await get_temporal_client()

    # Create worker
    worker = Worker(
        client,
        task_queue=config.TEMPORAL_TASK_QUEUE,
        workflows=[DocumentWorkflowPR16],
        activities=[process_job_activity],
    )

    logger.info(f"Worker connected and listening on task queue: {config.TEMPORAL_TASK_QUEUE}")

    # Run worker
    await worker.run()


def main():
    """Entry point."""
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
