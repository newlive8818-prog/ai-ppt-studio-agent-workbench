export type SpaceId = "overview" | "materials" | "blueprint" | "visual" | "delivery";

export interface ProjectSnapshot {
  schema_version: string;
  revision: number;
  updated_at: string;
  active_space: SpaceId;
  project: {
    project_id: string;
    name: string;
    project_root: string;
  };
  gate_state: {
    current_gate: string;
    gates: Record<string, string>;
  };
  cognition_map: {
    delivery_goal: string;
    audiences: string[];
    problem: string;
    ai_judgment: string;
    facts: Array<Record<string, unknown>>;
    confirmed_decisions: Array<Record<string, unknown>>;
    uncertainty: string;
    affected_artifacts: string[];
    outcome_status: string;
    dialogue_focus: string;
  };
  artifacts: Record<string, {
    kind: string;
    version: number;
    path: string;
    sha256: string;
    created_at: string;
  }>;
  current_decision: {
    target_ref: string;
    status: string;
    question: string;
    why_now?: string;
    options?: string[];
    recommended_choice?: string;
    reversible?: boolean;
  };
  last_human_decision_id: string | null;
  allowed_next_actions: string[];
}

export interface WidgetData {
  snapshot: ProjectSnapshot;
  selectedProjectRoot?: string;
  initialSpace?: SpaceId;
  requestedDisplayMode?: "inline" | "fullscreen";
}

export interface DecisionResult {
  decision: Record<string, unknown>;
  snapshot: ProjectSnapshot;
  follow_up_message: string;
  model_context: Record<string, unknown>;
  affected_artifacts: string[];
}

export interface HostBridge {
  connect(onData?: (data: WidgetData) => void): Promise<void>;
  callTool(name: string, args: Record<string, unknown>): Promise<DecisionResult>;
  updateModelContext(context: Record<string, unknown>): Promise<void>;
  sendFollowUp(message: string): Promise<void>;
  requestDisplayMode(mode: "inline" | "fullscreen"): Promise<void>;
  notifySize(): void;
}

declare global {
  interface Window {
    __AI_PPT_PREVIEW__?: WidgetData;
    openai?: Record<string, unknown>;
  }
}
