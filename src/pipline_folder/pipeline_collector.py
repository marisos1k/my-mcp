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

# ── SQL fragments aligned with BrAIniac's Prisma schema ──────────────────────
# Tables: "User", "Project", "Pipeline", "NodeType", "Tool", "Node", "Edge"
# All CHAR(N) name fields are TRIMmed; PKs aliased to legacy short names.

_PIPELINE_COLS = """
    p.pipeline_id        AS id,
    TRIM(p.name)         AS name,
    p.max_time,
    p.max_cost,
    p.max_reject         AS max_fail_percent,
    p.score,
    NULL::text           AS report,
    TRIM(pr.name)        AS project_name
"""

_NODE_COLS = """
    n.node_id                          AS id,
    n.fk_pipeline_id                   AS pipeline_id,
    n.fk_type_id                       AS type_id,
    n.fk_sub_pipeline                  AS nested_pipeline_id,
    n.top_k,
    n.output_json                      AS node_config,
    n.ui_json->>'label'                AS report,
    TRIM(np.name)                      AS nested_pipeline_name,
    TRIM(nt.name)                      AS type_name,
    TRIM(nt.desc)                      AS type_description,
    nt.config_json                     AS tool_config,
    TRIM(t.name)                       AS tool_name
"""

_NODE_JOINS = """
    LEFT JOIN "Pipeline"  np ON np.pipeline_id = n.fk_sub_pipeline
    JOIN      "NodeType"  nt ON nt.type_id     = n.fk_type_id
    JOIN      "Tool"       t ON t.tool_id      = nt.fk_tool_id
"""


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
        user = await self._authenticate()
        pname = project_name.strip() if project_name else None
        if pname == "":
            pname = None

        if pname:
            return await self.db_conn.fetch(
                f"""
                SELECT {_PIPELINE_COLS}
                FROM "Pipeline" p
                JOIN "Project" pr ON pr.project_id = p.fk_project_id
                WHERE pr.fk_user_id = $1 AND TRIM(pr.name) = $2
                ORDER BY TRIM(p.name)
                """,
                user["id"],
                pname,
            )

        return await self.db_conn.fetch(
            f"""
            SELECT {_PIPELINE_COLS}
            FROM "Pipeline" p
            JOIN "Project" pr ON pr.project_id = p.fk_project_id
            WHERE pr.fk_user_id = $1
            ORDER BY TRIM(pr.name), TRIM(p.name)
            """,
            user["id"],
        )

    async def get_project_names(self) -> list[str]:
        user = await self._authenticate()
        rows = await self.db_conn.fetch(
            """
            SELECT TRIM(pr.name) AS name
            FROM "Project" pr
            WHERE pr.fk_user_id = $1
            ORDER BY TRIM(pr.name)
            """,
            user["id"],
        )
        return [r["name"] for r in rows]

    async def find_pipelines_by_name(self, query_substring: str):
        user = await self._authenticate()
        pattern = f"%{query_substring.strip()}%"
        return await self.db_conn.fetch(
            f"""
            SELECT {_PIPELINE_COLS}
            FROM "Pipeline" p
            JOIN "Project" pr ON pr.project_id = p.fk_project_id
            WHERE pr.fk_user_id = $1 AND TRIM(p.name) ILIKE $2
            ORDER BY TRIM(pr.name), TRIM(p.name)
            """,
            user["id"],
            pattern,
        )

    async def _list_pipeline_ids_for_names(
        self, user_id: int, project_name: str, pipeline_name: str
    ) -> list[int]:
        rows = await self.db_conn.fetch(
            """
            SELECT p.pipeline_id AS id
            FROM "Pipeline" p
            JOIN "Project" pr ON pr.project_id = p.fk_project_id
            WHERE pr.fk_user_id = $1
              AND TRIM(pr.name) = $2
              AND TRIM(p.name)  = $3
            ORDER BY p.pipeline_id
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
            f"""
            SELECT {_PIPELINE_COLS}
            FROM "Pipeline" p
            JOIN "Project" pr ON pr.project_id = p.fk_project_id
            WHERE p.pipeline_id = $1 AND pr.fk_user_id = $2
            """,
            pipeline_id,
            user_id,
        )
        if not pipeline:
            return None

        nodes = await self.db_conn.fetch(
            f"""
            SELECT {_NODE_COLS}
            FROM "Node" n
            {_NODE_JOINS}
            WHERE n.fk_pipeline_id = $1
            ORDER BY n.node_id
            """,
            pipeline_id,
        )

        links = await self.db_conn.fetch(
            """
            SELECT
                e.edge_id        AS id,
                e.fk_from_node   AS from_node,
                e.fk_to_node     AS to_node,
                e.source_handle,
                e.target_handle
            FROM "Edge" e
            JOIN "Node" n ON n.node_id = e.fk_from_node
            WHERE n.fk_pipeline_id = $1
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
