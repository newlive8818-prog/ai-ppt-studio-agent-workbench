export const DESIGN_SYSTEM_FIELD_ORDER = [
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
] as const;

export const FROZEN_SLIDE_FIELD_ORDER = [
  "core_claim",
  "visible_copy",
  "speaker_notes",
  "source_refs",
] as const;

export const VISUAL_SLIDE_FIELD_ORDER = [
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

export const REVIEWABLE_SLIDE_FIELD_KEYS = [
  ...FROZEN_SLIDE_FIELD_ORDER,
  ...VISUAL_SLIDE_FIELD_ORDER,
] as const;
