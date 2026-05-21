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
4. Порядок шагов — строго из **`execution_sequence`** в JSON.
5. Каждый шаг вызывает обработчик по полю **`tool`** через реестр, например `HANDLERS[tool](ctx, meta)`.
6. Связи графа — по **`connections`** (`from_step` / `to_step`), не по внутренним id БД.
7. Лимиты из **`limits`** — константы или декоратор таймаута в том же файле.
8. Не выводить сырой JSON пользователю — только код и краткий список созданных файлов.
9. Нет модуля для `tool` — добавить заглушку в `handlers/<tool>.py` с `NotImplementedError` и TODO.

## Структура целевого проекта

```
handlers/
  __init__.py      # HANDLERS = {"llm": ..., "calendar_api": ...}
  llm.py
  ...
pipelines/
  <pipeline_name>.py
```

## Пример запроса пользователя

«Экспортируй пайплайн schedule_agent кодом, проект time_manager, api_key tm_…»

## Тестовые имена (дамп test_brainiac)

- project: `time_manager`
- pipeline: `schedule_agent`
