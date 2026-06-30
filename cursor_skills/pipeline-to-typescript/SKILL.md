---
name: pipeline-to-typescript
description: >-
  Generates TypeScript implementation from a BrAIniac pipeline spec.
  Use when the user asks to export or implement a pipeline as TypeScript code.
---

# Pipeline → TypeScript

## Когда применять

Запросы: «экспортируй в TypeScript», «сгенерируй TS код», «реализуй пайплайн на TypeScript».

## Шаги

1. Вызвать `export_pipeline_as_code(api_key, project_name, pipeline_name, language="typescript")`.
2. Из ответа: `pipeline_spec` — данные графа, `workflow` — эти инструкции.
3. Создать файлы ниже (уточнить у пользователя целевую папку проекта).
4. Не выводить сырой JSON — только код и список созданных файлов.

## Структура файлов

```
src/pipelines/<pipeline_name>.ts   # runner пайплайна
src/handlers/index.ts              # реестр HANDLERS
src/handlers/<tool_name>.ts        # хендлер для каждого уникального blocks[].tool
```

---

## Типы (`src/types.ts`)

```typescript
export interface PipelineStep {
  step: string;
  tool: string;
  node_config: Record<string, unknown>;
  next?: number;
  branches?: Record<string, number>;
}

export type PipelineCtx = Record<string, unknown>;
export type Handler = (step: PipelineStep, ctx: PipelineCtx) => Promise<unknown>;
```

---

## `src/pipelines/<pipeline_name>.ts`

Заполни `PLAN` из `execution_plan`, константы из `limits`.

```typescript
import { HANDLERS } from "../handlers/index.js";
import type { PipelineCtx, PipelineStep } from "../types.js";

const MAX_TIME     = <limits.max_time>;          // сек; из pipeline_spec.limits
const MAX_COST     = <limits.max_cost>;
const MAX_FAIL_PCT = <limits.max_fail_percent>;

// Сгенерировано из pipeline_spec.execution_plan
const PLAN: Record<number, PipelineStep> = {
  1: { step: "Trigger",    tool: "mvp-core-nodes", node_config: {},                        next: 2 },
  2: { step: "LLMCall",   tool: "mvp-core-nodes", node_config: { model: "gpt-4o-mini" }, next: 3 },
  3: { step: "Branch",    tool: "mvp-core-nodes", node_config: {},
       branches: { yes: 4, no: 5, error: 6 } },
  4: { step: "Notify",    tool: "mvp-core-nodes", node_config: {} },
  5: { step: "SaveResult",tool: "mvp-core-nodes", node_config: {} },
  6: { step: "SaveResult",tool: "mvp-core-nodes", node_config: {} },
};

export async function run(initialCtx: PipelineCtx = {}): Promise<PipelineCtx> {
  const ctx: PipelineCtx = { ...initialCtx };
  let current: number | undefined = Math.min(...Object.keys(PLAN).map(Number));

  while (current !== undefined) {
    const step = PLAN[current];
    const handler = HANDLERS[step.tool];
    if (!handler) throw new Error(`No handler for tool: ${step.tool}`);

    const result = await handler(step, ctx);
    ctx[`step_${current}`] = result;             // результат доступен следующим шагам

    if (step.branches) {
      const port = (result as Record<string, string>)?.branch ?? "error";
      current = step.branches[port];
    } else {
      current = step.next;
    }
  }

  return ctx;
}
```

---

## `src/handlers/index.ts`

```typescript
import { handler as mvpCoreNodes } from "./mvp-core-nodes.js";
// import { handler as calendarApi } from "./calendar-api.js";

// Ключ = значение поля "tool" из pipeline_spec.blocks[].tool
export const HANDLERS: Record<string, (step: any, ctx: any) => Promise<unknown>> = {
  "mvp-core-nodes": mvpCoreNodes,
  // "calendar-api": calendarApi,
};
```

---

## `src/handlers/<tool_name>.ts`

Один файл на каждый уникальный `tool`. Диспатч по `step.step` (тип узла).

```typescript
import type { Handler, PipelineCtx, PipelineStep } from "../types.js";

export const handler: Handler = async (step, ctx) => {
  const cfg = (step.node_config ?? {}) as Record<string, unknown>;

  switch (step.step) {
    case "Trigger":
      return ctx["input"] ?? {};

    case "LLMCall":
      return llmCall(cfg, ctx);

    case "Branch":
      return branch(cfg, ctx);

    case "Notify": {
      const target = (cfg["target"] as string) ?? "default";
      console.log(`[Notify] → ${target}:`, ctx["step_2"]);
      return { notified: true };
    }

    case "SaveResult":
      ctx["output"] = ctx["step_2"];
      return ctx["output"];

    default:
      throw new Error(`TODO: ${step.step}`);
  }
};

async function llmCall(cfg: Record<string, unknown>, ctx: PipelineCtx): Promise<unknown> {
  const apiKey   = (cfg["api_key"]       as string) ?? process.env["LLM_API_KEY"] ?? "";
  const baseUrl  = (cfg["base_url"]      as string) ?? "https://api.openai.com/v1";
  const model    = (cfg["model"]         as string) ?? "gpt-4o-mini";
  const promptTpl= (cfg["system_prompt"] as string) ?? "";
  const timeout  = (cfg["timeout_s"]     as number) ?? 30;
  const prompt   = promptTpl.replace(/\{(\w+)\}/g, (_, k) => String(ctx[k] ?? ""));

  const resp = await fetch(`${baseUrl}/chat/completions`, {
    method: "POST",
    headers: { "Authorization": `Bearer ${apiKey}`, "Content-Type": "application/json" },
    body: JSON.stringify({ model, messages: [{ role: "user", content: prompt }] }),
    signal: AbortSignal.timeout(timeout * 1000),
  });
  if (!resp.ok) throw new Error(`LLM error: ${resp.status}`);
  const data = await resp.json() as { choices: { message: { content: string } }[] };
  return { text: data.choices[0].message.content };
}

async function branch(cfg: Record<string, unknown>, ctx: PipelineCtx): Promise<unknown> {
  // Логика ветвления — читай предыдущий результат из ctx.
  // Верни { branch: "yes" | "no" | "error" } — runner выберет путь.
  const prev = (ctx["step_2"] ?? {}) as Record<string, unknown>;
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
Сгенерируй `src/pipelines/<nested_name>.ts` и вызови `run()` рекурсивно:

```typescript
case "subpipeline": {
  const name = (cfg["nested_pipeline"] as any)?.name as string;
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

## `tsconfig.json` минимум

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "outDir": "dist"
  }
}
```
