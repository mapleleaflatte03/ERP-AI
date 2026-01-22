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
            f"Temporal client connected: address={config.TEMPORAL_ADDRESS}, "
            f"namespace={config.TEMPORAL_NAMESPACE}"
        )
        
        return _temporal_client
        
    except Exception as e:
        logger.error(f"Failed to connect to Temporal: {e}")
        raise


async def start_document_workflow(job_id: str) -> str:
    """
    Start a document processing workflow.
    
    Args:
        job_id: The job ID (also used as workflow ID)
        
    Returns:
        workflow_id (same as job_id)
    """
    from src.workflows.document_workflow_pr16 import DocumentWorkflowPR16
    
    client = await get_temporal_client()
    
    handle = await client.start_workflow(
        DocumentWorkflowPR16.run,
        job_id,
        id=job_id,
        task_queue=config.TEMPORAL_TASK_QUEUE,
    )
    
    logger.info(f"[{job_id}] Temporal workflow started: workflow_id={handle.id}")
    
    return handle.id
