import asyncio
from db_folder.db_connection import ConnectionDB
from dotenv import load_dotenv
import os

load_dotenv('config.env')

DB_CONFIG = {
    'user': os.getenv('user'),
    'password': os.getenv('password'),
    'database': os.getenv('database'),
    'host': os.getenv('host'),
    'port': int(os.getenv('port', 5432))
}

async def test():
    print("DB_CONFIG:", DB_CONFIG)
    db = ConnectionDB(DB_CONFIG)
    try:
        await db.connect_db()
        print("✅ Connected to DB!")
        
        # Проверяем наличие таблицы users
        result = await db.fetch_one("SELECT COUNT(*) FROM users")
        print(f"Users count: {result}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await db.close_conn()

asyncio.run(test())