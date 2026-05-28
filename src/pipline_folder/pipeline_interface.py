"""Внешний интерфейс пайплайна (входы/выходы) по графу узлов и связей."""

from __future__ import annotations

from typing import Any

from pipline_folder.port_schema import resolve_port_schema

DEFAULT_IN = {"id": "in", "label": "In"}
DEFAULT_OUT = {"id": "out", "label": "Out"}


def _node_label(node: dict[str, Any]) -> str:
    return (
        (node.get("report") or "").strip()
        or (node.get("type_name") or "").strip()
        or f"node_{node['id']}"
    )


def _port_id(node_id: int, port: str, total: int) -> str:
    if total == 1:
        return port
    return f"n{node_id}_{port}"


def _linked_source_ports(links: list[dict[str, Any]]) -> set[tuple[int, str]]:
    out: set[tuple[int, str]] = set()
    for link in links:
        fn = int(link["from_node"])
        sh = str(link.get("source_handle") or "out")
        out.add((fn, sh))
    return out


def _linked_target_ports(links: list[dict[str, Any]]) -> set[tuple[int, str]]:
    out: set[tuple[int, str]] = set()
    for link in links:
        tn = int(link["to_node"])
        th = str(link.get("target_handle") or "in")
        out.add((tn, th))
    return out


def compute_pipeline_interface(
    nodes: list[dict[str, Any]], links: list[dict[str, Any]]
) -> dict[str, list[dict[str, str]]]:
    """
    Входы: входные порты узлов без входящих рёбер (или порт in без связи внутри).
    Выходы: выходные порты без исходящей связи с этим source_handle.
    """
    if not nodes:
        return {"inputs": [dict(DEFAULT_IN)], "outputs": [dict(DEFAULT_OUT)]}

    incoming_count: dict[int, int] = {int(n["id"]): 0 for n in nodes}
    for link in links:
        tn = int(link["to_node"])
        if tn in incoming_count:
            incoming_count[tn] = incoming_count.get(tn, 0) + 1

    linked_targets = _linked_target_ports(links)
    linked_sources = _linked_source_ports(links)

    raw_inputs: list[dict[str, str]] = []
    for node in sorted(nodes, key=lambda n: int(n["id"])):
        nid = int(node["id"])
        schema = resolve_port_schema(node.get("tool_config"), node.get("type_name"))
        label_base = _node_label(node)
        ins = schema.get("inputs") or [DEFAULT_IN]
        is_entry = incoming_count.get(nid, 0) == 0
        for p in ins:
            pid = str(p.get("id") or "in")
            if is_entry or (nid, pid) not in linked_targets:
                raw_inputs.append(
                    {
                        "id": pid,
                        "label": f"{label_base} · {p.get('label') or pid}",
                        "_node_id": str(nid),
                    }
                )

    raw_outputs: list[dict[str, str]] = []
    for node in sorted(nodes, key=lambda n: int(n["id"])):
        nid = int(node["id"])
        schema = resolve_port_schema(node.get("tool_config"), node.get("type_name"))
        label_base = _node_label(node)
        outs = schema.get("outputs") or [DEFAULT_OUT]
        for p in outs:
            pid = str(p.get("id") or "out")
            if (nid, pid) not in linked_sources:
                raw_outputs.append(
                    {
                        "id": pid,
                        "label": f"{label_base} · {p.get('label') or pid}",
                        "_node_id": str(nid),
                    }
                )

    if not raw_inputs:
        start = min(nodes, key=lambda n: int(n["id"]))
        schema = resolve_port_schema(start.get("tool_config"), start.get("type_name"))
        ins = schema.get("inputs") or [DEFAULT_IN]
        label_base = _node_label(start)
        for p in ins:
            pid = str(p.get("id") or "in")
            raw_inputs.append(
                {
                    "id": pid,
                    "label": f"{label_base} · {p.get('label') or pid}",
                    "_node_id": str(start["id"]),
                }
            )

    if not raw_outputs:
        for node in sorted(nodes, key=lambda n: int(n["id"]), reverse=True):
            schema = resolve_port_schema(node.get("tool_config"), node.get("type_name"))
            outs = schema.get("outputs") or [DEFAULT_OUT]
            label_base = _node_label(node)
            for p in outs:
                pid = str(p.get("id") or "out")
                raw_outputs.append(
                    {
                        "id": pid,
                        "label": f"{label_base} · {p.get('label') or pid}",
                        "_node_id": str(node["id"]),
                    }
                )
            if raw_outputs:
                break

    inputs = [
        {
            "id": _port_id(int(x["_node_id"]), x["id"], len(raw_inputs)),
            "label": x["label"],
        }
        for x in raw_inputs
    ]
    outputs = [
        {
            "id": _port_id(int(x["_node_id"]), x["id"], len(raw_outputs)),
            "label": x["label"],
        }
        for x in raw_outputs
    ]

    return {
        "inputs": inputs or [dict(DEFAULT_IN)],
        "outputs": outputs or [dict(DEFAULT_OUT)],
    }


def subpipeline_ui_schema(
    nested_nodes: list[dict[str, Any]], nested_links: list[dict[str, Any]]
) -> dict[str, Any]:
    iface = compute_pipeline_interface(nested_nodes, nested_links)
    return {
        "react_component": "subpipeline",
        "color": "#009688",
        "inputs": iface["inputs"],
        "outputs": iface["outputs"],
    }
