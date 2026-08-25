export type ContentPageDecision =
  | "approved"
  | "modify"
  | "evidence"
  | "merge-or-delete";

export type ContentDecisionSaveStatus =
  | "idle"
  | "pending"
  | "saved"
  | "failed"
  | "conflict";

export interface ContentDecisionState {
  selected: ContentPageDecision | "";
  comment: string;
  completed: boolean;
  saved: boolean;
  frozen: boolean;
}

export interface ContentVisibleCopyBlock {
  block_id: string;
  role: string;
  text: string;
}

export interface ContentEvidenceBinding {
  binding_id: string;
  identity: string;
  source_refs: string[];
  supports_block_refs: string[];
  material_ref?: string;
  asset_ref?: string;
  caption?: string;
  material_kind?: "image" | "document" | "text" | "link";
}

export interface ContentAnalysisOrProposalBlock {
  block_id: string;
  identity: string;
  text: string;
}

export interface ContentReviewSlide {
  slide_id: string;
  order: number;
  neutral_title: string;
  page_task: string;
  reading_question: string;
  visible_copy_blocks: ContentVisibleCopyBlock[];
  identity_labels: string[];
  evidence_bindings: ContentEvidenceBinding[];
  analysis_or_proposal_blocks: ContentAnalysisOrProposalBlock[];
  solution_mapping_refs: string[];
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
  counts: {
    approved: number;
    modify: number;
    evidence: number;
    merge_or_delete: number;
  };
}

export interface ContentReviewSession {
  review_session_id: string;
  review_type: "content-full-deck";
  project_id: string;
  target_artifact_ref: string;
  source_version: string;
  revision: number;
  status: "preparing" | "ready" | "opened" | "submitted" | "superseded" | "expired";
  open_policy: "foreground-if-waiting" | "notify-only";
  host_open_status: "not-requested" | "pending" | "opened" | "failed" | "unavailable";
  persistence_status: "saving" | "saved" | "failed";
  host_notification_status: "not-requested" | "pending" | "sent" | "failed" | "unavailable";
  ai_receipt_status: "pending" | "received" | "rejected" | "unverified";
  created_at: string;
  last_opened_at: string | null;
  submitted_at: string | null;
}

export interface ContentFullDeckReviewProjection {
  surface: "content-full-deck";
  project_id: string;
  revision: number;
  source_version: string;
  review_session: ContentReviewSession;
  gate_status: "content-review-ready";
  review_progress: ContentReviewProgress;
  slides: ContentReviewSlide[];
}

export function contentReviewBatchId(reviewSessionId: string): string {
  return `content-review-batch:${reviewSessionId}`;
}

export function nextIncompleteSlideId(
  projection: ContentFullDeckReviewProjection,
): string {
  return projection.slides.find((slide) => !slide.decision_state.completed)?.slide_id || "";
}
