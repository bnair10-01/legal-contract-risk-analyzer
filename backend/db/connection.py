import asyncpg
import asyncio
from backend.config import settings

_pool: asyncpg.Pool | None = None
_lock = asyncio.Lock()


async def get_db_pool() -> asyncpg.Pool:
    global _pool
    async with _lock:
        if _pool is None:
            _pool = await asyncpg.create_pool(
                settings.database_url,
                min_size=2,
                max_size=10,
                command_timeout=60,
            )
    return _pool


async def close_db_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
