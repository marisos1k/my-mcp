from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from api_folder.api_module import APIKeyManager
from db_folder.db_connection import ConnectionDB
from mcp_app.bundled_skills import list_skill_names, load_skill_body
from mcp_app.context import AppContext
from mcp_app.views import public_pipeline_row, public_structure
from pipline_folder.pipeline_collector import execution_sequence_walk


async def _require_pipeline(
    db: ConnectionDB, user_id: int, project_name: str, pipeline_name: str
) -> int:
    row = await db.fetch_one(
        'SELECT p.pipeline_id FROM "Pipeline" p '
        'JOIN "Project" pr ON pr.project_id = p.fk_project_id '
        'WHERE pr.fk_user_id = $1 AND TRIM(pr.name) = $2 AND TRIM(p.name) = $3',
        user_id, project_name.strip(), pipeline_name.strip(),
    )
    if not row:
        raise ValueError(
            f"Pipeline {pipeline_name!r} in project {project_name!r} not found or access denied"
        )
    return row["pipeline_id"]


def register_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        description=(
            "Bootstrap: выпустить новый API-ключ для пользователя по email+password — без "
            "необходимости иметь существующий api_key или прямой доступ к БД. Ключ возвращается "
            "ОДИН РАЗ, сохраните его — он нужен для всех остальных tools."
        )
    )
    async def create_api_key(
        email: str,
        password: str,
        key_name: str,
        ctx: Context[ServerSession, AppContext],
    ) -> dict[str, Any]:
        app = ctx.request_context.lifespan_context
        user = await app.db.fetch_one(
            'SELECT user_id AS id, password_hash AS pass_hash FROM "User" WHERE email = $1',
            email,
        )
        if not user or not APIKeyManager.verify_password(password, user["pass_hash"]):
            raise ValueError("Invalid email or password")
        api_key = await app.auth.api_manager.create_api_key(user["id"], key_name)
        return {"api_key": api_key, "key_name": key_name, "email": email}

    @mcp.tool(description="Список API-ключей текущего пользователя (имя, префикс, статус), без хэшей.")
    async def list_api_keys(
        api_key: str,
        ctx: Context[ServerSession, AppContext],
    ) -> list[dict[str, Any]]:
        app = ctx.request_context.lifespan_context
        user = await app.auth.authenticate(api_key)
        rows = await app.auth.api_manager.list_user_keys(user["id"])
        return [
            {
                "key_name": row["key_name"],
                "key_prefix": row["key_prefix"],
                "is_active": row["is_active"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "last_used_at": row["last_used_at"].isoformat() if row["last_used_at"] else None,
            }
            for row in rows
        ]

    @mcp.tool(description="Отозвать (деактивировать) именованный API-ключ текущего пользователя.")
    async def revoke_api_key(
        api_key: str,
        key_name: str,
        ctx: Context[ServerSession, AppContext],
    ) -> dict[str, Any]:
        app = ctx.request_context.lifespan_context
        user = await app.auth.authenticate(api_key)
        await app.auth.api_manager.revoke_api_key(user["id"], key_name)
        return {"revoked": key_name, "email": user["email"]}

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
        language: str = "python",
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
        skill_name = f"pipeline-to-{language}"
        try:
            workflow = load_skill_body(skill_name)
        except FileNotFoundError:
            prefix = "pipeline-to-"
            langs = [n[len(prefix):] for n in list_skill_names() if n.startswith(prefix)]
            raise ValueError(
                f"Unknown language {language!r}. Available: {', '.join(langs)}"
            )
        _ext = {"typescript": ".ts", "javascript": ".js"}.get(language, ".py")
        _js_like = language in ("typescript", "javascript")
        return {
            "pipeline_spec": spec,
            "workflow": workflow,
            "output_hint": {
                "pipeline_file": f"src/pipelines/{pl}{_ext}" if _js_like else f"pipelines/{pl}{_ext}",
                "handlers_dir": "src/handlers/" if _js_like else "handlers/",
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

    # ── Metadata tools ────────────────────────────────────────────────────────

    @mcp.tool(
        description="Список доступных языков для export_pipeline_as_code (python, typescript, javascript…)."
    )
    async def list_languages(
        ctx: Context[ServerSession, AppContext],
    ) -> list[str]:
        prefix = "pipeline-to-"
        return sorted(
            name[len(prefix):]
            for name in list_skill_names()
            if name.startswith(prefix)
        )

    @mcp.tool(
        description=(
            "Список всех типов узлов (NodeType) с их инструментом и описанием. "
            "Нужен перед create_node, чтобы выбрать правильный node_type_name."
        )
    )
    async def list_node_types(
        ctx: Context[ServerSession, AppContext],
    ) -> list[dict[str, Any]]:
        app = ctx.request_context.lifespan_context
        rows = await app.db.fetch(
            'SELECT TRIM(nt.name) AS name, TRIM(nt.desc) AS description, TRIM(t.name) AS tool '
            'FROM "NodeType" nt JOIN "Tool" t ON t.tool_id = nt.fk_tool_id '
            'ORDER BY TRIM(t.name), TRIM(nt.name)'
        )
        return [dict(r) for r in rows]

    # ── Write tools ───────────────────────────────────────────────────────────

    @mcp.tool(description="Создать новый проект для текущего пользователя.")
    async def create_project(
        api_key: str,
        name: str,
        ctx: Context[ServerSession, AppContext],
    ) -> dict[str, Any]:
        app = ctx.request_context.lifespan_context
        user = await app.auth.authenticate(api_key)
        try:
            await app.db.fetch_one(
                'INSERT INTO "Project" (fk_user_id, name) VALUES ($1, $2) RETURNING project_id',
                user["id"], name.strip(),
            )
        except Exception as e:
            msg = str(e).lower()
            if "unique" in msg or "duplicate" in msg:
                raise ValueError(f"Project name {name!r} is already taken") from e
            raise
        return {"project_name": name.strip(), "created": True}

    @mcp.tool(
        description=(
            "Создать пайплайн в существующем проекте. "
            "max_time (сек, default 120), max_cost (у.е., default 100), "
            "max_reject (доля 0..1, default 0.15) — опциональны."
        )
    )
    async def create_pipeline(
        api_key: str,
        project_name: str,
        pipeline_name: str,
        ctx: Context[ServerSession, AppContext],
        max_time: float = 120.0,
        max_cost: float = 100.0,
        max_reject: float = 0.15,
    ) -> dict[str, Any]:
        app = ctx.request_context.lifespan_context
        user = await app.auth.authenticate(api_key)
        project = await app.db.fetch_one(
            'SELECT project_id FROM "Project" WHERE fk_user_id = $1 AND TRIM(name) = $2',
            user["id"], project_name.strip(),
        )
        if not project:
            raise ValueError(f"Project {project_name!r} not found or access denied")
        try:
            await app.db.fetch_one(
                'INSERT INTO "Pipeline" (fk_project_id, name, max_time, max_cost, max_reject, score) '
                'VALUES ($1, $2, $3, $4, $5, 0) RETURNING pipeline_id',
                project["project_id"], pipeline_name.strip(), max_time, max_cost, max_reject,
            )
        except Exception as e:
            msg = str(e).lower()
            if "unique" in msg or "duplicate" in msg:
                raise ValueError(
                    f"Pipeline {pipeline_name!r} already exists in project {project_name!r}"
                ) from e
            raise
        return {
            "project_name": project_name.strip(),
            "pipeline_name": pipeline_name.strip(),
            "created": True,
        }

    @mcp.tool(
        description=(
            "Добавить узел в пайплайн. node_type_name — из list_node_types. "
            "Возвращает step_slot нового узла (используй в connect_nodes)."
        )
    )
    async def create_node(
        api_key: str,
        project_name: str,
        pipeline_name: str,
        node_type_name: str,
        ctx: Context[ServerSession, AppContext],
        label: str | None = None,
        x: float | None = None,
        y: float | None = None,
    ) -> dict[str, Any]:
        app = ctx.request_context.lifespan_context
        user = await app.auth.authenticate(api_key)
        pipeline_id = await _require_pipeline(
            app.db, user["id"], project_name, pipeline_name
        )
        node_type = await app.db.fetch_one(
            'SELECT type_id FROM "NodeType" WHERE TRIM(name) = $1',
            node_type_name.strip(),
        )
        if not node_type:
            raise ValueError(
                f"Node type {node_type_name!r} not found — call list_node_types for options"
            )
        if x is None or y is None:
            count_row = await app.db.fetch_one(
                'SELECT COUNT(*) AS cnt FROM "Node" WHERE fk_pipeline_id = $1',
                pipeline_id,
            )
            n = int(count_row["cnt"])
            x = x if x is not None else float(200 + n * 380)
            y = y if y is not None else 200.0

        node_label = label or node_type_name
        ui = {"label": node_label, "position": {"x": x, "y": y}}

        await app.db.fetch_one(
            'INSERT INTO "Node" (fk_pipeline_id, fk_type_id, top_k, output_json, ui_json) '
            'VALUES ($1, $2, 1, $3::jsonb, $4::jsonb) RETURNING node_id',
            pipeline_id, node_type["type_id"],
            json.dumps({}), json.dumps(ui),
        )
        count_row = await app.db.fetch_one(
            'SELECT COUNT(*) AS cnt FROM "Node" WHERE fk_pipeline_id = $1',
            pipeline_id,
        )
        return {
            "step_slot": int(count_row["cnt"]),
            "node_type": node_type_name.strip(),
            "label": node_label,
        }

    @mcp.tool(
        description=(
            "Соединить два узла рёбром. from_slot / to_slot — step_slot из create_node "
            "или get_pipeline_structure. "
            "from_port: 'out' (default), 'yes', 'no', 'error'. to_port: 'in' (default)."
        )
    )
    async def connect_nodes(
        api_key: str,
        project_name: str,
        pipeline_name: str,
        from_slot: int,
        to_slot: int,
        ctx: Context[ServerSession, AppContext],
        from_port: str = "out",
        to_port: str = "in",
    ) -> dict[str, Any]:
        app = ctx.request_context.lifespan_context
        user = await app.auth.authenticate(api_key)
        pipeline_id = await _require_pipeline(
            app.db, user["id"], project_name, pipeline_name
        )
        rows = await app.db.fetch(
            'SELECT node_id FROM "Node" WHERE fk_pipeline_id = $1 ORDER BY node_id',
            pipeline_id,
        )
        n = len(rows)
        if from_slot < 1 or from_slot > n:
            raise ValueError(f"from_slot {from_slot} out of range 1..{n}")
        if to_slot < 1 or to_slot > n:
            raise ValueError(f"to_slot {to_slot} out of range 1..{n}")

        from_node_id = rows[from_slot - 1]["node_id"]
        to_node_id = rows[to_slot - 1]["node_id"]

        await app.db.fetch_one(
            'INSERT INTO "Edge" (fk_from_node, fk_to_node, source_handle, target_handle) '
            'VALUES ($1, $2, $3, $4) RETURNING edge_id',
            from_node_id, to_node_id, from_port, to_port,
        )
        return {
            "connected": True,
            "from_slot": from_slot,
            "to_slot": to_slot,
            "from_port": from_port,
            "to_port": to_port,
        }
