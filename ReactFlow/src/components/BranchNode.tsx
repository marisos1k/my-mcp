import { PortNode } from "./PortNode";
import type { NodeProps } from "@xyflow/react";

/** Ветвление да / нет / ошибка — схема портов задаётся в tools.config (тип branch). */
export function BranchNode(props: NodeProps) {
  return (
    <div className="branch-node-wrap">
      <PortNode {...props} />
    </div>
  );
}
