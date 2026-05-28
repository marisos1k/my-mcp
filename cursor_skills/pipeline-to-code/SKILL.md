---
name: pipeline-to-code
description: >-
  Exports a pipeline from the Pipeline MCP server (export_for_llm) and generates
  Python implementation code with handlers. Use when the user asks to export a
  pipeline as code, implement a pipeline, or mentions pipeline-to-code / MCP export.
---

# Pipeline → код

## Когда применять

Запросы вроде: «экспортируй пайплайн X кодом», «реализуй пайплайн», «сгенерируй код по MCP».

## Шаги

1. Убедиться, что MCP Pipeline подключён в Cursor.
2. Вызвать tool **`export_pipeline_as_code`** с `api_key`, `project_name`, `pipeline_name` (один вызов: `pipeline_spec` + `workflow`). Альтернатива: resource `skill://pipeline-to-code` + `export_for_llm`.
3. Создать или обновить **`pipelines/<pipeline_name>.py`** в проекте приложения (не в `my-mcp`, если открыт только MCP-репо — уточнить у пользователя целевую папку).
4. Порядок шагов — из **`execution_plan`** (ветвления) или **`execution_sequence`** (линейный обход).
5. Каждый шаг вызывает обработчик по полю **`tool`** через реестр, например `HANDLERS[tool](ctx, meta)`.
6. **Настройки блоков** брать из `blocks[].node_config` и `execution_plan[].node_config`:
   - LLM: `api_key`, `base_url`, `model`, `system_prompt`, `temperature`, `timeout_s`
   - subpipeline: `nested_pipeline` + `nested_pipeline_spec` / `nested_pipelines`
7. Связи графа — по **`connections`** (`from_step`, `to_step`, `from_port`, `to_port`).
8. Лимиты из **`limits`** — константы или декоратор таймаута в том же файле.
9. Не выводить сырой JSON пользователю — только код и краткий список созданных файлов.
10. Нет модуля для `tool` — добавить заглушку в `handlers/<tool>.py` с `NotImplementedError` и TODO.

## Формат export (export_version=2)

- `blocks[]`: step_slot, tool, ports, node_config, nested_pipeline
- `connections[]`: from_step, to_step, from_port, to_port
- `execution_plan[]`: шаги с branches/next и node_config
- `nested_pipelines{}`: полные спеки вложенных пайплайнов

## Структура целевого проекта

```
handlers/
  __init__.py      # HANDLERS = {"llm": ..., "calendar_api": ...}
  llm.py           # читает node_config (api_key, model, ...)
  ...
pipelines/
  <pipeline_name>.py
config/
  pipeline_settings.json   # опционально: node_config по step_slot
```

## Пример LLM handler из node_config

```python
async def llm_handler(step, ctx):
    cfg = step.get("node_config") or {}
    api_key = cfg.get("api_key") or os.getenv("LLM_API_KEY")
    base_url = cfg.get("base_url") or "https://api.openai.com"
    model = cfg.get("model") or "gpt-4o-mini"
    ...
```

## Пример запроса пользователя

«Экспортируй пайплайн schedule_agent кодом, проект time_manager, api_key tm_…»

## Тестовые имена (дамп test_brainiac)

- project: `time_manager`
- pipeline: `schedule_agent`
