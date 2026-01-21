"""
ERPX AI Accounting - Data Zones Service
=======================================
PR-10: Data lineage tracking through processing zones.

Zones:
- RAW: Original uploaded document
- EXTRACTED: OCR/PDF text extraction result
- PROPOSED: Journal proposal from LLM
- POSTED: Final ledger entry
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger("erpx.datazones")


class DataZone(str, Enum):
    """Data processing zones."""

    RAW = "raw"
    EXTRACTED = "extracted"
    PROPOSED = "proposed"
    POSTED = "posted"


class ZoneStatus(str, Enum):
    """Zone record status."""

    ACTIVE = "active"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


async def track_zone_entry(
    conn,
    job_id: str,
    zone: DataZone,
    tenant_id: str | None = None,
    document_id: str | None = None,
    raw_file_uri: str | None = None,
    extracted_text_preview: str | None = None,
    proposal_id: str | None = None,
    ledger_entry_id: str | None = None,
    checksum: str | None = None,
    byte_count: int | None = None,
    processing_time_ms: int | None = None,
    request_id: str | None = None,
) -> str:
    """
    Track data entering a processing zone.

    Args:
        conn: asyncpg connection
        job_id: Job identifier
        zone: Target zone
        ... other zone-specific data

    Returns:
        Zone record ID
    """
    zone_id = uuid.uuid4()

    await conn.execute(
        """
        INSERT INTO data_zones
        (id, job_id, tenant_id, document_id, zone, status,
         raw_file_uri, extracted_text_preview, proposal_id, ledger_entry_id,
         checksum, byte_count, processing_time_ms, request_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        """,
        zone_id,
        job_id,
        uuid.UUID(tenant_id) if tenant_id and len(str(tenant_id)) > 10 else None,
        uuid.UUID(document_id) if document_id else None,
        zone.value,
        ZoneStatus.ACTIVE.value,
        raw_file_uri,
        (extracted_text_preview or "")[:4000] if extracted_text_preview else None,
        uuid.UUID(proposal_id) if proposal_id else None,
        uuid.UUID(ledger_entry_id) if ledger_entry_id else None,
        checksum,
        byte_count,
        processing_time_ms,
        request_id,
    )

    logger.info(f"[{request_id}] Job {job_id} entered zone {zone.value}")
    return str(zone_id)


async def get_job_zones(conn, job_id: str) -> list[dict]:
    """Get all zone records for a job."""
    rows = await conn.fetch(
        """
        SELECT * FROM data_zones
        WHERE job_id = $1
        ORDER BY zone_entered_at ASC
        """,
        job_id,
    )

    return [
        {
            "id": str(row["id"]),
            "job_id": row["job_id"],
            "zone": row["zone"],
            "status": row["status"],
            "checksum": row["checksum"],
            "byte_count": row["byte_count"],
            "processing_time_ms": row["processing_time_ms"],
            "zone_entered_at": row["zone_entered_at"].isoformat() if row["zone_entered_at"] else None,
            "raw_file_uri": row["raw_file_uri"],
            "proposal_id": str(row["proposal_id"]) if row["proposal_id"] else None,
            "ledger_entry_id": str(row["ledger_entry_id"]) if row["ledger_entry_id"] else None,
        }
        for row in rows
    ]


async def get_current_zone(conn, job_id: str) -> str | None:
    """Get current (latest) zone for a job."""
    row = await conn.fetchrow(
        """
        SELECT zone FROM data_zones
        WHERE job_id = $1 AND status = 'active'
        ORDER BY zone_entered_at DESC
        LIMIT 1
        """,
        job_id,
    )
    return row["zone"] if row else None


async def supersede_zone(conn, job_id: str, zone: DataZone, request_id: str | None = None):
    """Mark old zone records as superseded (for reprocessing)."""
    await conn.execute(
        """
        UPDATE data_zones
        SET status = 'superseded'
        WHERE job_id = $1 AND zone = $2 AND status = 'active'
        """,
        job_id,
        zone.value,
    )
    logger.info(f"[{request_id}] Superseded zone {zone.value} for job {job_id}")
