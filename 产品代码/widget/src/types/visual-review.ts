export interface NormalizedRegion {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface AnchorRenderAsset {
  readonly slide_id: string;
  readonly current_asset_ref: string;
  readonly previous_asset_ref: string;
}

export interface AnchorIdentity {
  readonly slide_ids: ReadonlyArray<string>;
  readonly selection_reason: string;
  readonly native_first_frozen: true;
  readonly visual_contract_set_ref?: string;
  readonly native_first_pptx_ref?: string;
  readonly pptx_sha256?: string;
  readonly editability_evidence_refs?: ReadonlyArray<string>;
  readonly preflight_render_refs?: ReadonlyArray<string>;
  readonly render_assets?: ReadonlyArray<AnchorRenderAsset>;
}

export interface AnchorRegionFeedback {
  feedback_id: string;
  anchor_slide_id: string;
  anchor_artifact_ref: string;
  normalized_region: NormalizedRegion;
  comment: string;
  order: number;
  visual_source_version: string;
  revision: number;
  created_at: string;
  created_by: string;
}

export interface AnchorFeedbackBatch {
  batch_id: string;
  project_id: string;
  review_session_id: string;
  visual_contract_ref: string;
  deck_design_system_ref: string;
  anchor_slide_set_ref: string;
  items: AnchorRegionFeedback[];
  source_version: string;
  revision: number;
  persistence_status: "saved";
  host_notification_status: "not-requested" | "pending" | "sent" | "failed" | "unavailable";
  ai_receipt_status: "pending" | "received" | "rejected" | "unverified";
  immutable_after_submit: true;
  submitted_at: string;
  submitted_by: string;
}

export interface VisualContractReviewMark {
  mark_id: string;
  target_type: "contract-field" | "text-range";
  slide_id: string;
  deck_section_id: string;
  target_key: string;
  selected_text: string;
  context_before: string;
  context_after: string;
  comment: string;
  visual_contract_ref: string;
  source_version: string;
  revision: number;
  created_at: string;
  created_by: string;
}

export interface VisualContractReviewMarkSet {
  mark_set_id: string;
  project_id: string;
  review_session_id: string;
  visual_contract_ref: string;
  source_version: string;
  revision: number;
  marks: VisualContractReviewMark[];
  persistence_status: "saved";
  host_notification_status: "not-requested" | "pending" | "sent" | "failed" | "unavailable";
  ai_receipt_status: "pending" | "received" | "rejected" | "unverified";
  saved_at: string;
}

export interface VisualReviewProjection {
  project_id: string;
  project_name: string;
  review_type: "visual-professional";
  review_session_id: string;
  review_session: Record<string, unknown>;
  source_version: string;
  revision: number;
  authoritative_revision: number;
  visual_contract_ref: string;
  deck_design_system_ref: string;
  deck_design_system: Record<string, unknown>;
  anchor_slide_set_ref: string;
  readonly anchors: ReadonlyArray<AnchorRenderAsset>;
  readonly anchor_identity: AnchorIdentity;
  slide_visual_contracts: Array<Record<string, unknown> & { slide_id: string }>;
  anchor_feedback_batch_ref: string | null;
  anchor_feedback_batch: AnchorFeedbackBatch | null;
  contract_review_marks_ref: string | null;
  contract_review_marks: VisualContractReviewMarkSet | null;
  gate_status?: Record<"G1" | "G2" | "G3", string>;
  host_submission_capability: "available" | "unavailable" | "unknown";
  ai_receipt_capability: "available" | "unavailable" | "unknown";
}

export interface VisualReviewSurfaceData {
  surface: "review";
  selectedProjectRoot: string;
  snapshotRevision: number;
  review: VisualReviewProjection;
}
