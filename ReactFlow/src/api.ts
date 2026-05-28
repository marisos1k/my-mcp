import type {
  ApiKeyInfo,
  AgentTemplate,
  ExecutionPlanStep,
  NodeTypeCatalogItem,
  Pipeline,
  PipelineGraphResponse,
  PipelineInterface,
  Project,
  TokenResponse,
} from "./types";

const TOKEN_KEY = "pipeline_studio_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(path, { ...options, headers });
  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      const err = await res.json();
      detail = err.detail ?? err;
    } catch {
      /* ignore */
    }
    if (Array.isArray(detail)) {
      throw new Error(
        detail
          .map((d: { loc?: unknown[]; msg?: string }) =>
            `${(d.loc ?? []).join(".")}: ${d.msg ?? ""}`.trim()
          )
          .join("; ")
      );
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

export const api = {
  register(email: string, password: string) {
    return request<TokenResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },
  login(email: string, password: string) {
    return request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },
  me() {
    const token = getToken();
    return request<{ id: number; email: string }>(
      `/auth/me?token=${encodeURIComponent(token ?? "")}`
    );
  },
  createApiKey(keyName: string) {
    const token = getToken();
    return request<{ api_key: string }>(
      `/api/keys?token=${encodeURIComponent(token ?? "")}`,
      {
        method: "POST",
        body: JSON.stringify({ key_name: keyName }),
      }
    );
  },
  listApiKeys() {
    const token = getToken();
    return request<ApiKeyInfo[]>(
      `/api/keys?token=${encodeURIComponent(token ?? "")}`
    );
  },
  revokeApiKey(keyId: number) {
    const token = getToken();
    return request<{ ok: boolean }>(
      `/api/keys/revoke?token=${encodeURIComponent(token ?? "")}`,
      {
        method: "POST",
        body: JSON.stringify({ key_id: keyId }),
      }
    );
  },
  listProjects() {
    const token = getToken();
    return request<Project[]>(`/api/projects?token=${encodeURIComponent(token ?? "")}`);
  },
  createProject(name: string) {
    const token = getToken();
    return request<Project>(
      `/api/projects?token=${encodeURIComponent(token ?? "")}&name=${encodeURIComponent(name)}`,
      { method: "POST" }
    );
  },
  listPipelines(projectId: number) {
    const token = getToken();
    return request<Pipeline[]>(
      `/api/projects/${projectId}/pipelines?token=${encodeURIComponent(token ?? "")}`
    );
  },
  createPipeline(projectId: number, name: string, report?: string) {
    return request<Pipeline>(`/api/projects/${projectId}/pipelines`, {
      method: "POST",
      body: JSON.stringify({ name, report: report || null }),
    });
  },
  listAgentTemplates() {
    return request<AgentTemplate[]>("/api/catalog/agent-templates");
  },
  createPipelineFromTemplate(
    projectId: number,
    name: string,
    templateId: string,
    report?: string
  ) {
    return request<PipelineGraphResponse>(
      `/api/projects/${projectId}/pipelines/from-template`,
      {
        method: "POST",
        body: JSON.stringify({
          name,
          template_id: templateId,
          report: report || null,
        }),
      }
    );
  },
  getGraph(pipelineId: number) {
    return request<PipelineGraphResponse>(`/api/pipelines/${pipelineId}/graph`);
  },
  saveGraph(
    pipelineId: number,
    payload: {
      nodes: Array<{
        id: string;
        type_id: number;
        position: { x: number; y: number };
        label?: string;
        nested_pipeline_id?: number | null;
        node_config?: Record<string, unknown> | null;
      }>;
      edges: Array<{
        source: string;
        target: string;
        source_handle?: string;
        target_handle?: string;
      }>;
    }
  ) {
    return request<PipelineGraphResponse>(`/api/pipelines/${pipelineId}/graph`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },
  getExecutionPlan(pipelineId: number) {
    return request<{
      execution_plan: ExecutionPlanStep[];
      connections: unknown[];
    }>(`/api/pipelines/${pipelineId}/execution-plan`);
  },
  listNodeTypes() {
    return request<NodeTypeCatalogItem[]>("/api/catalog/node-types");
  },
  getPipelineInterface(pipelineId: number) {
    return request<PipelineInterface>(
      `/api/pipelines/${pipelineId}/interface`
    );
  },
};
