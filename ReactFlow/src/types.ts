export interface TokenResponse {
  access_token: string;
  token_type: string;
  user_id: number;
  email: string;
}

export interface Project {
  id: number;
  name: string;
}

export interface Pipeline {
  id: number;
  name: string;
  report?: string | null;
}

export interface AgentTemplate {
  id: string;
  title: string;
  description: string;
  category: string;
  node_count: number;
  edge_count: number;
}

export interface ApiKeyInfo {
  id: number;
  key_name: string;
  key_prefix: string;
  is_active: boolean;
  created_at: string;
  last_used_at?: string | null;
}

export interface PortDef {
  id: string;
  label: string;
}

export interface PipelineInterface {
  pipeline_id: number;
  inputs: PortDef[];
  outputs: PortDef[];
}

export interface NodeUiSchema {
  react_component: string;
  color?: string;
  inputs: PortDef[];
  outputs: PortDef[];
}

export interface NodeTypeCatalogItem {
  id: number;
  name: string;
  description: string | null;
  tool_id: number;
  tool_name: string;
  react_component: string;
  ui: NodeUiSchema;
  tool_config?: Record<string, unknown>;
}

export interface GraphNodeData {
  label: string;
  type_id: number;
  type_name: string;
  type_description?: string | null;
  tool_name: string;
  report?: string | null;
  node_config?: Record<string, unknown>;
  nested_pipeline_id?: number | null;
  nested_pipeline_name?: string | null;
  project_name?: string | null;
  pipeline_options?: Pipeline[];
  ui?: NodeUiSchema;
  ports?: { inputs: PortDef[]; outputs: PortDef[] };
  color?: string;
}

export interface PipelineGraphResponse {
  pipeline: {
    id: number;
    name: string;
    project_id: number;
    project_name: string;
    report?: string | null;
  };
  /** Другие пайплайны того же проекта (для блока subpipeline). */
  available_pipelines?: Pipeline[];
  nodes: Array<{
    id: string;
    type: string;
    position: { x: number; y: number };
    data: GraphNodeData;
  }>;
  edges: Array<{
    id: string;
    source: string;
    target: string;
    sourceHandle?: string;
    targetHandle?: string;
    type?: string;
    animated?: boolean;
    label?: string | null;
  }>;
}

export interface ExecutionPlanStep {
  step_slot: number;
  step: string;
  tool: string;
  description?: string | null;
  react_component?: string;
  next?: number;
  branches?: Record<
    string,
    { to_step: number; to_node_type?: string }
  >;
}
