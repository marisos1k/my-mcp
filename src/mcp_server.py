"""Точка входа MCP-сервера (Model Context Protocol Python SDK)."""

from __future__ import annotations

from mcp_app.config import mcp_transport
from mcp_app.server import create_mcp

mcp = create_mcp()

if __name__ == "__main__":
    transport = mcp_transport()
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport=transport)
