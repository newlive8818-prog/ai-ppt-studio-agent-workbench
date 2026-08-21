export type SpaceId = "overview" | "materials" | "blueprint" | "visual" | "delivery";

export type GateStatus = "locked" | "open" | "user-reviewable" | "passed" | "failed";
export type WorkspaceStatus = GateStatus | "ready" | "needs-input" | "pending";

export type WorkspaceActionKind =
  | "continue-chat"
  | "confirm-mission"
  | "review-complete-deck"
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
  phase: ContentWorkflowPhase;
  internal_status: DeliveryStatusProjection;
  slide_count: number;
  completed_page_count: number;
  remaining_page_count: number;
  current_batch_status: string;
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

export type DeliveryStatusProjection =
  | "passed"
  | "failed"
  | "pending"
  | "locked"
  | "stale"
  | "deferred";

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

export interface ReleaseTargetPolicyProjection {
  policy_ref: string;
  policy_id: string;
  required_target_ids: DeliveryTargetId[];
  deferred_target_ids: DeliveryTargetId[];
  compatibility_claim_scope: DeliveryTargetId[];
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
  release_target_policy: ReleaseTargetPolicyProjection;
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
  evidenceScope: "local-development-preview" | "deterministic-contract-fixture";
  proofEligible: false;
  realHostEvidence: false;
  evidenceIdentity?: "deterministic-contract-fixture-not-real-project-proof";
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
  review_type: "content" | "visual" | "content-evidence";
  display_policy: "professional-review" | "content-evidence-read-only";
  project_id: string;
  project_name: string;
  title: string;
  revision: number;
  status: string;
  release_target_policy?: ReleaseTargetPolicyProjection;
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
  capabilities?: {
    canSavePageDecision: boolean;
    canSaveReviewMarks: boolean;
    canCompareSourceAndSlide: boolean;
    canCompareAdjacentSlides: boolean;
  };
  evidence_view?: {
    slide: {
      slide_id: string;
      order: number;
      neutral_title: string;
      page_task: string;
      reading_question?: string;
      visible_copy?: Array<{ copy_id?: string; role?: string; text: string }>;
    };
    evidence: {
      evidence_id: string;
      material_ref: string;
      asset_ref: string;
      source_file: string;
      source_page_or_region: string;
      used_region: string;
      supports_claim: string;
      treatment: string;
      evidence_gap?: string;
    };
    asset: {
      assetRef: string;
      mimeType: string;
      bytes: number;
      dataBase64: string;
    } | null;
    adjacent: {
      previous: { slide_id: string; order: number; neutral_title: string; page_task: string } | null;
      next: { slide_id: string; order: number; neutral_title: string; page_task: string } | null;
    };
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

export type ContentWorkflowPhase =
  | "content-producing"
  | "content-hard-gate-review"
  | "full-deck-review-ready"
  | "review-batch-submitted"
  | "batch-plan-proposed"
  | "batch-plan-confirmed";

export type ContentMaterialMode =
  | "material-backed"
  | "mixed-evidence"
  | "proposal-led";

export type ContentPageDecision =
  | "approved"
  | "modify"
  | "evidence"
  | "merge-or-delete";

export interface ContentMissionSummary {
  topic: string;
  primary_audience: string;
  decision_question_or_next_action: string;
}

export interface ContentReviewChapter {
  section_id: string;
  title: string;
  first_slide_id: string;
}

export interface ContentVisibleCopyBlock {
  copy_id: string;
  role: string;
  text: string;
}

export interface ContentEvidenceItem {
  evidence_id: string;
  evidence_kind: string;
  fact_identity: string;
  material_ref: string;
  asset_ref: string;
  source_file: string;
  source_page_or_region: string;
  used_region: string;
  supports_claim: string;
  treatment: string;
  evidence_gap: string;
  [key: string]: unknown;
}

export interface ContentAnalysisBlock {
  identity: string;
  text: string;
  [key: string]: unknown;
}

export interface ContentDecisionState {
  selected: ContentPageDecision | "";
  comment: string;
  completed: boolean;
  saved: boolean;
  frozen: boolean;
}

export type ContentDecisionSaveStatus =
  | "idle"
  | "pending"
  | "saved"
  | "failed"
  | "conflict";

export interface ContentReviewSlide {
  slide_id: string;
  order: number;
  section_id: string;
  neutral_title: string;
  page_task: string;
  reading_question: string;
  visible_copy: ContentVisibleCopyBlock[];
  identity_labels: string[];
  evidence_items: ContentEvidenceItem[];
  analysis_or_proposal_blocks: ContentAnalysisBlock[];
  solution_mapping_refs: string[];
  source_refs: string[];
  speaker_notes: string;
  reading_quality: Record<string, unknown>;
  previous_relation: string;
  next_relation: string;
  decision_state: ContentDecisionState;
}

export interface ContentReviewProgress {
  total: number;
  completed: number;
  remaining: number;
  saved_comment_count: number;
  next_incomplete_slide_id: string;
  counts: {
    approved: number;
    modify: number;
    evidence: number;
    merge_or_delete: number;
  };
}

export interface ContentProgressProjection {
  display_policy: "content-sidebar-progress";
  phase: "content-producing" | "content-hard-gate-review";
  project_id: string;
  revision: number;
  mission_summary: ContentMissionSummary;
  next_action: "continue-content-production";
}

export interface ContentFullDeckProjection {
  display_policy: "content-sidebar-full-deck";
  phase: Exclude<ContentWorkflowPhase, "content-producing" | "content-hard-gate-review">;
  project_id: string;
  revision: number;
  mission_summary: ContentMissionSummary;
  material_mode: ContentMaterialMode;
  source_version: string;
  chapters: ContentReviewChapter[];
  slides: ContentReviewSlide[];
  review_progress: ContentReviewProgress;
  decision_set: {
    decision_set_id: string;
    review_batch_id: string;
    status: string;
  };
  current_batch: {
    batch_ref: string;
    review_batch_id: string;
    status: string;
  };
  current_plan: {
    plan_ref: string;
    confirmation_ref: string;
    status: string;
    requires_blueprint_revision: boolean;
  };
  previous_round: null | {
    source_version: string;
    review_batch_ref: string;
    revision_plan_ref: string;
    plan_confirmation_ref: string;
    result: string;
  };
  next_action: string;
}

export type ContentSidebarReviewProjection =
  | ContentProgressProjection
  | ContentFullDeckProjection;

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
    __AI_PPT_CONTENT_REVIEW_PREVIEW__?: ContentSidebarReviewProjection;
    __AI_PPT_CONTENT_REVIEW_SCENARIO__?: string;
    __AI_PPT_PREVIEW_CALLS__?: Record<string, number>;
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
