import type {
  VisualContractReviewMark,
  VisualContractReviewMarkSet,
} from "../types/visual-review";
import type { VisualReviewPageViewModel } from "./visual-review-page-view-model";
import { isArtifactReference } from "../lib/artifact-reference";
import { isIsoInstant, parseIsoInstantMicros } from "../lib/iso-instant";
import {
  deriveVisualReceiptFacts,
  type VisualReceiptFacts,
} from "./visual-receipt-facts";

export interface ValidatedVisualContractMarkResult {
  markSetRef: string;
  markSet: VisualContractReviewMarkSet;
  revision: number;
}

export interface ValidatedInitialVisualContractMarkSet {
  markSet: VisualContractReviewMarkSet | null;
}

const resultFields = ["mark_set_ref", "mark_set", "snapshot"] as const;
const snapshotFields = ["revision"] as const;
const markSetFields = [
  "mark_set_id", "project_id", "review_session_id", "visual_contract_ref", "source_version",
  "revision", "marks", "persistence_status", "host_notification_status", "ai_receipt_status", "saved_at",
] as const;
const markFields = [
  "mark_id", "target_type", "slide_id", "deck_section_id", "target_key", "selected_text",
  "context_before", "context_after", "comment", "visual_contract_ref", "source_version",
  "revision", "created_at", "created_by",
] as const;

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value)
    && typeof value === "object"
    && !Array.isArray(value)
    && Object.getPrototypeOf(value) === Object.prototype;
}

function isClosedRecord(value: unknown, fields: readonly string[]): value is Record<string, unknown> {
  if (!isPlainRecord(value)) return false;
  const fieldSet = new Set(fields);
  const keys = Reflect.ownKeys(value);
  if (keys.length !== fields.length) return false;
  for (const key of keys) {
    if (typeof key !== "string" || !fieldSet.has(key)) return false;
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    if (!descriptor || !("value" in descriptor) || !descriptor.enumerable) return false;
  }
  return true;
}

function isClosedArray(value: unknown): value is unknown[] {
  if (!Array.isArray(value) || Object.getPrototypeOf(value) !== Array.prototype) return false;
  const lengthDescriptor = Object.getOwnPropertyDescriptor(value, "length");
  if (!lengthDescriptor || !("value" in lengthDescriptor) || lengthDescriptor.enumerable) return false;
  const length = lengthDescriptor.value;
  if (typeof length !== "number" || !Number.isSafeInteger(length) || length < 0) return false;
  const keys = Reflect.ownKeys(value);
  if (keys.length !== length + 1) return false;
  const expectedKeys = new Set(["length", ...Array.from({ length }, (_, index) => String(index))]);
  for (const key of keys) {
    if (typeof key !== "string" || !expectedKeys.has(key)) return false;
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    if (!descriptor || !("value" in descriptor)) return false;
    if (key === "length" ? descriptor.enumerable : !descriptor.enumerable) return false;
  }
  return true;
}

function isRevision(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

function isNonEmptyText(value: unknown): value is string {
  return typeof value === "string" && Boolean(value.trim()) && value === value.trim();
}

function isOptionalText(value: unknown): value is string {
  return typeof value === "string" && (value === "" || value === value.trim());
}

function isHostNotificationStatus(value: unknown): value is VisualContractReviewMarkSet["host_notification_status"] {
  return value === "not-requested" || value === "pending" || value === "sent" || value === "failed" || value === "unavailable";
}

function isAiReceiptStatus(value: unknown): value is VisualContractReviewMarkSet["ai_receipt_status"] {
  return value === "pending" || value === "received" || value === "rejected" || value === "unverified";
}

type SlideVisualContract = VisualReviewPageViewModel["review"]["slide_visual_contracts"][number];

function currentSlideTargets(data: VisualReviewPageViewModel) {
  const targets = new Map<string, SlideVisualContract>();
  for (const slide of data.review.slide_visual_contracts) {
    if (!targets.has(slide.slide_id)) targets.set(slide.slide_id, slide);
  }
  return targets;
}

function hasCurrentTarget(
  mark: Record<string, unknown>,
  data: VisualReviewPageViewModel,
  slideTargets: ReadonlyMap<string, SlideVisualContract>,
) {
  const slideId = mark.slide_id as string;
  const deckSectionId = mark.deck_section_id as string;
  const targetKey = mark.target_key as string;
  if (Boolean(slideId) === Boolean(deckSectionId)) return false;
  if (slideId) {
    const slide = slideTargets.get(slideId);
    return Boolean(slide) && Object.prototype.hasOwnProperty.call(slide, targetKey);
  }
  return deckSectionId === "deck-design-system"
    && Object.prototype.hasOwnProperty.call(data.review.deck_design_system, targetKey);
}

function isValidMark(
  value: unknown,
  data: VisualReviewPageViewModel,
  maximumRevision: number,
  savedAt: string,
  slideTargets: ReadonlyMap<string, SlideVisualContract>,
): value is VisualContractReviewMark {
  if (!isClosedRecord(value, markFields)) return false;
  const createdAtInstant = parseIsoInstantMicros(value.created_at);
  const savedAtInstant = parseIsoInstantMicros(savedAt);
  if (
    !isNonEmptyText(value.mark_id)
    || (value.target_type !== "contract-field" && value.target_type !== "text-range")
    || !isOptionalText(value.slide_id)
    || !isOptionalText(value.deck_section_id)
    || !isNonEmptyText(value.target_key)
    || !isOptionalText(value.selected_text)
    || !isOptionalText(value.context_before)
    || !isOptionalText(value.context_after)
    || !isNonEmptyText(value.comment)
    || value.visual_contract_ref !== data.review.visual_contract_ref
    || value.source_version !== data.review.source_version
    || !isRevision(value.revision)
    || value.revision > maximumRevision
    || createdAtInstant === null
    || savedAtInstant === null
    || createdAtInstant > savedAtInstant
    || value.created_by !== "user"
    || !hasCurrentTarget(value, data, slideTargets)
  ) return false;
  return value.target_type !== "text-range" || Boolean(value.selected_text.trim());
}

function sameMark(left: VisualContractReviewMark, right: VisualContractReviewMark) {
  return markFields.every((field) => left[field] === right[field]);
}

export function sameVisualContractMarkSetImmutableAuthority(
  left: VisualContractReviewMarkSet,
  right: VisualContractReviewMarkSet,
) {
  return left.mark_set_id === right.mark_set_id
    && left.project_id === right.project_id
    && left.review_session_id === right.review_session_id
    && left.visual_contract_ref === right.visual_contract_ref
    && left.source_version === right.source_version
    && left.revision === right.revision
    && left.marks.length === right.marks.length
    && left.marks.every((mark, index) => sameMark(mark, right.marks[index]))
    && left.persistence_status === right.persistence_status
    && left.saved_at === right.saved_at;
}

function copyMark(mark: VisualContractReviewMark): VisualContractReviewMark {
  return {
    mark_id: mark.mark_id,
    target_type: mark.target_type,
    slide_id: mark.slide_id,
    deck_section_id: mark.deck_section_id,
    target_key: mark.target_key,
    selected_text: mark.selected_text,
    context_before: mark.context_before,
    context_after: mark.context_after,
    comment: mark.comment,
    visual_contract_ref: mark.visual_contract_ref,
    source_version: mark.source_version,
    revision: mark.revision,
    created_at: mark.created_at,
    created_by: mark.created_by,
  };
}

export function validateInitialVisualContractMarkSet(
  value: unknown,
  data: VisualReviewPageViewModel,
  facts: VisualReceiptFacts,
): ValidatedInitialVisualContractMarkSet | null {
  if (value === null) return { markSet: null };
  if (!isClosedRecord(value, markSetFields)) return null;
  const expectedHost = facts.hostNotificationStatus;
  const expectedAi = facts.aiReceiptStatus;
  if (
    !isNonEmptyText(value.mark_set_id)
    || value.project_id !== data.review.project_id
    || value.review_session_id !== data.review.review_session_id
    || value.visual_contract_ref !== data.review.visual_contract_ref
    || value.source_version !== data.review.source_version
    || !isRevision(value.revision)
    || value.revision > data.snapshotRevision
    || value.persistence_status !== "saved"
    || value.host_notification_status !== expectedHost
    || value.ai_receipt_status !== expectedAi
    || !isIsoInstant(value.saved_at)
    || !isClosedArray(value.marks)
    || value.marks.length === 0
  ) return null;

  const marks: VisualContractReviewMark[] = [];
  const ids = new Set<string>();
  const slideTargets = currentSlideTargets(data);
  for (const rawMark of value.marks) {
    if (
      !isValidMark(rawMark, data, value.revision as number, value.saved_at as string, slideTargets)
      || ids.has(rawMark.mark_id)
    ) return null;
    ids.add(rawMark.mark_id);
    marks.push(copyMark(rawMark));
  }
  return {
    markSet: {
      mark_set_id: value.mark_set_id as string,
      project_id: value.project_id as string,
      review_session_id: value.review_session_id as string,
      visual_contract_ref: value.visual_contract_ref as string,
      source_version: value.source_version as string,
      revision: value.revision as number,
      marks,
      persistence_status: "saved",
      host_notification_status: expectedHost,
      ai_receipt_status: expectedAi,
      saved_at: value.saved_at as string,
    },
  };
}

export function validateVisualContractMarkToolResult(
  value: unknown,
  data: VisualReviewPageViewModel,
  submittedMarks: ReadonlyArray<VisualContractReviewMark>,
  commandRevision: number,
): ValidatedVisualContractMarkResult | null {
  if (!isRevision(commandRevision) || !submittedMarks.length || !isClosedRecord(value, resultFields)) return null;
  if (!isArtifactReference(value.mark_set_ref, "visual-contract-review-mark-set")
    || !isClosedRecord(value.snapshot, snapshotFields)) return null;
  const nextRevision = value.snapshot.revision;
  if (!isRevision(nextRevision)) return null;
  if (!isClosedRecord(value.mark_set, markSetFields)) return null;
  const rawMarkSet = value.mark_set;
  const receiptFacts = deriveVisualReceiptFacts({
    host_notification_status: rawMarkSet.host_notification_status,
    ai_receipt_status: rawMarkSet.ai_receipt_status,
  });
  if (
    !isNonEmptyText(rawMarkSet.mark_set_id)
    || rawMarkSet.project_id !== data.review.project_id
    || rawMarkSet.review_session_id !== data.review.review_session_id
    || rawMarkSet.visual_contract_ref !== data.review.visual_contract_ref
    || rawMarkSet.source_version !== data.review.source_version
    || rawMarkSet.revision !== commandRevision
    || rawMarkSet.persistence_status !== "saved"
    || !isHostNotificationStatus(rawMarkSet.host_notification_status)
    || !isAiReceiptStatus(rawMarkSet.ai_receipt_status)
    || !receiptFacts
    || receiptFacts.aiReceiptStatus !== "unverified"
    || nextRevision !== commandRevision + (receiptFacts.hostNotificationStatus === "sent" ? 2 : 1)
    || !isIsoInstant(rawMarkSet.saved_at)
    || !isClosedArray(rawMarkSet.marks)
    || rawMarkSet.marks.length === 0
  ) return null;

  const savedAt = rawMarkSet.saved_at;
  const slideTargets = currentSlideTargets(data);
  const returnedById = new Map<string, VisualContractReviewMark>();
  for (const rawMark of rawMarkSet.marks) {
    if (!isValidMark(rawMark, data, commandRevision, savedAt, slideTargets) || returnedById.has(rawMark.mark_id)) return null;
    returnedById.set(rawMark.mark_id, rawMark);
  }

  const submittedIds = new Set<string>();
  for (const submitted of submittedMarks) {
    if (
      !isValidMark(submitted, data, commandRevision, savedAt, slideTargets)
      || submitted.revision !== commandRevision
      || submittedIds.has(submitted.mark_id)
    ) return null;
    submittedIds.add(submitted.mark_id);
    const returned = returnedById.get(submitted.mark_id);
    if (!returned || !sameMark(returned, submitted)) return null;
  }
  for (const [id, returned] of returnedById) {
    if (!submittedIds.has(id) && returned.revision >= commandRevision) return null;
  }

  const marks = [...returnedById.values()].map(copyMark);
  const markSet: VisualContractReviewMarkSet = {
    mark_set_id: rawMarkSet.mark_set_id as string,
    project_id: rawMarkSet.project_id as string,
    review_session_id: rawMarkSet.review_session_id as string,
    visual_contract_ref: rawMarkSet.visual_contract_ref as string,
    source_version: rawMarkSet.source_version as string,
    revision: rawMarkSet.revision as number,
    marks,
    persistence_status: rawMarkSet.persistence_status as "saved",
    host_notification_status: receiptFacts.hostNotificationStatus,
    ai_receipt_status: receiptFacts.aiReceiptStatus,
    saved_at: rawMarkSet.saved_at as string,
  };

  return {
    markSetRef: value.mark_set_ref as string,
    markSet,
    revision: nextRevision,
  };
}
