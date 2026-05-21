from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_app.config import mcp_host, mcp_port
from mcp_app.context import app_lifespan
from mcp_app.prompts_resources import register_prompts_and_resources, server_instructions
from mcp_app.tools import register_tools


def create_mcp() -> FastMCP:
    """Сервер на официальном MCP Python SDK (слой FastMCP)."""
    mcp = FastMCP(
        "pipeline-mcp-server",
        instructions=server_instructions(),
        host=mcp_host(),
        port=mcp_port(),
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        lifespan=app_lifespan,
    )
    register_tools(mcp)
    register_prompts_and_resources(mcp)
    return mcp
