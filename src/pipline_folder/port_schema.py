"""Схема портов узла из tools.config (JSON)."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

DEFAULT_WORKFLOW_SCHEMA: dict[str, Any] = {
    "react_component": "workflow",
    "color": "#3d5afe",
    "inputs": [{"id": "in", "label": "In"}],
    "outputs": [{"id": "out", "label": "Out"}],
}

DEFAULT_BRANCH_SCHEMA: dict[str, Any] = {
    "react_component": "branch",
    "color": "#7c4dff",
    "inputs": [{"id": "in", "label": "In"}],
    "outputs": [
        {"id": "yes", "label": "Да"},
        {"id": "no", "label": "Нет"},
        {"id": "error", "label": "Ошибка"},
    ],
}

DEFAULT_SUBPIPELINE_SCHEMA: dict[str, Any] = {
    "react_component": "subpipeline",
    "color": "#009688",
    "inputs": [{"id": "in", "label": "In"}],
    "outputs": [{"id": "out", "label": "Out"}],
}


def _parse_config_raw(config: Any) -> dict[str, Any]:
    if config is None:
        return {}
    if isinstance(config, dict):
        return config
    if isinstance(config, str):
        try:
            return json.loads(config)
        except json.JSONDecodeError:
            return {}
    return {}


def _js_number(value: Any) -> float | None:
    """Number(value) из JS; None вместо NaN.

    BrAIniac приводит maxIterations через Number() ДО проверки на целое, поэтому
    "3", true и 3.0 там валидны. Без такой же коэрции my-mcp был бы строже
    редактора и отвергал рёбра, которые BrAIniac принимает.
    Вырожденные случаи (Number([5]) === 5, Number("0x10") === 16) не зеркалим.
    """
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return 0.0
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return 0.0
        try:
            return float(text)
        except ValueError:
            return None
    return None


def loop_limit_status(tool_config: Any) -> str:
    """'valid' | 'invalid' | 'missing' — зеркало getLoopLimitStatus из BrAIniac.

    Цикл в графе легален, только если хотя бы один его узел несёт
    loop.maxIterations >= 1 в NodeType.config_json.
    """
    loop = _parse_config_raw(tool_config).get("loop")
    if loop is None:
        return "missing"
    if not isinstance(loop, dict):
        return "invalid"
    number = _js_number(loop.get("maxIterations"))
    if number is None or not number.is_integer() or number <= 0:
        return "invalid"
    return "valid"


def resolve_port_schema(tool_config: Any, type_name: str | None = None) -> dict[str, Any]:
    raw = _parse_config_raw(tool_config)
    if raw.get("inputs") and raw.get("outputs"):
        base = deepcopy(raw)
    elif type_name == "subpipeline":
        base = deepcopy(DEFAULT_SUBPIPELINE_SCHEMA)
    elif type_name == "branch":
        base = deepcopy(DEFAULT_BRANCH_SCHEMA)
    else:
        base = deepcopy(DEFAULT_WORKFLOW_SCHEMA)

    base.setdefault("react_component", "workflow")
    base.setdefault("color", "#3d5afe")
    base.setdefault("inputs", [{"id": "in", "label": "In"}])
    base.setdefault("outputs", [{"id": "out", "label": "Out"}])
    return base


def default_source_handle(schema: dict[str, Any]) -> str:
    outs = schema.get("outputs") or []
    return str(outs[0]["id"]) if outs else "out"


def default_target_handle(schema: dict[str, Any]) -> str:
    ins = schema.get("inputs") or []
    return str(ins[0]["id"]) if ins else "in"
