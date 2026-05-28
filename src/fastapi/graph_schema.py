"""Применение миграций схемы графа при старте API."""

from __future__ import annotations

from demo_auth import db

_MIGRATION_DONE = False


async def _column_exists(table: str, column: str) -> bool:
    row = await db.fetch_one(
        """
        SELECT 1 AS ok
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = $1
          AND column_name = $2
        """,
        table,
        column,
    )
    return row is not None


async def ensure_graph_schema() -> None:
    """Добавляет handles на links + системные node_types (идемпотентно)."""
    global _MIGRATION_DONE
    if _MIGRATION_DONE:
        return

    if not await _column_exists("links", "source_handle"):
        await db.execute(
            """
            ALTER TABLE public.links
            ADD COLUMN IF NOT EXISTS source_handle character varying(50) DEFAULT 'out'
            """
        )
    if not await _column_exists("links", "target_handle"):
        await db.execute(
            """
            ALTER TABLE public.links
            ADD COLUMN IF NOT EXISTS target_handle character varying(50) DEFAULT 'in'
            """
        )

    # Настройки узлов (например, LLM API key / model) — храним как jsonb
    if not await _column_exists("nodes", "node_config"):
        await db.execute(
            """
            ALTER TABLE public.nodes
            ADD COLUMN IF NOT EXISTS node_config jsonb DEFAULT '{}'::jsonb
            """
        )

    await db.execute(
        """
        UPDATE public.tools
        SET config = COALESCE(config, '{}'::jsonb) || '{"react_component":"workflow","color":"#3d5afe","inputs":[{"id":"in","label":"In"}],"outputs":[{"id":"out","label":"Out"}]}'::jsonb
        WHERE name IN ('llm', 'calendar_api', 'scheduler', 'notifier')
          AND (config IS NULL OR config = '{}'::jsonb OR NOT (config ? 'react_component'))
        """
    )

    # LLM — отдельный react_component с настройками
    await db.execute(
        """
        UPDATE public.tools
        SET config = COALESCE(config, '{}'::jsonb) || '{"react_component":"llm","color":"#3d5afe","inputs":[{"id":"in","label":"In"}],"outputs":[{"id":"out","label":"Out"}]}'::jsonb
        WHERE name = 'llm'
          AND (config IS NULL OR config = '{}'::jsonb OR NOT (config ? 'react_component') OR (config->>'react_component') <> 'llm')
        """
    )

    await db.execute(
        """
        INSERT INTO public.tools (name, config)
        SELECT 'branch_router', '{"react_component":"branch","color":"#7c4dff","inputs":[{"id":"in","label":"In"}],"outputs":[{"id":"yes","label":"Да"},{"id":"no","label":"Нет"},{"id":"error","label":"Ошибка"}]}'::jsonb
        WHERE NOT EXISTS (SELECT 1 FROM public.tools WHERE name = 'branch_router')
        """
    )

    await db.execute(
        """
        INSERT INTO public.tools (name, config)
        SELECT 'subpipeline', '{"react_component":"subpipeline","color":"#009688","inputs":[{"id":"in","label":"In"}],"outputs":[{"id":"out","label":"Out"}]}'::jsonb
        WHERE NOT EXISTS (SELECT 1 FROM public.tools WHERE name = 'subpipeline')
        """
    )

    await db.execute(
        """
        INSERT INTO public.node_types (tool_id, name, description)
        SELECT t.id, 'branch', 'Ветвление: да / нет / ошибка'
        FROM public.tools t
        WHERE t.name = 'branch_router'
          AND NOT EXISTS (
              SELECT 1 FROM public.node_types nt
              WHERE nt.name = 'branch' AND nt.tool_id = t.id
          )
        """
    )

    await db.execute(
        """
        INSERT INTO public.node_types (tool_id, name, description)
        SELECT t.id, 'subpipeline', 'Запуск вложенного пайплайна как блока'
        FROM public.tools t
        WHERE t.name = 'subpipeline'
          AND NOT EXISTS (
              SELECT 1 FROM public.node_types nt
              WHERE nt.name = 'subpipeline' AND nt.tool_id = t.id
          )
        """
    )

    # Базовые шаги агентных пайплайнов (если дамп БД без node_types)
    await db.execute(
        """
        INSERT INTO public.tools (name, config)
        SELECT v.name, v.config::jsonb
        FROM (VALUES
            ('llm', '{"model":"local","react_component":"workflow","color":"#3d5afe","inputs":[{"id":"in","label":"In"}],"outputs":[{"id":"out","label":"Out"}]}'),
            ('calendar_api', '{"react_component":"workflow","color":"#ff9800","inputs":[{"id":"in","label":"In"}],"outputs":[{"id":"out","label":"Out"}]}'),
            ('scheduler', '{"react_component":"workflow","color":"#ffc107","inputs":[{"id":"in","label":"In"}],"outputs":[{"id":"out","label":"Out"}]}'),
            ('notifier', '{"react_component":"workflow","color":"#4caf50","inputs":[{"id":"in","label":"In"}],"outputs":[{"id":"out","label":"Out"}]}')
        ) AS v(name, config)
        WHERE NOT EXISTS (SELECT 1 FROM public.tools t WHERE t.name = v.name)
        """
    )

    agent_steps = [
        ("llm", "parse_request", "Парсинг запроса (LLM)"),
        ("calendar_api", "check_availability", "Проверка календаря"),
        ("scheduler", "find_best_time", "Поиск времени"),
        ("notifier", "send_notification", "Уведомление пользователю"),
    ]
    for tool_name, nt_name, descr in agent_steps:
        await db.execute(
            """
            INSERT INTO public.node_types (tool_id, name, description)
            SELECT t.id, $2::varchar, $3::text
            FROM public.tools t
            WHERE t.name = $1::varchar
              AND NOT EXISTS (
                  SELECT 1 FROM public.node_types nt
                  WHERE nt.name = $2::varchar
              )
            """,
            tool_name,
            nt_name,
            descr,
        )

    _MIGRATION_DONE = True
