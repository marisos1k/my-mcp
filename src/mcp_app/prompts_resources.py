from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_app.bundled_skills import load_skill_body, load_skill_markdown


def server_instructions() -> str:
    return (
        "Pipeline MCP: данные пайплайнов в PostgreSQL. "
        "Если пользователь просит экспортировать пайплайн КОДОМ или реализовать пайплайн — "
        "сначала вызови tool export_pipeline_as_code (даёт спецификацию и workflow). "
        "Затем создай файлы в проекте пользователя по полю workflow, не выводи сырой JSON. "
        "Skill-текст также доступен как resource skill://pipeline-to-code и prompt export_pipeline_as_code."
    )


def register_prompts_and_resources(mcp: FastMCP) -> None:
    @mcp.resource(
        "skill://pipeline-to-code",
        name="pipeline-to-code-skill",
        description="Инструкции агента: экспорт пайплайна в код (handlers + pipelines).",
        mime_type="text/markdown",
    )
    def resource_pipeline_to_code_skill() -> str:
        return load_skill_markdown("pipeline-to-code")

    @mcp.prompt(
        name="export_pipeline_as_code",
        title="Экспорт пайплайна в код",
        description=(
            "Сгенерировать код реализации пайплайна по project_name и pipeline_name. "
            "Требуется api_key пользователя."
        ),
    )
    def prompt_export_pipeline_as_code(
        project_name: str, pipeline_name: str, api_key: str = ""
    ) -> str:
        workflow = load_skill_body("pipeline-to-code")
        key_hint = (
            f'Используй api_key="{api_key}" в tool export_pipeline_as_code.'
            if api_key
            else "Запроси api_key у пользователя, если не передан."
        )
        return (
            f"Экспортируй пайплайн **{pipeline_name}** из проекта **{project_name}** в виде кода.\n\n"
            f"{key_hint}\n\n"
            "1. Вызови MCP tool **export_pipeline_as_code** (не только export_for_llm).\n"
            "2. Следуй полю **workflow** и данным **pipeline_spec** из ответа.\n"
            "3. Создай/обнови файлы в `pipelines/` и `handlers/` целевого проекта.\n\n"
            f"---\n\n{workflow}"
        )
