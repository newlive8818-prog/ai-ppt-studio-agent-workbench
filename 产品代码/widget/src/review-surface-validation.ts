import type { ContentReviewProjection, ContentReviewSurfaceData } from "./types/content-review";
import type { ReviewSurfaceData } from "./types/host";
import type { VisualReviewProjection, VisualReviewSurfaceData } from "./types/visual-review";
import { isArtifactReference } from "./lib/artifact-reference";
import { isIsoInstant } from "./lib/iso-instant";
import { clonePlainData } from "./lib/plain-data";
import { validateInitialAnchorFeedbackBatch } from "./visual-review/anchor-feedback-validation";
import { validateInitialVisualContractMarkSet } from "./visual-review/visual-contract-mark-validation";
import { isReviewableVisualMapKey } from "./visual-review/visual-map-key-policy";
import type { VisualReceiptFacts } from "./visual-review/visual-receipt-facts";
import { toVisualReviewPageViewModel } from "./visual-review/visual-review-page-view-model";

const envelopeFields = [
  "ok", "projectRoot", "reviewType", "sourceVersion", "expectedRevision", "bridgeSessionId", "review",
] as const;
const hostOpenFields = ["ok", "hostOpenStatus", "snapshotRevision"] as const;
const surfaceFields = ["surface", "selectedProjectRoot", "snapshotRevision", "review"] as const;
const sessionRequiredFields = [
  "review_session_id", "review_type", "project_id", "target_artifact_ref", "source_version",
  "revision", "status", "open_policy", "host_open_status", "persistence_status",
  "host_notification_status", "ai_receipt_status", "created_at", "last_opened_at", "submitted_at",
] as const;
const sessionOptionalFields = [
  "host_open_receipt_ref", "host_notification_receipt_ref", "host_notification_receipts",
  "ai_receipt_ref", "ai_receipts", "superseded_at",
] as const;
const contentFields = [
  "project_id", "review_type", "review_session_id", "review_session", "source_version", "revision",
  "authoritative_revision", "reading_blueprint_ref", "material_mode", "section_flow", "slides",
  "decisions", "progress", "batch", "revision_plan", "content_acceptance_ref",
] as const;
const visualFields = [
  "project_id", "project_name", "review_type", "review_session_id", "review_session", "source_version",
  "revision", "authoritative_revision", "visual_contract_ref", "visual_brief_ref", "visual_brief",
  "deck_design_system_ref", "deck_design_system", "anchor_slide_set_ref", "anchors", "anchor_identity", "slide_visual_contracts",
  "anchor_feedback_batch_ref", "anchor_feedback_batch", "contract_review_marks_ref",
  "contract_review_marks", "host_submission_capability", "ai_receipt_capability",
] as const;
const imageLedFormalProjectionContract = "image-led-formal-visual-review/v1";
const contentSlideFields = [
  "slide_id", "order", "section_id", "page_task", "reading_question", "neutral_title",
  "customerJudgment", "visible_copy_blocks", "material_views",
] as const;
const materialViewFields = ["material_view_id", "asset_ref"] as const;
const decisionFields = [
  "page_decision_id", "project_id", "review_session_id", "source_version", "reading_blueprint_ref",
  "slide_id", "slide_order", "slide_title_snapshot", "decision", "comment", "status", "saved_at",
  "supersedes_decision_ref",
] as const;
const anchorFields = ["slide_id", "current_asset_ref", "previous_asset_ref"] as const;
const anchorIdentityFields = [
  "slide_ids", "selection_reason", "native_first_frozen",
] as const;
const visualBriefFields = [
  "design_proposition", "audience_fit", "decision_task", "design_stance", "emotional_boundary",
  "brand_boundary", "density_strategy", "narrative_rhythm", "imagery_strategy", "diagram_strategy",
  "powerpoint_constraints", "forbidden_patterns", "five_second_test_contract", "design_philosophy_refs",
] as const;
const deckDesignSystemFields = [
  "theme_proposition", "composition_grammar", "color_tokens", "typography_tokens", "page_families",
  "density_rhythm", "cross_slide_rhythm_rules", "emphasis_budget", "imagery_strategy", "image_language",
  "diagram_strategy", "diagram_language", "table_strategy", "editability_rules", "accessibility_rules",
  "forbidden_patterns", "five_second_test_rules", "anchor_specification", "production_route",
] as const;
const slideVisualContractFields = [
  "slide_id", "order", "neutral_title", "page_family", "anchor_title", "validation_purpose",
  "core_claim", "visible_copy", "speaker_notes", "source_refs", "communication_goal",
  "composition_intent", "information_hierarchy", "reading_order", "regions",
  "object_relationships", "diagram_chart_table_treatment", "image_selection_and_crop",
  "color_application", "typography_application", "native_bitmap_routing",
  "editability_requirements", "fallbacks", "acceptance_criteria", "reader_judgment",
  "primary_relationship", "secondary_relationship", "visual_mechanism", "focal_point", "asset_roles",
  "forbidden_patterns", "previous_rhythm_relation", "next_rhythm_relation", "text_density_budget",
  "powerpoint_implementation_requirements", "acceptance_evidence_plan",
] as const;
const fiveSecondTestContractFields = [
  "prompt", "expected_judgment", "record_fields",
] as const;
const emphasisBudgetFields = [
  "max_primary_focal_points_per_slide", "max_accent_color_roles",
  "consecutive_high_density_slide_limit",
] as const;
const assetRoleFields = [
  "asset_id", "role", "source_ref", "narrative_task", "replaceable",
] as const;
const textDensityBudgetFields = [
  "max_body_lines", "max_text_blocks", "reduction_strategy",
] as const;
const powerpointImplementationFields = [
  "object_plan", "connector_semantics", "layout_constraints",
  "native_bitmap_routing", "degradation_strategy",
] as const;
const powerpointObjectPlanFields = [
  "role", "object_type", "layer", "editability",
] as const;
const powerpointConnectorFields = [
  "from_role", "to_role", "meaning", "direction", "crossing_forbidden",
] as const;
const powerpointLayoutFields = [
  "entry_region", "focal_region", "minimum_clear_space",
] as const;
const acceptanceEvidencePlanFields = [
  "automated_checks", "human_review_checks", "target_powerpoint_checks",
  "user_review_question",
] as const;
const anchorSpecificationFields = [
  "slide_ids", "selection_reason", "native_first_frozen",
] as const;
const visualRegionFields = ["region_id", "purpose"] as const;
const visualRelationships = new Set([
  "comparison", "sequence", "causality", "hierarchy", "network",
  "system-boundary", "cycle", "tension", "evidence-to-judgment",
  "single-focus",
]);
const visualAssetRoles = new Set([
  "evidence", "structure", "explanation", "emotion-context",
]);
const expectedFiveSecondRecordFields = [
  "first_noticed_object", "perceived_message", "perceived_relationship",
  "next_reading_step", "misdirection",
] as const;

type PlainRecord = Record<string, unknown>;

export interface ValidatedReviewConnectionEnvelope {
  projectRoot: string;
  expectedRevision: number;
  bridgeSessionId: string;
  sessionExpiresAt?: number;
  review: ContentReviewProjection | VisualReviewProjection;
}

export interface ValidatedHostOpenEnvelope {
  snapshotRevision: number;
}

function isPlainRecord(value: unknown): value is PlainRecord {
  return Boolean(value)
    && typeof value === "object"
    && !Array.isArray(value)
    && Object.getPrototypeOf(value) === Object.prototype;
}

function hasClosedDataFields(
  value: unknown,
  requiredFields: readonly string[],
  optionalFields: readonly string[] = [],
): value is PlainRecord {
  if (!isPlainRecord(value)) return false;
  const required = new Set(requiredFields);
  const allowed = new Set([...requiredFields, ...optionalFields]);
  const keys = Reflect.ownKeys(value);
  if (keys.length < required.size || keys.length > allowed.size) return false;
  if ([...required].some((field) => !keys.includes(field))) return false;
  return keys.every((key) => {
    if (typeof key !== "string" || !allowed.has(key)) return false;
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    return Boolean(descriptor && "value" in descriptor && descriptor.enumerable);
  });
}

function hasExactDataFields(value: unknown, fields: readonly string[]): value is PlainRecord {
  return hasClosedDataFields(value, fields);
}

function hasSessionDataFields(value: unknown): value is PlainRecord {
  if (!isPlainRecord(value)) return false;
  const required = new Set<string>(sessionRequiredFields);
  const allowed = new Set<string>([...sessionRequiredFields, ...sessionOptionalFields]);
  const keys = Reflect.ownKeys(value);
  if (keys.some((key) => typeof key !== "string" || !allowed.has(key))) return false;
  if ([...required].some((field) => !keys.includes(field))) return false;
  return keys.every((key) => {
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    return Boolean(descriptor && "value" in descriptor && descriptor.enumerable);
  });
}

function isRevision(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

function isText(value: unknown, optional = false): value is string {
  return typeof value === "string"
    && value === value.trim()
    && (optional || Boolean(value));
}

function isTimestamp(value: unknown): value is string {
  return isIsoInstant(value);
}

function isTimestampOrNull(value: unknown): value is string | null {
  return value === null || isTimestamp(value);
}

function isStringArray(value: unknown, nonEmptyItems = true): value is string[] {
  return Array.isArray(value) && value.every((item) => isText(item, !nonEmptyItems));
}

function isUniqueTextArray(value: unknown, allowEmpty = false): value is string[] {
  return isStringArray(value)
    && (allowEmpty || value.length > 0)
    && new Set(value).size === value.length;
}

function isPositiveInteger(value: unknown): value is number {
  return typeof value === "number"
    && Number.isSafeInteger(value)
    && value > 0;
}

function validateVisualTextMap(value: unknown): value is Record<string, string> {
  if (!isPlainRecord(value)) return false;
  const keys = Reflect.ownKeys(value);
  if (keys.length === 0) return false;
  const normalizedKeys = new Set<string>();
  return keys.every((key) => {
    if (typeof key !== "string") return false;
    const normalizedKey = key.trim();
    if (
      !isReviewableVisualMapKey(normalizedKey)
      || normalizedKeys.has(normalizedKey)
    ) return false;
    normalizedKeys.add(normalizedKey);
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    return Boolean(
      descriptor
      && "value" in descriptor
      && descriptor.enumerable
      && isText(descriptor.value),
    );
  });
}

function validateTextOrTextArray(value: unknown): boolean {
  return isText(value) || isUniqueTextArray(value);
}

function validateAnchorSpecification(value: unknown): boolean {
  if (isText(value)) return true;
  return hasExactDataFields(value, anchorSpecificationFields)
    && isUniqueTextArray(value.slide_ids)
    && isText(value.selection_reason)
    && value.native_first_frozen === true;
}

function validateVisualRegions(
  value: unknown,
  allowUnestablished = false,
): boolean {
  if (!Array.isArray(value) || value.length === 0) return false;
  const regionIds = new Set<string>();
  return value.every((region) => {
    if (isText(region)) return true;
    if (
      !hasExactDataFields(region, visualRegionFields)
      || !isText(region.region_id)
      || regionIds.has(region.region_id)
      || !(isText(region.purpose) || (allowUnestablished && region.purpose === null))
    ) return false;
    regionIds.add(region.region_id);
    return true;
  });
}

function validateReceiptBindingMap(
  value: unknown,
  receiptKind: "review-host-notification-receipt" | "review-ai-receipt",
): Record<string, string> | null {
  if (!isPlainRecord(value)) return null;
  const bindings: Record<string, string> = {};
  for (const key of Reflect.ownKeys(value)) {
    if (
      typeof key !== "string"
      || !(
        isArtifactReference(key, "visual-anchor-feedback-batch")
        || isArtifactReference(key, "visual-contract-review-mark-set")
      )
    ) return null;
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    if (
      !descriptor
      || !("value" in descriptor)
      || !descriptor.enumerable
      || !isArtifactReference(descriptor.value, receiptKind)
    ) return null;
    bindings[key] = descriptor.value;
  }
  return bindings;
}

function validateSession(
  value: unknown,
  identity: {
    reviewType: "content-full-deck" | "visual-professional";
    projectId: string;
    reviewSessionId: string;
    sourceVersion: string;
    targetArtifactRef: string;
    targetArtifactKind: "reading-deck-blueprint" | "visual-contract";
    authoritativeRevision: number;
    revision: number;
  },
): PlainRecord | null {
  if (!hasSessionDataFields(value)) return null;
  if (
    value.review_session_id !== identity.reviewSessionId
    || value.review_type !== identity.reviewType
    || value.project_id !== identity.projectId
    || value.target_artifact_ref !== identity.targetArtifactRef
    || !isArtifactReference(value.target_artifact_ref, identity.targetArtifactKind)
    || value.source_version !== identity.sourceVersion
    || value.revision !== identity.revision
    || !isRevision(value.revision)
    || value.revision > identity.authoritativeRevision
    || !["ready", "opened", "submitted", "superseded"].includes(String(value.status))
    || !["foreground-if-waiting", "notify-only"].includes(String(value.open_policy))
    || !["not-requested", "pending", "opened", "failed", "unavailable"].includes(String(value.host_open_status))
    || value.persistence_status !== "saved"
    || !["not-requested", "pending", "sent", "failed", "unavailable"].includes(String(value.host_notification_status))
    || !["pending", "received", "rejected", "unverified"].includes(String(value.ai_receipt_status))
    || !isTimestamp(value.created_at)
    || !isTimestampOrNull(value.last_opened_at)
    || !isTimestampOrNull(value.submitted_at)
  ) return null;
  for (const [field, kind] of [
    ["host_open_receipt_ref", "review-host-open-receipt"],
    ["host_notification_receipt_ref", "review-host-notification-receipt"],
    ["ai_receipt_ref", "review-ai-receipt"],
  ] as const) {
    if (field in value && !isArtifactReference(value[field], kind)) return null;
  }
  const hostBindings = "host_notification_receipts" in value
    ? validateReceiptBindingMap(
        value.host_notification_receipts,
        "review-host-notification-receipt",
      )
    : {};
  const aiBindings = "ai_receipts" in value
    ? validateReceiptBindingMap(value.ai_receipts, "review-ai-receipt")
    : {};
  if (!hostBindings || !aiBindings) return null;
  if (
    identity.reviewType !== "visual-professional"
    && ("host_notification_receipts" in value || "ai_receipts" in value)
  ) return null;
  if (identity.reviewType === "visual-professional") {
    const hostReceiptRef = String(value.host_notification_receipt_ref || "");
    const aiReceiptRef = String(value.ai_receipt_ref || "");
    if (
      (value.host_notification_status === "sent"
        ? !Object.values(hostBindings).includes(hostReceiptRef)
        : Object.keys(hostBindings).length > 0)
      || (value.ai_receipt_status === "received"
        ? !Object.values(aiBindings).includes(aiReceiptRef)
        : Object.keys(aiBindings).length > 0)
    ) return null;
  }
  if ("superseded_at" in value && !isTimestampOrNull(value.superseded_at)) return null;
  if (value.host_open_status === "opened" && value.last_opened_at === null) return null;
  if ((value.status === "opened" || value.host_open_status === "opened") && !("host_open_receipt_ref" in value)) return null;
  if (value.host_notification_status === "sent" && !("host_notification_receipt_ref" in value)) return null;
  if (value.ai_receipt_status === "received" && !("ai_receipt_ref" in value)) return null;
  if (value.status === "submitted" && value.submitted_at === null) return null;
  if (value.status === "superseded" && !isTimestamp(value.superseded_at)) return null;
  return value;
}

function validateContentSlide(value: unknown): boolean {
  if (!hasExactDataFields(value, contentSlideFields)) return false;
  if (
    !isText(value.slide_id) || !isRevision(value.order) || value.order < 1
    || !isText(value.section_id) || !isText(value.page_task) || !isText(value.reading_question)
    || !isText(value.neutral_title) || !isText(value.customerJudgment)
    || !Array.isArray(value.visible_copy_blocks)
    || !Array.isArray(value.material_views)
  ) return false;
  for (const block of value.visible_copy_blocks) {
    if (!hasExactDataFields(block, ["block_id", "text"]) || !isText(block.block_id) || !isText(block.text)) return false;
  }
  for (const material of value.material_views) {
    if (!hasExactDataFields(material, materialViewFields)
      || !isText(material.material_view_id) || !isText(material.asset_ref)) return false;
  }
  return true;
}

function validateContentDecision(value: unknown, review: PlainRecord): boolean {
  return hasExactDataFields(value, decisionFields)
    && isText(value.page_decision_id)
    && value.project_id === review.project_id
    && value.review_session_id === review.review_session_id
    && value.source_version === review.source_version
    && value.reading_blueprint_ref === review.reading_blueprint_ref
    && isText(value.slide_id)
    && isRevision(value.slide_order) && value.slide_order >= 1
    && isText(value.slide_title_snapshot)
    && ["approved", "modify", "evidence", "merge-or-delete"].includes(String(value.decision))
    && isText(value.comment, true)
    && value.status === "completed"
    && isTimestamp(value.saved_at)
    && isText(value.supersedes_decision_ref, true);
}

function validateProgress(value: unknown): boolean {
  if (!hasExactDataFields(value, ["completed", "total", "remaining", "unsaved"])) return false;
  const { completed, total, remaining, unsaved } = value;
  return isRevision(completed)
    && isRevision(total)
    && isRevision(remaining)
    && isRevision(unsaved)
    && completed + remaining === total;
}

function validateContentDeckStructure(sectionFlow: unknown, slides: unknown): boolean {
  if (!isStringArray(sectionFlow) || !Array.isArray(slides)) return false;
  const sectionTitles = new Set<string>();
  for (const sectionTitle of sectionFlow) {
    if (sectionTitles.has(sectionTitle)) return false;
    sectionTitles.add(sectionTitle);
  }
  const slideIds = new Set<string>();
  const seenSectionIds = new Set<string>();
  let currentSectionId = "";
  for (const [index, slide] of slides.entries()) {
    if (!isPlainRecord(slide) || !isText(slide.slide_id) || slideIds.has(slide.slide_id)) return false;
    if (slide.order !== index + 1 || !isText(slide.section_id)) return false;
    if (slide.section_id !== currentSectionId) {
      if (seenSectionIds.has(slide.section_id)) return false;
      seenSectionIds.add(slide.section_id);
      currentSectionId = slide.section_id;
    }
    slideIds.add(slide.slide_id);
  }
  return seenSectionIds.size <= sectionFlow.length;
}

function validateContentProjection(value: unknown, expectedRevision?: number): ContentReviewProjection | null {
  if (!hasExactDataFields(value, contentFields)) return null;
  if (
    value.review_type !== "content-full-deck"
    || !isText(value.project_id) || !isText(value.review_session_id) || !isText(value.source_version)
    || !isRevision(value.revision) || !isRevision(value.authoritative_revision)
    || value.revision > value.authoritative_revision
    || (expectedRevision !== undefined && value.authoritative_revision !== expectedRevision)
    || !isArtifactReference(value.reading_blueprint_ref, "reading-deck-blueprint")
    || !["material-backed", "mixed-evidence", "proposal-led"].includes(String(value.material_mode))
    || !Array.isArray(value.slides)
    || !validateContentDeckStructure(value.section_flow, value.slides)
    || !value.slides.every(validateContentSlide)
    || !Array.isArray(value.decisions) || !value.decisions.every((item) => validateContentDecision(item, value))
    || !validateProgress(value.progress)
    || (value.batch !== null && !isPlainRecord(value.batch))
    || (value.revision_plan !== null && !isPlainRecord(value.revision_plan))
    || !isText(value.content_acceptance_ref)
  ) return null;
  const session = validateSession(value.review_session, {
    reviewType: "content-full-deck",
    projectId: value.project_id,
    reviewSessionId: value.review_session_id,
    sourceVersion: value.source_version,
    targetArtifactRef: value.reading_blueprint_ref,
    targetArtifactKind: "reading-deck-blueprint",
    authoritativeRevision: value.authoritative_revision,
    revision: value.revision,
  });
  return session ? value as unknown as ContentReviewProjection : null;
}

function validateAnchors(value: unknown): value is Array<{ slide_id: string; current_asset_ref: string; previous_asset_ref: string }> {
  if (!Array.isArray(value) || value.length !== 3) return false;
  const ids = new Set<string>();
  return value.every((anchor) => {
    if (!hasExactDataFields(anchor, anchorFields)
      || !isText(anchor.slide_id) || ids.has(anchor.slide_id)
      || !isText(anchor.current_asset_ref) || !isText(anchor.previous_asset_ref, true)) return false;
    ids.add(anchor.slide_id);
    return true;
  });
}

function validateAnchorIdentity(value: unknown, anchors: Array<{ slide_id: string; current_asset_ref: string; previous_asset_ref: string }>): boolean {
  return hasExactDataFields(value, anchorIdentityFields)
    && isStringArray(value.slide_ids)
    && value.slide_ids.length === anchors.length
    && value.slide_ids.every((id, index) => id === anchors[index].slide_id)
    && isText(value.selection_reason)
    && value.native_first_frozen === true;
}

function validateVisualBrief(value: unknown): boolean {
  if (!hasExactDataFields(value, visualBriefFields)) return false;
  for (const field of [
    "design_proposition", "audience_fit", "decision_task", "design_stance",
    "emotional_boundary", "brand_boundary", "density_strategy",
    "narrative_rhythm", "imagery_strategy", "diagram_strategy",
    "powerpoint_constraints",
  ] as const) {
    if (!isText(value[field])) return false;
  }
  return isUniqueTextArray(value.forbidden_patterns)
    && isUniqueTextArray(value.design_philosophy_refs, true)
    && validateFiveSecondTestContract(value.five_second_test_contract);
}

function validateFiveSecondTestContract(value: unknown): boolean {
  if (!hasExactDataFields(value, fiveSecondTestContractFields)) return false;
  const recordFields = value.record_fields;
  return value.prompt === "五秒后隐藏页面并记录第一判断"
    && value.expected_judgment === "读者形成与页面合同一致的核心判断"
    && Array.isArray(recordFields)
    && recordFields.length === expectedFiveSecondRecordFields.length
    && expectedFiveSecondRecordFields.every(
      (field, index) => recordFields[index] === field,
    );
}

function validateEmphasisBudget(value: unknown): boolean {
  return hasExactDataFields(value, emphasisBudgetFields)
    && emphasisBudgetFields.every((field) => isPositiveInteger(value[field]));
}

function validateDeckDesignSystem(value: unknown): boolean {
  if (!isPlainRecord(value)) return false;
  const allowed = new Set<string>([...deckDesignSystemFields, "fallback_fonts"]);
  const keys = Reflect.ownKeys(value);
  if (keys.some((key) => typeof key !== "string" || !allowed.has(key))) return false;
  if (deckDesignSystemFields.some((field) => !keys.includes(field))) return false;
  if (!keys.every((key) => {
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    return Boolean(descriptor && "value" in descriptor && descriptor.enumerable);
  })) return false;
  return isText(value.theme_proposition)
    && isText(value.composition_grammar)
    && validateVisualTextMap(value.color_tokens)
    && validateVisualTextMap(value.typography_tokens)
    && isUniqueTextArray(value.page_families)
    && isUniqueTextArray(value.density_rhythm)
    && isUniqueTextArray(value.cross_slide_rhythm_rules)
    && validateEmphasisBudget(value.emphasis_budget)
    && isText(value.imagery_strategy)
    && isText(value.image_language)
    && isText(value.diagram_strategy)
    && isText(value.diagram_language)
    && isText(value.table_strategy)
    && validateTextOrTextArray(value.editability_rules)
    && (value.accessibility_rules === null
      || validateTextOrTextArray(value.accessibility_rules))
    && isUniqueTextArray(value.forbidden_patterns)
    && isUniqueTextArray(value.five_second_test_rules)
    && validateAnchorSpecification(value.anchor_specification)
    && value.production_route === "strict-B"
    && (!("fallback_fonts" in value)
      || validateVisualTextMap(value.fallback_fonts));
}

function validateAssetRoles(value: unknown): boolean {
  if (!Array.isArray(value)) return false;
  const assetIds = new Set<string>();
  for (const asset of value) {
    if (
      !hasExactDataFields(asset, assetRoleFields)
      || !isText(asset.asset_id)
      || assetIds.has(asset.asset_id)
      || !visualAssetRoles.has(String(asset.role))
      || typeof asset.source_ref !== "string"
      || asset.source_ref !== asset.source_ref.trim()
      || !isText(asset.narrative_task)
      || typeof asset.replaceable !== "boolean"
      || (asset.role === "evidence" && !asset.source_ref)
    ) return false;
    assetIds.add(asset.asset_id);
  }
  return true;
}

function validateTextDensityBudget(value: unknown): boolean {
  return hasExactDataFields(value, textDensityBudgetFields)
    && isPositiveInteger(value.max_body_lines)
    && isPositiveInteger(value.max_text_blocks)
    && isText(value.reduction_strategy);
}

function validatePowerpointImplementationRequirements(value: unknown): boolean {
  if (!hasExactDataFields(value, powerpointImplementationFields)) return false;
  if (!Array.isArray(value.object_plan) || value.object_plan.length === 0) return false;
  const objectRoles = new Set<string>();
  for (const object of value.object_plan) {
    if (
      !hasExactDataFields(object, powerpointObjectPlanFields)
      || !isText(object.role)
      || objectRoles.has(object.role)
      || !isText(object.object_type)
      || !isText(object.layer)
      || !isText(object.editability)
    ) return false;
    objectRoles.add(object.role);
  }
  if (!Array.isArray(value.connector_semantics)) return false;
  for (const connector of value.connector_semantics) {
    if (
      !hasExactDataFields(connector, powerpointConnectorFields)
      || !isText(connector.from_role)
      || !isText(connector.to_role)
      || connector.from_role === connector.to_role
      || !isText(connector.meaning)
      || !isText(connector.direction)
      || typeof connector.crossing_forbidden !== "boolean"
    ) return false;
  }
  const layout = value.layout_constraints;
  return hasExactDataFields(layout, powerpointLayoutFields)
    && powerpointLayoutFields.every((field) => isText(layout[field]))
    && isText(value.native_bitmap_routing)
    && isText(value.degradation_strategy);
}

function validateAcceptanceEvidencePlan(value: unknown): boolean {
  return hasExactDataFields(value, acceptanceEvidencePlanFields)
    && isUniqueTextArray(value.automated_checks)
    && isUniqueTextArray(value.human_review_checks)
    && isUniqueTextArray(value.target_powerpoint_checks)
    && isText(value.user_review_question);
}

function validateVisualAcceptanceCriteria(value: unknown): boolean {
  return Array.isArray(value)
    && value.length > 0
    && value.every((criterion) => (
      hasExactDataFields(criterion, ["criterion_id", "level", "expected_outcome"])
      && isText(criterion.criterion_id)
      && ["must-follow", "minimum-aesthetic", "reference-implementation"].includes(String(criterion.level))
      && isText(criterion.expected_outcome)
    ));
}

function validateSlideVisualContracts(
  value: unknown,
  allowUnestablished = false,
): value is Array<PlainRecord & { slide_id: string }> {
  if (!Array.isArray(value) || value.length === 0) return false;
  const ids = new Set<string>();
  for (let index = 0; index < value.length; index += 1) {
    const contract = value[index];
    if (
      !hasExactDataFields(contract, slideVisualContractFields)
      || !isText(contract.slide_id)
      || ids.has(contract.slide_id)
      || contract.order !== index + 1
      || !isText(contract.neutral_title)
      || !isText(contract.anchor_title)
      || !isText(contract.validation_purpose)
      || !isText(contract.page_family)
      || !(contract.core_claim === null || isText(contract.core_claim))
      || !isStringArray(contract.visible_copy)
      || !isText(contract.speaker_notes, true)
      || !isStringArray(contract.source_refs)
      || !(
        isText(contract.communication_goal)
        || (allowUnestablished && contract.communication_goal === null)
      )
      || !isText(contract.composition_intent)
      || !isText(contract.information_hierarchy)
      || !isUniqueTextArray(contract.reading_order)
      || !validateVisualRegions(contract.regions, allowUnestablished)
      || !isUniqueTextArray(contract.object_relationships)
      || !isText(contract.diagram_chart_table_treatment)
      || !isText(contract.image_selection_and_crop)
      || !isText(contract.color_application)
      || !isText(contract.typography_application)
      || !isText(contract.native_bitmap_routing)
      || !isText(contract.editability_requirements)
      || !isUniqueTextArray(contract.fallbacks)
      || !validateVisualAcceptanceCriteria(contract.acceptance_criteria)
      || !isText(contract.reader_judgment)
      || !visualRelationships.has(String(contract.primary_relationship))
      || !(contract.secondary_relationship === null
        || visualRelationships.has(String(contract.secondary_relationship)))
      || contract.secondary_relationship === contract.primary_relationship
      || !isText(contract.visual_mechanism)
      || !isText(contract.focal_point)
      || !validateAssetRoles(contract.asset_roles)
      || !isUniqueTextArray(contract.forbidden_patterns)
      || !isText(contract.previous_rhythm_relation)
      || !isText(contract.next_rhythm_relation)
      || !validateTextDensityBudget(contract.text_density_budget)
      || !validatePowerpointImplementationRequirements(
        contract.powerpoint_implementation_requirements,
      )
      || !validateAcceptanceEvidencePlan(contract.acceptance_evidence_plan)
    ) return false;
    ids.add(contract.slide_id);
  }
  return true;
}

function validateVisualProjection(value: unknown, expectedRevision?: number): VisualReviewProjection | null {
  if (!hasClosedDataFields(value, visualFields, ["projection_contract"])) return null;
  const imageLedFormal = value.projection_contract === imageLedFormalProjectionContract;
  if (value.projection_contract !== undefined && !imageLedFormal) return null;
  if (
    value.review_type !== "visual-professional"
    || !isText(value.project_id) || !isText(value.project_name) || !isText(value.review_session_id)
    || !isText(value.source_version) || !isRevision(value.revision) || !isRevision(value.authoritative_revision)
    || value.revision > value.authoritative_revision
    || (expectedRevision !== undefined && value.authoritative_revision !== expectedRevision)
    || !isArtifactReference(value.visual_contract_ref, "visual-contract")
    || !isArtifactReference(value.visual_brief_ref, "visual-brief")
    || !validateVisualBrief(value.visual_brief)
    || !isArtifactReference(value.deck_design_system_ref, "deck-design-system")
    || !validateDeckDesignSystem(value.deck_design_system)
    || !isArtifactReference(value.anchor_slide_set_ref, "anchor-slide-set")
    || !validateAnchors(value.anchors) || !validateAnchorIdentity(value.anchor_identity, value.anchors)
    || !validateSlideVisualContracts(value.slide_visual_contracts, imageLedFormal)
    || !["available", "unavailable", "unknown"].includes(String(value.host_submission_capability))
    || !["available", "unavailable", "unknown"].includes(String(value.ai_receipt_capability))
  ) return null;
  if (
    (value.anchor_feedback_batch === null) !== (value.anchor_feedback_batch_ref === null)
    || (value.contract_review_marks === null) !== (value.contract_review_marks_ref === null)
    || (value.anchor_feedback_batch_ref !== null
      && !isArtifactReference(value.anchor_feedback_batch_ref, "visual-anchor-feedback-batch"))
    || (value.contract_review_marks_ref !== null
      && !isArtifactReference(value.contract_review_marks_ref, "visual-contract-review-mark-set"))
  ) return null;
  const session = validateSession(value.review_session, {
    reviewType: "visual-professional",
    projectId: value.project_id,
    reviewSessionId: value.review_session_id,
    sourceVersion: value.source_version,
    targetArtifactRef: value.visual_contract_ref,
    targetArtifactKind: "visual-contract",
    authoritativeRevision: value.authoritative_revision,
    revision: value.revision,
  });
  if (!session) return null;
  const factsFor = (savedArtifactRef: unknown): VisualReceiptFacts => ({
    hostNotificationStatus:
      typeof savedArtifactRef === "string"
      && Object.prototype.hasOwnProperty.call(
        session.host_notification_receipts || {},
        savedArtifactRef,
      )
        ? "sent"
        : "unavailable",
    aiReceiptStatus:
      typeof savedArtifactRef === "string"
      && Object.prototype.hasOwnProperty.call(
        session.ai_receipts || {},
        savedArtifactRef,
      )
        ? "received"
        : "unverified",
  });
  const provisional = toVisualReviewPageViewModel({
    surface: "review",
    selectedProjectRoot: "validated-projection",
    snapshotRevision: value.authoritative_revision,
    review: { ...value, contract_review_marks: null } as unknown as VisualReviewProjection,
  });
  const marks = validateInitialVisualContractMarkSet(
    value.contract_review_marks,
    provisional,
    factsFor(value.contract_review_marks_ref),
  );
  if (!marks) return null;
  const batch = value.anchor_feedback_batch === null
    ? null
    : validateInitialAnchorFeedbackBatch(
        value.anchor_feedback_batch,
        provisional,
        factsFor(value.anchor_feedback_batch_ref),
      );
  if (value.anchor_feedback_batch !== null && !batch) return null;
  return {
    ...value,
    anchor_feedback_batch: batch,
    contract_review_marks: marks.markSet,
  } as unknown as VisualReviewProjection;
}

function validateProjection(value: unknown, expectedRevision?: number) {
  if (!isPlainRecord(value)) return null;
  if (value.review_type === "content-full-deck") return validateContentProjection(value, expectedRevision);
  if (value.review_type === "visual-professional") return validateVisualProjection(value, expectedRevision);
  return null;
}

export function validateReviewConnectionEnvelope(value: unknown): ValidatedReviewConnectionEnvelope | null {
  const cloned = clonePlainData(value);
  const hasDeadline = isPlainRecord(cloned) && Object.hasOwn(cloned, "sessionExpiresAt");
  if (!hasExactDataFields(cloned, hasDeadline ? [...envelopeFields, "sessionExpiresAt"] : envelopeFields)
    || cloned.ok !== true) return null;
  if (hasDeadline && (
    typeof cloned.sessionExpiresAt !== "number"
    || !Number.isSafeInteger(cloned.sessionExpiresAt)
    || cloned.sessionExpiresAt <= 0
    || cloned.sessionExpiresAt > 8_640_000_000_000_000
  )) return null;
  if (
    !isText(cloned.projectRoot) || !isText(cloned.bridgeSessionId)
    || !isRevision(cloned.expectedRevision)
    || (cloned.reviewType !== "content-full-deck" && cloned.reviewType !== "visual-professional")
    || !isText(cloned.sourceVersion)
  ) return null;
  const review = validateProjection(cloned.review, cloned.expectedRevision);
  if (!review || review.review_type !== cloned.reviewType || review.source_version !== cloned.sourceVersion) return null;
  return {
    projectRoot: cloned.projectRoot,
    expectedRevision: cloned.expectedRevision,
    bridgeSessionId: cloned.bridgeSessionId,
    ...(hasDeadline ? { sessionExpiresAt: cloned.sessionExpiresAt as number } : {}),
    review,
  };
}

export function validateHostOpenEnvelope(value: unknown, expectedRevision: number): ValidatedHostOpenEnvelope | null {
  const cloned = clonePlainData(value);
  if (!hasExactDataFields(cloned, hostOpenFields)
    || cloned.ok !== true || cloned.hostOpenStatus !== "opened"
    || !isRevision(expectedRevision)
    || expectedRevision >= Number.MAX_SAFE_INTEGER
    || !isRevision(cloned.snapshotRevision)
    || cloned.snapshotRevision !== expectedRevision + 1) return null;
  return { snapshotRevision: cloned.snapshotRevision };
}

export function validateReviewSurfaceData(value: unknown): ReviewSurfaceData | null {
  const cloned = clonePlainData(value);
  if (!hasExactDataFields(cloned, surfaceFields)
    || cloned.surface !== "review" || !isText(cloned.selectedProjectRoot)
    || !isRevision(cloned.snapshotRevision)) return null;
  const review = validateProjection(cloned.review);
  if (!review || review.authoritative_revision > cloned.snapshotRevision) return null;
  return review.review_type === "content-full-deck"
    ? {
        surface: "review",
        selectedProjectRoot: cloned.selectedProjectRoot,
        snapshotRevision: cloned.snapshotRevision,
        review,
      } satisfies ContentReviewSurfaceData
    : {
        surface: "review",
        selectedProjectRoot: cloned.selectedProjectRoot,
        snapshotRevision: cloned.snapshotRevision,
        review,
      } satisfies VisualReviewSurfaceData;
}
