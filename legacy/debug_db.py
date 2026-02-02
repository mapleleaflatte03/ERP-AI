
import asyncio
import os
import asyncpg

async def main():
    try:
        conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
        rows = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'ledger_lines'")
        print("Columns in ledger_lines:", [r['column_name'] for r in rows])
        await conn.close()
    except Exception as e:
        print(e)

if __name__ == "__main__":
    asyncio.run(main())
