import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_folder.db_connection import ConnectionDB
from db_settings import db_config

db = ConnectionDB(db_config())


async def register_user(email: str, password: str):
    """Регистрация нового пользователя"""
    existing = await db.fetch_one("SELECT id FROM users WHERE email = $1", email)
    if existing:
        return None, "User already exists"

    await db.execute(
        """
        INSERT INTO users (email, pass_hash) 
        VALUES ($1, $2)
    """,
        email,
        password,
    )

    user = await db.fetch_one(
        "SELECT id, email, created_at FROM users WHERE email = $1", email
    )
    return user, None


async def login_user(email: str, password: str):
    """Логин пользователя"""
    user = await db.fetch_one(
        "SELECT id, email, created_at FROM users WHERE email = $1 AND pass_hash = $2",
        email,
        password,
    )

    if not user:
        return None, "Invalid email or password"

    return user, None


async def get_user_by_id(user_id: int):
    return await db.fetch_one(
        "SELECT id, email, created_at FROM users WHERE id = $1", user_id
    )
