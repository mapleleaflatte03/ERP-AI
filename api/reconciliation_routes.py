"""
Reconciliation API Routes - Bank Statement Matching MVP
======================================================
Match bank transactions with invoices.

Endpoints:
- GET /reconciliation/transactions - List bank transactions
- GET /reconciliation/invoices - List unmatched invoices
- POST /reconciliation/match - Match transaction with invoice
- POST /reconciliation/import - Import bank statement
"""

import logging
import uuid
from datetime import datetime, date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

from src.db import get_pool

logger = logging.getLogger("reconciliation-routes")

router = APIRouter(prefix="/reconciliation", tags=["Reconciliation"])


# ===== Pydantic Models =====

class BankTransaction(BaseModel):
    """Bank transaction model"""
    id: str
    transaction_date: str
    description: str
    amount: float
    type: str  # credit/debit
    reference: Optional[str] = None
    status: str  # unmatched, matched, suspicious
    matched_invoice_id: Optional[str] = None


class UnmatchedInvoice(BaseModel):
    """Unmatched invoice for reconciliation"""
    id: str
    invoice_no: str
    invoice_date: str
    vendor_name: str
    amount: float
    status: str


class MatchRequest(BaseModel):
    """Match request"""
    transaction_id: str
    invoice_id: str


class ReconciliationStats(BaseModel):
    """Reconciliation statistics"""
    total_transactions: int
    matched_count: int
    unmatched_count: int
    suspicious_count: int
    total_amount: float


# ===== API Endpoints =====

@router.get("/stats", response_model=ReconciliationStats)
async def get_reconciliation_stats(pool=Depends(get_pool)):
    """Get reconciliation statistics"""
    try:
        async with pool.acquire() as conn:
            # Try to get stats from bank_transactions table
            try:
                row = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE status = 'matched') as matched,
                        COUNT(*) FILTER (WHERE status = 'unmatched') as unmatched,
                        COUNT(*) FILTER (WHERE status = 'suspicious') as suspicious,
                        COALESCE(SUM(amount), 0) as total_amount
                    FROM bank_transactions
                """)
                return ReconciliationStats(
                    total_transactions=row["total"] or 0,
                    matched_count=row["matched"] or 0,
                    unmatched_count=row["unmatched"] or 0,
                    suspicious_count=row["suspicious"] or 0,
                    total_amount=float(row["total_amount"] or 0)
                )
            except Exception:
                # Table doesn't exist yet - return zeros
                return ReconciliationStats(
                    total_transactions=0,
                    matched_count=0,
                    unmatched_count=0,
                    suspicious_count=0,
                    total_amount=0
                )
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return ReconciliationStats(
            total_transactions=0,
            matched_count=0,
            unmatched_count=0,
            suspicious_count=0,
            total_amount=0
        )


@router.get("/transactions", response_model=list[BankTransaction])
async def list_transactions(
    status: Optional[str] = None,
    limit: int = 50,
    pool=Depends(get_pool)
):
    """List bank transactions"""
    try:
        async with pool.acquire() as conn:
            if status:
                rows = await conn.fetch("""
                    SELECT id, transaction_date, description, amount, 
                           type, reference, status, matched_invoice_id
                    FROM bank_transactions
                    WHERE status = $1
                    ORDER BY transaction_date DESC
                    LIMIT $2
                """, status, limit)
            else:
                rows = await conn.fetch("""
                    SELECT id, transaction_date, description, amount,
                           type, reference, status, matched_invoice_id
                    FROM bank_transactions
                    ORDER BY transaction_date DESC
                    LIMIT $1
                """, limit)
            
            return [
                BankTransaction(
                    id=str(row["id"]),
                    transaction_date=row["transaction_date"].isoformat() if row["transaction_date"] else "",
                    description=row["description"] or "",
                    amount=float(row["amount"] or 0),
                    type=row["type"] or "debit",
                    reference=row.get("reference"),
                    status=row["status"] or "unmatched",
                    matched_invoice_id=str(row["matched_invoice_id"]) if row.get("matched_invoice_id") else None
                )
                for row in rows
            ]
    except Exception as e:
        logger.warning(f"Could not fetch transactions: {e}")
        return []


@router.get("/invoices", response_model=list[UnmatchedInvoice])
async def list_unmatched_invoices(
    search: Optional[str] = None,
    limit: int = 50,
    pool=Depends(get_pool)
):
    """List invoices available for matching"""
    try:
        async with pool.acquire() as conn:
            query = """
                SELECT d.id, d.invoice_no, d.invoice_date, d.vendor_name, d.total_amount, d.status
                FROM documents d
                LEFT JOIN bank_transactions bt ON bt.matched_invoice_id = d.id
                WHERE d.status IN ('approved', 'extracted')
                  AND bt.id IS NULL
            """
            params = []
            
            if search:
                query += " AND (d.invoice_no ILIKE $1 OR d.vendor_name ILIKE $1)"
                params.append(f"%{search}%")
            
            query += f" ORDER BY d.invoice_date DESC LIMIT {limit}"
            
            rows = await conn.fetch(query, *params)
            
            return [
                UnmatchedInvoice(
                    id=str(row["id"]),
                    invoice_no=row["invoice_no"] or "",
                    invoice_date=row["invoice_date"].isoformat() if row["invoice_date"] else "",
                    vendor_name=row["vendor_name"] or "",
                    amount=float(row["total_amount"] or 0),
                    status=row["status"] or ""
                )
                for row in rows
            ]
    except Exception as e:
        logger.warning(f"Could not fetch invoices: {e}")
        return []


@router.post("/match")
async def match_transaction(request: MatchRequest, pool=Depends(get_pool)):
    """Match a bank transaction with an invoice"""
    try:
        async with pool.acquire() as conn:
            # Update transaction
            await conn.execute("""
                UPDATE bank_transactions
                SET status = 'matched',
                    matched_invoice_id = $1,
                    matched_at = $2
                WHERE id = $3
            """, request.invoice_id, datetime.utcnow(), request.transaction_id)
            
            return {"success": True, "message": "Transaction matched successfully"}
    except Exception as e:
        logger.error(f"Match failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/unmatch/{transaction_id}")
async def unmatch_transaction(transaction_id: str, pool=Depends(get_pool)):
    """Unmatch a transaction"""
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE bank_transactions
                SET status = 'unmatched',
                    matched_invoice_id = NULL,
                    matched_at = NULL
                WHERE id = $1
            """, transaction_id)
            
            return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
