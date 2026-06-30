from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_app.bundled_skills import load_skill_body, load_skill_markdown


def server_instructions() -> str:
    return (
        "Pipeline MCP: данные пайплайнов в PostgreSQL. "
        "Если пользователь просит экспортировать пайплайн КОДОМ или реализовать пайплайн — "
        "вызови tool export_pipeline_as_code (параметр language: 'python', 'typescript' или 'javascript', "
        "по умолчанию 'python'). "
        "Ответ содержит pipeline_spec (граф) и workflow (инструкции по генерации кода). "
        "Создай файлы по workflow — не выводи сырой JSON. "
        "Доступные языки: tool list_languages. "
        "Типы узлов для create_node: tool list_node_types."
    )


def register_prompts_and_resources(mcp: FastMCP) -> None:
    @mcp.resource(
        "skill://pipeline-to-python",
        name="pipeline-to-python-skill",
        description="Инструкции агента: экспорт пайплайна в Python код (handlers + pipelines).",
        mime_type="text/markdown",
    )
    def resource_pipeline_to_python_skill() -> str:
        return load_skill_markdown("pipeline-to-python")

    @mcp.prompt(
        name="export_pipeline_as_code",
        title="Экспорт пайплайна в код",
        description=(
            "Сгенерировать код реализации пайплайна по project_name и pipeline_name. "
            "Требуется api_key пользователя. "
            "Параметр language: 'python' (default), 'typescript', 'javascript'."
        ),
    )
    def prompt_export_pipeline_as_code(
        project_name: str,
        pipeline_name: str,
        api_key: str = "",
        language: str = "python",
    ) -> str:
        workflow = load_skill_body(f"pipeline-to-{language}")
        key_hint = (
            f'Используй api_key="{api_key}" в tool export_pipeline_as_code.'
            if api_key
            else "Запроси api_key у пользователя, если не передан."
        )
        handlers_dir = "src/handlers/" if language in ("typescript", "javascript") else "handlers/"
        pipelines_dir = "src/pipelines/" if language == "typescript" else "pipelines/"
        return (
            f"Экспортируй пайплайн **{pipeline_name}** из проекта **{project_name}** "
            f"в виде **{language}** кода.\n\n"
            f"{key_hint}\n\n"
            f"1. Вызови MCP tool **export_pipeline_as_code** с language=\"{language}\".\n"
            "2. Следуй полю **workflow** и данным **pipeline_spec** из ответа.\n"
            f"3. Создай/обнови файлы в `{pipelines_dir}` и `{handlers_dir}` целевого проекта.\n\n"
            f"---\n\n{workflow}"
        )
