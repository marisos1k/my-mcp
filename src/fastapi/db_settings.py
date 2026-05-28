"""Настройки БД для demo API (путь к config.env не зависит от cwd)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_FASTAPI_DIR = Path(__file__).resolve().parent
_ENV_FILE = _FASTAPI_DIR / "config.env"

load_dotenv(_ENV_FILE)


def db_config() -> dict:
    host = os.getenv("host") or "127.0.0.1"
    if host == "localhost":
        host = "127.0.0.1"
    return {
        "user": os.getenv("user", "postgres"),
        "password": os.getenv("password", "7474"),
        "database": os.getenv("database", "test_brainiac"),
        "host": host,
        "port": int(os.getenv("port", "5432")),
    }


def config_summary() -> str:
    c = db_config()
    return f"{c['user']}@{c['host']}:{c['port']}/{c['database']} ({_ENV_FILE})"
