import type {
  AnchorFeedbackBatch,
  AnchorRenderAsset,
  VisualContractReviewMarkSet,
  VisualReviewSurfaceData,
} from "../types/visual-review";

export interface VisualReviewPageDeckDesignSystem {
  theme_proposition: unknown;
  composition_grammar: unknown;
  color_tokens: unknown;
  typography_tokens: unknown;
  page_families: unknown;
  density_rhythm: unknown;
  imagery_strategy: unknown;
  diagram_strategy: unknown;
  table_strategy: unknown;
  editability_rules: unknown;
  accessibility_rules: unknown;
  forbidden_patterns: unknown;
  anchor_specification: unknown;
  production_route: unknown;
  fallback_fonts: unknown;
}

export interface VisualReviewPageAnchorIdentity {
  slide_ids: string[];
  selection_reason: string;
  native_first_frozen: true;
}

export interface VisualReviewPageSlideContract {
  slide_id: string;
  order: unknown;
  neutral_title: string;
  page_family: unknown;
  anchor_title: string;
  validation_purpose: string;
  core_claim: unknown;
  visible_copy: unknown;
  speaker_notes: unknown;
  source_refs: unknown;
  communication_goal: unknown;
  composition_intent: unknown;
  information_hierarchy: unknown;
  reading_order: unknown;
  regions: unknown;
  object_relationships: unknown;
  diagram_chart_table_treatment: unknown;
  image_selection_and_crop: unknown;
  color_application: unknown;
  typography_application: unknown;
  native_bitmap_routing: unknown;
  editability_requirements: unknown;
  fallbacks: unknown;
  acceptance_criteria: unknown;
}

export interface VisualReviewPageViewModel {
  surface: "review";
  selectedProjectRoot: string;
  snapshotRevision: number;
  review: {
    project_id: string;
    project_name: string;
    review_type: "visual-professional";
    review_session_id: string;
    source_version: string;
    revision: number;
    authoritative_revision: number;
    visual_contract_ref: string;
    deck_design_system_ref: string;
    deck_design_system: VisualReviewPageDeckDesignSystem;
    anchor_slide_set_ref: string;
    anchors: AnchorRenderAsset[];
    anchor_identity: VisualReviewPageAnchorIdentity;
    slide_visual_contracts: VisualReviewPageSlideContract[];
    anchor_feedback_batch_ref: string | null;
    anchor_feedback_batch: AnchorFeedbackBatch | null;
    contract_review_marks_ref: string | null;
    contract_review_marks: VisualContractReviewMarkSet | null;
    host_submission_capability: "available" | "unavailable" | "unknown";
    ai_receipt_capability: "available" | "unavailable" | "unknown";
  };
}

const DESIGN_SYSTEM_FIELDS = [
  "theme_proposition",
  "composition_grammar",
  "color_tokens",
  "typography_tokens",
  "page_families",
  "density_rhythm",
  "imagery_strategy",
  "diagram_strategy",
  "table_strategy",
  "editability_rules",
  "accessibility_rules",
  "forbidden_patterns",
  "anchor_specification",
  "production_route",
  "fallback_fonts",
] as const;

const SLIDE_FIELDS = [
  "core_claim",
  "speaker_notes",
  "communication_goal",
  "composition_intent",
  "information_hierarchy",
  "reading_order",
  "regions",
  "object_relationships",
  "diagram_chart_table_treatment",
  "image_selection_and_crop",
  "color_application",
  "typography_application",
  "native_bitmap_routing",
  "editability_requirements",
  "fallbacks",
  "acceptance_criteria",
] as const;

function clone<T>(value: T): T {
  return value === undefined ? value : structuredClone(value);
}

function firstText(...values: unknown[]): string {
  const value = values.find((candidate) => typeof candidate === "string" && Boolean(candidate.trim()));
  return typeof value === "string" ? value : "";
}

function visibleCopy(slide: Record<string, unknown>): unknown {
  if (Object.prototype.hasOwnProperty.call(slide, "visible_copy")) return clone(slide.visible_copy);
  if (Object.prototype.hasOwnProperty.call(slide, "visible_copy_blocks")) {
    if (!Array.isArray(slide.visible_copy_blocks)) return [];
    const blocks = slide.visible_copy_blocks.flatMap((block) => {
      if (!block || typeof block !== "object" || Array.isArray(block)) return [];
      const text = (block as Record<string, unknown>).text;
      return typeof text === "string" && text.trim() ? [text] : [];
    });
    return blocks;
  }
  return clone(slide.frozen_copy);
}

function sourceRefs(slide: Record<string, unknown>): unknown {
  if (slide.source_refs !== undefined && slide.source_refs !== null) return clone(slide.source_refs);
  if (!Array.isArray(slide.evidence_bindings)) return [];
  const references = slide.evidence_bindings.flatMap((binding) => {
    if (!binding || typeof binding !== "object" || Array.isArray(binding)) return [];
    const record = binding as Record<string, unknown>;
    if (Array.isArray(record.source_refs)) {
      return record.source_refs.filter((reference): reference is string => (
        typeof reference === "string" && Boolean(reference.trim())
      ));
    }
    return typeof record.source_ref === "string" && record.source_ref.trim()
      ? [record.source_ref]
      : [];
  });
  return [...new Set(references)];
}

function projectDeckDesignSystem(source: Record<string, unknown>): VisualReviewPageDeckDesignSystem {
  return Object.fromEntries(
    DESIGN_SYSTEM_FIELDS.map((field) => [field, clone(source[field])]),
  ) as unknown as VisualReviewPageDeckDesignSystem;
}

function projectSlide(source: Record<string, unknown> & { slide_id: string }): VisualReviewPageSlideContract {
  return {
    slide_id: source.slide_id,
    order: clone(source.order),
    neutral_title: firstText(source.neutral_title, source.title, source.page_task),
    page_family: clone(source.page_family),
    anchor_title: firstText(source.anchor_title, source.neutral_title, source.title),
    validation_purpose: firstText(
      source.validation_purpose,
      source.anchor_validation_purpose,
      source.page_task,
    ),
    ...Object.fromEntries(SLIDE_FIELDS.map((field) => [field, clone(source[field])])),
    visible_copy: visibleCopy(source),
    source_refs: sourceRefs(source),
  } as VisualReviewPageSlideContract;
}

export function toVisualReviewPageViewModel(
  data: VisualReviewSurfaceData,
): VisualReviewPageViewModel {
  const { review } = data;
  return {
    surface: "review",
    selectedProjectRoot: data.selectedProjectRoot,
    snapshotRevision: data.snapshotRevision,
    review: {
      project_id: review.project_id,
      project_name: review.project_name,
      review_type: "visual-professional",
      review_session_id: review.review_session_id,
      source_version: review.source_version,
      revision: review.revision,
      authoritative_revision: review.authoritative_revision,
      visual_contract_ref: review.visual_contract_ref,
      deck_design_system_ref: review.deck_design_system_ref,
      deck_design_system: projectDeckDesignSystem(review.deck_design_system),
      anchor_slide_set_ref: review.anchor_slide_set_ref,
      anchors: review.anchors.map((anchor) => ({ ...anchor })),
      anchor_identity: {
        slide_ids: [...review.anchor_identity.slide_ids],
        selection_reason: review.anchor_identity.selection_reason,
        native_first_frozen: true,
      },
      slide_visual_contracts: review.slide_visual_contracts.map(projectSlide),
      anchor_feedback_batch_ref: review.anchor_feedback_batch_ref,
      anchor_feedback_batch: clone(review.anchor_feedback_batch),
      contract_review_marks_ref: review.contract_review_marks_ref,
      contract_review_marks: clone(review.contract_review_marks),
      host_submission_capability: review.host_submission_capability,
      ai_receipt_capability: review.ai_receipt_capability,
    },
  };
}
