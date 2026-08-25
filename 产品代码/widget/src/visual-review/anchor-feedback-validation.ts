import type {
  AnchorFeedbackBatch,
  AnchorRegionFeedback,
  NormalizedRegion,
} from "../types/visual-review";
import type { VisualReviewPageViewModel } from "./visual-review-page-view-model";
import { isIsoInstant, parseIsoInstantMicros } from "../lib/iso-instant";
import { isArtifactReference } from "../lib/artifact-reference";
import { clonePlainData, hasExactDataFields } from "../review-draft/reviewDraftStore";
import { isValidNormalizedRegion } from "./normalized-region";
import {
  deriveVisualReceiptFacts,
  type VisualReceiptFacts,
} from "./visual-receipt-facts";

export interface ValidatedAnchorBatchResult {
  batchRef: string;
  batch: AnchorFeedbackBatch;
  revision: number;
}

const batchFields = [
  "batch_id", "project_id", "review_session_id", "visual_contract_ref", "deck_design_system_ref",
  "anchor_slide_set_ref", "items", "source_version", "revision", "persistence_status",
  "host_notification_status", "ai_receipt_status", "immutable_after_submit", "submitted_at", "submitted_by",
] as const;

const feedbackFields = [
  "feedback_id", "anchor_slide_id", "anchor_artifact_ref", "normalized_region", "comment", "order",
  "visual_source_version", "revision", "created_at", "created_by",
] as const;

function isNonEmptyText(value: unknown): value is string {
  return typeof value === "string" && Boolean(value.trim());
}

function isRevision(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

function sameRegion(left: NormalizedRegion, right: NormalizedRegion) {
  return left.x === right.x
    && left.y === right.y
    && left.width === right.width
    && left.height === right.height;
}

function sameFeedback(left: AnchorRegionFeedback, right: AnchorRegionFeedback) {
  return left.feedback_id === right.feedback_id
    && left.anchor_slide_id === right.anchor_slide_id
    && left.anchor_artifact_ref === right.anchor_artifact_ref
    && sameRegion(left.normalized_region, right.normalized_region)
    && left.comment === right.comment
    && left.order === right.order
    && left.visual_source_version === right.visual_source_version
    && left.revision === right.revision
    && left.created_at === right.created_at
    && left.created_by === right.created_by;
}

export function sameAnchorFeedbackBatchImmutableAuthority(
  left: AnchorFeedbackBatch,
  right: AnchorFeedbackBatch,
) {
  return left.batch_id === right.batch_id
    && left.project_id === right.project_id
    && left.review_session_id === right.review_session_id
    && left.visual_contract_ref === right.visual_contract_ref
    && left.deck_design_system_ref === right.deck_design_system_ref
    && left.anchor_slide_set_ref === right.anchor_slide_set_ref
    && left.items.length === right.items.length
    && left.items.every((item, index) => sameFeedback(item, right.items[index]))
    && left.source_version === right.source_version
    && left.revision === right.revision
    && left.persistence_status === right.persistence_status
    && left.immutable_after_submit === right.immutable_after_submit
    && left.submitted_at === right.submitted_at
    && left.submitted_by === right.submitted_by;
}

function isHostNotificationStatus(value: unknown): value is AnchorFeedbackBatch["host_notification_status"] {
  return value === "not-requested" || value === "pending" || value === "sent" || value === "failed" || value === "unavailable";
}

function isAiReceiptStatus(value: unknown): value is AnchorFeedbackBatch["ai_receipt_status"] {
  return value === "pending" || value === "received" || value === "rejected" || value === "unverified";
}

export function validateAnchorFeedbackBatch(
  value: unknown,
  data: VisualReviewPageViewModel,
  expectedItems?: ReadonlyArray<AnchorRegionFeedback>,
  expectedRevision?: number,
): AnchorFeedbackBatch | null {
  const cloned = clonePlainData(value);
  if (!hasExactDataFields(cloned, batchFields)) return null;
  const batchRevision = cloned.revision;
  const submittedAtInstant = parseIsoInstantMicros(cloned.submitted_at);
  const slideIds = new Set(data.review.anchors.map((anchor) => anchor.slide_id));
  if (
    !isNonEmptyText(cloned.batch_id)
    || cloned.project_id !== data.review.project_id
    || cloned.review_session_id !== data.review.review_session_id
    || cloned.visual_contract_ref !== data.review.visual_contract_ref
    || cloned.deck_design_system_ref !== data.review.deck_design_system_ref
    || cloned.anchor_slide_set_ref !== data.review.anchor_slide_set_ref
    || cloned.source_version !== data.review.source_version
    || !isRevision(batchRevision)
    || !isRevision(data.snapshotRevision)
    || batchRevision > data.snapshotRevision
    || (expectedRevision !== undefined && (!isRevision(expectedRevision) || batchRevision !== expectedRevision))
    || cloned.persistence_status !== "saved"
    || !isHostNotificationStatus(cloned.host_notification_status)
    || !isAiReceiptStatus(cloned.ai_receipt_status)
    || cloned.immutable_after_submit !== true
    || submittedAtInstant === null
    || cloned.submitted_by !== "user"
    || !Array.isArray(cloned.items)
    || cloned.items.length === 0
    || (expectedItems && cloned.items.length !== expectedItems.length)
  ) return null;

  const ids = new Set<string>();
  const items: AnchorRegionFeedback[] = [];
  for (let index = 0; index < cloned.items.length; index += 1) {
    const raw = cloned.items[index];
    if (!hasExactDataFields(raw, feedbackFields)) return null;
    if (
      !isNonEmptyText(raw.feedback_id)
      || ids.has(raw.feedback_id)
      || !slideIds.has(String(raw.anchor_slide_id))
      || raw.anchor_artifact_ref !== data.review.anchor_slide_set_ref
      || !isValidNormalizedRegion(raw.normalized_region)
      || !isNonEmptyText(raw.comment)
      || raw.comment !== raw.comment.trim()
      || raw.order !== index + 1
      || raw.visual_source_version !== data.review.source_version
      || raw.revision !== batchRevision
      || !isIsoInstant(raw.created_at)
      || parseIsoInstantMicros(raw.created_at)! > submittedAtInstant
      || raw.created_by !== "user"
    ) return null;
    ids.add(raw.feedback_id);
    const item: AnchorRegionFeedback = {
      feedback_id: raw.feedback_id,
      anchor_slide_id: raw.anchor_slide_id as string,
      anchor_artifact_ref: raw.anchor_artifact_ref as string,
      normalized_region: { ...raw.normalized_region },
      comment: raw.comment,
      order: raw.order as number,
      visual_source_version: raw.visual_source_version as string,
      revision: raw.revision as number,
      created_at: raw.created_at as string,
      created_by: "user",
    };
    if (expectedItems && !sameFeedback(item, expectedItems[index])) return null;
    items.push(item);
  }
  return {
    batch_id: cloned.batch_id,
    project_id: cloned.project_id as string,
    review_session_id: cloned.review_session_id as string,
    visual_contract_ref: cloned.visual_contract_ref as string,
    deck_design_system_ref: cloned.deck_design_system_ref as string,
    anchor_slide_set_ref: cloned.anchor_slide_set_ref as string,
    items,
    source_version: cloned.source_version as string,
    revision: batchRevision,
    persistence_status: "saved",
    host_notification_status: cloned.host_notification_status,
    ai_receipt_status: cloned.ai_receipt_status,
    immutable_after_submit: true,
    submitted_at: cloned.submitted_at as string,
    submitted_by: "user",
  };
}

export function validateInitialAnchorFeedbackBatch(
  value: unknown,
  data: VisualReviewPageViewModel,
  facts: VisualReceiptFacts,
): AnchorFeedbackBatch | null {
  const batch = validateAnchorFeedbackBatch(value, data);
  return batch
    && batch.host_notification_status === facts.hostNotificationStatus
    && batch.ai_receipt_status === facts.aiReceiptStatus
    ? batch
    : null;
}

export function validateAnchorFeedbackToolResult(
  value: unknown,
  data: VisualReviewPageViewModel,
  expectedItems: ReadonlyArray<AnchorRegionFeedback>,
  expectedRevision: number,
): ValidatedAnchorBatchResult | null {
  const cloned = clonePlainData(value);
  if (!isRevision(expectedRevision) || !hasExactDataFields(cloned, ["batch_ref", "batch", "snapshot"])) return null;
  if (!isArtifactReference(cloned.batch_ref, "visual-anchor-feedback-batch")) return null;
  const batch = validateAnchorFeedbackBatch(cloned.batch, data, expectedItems, expectedRevision);
  if (!batch || !hasExactDataFields(cloned.snapshot, ["revision"])) return null;
  const nextRevision = cloned.snapshot.revision;
  const receiptFacts = deriveVisualReceiptFacts(batch);
  if (
    !receiptFacts
    || receiptFacts.aiReceiptStatus !== "unverified"
    || !isRevision(nextRevision)
    || nextRevision !== expectedRevision + (receiptFacts.hostNotificationStatus === "sent" ? 2 : 1)
  ) return null;
  return {
    batchRef: cloned.batch_ref as string,
    batch: {
      batch_id: batch.batch_id,
      project_id: batch.project_id,
      review_session_id: batch.review_session_id,
      visual_contract_ref: batch.visual_contract_ref,
      deck_design_system_ref: batch.deck_design_system_ref,
      anchor_slide_set_ref: batch.anchor_slide_set_ref,
      items: batch.items.map((item) => ({
        feedback_id: item.feedback_id,
        anchor_slide_id: item.anchor_slide_id,
        anchor_artifact_ref: item.anchor_artifact_ref,
        normalized_region: { ...item.normalized_region },
        comment: item.comment,
        order: item.order,
        visual_source_version: item.visual_source_version,
        revision: item.revision,
        created_at: item.created_at,
        created_by: item.created_by,
      })),
      source_version: batch.source_version,
      revision: batch.revision,
      persistence_status: "saved",
      host_notification_status: receiptFacts.hostNotificationStatus,
      ai_receipt_status: receiptFacts.aiReceiptStatus,
      immutable_after_submit: true,
      submitted_at: batch.submitted_at,
      submitted_by: batch.submitted_by,
    },
    revision: nextRevision,
  };
}
