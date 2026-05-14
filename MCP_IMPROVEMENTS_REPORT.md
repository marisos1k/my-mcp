# Отчёт: доработки Brainiac / Pipeline MCP

Дата: 2026-05-14  
Кодовая база: `my-mcp/`

## Цели

- Согласовать порядок узлов в `get_pipeline_flow` и `export_for_llm` с топологией графа.  
- Устранить неоднозначность связей при одинаковых `type_name` у разных узлов.  
- Снизить утечку данных и лишние обращения к БД.  
- Улучшить предсказуемость ошибок аутентификации и удобство поиска пайплайнов.

## Реализованные изменения

### 1. Слоты шагов (`step_slot`) вместо ссылок по типу узла

- Введена стабильная нумерация узлов **1…N** в порядке возрастания внутреннего `id` узла в БД (используется только для сортировки и построения графа; в JSON MCP **не отдаётся** как идентификатор сущности для клиента).  
- Связи в публичной структуре и в LLM-экспорте задаются как **`from_step` / `to_step`** (целые слоты), а не пара `type_name` → `type_name`.  
- Функции в `pipline_folder/pipeline_collector.py`: `step_slots_by_node_id`, `connections_with_step_slots`, `execution_sequence_walk`, `blocks_ordered_with_slots`.

### 2. Единый порядок обхода для flow и экспорта

- **`get_pipeline_flow`** строит `execution_sequence` через **`execution_sequence_walk`**: обход по рёбрам от стартового узла (без входящих рёбер в рамках пайплайна; при цикле/нескольких стартах — запасной выбор минимального `id`).  
- **`export_for_llm`** использует тот же обход для поля **`execution_sequence`** и те же слоты в **`connections`**.  
- Раньше `get_pipeline_flow` отражал порядок строк из БД (`ORDER BY n.id`), что расходилось с логикой экспорта.

### 3. Одна аутентификация на запрос по имени проекта и пайплайна

- Добавлены **`load_structure_by_project_and_pipeline`**, **`_fetch_graph`**, **`_structure_for_user_pipeline`**: после одной проверки API-ключа выполняется резолв идентификаторов и загрузка графа без повторного `authenticate` в той же цепочке.  
- **`get_pipeline_structure`**, **`export_for_llm`**, **`get_pipeline_flow`** используют `load_structure_by_project_and_pipeline`; экспорт вызывает **`export_structure_to_llm`** без второго полного чтения структуры из БД.

### 4. Неоднозначность имён проекта + пайплайна

- Если по паре **`(project_name, pipeline_name)`** находится **более одной** строки в БД, возвращается **`ValueError`** с текстом о необходимости уникальности в базе (раньше молча использовался `LIMIT 1`).

### 5. Приватность и утечки в ответах MCP

- Из **`get_pipeline_structure`** убран блок **`user`** (email, key_name и т.д.).  
- В выборке узлов из таблицы **`tools`** больше не подтягиваются **`config`** и **`id`** инструмента — только **`t.name` как `tool_name`**, чтобы конфиги и лишние id не попадали в память/цепочку экспорта рядом с узлом (при этом **`n.*`** по-прежнему даёт поля узла для внутреннего графа; наружу через MCP уходит только санитизированный вид).  
- В публичных узлах остаются: `step_slot`, тип, инструмент, описание, `report`, `attempts`.

### 6. Ошибка аутентификации

- В **`auth_middleware.py`** введён **`InvalidApiKeyError(ValueError)`** вместо общего `Exception` для неверного ключа и отсутствия пользователя.

### 7. Новый tool: `search_pipelines`

- Поиск по подстроке имени пайплайна (**`ILIKE`**) с тем же форматом строк, что и **`get_pipelines`** (без id).  
- Пустой **`query_substring`** даёт **`ValueError`**.

### 8. Загрузка конфигурации

- В **`mcp_server.py`** путь к **`config.env`** задаётся относительно расположения файла: **`Path(__file__).resolve().parent.parent`**, чтобы не зависеть от текущего каталога процесса.

### 9. Общий модуль сериализации

- Файл **`json_utils.py`**: функция **`json_safe`** для `Decimal` и `interval` → JSON-совместимые типы (используется в MCP-слое; коллектор импортирует для блока **`limits`** в LLM-экспорте).

### 10. Формат `export_for_llm`

- Добавлен объект **`limits`**: `max_time`, `max_cost`, `max_fail_percent`, `score` (через `json_safe`).  
- **`blocks`**: упорядочены по `id` узла, каждый с **`step_slot`**.  
- **`connections`**: `from_step`, `to_step`.  
- **`execution_sequence`**: список объектов с **`step_slot`**, **`step`**, **`tool`**, **`description`**.

## Файлы

| Файл | Изменение |
|------|-----------|
| `src/json_utils.py` | Новый: `json_safe`. |
| `src/mcp_server.py` | Рефакторинг, новый tool, `_public_structure`, `load_dotenv` по пути, единый flow. |
| `src/pipline_folder/pipeline_collector.py` | Граф, загрузка без двойного auth, урезанный SELECT узлов, LLM-экспорт. |
| `src/pipline_folder/auth_middleware.py` | `InvalidApiKeyError`. |

## Что сознательно не делали

- Повторное подключение к БД при обрыве пула (**retry**) — потребует доработки `ConnectionDB` и политики пула asyncpg.  
- Вынесение API-ключа из аргументов tools в заголовки транспорта — зависит от возможностей хостинга MCP-клиента.  
- Уникальные ограничения в PostgreSQL на `(user_id, project_id, pipeline.name)` — только рекомендация; ошибка неоднозначности уже отдаётся на уровне приложения.

## Рекомендации по внедрению

1. Пересобрать контейнер: в каталоге `my-mcp` выполнить `docker compose up -d --build`.  
2. В Cursor обновить список MCP-tools (появился **`search_pipelines`**, изменились схемы **`export_for_llm`** и **`get_pipeline_flow`**).  
3. Проверить клиентов, которые парсили старый формат `connections` / `execution_sequence`.

## Краткая проверка импорта

Из рабочего каталога **`my-mcp/src`** (как в Docker `WORKDIR`):

```bash
python -c "import mcp_server; print('ok')"
```
