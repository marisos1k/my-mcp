import type { NodeTypes } from "@xyflow/react";
import { BranchNode } from "./BranchNode";
import { LLMNode } from "./LLMNode";
import { PortNode } from "./PortNode";
import { SubPipelineNode } from "./SubPipelineNode";
import { WorkflowNode } from "./WorkflowNode";

export const nodeTypes: NodeTypes = {
  workflow: PortNode,
  llm: LLMNode,
  branch: BranchNode,
  subpipeline: SubPipelineNode,
  /** @deprecated alias */
  default: WorkflowNode,
};
