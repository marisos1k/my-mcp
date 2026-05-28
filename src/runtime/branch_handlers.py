"""Пример обработчиков для execute_plan (ветвление branch)."""

from __future__ import annotations

from typing import Any

from pipline_folder.graph_executor import HandlerFn, execute_plan
from runtime.llm_handler import llm_chat_handler


async def branch_router_handler(step: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """
    Демо: выбирает порт yes/no/error из ctx['branch'] или всегда 'yes'.
    Реальный код подставляет результат шага (HTTP, LLM, условие).
    """
    port = str(ctx.get("branch", "yes"))
    if port not in (step.get("branches") or {}):
        port = "yes"
    return {"branch": port, "step": step.get("step")}


async def default_handler(step: dict[str, Any], ctx: dict[str, Any]) -> Any:
    return {"ok": True, "step": step.get("step")}


HANDLERS: dict[str, HandlerFn] = {
    "branch_router": branch_router_handler,
    "default": default_handler,
    "llm": llm_chat_handler,
    "calendar_api": default_handler,
    "scheduler": default_handler,
    "notifier": default_handler,
}


async def run_demo_plan(plan: list[dict[str, Any]], branch: str = "yes") -> dict[str, Any]:
    return await execute_plan(plan, HANDLERS, {"branch": branch})
