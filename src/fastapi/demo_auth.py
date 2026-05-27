import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

db = ConnectionDB(DB_CONFIG)

async def register_user(email: str, password: str):
    """Регистрация нового пользователя"""
    await db.connect_db()
    
    existing = await db.fetch_one("SELECT id FROM users WHERE email = $1", email)
    if existing:
        return None, "User already exists"
    
    await db.execute("""
        INSERT INTO users (email, pass_hash) 
        VALUES ($1, $2)
    """, email, password)
    
    user = await db.fetch_one("SELECT id, email, created_at FROM users WHERE email = $1", email)
    return user, None

async def login_user(email: str, password: str):
    """Логин пользователя"""
    await db.connect_db()
    
    user = await db.fetch_one(
        "SELECT id, email, created_at FROM users WHERE email = $1 AND pass_hash = $2",
        email, password
    )
    
    if not user:
        return None, "Invalid email or password"
    
    return user, None

async def get_user_by_id(user_id: int):
    await db.connect_db()
    return await db.fetch_one("SELECT id, email, created_at FROM users WHERE id = $1", user_id)