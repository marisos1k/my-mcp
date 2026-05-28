"""API графа пайплайна для React Flow (узлы, связи, каталог типов, порты)."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel, Field, field_validator

from agent_templates import apply_agent_template, get_agent_template, list_agent_templates
from demo_auth import db
from graph_schema import ensure_graph_schema
from pipline_folder.graph_executor import build_execution_plan, connections_with_ports
from pipline_folder.pipeline_interface import compute_pipeline_interface, subpipeline_ui_schema
from pipline_folder.port_schema import (
    default_source_handle,
    default_target_handle,
    resolve_port_schema,
)

router = APIRouter(tags=["workflow-graph"])


def _parse_token(authorization: Optional[str], token: Optional[str]) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    if token:
        return token.strip()
    raise HTTPException(status_code=401, detail="Missing token")


def _user_id_from_token(authorization: Optional[str], token: Optional[str]) -> int:
    from jwt_auth import verify_token

    raw = _parse_token(authorization, token)
    payload = verify_token(raw)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return int(payload["sub"])


async def _ensure_pipeline_access(pipeline_id: int, user_id: int) -> dict[str, Any]:
    row = await db.fetch_one(
        """
        SELECT p.id, p.name, p.project_id, p.report, pr.name AS project_name
        FROM pipelines p
        JOIN projects pr ON pr.id = p.project_id
        WHERE p.id = $1 AND pr.user_id = $2
        """,
        pipeline_id,
        user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return dict(row)


def _coords_to_position(coords: Any) -> dict[str, float]:
    if coords is None:
        return {"x": 0, "y": 0}
    if hasattr(coords, "x") and hasattr(coords, "y"):
        return {"x": float(coords.x), "y": float(coords.y)}
    if isinstance(coords, (list, tuple)) and len(coords) >= 2:
        return {"x": float(coords[0]), "y": float(coords[1])}
    text = str(coords).strip("()")
    m = re.match(r"^\s*([-\d.]+)\s*,\s*([-\d.]+)\s*$", text)
    if m:
        return {"x": float(m.group(1)), "y": float(m.group(2))}
    return {"x": 0, "y": 0}


def _serialize_catalog_row(row: Any) -> dict[str, Any]:
    d = dict(row)
    schema = resolve_port_schema(d.get("tool_config"), d.get("name"))
    d["ui"] = schema
    d["react_component"] = schema.get("react_component", "workflow")
    if isinstance(d.get("tool_config"), dict):
        d["tool_config"] = d["tool_config"]
    elif d.get("tool_config") is not None:
        try:
            d["tool_config"] = json.loads(d["tool_config"]) if isinstance(d["tool_config"], str) else d["tool_config"]
        except json.JSONDecodeError:
            d["tool_config"] = {}
    return d


class CreatePipelineBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    report: Optional[str] = None


class CreateFromTemplateBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    template_id: str = Field(min_length=1, max_length=80)
    report: Optional[str] = None


def _parse_json_object(value: Any) -> dict[str, Any]:
    """asyncpg часто возвращает jsonb как str — приводим к dict."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


class GraphNodeIn(BaseModel):
    id: str
    type_id: int
    position: dict[str, float]
    label: Optional[str] = None
    nested_pipeline_id: Optional[int] = None
    node_config: Optional[dict[str, Any]] = None

    @field_validator("node_config", mode="before")
    @classmethod
    def _coerce_node_config(cls, value: Any) -> dict[str, Any] | None:
        if value is None:
            return None
        parsed = _parse_json_object(value)
        return parsed if parsed else {}


class GraphEdgeIn(BaseModel):
    source: str
    target: str
    source_handle: Optional[str] = None
    target_handle: Optional[str] = None


class SaveGraphBody(BaseModel):
    nodes: list[GraphNodeIn]
    edges: list[GraphEdgeIn]


@router.get("/catalog/agent-templates")
async def list_agent_templates_route(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
):
    _user_id_from_token(authorization, token)
    return list_agent_templates()


@router.get("/catalog/node-types")
async def list_node_types(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
):
    _user_id_from_token(authorization, token)
    rows = await db.fetch(
        """
        SELECT nt.id, nt.name, nt.description,
               t.id AS tool_id, t.name AS tool_name, t.config AS tool_config
        FROM node_types nt
        JOIN tools t ON t.id = nt.tool_id
        ORDER BY nt.id
        """
    )
    return [_serialize_catalog_row(r) for r in rows]


@router.post("/projects/{project_id}/pipelines")
async def create_pipeline(
    project_id: int,
    body: CreatePipelineBody,
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
):
    user_id = _user_id_from_token(authorization, token)
    project = await db.fetch_one(
        "SELECT id FROM projects WHERE id = $1 AND user_id = $2",
        project_id,
        user_id,
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    dup = await db.fetch_one(
        "SELECT id FROM pipelines WHERE project_id = $1 AND name = $2",
        project_id,
        body.name.strip(),
    )
    if dup:
        raise HTTPException(status_code=400, detail="Pipeline name already exists in project")

    await db.execute(
        """
        INSERT INTO pipelines (project_id, name, report)
        VALUES ($1, $2, $3)
        """,
        project_id,
        body.name.strip(),
        body.report,
    )
    pipeline = await db.fetch_one(
        "SELECT id, name, report FROM pipelines WHERE project_id = $1 AND name = $2",
        project_id,
        body.name.strip(),
    )
    return dict(pipeline)


@router.post("/projects/{project_id}/pipelines/from-template")
async def create_pipeline_from_template(
    project_id: int,
    body: CreateFromTemplateBody,
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
):
    """Создать пайплайн и заполнить граф по шаблону агентного workflow."""
    user_id = _user_id_from_token(authorization, token)
    get_agent_template(body.template_id)

    project = await db.fetch_one(
        "SELECT id FROM projects WHERE id = $1 AND user_id = $2",
        project_id,
        user_id,
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    name = body.name.strip()
    dup = await db.fetch_one(
        "SELECT id FROM pipelines WHERE project_id = $1 AND name = $2",
        project_id,
        name,
    )
    if dup:
        raise HTTPException(status_code=400, detail="Pipeline name already exists in project")

    tmpl = get_agent_template(body.template_id)
    report = body.report or tmpl.get("report")

    await db.execute(
        """
        INSERT INTO pipelines (project_id, name, report)
        VALUES ($1, $2, $3)
        """,
        project_id,
        name,
        report,
    )
    pipeline = await db.fetch_one(
        "SELECT id, name, report FROM pipelines WHERE project_id = $1 AND name = $2",
        project_id,
        name,
    )
    pipeline_id = int(pipeline["id"])
    await apply_agent_template(pipeline_id, body.template_id)

    return await get_pipeline_graph(
        pipeline_id, authorization=authorization, token=token
    )


async def _load_graph_rows(pipeline_id: int) -> tuple[list[Any], list[Any]]:
    await ensure_graph_schema()
    nodes = await db.fetch(
        """
        SELECT n.id, n.type_id, n.coords, n.report, n.nested_pipeline_id, n.node_config,
               np.name AS nested_pipeline_name,
               nt.name AS type_name, nt.description AS type_description,
               t.name AS tool_name, t.config AS tool_config
        FROM nodes n
        LEFT JOIN pipelines np ON np.id = n.nested_pipeline_id
        JOIN node_types nt ON nt.id = n.type_id
        JOIN tools t ON t.id = nt.tool_id
        WHERE n.pipeline_id = $1
        ORDER BY n.id
        """,
        pipeline_id,
    )
    links = await db.fetch(
        """
        SELECT l.id, l.from_node, l.to_node, l.source_handle, l.target_handle
        FROM links l
        JOIN nodes n ON n.id = l.from_node
        WHERE n.pipeline_id = $1
        """,
        pipeline_id,
    )
    norm_nodes = []
    for n in nodes:
        nd = dict(n)
        nd["node_config"] = _parse_json_object(nd.get("node_config"))
        norm_nodes.append(nd)
    return norm_nodes, links


_subpipeline_schema_cache: dict[int, dict[str, Any]] = {}


async def _schema_for_node(nd: dict[str, Any]) -> dict[str, Any]:
    type_name = nd.get("type_name")
    nested_id = nd.get("nested_pipeline_id")
    if type_name == "subpipeline" and nested_id:
        nid = int(nested_id)
        if nid not in _subpipeline_schema_cache:
            nested_nodes, nested_links = await _load_graph_rows(nid)
            _subpipeline_schema_cache[nid] = subpipeline_ui_schema(
                [dict(x) for x in nested_nodes],
                [dict(x) for x in nested_links],
            )
        return _subpipeline_schema_cache[nid]
    return resolve_port_schema(nd.get("tool_config"), type_name)


async def _enrich_subpipeline_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for n in nodes:
        nd = dict(n)
        if nd.get("type_name") == "subpipeline" and nd.get("nested_pipeline_id"):
            nd["tool_config"] = await _schema_for_node(nd)
        out.append(nd)
    return out


async def _graph_to_reactflow(nodes: list[Any], links: list[Any]) -> tuple[list[dict], list[dict]]:
    _subpipeline_schema_cache.clear()
    rf_nodes = []
    for n in nodes:
        nd = dict(n)
        schema = await _schema_for_node(nd)
        pos = _coords_to_position(nd["coords"])
        component = str(schema.get("react_component", "workflow"))
        rf_nodes.append(
            {
                "id": str(nd["id"]),
                "type": component,
                "position": pos,
                "data": {
                    "label": nd.get("report") or nd.get("nested_pipeline_name") or nd["type_name"],
                    "type_id": nd["type_id"],
                    "type_name": nd["type_name"],
                    "type_description": nd.get("type_description"),
                    "tool_name": nd["tool_name"],
                    "report": nd.get("report"),
                    "nested_pipeline_id": nd.get("nested_pipeline_id"),
                    "nested_pipeline_name": nd.get("nested_pipeline_name"),
                    "node_config": _parse_json_object(nd.get("node_config")),
                    "ui": schema,
                    "ports": {
                        "inputs": schema.get("inputs", []),
                        "outputs": schema.get("outputs", []),
                    },
                    "color": schema.get("color"),
                },
            }
        )

    rf_edges = []
    for l in links:
        sh = l.get("source_handle") or "out"
        th = l.get("target_handle") or "in"
        rf_edges.append(
            {
                "id": f"e{l['from_node']}-{sh}-{l['to_node']}-{th}",
                "source": str(l["from_node"]),
                "target": str(l["to_node"]),
                "sourceHandle": sh,
                "targetHandle": th,
                "type": "smoothstep",
                "animated": True,
                "label": sh if sh not in ("out",) else None,
            }
        )
    return rf_nodes, rf_edges


async def _pipelines_for_nesting(project_id: int, exclude_pipeline_id: int) -> list[dict[str, Any]]:
    rows = await db.fetch(
        """
        SELECT id, name
        FROM pipelines
        WHERE project_id = $1 AND id != $2
        ORDER BY name
        """,
        project_id,
        exclude_pipeline_id,
    )
    return [dict(r) for r in rows]


@router.get("/pipelines/{pipeline_id}/graph")
async def get_pipeline_graph(
    pipeline_id: int,
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
):
    user_id = _user_id_from_token(authorization, token)
    meta = await _ensure_pipeline_access(pipeline_id, user_id)
    nodes, links = await _load_graph_rows(pipeline_id)
    rf_nodes, rf_edges = await _graph_to_reactflow(nodes, links)
    nested_options = await _pipelines_for_nesting(
        int(meta["project_id"]), pipeline_id
    )
    return {
        "pipeline": meta,
        "nodes": rf_nodes,
        "edges": rf_edges,
        "available_pipelines": nested_options,
    }


@router.get("/pipelines/{pipeline_id}/interface")
async def get_pipeline_interface(
    pipeline_id: int,
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
):
    """Входы/выходы пайплайна для блока subpipeline."""
    user_id = _user_id_from_token(authorization, token)
    await _ensure_pipeline_access(pipeline_id, user_id)
    nodes, links = await _load_graph_rows(pipeline_id)
    iface = compute_pipeline_interface(
        [dict(n) for n in nodes], [dict(l) for l in links]
    )
    return {
        "pipeline_id": pipeline_id,
        "inputs": iface["inputs"],
        "outputs": iface["outputs"],
    }


@router.get("/pipelines/{pipeline_id}/execution-plan")
async def get_execution_plan(
    pipeline_id: int,
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
):
    user_id = _user_id_from_token(authorization, token)
    await _ensure_pipeline_access(pipeline_id, user_id)
    nodes, links = await _load_graph_rows(pipeline_id)
    node_list = await _enrich_subpipeline_nodes([dict(n) for n in nodes])
    link_list = [dict(l) for l in links]
    return {
        "execution_plan": build_execution_plan(node_list, link_list),
        "connections": connections_with_ports(node_list, link_list),
    }


@router.put("/pipelines/{pipeline_id}/graph")
async def save_pipeline_graph(
    pipeline_id: int,
    body: SaveGraphBody,
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
):
    user_id = _user_id_from_token(authorization, token)
    await _ensure_pipeline_access(pipeline_id, user_id)

    type_ids = list({n.type_id for n in body.nodes})
    type_map: dict[int, dict[str, Any]] = {}
    if type_ids:
        type_rows = await db.fetch(
            """
            SELECT nt.id, nt.name, t.config AS tool_config
            FROM node_types nt
            JOIN tools t ON t.id = nt.tool_id
            WHERE nt.id = ANY($1::bigint[])
            """,
            type_ids,
        )
        type_map = {int(r["id"]): dict(r) for r in type_rows}
        if len(type_map) != len(type_ids):
            raise HTTPException(status_code=400, detail="Unknown node type_id")

    async with db.pool.acquire() as conn:
        async with conn.transaction():
            existing = await conn.fetch(
                "SELECT id FROM nodes WHERE pipeline_id = $1", pipeline_id
            )
            existing_ids = {r["id"] for r in existing}
            kept_ids: set[int] = set()
            id_map: dict[str, int] = {}

            for node in body.nodes:
                x = float(node.position.get("x", 0))
                y = float(node.position.get("y", 0))
                nid = node.id.strip()
                if nid.isdigit() and int(nid) in existing_ids:
                    db_id = int(nid)
                    await conn.execute(
                        """
                        UPDATE nodes
                        SET type_id = $1,
                            coords = point($2, $3),
                            report = $4,
                            nested_pipeline_id = $5
                            , node_config = COALESCE($6::jsonb, '{}'::jsonb)
                        WHERE id = $7 AND pipeline_id = $8
                        """,
                        node.type_id,
                        x,
                        y,
                        node.label,
                        node.nested_pipeline_id,
                        json.dumps(node.node_config or {}),
                        db_id,
                        pipeline_id,
                    )
                    kept_ids.add(db_id)
                    id_map[nid] = db_id
                else:
                    row = await conn.fetchrow(
                        """
                        INSERT INTO nodes (pipeline_id, type_id, coords, report, nested_pipeline_id, node_config)
                        VALUES ($1, $2, point($3, $4), $5, $6, COALESCE($7::jsonb, '{}'::jsonb))
                        RETURNING id
                        """,
                        pipeline_id,
                        node.type_id,
                        x,
                        y,
                        node.label,
                        node.nested_pipeline_id,
                        json.dumps(node.node_config or {}),
                    )
                    db_id = int(row["id"])
                    kept_ids.add(db_id)
                    id_map[nid] = db_id

            to_delete = existing_ids - kept_ids
            if to_delete:
                await conn.execute(
                    "DELETE FROM links WHERE from_node = ANY($1::bigint[]) OR to_node = ANY($1::bigint[])",
                    list(to_delete),
                )
                await conn.execute(
                    "DELETE FROM nodes WHERE id = ANY($1::bigint[]) AND pipeline_id = $2",
                    list(to_delete),
                    pipeline_id,
                )

            await conn.execute(
                """
                DELETE FROM links
                WHERE from_node IN (SELECT id FROM nodes WHERE pipeline_id = $1)
                """,
                pipeline_id,
            )

            db_id_to_type: dict[int, int] = {}
            for n in body.nodes:
                mapped = id_map.get(n.id)
                if mapped is not None:
                    db_id_to_type[mapped] = n.type_id

            for edge in body.edges:
                src = id_map.get(edge.source) or (
                    int(edge.source) if edge.source.isdigit() else None
                )
                tgt = id_map.get(edge.target) or (
                    int(edge.target) if edge.target.isdigit() else None
                )
                if src is None or tgt is None:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Unknown edge endpoints: {edge.source} -> {edge.target}",
                    )
                if src == tgt:
                    continue
                src_type = type_map[db_id_to_type[src]]
                tgt_type = type_map[db_id_to_type[tgt]]
                src_schema = resolve_port_schema(
                    src_type.get("tool_config"), src_type.get("name")
                )
                tgt_schema = resolve_port_schema(
                    tgt_type.get("tool_config"), tgt_type.get("name")
                )
                sh = edge.source_handle or default_source_handle(src_schema)
                th = edge.target_handle or default_target_handle(tgt_schema)
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

    graph = await get_pipeline_graph(
        pipeline_id, authorization=authorization, token=token
    )
    return graph
