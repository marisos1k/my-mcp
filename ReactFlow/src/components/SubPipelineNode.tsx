import { useReactFlow, type NodeProps } from "@xyflow/react";
import { useCallback } from "react";
import { api } from "../api";
import { usePipelineOptions } from "../context/PipelineOptionsContext";
import type { GraphNodeData, NodeUiSchema } from "../types";
import { PortNode } from "./PortNode";

function isSubPipelineNode(type: string | undefined, d: GraphNodeData) {
  return (
    type === "subpipeline" ||
    d.type_name === "subpipeline" ||
    d.ui?.react_component === "subpipeline"
  );
}

function applyInterface(
  data: GraphNodeData,
  iface: { inputs: NodeUiSchema["inputs"]; outputs: NodeUiSchema["outputs"] },
  nestedId: number,
  nestedName?: string
): GraphNodeData {
  const ui: NodeUiSchema = {
    react_component: "subpipeline",
    color: data.color ?? data.ui?.color ?? "#009688",
    inputs: iface.inputs,
    outputs: iface.outputs,
  };
  return {
    ...data,
    nested_pipeline_id: nestedId,
    nested_pipeline_name: nestedName,
    label: nestedName ?? data.label ?? data.type_name,
    ui,
    ports: { inputs: iface.inputs, outputs: iface.outputs },
  };
}

export function SubPipelineNode(props: NodeProps) {
  const { setNodes } = useReactFlow();
  const { pipelines, currentPipelineId, projectName } = usePipelineOptions();
  const d = props.data as GraphNodeData;

  const fromContext = pipelines.filter((p) => p.id !== currentPipelineId);
  const fromNode = (d.pipeline_options ?? []).filter(
    (p) => p.id !== currentPipelineId
  );
  const options = fromContext.length > 0 ? fromContext : fromNode;

  const value = d.nested_pipeline_id ?? "";

  const onSelectPipeline = useCallback(
    async (raw: string) => {
      const nestedId = raw ? Number(raw) : null;
      const nestedName =
        nestedId != null
          ? options.find((p) => p.id === nestedId)?.name
          : undefined;

      if (!nestedId) {
        setNodes((nds) =>
          nds.map((n) => {
            if (n.id !== props.id) return n;
            const data = n.data as GraphNodeData;
            return {
              ...n,
              data: {
                ...data,
                nested_pipeline_id: undefined,
                nested_pipeline_name: undefined,
                ports: {
                  inputs: [{ id: "in", label: "In" }],
                  outputs: [{ id: "out", label: "Out" }],
                },
                ui: {
                  react_component: "subpipeline",
                  color: "#009688",
                  inputs: [{ id: "in", label: "In" }],
                  outputs: [{ id: "out", label: "Out" }],
                },
              },
            };
          })
        );
        return;
      }

      try {
        const iface = await api.getPipelineInterface(nestedId);
        setNodes((nds) =>
          nds.map((n) => {
            if (n.id !== props.id) return n;
            const data = n.data as GraphNodeData;
            return {
              ...n,
              data: applyInterface(data, iface, nestedId, nestedName),
            };
          })
        );
      } catch {
        setNodes((nds) =>
          nds.map((n) => {
            if (n.id !== props.id) return n;
            const data = n.data as GraphNodeData;
            return {
              ...n,
              data: {
                ...data,
                nested_pipeline_id: nestedId,
                nested_pipeline_name: nestedName,
                label: nestedName ?? data.label,
              },
            };
          })
        );
      }
    },
    [options, props.id, setNodes]
  );

  const portCount = (d.ports?.inputs?.length ?? 0) + (d.ports?.outputs?.length ?? 0);

  return (
    <div
      className={`subpipeline-node-wrap${portCount > 4 ? " subpipeline-node-wrap-wide" : ""}`}
    >
      <PortNode {...props} />
      <div
        className="subpipeline-node-controls nodrag nopan"
        onPointerDown={(e) => e.stopPropagation()}
      >
        <label className="subpipeline-label">Вложенный пайплайн</label>
        <select
          className="subpipeline-select"
          value={value}
          onChange={(e) => void onSelectPipeline(e.target.value)}
        >
          <option value="">
            {options.length
              ? "— выбрать пайплайн —"
              : "— нет других пайплайнов в проекте —"}
          </option>
          {options.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        {d.nested_pipeline_id && d.ports ? (
          <p className="subpipeline-ports-summary">
            {d.ports.inputs.length} вх. / {d.ports.outputs.length} вых.
          </p>
        ) : null}
        {options.length === 0 ? (
          <p className="subpipeline-hint">
            Создайте ещё один пайплайн в проекте «
            {projectName || d.project_name || "…"}».
          </p>
        ) : null}
      </div>
    </div>
  );
}

export { isSubPipelineNode };
