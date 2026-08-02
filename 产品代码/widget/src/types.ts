export type SpaceId = "overview" | "materials" | "blueprint" | "visual" | "delivery";

export interface AgentTaskSummary {
  task_id: string;
  action_type: string;
  status: string;
  updated_at?: string;
}

export interface MaterialsProjection {
  status: string;
  source_count: number;
  summary: string;
  sources: Array<{
    source_id: string;
    source_ref: string;
    name: string;
    kind: string;
    mode: string;
    size_bytes: number | null;
    classification: string;
    purposes: string[];
    status: string;
  }>;
  findings: Array<{
    finding_id: string;
    finding_type: string;
    content: string;
    source_ref: string;
    locator: string;
    fact_status: string;
    purposes: string[];
  }>;
  conflicts: string[];
  gaps: string[];
  active_task: AgentTaskSummary | null;
}

export interface BlueprintSlide {
  slide_id: string;
  title: string;
  role: string;
  purpose: string;
  claim: string;
  visible_content: string[];
  speaker_notes: string;
  source_refs: string[];
  material_refs: string[];
  fact_status: string;
}

export interface BlueprintProjection {
  status: string;
  title: string;
  audience: string;
  goal: string;
  context: string;
  narrative_thesis: string;
  chapters: Array<{ title: string; slide_ids: string[] }>;
  slides: BlueprintSlide[];
  slide_count: number;
  source_coverage: { available: number; referenced: number; unreferenced: number };
  active_task: AgentTaskSummary | null;
}

export interface VisualDirection {
  id: string;
  name: string;
  thesis: string;
  composition: string;
  density: string;
  image_language: string;
  risk: string;
  sample_asset_ref: string;
  sample_exists: boolean;
}

export interface EngineeringSample {
  sample_id: string;
  slide_refs: string[];
  render_ref: string;
  render_exists: boolean;
  native_element_ratio: number;
  editable: boolean;
  notes: string;
}

export interface VisualProjection {
  status: string;
  visual_brief: {
    design_challenge: string;
    audience: string;
    desired_response: string;
    design_posture: string;
    constraints: string[];
    visual_prohibitions: string[];
  };
  directions: VisualDirection[];
  direction_count: number;
  recommended_direction: string;
  selected_direction: string;
  engineering_samples: EngineeringSample[];
  engineering_summary: string;
  native_coverage: Record<string, boolean>;
  engineering_qa_status: string;
  visual_contract: {
    design_thesis: string;
    palette: Record<string, string>;
    typography: Record<string, string>;
    layout_rules: string[];
    image_language: string[];
    editability_rules: string[];
    page_families: string[];
  };
  scene_graph_coverage: number;
  active_task: AgentTaskSummary | null;
}

export interface DeliveryProjection {
  status: string;
  gate_state: {
    current_gate: string;
    gates: Record<string, string>;
  };
  pptx_ref: string;
  pptx_exists: boolean;
  slide_count: number;
  renders: Array<{ asset_ref: string; exists: boolean }>;
  render_count: number;
  qa_status: string;
  editable: boolean;
  whole_slide_bitmap: boolean;
  validation_ref: string;
  qa_checks: Record<string, unknown>;
  qa_notes: string[];
  qa_issues: string[];
  source_count: number;
  active_task: AgentTaskSummary | null;
}

export interface SpaceProjections {
  materials: MaterialsProjection;
  blueprint: BlueprintProjection;
  visual: VisualProjection;
  delivery: DeliveryProjection;
}

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
  space_projections?: SpaceProjections;
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
  callTool<T = DecisionResult>(name: string, args: Record<string, unknown>): Promise<T>;
  updateModelContext(context: Record<string, unknown>): Promise<void>;
  sendFollowUp(message: string): Promise<void>;
  requestDisplayMode(mode: "inline" | "fullscreen"): Promise<void>;
  notifySize(): void;
}

declare global {
  interface Window {
    __AI_PPT_PREVIEW__?: WidgetData;
    __AI_PPT_PREVIEW_ASSETS__?: Record<string, {
      assetRef: string;
      mimeType: string;
      bytes: number;
      dataBase64: string;
    }>;
    openai?: Record<string, unknown>;
  }
}
