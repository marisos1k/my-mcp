from __future__ import annotations

from typing import Any, Dict, Optional

from api_folder.api_module import APIKeyManager
from db_folder.db_connection import ConnectionDB
from json_utils import json_safe
from pipline_folder.auth_middleware import AuthMiddleware


def step_slots_by_node_id(nodes: list[dict[str, Any]]) -> dict[int, int]:
    """Стабильные порядковые слоты 1..N по возрастанию внутреннего id узла (не отдаётся наружу как id сущности)."""
    sorted_nodes = sorted(nodes, key=lambda n: n["id"])
    return {n["id"]: i + 1 for i, n in enumerate(sorted_nodes)}


def connections_with_step_slots(
    nodes: list[dict[str, Any]], links: list[dict[str, Any]]
) -> list[dict[str, int]]:
    slot = step_slots_by_node_id(nodes)
    return [
        {"from_step": slot[link["from_node"]], "to_step": slot[link["to_node"]]}
        for link in links
    ]


def execution_sequence_walk(
    nodes: list[dict[str, Any]], links: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Порядок обхода по рёбрам от стартового узла (нет входящих рёбер в этот пайплайн)."""
    if not nodes:
        return []
    slot = step_slots_by_node_id(nodes)
    nodes_dict = {node["id"]: node for node in nodes}
    to_nodes = {link["to_node"] for link in links}
    start_node = next((node for node in nodes if node["id"] not in to_nodes), None)
    if not start_node:
        start_node = sorted(nodes, key=lambda n: n["id"])[0]

    out: list[dict[str, Any]] = []
    current_id: int | None = start_node["id"]
    while current_id is not None:
        node = nodes_dict[current_id]
        out.append(
            {
                "step_slot": slot[current_id],
                "step": node["type_name"],
                "tool": node["tool_name"],
                "description": node.get("type_description"),
            }
        )
        next_link = next(
            (link for link in links if link["from_node"] == current_id), None
        )
        current_id = next_link["to_node"] if next_link else None
    return out


def blocks_ordered_with_slots(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    slot = step_slots_by_node_id(nodes)
    ordered = sorted(nodes, key=lambda n: n["id"])
    return [
        {
            "step_slot": slot[n["id"]],
            "name": n["type_name"],
            "description": n.get("type_description"),
            "tool": n["tool_name"],
        }
        for n in ordered
    ]


class PipelineCollector:
    def __init__(
        self, db_conn: ConnectionDB, auth_middleware: AuthMiddleware, api_key: str
    ):
        self.db_conn = db_conn
        self.auth_middleware = auth_middleware
        self.api_key = api_key

    async def _authenticate(self) -> dict:
        return await self.auth_middleware.authenticate(self.api_key)

    async def get_pipelines(self, project_name: str | None = None):
        """Получить пайплайны пользователя; опционально только в проекте с точным именем."""
        user = await self._authenticate()
        pname = project_name.strip() if project_name else None
        if pname == "":
            pname = None

        if pname:
            return await self.db_conn.fetch(
                """
                SELECT p.*, pr.name as project_name
                FROM pipelines p
                JOIN projects pr ON pr.id = p.project_id
                WHERE pr.user_id = $1 AND pr.name = $2
                ORDER BY p.name
                """,
                user["id"],
                pname,
            )

        return await self.db_conn.fetch(
            """
            SELECT p.*, pr.name as project_name
            FROM pipelines p
            JOIN projects pr ON pr.id = p.project_id
            WHERE pr.user_id = $1
            ORDER BY pr.name, p.name
            """,
            user["id"],
        )

    async def get_project_names(self) -> list[str]:
        user = await self._authenticate()
        rows = await self.db_conn.fetch(
            """
            SELECT pr.name
            FROM projects pr
            WHERE pr.user_id = $1
            ORDER BY pr.name
            """,
            user["id"],
        )
        return [r["name"] for r in rows]

    async def find_pipelines_by_name(self, query_substring: str):
        """Пайплайны пользователя по подстроке имени (ILIKE)."""
        user = await self._authenticate()
        pattern = f"%{query_substring.strip()}%"
        return await self.db_conn.fetch(
            """
            SELECT p.*, pr.name as project_name
            FROM pipelines p
            JOIN projects pr ON pr.id = p.project_id
            WHERE pr.user_id = $1 AND p.name ILIKE $2
            ORDER BY pr.name, p.name
            """,
            user["id"],
            pattern,
        )

    async def _list_pipeline_ids_for_names(
        self, user_id: int, project_name: str, pipeline_name: str
    ) -> list[int]:
        rows = await self.db_conn.fetch(
            """
            SELECT p.id
            FROM pipelines p
            JOIN projects pr ON pr.id = p.project_id
            WHERE pr.user_id = $1 AND pr.name = $2 AND p.name = $3
            ORDER BY p.id
            """,
            user_id,
            project_name,
            pipeline_name,
        )
        return [int(r["id"]) for r in rows]

    async def _fetch_graph(
        self, user_id: int, pipeline_id: int
    ) -> dict[str, Any] | None:
        pipeline = await self.db_conn.fetch_one(
            """
            SELECT p.*, pr.name as project_name
            FROM pipelines p
            JOIN projects pr ON pr.id = p.project_id
            WHERE p.id = $1 AND pr.user_id = $2
            """,
            pipeline_id,
            user_id,
        )
        if not pipeline:
            return None

        nodes = await self.db_conn.fetch(
            """
            SELECT
                n.*,
                nt.name as type_name,
                nt.description as type_description,
                t.name as tool_name
            FROM nodes n
            JOIN node_types nt ON nt.id = n.type_id
            JOIN tools t ON t.id = nt.tool_id
            WHERE n.pipeline_id = $1
            ORDER BY n.id
            """,
            pipeline_id,
        )

        links = await self.db_conn.fetch(
            """
            SELECT l.*
            FROM links l
            JOIN nodes n ON n.id = l.from_node
            WHERE n.pipeline_id = $1
            """,
            pipeline_id,
        )

        node_list = [dict(n) for n in nodes]
        link_list = [dict(l) for l in links]
        return {
            "pipeline": dict(pipeline),
            "nodes": node_list,
            "links": link_list,
            "statistics": {
                "total_nodes": len(node_list),
                "total_links": len(link_list),
            },
        }

    async def _structure_for_user_pipeline(
        self, user: dict[str, Any], pipeline_id: int
    ) -> dict[str, Any] | None:
        body = await self._fetch_graph(user["id"], pipeline_id)
        if not body:
            return None
        return {"user": dict(user), **body}

    async def get_structure_of_pipeline(self, pipeline_id: int) -> dict[str, Any] | None:
        user = await self._authenticate()
        return await self._structure_for_user_pipeline(user, pipeline_id)

    async def load_structure_by_project_and_pipeline(
        self, project_name: str, pipeline_name: str
    ) -> dict[str, Any] | None:
        """Одна аутентификация + загрузка графа; при дубликатах имён — ValueError."""
        user = await self._authenticate()
        pr_name = project_name.strip()
        pl_name = pipeline_name.strip()
        if not pr_name or not pl_name:
            raise ValueError("Нужны непустые project_name и pipeline_name")

        ids = await self._list_pipeline_ids_for_names(user["id"], pr_name, pl_name)
        if not ids:
            return None
        if len(ids) > 1:
            raise ValueError(
                "Найдено несколько пайплайнов с этой парой project_name и pipeline_name; "
                "нужна уникальность в базе."
            )
        return await self._structure_for_user_pipeline(user, ids[0])

    def pipeline_to_llm_json(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not data:
            return {}

        nodes = data["nodes"]
        links = data["links"]
        p = data["pipeline"]

        return {
            "project_name": p.get("project_name"),
            "pipeline_name": p["name"],
            "description": p.get("report"),
            "limits": {
                "max_time": json_safe(p.get("max_time")),
                "max_cost": json_safe(p.get("max_cost")),
                "max_fail_percent": json_safe(p.get("max_fail_percent")),
                "score": json_safe(p.get("score")),
            },
            "blocks": blocks_ordered_with_slots(nodes),
            "connections": connections_with_step_slots(nodes, links),
            "execution_sequence": execution_sequence_walk(nodes, links),
        }

    async def export_pipeline_to_llm(
        self, pipeline_id: int
    ) -> Optional[Dict[str, Any]]:
        structure = await self.get_structure_of_pipeline(pipeline_id)
        if not structure:
            return None
        return self.pipeline_to_llm_json(structure)

    def export_structure_to_llm(self, structure: dict[str, Any]) -> dict[str, Any]:
        """Экспорт без повторного запроса к БД (ожидает полный structure с nodes/links/pipeline)."""
        return self.pipeline_to_llm_json(structure)
