import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import type { AgentTemplate, ApiKeyInfo, Pipeline, Project } from "../types";

export function ProjectsPage() {
  const { email, logout } = useAuth();
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [pipelines, setPipelines] = useState<Record<number, Pipeline[]>>({});
  const [templates, setTemplates] = useState<AgentTemplate[]>([]);
  const [apiKeys, setApiKeys] = useState<ApiKeyInfo[]>([]);
  const [newApiKeyName, setNewApiKeyName] = useState("default");
  const [createdApiKey, setCreatedApiKey] = useState("");
  const [copied, setCopied] = useState(false);
  const [newProject, setNewProject] = useState("");
  const [pipelineNames, setPipelineNames] = useState<Record<number, string>>({});
  const [selectedTemplate, setSelectedTemplate] = useState<Record<number, string>>(
    {}
  );
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [list, tpls] = await Promise.all([
        api.listProjects(),
        api.listAgentTemplates(),
      ]);
      const keys = await api.listApiKeys();
      setProjects(list);
      setTemplates(tpls);
      setApiKeys(keys);
      const map: Record<number, Pipeline[]> = {};
      await Promise.all(
        list.map(async (p) => {
          map[p.id] = await api.listPipelines(p.id);
        })
      );
      setPipelines(map);
      const defaultTpl = tpls[0]?.id ?? "";
      setSelectedTemplate((prev) => {
        const next = { ...prev };
        for (const p of list) {
          if (!next[p.id]) next[p.id] = defaultTpl;
        }
        return next;
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  }, []);

  async function createMcpApiKey(e: FormEvent) {
    e.preventDefault();
    const keyName = newApiKeyName.trim();
    if (!keyName) return;
    try {
      const res = await api.createApiKey(keyName);
      setCreatedApiKey(res.api_key);
      setCopied(false);
      const keys = await api.listApiKeys();
      setApiKeys(keys);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    }
  }

  async function revokeMcpApiKey(keyId: number) {
    try {
      await api.revokeApiKey(keyId);
      const keys = await api.listApiKeys();
      setApiKeys(keys);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    }
  }

  useEffect(() => {
    load();
  }, [load]);

  async function createProject(e: FormEvent) {
    e.preventDefault();
    if (!newProject.trim()) return;
    try {
      await api.createProject(newProject.trim());
      setNewProject("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    }
  }

  async function createEmptyPipeline(projectId: number) {
    const name = (pipelineNames[projectId] ?? "").trim();
    if (!name) return;
    try {
      const pl = await api.createPipeline(projectId, name);
      setPipelineNames((s) => ({ ...s, [projectId]: "" }));
      navigate(`/editor/${pl.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    }
  }

  async function createFromTemplate(projectId: number) {
    const name = (pipelineNames[projectId] ?? "").trim();
    const templateId = selectedTemplate[projectId];
    if (!name || !templateId) return;
    try {
      const graph = await api.createPipelineFromTemplate(
        projectId,
        name,
        templateId
      );
      setPipelineNames((s) => ({ ...s, [projectId]: "" }));
      navigate(`/editor/${graph.pipeline.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    }
  }

  return (
    <div className="projects-page">
      <header className="topbar">
        <div>
          <h1>Проекты</h1>
          <span className="muted">{email}</span>
        </div>
        <button type="button" className="btn-ghost" onClick={logout}>
          Выйти
        </button>
      </header>

      <section className="panel">
        <h2>Новый проект</h2>
        <form className="inline-form" onSubmit={createProject}>
          <input
            placeholder="Название проекта"
            value={newProject}
            onChange={(e) => setNewProject(e.target.value)}
          />
          <button type="submit">Создать</button>
        </form>
      </section>

      <section className="panel">
        <h2>MCP API ключи</h2>
        <form className="inline-form" onSubmit={createMcpApiKey}>
          <input
            placeholder="Имя ключа (например client-app)"
            value={newApiKeyName}
            onChange={(e) => setNewApiKeyName(e.target.value)}
          />
          <button type="submit">Создать ключ</button>
        </form>
        {createdApiKey ? (
          <div className="api-key-created">
            <p>
              Новый ключ (сохраните сейчас, позже его нельзя посмотреть снова):
            </p>
            <code>{createdApiKey}</code>
            <button
              type="button"
              className="btn-ghost"
              onClick={async () => {
                await navigator.clipboard.writeText(createdApiKey);
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
              }}
            >
              {copied ? "Скопировано" : "Копировать"}
            </button>
          </div>
        ) : null}
        <ul className="api-keys-list">
          {apiKeys.map((k) => (
            <li key={k.id} className="api-key-item">
              <div>
                <strong>{k.key_name}</strong>{" "}
                <span className="muted">{k.key_prefix}…</span>
                <div className="muted">
                  Создан: {new Date(k.created_at).toLocaleString()}
                  {k.last_used_at
                    ? ` · Использовался: ${new Date(k.last_used_at).toLocaleString()}`
                    : ""}
                </div>
              </div>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => revokeMcpApiKey(k.id)}
                disabled={!k.is_active}
              >
                {k.is_active ? "Деактивировать" : "Неактивен"}
              </button>
            </li>
          ))}
          {apiKeys.length === 0 ? (
            <li className="muted">Ключей пока нет</li>
          ) : null}
        </ul>
      </section>

      {error ? <div className="error banner">{error}</div> : null}
      {loading ? <p className="muted">Загрузка...</p> : null}

      <div className="project-grid">
        {projects.map((project) => (
          <article key={project.id} className="project-card">
            <h3>{project.name}</h3>
            <p className="muted">Пайплайны (workflow)</p>
            <ul className="pipeline-list">
              {(pipelines[project.id] ?? []).map((pl) => (
                <li key={pl.id}>
                  <Link to={`/editor/${pl.id}`}>{pl.name}</Link>
                </li>
              ))}
              {(pipelines[project.id] ?? []).length === 0 ? (
                <li className="muted">Пока нет пайплайнов</li>
              ) : null}
            </ul>

            <section className="template-section">
              <h4>Агентный пайплайн из шаблона</h4>
              <div className="template-grid">
                {templates.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    className={`template-card${
                      selectedTemplate[project.id] === t.id ? " selected" : ""
                    }`}
                    onClick={() =>
                      setSelectedTemplate((s) => ({
                        ...s,
                        [project.id]: t.id,
                      }))
                    }
                  >
                    <strong>{t.title}</strong>
                    <span className="muted">{t.description}</span>
                    <span className="template-meta">
                      {t.node_count} блоков · {t.edge_count} связей
                    </span>
                  </button>
                ))}
              </div>
              <div className="inline-form">
                <input
                  placeholder="Имя пайплайна"
                  value={pipelineNames[project.id] ?? ""}
                  onChange={(e) =>
                    setPipelineNames((s) => ({
                      ...s,
                      [project.id]: e.target.value,
                    }))
                  }
                />
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => createFromTemplate(project.id)}
                  disabled={!selectedTemplate[project.id]}
                >
                  Создать по шаблону
                </button>
              </div>
            </section>

            <details className="empty-pipeline-details">
              <summary>Пустой пайплайн</summary>
              <div className="inline-form">
                <input
                  placeholder="Имя пайплайна"
                  value={pipelineNames[project.id] ?? ""}
                  onChange={(e) =>
                    setPipelineNames((s) => ({
                      ...s,
                      [project.id]: e.target.value,
                    }))
                  }
                />
                <button type="button" onClick={() => createEmptyPipeline(project.id)}>
                  Открыть пустой редактор
                </button>
              </div>
            </details>
          </article>
        ))}
      </div>
    </div>
  );
}
