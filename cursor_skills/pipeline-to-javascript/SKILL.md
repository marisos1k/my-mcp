---
name: pipeline-to-javascript
description: >-
  Generates JavaScript (ES modules, Node 18+) implementation from a BrAIniac pipeline spec.
  Use when the user asks to export or implement a pipeline as JavaScript code.
---

# Pipeline → JavaScript

## Когда применять

Запросы: «экспортируй в JavaScript», «сгенерируй JS код», «реализуй пайплайн на JS».

## Шаги

1. Вызвать `export_pipeline_as_code(api_key, project_name, pipeline_name, language="javascript")`.
2. Из ответа: `pipeline_spec` — данные графа, `workflow` — эти инструкции.
3. Создать файлы ниже (уточнить у пользователя целевую папку проекта).
4. Не выводить сырой JSON — только код и список созданных файлов.

## Структура файлов

```
pipelines/<pipeline_name>.js   # runner пайплайна
handlers/index.js              # реестр HANDLERS
handlers/<tool_name>.js        # хендлер для каждого уникального blocks[].tool
```

---

## `pipelines/<pipeline_name>.js`

Заполни `PLAN` из `execution_plan`, константы из `limits`.

```javascript
import { HANDLERS } from "../handlers/index.js";

const MAX_TIME     = <limits.max_time>;          // сек; из pipeline_spec.limits
const MAX_COST     = <limits.max_cost>;
const MAX_FAIL_PCT = <limits.max_fail_percent>;

// Сгенерировано из pipeline_spec.execution_plan
/** @type {Record<number, {step: string, tool: string, node_config: object, next?: number, branches?: Record<string, number>}>} */
const PLAN = {
  1: { step: "Trigger",    tool: "mvp-core-nodes", node_config: {},                        next: 2 },
  2: { step: "LLMCall",   tool: "mvp-core-nodes", node_config: { model: "gpt-4o-mini" }, next: 3 },
  3: { step: "Branch",    tool: "mvp-core-nodes", node_config: {},
       branches: { yes: 4, no: 5, error: 6 } },
  4: { step: "Notify",    tool: "mvp-core-nodes", node_config: {} },
  5: { step: "SaveResult",tool: "mvp-core-nodes", node_config: {} },
  6: { step: "SaveResult",tool: "mvp-core-nodes", node_config: {} },
};

/**
 * @param {Record<string, unknown>} initialCtx
 * @returns {Promise<Record<string, unknown>>}
 */
export async function run(initialCtx = {}) {
  const ctx = { ...initialCtx };
  let current = Math.min(...Object.keys(PLAN).map(Number));

  while (current !== undefined) {
    const step = PLAN[current];
    const handler = HANDLERS[step.tool];
    if (!handler) throw new Error(`No handler for tool: ${step.tool}`);

    const result = await handler(step, ctx);
    ctx[`step_${current}`] = result;             // результат доступен следующим шагам

    if (step.branches) {
      const port = result?.branch ?? "error";
      current = step.branches[port];
    } else {
      current = step.next;
    }
  }

  return ctx;
}
```

---

## `handlers/index.js`

```javascript
import { handler as mvpCoreNodes } from "./mvp-core-nodes.js";
// import { handler as calendarApi } from "./calendar-api.js";

// Ключ = значение поля "tool" из pipeline_spec.blocks[].tool
export const HANDLERS = {
  "mvp-core-nodes": mvpCoreNodes,
  // "calendar-api": calendarApi,
};
```

---

## `handlers/<tool_name>.js`

Один файл на каждый уникальный `tool`. Диспатч по `step.step` (тип узла).

```javascript
import { env } from "node:process";

/**
 * @param {{ step: string, node_config: object }} step
 * @param {Record<string, unknown>} ctx
 * @returns {Promise<unknown>}
 */
export async function handler(step, ctx) {
  const cfg = step.node_config ?? {};

  switch (step.step) {
    case "Trigger":
      return ctx["input"] ?? {};

    case "LLMCall":
      return llmCall(cfg, ctx);

    case "Branch":
      return branch(cfg, ctx);

    case "Notify": {
      const target = cfg["target"] ?? "default";
      console.log(`[Notify] → ${target}:`, ctx["step_2"]);
      return { notified: true };
    }

    case "SaveResult":
      ctx["output"] = ctx["step_2"];
      return ctx["output"];

    default:
      throw new Error(`TODO: ${step.step}`);
  }
}

async function llmCall(cfg, ctx) {
  const apiKey  = cfg["api_key"]       ?? env["LLM_API_KEY"] ?? "";
  const baseUrl = cfg["base_url"]      ?? "https://api.openai.com/v1";
  const model   = cfg["model"]         ?? "gpt-4o-mini";
  const promptTpl = cfg["system_prompt"] ?? "";
  const timeout = (cfg["timeout_s"]    ?? 30) * 1000;
  const prompt  = promptTpl.replace(/\{(\w+)\}/g, (_, k) => String(ctx[k] ?? ""));

  const resp = await fetch(`${baseUrl}/chat/completions`, {
    method: "POST",
    headers: { "Authorization": `Bearer ${apiKey}`, "Content-Type": "application/json" },
    body: JSON.stringify({ model, messages: [{ role: "user", content: prompt }] }),
    signal: AbortSignal.timeout(timeout),
  });
  if (!resp.ok) throw new Error(`LLM error: ${resp.status}`);
  const data = await resp.json();
  return { text: data.choices[0].message.content };
}

async function branch(cfg, ctx) {
  // Логика ветвления — читай предыдущий результат из ctx.
  // Верни { branch: "yes" | "no" | "error" } — runner выберет путь.
  const prev = ctx["step_2"] ?? {};
  if (prev["error"]) return { branch: "error" };
  const text = String(prev["text"] ?? "").toLowerCase();
  return { branch: text.includes("urgent") ? "yes" : "no" };
}
```

---

## Передача контекста между шагами

```
ctx["step_1"] = результат Trigger     // { ticket_id: 42, ... }
ctx["step_2"] = результат LLMCall     // { text: "URGENT: ..." }  ← читает Branch
ctx["step_3"] = результат Branch      // { branch: "yes" }
```

Ключи — `step_${step_slot}`. Используй точные номера из PLAN.

---

## Вложенные пайплайны (`subpipeline`)

Узел `step.step === "subpipeline"` → в `pipeline_spec.nested_pipelines[name]` лежит полный spec.
Сгенерируй `pipelines/<nested_name>.js` и вызови `run()` рекурсивно:

```javascript
case "subpipeline": {
  const name = cfg["nested_pipeline"]?.name;
  const { run: runNested } = await import(`./${name}.js`);
  return runNested(ctx);
}
```

---

## Справка: поля execution_plan

| Поле | Тип | Описание |
|---|---|---|
| `step_slot` | number | Номер шага 1..N (ключ PLAN) |
| `step` | string | Тип узла (LLMCall, Branch, …) |
| `tool` | string | Ключ в HANDLERS |
| `node_config` | object | Настройки экземпляра |
| `next` | number\|undefined | Следующий step_slot (линейно) |
| `branches` | object | `{ yes: slot, no: slot, error: slot }` |

## `package.json` минимум

```json
{
  "type": "module",
  "engines": { "node": ">=18" }
}
```
