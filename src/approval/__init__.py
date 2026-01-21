"""
ERPX Approval Inbox Module
==========================
PR-8: Approval workflow services.
"""

from .service import (
    approve_proposal,
    create_pending_approval,
    get_approval_by_id,
    list_pending_approvals,
    post_to_ledger,
    reject_proposal,
)

__all__ = [
    "list_pending_approvals",
    "get_approval_by_id",
    "approve_proposal",
    "reject_proposal",
    "post_to_ledger",
    "create_pending_approval",
]
