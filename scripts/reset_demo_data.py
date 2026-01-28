import asyncio
import logging
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db import get_pool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reset_data")

async def reset_data():
    """Truncate all user data tables"""
    logger.info("Initializing DB pool...")
    pool = await get_pool()
    
    if not pool:
        logger.error("Failed to connect to DB")
        return

    async with pool.acquire() as conn:
        logger.warning("!!! WIPING ALL DATA IN 5 SECONDS !!!")
        logger.warning("Tables: ledger_lines, ledger_entries, approvals, journal_proposals, extracted_invoices, audit_evidence, documents, jobs")
        await asyncio.sleep(5)
        
        try:
            # Delete in order of dependencies (child first)
            await conn.execute("TRUNCATE TABLE ledger_lines CASCADE")
            await conn.execute("TRUNCATE TABLE ledger_entries CASCADE")
            await conn.execute("TRUNCATE TABLE approvals CASCADE")
            await conn.execute("TRUNCATE TABLE journal_proposals CASCADE")
            await conn.execute("TRUNCATE TABLE extracted_invoices CASCADE")
            await conn.execute("TRUNCATE TABLE audit_evidence CASCADE")
            await conn.execute("TRUNCATE TABLE documents CASCADE")
            await conn.execute("TRUNCATE TABLE jobs CASCADE")
            
            logger.info("✓ All data tables truncated successfully")
        except Exception as e:
            logger.error(f"Failed to truncate tables: {e}")

if __name__ == "__main__":
    if os.getenv("APP_ENV") == "production":
        print("Cannot run reset script in production!")
        sys.exit(1)
        
    asyncio.run(reset_data())
