import type { ReviewField, ReviewProjection, ReviewWidgetData } from "../types";
import type { AnchorRenderAsset } from "../types/visual-review";
import type {
  VisualReviewPageDeckDesignSystem,
  VisualReviewPageSlideContract,
  VisualReviewPageViewModel,
} from "./visual-review-page-view-model";

function fieldMap(fields: ReviewField[]): Record<string, unknown> {
  return Object.fromEntries(fields.map((field) => [field.label, structuredClone(field.value)]));
}

function text(value: unknown, fallback = ""): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string" && Boolean(item.trim()))
    : [];
}

function objectValue(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? structuredClone(value as Record<string, unknown>)
    : {};
}

function artifactField(review: ReviewProjection, label: string, fallback: string): string {
  for (const section of review.sections) {
    const value = section.fields.find((field) => field.label === label)?.value;
    if (typeof value === "string" && value.trim()) return value;
  }
  return fallback;
}

function projectDesignSystem(review: ReviewProjection): VisualReviewPageDeckDesignSystem {
  const section = review.sections.find((item) => item.anchor === "deck-design-system");
  const source = section ? fieldMap(section.fields) : {};
  return {
    theme_proposition: source.theme_proposition,
    composition_grammar: source.composition_grammar,
    color_tokens: source.color_tokens,
    typography_tokens: source.typography_tokens,
    page_families: source.page_families,
    density_rhythm: source.density_rhythm,
    imagery_strategy: source.imagery_strategy,
    diagram_strategy: source.diagram_strategy,
    table_strategy: source.table_strategy,
    editability_rules: source.editability_rules,
    accessibility_rules: source.accessibility_rules,
    forbidden_patterns: source.forbidden_patterns,
    anchor_specification: source.anchor_specification,
    production_route: source.production_route,
    fallback_fonts: source.fallback_fonts,
  };
}

function projectSlide(section: ReviewProjection["sections"][number], index: number): VisualReviewPageSlideContract {
  const source = fieldMap(section.fields);
  const slideId = text(source.slide_id, section.anchor.replace(/^visual-slide-/, "") || `S${index + 1}`);
  const neutralTitle = text(source.neutral_title, text(source.title, section.title));
  return {
    slide_id: slideId,
    order: source.order ?? index + 1,
    neutral_title: neutralTitle,
    page_family: source.page_family,
    anchor_title: text(source.anchor_title, neutralTitle),
    validation_purpose: text(source.validation_purpose, text(source.anchor_validation_purpose, text(source.page_task))),
    core_claim: source.core_claim,
    visible_copy: Object.prototype.hasOwnProperty.call(source, "visible_copy")
      ? structuredClone(source.visible_copy)
      : structuredClone(source.frozen_copy ?? []),
    speaker_notes: source.speaker_notes,
    source_refs: structuredClone(source.source_refs ?? []),
    communication_goal: source.communication_goal,
    composition_intent: source.composition_intent,
    information_hierarchy: source.information_hierarchy,
    reading_order: source.reading_order,
    regions: source.regions,
    object_relationships: source.object_relationships,
    diagram_chart_table_treatment: source.diagram_chart_table_treatment,
    image_selection_and_crop: source.image_selection_and_crop,
    color_application: source.color_application,
    typography_application: source.typography_application,
    native_bitmap_routing: source.native_bitmap_routing,
    editability_requirements: source.editability_requirements,
    fallbacks: source.fallbacks,
    acceptance_criteria: source.acceptance_criteria,
  };
}

function anchorAssets(review: ReviewProjection, slides: VisualReviewPageSlideContract[]): AnchorRenderAsset[] {
  const framework = review.sections.find((section) => section.anchor === "visual-framework");
  const frameworkFields = framework ? fieldMap(framework.fields) : {};
  const identity = objectValue(frameworkFields.anchor_identity);
  const declaredAssets = Array.isArray(identity.render_assets) ? identity.render_assets : [];
  const bySlide = new Map<string, AnchorRenderAsset>();
  for (const candidate of declaredAssets) {
    const source = objectValue(candidate);
    const slideId = text(source.slide_id);
    if (!slideId) continue;
    bySlide.set(slideId, {
      slide_id: slideId,
      current_asset_ref: text(source.current_asset_ref),
      previous_asset_ref: text(source.previous_asset_ref),
    });
  }
  for (const slide of slides.slice(0, 3)) {
    if (bySlide.has(slide.slide_id)) continue;
    const section = review.sections.find((item) => item.anchor === `visual-slide-${slide.slide_id}`);
    const source = section ? fieldMap(section.fields) : {};
    bySlide.set(slide.slide_id, {
      slide_id: slide.slide_id,
      current_asset_ref: text(source.current_asset_ref, text(source.render_asset_ref)),
      previous_asset_ref: text(source.previous_asset_ref),
    });
  }
  const result = [...bySlide.values()].slice(0, 3);
  while (result.length < 3) {
    const slot = result.length + 1;
    result.push({
      slide_id: `锚点缺口 ${slot}`,
      current_asset_ref: "",
      previous_asset_ref: "",
    });
  }
  return result;
}

export function legacyVisualReviewToPageViewModel(data: ReviewWidgetData): VisualReviewPageViewModel {
  const { review } = data;
  const slideContracts = review.sections
    .filter((section) => section.anchor.startsWith("visual-slide-"))
    .map(projectSlide);
  const anchors = anchorAssets(review, slideContracts);
  const framework = review.sections.find((section) => section.anchor === "visual-framework");
  const frameworkFields = framework ? fieldMap(framework.fields) : {};
  const identity = objectValue(frameworkFields.anchor_identity);
  const visualContractRef = text(review.source_version, review.source_refs[0] || "");
  return {
    surface: "review",
    selectedProjectRoot: data.selectedProjectRoot,
    snapshotRevision: data.snapshotRevision,
    review: {
      project_id: review.project_id,
      project_name: review.project_name,
      review_type: "visual-professional",
      review_session_id: `legacy-visual-${review.project_id}-r${review.revision}`,
      source_version: review.source_version,
      revision: review.revision,
      authoritative_revision: data.snapshotRevision,
      visual_contract_ref: visualContractRef,
      deck_design_system_ref: artifactField(review, "deck_design_system_ref", visualContractRef),
      deck_design_system: projectDesignSystem(review),
      anchor_slide_set_ref: artifactField(review, "anchor_slide_set_ref", visualContractRef),
      anchors,
      anchor_identity: {
        slide_ids: stringList(identity.slide_ids),
        selection_reason: text(identity.selection_reason, "覆盖整套方案中需要专业视觉核验的代表性页面"),
        native_first_frozen: true,
      },
      slide_visual_contracts: slideContracts,
      anchor_feedback_batch_ref: null,
      anchor_feedback_batch: null,
      contract_review_marks_ref: null,
      contract_review_marks: null,
      host_submission_capability: "unknown",
      ai_receipt_capability: "unknown",
    },
  };
}
