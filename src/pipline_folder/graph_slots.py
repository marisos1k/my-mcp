from __future__ import annotations

from typing import Any


def step_slots_by_node_id(nodes: list[dict[str, Any]]) -> dict[int, int]:
    sorted_nodes = sorted(nodes, key=lambda n: n["id"])
    return {n["id"]: i + 1 for i, n in enumerate(sorted_nodes)}
