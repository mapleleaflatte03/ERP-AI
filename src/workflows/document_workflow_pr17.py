"""
ERPX AI - Document Processing Workflow (PR17)
==============================================
Temporal workflow with human-in-the-loop approval support.
Waits for approval signal and resumes posting after approval.
"""

import logging
from datetime import timedelta
from typing import Any, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

# Import activity references with passthrough for non-deterministic imports
with workflow.unsafe.imports_passed_through():
    from src.workflows.activities_pr16 import process_job_activity
    from src.workflows.activities_pr17 import (
        finalize_posting_activity,
        finalize_rejection_activity,
    )

logger = logging.getLogger("erpx.workflows.pr17")


@workflow.defn
class DocumentWorkflowPR17:
    """
    Document processing workflow with human approval support (PR17).
    
    Workflow:
    1. Execute process_job_activity with the job_id
    2. If result is waiting_for_approval:
       - Wait for approval/rejection signal
       - Execute finalize activity based on signal
    3. Returns terminal state (completed/rejected/waiting_for_approval)
    """
    
    def __init__(self):
        self._approval_decision: Optional[str] = None  # "approve" or "reject"
    
    @workflow.signal
    async def signal_approve(self) -> None:
        """Signal to approve the pending job."""
        workflow.logger.info("Received approval signal")
        self._approval_decision = "approve"
    
    @workflow.signal
    async def signal_reject(self) -> None:
        """Signal to reject the pending job."""
        workflow.logger.info("Received rejection signal")
        self._approval_decision = "reject"
    
    @workflow.run
    async def run(self, job_id: str) -> str:
        """
        Run document processing workflow with approval support.
        
        Args:
            job_id: The job ID to process
            
        Returns:
            Terminal state string (completed/rejected/waiting_for_approval)
        """
        workflow.logger.info(f"[{job_id}] DocumentWorkflowPR17 starting")
        
        # Reset decision state
        self._approval_decision = None
        
        # Execute the initial processing activity
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
        
        workflow.logger.info(f"[{job_id}] Initial processing result: {result}")
        
        # If waiting for approval, wait for signal
        if result == "waiting_for_approval":
            workflow.logger.info(f"[{job_id}] Waiting for approval signal...")
            
            # Wait for signal (with long timeout - approvals can take days)
            await workflow.wait_condition(
                lambda: self._approval_decision is not None,
                timeout=timedelta(days=30),  # Max wait time for approval
            )
            
            if self._approval_decision == "approve":
                workflow.logger.info(f"[{job_id}] Processing approval...")
                
                # Execute finalize posting activity
                final_result = await workflow.execute_activity(
                    finalize_posting_activity,
                    job_id,
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=5),
                        backoff_coefficient=2.0,
                        maximum_interval=timedelta(minutes=1),
                        maximum_attempts=3,
                    ),
                )
                
                workflow.logger.info(f"[{job_id}] DocumentWorkflowPR17 completed: {final_result}")
                return final_result
                
            elif self._approval_decision == "reject":
                workflow.logger.info(f"[{job_id}] Processing rejection...")
                
                # Execute finalize rejection activity
                final_result = await workflow.execute_activity(
                    finalize_rejection_activity,
                    job_id,
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=5),
                        backoff_coefficient=2.0,
                        maximum_interval=timedelta(minutes=1),
                        maximum_attempts=3,
                    ),
                )
                
                workflow.logger.info(f"[{job_id}] DocumentWorkflowPR17 rejected: {final_result}")
                return final_result
            
            else:
                # Timeout waiting for approval
                workflow.logger.warning(f"[{job_id}] Approval timeout, staying at waiting_for_approval")
                return "waiting_for_approval"
        
        # Auto-approved or failed - return directly
        workflow.logger.info(f"[{job_id}] DocumentWorkflowPR17 completed: {result}")
        return result
