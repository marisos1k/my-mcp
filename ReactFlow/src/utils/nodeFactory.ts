import type { Node } from "@xyflow/react";
import type {
  GraphNodeData,
  NodeTypeCatalogItem,
  PipelineGraphResponse,
} from "../types";

export function catalogItemToNode(
  item: NodeTypeCatalogItem,
  id: string,
  position: { x: number; y: number },
  extra?: Partial<GraphNodeData>
): Node {
  const ui = item.ui;
  const component = item.react_component || ui?.react_component || "workflow";
  const data: GraphNodeData = {
    label: item.name,
    type_id: item.id,
    type_name: item.name,
    type_description: item.description,
    tool_name: item.tool_name,
    ui,
    ports: {
      inputs: ui?.inputs ?? [{ id: "in", label: "In" }],
      outputs: ui?.outputs ?? [{ id: "out", label: "Out" }],
    },
    color: ui?.color,
    ...extra,
  };
  return {
    id,
    type: component,
    position,
    data,
  };
}

export function graphNodeToFlowNode(
  n: PipelineGraphResponse["nodes"][number]
): Node {
  const rawCfg = n.data.node_config;
  const node_config =
    typeof rawCfg === "string"
      ? (() => {
          try {
            const parsed = JSON.parse(rawCfg);
            return typeof parsed === "object" && parsed ? parsed : {};
          } catch {
            return {};
          }
        })()
      : rawCfg ?? {};
  return {
    id: n.id,
    type: n.type,
    position: n.position,
    data: { ...n.data, node_config },
  };
}
