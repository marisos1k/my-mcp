---
name: pipeline-to-python
description: >-
  Generates Python implementation from a BrAIniac pipeline spec.
  Use when the user asks to export or implement a pipeline as Python code.
---

# Pipeline → Python

## Когда применять

Запросы: «экспортируй кодом», «реализуй пайплайн», «сгенерируй Python по MCP».

## Шаги

1. Вызвать `export_pipeline_as_code(api_key, project_name, pipeline_name, language="python")`.
2. Из ответа: `pipeline_spec` — данные графа, `workflow` — эти инструкции.
3. Создать файлы ниже (уточнить у пользователя целевую папку проекта, если нужно).
4. Не выводить сырой JSON — только код и список созданных файлов.

## Структура файлов

```
pipelines/<pipeline_name>.py   # runner пайплайна
handlers/__init__.py           # реестр HANDLERS
handlers/<tool_name>.py        # хендлер для каждого уникального blocks[].tool
```

---

## `pipelines/<pipeline_name>.py`

Заполни `PLAN` из `execution_plan`, `MAX_TIME`/`MAX_COST` из `limits`.

```python
import asyncio
from handlers import HANDLERS

MAX_TIME     = <limits.max_time>         # сек; из pipeline_spec.limits
MAX_COST     = <limits.max_cost>
MAX_FAIL_PCT = <limits.max_fail_percent>

# Сгенерировано из pipeline_spec.execution_plan
# Каждый ключ — step_slot (int), значение — поля шага.
PLAN: dict[int, dict] = {
    1: {"step": "Trigger",    "tool": "mvp-core-nodes", "node_config": {}, "next": 2},
    2: {"step": "LLMCall",    "tool": "mvp-core-nodes", "node_config": {"model": "gpt-4o-mini"}, "next": 3},
    3: {"step": "Branch",     "tool": "mvp-core-nodes", "node_config": {},
        "branches": {"yes": 4, "no": 5, "error": 6}},
    4: {"step": "Notify",     "tool": "mvp-core-nodes", "node_config": {}, "next": None},
    5: {"step": "SaveResult", "tool": "mvp-core-nodes", "node_config": {}, "next": None},
    6: {"step": "SaveResult", "tool": "mvp-core-nodes", "node_config": {}, "next": None},
}

async def run(initial_ctx: dict | None = None) -> dict:
    ctx: dict = dict(initial_ctx or {})
    current: int | None = min(PLAN)          # старт = наименьший step_slot

    while current is not None:
        step = PLAN[current]
        handler = HANDLERS.get(step["tool"])
        if handler is None:
            raise NotImplementedError(f"No handler for tool: {step['tool']!r}")

        result = await handler(step, ctx)
        ctx[f"step_{current}"] = result       # результат доступен всем следующим шагам

        if "branches" in step:
            port = (result or {}).get("branch", "error")
            current = step["branches"].get(port)
        else:
            current = step.get("next")

    return ctx

if __name__ == "__main__":
    asyncio.run(run())
```

---

## `handlers/__init__.py`

Добавь `import` для каждого уникального значения `blocks[].tool`.

```python
from handlers.mvp_core_nodes import handler as mvp_core_nodes

# Ключ = значение поля "tool" из pipeline_spec.blocks[].tool
HANDLERS: dict[str, object] = {
    "mvp-core-nodes": mvp_core_nodes,
    # "calendar-api": calendar_api,
}
```

---

## `handlers/<tool_name>.py`

Один файл на каждый уникальный `tool`. Внутри — диспатч по `step["step"]` (тип узла).

```python
import os
from typing import Any

async def handler(step: dict[str, Any], ctx: dict[str, Any]) -> Any:
    """
    step["step"]        — тип узла: Trigger, LLMCall, Branch, Notify, SaveResult, …
    step["node_config"] — настройки конкретного экземпляра из spec
    step["step_slot"]   — номер шага (используй для ctx-ключей)
    ctx                 — общий контекст; ctx["step_N"] — результат шага N
    """
    node_type = step["step"]
    cfg       = step.get("node_config") or {}

    match node_type:
        case "Trigger":
            return ctx.get("input") or {}

        case "LLMCall":
            return await _llm_call(cfg, ctx)

        case "Branch":
            return await _branch(cfg, ctx)

        case "Notify":
            target = cfg.get("target") or "default"
            print(f"[Notify] → {target}: {ctx.get('step_2')}")
            return {"notified": True}

        case "SaveResult":
            ctx["output"] = ctx.get("step_2")   # сохранить нужный шаг
            return ctx["output"]

        case _:
            raise NotImplementedError(f"TODO: {node_type}")


async def _llm_call(cfg: dict, ctx: dict) -> dict:
    import httpx
    api_key  = cfg.get("api_key")       or os.getenv("LLM_API_KEY", "")
    base_url = cfg.get("base_url")      or "https://api.openai.com/v1"
    model    = cfg.get("model")         or "gpt-4o-mini"
    prompt   = (cfg.get("system_prompt") or "").format(**ctx)
    timeout  = cfg.get("timeout_s", 30)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}]},
            timeout=timeout,
        )
        resp.raise_for_status()
        return {"text": resp.json()["choices"][0]["message"]["content"]}


async def _branch(cfg: dict, ctx: dict) -> dict:
    # Логика ветвления — читай предыдущий результат из ctx.
    # Верни {"branch": "yes" | "no" | "error"} — runner выберет путь по branches[port].
    prev = ctx.get("step_2") or {}
    if prev.get("error"):
        return {"branch": "error"}
    text = str(prev.get("text", "")).lower()
    return {"branch": "yes" if "urgent" in text else "no"}
```

---

## Передача контекста между шагами

```
ctx["step_1"] = результат Trigger     # {"ticket_id": 42, ...}
ctx["step_2"] = результат LLMCall     # {"text": "URGENT: ..."} ← читает Branch
ctx["step_3"] = результат Branch      # {"branch": "yes"}
```

Имена ключей — `step_{step_slot}`. Используй точные номера из PLAN, не угадывай.

---

## Вложенные пайплайны (`subpipeline`)

Узел `step["step"] == "subpipeline"` → в `pipeline_spec.nested_pipelines[name]` лежит полный spec.
Сгенерируй для него отдельный `pipelines/<nested_name>.py` и вызови `run()` рекурсивно:

```python
case "subpipeline":
    name = step.get("node_config", {}).get("nested_pipeline", {}).get("name", "")
    from pipelines import <nested_name>
    return await <nested_name>.run(ctx)
```

---

## Справка: поля execution_plan

| Поле | Тип | Описание |
|---|---|---|
| `step_slot` | int | Номер шага 1..N (ключ PLAN) |
| `step` | str | Тип узла (LLMCall, Branch, …) |
| `tool` | str | Ключ в HANDLERS |
| `node_config` | dict | Настройки экземпляра |
| `next` | int\|None | Следующий step_slot (линейно) |
| `branches` | dict | `{"yes": slot, "no": slot, "error": slot}` |
