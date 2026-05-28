import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { GraphNodeData } from "../types";

export function WorkflowNode({ data, selected }: NodeProps) {
  const d = data as GraphNodeData;
  return (
    <div className={`workflow-node ${selected ? "selected" : ""}`}>
      <Handle type="target" position={Position.Left} />
      <div className="workflow-node-title">{d.label || d.type_name}</div>
      <div className="workflow-node-tool">{d.tool_name}</div>
      {d.type_description ? (
        <div className="workflow-node-desc">{d.type_description}</div>
      ) : null}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
