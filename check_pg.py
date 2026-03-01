import asyncio
import asyncpg

async def check():
    conn = await asyncpg.connect(
        host="localhost", port=5432,
        user="postgres", password="2410",
        database="postgres"
    )
    v = await conn.fetchval("SHOW server_version")
    ext = await conn.fetch("SELECT name FROM pg_available_extensions WHERE name='vector'")
    print(f"PostgreSQL version: {v}")
    print(f"pgvector available: {len(ext) > 0}")
    if ext:
        print(f"  Extension name: {ext[0]['name']}")
    
    db_exists = await conn.fetchval(
        "SELECT 1 FROM pg_database WHERE datname = 'horob1_docub_rm_service'"
    )
    print(f"Database exists: {db_exists is not None}")
    await conn.close()

asyncio.run(check())
