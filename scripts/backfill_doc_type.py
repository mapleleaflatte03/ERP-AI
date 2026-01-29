import asyncio
import os
import sys
import json
from datetime import datetime

# Add project root
sys.path.insert(0, "/root/erp-ai")

async def backfill_classification():
    from src.db import get_pool
    print("Starting backfill classification...")
    
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Get documents with NULL doc_type
        rows = await conn.fetch("SELECT id, filename, raw_text, doc_type FROM documents WHERE doc_type IS NULL OR doc_type = 'other'")
        print(f"Found {len(rows)} documents to check.")
        
        for row in rows:
            doc_id = row['id']
            filename = (row['filename'] or "").lower()
            text = (row['raw_text'] or "").lower()
            
            doc_type = "other"
            if "hóa đơn" in text or "invoice" in text or "giá trị gia tăng" in text or "hoa_don" in filename:
                doc_type = "invoice"
            elif "phiếu thu" in text or "receipt" in text or "phieu_thu" in filename:
                doc_type = "receipt"
            elif "phiếu chi" in text or "payment" in text or "phieu_chi" in filename:
                doc_type = "payment"
            elif "sổ phụ" in text or "sao kê" in text or "bank statement" in text or "so_phu" in filename:
                doc_type = "bank_statement"
            
            if doc_type != "other" or row['doc_type'] is None:
                print(f"Updating {filename} -> {doc_type}")
                await conn.execute("UPDATE documents SET doc_type = $1 WHERE id = $2", doc_type, doc_id)

    print("Backfill complete.")

if __name__ == "__main__":
    asyncio.run(backfill_classification())
