from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT_DIR / "config.env")


def skills_dir() -> Path:
    return ROOT_DIR / "cursor_skills"


def db_config() -> dict:
    return {
        "user": os.getenv("user"),
        "password": os.getenv("password"),
        "database": os.getenv("database"),
        "host": os.getenv("host"),
        "port": int(os.getenv("port", 5432)),
    }


def mcp_host() -> str:
    return os.getenv("MCP_HOST", "0.0.0.0")


def mcp_port() -> int:
    return int(os.getenv("MCP_PORT", "8000"))


def mcp_transport() -> str:
    return os.getenv("MCP_TRANSPORT", "streamable-http")
