from __future__ import annotations

from typing import Any

from json_utils import json_safe
from pipline_folder.graph_export import block_export_view, normalize_node, parse_json_object
from pipline_folder.graph_executor import connections_with_ports
from pipline_folder.graph_slots import step_slots_by_node_id


def public_pipeline_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": row["name"],
        "project_name": row["project_name"],
        "max_time": json_safe(row.get("max_time")),
        "max_cost": json_safe(row.get("max_cost")),
        "max_fail_percent": json_safe(row.get("max_fail_percent")),
        "score": json_safe(row.get("score")),
        "report": row.get("report"),
    }


def public_structure(structure: dict[str, Any]) -> dict[str, Any]:
    p = structure["pipeline"]
    pipeline_public = {
        "name": p["name"],
        "project_name": p["project_name"],
        "max_time": json_safe(p.get("max_time")),
        "max_cost": json_safe(p.get("max_cost")),
        "max_fail_percent": json_safe(p.get("max_fail_percent")),
        "score": json_safe(p.get("score")),
        "report": p.get("report"),
    }
    nodes = structure["nodes"]
    slot = step_slots_by_node_id(nodes)
    nodes_public: list[dict[str, Any]] = []
    for n in sorted(nodes, key=lambda x: x["id"]):
        nd = normalize_node(dict(n))
        nd["step_slot"] = slot[nd["id"]]
        nodes_public.append(block_export_view(nd))

    norm_nodes = [normalize_node(dict(n)) for n in nodes]
    links = [dict(l) for l in structure["links"]]
    links_public = connections_with_ports(norm_nodes, links)

    return {
        "export_version": 2,
        "pipeline": pipeline_public,
        "nodes": nodes_public,
        "links": links_public,
        "statistics": dict(structure.get("statistics", {})),
    }
