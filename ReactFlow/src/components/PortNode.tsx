import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { GraphNodeData, PortDef } from "../types";

function handleTop(index: number, total: number): string {
  if (total <= 1) return "50%";
  return `${((index + 1) / (total + 1)) * 100}%`;
}

export function PortNode({ data, selected }: NodeProps) {
  const d = data as GraphNodeData;
  const color = d.color || "#3d5afe";
  const inputs: PortDef[] = d.ports?.inputs?.length
    ? d.ports.inputs
    : [{ id: "in", label: "In" }];
  const outputs: PortDef[] = d.ports?.outputs?.length
    ? d.ports.outputs
    : [{ id: "out", label: "Out" }];

  return (
    <div
      className={`port-node ${selected ? "selected" : ""}`}
      style={{ borderColor: color, boxShadow: selected ? `0 0 0 2px ${color}` : undefined }}
    >
      {inputs.map((p, i) => (
        <Handle
          key={`in-${p.id}`}
          id={p.id}
          type="target"
          position={Position.Left}
          style={{ top: handleTop(i, inputs.length) }}
          title={p.label}
        />
      ))}
      <div className="port-node-title">{d.label || d.type_name}</div>
      <div className="port-node-tool">{d.tool_name}</div>
      {outputs.map((p, i) => (
        <Handle
          key={`out-${p.id}`}
          id={p.id}
          type="source"
          position={Position.Right}
          style={{ top: handleTop(i, outputs.length) }}
          title={p.label}
        />
      ))}
      {outputs.map((p, i) => (
        <span
          key={`lbl-${p.id}`}
          className="port-label port-label-out"
          style={{ top: handleTop(i, outputs.length) }}
        >
          {p.label}
        </span>
      ))}
    </div>
  );
}
