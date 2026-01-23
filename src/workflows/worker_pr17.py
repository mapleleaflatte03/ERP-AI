"""
ERPX AI - Temporal Worker (PR17)
================================
Worker with human-in-the-loop approval support.
Registers PR17 workflow and finalize activities.
"""

import asyncio
import logging
import sys

# Setup path
sys.path.insert(0, "/root/erp-ai")

from src.core import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("erpx.worker.pr17")


async def run_worker():
    """Run the Temporal worker with PR17 workflow and activities."""
    from temporalio.worker import Worker
    
    from src.workflows.activities_pr16 import process_job_activity
    from src.workflows.activities_pr17 import (
        finalize_posting_activity,
        finalize_rejection_activity,
    )
    from src.workflows.document_workflow_pr17 import DocumentWorkflowPR17
    from src.workflows.temporal_client import get_temporal_client
    
    logger.info("=" * 60)
    logger.info("ERPX AI - Temporal Worker (PR17) starting...")
    logger.info(f"  TEMPORAL_ADDRESS: {config.TEMPORAL_ADDRESS}")
    logger.info(f"  TEMPORAL_NAMESPACE: {config.TEMPORAL_NAMESPACE}")
    logger.info(f"  TEMPORAL_TASK_QUEUE: {config.TEMPORAL_TASK_QUEUE}")
    logger.info("=" * 60)
    
    client = await get_temporal_client()
    
    worker = Worker(
        client,
        task_queue=config.TEMPORAL_TASK_QUEUE,
        workflows=[DocumentWorkflowPR17],
        activities=[
            process_job_activity,
            finalize_posting_activity,
            finalize_rejection_activity,
        ],
    )
    
    logger.info(f"Worker connected and listening on task queue: {config.TEMPORAL_TASK_QUEUE}")
    logger.info("Registered workflows: DocumentWorkflowPR17")
    logger.info("Registered activities: process_job_activity, finalize_posting_activity, finalize_rejection_activity")
    
    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_worker())
