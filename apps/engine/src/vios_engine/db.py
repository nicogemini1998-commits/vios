"""Pool Postgres (asyncpg). Chequeo real para /health."""
from __future__ import annotations

import asyncpg


async def check_db(database_url: str) -> bool:
    """Devuelve True si `SELECT 1` responde. False si la conexión falla."""
    try:
        conn = await asyncpg.connect(database_url, timeout=5)
    except Exception:
        return False
    try:
        return (await conn.fetchval("SELECT 1")) == 1
    finally:
        await conn.close()
