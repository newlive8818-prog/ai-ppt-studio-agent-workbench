import { isIsoInstant } from "../lib/iso-instant";
import { clonePlainData } from "../lib/plain-data";
import type { ContentReviewSurfaceData } from "../types/content-review";
import type { NormalizedRegion } from "../types/visual-review";
import type { VisualReviewPageViewModel } from "../visual-review/visual-review-page-view-model";
import { isValidNormalizedRegion } from "../visual-review/normalized-region";
import {
  DESIGN_SYSTEM_FIELD_ORDER,
  REVIEWABLE_SLIDE_FIELD_KEYS,
} from "../visual-review/visual-contract-field-contract";

export { clonePlainData } from "../lib/plain-data";

export const REVIEW_DRAFT_MAX_RAW_BYTES = 256 * 1024;

export interface ReviewDraftStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

interface ReviewDraftContextBase {
  projectId: string;
  reviewSessionId: string;
  sourceVersion: string;
  sourceRevision: number;
}

export interface ContentReviewDraftContext extends ReviewDraftContextBase {
  reviewType: "content";
  lineage: { readingBlueprintRef: string };
  slideIds: string[];
}

export interface VisualReviewDraftContext extends ReviewDraftContextBase {
  reviewType: "visual";
  lineage: {
    visualContractRef: string;
    anchorSlideSetRef: string;
    deckDesignSystemRef: string;
  };
  anchorSlideIds: string[];
  visualContractFields: Record<string, string[]>;
  deckDesignSystemFields: string[];
}

export type ReviewDraftContext = ContentReviewDraftContext | VisualReviewDraftContext;

export interface LogicalReviewScroll {
  object_id: string;
  offset: number;
}

export interface ContentReviewPageDraft {
  slide_id: string;
  decision: "" | "approved" | "modify" | "evidence" | "merge-or-delete";
  comment: string;
}

export interface ContentReviewDraftUi {
  view: "document";
  current_slide_id: string | null;
  page_drafts: ContentReviewPageDraft[];
  logical_scroll: LogicalReviewScroll | null;
}

export interface AnchorFeedbackDraftState {
  feedback_id: string;
  anchor_slide_id: string;
  normalized_region: NormalizedRegion;
  comment: string;
  created_at: string;
}

export interface AnchorFeedbackComposerState {
  anchor_slide_id: string;
  candidate_region: NormalizedRegion | null;
  editing_feedback_id: string;
  comment: string;
}

export interface ContractMarkDraftState {
  mark_id: string;
  target_type: "contract-field" | "text-range";
  slide_id: string;
  deck_section_id: string;
  target_key: string;
  selected_text: string;
  context_before: string;
  context_after: string;
  comment: string;
  created_at: string;
}

export interface ContractMarkComposerState {
  editing_mark_id: string;
  target_type: "contract-field" | "text-range";
  slide_id: string;
  deck_section_id: string;
  target_key: string;
  selected_text: string;
  context_before: string;
  context_after: string;
  comment: string;
}

export interface VisualReviewDraftUi {
  view: "anchors" | "contract";
  current_anchor_slide_id: string | null;
  anchor_feedback_drafts: AnchorFeedbackDraftState[];
  anchor_feedback_composer: AnchorFeedbackComposerState | null;
  contract_mark_drafts: ContractMarkDraftState[];
  contract_mark_composer: ContractMarkComposerState | null;
  anchor_logical_scroll: LogicalReviewScroll | null;
  contract_logical_scroll: LogicalReviewScroll | null;
}

export type ContentReviewDraftUpdate =
  | { type: "upsert-page-draft"; draft: ContentReviewPageDraft }
  | { type: "clear-page-draft"; slideId: string }
  | { type: "clear-content-batch" }
  | { type: "set-content-logical-position"; slideId: string; offset: number };

export type VisualReviewDraftUpdate =
  | {
      type: "replace-anchor-slice";
      drafts: AnchorFeedbackDraftState[];
      composer: AnchorFeedbackComposerState | null;
    }
  | { type: "clear-anchor-slice" }
  | {
      type: "replace-contract-slice";
      drafts: ContractMarkDraftState[];
      composer: ContractMarkComposerState | null;
    }
  | { type: "clear-contract-slice" }
  | { type: "set-visual-view"; view: "anchors" | "contract" }
  | { type: "set-current-anchor-slide"; slideId: string | null }
  | { type: "set-anchor-logical-scroll"; scroll: LogicalReviewScroll | null }
  | { type: "set-contract-logical-scroll"; scroll: LogicalReviewScroll | null };

export type ReviewDraftUpdate = ContentReviewDraftUpdate | VisualReviewDraftUpdate;

interface ReviewDraftEnvelopeBase {
  schema_version: 1;
  project_id: string;
  review_session_id: string;
  source_version: string;
  source_revision: number;
  updated_at: string;
}

export interface ContentReviewDraftEnvelope extends ReviewDraftEnvelopeBase {
  review_type: "content";
  lineage: { reading_blueprint_ref: string };
  ui: ContentReviewDraftUi;
}

export interface VisualReviewDraftEnvelope extends ReviewDraftEnvelopeBase {
  review_type: "visual";
  lineage: {
    visual_contract_ref: string;
    anchor_slide_set_ref: string;
    deck_design_system_ref: string;
  };
  ui: VisualReviewDraftUi;
}

export type ReviewDraftEnvelope = ContentReviewDraftEnvelope | VisualReviewDraftEnvelope;

export type PlainRecord = Record<string, unknown>;

const envelopeFields = [
  "schema_version", "project_id", "review_type", "review_session_id", "source_version",
  "source_revision", "lineage", "updated_at", "ui",
] as const;
const contentLineageFields = ["reading_blueprint_ref"] as const;
const visualLineageFields = [
  "visual_contract_ref", "anchor_slide_set_ref", "deck_design_system_ref",
] as const;
const contentUiFields = ["view", "current_slide_id", "page_drafts", "logical_scroll"] as const;
const pageDraftFields = ["slide_id", "decision", "comment"] as const;
const logicalScrollFields = ["object_id", "offset"] as const;
const visualUiFields = [
  "view", "current_anchor_slide_id", "anchor_feedback_drafts", "anchor_feedback_composer",
  "contract_mark_drafts", "contract_mark_composer", "anchor_logical_scroll",
  "contract_logical_scroll",
] as const;
const anchorFeedbackFields = [
  "feedback_id", "anchor_slide_id", "normalized_region", "comment", "created_at",
] as const;
const anchorComposerFields = [
  "anchor_slide_id", "candidate_region", "editing_feedback_id", "comment",
] as const;
const contractMarkFields = [
  "mark_id", "target_type", "slide_id", "deck_section_id", "target_key", "selected_text",
  "context_before", "context_after", "comment", "created_at",
] as const;
const contractComposerFields = [
  "editing_mark_id", "target_type", "slide_id", "deck_section_id", "target_key",
  "selected_text", "context_before", "context_after", "comment",
] as const;
const contractEditingIdentityFields = [
  "target_type", "slide_id", "deck_section_id", "target_key", "selected_text",
  "context_before", "context_after",
] as const;
const normalizedRegionFields = ["x", "y", "width", "height"] as const;

function isPlainRecord(value: unknown): value is PlainRecord {
  return Boolean(value)
    && typeof value === "object"
    && !Array.isArray(value)
    && Object.getPrototypeOf(value) === Object.prototype;
}

export function hasExactDataFields(value: unknown, fields: readonly string[]): value is PlainRecord {
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

function isNonemptyText(value: unknown): value is string {
  return typeof value === "string" && Boolean(value) && value === value.trim();
}

function isCanonicalOptionalText(value: unknown): value is string {
  return typeof value === "string" && value === value.trim();
}

function isSourceRevision(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

function isExactNormalizedRegion(value: unknown): value is NormalizedRegion {
  return hasExactDataFields(value, normalizedRegionFields) && isValidNormalizedRegion(value);
}

function hasUniqueIds<T>(items: T[], id: (item: T) => string): boolean {
  const ids = items.map(id);
  return new Set(ids).size === ids.length;
}

function validateLogicalScroll(
  value: unknown,
  membership: ReadonlySet<string>,
): value is LogicalReviewScroll | null {
  if (value === null) return true;
  return hasExactDataFields(value, logicalScrollFields)
    && isNonemptyText(value.object_id)
    && membership.has(value.object_id)
    && typeof value.offset === "number"
    && Number.isSafeInteger(value.offset)
    && value.offset >= 0;
}

function validateContentUi(value: unknown, context: ContentReviewDraftContext): value is ContentReviewDraftUi {
  if (!hasExactDataFields(value, contentUiFields)
    || value.view !== "document"
    || (value.current_slide_id !== null
      && (!isNonemptyText(value.current_slide_id) || !context.slideIds.includes(value.current_slide_id)))
    || !Array.isArray(value.page_drafts)) return false;
  const pageDrafts = value.page_drafts;
  if (!pageDrafts.every((draft) => hasExactDataFields(draft, pageDraftFields)
    && isNonemptyText(draft.slide_id)
    && context.slideIds.includes(draft.slide_id)
    && ["", "approved", "modify", "evidence", "merge-or-delete"].includes(String(draft.decision))
    && typeof draft.comment === "string")) return false;
  return hasUniqueIds(pageDrafts, (draft) => draft.slide_id as string)
    && validateLogicalScroll(value.logical_scroll, new Set(context.slideIds));
}

function validContractTarget(value: PlainRecord, context: VisualReviewDraftContext): boolean {
  if (!isNonemptyText(value.target_key)) return false;
  if (isNonemptyText(value.slide_id) && value.deck_section_id === "") {
    const fields = Object.prototype.hasOwnProperty.call(context.visualContractFields, value.slide_id)
      ? context.visualContractFields[value.slide_id]
      : undefined;
    return Array.isArray(fields) && fields.includes(value.target_key);
  }
  return value.slide_id === ""
    && value.deck_section_id === "deck-design-system"
    && context.deckDesignSystemFields.includes(value.target_key);
}

function validContractSelection(value: PlainRecord): boolean {
  if (value.target_type === "contract-field") {
    return value.selected_text === "" && value.context_before === "" && value.context_after === "";
  }
  return value.target_type === "text-range"
    && isNonemptyText(value.selected_text)
    && isCanonicalOptionalText(value.context_before)
    && isCanonicalOptionalText(value.context_after);
}

function validateVisualUi(value: unknown, context: VisualReviewDraftContext): value is VisualReviewDraftUi {
  if (!hasExactDataFields(value, visualUiFields)
    || (value.view !== "anchors" && value.view !== "contract")
    || (value.current_anchor_slide_id !== null
      && (!isNonemptyText(value.current_anchor_slide_id)
        || !context.anchorSlideIds.includes(value.current_anchor_slide_id)))
    || !Array.isArray(value.anchor_feedback_drafts)
    || !Array.isArray(value.contract_mark_drafts)) return false;

  const feedback = value.anchor_feedback_drafts;
  if (!feedback.every((draft) => hasExactDataFields(draft, anchorFeedbackFields)
    && isNonemptyText(draft.feedback_id)
    && isNonemptyText(draft.anchor_slide_id)
    && context.anchorSlideIds.includes(draft.anchor_slide_id)
    && isExactNormalizedRegion(draft.normalized_region)
    && isNonemptyText(draft.comment)
    && isIsoInstant(draft.created_at))
    || !hasUniqueIds(feedback, (draft) => draft.feedback_id as string)) return false;

  const marks = value.contract_mark_drafts;
  if (!marks.every((mark) => hasExactDataFields(mark, contractMarkFields)
    && isNonemptyText(mark.mark_id)
    && (mark.target_type === "contract-field" || mark.target_type === "text-range")
    && typeof mark.slide_id === "string"
    && typeof mark.deck_section_id === "string"
    && validContractTarget(mark, context)
    && validContractSelection(mark)
    && isNonemptyText(mark.comment)
    && isIsoInstant(mark.created_at))
    || !hasUniqueIds(marks, (mark) => mark.mark_id as string)) return false;

  if (value.anchor_feedback_composer !== null) {
    const composer = value.anchor_feedback_composer;
    if (!hasExactDataFields(composer, anchorComposerFields)
      || !isNonemptyText(composer.anchor_slide_id)
      || !context.anchorSlideIds.includes(composer.anchor_slide_id)
      || !isExactNormalizedRegion(composer.candidate_region)
      || typeof composer.editing_feedback_id !== "string"
      || typeof composer.comment !== "string") return false;
    if (composer.editing_feedback_id) {
      const edited = feedback.find((draft) => draft.feedback_id === composer.editing_feedback_id);
      if (!edited || edited.anchor_slide_id !== composer.anchor_slide_id) return false;
    }
  }

  if (value.contract_mark_composer !== null) {
    const composer = value.contract_mark_composer;
    if (!hasExactDataFields(composer, contractComposerFields)
      || typeof composer.editing_mark_id !== "string"
      || (composer.target_type !== "contract-field" && composer.target_type !== "text-range")
      || typeof composer.slide_id !== "string"
      || typeof composer.deck_section_id !== "string"
      || !validContractTarget(composer, context)
      || !validContractSelection(composer)
      || typeof composer.comment !== "string") return false;
    if (composer.editing_mark_id) {
      const edited = marks.find((mark) => mark.mark_id === composer.editing_mark_id);
      if (!edited || contractEditingIdentityFields.some((field) => edited[field] !== composer[field])) {
        return false;
      }
    }
  }

  const contractLogicalObjects = new Set([
    ...Object.keys(context.visualContractFields),
    "deck-design-system",
  ]);
  return validateLogicalScroll(value.anchor_logical_scroll, new Set(context.anchorSlideIds))
    && validateLogicalScroll(value.contract_logical_scroll, contractLogicalObjects);
}

function utf8ByteLength(value: string): number {
  return new TextEncoder().encode(value).byteLength;
}

export function createReviewDraftContext(data: ContentReviewSurfaceData): ContentReviewDraftContext;
export function createReviewDraftContext(data: VisualReviewPageViewModel): VisualReviewDraftContext;
export function createReviewDraftContext(data: ContentReviewSurfaceData | VisualReviewPageViewModel): ReviewDraftContext {
  const { review } = data;
  if (review.review_type === "content-full-deck") {
    return {
      reviewType: "content",
      projectId: review.project_id,
      reviewSessionId: review.review_session_id,
      sourceVersion: review.source_version,
      sourceRevision: review.revision,
      lineage: { readingBlueprintRef: review.reading_blueprint_ref },
      slideIds: review.slides.map((slide) => slide.slide_id),
    };
  }
  return {
    reviewType: "visual",
    projectId: review.project_id,
    reviewSessionId: review.review_session_id,
    sourceVersion: review.source_version,
    sourceRevision: review.revision,
    lineage: {
      visualContractRef: review.visual_contract_ref,
      anchorSlideSetRef: review.anchor_slide_set_ref,
      deckDesignSystemRef: review.deck_design_system_ref,
    },
    anchorSlideIds: review.anchors.map((anchor) => anchor.slide_id),
    visualContractFields: Object.fromEntries(review.slide_visual_contracts.map((contract) => (
      [contract.slide_id, [...REVIEWABLE_SLIDE_FIELD_KEYS]]
    ))),
    deckDesignSystemFields: [...DESIGN_SYSTEM_FIELD_ORDER],
  };
}

export function reviewDraftStorageKey(context: ReviewDraftContext): string {
  return [
    "ai-ppt-review-draft",
    "v1",
    encodeURIComponent(context.projectId),
    context.reviewType,
    encodeURIComponent(context.reviewSessionId),
    encodeURIComponent(context.sourceVersion),
    String(context.sourceRevision),
  ].join(":");
}

export function reviewDraftPageIdentity(context: ReviewDraftContext): string {
  const lineage = context.reviewType === "content"
    ? [context.lineage.readingBlueprintRef]
    : [
        context.lineage.visualContractRef,
        context.lineage.anchorSlideSetRef,
        context.lineage.deckDesignSystemRef,
      ];
  return `${reviewDraftStorageKey(context)}:lineage:${lineage.map(encodeURIComponent).join(":")}`;
}

export function createReviewDraftEnvelope(
  context: ContentReviewDraftContext,
  ui: ContentReviewDraftUi,
  updatedAt: string,
): ContentReviewDraftEnvelope;
export function createReviewDraftEnvelope(
  context: VisualReviewDraftContext,
  ui: VisualReviewDraftUi,
  updatedAt: string,
): VisualReviewDraftEnvelope;
export function createReviewDraftEnvelope(
  context: ReviewDraftContext,
  ui: ContentReviewDraftUi | VisualReviewDraftUi,
  updatedAt: string,
): ReviewDraftEnvelope {
  const clonedUi = clonePlainData(ui) as ContentReviewDraftUi | VisualReviewDraftUi;
  const base = {
    schema_version: 1 as const,
    project_id: context.projectId,
    review_session_id: context.reviewSessionId,
    source_version: context.sourceVersion,
    source_revision: context.sourceRevision,
    updated_at: updatedAt,
  };
  return context.reviewType === "content"
    ? {
        ...base,
        review_type: "content",
        lineage: { reading_blueprint_ref: context.lineage.readingBlueprintRef },
        ui: clonedUi as ContentReviewDraftUi,
      }
    : {
        ...base,
        review_type: "visual",
        lineage: {
          visual_contract_ref: context.lineage.visualContractRef,
          anchor_slide_set_ref: context.lineage.anchorSlideSetRef,
          deck_design_system_ref: context.lineage.deckDesignSystemRef,
        },
        ui: clonedUi as VisualReviewDraftUi,
      };
}

export function validateReviewDraftEnvelope(
  value: unknown,
  context: ContentReviewDraftContext,
): ContentReviewDraftEnvelope | null;
export function validateReviewDraftEnvelope(
  value: unknown,
  context: VisualReviewDraftContext,
): VisualReviewDraftEnvelope | null;
export function validateReviewDraftEnvelope(
  value: unknown,
  context: ReviewDraftContext,
): ReviewDraftEnvelope | null {
  const cloned = clonePlainData(value);
  if (!hasExactDataFields(cloned, envelopeFields)
    || cloned.schema_version !== 1
    || cloned.project_id !== context.projectId
    || cloned.review_type !== context.reviewType
    || cloned.review_session_id !== context.reviewSessionId
    || cloned.source_version !== context.sourceVersion
    || cloned.source_revision !== context.sourceRevision
    || !isSourceRevision(cloned.source_revision)
    || !isIsoInstant(cloned.updated_at)) return null;

  if (context.reviewType === "content") {
    if (!hasExactDataFields(cloned.lineage, contentLineageFields)
      || cloned.lineage.reading_blueprint_ref !== context.lineage.readingBlueprintRef
      || !validateContentUi(cloned.ui, context)) return null;
    return cloned as unknown as ContentReviewDraftEnvelope;
  }
  if (!hasExactDataFields(cloned.lineage, visualLineageFields)
    || cloned.lineage.visual_contract_ref !== context.lineage.visualContractRef
    || cloned.lineage.anchor_slide_set_ref !== context.lineage.anchorSlideSetRef
    || cloned.lineage.deck_design_system_ref !== context.lineage.deckDesignSystemRef
    || !validateVisualUi(cloned.ui, context)) return null;
  return cloned as unknown as VisualReviewDraftEnvelope;
}

const updateValidationInstant = "2000-01-01T00:00:00Z";

function validatedContentUpdate(
  context: ContentReviewDraftContext,
  ui: ContentReviewDraftUi,
): ContentReviewDraftUi | null {
  return validateReviewDraftEnvelope(
    createReviewDraftEnvelope(context, ui, updateValidationInstant),
    context,
  )?.ui ?? null;
}

function validatedVisualUpdate(
  context: VisualReviewDraftContext,
  ui: VisualReviewDraftUi,
): VisualReviewDraftUi | null {
  return validateReviewDraftEnvelope(
    createReviewDraftEnvelope(context, ui, updateValidationInstant),
    context,
  )?.ui ?? null;
}

export function applyReviewDraftUpdate(
  context: ContentReviewDraftContext,
  ui: ContentReviewDraftUi,
  update: ContentReviewDraftUpdate,
): ContentReviewDraftUi | null;
export function applyReviewDraftUpdate(
  context: VisualReviewDraftContext,
  ui: VisualReviewDraftUi,
  update: VisualReviewDraftUpdate,
): VisualReviewDraftUi | null;
export function applyReviewDraftUpdate(
  context: ReviewDraftContext,
  ui: ContentReviewDraftUi | VisualReviewDraftUi,
  update: ReviewDraftUpdate,
): ContentReviewDraftUi | VisualReviewDraftUi | null {
  if (context.reviewType === "content") {
    const current = ui as ContentReviewDraftUi;
    const action = update as ContentReviewDraftUpdate;
    if (action.type === "upsert-page-draft") {
      const existing = current.page_drafts.some((draft) => draft.slide_id === action.draft.slide_id);
      return validatedContentUpdate(context, {
        ...current,
        page_drafts: existing
          ? current.page_drafts.map((draft) => (
              draft.slide_id === action.draft.slide_id ? action.draft : draft
            ))
          : [...current.page_drafts, action.draft],
      });
    }
    if (action.type === "clear-page-draft") {
      if (!context.slideIds.includes(action.slideId)) return null;
      return validatedContentUpdate(context, {
        ...current,
        page_drafts: current.page_drafts.filter((draft) => draft.slide_id !== action.slideId),
      });
    }
    if (action.type === "clear-content-batch") {
      return validatedContentUpdate(context, { ...current, page_drafts: [] });
    }
    if (action.type === "set-content-logical-position") {
      return validatedContentUpdate(context, {
        ...current,
        current_slide_id: action.slideId,
        logical_scroll: { object_id: action.slideId, offset: action.offset },
      });
    }
    return null;
  }

  const current = ui as VisualReviewDraftUi;
  const action = update as VisualReviewDraftUpdate;
  if (action.type === "replace-anchor-slice") {
    return validatedVisualUpdate(context, {
      ...current,
      anchor_feedback_drafts: action.drafts,
      anchor_feedback_composer: action.composer,
    });
  }
  if (action.type === "clear-anchor-slice") {
    return validatedVisualUpdate(context, {
      ...current,
      anchor_feedback_drafts: [],
      anchor_feedback_composer: null,
    });
  }
  if (action.type === "replace-contract-slice") {
    return validatedVisualUpdate(context, {
      ...current,
      contract_mark_drafts: action.drafts,
      contract_mark_composer: action.composer,
    });
  }
  if (action.type === "clear-contract-slice") {
    return validatedVisualUpdate(context, {
      ...current,
      contract_mark_drafts: [],
      contract_mark_composer: null,
    });
  }
  if (action.type === "set-visual-view") {
    return validatedVisualUpdate(context, { ...current, view: action.view });
  }
  if (action.type === "set-current-anchor-slide") {
    return validatedVisualUpdate(context, { ...current, current_anchor_slide_id: action.slideId });
  }
  if (action.type === "set-anchor-logical-scroll") {
    return validatedVisualUpdate(context, { ...current, anchor_logical_scroll: action.scroll });
  }
  if (action.type === "set-contract-logical-scroll") {
    return validatedVisualUpdate(context, { ...current, contract_logical_scroll: action.scroll });
  }
  return null;
}

export function isReviewDraftSliceClear(update: ReviewDraftUpdate): boolean {
  return update.type === "clear-page-draft"
    || update.type === "clear-content-batch"
    || update.type === "clear-anchor-slice"
    || update.type === "clear-contract-slice";
}

export function loadReviewDraft(
  storage: ReviewDraftStorage,
  context: ContentReviewDraftContext,
): ContentReviewDraftEnvelope | null;
export function loadReviewDraft(
  storage: ReviewDraftStorage,
  context: VisualReviewDraftContext,
): VisualReviewDraftEnvelope | null;
export function loadReviewDraft(
  storage: ReviewDraftStorage,
  context: ReviewDraftContext,
): ReviewDraftEnvelope | null {
  let raw: string | null;
  try {
    raw = storage.getItem(reviewDraftStorageKey(context));
  } catch {
    return null;
  }
  if (raw === null || utf8ByteLength(raw) > REVIEW_DRAFT_MAX_RAW_BYTES) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    return context.reviewType === "content"
      ? validateReviewDraftEnvelope(parsed, context)
      : validateReviewDraftEnvelope(parsed, context);
  } catch {
    return null;
  }
}

export function saveReviewDraft(
  storage: ReviewDraftStorage,
  context: ContentReviewDraftContext,
  ui: ContentReviewDraftUi,
  updatedAt: string,
): boolean;
export function saveReviewDraft(
  storage: ReviewDraftStorage,
  context: VisualReviewDraftContext,
  ui: VisualReviewDraftUi,
  updatedAt: string,
): boolean;
export function saveReviewDraft(
  storage: ReviewDraftStorage,
  context: ReviewDraftContext,
  ui: ContentReviewDraftUi | VisualReviewDraftUi,
  updatedAt: string,
): boolean {
  const envelope = context.reviewType === "content"
    ? createReviewDraftEnvelope(context, ui as ContentReviewDraftUi, updatedAt)
    : createReviewDraftEnvelope(context, ui as VisualReviewDraftUi, updatedAt);
  const validated = context.reviewType === "content"
    ? validateReviewDraftEnvelope(envelope, context)
    : validateReviewDraftEnvelope(envelope, context);
  if (!validated) return false;
  try {
    const raw = JSON.stringify(validated);
    if (utf8ByteLength(raw) > REVIEW_DRAFT_MAX_RAW_BYTES) return false;
    storage.setItem(reviewDraftStorageKey(context), raw);
    return true;
  } catch {
    return false;
  }
}

export function discardReviewDraft(storage: ReviewDraftStorage, context: ReviewDraftContext): boolean {
  try {
    storage.removeItem(reviewDraftStorageKey(context));
    return true;
  } catch {
    return false;
  }
}
