"""Нормализация узлов/связей для полного экспорта пайплайна (MCP, codegen)."""

from __future__ import annotations

import json
from typing import Any

from json_utils import json_safe
from pipline_folder.graph_executor import (
    build_execution_plan,
    connections_with_ports,
    execution_sequence_walk,
)
from pipline_folder.graph_slots import step_slots_by_node_id
from pipline_folder.pipeline_interface import subpipeline_ui_schema
from pipline_folder.port_schema import resolve_port_schema


def parse_json_object(value: Any) -> dict[str, Any]:
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


def normalize_node(row: dict[str, Any]) -> dict[str, Any]:
    nd = dict(row)
    nd["node_config"] = parse_json_object(nd.get("node_config"))
    nd["tool_config"] = parse_json_object(nd.get("tool_config"))
    return nd


def block_export_view(node: dict[str, Any]) -> dict[str, Any]:
    """Блок со всеми настройками для codegen."""
    schema = resolve_port_schema(node.get("tool_config"), node.get("type_name"))
    if node.get("type_name") == "subpipeline" and node.get("nested_pipeline_id"):
        nested_nodes = node.get("_nested_nodes") or []
        nested_links = node.get("_nested_links") or []
        if nested_nodes:
            schema = subpipeline_ui_schema(nested_nodes, nested_links)

    out: dict[str, Any] = {
        "step_slot": node.get("step_slot"),
        "name": node.get("type_name"),
        "description": node.get("type_description"),
        "tool": node.get("tool_name"),
        "label": node.get("report"),
        "react_component": schema.get("react_component"),
        "ports": {
            "inputs": schema.get("inputs", []),
            "outputs": schema.get("outputs", []),
        },
        "node_config": node.get("node_config") or {},
        "tool_config": node.get("tool_config") or {},
    }
    if node.get("nested_pipeline_id"):
        out["nested_pipeline"] = {
            "id": node.get("nested_pipeline_id"),
            "name": node.get("nested_pipeline_name"),
        }
    if node.get("_nested_export"):
        out["nested_pipeline_spec"] = node["_nested_export"]
    return out


def pipeline_spec_from_graph(
    pipeline: dict[str, Any],
    nodes: list[dict[str, Any]],
    links: list[dict[str, Any]],
    *,
    nested_specs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    slot = step_slots_by_node_id(nodes)
    norm_nodes: list[dict[str, Any]] = []
    for n in sorted(nodes, key=lambda x: x["id"]):
        nd = normalize_node(n)
        nd["step_slot"] = slot[nd["id"]]
        nested_name = nd.get("nested_pipeline_name")
        if nested_name and nested_specs and nested_name in nested_specs:
            nd["_nested_export"] = nested_specs[nested_name]
        norm_nodes.append(nd)

    enriched: list[dict[str, Any]] = []
    for nd in norm_nodes:
        row = dict(nd)
        if row.get("type_name") == "subpipeline" and row.get("nested_pipeline_id"):
            nested_name = row.get("nested_pipeline_name")
            if nested_specs and nested_name in nested_specs:
                nested = nested_specs[nested_name]
                row["_nested_nodes"] = nested.get("_raw_nodes", [])
                row["_nested_links"] = nested.get("_raw_links", [])
                if row["_nested_nodes"]:
                    row["tool_config"] = subpipeline_ui_schema(
                        row["_nested_nodes"], row["_nested_links"]
                    )
        enriched.append(row)

    node_list = [dict(n) for n in enriched]
    blocks = [block_export_view(n) for n in enriched]

    public_nested = {
        k: {key: v[key] for key in v if not key.startswith("_")}
        for k, v in (nested_specs or {}).items()
    }

    return {
        "export_version": 2,
        "project_name": pipeline.get("project_name"),
        "pipeline_name": pipeline["name"],
        "description": pipeline.get("report"),
        "limits": {
            "max_time": json_safe(pipeline.get("max_time")),
            "max_cost": json_safe(pipeline.get("max_cost")),
            "max_fail_percent": json_safe(pipeline.get("max_fail_percent")),
            "score": json_safe(pipeline.get("score")),
        },
        "blocks": blocks,
        "connections": connections_with_ports(node_list, links),
        "execution_sequence": execution_sequence_walk(node_list, links),
        "execution_plan": build_execution_plan(node_list, links),
        "nested_pipelines": public_nested,
    }
