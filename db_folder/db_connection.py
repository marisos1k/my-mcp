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
    """Подключение к бд 
        и базовые операции"""
    def __init__(self, config: dict):
        self.config = config
        self.pool = None
    
    async def connect_db(self):
        self.pool = await asyncpg.create_pool(**self.config)
        print('БД подключена')
        return self.pool
    
    async def close_conn(self):
        if self.pool:
            await self.pool.close()
            print('Подключение прервано')

    async def fetch_one(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    async def fetch(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)
        
    async def execute(self, query: str, *args):
        async with self.pool.acquire() as conn:
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