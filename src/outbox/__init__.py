"""
ERPX Outbox Module
==================
PR-11: Event Bus / Outbox pattern.
"""

from .producer import (
    AggregateType,
    DeliveryType,
    EventStatus,
    EventType,
    emit_job_completed,
    emit_job_created,
    emit_job_failed,
    emit_ledger_posted,
    emit_proposal_approved,
    get_outbox_stats,
    get_pending_events,
    get_subscriptions_for_event,
    log_delivery_attempt,
    mark_event_delivered,
    mark_event_failed,
    mark_event_processing,
    move_to_dead_letter,
    publish_event,
)
from .worker import OutboxWorker

__all__ = [
    # Types
    "EventType",
    "AggregateType",
    "EventStatus",
    "DeliveryType",
    # Producer
    "publish_event",
    "get_pending_events",
    "mark_event_processing",
    "mark_event_delivered",
    "mark_event_failed",
    "move_to_dead_letter",
    "get_subscriptions_for_event",
    "log_delivery_attempt",
    "get_outbox_stats",
    # Convenience emitters
    "emit_job_created",
    "emit_job_completed",
    "emit_job_failed",
    "emit_proposal_approved",
    "emit_ledger_posted",
    # Worker
    "OutboxWorker",
]
