# BrAIniac MCP Server

MCP-сервер для работы с пайплайнами [BrAIniac](../BrAIniac) через Model Context Protocol.  
Позволяет агентам (Cursor, Claude Code и др.) читать, создавать и экспортировать пайплайны напрямую из IDE.

## Как это работает

```
IDE (Cursor / Claude Code)
        │  MCP (HTTP)
        ▼
  my-mcp сервер  ──── SQL ────▶  PostgreSQL BrAIniac
```

Сервер подключается к **той же БД**, что и BrAIniac, и общается с агентом по протоколу MCP (Streamable HTTP).  
Доступ к данным изолирован по пользователю через API-ключ.

## Требования

- **BrAIniac** запущен (`docker compose up` в папке `BrAIniac/`) — сервер использует его БД
- **Docker** и **Docker Compose** — для запуска my-mcp
- Или **Python 3.14+** и [uv](https://docs.astral.sh/uv/) — для локального запуска без Docker

## Быстрый старт

### 1. Настрой подключение к БД

```bash
cp config.env.example config.env
# Отредактируй config.env: укажи пароль БД BrAIniac
```

### 2. Запусти сервер

```bash
docker compose up --build
```

Сервер доступен на `http://localhost:8000/mcp`.  
В `docker-compose.override.yml` можно переключить порт на `8010`.

### 3. Получи API-ключ

Используй MCP-инструмент `create_api_key` с логином и паролем своего аккаунта BrAIniac:

```
create_api_key(email="you@example.com", password="...", key_name="cursor")
```

Ключ показывается **один раз** — сохрани его.

## Инструменты MCP

### Авторизация
| Инструмент | Описание |
|---|---|
| `create_api_key` | Получить API-ключ по email + password |
| `list_api_keys` | Список своих ключей |
| `revoke_api_key` | Отозвать ключ |

### Чтение пайплайнов
| Инструмент | Описание |
|---|---|
| `get_projects` | Список проектов |
| `get_pipelines` | Список пайплайнов (с фильтром по проекту) |
| `search_pipelines` | Поиск по подстроке имени |
| `get_pipeline_structure` | Узлы и рёбра пайплайна |
| `get_pipeline_flow` | Порядок обхода узлов |
| `export_for_llm` | Полный граф + `execution_plan` для LLM |

### Экспорт кода
| Инструмент | Описание |
|---|---|
| `export_pipeline_as_code` | Граф + инструкции для генерации кода (`language`: python / typescript / javascript) |
| `list_languages` | Доступные языки экспорта |

### Создание пайплайнов
| Инструмент | Описание |
|---|---|
| `list_node_types` | Доступные типы узлов |
| `create_project` | Создать проект |
| `create_pipeline` | Создать пайплайн в проекте |
| `create_node` | Добавить узел (возвращает `step_slot`) |
| `connect_nodes` | Соединить два узла ребром |

## Подключение к Cursor / Claude Code

Добавь в настройки MCP-клиента:

```json
{
  "mcpServers": {
    "brainiac": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

## Структура проекта

```
src/
  mcp_app/          # точка входа: инструменты, промпты, конфиг
  pipline_folder/   # логика: граф, план выполнения, экспорт
  api_folder/       # API-ключи: создание, проверка
  db_folder/        # пул соединений asyncpg

cursor_skills/
  pipeline-to-python/      # шаблон генерации Python-кода
  pipeline-to-typescript/  # шаблон генерации TypeScript-кода
  pipeline-to-javascript/  # шаблон генерации JavaScript-кода
```
