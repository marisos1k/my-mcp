import os
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from api_folder.api_module import APIKeyManager
from db_folder.db_connection import ConnectionDB
from pipline_folder.auth_middleware import AuthMiddleware
from pipline_folder.pipeline_collector import PipelineCollector

load_dotenv("config.env")

DB_CONFIG = {
    "user": os.getenv("user"),
    "password": os.getenv("password"),
    "database": os.getenv("database"),
    "host": os.getenv("host"),
    "port": int(os.getenv("port", 5432)),
}

mcp = FastMCP(
    "pipeline-mcp-server",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("MCP_PORT", "8000")),
    streamable_http_path="/mcp",
)

db: ConnectionDB | None = None
auth_middleware: AuthMiddleware | None = None


async def ensure_services_ready() -> None:
    """Инициализировать DB и auth один раз при первом запросе."""
    global db, auth_middleware
    if db is not None and auth_middleware is not None:
        return

    db = ConnectionDB(DB_CONFIG)
    await db.connect_db()
    auth_middleware = AuthMiddleware(APIKeyManager(db))


async def get_collector(api_key: str) -> PipelineCollector:
    await ensure_services_ready()
    if not db or not auth_middleware:
        raise RuntimeError("Server dependencies are not initialized")
    return PipelineCollector(db, auth_middleware, api_key)


@mcp.tool(description="Получить список всех пайплайнов пользователя")
async def get_pipelines(api_key: str) -> list[dict[str, Any]]:
    collector = await get_collector(api_key)
    pipelines = await collector.get_pipelines()
    return [dict(item) for item in pipelines]


@mcp.tool(description="Получить структуру пайплайна (узлы и связи)")
async def get_pipeline_structure(api_key: str, pipeline_id: int) -> dict[str, Any]:
    collector = await get_collector(api_key)
    structure = await collector.get_structure_of_pipeline(pipeline_id)
    if not structure:
        raise ValueError("Pipeline not found or access denied")
    return structure


@mcp.tool(description="Экспортировать пайплайн в формате, понятном LLM")
async def export_for_llm(api_key: str, pipeline_id: int) -> dict[str, Any]:
    collector = await get_collector(api_key)
    llm_data = await collector.export_pipeline_to_llm(pipeline_id)
    if not llm_data:
        raise ValueError("Pipeline not found or access denied")
    return llm_data


@mcp.tool(description="Получить порядок выполнения узлов в пайплайне")
async def get_pipeline_flow(api_key: str, pipeline_id: int) -> dict[str, Any]:
    collector = await get_collector(api_key)
    structure = await collector.get_structure_of_pipeline(pipeline_id)
    if not structure:
        raise ValueError("Pipeline not found or access denied")

    flow: dict[str, Any] = {
        "pipeline": structure["pipeline"]["name"],
        "execution_sequence": [],
    }
    for node in structure["nodes"]:
        flow["execution_sequence"].append(
            {
                "step": node["type_name"],
                "tool": node["tool_name"],
                "description": node["type_description"],
            }
        )
    return flow


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "streamable-http")
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(
            transport=transport
        )