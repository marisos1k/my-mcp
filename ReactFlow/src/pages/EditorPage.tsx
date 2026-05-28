import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  addEdge,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { isSubPipelineNode } from "../components/SubPipelineNode";
import { nodeTypes } from "../components/nodeTypes";
import {
  PipelineOptionsProvider,
} from "../context/PipelineOptionsContext";
import type {
  ExecutionPlanStep,
  GraphNodeData,
  NodeTypeCatalogItem,
  Pipeline,
} from "../types";
import { catalogItemToNode, graphNodeToFlowNode } from "../utils/nodeFactory";

let idSeq = 1;
function newNodeId() {
  return `new-${Date.now()}-${idSeq++}`;
}

function withSubPipelineOptions(
  nds: Node[],
  opts: Pipeline[],
  projectName: string
): Node[] {
  return nds.map((n) => {
    const d = n.data as GraphNodeData;
    if (!isSubPipelineNode(n.type, d)) {
      return n;
    }
    return {
      ...n,
      data: {
        ...d,
        project_name: projectName,
        pipeline_options: opts,
      },
    };
  });
}

export function EditorPage() {
  const { pipelineId } = useParams<{ pipelineId: string }>();
  const pid = Number(pipelineId);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [title, setTitle] = useState("");
  const [projectName, setProjectName] = useState("");
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [catalog, setCatalog] = useState<NodeTypeCatalogItem[]>([]);
  const [selectedTypeId, setSelectedTypeId] = useState<number | "">("");
  const [plan, setPlan] = useState<ExecutionPlanStep[]>([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!pid) return;
    setLoading(true);
    setError("");
    try {
      const [graph, types, exec] = await Promise.all([
        api.getGraph(pid),
        api.listNodeTypes(),
        api.getExecutionPlan(pid),
      ]);
      const prId = graph.pipeline.project_id;
      const prName = graph.pipeline.project_name;
      const nestedOpts =
        graph.available_pipelines ??
        (await api.listPipelines(prId)).filter((p) => p.id !== pid);

      setPipelines(nestedOpts);
      setCatalog(types);
      if (types.length) {
        setSelectedTypeId((prev) => (prev === "" ? types[0].id : prev));
      }
      setTitle(graph.pipeline.name);
      setProjectName(prName);
      setNodes(
        withSubPipelineOptions(
          graph.nodes.map(graphNodeToFlowNode),
          nestedOpts,
          prName
        )
      );
      setEdges(
        graph.edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          sourceHandle: e.sourceHandle,
          targetHandle: e.targetHandle,
          type: "smoothstep",
          animated: true,
          label: e.label ?? e.sourceHandle,
        }))
      );
      setPlan(exec.execution_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  }, [pid, setNodes, setEdges]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!pipelines.length && !projectName) return;
    setNodes((nds) => withSubPipelineOptions(nds, pipelines, projectName));
  }, [pipelines, projectName, setNodes]);

  const onConnect = useCallback(
    (connection: Connection) =>
      setEdges((eds) =>
        addEdge(
          {
            ...connection,
            type: "smoothstep",
            animated: true,
            label: connection.sourceHandle ?? undefined,
          },
          eds
        )
      ),
    [setEdges]
  );

  const addBlock = useCallback(() => {
    if (selectedTypeId === "") return;
    const item = catalog.find((c) => c.id === selectedTypeId);
    if (!item) return;
    const component =
      item.react_component || item.ui?.react_component || "workflow";
    const extra: Partial<GraphNodeData> | undefined =
      component === "subpipeline"
        ? {
            project_name: projectName,
            pipeline_options: pipelines,
          }
        : undefined;

    setNodes((nds) =>
      withSubPipelineOptions(
        [
          ...nds,
          catalogItemToNode(
            item,
            newNodeId(),
            {
              x: 120 + nds.length * 40,
              y: 80 + nds.length * 60,
            },
            extra
          ),
        ],
        pipelines,
        projectName
      )
    );
  }, [catalog, selectedTypeId, setNodes, pipelines, projectName]);

  const save = useCallback(async () => {
    if (!pid) return;
    setStatus("Сохранение...");
    setError("");
    try {
      const payload = {
        nodes: nodes.map((n) => {
          const d = n.data as GraphNodeData;
          return {
            id: n.id,
            type_id: d.type_id,
            position: n.position,
            label: d.label,
            nested_pipeline_id: d.nested_pipeline_id ?? null,
            node_config: d.node_config ?? null,
          };
        }),
        edges: edges.map((e) => ({
          source: e.source,
          target: e.target,
          source_handle: e.sourceHandle ?? undefined,
          target_handle: e.targetHandle ?? undefined,
        })),
      };
      const graph = await api.saveGraph(pid, payload);
      const nestedOpts =
        graph.available_pipelines ??
        pipelines.filter((p) => p.id !== pid);
      setPipelines(nestedOpts);
      setNodes(
        withSubPipelineOptions(
          graph.nodes.map(graphNodeToFlowNode),
          nestedOpts,
          graph.pipeline.project_name
        )
      );
      setEdges(
        graph.edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          sourceHandle: e.sourceHandle,
          targetHandle: e.targetHandle,
          type: "smoothstep",
          animated: true,
          label: e.label ?? e.sourceHandle,
        }))
      );
      const exec = await api.getExecutionPlan(pid);
      setPlan(exec.execution_plan);
      setStatus("Сохранено");
      setTimeout(() => setStatus(""), 2000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка сохранения");
      setStatus("");
    }
  }, [pid, nodes, edges, setNodes, setEdges, pipelines]);

  const refreshPlan = useCallback(async () => {
    if (!pid) return;
    try {
      const exec = await api.getExecutionPlan(pid);
      setPlan(exec.execution_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка плана");
    }
  }, [pid]);

  const pipelineOptionsValue = useMemo(
    () => ({ pipelines, currentPipelineId: pid, projectName }),
    [pipelines, pid, projectName]
  );

  const proOptions = useMemo(() => ({ hideAttribution: true }), []);

  if (loading) {
    return <div className="editor-loading">Загрузка редактора...</div>;
  }

  return (
    <div className="editor-layout editor-layout-wide">
      <aside className="sidebar">
        <Link to="/" className="back-link">
          ← Проекты
        </Link>
        <h2>{title}</h2>
        <p className="muted">{projectName}</p>

        <h3>Блоки</h3>
        <select
          value={selectedTypeId}
          onChange={(e) =>
            setSelectedTypeId(e.target.value ? Number(e.target.value) : "")
          }
        >
          {catalog.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} ({c.tool_name})
              {c.react_component === "branch" ? " — ветвление" : ""}
              {c.react_component === "subpipeline" ? " — пайплайн" : ""}
            </option>
          ))}
        </select>
        <button type="button" className="btn-block" onClick={addBlock}>
          + Добавить на холст
        </button>

        {pipelines.length === 0 ? (
          <p className="hint">
            Для вложенного пайплайна создайте в этом проекте ещё один workflow
            (кроме текущего).
          </p>
        ) : null}

        <button type="button" className="btn-primary" onClick={save}>
          Сохранить workflow
        </button>
        <button type="button" className="btn-ghost" onClick={refreshPlan}>
          Обновить план
        </button>
        {status ? <p className="status-ok">{status}</p> : null}
        {error ? <p className="error">{error}</p> : null}

        <h3>План выполнения</h3>
        <ul className="plan-list">
          {plan.map((s) => (
            <li key={s.step_slot}>
              <strong>#{s.step_slot}</strong> {s.step}
              {s.branches ? (
                <ul>
                  {Object.entries(s.branches).map(([port, b]) => (
                    <li key={port}>
                      {port} → шаг {b.to_step}
                    </li>
                  ))}
                </ul>
              ) : s.next ? (
                <span className="muted"> → {s.next}</span>
              ) : null}
            </li>
          ))}
        </ul>

        <p className="hint">
          Тяните связь от нужного выхода (да / нет / ошибка у блока branch) к
          входу следующего узла.
        </p>
      </aside>

      <div className="canvas-wrap">
        <PipelineOptionsProvider value={pipelineOptionsValue}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            nodeTypes={nodeTypes}
            fitView
            proOptions={proOptions}
            deleteKeyCode={["Backspace", "Delete"]}
          >
            <Background gap={16} size={1} />
            <Controls />
            <MiniMap />
          </ReactFlow>
        </PipelineOptionsProvider>
      </div>
    </div>
  );
}
