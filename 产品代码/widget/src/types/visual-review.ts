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
  anchor_representation_version?: "browser-v1" | "browser-v2";
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

export interface VisualReviewVisualBrief {
  readonly design_proposition: string;
  readonly audience_fit: string;
  readonly decision_task: string;
  readonly design_stance: string;
  readonly emotional_boundary: string;
  readonly brand_boundary: string;
  readonly density_strategy: string;
  readonly narrative_rhythm: string;
  readonly imagery_strategy: string;
  readonly diagram_strategy: string;
  readonly powerpoint_constraints: string;
  readonly forbidden_patterns: ReadonlyArray<string>;
  readonly five_second_test_contract: VisualReviewFiveSecondTestContract;
  readonly design_philosophy_refs: ReadonlyArray<string>;
}

export interface VisualReviewFiveSecondTestContract {
  readonly prompt: string;
  readonly expected_judgment: string;
  readonly record_fields: ReadonlyArray<string>;
}

export interface VisualReviewEmphasisBudget {
  readonly max_primary_focal_points_per_slide: number;
  readonly max_accent_color_roles: number;
  readonly consecutive_high_density_slide_limit: number;
}

export type VisualReviewTokenMap = Readonly<Record<string, string>>;

export interface VisualReviewAnchorSpecification {
  readonly slide_ids: ReadonlyArray<string>;
  readonly selection_reason: string;
  readonly native_first_frozen: true;
}

export interface VisualReviewRegion {
  readonly region_id: string;
  readonly purpose: string | null;
}

export interface VisualReviewAcceptanceCriterion {
  readonly criterion_id: string;
  readonly level: "must-follow" | "minimum-aesthetic" | "reference-implementation";
  readonly expected_outcome: string;
}

export interface VisualReviewDeckDesignSystem {
  readonly theme_proposition: string;
  readonly composition_grammar: string;
  readonly color_tokens: VisualReviewTokenMap;
  readonly typography_tokens: VisualReviewTokenMap;
  readonly page_families: ReadonlyArray<string>;
  readonly density_rhythm: ReadonlyArray<string>;
  readonly cross_slide_rhythm_rules: ReadonlyArray<string>;
  readonly emphasis_budget: VisualReviewEmphasisBudget;
  readonly imagery_strategy: string;
  readonly image_language: string;
  readonly diagram_strategy: string;
  readonly diagram_language: string;
  readonly table_strategy: string;
  readonly editability_rules: string | ReadonlyArray<string>;
  readonly accessibility_rules: string | ReadonlyArray<string> | null;
  readonly forbidden_patterns: ReadonlyArray<string>;
  readonly five_second_test_rules: ReadonlyArray<string>;
  readonly anchor_specification: string | VisualReviewAnchorSpecification;
  readonly production_route: "strict-B";
  readonly fallback_fonts?: VisualReviewTokenMap;
}

export interface VisualReviewSlideVisualContract {
  readonly slide_id: string;
  readonly order: number;
  readonly neutral_title: string;
  readonly page_family: string;
  readonly anchor_title: string;
  readonly validation_purpose: string;
  readonly core_claim: string | null;
  readonly visible_copy: ReadonlyArray<string>;
  readonly speaker_notes: string;
  readonly source_refs: ReadonlyArray<string>;
  readonly communication_goal: string | null;
  readonly composition_intent: string;
  readonly information_hierarchy: string;
  readonly reading_order: ReadonlyArray<string>;
  readonly regions: ReadonlyArray<string | VisualReviewRegion>;
  readonly object_relationships: ReadonlyArray<string>;
  readonly diagram_chart_table_treatment: string;
  readonly image_selection_and_crop: string;
  readonly color_application: string;
  readonly typography_application: string;
  readonly native_bitmap_routing: string;
  readonly editability_requirements: string;
  readonly fallbacks: ReadonlyArray<string>;
  readonly acceptance_criteria: ReadonlyArray<VisualReviewAcceptanceCriterion>;
  readonly reader_judgment: string;
  readonly primary_relationship: VisualRelationship;
  readonly secondary_relationship: VisualRelationship | null;
  readonly visual_mechanism: string;
  readonly focal_point: string;
  readonly asset_roles: ReadonlyArray<VisualReviewAssetRole>;
  readonly forbidden_patterns: ReadonlyArray<string>;
  readonly previous_rhythm_relation: string;
  readonly next_rhythm_relation: string;
  readonly text_density_budget: VisualReviewTextDensityBudget;
  readonly powerpoint_implementation_requirements: VisualReviewPowerpointImplementationRequirements;
  readonly acceptance_evidence_plan: VisualReviewAcceptanceEvidencePlan;
}

export type VisualRelationship =
  | "comparison"
  | "sequence"
  | "causality"
  | "hierarchy"
  | "network"
  | "system-boundary"
  | "cycle"
  | "tension"
  | "evidence-to-judgment"
  | "single-focus";

export interface VisualReviewAssetRole {
  readonly asset_id: string;
  readonly role: "evidence" | "structure" | "explanation" | "emotion-context";
  readonly source_ref: string;
  readonly narrative_task: string;
  readonly replaceable: boolean;
}

export interface VisualReviewTextDensityBudget {
  readonly max_body_lines: number;
  readonly max_text_blocks: number;
  readonly reduction_strategy: string;
}

export interface VisualReviewPowerpointObjectPlanItem {
  readonly role: string;
  readonly object_type: string;
  readonly layer: string;
  readonly editability: string;
}

export interface VisualReviewPowerpointConnector {
  readonly from_role: string;
  readonly to_role: string;
  readonly meaning: string;
  readonly direction: string;
  readonly crossing_forbidden: boolean;
}

export interface VisualReviewPowerpointLayoutConstraints {
  readonly entry_region: string;
  readonly focal_region: string;
  readonly minimum_clear_space: string;
}

export interface VisualReviewPowerpointImplementationRequirements {
  readonly object_plan: ReadonlyArray<VisualReviewPowerpointObjectPlanItem>;
  readonly connector_semantics: ReadonlyArray<VisualReviewPowerpointConnector>;
  readonly layout_constraints: VisualReviewPowerpointLayoutConstraints;
  readonly native_bitmap_routing: string;
  readonly degradation_strategy: string;
}

export interface VisualReviewAcceptanceEvidencePlan {
  readonly automated_checks: ReadonlyArray<string>;
  readonly human_review_checks: ReadonlyArray<string>;
  readonly target_powerpoint_checks: ReadonlyArray<string>;
  readonly user_review_question: string;
}

export interface VisualReviewProjection {
  project_id: string;
  project_name: string;
  review_type: "visual-professional";
  readonly projection_contract?: "image-led-formal-visual-review/v1";
  review_session_id: string;
  review_session: Record<string, unknown>;
  source_version: string;
  revision: number;
  authoritative_revision: number;
  visual_contract_ref: string;
  visual_brief_ref: string;
  visual_brief: VisualReviewVisualBrief;
  deck_design_system_ref: string;
  deck_design_system: VisualReviewDeckDesignSystem;
  anchor_slide_set_ref: string;
  readonly anchors: ReadonlyArray<AnchorRenderAsset>;
  readonly anchor_identity: AnchorIdentity;
  slide_visual_contracts: VisualReviewSlideVisualContract[];
  anchor_feedback_batch_ref: string | null;
  anchor_feedback_batch: AnchorFeedbackBatch | null;
  contract_review_marks_ref: string | null;
  contract_review_marks: VisualContractReviewMarkSet | null;
  host_submission_capability: "available" | "unavailable" | "unknown";
  ai_receipt_capability: "available" | "unavailable" | "unknown";
}

export interface VisualReviewSurfaceData {
  surface: "review";
  selectedProjectRoot: string;
  snapshotRevision: number;
  review: VisualReviewProjection;
}
