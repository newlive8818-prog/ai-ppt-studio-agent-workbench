import type { ContentReviewProjection, ContentReviewSurfaceData } from "./types/content-review";
import type { ReviewSurfaceData } from "./types/host";
import type { VisualReviewProjection, VisualReviewSurfaceData } from "./types/visual-review";
import { isArtifactReference } from "./lib/artifact-reference";
import { isIsoInstant } from "./lib/iso-instant";
import { clonePlainData } from "./lib/plain-data";
import { validateInitialAnchorFeedbackBatch } from "./visual-review/anchor-feedback-validation";
import { validateInitialVisualContractMarkSet } from "./visual-review/visual-contract-mark-validation";
import type { VisualReceiptFacts } from "./visual-review/visual-receipt-facts";

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
  "revision", "authoritative_revision", "visual_contract_ref", "deck_design_system_ref",
  "deck_design_system", "anchor_slide_set_ref", "anchors", "anchor_identity", "slide_visual_contracts",
  "anchor_feedback_batch_ref", "anchor_feedback_batch", "contract_review_marks_ref",
  "contract_review_marks", "gate_status", "host_submission_capability", "ai_receipt_capability",
] as const;
const contentSlideFields = [
  "slide_id", "order", "section_id", "page_task", "reading_question", "neutral_title",
  "visible_copy_blocks", "identity_labels", "evidence_bindings", "material_views",
  "analysis_or_proposal_blocks", "solution_mapping_refs", "previous_relation", "next_relation",
  "speaker_notes", "reading_quality", "material_mode",
] as const;
const materialViewFields = [
  "material_view_id", "source_ref", "asset_ref", "source_file_name", "page_number", "region_label",
  "purpose", "treatment", "evidence_identity",
] as const;
const decisionFields = [
  "page_decision_id", "project_id", "review_session_id", "source_version", "reading_blueprint_ref",
  "slide_id", "slide_order", "slide_title_snapshot", "decision", "comment", "status", "saved_at",
  "supersedes_decision_ref",
] as const;
const anchorFields = ["slide_id", "current_asset_ref", "previous_asset_ref"] as const;
const anchorIdentityFields = [
  "visual_contract_set_ref", "slide_ids", "selection_reason", "native_first_frozen", "native_first_pptx_ref", "pptx_sha256",
  "editability_evidence_refs", "preflight_render_refs", "render_assets",
] as const;
const slideVisualContractRequiredTextFields = [
  "page_family", "information_hierarchy", "composition_intent", "image_selection_and_crop",
  "typography_application", "color_application", "diagram_chart_table_treatment",
  "native_bitmap_routing", "editability_requirements",
] as const;
const slideVisualContractNonemptyFields = [
  "regions", "object_relationships", "reading_order", "fallbacks", "acceptance_criteria",
] as const;

type PlainRecord = Record<string, unknown>;

export interface ValidatedReviewConnectionEnvelope {
  projectRoot: string;
  expectedRevision: number;
  bridgeSessionId: string;
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

function hasExactDataFields(value: unknown, fields: readonly string[]): value is PlainRecord {
  if (!isPlainRecord(value)) return false;
  const expected = new Set(fields);
  const keys = Reflect.ownKeys(value);
  if (keys.length !== fields.length) return false;
  return keys.every((key) => {
    if (typeof key !== "string" || !expected.has(key)) return false;
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    return Boolean(descriptor && "value" in descriptor && descriptor.enumerable);
  });
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
    || !["not-requested", "opened", "failed"].includes(String(value.host_open_status))
    || value.persistence_status !== "saved"
    || !["not-requested", "sent", "failed"].includes(String(value.host_notification_status))
    || !["pending", "received", "failed"].includes(String(value.ai_receipt_status))
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
    || !isText(value.neutral_title) || !isStringArray(value.identity_labels)
    || !isStringArray(value.solution_mapping_refs, false)
    || !isText(value.previous_relation, true) || !isText(value.next_relation, true)
    || !isText(value.speaker_notes, true)
    || !["material-backed", "mixed-evidence", "proposal-led"].includes(String(value.material_mode))
    || !Array.isArray(value.visible_copy_blocks)
    || !Array.isArray(value.analysis_or_proposal_blocks)
    || !Array.isArray(value.evidence_bindings)
    || !Array.isArray(value.material_views)
  ) return false;
  for (const block of [...value.visible_copy_blocks, ...value.analysis_or_proposal_blocks]) {
    if (!hasExactDataFields(block, ["block_id", "text", "identity"]) || !isText(block.block_id) || !isText(block.text) || !isText(block.identity)) return false;
  }
  for (const binding of value.evidence_bindings) if (!isPlainRecord(binding)) return false;
  for (const material of value.material_views) {
    if (!hasExactDataFields(material, materialViewFields)
      || !isText(material.material_view_id) || !isText(material.source_ref) || !isText(material.asset_ref)
      || !isText(material.source_file_name) || !isRevision(material.page_number) || material.page_number < 1
      || !isText(material.region_label) || !isText(material.purpose) || !isText(material.treatment)
      || !isText(material.evidence_identity)) return false;
  }
  return hasExactDataFields(value.reading_quality, ["independently_readable", "information_density", "review_note"])
    && typeof value.reading_quality.independently_readable === "boolean"
    && isText(value.reading_quality.information_density)
    && isText(value.reading_quality.review_note, true);
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
    || !isStringArray(value.section_flow, false)
    || !Array.isArray(value.slides) || !value.slides.every(validateContentSlide)
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
  if (!Array.isArray(value)) return false;
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
    && isArtifactReference(value.visual_contract_set_ref, "visual-contract-set")
    && isStringArray(value.slide_ids)
    && value.slide_ids.length === anchors.length
    && value.slide_ids.every((id, index) => id === anchors[index].slide_id)
    && isText(value.selection_reason)
    && value.native_first_frozen === true
    && isText(value.native_first_pptx_ref)
    && typeof value.pptx_sha256 === "string" && /^[0-9a-f]{64}$/i.test(value.pptx_sha256)
    && isStringArray(value.editability_evidence_refs)
    && isStringArray(value.preflight_render_refs)
    && validateAnchors(value.render_assets)
    && value.render_assets.every((asset, index) => (
      asset.slide_id === anchors[index].slide_id
      && asset.current_asset_ref === anchors[index].current_asset_ref
      && asset.previous_asset_ref === anchors[index].previous_asset_ref
    ));
}

function isNonemptyContractValue(value: unknown): boolean {
  if (typeof value === "string") return isText(value);
  if (Array.isArray(value)) return value.length > 0;
  return isPlainRecord(value) && Reflect.ownKeys(value).length > 0;
}

function validateVisualAcceptanceCriteria(value: unknown): boolean {
  return Array.isArray(value)
    && value.length > 0
    && value.every((criterion) => (
      isPlainRecord(criterion)
      && isText(criterion.criterion_id)
      && ["must-follow", "minimum-aesthetic", "reference-implementation"].includes(String(criterion.level))
      && isText(criterion.expected_outcome)
    ));
}

function validateSlideVisualContracts(value: unknown): value is Array<PlainRecord & { slide_id: string }> {
  if (!Array.isArray(value) || value.length === 0) return false;
  const ids = new Set<string>();
  for (let index = 0; index < value.length; index += 1) {
    const contract = value[index];
    if (
      !isPlainRecord(contract)
      || !isText(contract.slide_id)
      || ids.has(contract.slide_id)
      || contract.order !== index + 1
      || !isText(contract.page_task)
      || !isText(contract.reading_question)
      || !isText(contract.neutral_title)
      || !Array.isArray(contract.visible_copy_blocks)
      || !contract.visible_copy_blocks.every(isPlainRecord)
      || !isStringArray(contract.identity_labels)
      || !Array.isArray(contract.evidence_bindings)
      || !contract.evidence_bindings.every(isPlainRecord)
      || !Array.isArray(contract.analysis_or_proposal_blocks)
      || !contract.analysis_or_proposal_blocks.every(isPlainRecord)
      || !isStringArray(contract.solution_mapping_refs, false)
      || !isText(contract.previous_relation, true)
      || !isText(contract.next_relation, true)
      || !isText(contract.speaker_notes, true)
      || !isPlainRecord(contract.reading_quality)
      || !["material-backed", "mixed-evidence", "proposal-led"].includes(String(contract.material_mode))
      || slideVisualContractRequiredTextFields.some((field) => !isText(contract[field]))
      || slideVisualContractNonemptyFields.some((field) => !isNonemptyContractValue(contract[field]))
      || !validateVisualAcceptanceCriteria(contract.acceptance_criteria)
      || !Array.isArray(contract.allowed_exceptions)
    ) return false;
    ids.add(contract.slide_id);
  }
  return true;
}

function validateVisualProjection(value: unknown, expectedRevision?: number): VisualReviewProjection | null {
  if (!hasExactDataFields(value, visualFields)) return null;
  if (
    value.review_type !== "visual-professional"
    || !isText(value.project_id) || !isText(value.project_name) || !isText(value.review_session_id)
    || !isText(value.source_version) || !isRevision(value.revision) || !isRevision(value.authoritative_revision)
    || value.revision > value.authoritative_revision
    || (expectedRevision !== undefined && value.authoritative_revision !== expectedRevision)
    || !isArtifactReference(value.visual_contract_ref, "visual-contract")
    || !isArtifactReference(value.deck_design_system_ref, "deck-design-system")
    || !isPlainRecord(value.deck_design_system)
    || !isArtifactReference(value.anchor_slide_set_ref, "anchor-slide-set")
    || !validateAnchors(value.anchors) || !validateAnchorIdentity(value.anchor_identity, value.anchors)
    || !validateSlideVisualContracts(value.slide_visual_contracts)
    || !hasExactDataFields(value.gate_status, ["G1", "G2", "G3"])
    || ![value.gate_status.G1, value.gate_status.G2, value.gate_status.G3].every((status) => isText(status))
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
  const provisional: VisualReviewSurfaceData = {
    surface: "review",
    selectedProjectRoot: "validated-projection",
    snapshotRevision: value.authoritative_revision,
    review: { ...value, contract_review_marks: null } as unknown as VisualReviewProjection,
  };
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
  if (!hasExactDataFields(cloned, envelopeFields) || cloned.ok !== true) return null;
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
