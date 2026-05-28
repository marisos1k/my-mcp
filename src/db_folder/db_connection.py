import asyncio
import asyncpg
from dotenv import load_dotenv
import os

load_dotenv('config.env')

DB_CONFIG = {
    'user': os.getenv('user'),
    'password': os.getenv('password'),
    'database':os.getenv('database'),
    'host': os.getenv('host'),
    'port': int(os.getenv('port', 5432))
}

class ConnectionDB:
    """Подключение к бд и базовые операции (один пул на процесс)."""

    def __init__(self, config: dict, *, min_size: int = 1, max_size: int = 5):
        self.config = config
        self._min_size = min_size
        self._max_size = max_size
        self.pool: asyncpg.Pool | None = None

    async def connect_db(self) -> asyncpg.Pool:
        """Создаёт пул один раз; повторные вызовы безопасны."""
        if self.pool is not None:
            return self.pool
        self.pool = await asyncpg.create_pool(
            min_size=self._min_size,
            max_size=self._max_size,
            **self.config,
        )
        print("БД подключена")
        return self.pool

    async def close_conn(self) -> None:
        if self.pool is not None:
            await self.pool.close()
            self.pool = None
            print("Подключение прервано")

    def _require_pool(self) -> asyncpg.Pool:
        if self.pool is None:
            raise RuntimeError("Database pool is not connected")
        return self.pool

    async def fetch_one(self, query: str, *args):
        async with self._require_pool().acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    async def fetch(self, query: str, *args):
        async with self._require_pool().acquire() as conn:
            return await conn.fetch(query, *args)
        
    async def execute(self, query: str, *args):
        async with self._require_pool().acquire() as conn:
            return await conn.execute(query, *args)


# async def main():
#     db = ConnectionDB(DB_CONFIG)
#     try:
#         await db.connect_db()
#         result = await db.fetch_one("""
#             SELECT u.*, ak.key_name
#             FROM users u
#             JOIN api_keys ak ON ak.user_id = u.id
#             WHERE ak.api_key = $1 AND ak.is_active = true
#         """, 'tm_export_key_abc123xyz')
#         print(f"Результат: {result}")
#     finally:
#         await db.close_conn()

# asyncio.run(main())