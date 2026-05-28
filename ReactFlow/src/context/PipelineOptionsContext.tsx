import { createContext, useContext } from "react";
import type { Pipeline } from "../types";

export interface PipelineOptionsContextValue {
  pipelines: Pipeline[];
  currentPipelineId: number;
  projectName: string;
}

const PipelineOptionsContext = createContext<PipelineOptionsContextValue>({
  pipelines: [],
  currentPipelineId: 0,
  projectName: "",
});

export function PipelineOptionsProvider({
  value,
  children,
}: {
  value: PipelineOptionsContextValue;
  children: React.ReactNode;
}) {
  return (
    <PipelineOptionsContext.Provider value={value}>
      {children}
    </PipelineOptionsContext.Provider>
  );
}

export function usePipelineOptions() {
  return useContext(PipelineOptionsContext);
}
