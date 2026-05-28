from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from mcp_app.bundled_skills import load_skill_body
from mcp_app.context import AppContext
from mcp_app.views import public_pipeline_row, public_structure
from pipline_folder.pipeline_collector import execution_sequence_walk


def register_tools(mcp: FastMCP) -> None:
    @mcp.tool(description="Список имён проектов текущего пользователя (без числовых id).")
    async def get_projects(
        api_key: str, ctx: Context[ServerSession, AppContext]
    ) -> list[str]:
        app = ctx.request_context.lifespan_context
        return await app.collector(api_key).get_project_names()

    @mcp.tool(
        description=(
            "Список пайплайнов пользователя: только имена и метаданные, без id. "
            "project_name: точное имя проекта для фильтра; пустая строка или не указано — все проекты."
        )
    )
    async def get_pipelines(
        api_key: str,
        ctx: Context[ServerSession, AppContext],
        project_name: str | None = None,
    ) -> list[dict[str, Any]]:
        app = ctx.request_context.lifespan_context
        rows = await app.collector(api_key).get_pipelines(project_name)
        return [public_pipeline_row(dict(item)) for item in rows]

    @mcp.tool(
        description=(
            "Поиск пайплайнов по подстроке имени (без учёта регистра). "
            "Возвращает те же поля, что и get_pipelines, без id."
        )
    )
    async def search_pipelines(
        api_key: str,
        query_substring: str,
        ctx: Context[ServerSession, AppContext],
    ) -> list[dict[str, Any]]:
        if not query_substring or not query_substring.strip():
            raise ValueError("query_substring не должен быть пустым")
        app = ctx.request_context.lifespan_context
        rows = await app.collector(api_key).find_pipelines_by_name(query_substring)
        return [public_pipeline_row(dict(item)) for item in rows]

    @mcp.tool(
        description=(
            "Структура пайплайна (export_version=2): blocks с node_config/ports, "
            "connections с from_port/to_port, nested_pipeline refs."
        )
    )
    async def get_pipeline_structure(
        api_key: str,
        project_name: str,
        pipeline_name: str,
        ctx: Context[ServerSession, AppContext],
    ) -> dict[str, Any]:
        app = ctx.request_context.lifespan_context
        structure = await app.collector(api_key).load_structure_by_project_and_pipeline(
            project_name, pipeline_name
        )
        if not structure:
            raise ValueError("Pipeline not found or access denied")
        return public_structure(structure)

    @mcp.tool(
        description=(
            "Главный сценарий «пайплайн → код»: спецификация пайплайна (как export_for_llm) "
            "плюс workflow-инструкции для агента (skill pipeline-to-code). "
            "Вызывай, когда пользователь просит экспортировать/реализовать пайплайн кодом. "
            "Дальше создай файлы pipelines/ и handlers/ по workflow, без вывода сырого JSON."
        )
    )
    async def export_pipeline_as_code(
        api_key: str,
        project_name: str,
        pipeline_name: str,
        ctx: Context[ServerSession, AppContext],
    ) -> dict[str, Any]:
        app = ctx.request_context.lifespan_context
        collector = app.collector(api_key)
        structure = await collector.load_structure_by_project_and_pipeline(
            project_name, pipeline_name
        )
        if not structure:
            raise ValueError("Pipeline not found or access denied")
        spec = await collector.export_structure_to_llm(structure)
        pl = spec.get("pipeline_name") or pipeline_name
        return {
            "pipeline_spec": spec,
            "workflow": load_skill_body("pipeline-to-code"),
            "output_hint": {
                "pipeline_file": f"pipelines/{pl}.py",
                "handlers_dir": "handlers/",
            },
        }

    @mcp.tool(
        description=(
            "Экспорт пайплайна для LLM: blocks с node_config/ports, connections с портами, "
            "execution_plan, nested_pipelines (export_version=2)."
        )
    )
    async def export_for_llm(
        api_key: str,
        project_name: str,
        pipeline_name: str,
        ctx: Context[ServerSession, AppContext],
    ) -> dict[str, Any]:
        app = ctx.request_context.lifespan_context
        collector = app.collector(api_key)
        structure = await collector.load_structure_by_project_and_pipeline(
            project_name, pipeline_name
        )
        if not structure:
            raise ValueError("Pipeline not found or access denied")
        return await collector.export_structure_to_llm(structure)

    @mcp.tool(
        description=(
            "Порядок выполнения узлов: step_slot, tool, node_config (согласован с export_for_llm)."
        )
    )
    async def get_pipeline_flow(
        api_key: str,
        project_name: str,
        pipeline_name: str,
        ctx: Context[ServerSession, AppContext],
    ) -> dict[str, Any]:
        app = ctx.request_context.lifespan_context
        structure = await app.collector(api_key).load_structure_by_project_and_pipeline(
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
