from __future__ import annotations

from typing import Any

from json_utils import json_safe
from pipline_folder.pipeline_collector import (
    connections_with_step_slots,
    step_slots_by_node_id,
)


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
        nodes_public.append(
            {
                "step_slot": slot[n["id"]],
                "type_name": n["type_name"],
                "type_description": n.get("type_description"),
                "tool_name": n["tool_name"],
                "report": n.get("report"),
                "attempts": n.get("attempts"),
            }
        )
    links_public = connections_with_step_slots(nodes, structure["links"])
    return {
        "pipeline": pipeline_public,
        "nodes": nodes_public,
        "links": links_public,
        "statistics": dict(structure.get("statistics", {})),
    }
