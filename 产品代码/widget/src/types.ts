export type SpaceId = "overview" | "materials" | "blueprint" | "visual" | "delivery";

export type GateStatus = "locked" | "open" | "user-reviewable" | "passed" | "failed";
export type WorkspaceStatus = GateStatus | "ready" | "needs-input" | "pending";

export type WorkspaceActionKind =
  | "continue-chat"
  | "confirm-mission"
  | "open-content-review"
  | "open-visual-review"
  | "none";

export interface WorkspacePrimaryAction {
  kind: WorkspaceActionKind;
  label: string;
  enabled: boolean;
}

export interface CognitionSpaceProjection {
  status: WorkspaceStatus;
  conclusion: string;
  focus: string;
  risk: string;
  affected_artifacts: string[];
  high_impact_count: number;
  primary_action: WorkspacePrimaryAction;
}

export interface OverviewWorkspaceProjection extends CognitionSpaceProjection {
  delivery_goal: string;
  audiences: string[];
  topic: string;
  mission_status?: "draft" | "confirmable" | "reopened" | "superseded";
  mission_draft_ref?: string;
  mission_confirmation_ref?: string;
  material_mode?: "materials-provided" | "no-materials-confirmed" | "unconfirmed";
  content_identity_mode?: "material-backed" | "proposal-only" | "blocked";
  mission_card?: {
    topic: string;
    primary_audience: string;
    desired_judgment_or_action: string;
    material_state: "materials-provided" | "no-materials";
    material_inventory_ref: string;
    materials: string[];
    background: string[];
    constraints: string[];
    red_lines: string[];
    unknowns: string[];
  };
}

export interface MaterialsWorkspaceProjection extends CognitionSpaceProjection {
  source_count: number;
  parsed_count: number;
  failed_count: number;
  authorization_count: number;
  external_search: boolean;
}

export interface BlueprintWorkspaceProjection extends CognitionSpaceProjection {
  phase: GateStatus;
  internal_status: DeliveryStatusProjection;
  slide_count: number;
  saved_mark_count: number;
  review_available: boolean;
  source_version: string;
}

export interface VisualWorkspaceProjection extends CognitionSpaceProjection {
  g1_status: GateStatus;
  g2_status: GateStatus;
  g3_status: GateStatus;
  saved_mark_count: number;
  review_available: boolean;
  source_version: string;
  production_route: string;
}

export type DeliveryStatusProjection = "passed" | "failed" | "pending" | "locked";

export type DeliveryTargetId =
  | "macos-powerpoint"
  | "macos-wps"
  | "windows-powerpoint"
  | "windows-wps";

export interface TargetStatusProjection {
  target_id: DeliveryTargetId;
  status: DeliveryStatusProjection;
  pptx_sha256: string;
  [key: string]: unknown;
}

export interface DeliveryWorkspaceProjection extends CognitionSpaceProjection {
  phase: GateStatus;
  slides: { completed: number; total: number };
  quality_gates: {
    semantic: DeliveryStatusProjection;
    aesthetic: DeliveryStatusProjection;
    engineering: DeliveryStatusProjection;
    target_render: DeliveryStatusProjection;
  };
  highest_blocker: string | null;
  targets: TargetStatusProjection[];
  hash_identity: string;
  chat_send: {
    status: "pending" | "sent" | "failed";
    message_ref?: string;
    sent_at?: string;
  };
}

export interface WorkspaceProjection {
  active_space: SpaceId;
  navigation: Array<{
    space_id: SpaceId;
    label: string;
    status: WorkspaceStatus;
    high_impact_count: number;
  }>;
  overview: OverviewWorkspaceProjection;
  materials: MaterialsWorkspaceProjection;
  blueprint: BlueprintWorkspaceProjection;
  visual: VisualWorkspaceProjection;
  delivery: DeliveryWorkspaceProjection;
}

export interface ProjectSnapshot {
  schema_version: "3.0";
  revision: number;
  project: {
    project_id: string;
    name: string;
    project_root: string;
  };
  gate_state: {
    current_gate: string;
    gates: Record<string, GateStatus>;
  };
  artifacts: Record<string, string>;
  missionDraftRef?: string;
  missionConfirmationRef?: string;
  materialMode?: "materials-provided" | "no-materials-confirmed" | "unconfirmed";
  contentIdentityMode?: "material-backed" | "proposal-only" | "blocked";
  workspace: WorkspaceProjection;
  experience: Record<string, unknown>;
  allowed_next_actions: string[];
}

export interface WidgetData {
  surface?: "workbench";
  snapshot: ProjectSnapshot;
  selectedProjectRoot?: string;
  initialSpace?: SpaceId;
  previewEvidence?: PreviewEvidence;
}

export interface PreviewEvidence {
  evidenceScope: "local-development-preview";
  proofEligible: false;
  realHostEvidence: false;
}

export interface ReviewMark {
  mark_id: string;
  field_anchor: string;
  exact_text: string;
  prefix: string;
  suffix: string;
  comment: string;
}

export interface ReviewField {
  anchor: string;
  label: string;
  value: unknown;
}

export interface ReviewSection {
  anchor: string;
  title: string;
  fields: ReviewField[];
}

export interface ReviewProjection {
  review_type: "content" | "visual";
  display_policy: "professional-review";
  project_id: string;
  project_name: string;
  title: string;
  revision: number;
  status: string;
  gate_status: Partial<Record<"G0" | "G1" | "G2" | "G3" | "G4", GateStatus>>;
  source_version: string;
  source_refs: string[];
  generated_at?: string;
  sections: ReviewSection[];
  outline: Array<{ anchor: string; title: string }>;
  mark_set: {
    mark_set_id?: string;
    project_id?: string;
    review_type?: string;
    source_version?: string;
    revision?: number;
    status?: string;
    saved_at?: string;
    marks: ReviewMark[];
  };
}

export interface ReviewWidgetData {
  surface: "review";
  selectedProjectRoot: string;
  snapshotRevision: number;
  previewEvidence?: PreviewEvidence;
  review: ReviewProjection;
}

export type SurfaceData = WidgetData | ReviewWidgetData;

export interface HostEnvironment {
  containerWidth: number | null;
  canSendMessage: boolean;
  canUpdateModelContext: boolean;
}

export interface DecisionResult {
  decision: Record<string, unknown>;
  snapshot: ProjectSnapshot;
  follow_up_message: string;
  model_context: Record<string, unknown>;
  affected_artifacts: string[];
}

export interface MissionConfirmationRequest {
  projectRoot: string;
  expectedRevision: number;
  missionDraftRef: string;
  materialMode: "materials-provided" | "no-materials-confirmed";
  materialInventoryRef: string;
}

export interface MissionConfirmationResult {
  artifact_ref: string;
  snapshot: ProjectSnapshot;
}

export interface HostBridge {
  connect(onData?: (data: SurfaceData) => void): Promise<void>;
  callTool<T = DecisionResult>(name: string, args: Record<string, unknown>): Promise<T>;
  switchReview?(reviewType: "content" | "visual"): Promise<void>;
  updateModelContext(context: Record<string, unknown>): Promise<void>;
  sendFollowUp(message: string): Promise<void>;
  confirmMission(args: MissionConfirmationRequest): Promise<MissionConfirmationResult>;
  getHostEnvironment(): HostEnvironment | undefined;
  notifySize(): void;
}

declare global {
  interface Window {
    __AI_PPT_PREVIEW__?: SurfaceData;
    __AI_PPT_PREVIEW_ASSETS__?: Record<string, {
      assetRef: string;
      mimeType: string;
      bytes: number;
      dataBase64: string;
    }>;
    openai?: Record<string, unknown>;
    __AI_PPT_SIDEBAR_HOST__?: {
      connect(onData?: (data: SurfaceData) => void): Promise<void>;
      callTool<T>(name: string, args: Record<string, unknown>): Promise<T>;
      updateModelContext?(context: Record<string, unknown>): Promise<void>;
      sendFollowUp?(message: string): Promise<void>;
      confirmMission?<T = MissionConfirmationResult>(
        args: MissionConfirmationRequest,
      ): Promise<T>;
      getHostEnvironment?(): HostEnvironment | undefined;
      notifySize?(): void;
    };
  }
}
