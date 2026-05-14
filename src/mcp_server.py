from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from api_folder.api_module import APIKeyManager
from db_folder.db_connection import ConnectionDB
from json_utils import json_safe
from pipline_folder.auth_middleware import AuthMiddleware
from pipline_folder.pipeline_collector import (
    PipelineCollector,
    connections_with_step_slots,
    execution_sequence_walk,
    step_slots_by_node_id,
)

_ENV_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_ENV_DIR / "config.env")

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


def _public_pipeline_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": row["name"],
        "project_name": row["project_name"],
        "max_time": json_safe(row.get("max_time")),
        "max_cost": json_safe(row.get("max_cost")),
        "max_fail_percent": json_safe(row.get("max_fail_percent")),
        "score": json_safe(row.get("score")),
        "report": row.get("report"),
    }


def _public_structure(structure: dict[str, Any]) -> dict[str, Any]:
    p = structure["pipeline"]
    pipeline_public = {
        "name": p["name"],
        "project_name": p["project_name"],
        "max_time": json_safe(p.get("max_time")),
        "max_cost": json_safe(p.get("max_cost")),
        "max_fail_percent": json_safe(p.get("max_fail_percent")),
        "score": json_safe(p.get("score")),
        "report": p.get("report"),
    }
    nodes = structure["nodes"]
    slot = step_slots_by_node_id(nodes)
    nodes_public: list[dict[str, Any]] = []
    for n in sorted(nodes, key=lambda x: x["id"]):
        nodes_public.append(
            {
                "step_slot": slot[n["id"]],
                "type_name": n["type_name"],
                "type_description": n.get("type_description"),
                "tool_name": n["tool_name"],
                "report": n.get("report"),
                "attempts": n.get("attempts"),
            }
        )
    links_public = connections_with_step_slots(nodes, structure["links"])
    return {
        "pipeline": pipeline_public,
        "nodes": nodes_public,
        "links": links_public,
        "statistics": dict(structure.get("statistics", {})),
    }


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


@mcp.tool(description="Список имён проектов текущего пользователя (без числовых id).")
async def get_projects(api_key: str) -> list[str]:
    collector = await get_collector(api_key)
    return await collector.get_project_names()


@mcp.tool(
    description=(
        "Список пайплайнов пользователя: только имена и метаданные, без id. "
        "project_name: точное имя проекта для фильтра; пустая строка или не указано — все проекты."
    )
)
async def get_pipelines(
    api_key: str, project_name: str | None = None
) -> list[dict[str, Any]]:
    collector = await get_collector(api_key)
    rows = await collector.get_pipelines(project_name)
    return [_public_pipeline_row(dict(item)) for item in rows]


@mcp.tool(
    description=(
        "Поиск пайплайнов по подстроке имени (без учёта регистра). "
        "Возвращает те же поля, что и get_pipelines, без id."
    )
)
async def search_pipelines(
    api_key: str, query_substring: str
) -> list[dict[str, Any]]:
    collector = await get_collector(api_key)
    if not query_substring or not query_substring.strip():
        raise ValueError("query_substring не должен быть пустым")
    rows = await collector.find_pipelines_by_name(query_substring)
    return [_public_pipeline_row(dict(item)) for item in rows]


@mcp.tool(
    description=(
        "Структура пайплайна по точным project_name и pipeline_name. "
        "Узлы с step_slot, связи from_step/to_step (не id БД). "
        "Персональные данные пользователя в ответ не включаются."
    )
)
async def get_pipeline_structure(
    api_key: str, project_name: str, pipeline_name: str
) -> dict[str, Any]:
    collector = await get_collector(api_key)
    structure = await collector.load_structure_by_project_and_pipeline(
        project_name, pipeline_name
    )
    if not structure:
        raise ValueError("Pipeline not found or access denied")
    return _public_structure(structure)


@mcp.tool(
    description=(
        "Экспорт пайплайна для LLM: blocks со step_slot, connections по from_step/to_step, "
        "execution_sequence в порядке обхода графа (как связи), без id сущностей БД."
    )
)
async def export_for_llm(
    api_key: str, project_name: str, pipeline_name: str
) -> dict[str, Any]:
    collector = await get_collector(api_key)
    structure = await collector.load_structure_by_project_and_pipeline(
        project_name, pipeline_name
    )
    if not structure:
        raise ValueError("Pipeline not found or access denied")
    return collector.export_structure_to_llm(structure)


@mcp.tool(
    description=(
        "Порядок выполнения узлов по рёбрам графа (согласован с export_for_llm). "
        "Поля: step_slot, step (type_name), tool, description."
    )
)
async def get_pipeline_flow(
    api_key: str, project_name: str, pipeline_name: str
) -> dict[str, Any]:
    collector = await get_collector(api_key)
    structure = await collector.load_structure_by_project_and_pipeline(
        project_name, pipeline_name
    )
    if not structure:
        raise ValueError("Pipeline not found or access denied")
    return {
        "project_name": structure["pipeline"]["project_name"],
        "pipeline": structure["pipeline"]["name"],
        "execution_sequence": execution_sequence_walk(
            structure["nodes"], structure["links"]
        ),
    }


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "streamable-http")
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport=transport)
