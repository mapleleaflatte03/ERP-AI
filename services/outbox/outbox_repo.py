"""
Outbox Repository for ERPX E2E
Implements Outbox pattern for reliable event publishing
"""

import logging
import sys
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

sys.path.insert(0, "/root/erp-ai")

from domain.enums import OutboxEventType, OutboxStatus
from domain.models import OutboxEvent

logger = logging.getLogger("OutboxRepo")


class OutboxRepository:
    """
    Outbox Repository - Event Bus / Outbox pattern implementation
    Ensures reliable event publishing with at-least-once delivery
    """

    def __init__(self, db: Session):
        self.db = db

    def publish(
        self,
        event_type: OutboxEventType,
        payload: dict[str, Any],
        *,
        aggregate_type: str | None = None,
        aggregate_id: str | None = None,
        tenant_id: str | None = None,
        trace_id: str | None = None,
    ) -> OutboxEvent:
        """
        Publish an event to the outbox

        Args:
            event_type: Type of event
            payload: Event payload (will be JSON serialized)
            aggregate_type: Type of aggregate (e.g., "Invoice", "Proposal")
            aggregate_id: ID of the aggregate
            tenant_id: Tenant identifier
            trace_id: E2E trace ID

        Returns:
            Created OutboxEvent
        """
        event = OutboxEvent(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=str(aggregate_id) if aggregate_id else None,
            payload=payload,
            status=OutboxStatus.PENDING,
            tenant_id=tenant_id,
            trace_id=trace_id,
        )

        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)

        logger.info(f"OUTBOX: Published event {event_type.value} for {aggregate_type}:{aggregate_id} trace={trace_id}")

        return event

    def get_pending_events(self, limit: int = 100) -> list[OutboxEvent]:
        """Get pending events to process"""
        return (
            self.db.query(OutboxEvent)
            .filter(OutboxEvent.status == OutboxStatus.PENDING)
            .filter(OutboxEvent.retry_count < OutboxEvent.max_retries)
            .order_by(OutboxEvent.created_at.asc())
            .limit(limit)
            .all()
        )

    def mark_processing(self, event_id: uuid.UUID) -> None:
        """Mark event as processing"""
        event = self.db.query(OutboxEvent).filter(OutboxEvent.id == event_id).first()
        if event:
            event.status = OutboxStatus.PROCESSING
            self.db.commit()

    def mark_completed(self, event_id: uuid.UUID) -> None:
        """Mark event as completed"""
        event = self.db.query(OutboxEvent).filter(OutboxEvent.id == event_id).first()
        if event:
            event.status = OutboxStatus.COMPLETED
            event.processed_at = datetime.utcnow()
            self.db.commit()
            logger.info(f"OUTBOX: Completed event {event_id}")

    def mark_failed(self, event_id: uuid.UUID, error_message: str) -> None:
        """Mark event as failed and increment retry count"""
        event = self.db.query(OutboxEvent).filter(OutboxEvent.id == event_id).first()
        if event:
            event.retry_count += 1
            event.error_message = error_message

            if event.retry_count >= event.max_retries:
                event.status = OutboxStatus.FAILED
                logger.error(
                    f"OUTBOX: Event {event_id} permanently failed after {event.retry_count} retries: {error_message}"
                )
            else:
                event.status = OutboxStatus.PENDING  # Will be retried
                logger.warning(f"OUTBOX: Event {event_id} failed (retry {event.retry_count}): {error_message}")

            self.db.commit()

    def get_events_by_aggregate(
        self,
        aggregate_type: str,
        aggregate_id: str,
        limit: int = 100,
    ) -> list[OutboxEvent]:
        """Get events for a specific aggregate"""
        return (
            self.db.query(OutboxEvent)
            .filter(OutboxEvent.aggregate_type == aggregate_type)
            .filter(OutboxEvent.aggregate_id == str(aggregate_id))
            .order_by(OutboxEvent.created_at.desc())
            .limit(limit)
            .all()
        )

    def cleanup_old_completed(self, days: int = 30) -> int:
        """Clean up old completed events"""
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(days=days)

        result = (
            self.db.query(OutboxEvent)
            .filter(OutboxEvent.status == OutboxStatus.COMPLETED)
            .filter(OutboxEvent.processed_at < cutoff)
            .delete()
        )
        self.db.commit()

        logger.info(f"OUTBOX: Cleaned up {result} old completed events")
        return result
