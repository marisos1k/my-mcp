"""Построение и исполнение плана пайплайна с ветвлением по портам."""

from __future__ import annotations

from collections import deque
from typing import Any, Awaitable, Callable

from pipline_folder.graph_slots import step_slots_by_node_id
from pipline_folder.port_schema import resolve_port_schema

HandlerFn = Callable[[dict[str, Any], dict[str, Any]], Awaitable[Any]]


def connections_with_ports(
    nodes: list[dict[str, Any]], links: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    slot = step_slots_by_node_id(nodes)
    out: list[dict[str, Any]] = []
    for link in links:
        sh = link.get("source_handle") or "out"
        th = link.get("target_handle") or "in"
        out.append(
            {
                "from_step": slot[link["from_node"]],
                "to_step": slot[link["to_node"]],
                "from_port": sh,
                "to_port": th,
            }
        )
    return out


def execution_sequence_walk(
    nodes: list[dict[str, Any]], links: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Порядок обхода от стартового узла по рёбрам"""
    if not nodes:
        return []
    slot = step_slots_by_node_id(nodes)
    nodes_dict = {node["id"]: node for node in nodes}
    to_nodes = {link["to_node"] for link in links}
    start_node = next((node for node in nodes if node["id"] not in to_nodes), None)
    if not start_node:
        start_node = sorted(nodes, key=lambda n: n["id"])[0]

    out: list[dict[str, Any]] = []
    visited: set[int] = set()
    current_id: int | None = start_node["id"]
    while current_id is not None and current_id not in visited:
        visited.add(current_id)
        node = nodes_dict[current_id]
        schema = resolve_port_schema(node.get("tool_config"), node.get("type_name"))
        out.append(
            {
                "step_slot": slot[current_id],
                "step": node.get("type_name"),
                "tool": node.get("tool_name"),
                "description": node.get("type_description"),
                "react_component": schema.get("react_component"),
                "node_config": node.get("node_config") or {},
            }
        )
        next_link = next(
            (link for link in links if link["from_node"] == current_id), None
        )
        current_id = next_link["to_node"] if next_link else None
    return out


def build_execution_plan(
    nodes: list[dict[str, Any]], links: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """План узлов: линейный next и/или branches по source_handle."""
    if not nodes:
        return []

    slot = step_slots_by_node_id(nodes)
    by_id = {n["id"]: n for n in nodes}
    outgoing: dict[int, list[dict[str, Any]]] = {n["id"]: [] for n in nodes}
    incoming_count: dict[int, int] = {n["id"]: 0 for n in nodes}

    for link in links:
        fn, tn = int(link["from_node"]), int(link["to_node"])
        outgoing[fn].append(link)
        incoming_count[tn] = incoming_count.get(tn, 0) + 1

    starts = [n for n in nodes if incoming_count.get(n["id"], 0) == 0]
    start = starts[0] if starts else sorted(nodes, key=lambda n: n["id"])[0]

    visited: set[int] = set()
    plan: list[dict[str, Any]] = []

    def visit(node_id: int) -> None:
        if node_id in visited:
            return
        visited.add(node_id)
        node = by_id[node_id]
        schema = resolve_port_schema(
            node.get("tool_config"), node.get("type_name")
        )
        step: dict[str, Any] = {
            "step_slot": slot[node_id],
            "step": node.get("type_name"),
            "tool": node.get("tool_name"),
            "description": node.get("type_description"),
            "react_component": schema.get("react_component"),
            "node_config": node.get("node_config") or {},
            "tool_config": node.get("tool_config") or {},
        }
        outs = outgoing.get(node_id, [])
        multi_out = len(schema.get("outputs") or []) > 1
        is_branch_like = schema.get("react_component") in ("branch", "subpipeline")
        if len(outs) > 1 or (is_branch_like and multi_out):
            branches: dict[str, Any] = {}
            for link in outs:
                port = str(link.get("source_handle") or "out")
                branches[port] = {
                    "to_step": slot[int(link["to_node"])],
                    "to_node_type": by_id[int(link["to_node"])].get("type_name"),
                }
            step["branches"] = branches
            plan.append(step)
        elif len(outs) == 1:
            step["next"] = slot[int(outs[0]["to_node"])]
            plan.append(step)
            visit(int(outs[0]["to_node"]))
        else:
            plan.append(step)

    visit(start["id"])
    for n in sorted(nodes, key=lambda x: x["id"]):
        if n["id"] not in visited:
            visit(n["id"])
    return plan


def find_path(
    links: list[dict[str, Any]], src: int, dst: int
) -> list[int] | None:
    """BFS-путь src → dst включительно; None если пути нет.

    Устойчив к уже существующим в графе циклам (visited).
    Зеркало findPath из BrAIniac edge.application.service.ts.
    """
    adjacency: dict[int, list[int]] = {}
    for link in links:
        adjacency.setdefault(int(link["from_node"]), []).append(int(link["to_node"]))

    parent: dict[int, int] = {}
    visited = {src}
    queue = deque([src])
    while queue:
        current = queue.popleft()
        if current == dst:
            path = [current]
            while path[-1] != src:
                path.append(parent[path[-1]])
            return list(reversed(path))
        for nxt in adjacency.get(current, ()):
            if nxt not in visited:
                visited.add(nxt)
                parent[nxt] = current
                queue.append(nxt)
    return None


async def execute_plan(
    plan: list[dict[str, Any]],
    handlers: dict[str, HandlerFn],
    ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Исполнитель: для branch вызывает handler и переходит по порту
    yes | no | error. Для линейных — next.
  """
    ctx = ctx or {}
    logs: list[dict[str, Any]] = []
    by_slot = {s["step_slot"]: s for s in plan}

    current = plan[0]["step_slot"] if plan else None
    while current is not None:
        step = by_slot.get(current)
        if not step:
            break
        tool = step.get("tool") or "default"
        handler = handlers.get(tool) or handlers.get("default")
        if not handler:
            raise RuntimeError(f"No handler for tool: {tool}")

        result = await handler(step, ctx)
        logs.append({"step_slot": current, "tool": tool, "result": result})

        if "branches" in step:
            port = str(result.get("branch", "yes") if isinstance(result, dict) else "yes")
            if port not in step["branches"]:
                port = next(iter(step["branches"]), "yes")
            current = step["branches"][port].get("to_step")
        else:
            current = step.get("next")

    return {"status": "completed", "logs": logs}
