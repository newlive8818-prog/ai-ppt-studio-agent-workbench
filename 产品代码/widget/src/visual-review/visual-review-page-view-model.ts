import type {
  AnchorFeedbackBatch,
  AnchorRenderAsset,
  VisualContractReviewMarkSet,
  VisualReviewAcceptanceCriterion,
  VisualReviewAnchorSpecification,
  VisualReviewAssetRole,
  VisualReviewDeckDesignSystem,
  VisualReviewPowerpointImplementationRequirements,
  VisualReviewRegion,
  VisualReviewSlideVisualContract,
  VisualReviewSurfaceData,
  VisualReviewTextDensityBudget,
  VisualReviewTokenMap,
  VisualReviewVisualBrief,
} from "../types/visual-review";
import { VISUAL_BRIEF_FIELD_ORDER } from "./visual-contract-field-contract";
import { isReviewableVisualMapKey } from "./visual-map-key-policy";

export type VisualReviewPageVisualBrief = VisualReviewVisualBrief;

export type VisualReviewPageDeckDesignSystem = VisualReviewDeckDesignSystem;

export interface VisualReviewPageAnchorIdentity {
  slide_ids: string[];
  selection_reason: string;
  native_first_frozen: true;
}

export type VisualReviewPageSlideContract = VisualReviewSlideVisualContract;

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
    visual_brief_ref: string;
    visual_brief: VisualReviewPageVisualBrief;
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

const VISUAL_BRIEF_FIELDS = [
  "design_proposition",
  ...VISUAL_BRIEF_FIELD_ORDER,
] as const;

const DESIGN_SYSTEM_FIELDS = [
  "theme_proposition",
  "composition_grammar",
  "color_tokens",
  "typography_tokens",
  "page_families",
  "density_rhythm",
  "cross_slide_rhythm_rules",
  "emphasis_budget",
  "imagery_strategy",
  "image_language",
  "diagram_strategy",
  "diagram_language",
  "table_strategy",
  "editability_rules",
  "accessibility_rules",
  "forbidden_patterns",
  "five_second_test_rules",
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
  "reader_judgment",
  "primary_relationship",
  "secondary_relationship",
  "visual_mechanism",
  "focal_point",
  "asset_roles",
  "forbidden_patterns",
  "previous_rhythm_relation",
  "next_rhythm_relation",
  "text_density_budget",
  "powerpoint_implementation_requirements",
  "acceptance_evidence_plan",
] as const;

function clone<T>(value: T): T {
  return value === undefined ? value : structuredClone(value);
}

function projectTextMap(value: unknown): VisualReviewTokenMap {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const projected: Record<string, string> = {};
  for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
    const normalizedKey = key.trim();
    if (
      isReviewableVisualMapKey(normalizedKey)
      && typeof item === "string"
      && !Object.hasOwn(projected, normalizedKey)
    ) projected[normalizedKey] = item.trim();
  }
  return projected;
}

function projectAnchorSpecification(value: unknown): string | VisualReviewAnchorSpecification {
  if (!value || typeof value !== "object" || Array.isArray(value)) return clone(value) as string;
  const source = value as Record<string, unknown>;
  return {
    slide_ids: Array.isArray(source.slide_ids)
      ? source.slide_ids.filter((item): item is string => typeof item === "string")
      : [],
    selection_reason: typeof source.selection_reason === "string" ? source.selection_reason : "",
    native_first_frozen: true,
  };
}

function projectRegions(value: unknown): ReadonlyArray<string | VisualReviewRegion> {
  if (!Array.isArray(value)) return [];
  const projected: Array<string | VisualReviewRegion> = [];
  for (const region of value) {
    if (typeof region === "string") {
      projected.push(region);
      continue;
    }
    if (!region || typeof region !== "object" || Array.isArray(region)) continue;
    const source = region as Record<string, unknown>;
    if (typeof source.region_id !== "string" || (source.purpose !== null && typeof source.purpose !== "string")) continue;
    projected.push({ region_id: source.region_id, purpose: source.purpose as string | null });
  }
  return projected;
}

function projectAcceptanceCriteria(value: unknown): ReadonlyArray<VisualReviewAcceptanceCriterion> {
  if (!Array.isArray(value)) return [];
  return value.flatMap((criterion) => {
    if (!criterion || typeof criterion !== "object" || Array.isArray(criterion)) return [];
    const source = criterion as Record<string, unknown>;
    if (
      typeof source.criterion_id !== "string"
      || typeof source.level !== "string"
      || typeof source.expected_outcome !== "string"
    ) return [];
    return [{
      criterion_id: source.criterion_id,
      level: source.level as VisualReviewAcceptanceCriterion["level"],
      expected_outcome: source.expected_outcome,
    }];
  });
}

function projectAssetRoles(value: unknown): ReadonlyArray<VisualReviewAssetRole> {
  if (!Array.isArray(value)) return [];
  return value.flatMap((asset) => {
    if (!asset || typeof asset !== "object" || Array.isArray(asset)) return [];
    const source = asset as Record<string, unknown>;
    return [{
      asset_id: String(source.asset_id ?? ""),
      role: source.role as VisualReviewAssetRole["role"],
      source_ref: String(source.source_ref ?? ""),
      narrative_task: String(source.narrative_task ?? ""),
      replaceable: source.replaceable === true,
    }];
  });
}

function projectTextDensityBudget(value: unknown): VisualReviewTextDensityBudget {
  const source = value as Record<string, unknown>;
  return {
    max_body_lines: Number(source.max_body_lines),
    max_text_blocks: Number(source.max_text_blocks),
    reduction_strategy: String(source.reduction_strategy ?? ""),
  };
}

function projectPowerpointRequirements(value: unknown): VisualReviewPowerpointImplementationRequirements {
  const source = value as Record<string, unknown>;
  const layout = source.layout_constraints as Record<string, unknown>;
  return {
    object_plan: Array.isArray(source.object_plan) ? source.object_plan.map((item) => {
      const row = item as Record<string, unknown>;
      return {
        role: String(row.role ?? ""),
        object_type: String(row.object_type ?? ""),
        layer: String(row.layer ?? ""),
        editability: String(row.editability ?? ""),
      };
    }) : [],
    connector_semantics: Array.isArray(source.connector_semantics)
      ? source.connector_semantics.map((item) => {
        const row = item as Record<string, unknown>;
        return {
          from_role: String(row.from_role ?? ""),
          to_role: String(row.to_role ?? ""),
          meaning: String(row.meaning ?? ""),
          direction: String(row.direction ?? ""),
          crossing_forbidden: row.crossing_forbidden === true,
        };
      })
      : [],
    layout_constraints: {
      entry_region: String(layout.entry_region ?? ""),
      focal_region: String(layout.focal_region ?? ""),
      minimum_clear_space: String(layout.minimum_clear_space ?? ""),
    },
    native_bitmap_routing: String(source.native_bitmap_routing ?? ""),
    degradation_strategy: String(source.degradation_strategy ?? ""),
  };
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

function projectVisualBrief(source: Record<string, unknown>): VisualReviewPageVisualBrief {
  const projected = Object.fromEntries(
    VISUAL_BRIEF_FIELDS.map((field) => [
      field,
      field === "design_philosophy_refs" && source[field] === undefined
        ? []
        : clone(source[field]),
    ]),
  ) as unknown as VisualReviewPageVisualBrief;
  const fiveSecond = source.five_second_test_contract as Record<string, unknown>;
  return {
    ...projected,
    five_second_test_contract: {
      prompt: String(fiveSecond.prompt ?? ""),
      expected_judgment: String(fiveSecond.expected_judgment ?? ""),
      record_fields: Array.isArray(fiveSecond.record_fields)
        ? fiveSecond.record_fields.filter((item): item is string => typeof item === "string")
        : [],
    },
  };
}

function projectDeckDesignSystem(source: Record<string, unknown>): VisualReviewPageDeckDesignSystem {
  const projected = Object.fromEntries(
    DESIGN_SYSTEM_FIELDS.map((field) => [field, clone(source[field])]),
  ) as unknown as VisualReviewPageDeckDesignSystem;
  return {
    ...projected,
    color_tokens: projectTextMap(source.color_tokens),
    typography_tokens: projectTextMap(source.typography_tokens),
    emphasis_budget: {
      max_primary_focal_points_per_slide: Number(
        (source.emphasis_budget as Record<string, unknown>).max_primary_focal_points_per_slide,
      ),
      max_accent_color_roles: Number(
        (source.emphasis_budget as Record<string, unknown>).max_accent_color_roles,
      ),
      consecutive_high_density_slide_limit: Number(
        (source.emphasis_budget as Record<string, unknown>).consecutive_high_density_slide_limit,
      ),
    },
    anchor_specification: projectAnchorSpecification(source.anchor_specification),
    ...(source.fallback_fonts === undefined
      ? {}
      : { fallback_fonts: projectTextMap(source.fallback_fonts) }),
  };
}

function projectSlide(source: Record<string, unknown> & { slide_id: string }): VisualReviewPageSlideContract {
  const slide = {
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
  const evidencePlan = source.acceptance_evidence_plan as Record<string, unknown>;
  return {
    ...slide,
    regions: projectRegions(source.regions),
    acceptance_criteria: projectAcceptanceCriteria(source.acceptance_criteria),
    asset_roles: projectAssetRoles(source.asset_roles),
    text_density_budget: projectTextDensityBudget(source.text_density_budget),
    powerpoint_implementation_requirements: projectPowerpointRequirements(
      source.powerpoint_implementation_requirements,
    ),
    acceptance_evidence_plan: {
      automated_checks: Array.isArray(evidencePlan.automated_checks)
        ? evidencePlan.automated_checks.filter((item): item is string => typeof item === "string")
        : [],
      human_review_checks: Array.isArray(evidencePlan.human_review_checks)
        ? evidencePlan.human_review_checks.filter((item): item is string => typeof item === "string")
        : [],
      target_powerpoint_checks: Array.isArray(evidencePlan.target_powerpoint_checks)
        ? evidencePlan.target_powerpoint_checks.filter((item): item is string => typeof item === "string")
        : [],
      user_review_question: String(evidencePlan.user_review_question ?? ""),
    },
  };
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
      visual_brief_ref: review.visual_brief_ref,
      visual_brief: projectVisualBrief(
        review.visual_brief as unknown as Record<string, unknown>,
      ),
      deck_design_system_ref: review.deck_design_system_ref,
      deck_design_system: projectDeckDesignSystem(
        review.deck_design_system as unknown as Record<string, unknown>,
      ),
      anchor_slide_set_ref: review.anchor_slide_set_ref,
      anchors: review.anchors.map((anchor) => ({ ...anchor })),
      anchor_identity: {
        slide_ids: [...review.anchor_identity.slide_ids],
        selection_reason: review.anchor_identity.selection_reason,
        native_first_frozen: true,
      },
      slide_visual_contracts: review.slide_visual_contracts.map((slide) => (
        projectSlide(slide as unknown as Record<string, unknown> & { slide_id: string })
      )),
      anchor_feedback_batch_ref: review.anchor_feedback_batch_ref,
      anchor_feedback_batch: clone(review.anchor_feedback_batch),
      contract_review_marks_ref: review.contract_review_marks_ref,
      contract_review_marks: clone(review.contract_review_marks),
      host_submission_capability: review.host_submission_capability,
      ai_receipt_capability: review.ai_receipt_capability,
    },
  };
}
