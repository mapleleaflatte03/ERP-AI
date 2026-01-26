"""
ERPX AI Accounting - Outbox Worker
==================================
PR-11: Background worker for processing outbox events.

Runs as background task or separate process.
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any

import httpx

from .producer import (
    EventStatus,
    get_pending_events,
    get_subscriptions_for_event,
    log_delivery_attempt,
    log_delivery_attempts_batch,
    mark_event_delivered,
    mark_event_failed,
    mark_event_processing,
    move_to_dead_letter,
)

logger = logging.getLogger("erpx.outbox.worker")


class OutboxWorker:
    """
    Outbox event delivery worker.

    Polls the outbox table and delivers events to subscribed handlers.
    """

    def __init__(
        self,
        db_connection_factory,
        poll_interval: float = 5.0,
        batch_size: int = 50,
        max_attempts: int = 5,
    ):
        self.db_connection_factory = db_connection_factory
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self.max_attempts = max_attempts
        self._running = False
        self._http_client: httpx.AsyncClient | None = None

    async def start(self):
        """Start the worker."""
        self._running = True
        self._http_client = httpx.AsyncClient(timeout=30.0)
        logger.info("Outbox worker started")

        while self._running:
            try:
                await self._process_batch()
            except Exception as e:
                logger.error(f"Outbox worker error: {e}", exc_info=True)

            await asyncio.sleep(self.poll_interval)

    async def stop(self):
        """Stop the worker."""
        self._running = False
        if self._http_client:
            await self._http_client.aclose()
        logger.info("Outbox worker stopped")

    async def _process_batch(self):
        """Process a batch of pending events."""
        conn = await self.db_connection_factory()

        try:
            events = await get_pending_events(
                conn,
                limit=self.batch_size,
                max_attempts=self.max_attempts,
            )

            if not events:
                return

            logger.debug(f"Processing {len(events)} events")

            for event in events:
                await self._process_event(conn, event)

        finally:
            await conn.close()

    async def _process_event(self, conn, event: dict):
        """Process a single event."""
        event_id = event["id"]
        request_id = event.get("request_id")

        try:
            # Mark as processing
            await mark_event_processing(conn, event_id, request_id)

            # Get subscriptions
            subscriptions = await get_subscriptions_for_event(conn, event["event_type"])

            if not subscriptions:
                # No subscriptions, mark as delivered
                await mark_event_delivered(conn, event_id, request_id)
                return

            # Deliver to each subscription
            all_success = True
            delivery_attempts = []

            try:
                for subscription in subscriptions:
                    success, log_entry = await self._deliver_to_subscription(conn, event, subscription)
                    if log_entry:
                        delivery_attempts.append(log_entry)
                    if not success:
                        all_success = False
            finally:
                # Batch log deliveries
                if delivery_attempts:
                    await log_delivery_attempts_batch(conn, delivery_attempts)

            if all_success:
                await mark_event_delivered(conn, event_id, request_id)
            else:
                # Check if max attempts reached
                if event["attempts"] + 1 >= self.max_attempts:
                    await move_to_dead_letter(
                        conn,
                        event_id,
                        f"Max attempts ({self.max_attempts}) reached",
                        request_id,
                    )
                else:
                    await mark_event_failed(conn, event_id, "Some deliveries failed", request_id)

        except Exception as e:
            logger.error(f"[{request_id}] Event processing error: {e}")
            await mark_event_failed(conn, event_id, str(e), request_id)

    async def _deliver_to_subscription(
        self,
        conn,
        event: dict,
        subscription: dict,
    ) -> tuple[bool, dict | None]:
        """Deliver event to a subscription."""
        delivery_type = subscription["delivery_type"]
        config = subscription["delivery_config"]
        start_time = time.time()

        try:
            if delivery_type == "webhook":
                result = await self._deliver_webhook(event, config)
            elif delivery_type == "temporal":
                result = await self._deliver_temporal(event, config)
            elif delivery_type == "internal":
                result = await self._deliver_internal(event, config)
            else:
                logger.warning(f"Unknown delivery type: {delivery_type}")
                return True, None  # Skip unknown types

            response_time_ms = int((time.time() - start_time) * 1000)

            # Return success log entry
            return True, {
                "event_id": event["id"],
                "subscription_id": subscription["id"],
                "attempt_number": event["attempts"] + 1,
                "status": "success",
                "response_code": result.get("status_code", 200),
                "response_time_ms": response_time_ms,
            }

        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)

            logger.warning(f"Delivery failed to {subscription['name']}: {e}")

            # Return failed log entry
            return False, {
                "event_id": event["id"],
                "subscription_id": subscription["id"],
                "attempt_number": event["attempts"] + 1,
                "status": "failed",
                "response_time_ms": response_time_ms,
                "error_message": str(e),
            }

    async def _deliver_webhook(self, event: dict, config: dict) -> dict:
        """Deliver event via webhook."""
        url = config["url"]
        method = config.get("method", "POST")
        headers = config.get("headers", {})
        headers["Content-Type"] = "application/json"

        payload = {
            "event_id": event["id"],
            "event_type": event["event_type"],
            "aggregate_type": event["aggregate_type"],
            "aggregate_id": event["aggregate_id"],
            "payload": event["payload"],
            "timestamp": datetime.utcnow().isoformat(),
        }

        response = await self._http_client.request(
            method,
            url,
            json=payload,
            headers=headers,
        )

        if response.status_code >= 400:
            raise Exception(f"Webhook returned {response.status_code}")

        return {"status_code": response.status_code}

    async def _deliver_temporal(self, event: dict, config: dict) -> dict:
        """Deliver event to Temporal workflow."""
        # Import Temporal client lazily
        try:
            from temporalio.client import Client

            workflow = config.get("workflow", "process_document_workflow")
            task_queue = config.get("task_queue", "erpx-ai")
            workflow_id_prefix = config.get("workflow_id_prefix", "event-")

            # Create workflow ID
            workflow_id = f"{workflow_id_prefix}{event['aggregate_id']}"

            # Connect to Temporal
            client = await Client.connect("temporal:7233")

            # Start workflow
            await client.execute_workflow(
                workflow,
                event["payload"],
                id=workflow_id,
                task_queue=task_queue,
            )

            logger.info(f"Started Temporal workflow: {workflow_id}")
            return {"status_code": 200, "workflow_id": workflow_id}

        except ImportError:
            logger.warning("Temporal client not available, skipping")
            return {"status_code": 200, "skipped": True}

    async def _deliver_internal(self, event: dict, config: dict) -> dict:
        """Deliver event to internal handler."""
        handler_name = config.get("handler", "default_handler")

        # Built-in handlers
        if handler_name == "audit_log_handler":
            logger.info(f"AUDIT: {event['event_type']} {event['aggregate_type']}:{event['aggregate_id']}")
        else:
            logger.warning(f"Unknown internal handler: {handler_name}")

        return {"status_code": 200, "handler": handler_name}


# ===========================================================================
# Standalone Worker Entry Point
# ===========================================================================


async def run_outbox_worker():
    """Run the outbox worker as standalone process."""
    import os

    import asyncpg

    db_url = os.getenv("DATABASE_URL", "postgresql://erpx:erpx_secret@postgres:5432/erpx")
    # Parse URL
    db_url = db_url.replace("postgresql://", "")
    parts = db_url.split("@")
    user_pass = parts[0].split(":")
    host_db = parts[1].split("/")
    host_port = host_db[0].split(":")

    async def connection_factory():
        return await asyncpg.connect(
            host=host_port[0],
            port=int(host_port[1]) if len(host_port) > 1 else 5432,
            user=user_pass[0],
            password=user_pass[1],
            database=host_db[1],
        )

    worker = OutboxWorker(connection_factory)

    # Handle shutdown
    import signal

    def shutdown_handler(sig, frame):
        logger.info("Shutdown signal received")
        asyncio.create_task(worker.stop())

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    await worker.start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_outbox_worker())
