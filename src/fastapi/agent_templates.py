"""Шаблоны базовых агентных пайплайнов для быстрого старта в редакторе."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from demo_auth import db
from pipline_folder.port_schema import default_source_handle, default_target_handle, resolve_port_schema

# type_name должен существовать в node_types (см. ensure_graph_schema)
AGENT_TEMPLATES: dict[str, dict[str, Any]] = {
    "simple_llm": {
        "title": "Простой LLM-агент",
        "description": "Один шаг: обработка запроса моделью.",
        "category": "agent",
        "report": "Базовый LLM-агент",
        "nodes": [
            {
                "type_name": "parse_request",
                "label": "LLM",
                "x": 200,
                "y": 160,
            },
        ],
        "edges": [],
    },
    "llm_notify": {
        "title": "LLM → уведомление",
        "description": "Обработка запроса и ответ пользователю.",
        "category": "agent",
        "report": "Агент: LLM и notifier",
        "nodes": [
            {"type_name": "parse_request", "label": "Обработка", "x": 120, "y": 160},
            {"type_name": "send_notification", "label": "Ответ", "x": 380, "y": 160},
        ],
        "edges": [{"from": 0, "to": 1}],
    },
    "schedule_agent": {
        "title": "Агент расписания",
        "description": "Парсинг → календарь → слот → уведомление (классический schedule_agent).",
        "category": "agent",
        "report": "ИИ-агент для управления расписанием",
        "nodes": [
            {"type_name": "parse_request", "label": "Парсинг запроса", "x": 80, "y": 160},
            {"type_name": "check_availability", "label": "Календарь", "x": 280, "y": 160},
            {"type_name": "find_best_time", "label": "Выбор времени", "x": 480, "y": 160},
            {"type_name": "send_notification", "label": "Уведомление", "x": 680, "y": 160},
        ],
        "edges": [
            {"from": 0, "to": 1},
            {"from": 1, "to": 2},
            {"from": 2, "to": 3},
        ],
    },
    "llm_router": {
        "title": "Агент с ветвлением",
        "description": "LLM планирует → branch → два сценария (да / нет).",
        "category": "agent",
        "report": "Агент с условным ветвлением",
        "nodes": [
            {"type_name": "parse_request", "label": "LLM / план", "x": 80, "y": 200},
            {"type_name": "branch", "label": "Решение", "x": 300, "y": 200},
            {"type_name": "send_notification", "label": "Успех", "x": 520, "y": 120},
            {"type_name": "find_best_time", "label": "Альтернатива", "x": 520, "y": 280},
        ],
        "edges": [
            {"from": 0, "to": 1},
            {"from": 1, "to": 2, "source_handle": "yes", "target_handle": "in"},
            {"from": 1, "to": 3, "source_handle": "no", "target_handle": "in"},
        ],
    },
    "error_handler_agent": {
        "title": "Агент с обработкой ошибок",
        "description": "LLM → branch (да / нет / ошибка) → разные действия.",
        "category": "agent",
        "report": "Агент с веткой error",
        "nodes": [
            {"type_name": "parse_request", "label": "LLM", "x": 60, "y": 200},
            {"type_name": "branch", "label": "Статус", "x": 260, "y": 200},
            {"type_name": "send_notification", "label": "OK", "x": 480, "y": 80},
            {"type_name": "find_best_time", "label": "Повтор", "x": 480, "y": 200},
            {"type_name": "check_availability", "label": "Ошибка", "x": 480, "y": 320},
        ],
        "edges": [
            {"from": 0, "to": 1},
            {"from": 1, "to": 2, "source_handle": "yes"},
            {"from": 1, "to": 3, "source_handle": "no"},
            {"from": 1, "to": 4, "source_handle": "error"},
        ],
    },
}


def list_agent_templates() -> list[dict[str, Any]]:
    return [
        {
            "id": tid,
            "title": t["title"],
            "description": t["description"],
            "category": t.get("category", "agent"),
            "node_count": len(t["nodes"]),
            "edge_count": len(t["edges"]),
        }
        for tid, t in AGENT_TEMPLATES.items()
    ]


def get_agent_template(template_id: str) -> dict[str, Any]:
    tmpl = AGENT_TEMPLATES.get(template_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail=f"Unknown template: {template_id}")
    return tmpl


async def _type_map_for_names(names: set[str]) -> dict[str, dict[str, Any]]:
    rows = await db.fetch(
        """
        SELECT nt.id, nt.name, nt.description, t.config AS tool_config
        FROM node_types nt
        JOIN tools t ON t.id = nt.tool_id
        WHERE nt.name = ANY($1::text[])
        """,
        list(names),
    )
    found = {r["name"]: dict(r) for r in rows}
    missing = names - set(found.keys())
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Node types not found in catalog: {', '.join(sorted(missing))}. "
            "Restart API to apply schema migrations.",
        )
    return found


async def apply_agent_template(pipeline_id: int, template_id: str) -> None:
    """Создаёт узлы и связи шаблона в пустом (или перезаписываемом) пайплайне."""
    tmpl = get_agent_template(template_id)
    type_names = {n["type_name"] for n in tmpl["nodes"]}
    type_map = await _type_map_for_names(type_names)

    async with db.pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "DELETE FROM links WHERE from_node IN (SELECT id FROM nodes WHERE pipeline_id = $1)",
                pipeline_id,
            )
            await conn.execute("DELETE FROM nodes WHERE pipeline_id = $1", pipeline_id)

            db_node_ids: list[int] = []
            for spec in tmpl["nodes"]:
                tname = spec["type_name"]
                tid = int(type_map[tname]["id"])
                row = await conn.fetchrow(
                    """
                    INSERT INTO nodes (pipeline_id, type_id, coords, report)
                    VALUES ($1, $2, point($3, $4), $5)
                    RETURNING id
                    """,
                    pipeline_id,
                    tid,
                    float(spec["x"]),
                    float(spec["y"]),
                    spec.get("label"),
                )
                db_node_ids.append(int(row["id"]))

            for edge in tmpl["edges"]:
                src = db_node_ids[int(edge["from"])]
                tgt = db_node_ids[int(edge["to"])]
                src_type = type_map[tmpl["nodes"][edge["from"]]["type_name"]]
                tgt_type = type_map[tmpl["nodes"][edge["to"]]["type_name"]]
                src_schema = resolve_port_schema(
                    src_type.get("tool_config"), src_type.get("name")
                )
                tgt_schema = resolve_port_schema(
                    tgt_type.get("tool_config"), tgt_type.get("name")
                )
                sh = edge.get("source_handle") or default_source_handle(src_schema)
                th = edge.get("target_handle") or default_target_handle(tgt_schema)
                await conn.execute(
                    """
                    INSERT INTO links (from_node, to_node, source_handle, target_handle)
                    VALUES ($1, $2, $3, $4)
                    """,
                    src,
                    tgt,
                    sh,
                    th,
                )
