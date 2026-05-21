from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP

from api_folder.api_module import APIKeyManager
from db_folder.db_connection import ConnectionDB
from mcp_app.config import db_config
from pipline_folder.auth_middleware import AuthMiddleware
from pipline_folder.pipeline_collector import PipelineCollector


@dataclass
class AppContext:
    db: ConnectionDB
    auth: AuthMiddleware

    def collector(self, api_key: str) -> PipelineCollector:
        return PipelineCollector(self.db, self.auth, api_key)


@asynccontextmanager
async def app_lifespan(_server: FastMCP) -> AsyncIterator[AppContext]:
    db = ConnectionDB(db_config())
    await db.connect_db()
    auth = AuthMiddleware(APIKeyManager(db))
    try:
        yield AppContext(db=db, auth=auth)
    finally:
        await db.close_conn()
