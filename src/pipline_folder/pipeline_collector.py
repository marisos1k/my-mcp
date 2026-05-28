from __future__ import annotations

from typing import Any, Dict, Optional

from api_folder.api_module import APIKeyManager
from db_folder.db_connection import ConnectionDB
from pipline_folder.auth_middleware import AuthMiddleware
from pipline_folder.graph_export import (
    normalize_node,
    pipeline_spec_from_graph,
)
from pipline_folder.graph_executor import (
    build_execution_plan,
    connections_with_ports,
    execution_sequence_walk,
)
from pipline_folder.graph_slots import step_slots_by_node_id


def connections_with_step_slots(
    nodes: list[dict[str, Any]], links: list[dict[str, Any]]
) -> list[dict[str, int]]:
    slot = step_slots_by_node_id(nodes)
    return [
        {"from_step": slot[link["from_node"]], "to_step": slot[link["to_node"]]}
        for link in links
    ]


def blocks_ordered_with_slots(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Устаревший формат blocks (без node_config). Оставлен для совместимости."""
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
                np.name AS nested_pipeline_name,
                nt.name as type_name,
                nt.description as type_description,
                t.name as tool_name,
                t.config as tool_config
            FROM nodes n
            LEFT JOIN pipelines np ON np.id = n.nested_pipeline_id
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

    async def _gather_nested_pipeline_specs(
        self,
        user_id: int,
        nodes: list[dict[str, Any]],
        *,
        seen_ids: set[int] | None = None,
    ) -> dict[str, dict[str, Any]]:
        seen = seen_ids or set()
        specs: dict[str, dict[str, Any]] = {}

        for n in nodes:
            nested_id = n.get("nested_pipeline_id")
            if not nested_id:
                continue
            nid = int(nested_id)
            if nid in seen:
                continue
            seen.add(nid)

            nested = await self._fetch_graph(user_id, nid)
            if not nested:
                continue

            name = nested["pipeline"]["name"]
            nn = [normalize_node(dict(x)) for x in nested["nodes"]]
            nl = [dict(x) for x in nested["links"]]
            inner = await self._gather_nested_pipeline_specs(user_id, nn, seen_ids=seen)
            spec = pipeline_spec_from_graph(
                nested["pipeline"], nn, nl, nested_specs=inner
            )
            spec["_raw_nodes"] = nn
            spec["_raw_links"] = nl
            specs[name] = spec
            specs.update(inner)

        return specs

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

    async def export_structure_to_llm(self, structure: dict[str, Any]) -> dict[str, Any]:
        """Полный экспорт: node_config, порты, nested pipelines, execution_plan."""
        user = structure.get("user") or {}
        user_id = int(user["id"])
        nodes = [normalize_node(dict(n)) for n in structure["nodes"]]
        links = [dict(l) for l in structure["links"]]
        nested_specs = await self._gather_nested_pipeline_specs(user_id, nodes)
        return pipeline_spec_from_graph(
            structure["pipeline"],
            nodes,
            links,
            nested_specs=nested_specs,
        )

    def pipeline_to_llm_json(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Синхронный экспорт без nested (legacy). Используйте export_structure_to_llm."""
        if not data:
            return {}
        nodes = [normalize_node(dict(n)) for n in data["nodes"]]
        links = [dict(l) for l in data["links"]]
        return pipeline_spec_from_graph(data["pipeline"], nodes, links)

    async def export_pipeline_to_llm(
        self, pipeline_id: int
    ) -> Optional[Dict[str, Any]]:
        structure = await self.get_structure_of_pipeline(pipeline_id)
        if not structure:
            return None
        return await self.export_structure_to_llm(structure)
