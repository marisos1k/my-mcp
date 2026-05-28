import { useReactFlow, type NodeProps } from "@xyflow/react";
import { useMemo, useState } from "react";
import type { GraphNodeData } from "../types";
import { PortNode } from "./PortNode";

type LlmNodeConfig = {
  api_key?: string;
  base_url?: string;
  model?: string;
  system_prompt?: string;
  temperature?: number;
  timeout_s?: number;
};

function readCfg(d: GraphNodeData): LlmNodeConfig {
  const raw = (d.node_config ?? {}) as Record<string, unknown>;
  return {
    api_key: typeof raw.api_key === "string" ? raw.api_key : undefined,
    base_url: typeof raw.base_url === "string" ? raw.base_url : undefined,
    model: typeof raw.model === "string" ? raw.model : undefined,
    system_prompt: typeof raw.system_prompt === "string" ? raw.system_prompt : undefined,
    temperature: typeof raw.temperature === "number" ? raw.temperature : undefined,
    timeout_s: typeof raw.timeout_s === "number" ? raw.timeout_s : undefined,
  };
}

function maskKey(key?: string) {
  if (!key) return "";
  if (key.length <= 8) return "********";
  return `${key.slice(0, 3)}…${key.slice(-4)}`;
}

export function LLMNode(props: NodeProps) {
  const { setNodes } = useReactFlow();
  const d = props.data as GraphNodeData;
  const cfg = useMemo(() => readCfg(d), [d]);
  const [open, setOpen] = useState(false);
  const [showKey, setShowKey] = useState(false);

  return (
    <div className="llm-node-wrap">
      <PortNode {...props} />
      <div
        className="llm-node-controls nodrag nopan"
        onPointerDown={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          className="llm-settings-btn"
          onClick={() => setOpen((v) => !v)}
        >
          Настройки LLM
        </button>
        <div className="llm-settings-summary">
          <span className="muted">
            {cfg.model ? `model: ${cfg.model}` : "model: (env)"}
          </span>
          <span className="muted">
            {cfg.api_key ? `key: ${maskKey(cfg.api_key)}` : "key: (env)"}
          </span>
        </div>

        {open ? (
          <div className="llm-settings-panel">
            <label>
              Base URL
              <input
                value={cfg.base_url ?? ""}
                placeholder="https://api.openai.com"
                onChange={(e) => {
                  const base_url = e.target.value;
                  setNodes((nds) =>
                    nds.map((n) => {
                      if (n.id !== props.id) return n;
                      const data = n.data as GraphNodeData;
                      return {
                        ...n,
                        data: {
                          ...data,
                          node_config: {
                            ...(data.node_config ?? {}),
                            base_url: base_url || undefined,
                          },
                        },
                      };
                    })
                  );
                }}
              />
            </label>

            <label>
              Model
              <input
                value={cfg.model ?? ""}
                placeholder="gpt-4o-mini"
                onChange={(e) => {
                  const model = e.target.value;
                  setNodes((nds) =>
                    nds.map((n) => {
                      if (n.id !== props.id) return n;
                      const data = n.data as GraphNodeData;
                      return {
                        ...n,
                        data: {
                          ...data,
                          node_config: {
                            ...(data.node_config ?? {}),
                            model: model || undefined,
                          },
                        },
                      };
                    })
                  );
                }}
              />
            </label>

            <label>
              API key
              <div className="llm-key-row">
                <input
                  type={showKey ? "text" : "password"}
                  value={cfg.api_key ?? ""}
                  placeholder="sk-…"
                  onChange={(e) => {
                    const api_key = e.target.value;
                    setNodes((nds) =>
                      nds.map((n) => {
                        if (n.id !== props.id) return n;
                        const data = n.data as GraphNodeData;
                        return {
                          ...n,
                          data: {
                            ...data,
                            node_config: {
                              ...(data.node_config ?? {}),
                              api_key: api_key || undefined,
                            },
                          },
                        };
                      })
                    );
                  }}
                />
                <button
                  type="button"
                  className="btn-ghost"
                  onClick={() => setShowKey((v) => !v)}
                >
                  {showKey ? "Скрыть" : "Показать"}
                </button>
              </div>
            </label>

            <label>
              System prompt
              <textarea
                value={cfg.system_prompt ?? ""}
                placeholder="(опционально)"
                onChange={(e) => {
                  const system_prompt = e.target.value;
                  setNodes((nds) =>
                    nds.map((n) => {
                      if (n.id !== props.id) return n;
                      const data = n.data as GraphNodeData;
                      return {
                        ...n,
                        data: {
                          ...data,
                          node_config: {
                            ...(data.node_config ?? {}),
                            system_prompt: system_prompt || undefined,
                          },
                        },
                      };
                    })
                  );
                }}
              />
            </label>

            <div className="llm-grid-2">
              <label>
                Temperature
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="2"
                  value={cfg.temperature ?? ""}
                  onChange={(e) => {
                    const v = e.target.value;
                    const temperature = v === "" ? undefined : Number(v);
                    setNodes((nds) =>
                      nds.map((n) => {
                        if (n.id !== props.id) return n;
                        const data = n.data as GraphNodeData;
                        return {
                          ...n,
                          data: {
                            ...data,
                            node_config: {
                              ...(data.node_config ?? {}),
                              temperature,
                            },
                          },
                        };
                      })
                    );
                  }}
                />
              </label>
              <label>
                Timeout (s)
                <input
                  type="number"
                  step="1"
                  min="1"
                  value={cfg.timeout_s ?? ""}
                  onChange={(e) => {
                    const v = e.target.value;
                    const timeout_s = v === "" ? undefined : Number(v);
                    setNodes((nds) =>
                      nds.map((n) => {
                        if (n.id !== props.id) return n;
                        const data = n.data as GraphNodeData;
                        return {
                          ...n,
                          data: {
                            ...data,
                            node_config: {
                              ...(data.node_config ?? {}),
                              timeout_s,
                            },
                          },
                        };
                      })
                    );
                  }}
                />
              </label>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

