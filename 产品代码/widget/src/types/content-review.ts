export type ContentDecisionChoice = "approved" | "modify" | "evidence" | "merge-or-delete";

export interface ContentPageDecision {
  page_decision_id: string;
  project_id: string;
  review_session_id: string;
  source_version: string;
  reading_blueprint_ref: string;
  slide_id: string;
  slide_order: number;
  slide_title_snapshot: string;
  decision: ContentDecisionChoice;
  comment: string;
  status: "completed";
  saved_at: string;
  supersedes_decision_ref: string;
}

export interface ContentMaterialView {
  readonly material_view_id: string;
  readonly asset_ref: string;
}

export interface ContentReviewSlide {
  slide_id: string;
  order: number;
  section_id: string;
  page_task: string;
  reading_question: string;
  neutral_title: string;
  customerJudgment: string;
  visible_copy_blocks: Array<{ block_id: string; text: string }>;
  readonly material_views: readonly ContentMaterialView[];
}

export interface LegacyContentMaterialView extends ContentMaterialView {
  readonly source_ref: string;
  readonly source_file_name: string;
  readonly page_number: number;
  readonly region_label: string;
  readonly purpose: string;
  readonly treatment: string;
  readonly evidence_identity: string;
}

export interface LegacyContentReviewSlide extends Omit<
  ContentReviewSlide,
  "visible_copy_blocks" | "material_views"
> {
  visible_copy_blocks: Array<{ block_id: string; text: string; identity: string }>;
  identity_labels: string[];
  evidence_bindings: Array<Record<string, unknown>>;
  readonly material_views: readonly LegacyContentMaterialView[];
  analysis_or_proposal_blocks: Array<{ block_id: string; text: string; identity: string }>;
  solution_mapping_refs: string[];
  previous_relation: string;
  next_relation: string;
  speaker_notes: string;
  reading_quality: {
    independently_readable: boolean;
    information_density: string;
    review_note: string;
  };
  material_mode: "material-backed" | "mixed-evidence" | "proposal-led";
}

export interface ContentReviewProjection {
  project_id: string;
  review_type: "content-full-deck";
  review_session_id: string;
  review_session: Record<string, unknown>;
  source_version: string;
  revision: number;
  authoritative_revision: number;
  reading_blueprint_ref: string;
  material_mode: "material-backed" | "mixed-evidence" | "proposal-led";
  section_flow: string[];
  slides: ContentReviewSlide[];
  decisions: ContentPageDecision[];
  progress: { completed: number; total: number; remaining: number; unsaved: number };
  batch: null | Record<string, unknown>;
  revision_plan: null | Record<string, unknown>;
  content_acceptance_ref: string;
}

export interface ContentReviewSurfaceData {
  surface: "review";
  selectedProjectRoot: string;
  snapshotRevision: number;
  review: ContentReviewProjection;
}

export type LegacyContentReviewProjection = Omit<ContentReviewProjection, "slides"> & {
  slides: LegacyContentReviewSlide[];
};

export type LegacyContentReviewSurfaceData = Omit<ContentReviewSurfaceData, "review"> & {
  review: LegacyContentReviewProjection;
};
