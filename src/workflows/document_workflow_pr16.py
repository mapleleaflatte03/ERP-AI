"""
ERPX AI - Document Processing Workflow (PR16)
==============================================
Temporal workflow that processes documents via worker.
Reuses existing pipeline logic from API.
"""

import logging
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

# Import activity reference for type checking only
# Actual activity is executed by name
with workflow.unsafe.imports_passed_through():
    from src.workflows.activities_pr16 import process_job_activity

logger = logging.getLogger("erpx.workflows.pr16")


@workflow.defn
class DocumentWorkflowPR16:
    """
    Document processing workflow (PR16).

    Workflow:
    1. Execute process_job_activity with the job_id
    2. Activity downloads from MinIO, runs full pipeline, updates DB
    3. Returns terminal state (completed/waiting_for_approval/failed)
    """

    @workflow.run
    async def run(self, job_id: str) -> str:
        """
        Run document processing workflow.

        Args:
            job_id: The job ID to process

        Returns:
            Terminal state string
        """
        workflow.logger.info(f"[{job_id}] DocumentWorkflowPR16 starting")

        # Execute the processing activity with retry policy
        result = await workflow.execute_activity(
            process_job_activity,
            job_id,
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=5),
                backoff_coefficient=2.0,
                maximum_interval=timedelta(minutes=1),
                maximum_attempts=3,
            ),
        )

        workflow.logger.info(f"[{job_id}] DocumentWorkflowPR16 completed: {result}")

        return result
