# Pipeline Studio (React Flow)

Визуальный редактор пайплайнов (workflow) в стиле n8n: проекты → пайплайны → граф на холсте.

## Стек

- React 19 + Vite
- [@xyflow/react](https://reactflow.dev/) (React Flow)
- Backend: `src/fastapi/demo_api.py` (порт **8001**)

## Запуск

1. PostgreSQL и API:

```bash
cd ..   # корень my-mcp
docker compose up db -d
cd src/fastapi
pip install fastapi uvicorn asyncpg python-dotenv pyjwt python-multipart
python demo_api.py
```

2. Frontend:

```bash
cd ReactFlow
npm install
npm run dev
```

Откройте http://localhost:5173

## Сценарий

1. Регистрация / вход
2. Создать **проект**
3. В проекте — **новый пайплайн** → открывается редактор
4. Добавить блоки из каталога, соединить рёбра, **Сохранить workflow**
5. Тот же граф доступен через MCP (`export_for_llm`, `export_pipeline_as_code`)

## API

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/catalog/node-types` | Каталог блоков + `ui` (порты, цвет, react_component) |
| POST | `/api/projects/{id}/pipelines` | Создать пайплайн |
| GET | `/api/pipelines/{id}/graph` | Граф (nodes/edges с `sourceHandle`) |
| PUT | `/api/pipelines/{id}/graph` | Сохранить граф |
| GET | `/api/pipelines/{id}/execution-plan` | План с ветвлением |

Авторизация: `Authorization: Bearer <JWT>`.

## Порты и кастомные блоки

Схема в `tools.config` (JSON):

```json
{
  "react_component": "branch",
  "color": "#7c4dff",
  "inputs": [{"id": "in", "label": "In"}],
  "outputs": [
    {"id": "yes", "label": "Да"},
    {"id": "no", "label": "Нет"},
    {"id": "error", "label": "Ошибка"}
  ]
}
```

- `react_component: "workflow"` — обычный блок (1 in / 1 out)
- `react_component: "branch"` — три выхода

Миграция БД (или автоматически при старте `demo_api.py`):

`migrations/002_link_handles_and_branch_type.sql`

Исполнитель: `src/runtime/branch_handlers.py` → `execute_plan()`.

MCP-экспорт включает `execution_plan` и `connections` с `from_port` / `to_port`.
