"""
ERPX AI - Temporal Client Helper (PR16)
=======================================
Singleton Temporal client for API and worker.
"""

import logging
from typing import Optional

from src.core import config

logger = logging.getLogger("erpx.temporal")

# Singleton client
_temporal_client = None


async def get_temporal_client():
    """
    Get singleton Temporal client.
    Connects to TEMPORAL_ADDRESS with TEMPORAL_NAMESPACE.
    """
    global _temporal_client

    if _temporal_client is not None:
        return _temporal_client

    try:
        from temporalio.client import Client

        _temporal_client = await Client.connect(
            config.TEMPORAL_ADDRESS,
            namespace=config.TEMPORAL_NAMESPACE,
        )

        logger.info(
            f"Temporal client connected: address={config.TEMPORAL_ADDRESS}, namespace={config.TEMPORAL_NAMESPACE}"
        )

        return _temporal_client

    except Exception as e:
        logger.error(f"Failed to connect to Temporal: {e}")
        raise


async def start_document_workflow(job_id: str) -> str:
    """
    Start a document processing workflow (PR17 with approval support).

    Args:
        job_id: The job ID (also used as workflow ID)

    Returns:
        workflow_id (same as job_id)
    """
    from src.workflows.document_workflow_pr17 import DocumentWorkflowPR17

    client = await get_temporal_client()

    handle = await client.start_workflow(
        DocumentWorkflowPR17.run,
        job_id,
        id=job_id,
        task_queue=config.TEMPORAL_TASK_QUEUE,
    )

    logger.info(f"[{job_id}] Temporal workflow started: workflow_id={handle.id}")

    return handle.id


async def signal_workflow_approval(job_id: str, action: str) -> dict:
    """
    Signal a workflow to approve or reject.

    Args:
        job_id: The workflow ID (same as job_id)
        action: "approve" or "reject"

    Returns:
        dict with signaled=True/False and message
    """
    from src.workflows.document_workflow_pr17 import DocumentWorkflowPR17

    try:
        client = await get_temporal_client()

        handle = client.get_workflow_handle(job_id)

        if action == "approve":
            await handle.signal(DocumentWorkflowPR17.signal_approve)
            logger.info(f"[{job_id}] Sent approval signal to workflow")
        elif action == "reject":
            await handle.signal(DocumentWorkflowPR17.signal_reject)
            logger.info(f"[{job_id}] Sent rejection signal to workflow")
        else:
            return {
                "signaled": False,
                "message": f"Invalid action: {action}. Must be 'approve' or 'reject'",
            }

        return {
            "signaled": True,
            "message": f"Signal '{action}' sent to workflow {job_id}",
        }

    except Exception as e:
        logger.warning(f"[{job_id}] Failed to signal workflow: {e}")
        return {
            "signaled": False,
            "message": f"Failed to signal workflow: {str(e)}",
        }
