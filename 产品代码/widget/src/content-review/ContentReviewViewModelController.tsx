import { useEffect, useMemo, useRef, useState } from "react";

import { isArtifactReference } from "../lib/artifact-reference";
import { isIsoInstant } from "../lib/iso-instant";
import {
  clonePlainData,
  createReviewDraftContext,
  hasExactDataFields,
  reviewDraftPageIdentity,
  type ContentReviewDraftUi,
} from "../review-draft/reviewDraftStore";
import { useReviewDraft } from "../review-draft/useReviewDraft";
import type {
  ContentDecisionChoice,
  ContentPageDecision,
  ContentReviewSlide,
  ContentReviewSurfaceData,
} from "../types/content-review";
import type { HostBridge } from "../types/host";
import type {
  ContentReviewBatchState,
  ContentReviewPageViewModel,
  ContentReviewSlideViewModel,
} from "./content-review-page-view-model";
import { contentDecisionChoices } from "./PageDecisionControl";
import { ContentReviewViewModelSurface } from "./ContentReviewViewModelSurface";

export interface ContentReviewViewModelControllerProps {
  initialData: ContentReviewSurfaceData;
  initialViewModel: ContentReviewPageViewModel;
  bridge: HostBridge;
}

interface ControllerDraft {
  decision: ContentDecisionChoice | "";
  comment: string;
  saved: ContentPageDecision | null;
  dirty: boolean;
}

interface ValidatedContentReviewBatch {
  batch_id: string;
  project_id: string;
  review_session_id: string;
  source_version: string;
  reading_blueprint_ref: string;
  slide_ids: string[];
  decision_refs: string[];
  counts: Record<ContentDecisionChoice, number>;
  status: "submitted" | "withdrawn";
  immutable_after_submit: true;
  submitted_at: string;
  withdrawn_at: string;
  supersedes_ref: string;
}

interface ValidatedControllerInput {
  decisions: ContentPageDecision[];
  batch: ValidatedContentReviewBatch | null;
  batchState: ContentReviewBatchState;
  sessionIdentity: string;
}

const pageDecisionFields = [
  "page_decision_id", "project_id", "review_session_id", "source_version", "reading_blueprint_ref",
  "slide_id", "slide_order", "slide_title_snapshot", "decision", "comment", "status", "saved_at",
  "supersedes_decision_ref",
] as const;
const batchFields = [
  "batch_id", "project_id", "review_session_id", "source_version", "reading_blueprint_ref",
  "slide_ids", "decision_refs", "counts", "status", "immutable_after_submit", "submitted_at",
  "withdrawn_at", "supersedes_ref",
] as const;
const pageSaveResultFields = ["decision_ref", "decision", "snapshot"] as const;
const batchResultFields = ["batch_ref", "batch", "snapshot"] as const;
const snapshotFields = ["revision"] as const;
const decisionChoices = contentDecisionChoices.map(({ value }) => value);
const versionConflictCodes = new Set([
  "REVISION_CONFLICT",
  "REVIEW_SOURCE_STALE",
  "CONTENT_REVIEW_CONFLICT",
  "CONTENT_REVIEW_BATCH_STALE",
]);

function isVersionConflictCode(code: unknown): boolean {
  return typeof code === "string" && versionConflictCodes.has(code);
}

function nextRevision(value: unknown, currentRevision: number): number | null {
  const snapshot = clonePlainData(value);
  if (!hasExactDataFields(snapshot, snapshotFields)) return null;
  const candidate = snapshot.revision;
  return Number.isSafeInteger(currentRevision)
    && currentRevision >= 0
    && Number.isSafeInteger(candidate)
    && (candidate as number) > currentRevision
    ? candidate as number
    : null;
}

function validatedDecision(
  value: unknown,
  review: ContentReviewSurfaceData["review"],
  slide: ContentReviewSlide,
): ContentPageDecision | null {
  const cloned = clonePlainData(value);
  if (!hasExactDataFields(cloned, pageDecisionFields)) return null;
  if (!decisionChoices.includes(cloned.decision as ContentDecisionChoice)) return null;
  const decision = cloned.decision as ContentDecisionChoice;
  if (typeof cloned.comment !== "string") return null;
  const comment = cloned.comment.trim();
  if (
    (decision === "approved" ? cloned.comment !== "" : !comment || cloned.comment !== comment)
    || [...comment].length > 1200
  ) return null;
  if (
    typeof cloned.page_decision_id !== "string"
    || !cloned.page_decision_id.trim()
    || cloned.project_id !== review.project_id
    || cloned.review_session_id !== review.review_session_id
    || cloned.source_version !== review.source_version
    || cloned.reading_blueprint_ref !== review.reading_blueprint_ref
    || !isArtifactReference(cloned.reading_blueprint_ref, "reading-deck-blueprint")
    || cloned.slide_id !== slide.slide_id
    || cloned.slide_order !== slide.order
    || cloned.slide_title_snapshot !== slide.neutral_title
    || cloned.status !== "completed"
    || !isIsoInstant(cloned.saved_at)
    || typeof cloned.supersedes_decision_ref !== "string"
    || (cloned.supersedes_decision_ref !== ""
      && !isArtifactReference(cloned.supersedes_decision_ref, "content-page-decision"))
  ) return null;
  return {
    page_decision_id: cloned.page_decision_id.trim(),
    project_id: review.project_id,
    review_session_id: review.review_session_id,
    source_version: review.source_version,
    reading_blueprint_ref: review.reading_blueprint_ref,
    slide_id: slide.slide_id,
    slide_order: slide.order,
    slide_title_snapshot: slide.neutral_title,
    decision,
    comment,
    status: "completed",
    saved_at: cloned.saved_at,
    supersedes_decision_ref: cloned.supersedes_decision_ref,
  };
}

function validatedInitialDecisions(
  review: ContentReviewSurfaceData["review"],
): ContentPageDecision[] | null {
  const cloned = clonePlainData(review.decisions);
  if (!Array.isArray(cloned)) return null;
  const slides = new Map(review.slides.map((slide) => [slide.slide_id, slide]));
  const seen = new Set<string>();
  const decisions: ContentPageDecision[] = [];
  let previousOrder = 0;
  for (const value of cloned) {
    if (!hasExactDataFields(value, pageDecisionFields) || typeof value.slide_id !== "string") return null;
    const slide = slides.get(value.slide_id);
    if (!slide || seen.has(slide.slide_id)) return null;
    const decision = validatedDecision(value, review, slide);
    if (!decision || decision.slide_order <= previousOrder) return null;
    previousOrder = decision.slide_order;
    seen.add(decision.slide_id);
    decisions.push(decision);
  }
  return decisions;
}

function validatedBatch(
  value: unknown,
  review: ContentReviewSurfaceData["review"],
): ValidatedContentReviewBatch | null {
  const cloned = clonePlainData(value);
  if (!hasExactDataFields(cloned, batchFields)) return null;
  const status = cloned.status;
  if (status !== "submitted" && status !== "withdrawn") return null;
  for (const field of [
    "batch_id", "project_id", "review_session_id", "source_version", "reading_blueprint_ref", "submitted_at",
  ] as const) {
    if (typeof cloned[field] !== "string" || !(cloned[field] as string).trim()) return null;
  }
  if (
    !isIsoInstant(cloned.submitted_at)
    || !isArtifactReference(cloned.reading_blueprint_ref, "reading-deck-blueprint")
    || cloned.project_id !== review.project_id
    || cloned.review_session_id !== review.review_session_id
    || cloned.source_version !== review.source_version
    || cloned.reading_blueprint_ref !== review.reading_blueprint_ref
    || cloned.immutable_after_submit !== true
    || !Array.isArray(cloned.slide_ids)
    || !Array.isArray(cloned.decision_refs)
  ) return null;
  if (
    cloned.slide_ids.length !== review.slides.length
    || cloned.decision_refs.length !== review.slides.length
    || cloned.slide_ids.some((slideId, index) => slideId !== review.slides[index]?.slide_id)
    || cloned.decision_refs.some((reference) => !isArtifactReference(reference, "content-page-decision"))
    || new Set(cloned.decision_refs).size !== cloned.decision_refs.length
  ) return null;
  if (!hasExactDataFields(cloned.counts, decisionChoices)) return null;
  const counts = cloned.counts;
  if (
    decisionChoices.some((choice) => !Number.isInteger(counts[choice]) || (counts[choice] as number) < 0)
    || decisionChoices.reduce((total, choice) => total + (counts[choice] as number), 0)
      !== review.slides.length
    || typeof cloned.withdrawn_at !== "string"
    || typeof cloned.supersedes_ref !== "string"
    || (cloned.supersedes_ref !== ""
      && !isArtifactReference(cloned.supersedes_ref, "content-review-batch"))
    || (status === "submitted" && cloned.withdrawn_at !== "")
    || (status === "withdrawn" && (!isIsoInstant(cloned.withdrawn_at) || !cloned.supersedes_ref))
  ) return null;
  return {
    batch_id: cloned.batch_id as string,
    project_id: cloned.project_id as string,
    review_session_id: cloned.review_session_id as string,
    source_version: cloned.source_version as string,
    reading_blueprint_ref: cloned.reading_blueprint_ref as string,
    slide_ids: [...cloned.slide_ids] as string[],
    decision_refs: [...cloned.decision_refs] as string[],
    counts: {
      approved: counts.approved as number,
      modify: counts.modify as number,
      evidence: counts.evidence as number,
      "merge-or-delete": counts["merge-or-delete"] as number,
    },
    status,
    immutable_after_submit: true,
    submitted_at: cloned.submitted_at,
    withdrawn_at: cloned.withdrawn_at,
    supersedes_ref: cloned.supersedes_ref,
  };
}

function sameDecision(left: ContentPageDecision | null, right: ContentPageDecision | null): boolean {
  if (left === null || right === null) return left === right;
  return pageDecisionFields.every((field) => left[field] === right[field]);
}

function expectedSections(review: ContentReviewSurfaceData["review"]) {
  const sections: Array<{ sectionId: string; title: string; slideIds: string[] }> = [];
  for (const slide of review.slides) {
    const current = sections.at(-1);
    if (current?.sectionId === slide.section_id) {
      current.slideIds.push(slide.slide_id);
      continue;
    }
    sections.push({
      sectionId: slide.section_id,
      title: review.section_flow[sections.length] ?? slide.section_id,
      slideIds: [slide.slide_id],
    });
  }
  return sections;
}

function validateControllerInput(
  data: ContentReviewSurfaceData,
  viewModel: ContentReviewPageViewModel,
): ValidatedControllerInput | null {
  const { review } = data;
  if (
    typeof data.selectedProjectRoot !== "string"
    || !data.selectedProjectRoot
    || data.selectedProjectRoot !== data.selectedProjectRoot.trim()
    || !review.project_id
    || review.project_id !== review.project_id.trim()
    || !review.review_session_id
    || review.review_session_id !== review.review_session_id.trim()
    || !review.source_version
    || review.source_version !== review.source_version.trim()
    || !isArtifactReference(review.reading_blueprint_ref, "reading-deck-blueprint")
    || viewModel.projectId !== review.project_id
    || viewModel.reviewSessionId !== review.review_session_id
    || viewModel.sourceVersion !== review.source_version
    || viewModel.readingBlueprintRef !== review.reading_blueprint_ref
    || viewModel.revision !== review.revision
    || viewModel.authoritativeRevision !== review.authoritative_revision
    || data.snapshotRevision !== review.authoritative_revision
    || !Number.isSafeInteger(review.revision)
    || review.revision < 0
    || !Number.isSafeInteger(review.authoritative_revision)
    || review.authoritative_revision < review.revision
    || viewModel.slides.length !== review.slides.length
  ) return null;

  const slideIds = review.slides.map((slide) => slide.slide_id);
  if (
    new Set(slideIds).size !== slideIds.length
    || review.slides.some((slide, index) => (
      !slide.slide_id
      || slide.slide_id !== slide.slide_id.trim()
      || !Number.isSafeInteger(slide.order)
      || slide.order <= 0
      || (index > 0 && slide.order <= review.slides[index - 1].order)
      || !slide.section_id
      || slide.section_id !== slide.section_id.trim()
      || !slide.neutral_title
      || slide.neutral_title !== slide.neutral_title.trim()
    ))
  ) return null;

  const decisions = validatedInitialDecisions(review);
  if (decisions === null) return null;
  const decisionsBySlide = new Map(decisions.map((decision) => [decision.slide_id, decision]));
  for (let index = 0; index < review.slides.length; index += 1) {
    const slide = review.slides[index];
    const visible = viewModel.slides[index];
    const saved = decisionsBySlide.get(slide.slide_id) ?? null;
    if (
      !visible
      || visible.slideId !== slide.slide_id
      || visible.order !== slide.order
      || visible.sectionId !== slide.section_id
      || visible.neutralTitle !== slide.neutral_title
      || !sameDecision(visible.savedDecision, saved)
      || visible.localDraftState.dirty
      || visible.localDraftState.decision !== (saved?.decision ?? "")
      || visible.localDraftState.comment !== (saved?.comment ?? "")
    ) return null;
  }

  const sections = expectedSections(review);
  if (viewModel.sections.length !== sections.length) return null;
  for (let index = 0; index < sections.length; index += 1) {
    const expected = sections[index];
    const visible = viewModel.sections[index];
    if (
      !visible
      || visible.sectionId !== expected.sectionId
      || visible.title !== expected.title
      || visible.slideIds.length !== expected.slideIds.length
      || visible.slideIds.some((slideId, slideIndex) => slideId !== expected.slideIds[slideIndex])
    ) return null;
  }

  const batch = review.batch === null ? null : validatedBatch(review.batch, review);
  if (review.batch !== null && batch === null) return null;
  if (batch) {
    const counts = decisions.reduce<Record<ContentDecisionChoice, number>>((result, decision) => {
      result[decision.decision] += 1;
      return result;
    }, { approved: 0, modify: 0, evidence: 0, "merge-or-delete": 0 });
    if (
      decisions.length !== review.slides.length
      || decisionChoices.some((choice) => counts[choice] !== batch.counts[choice])
    ) return null;
  }
  const batchState: ContentReviewBatchState = batch?.status ?? "open";
  const writesExpected = batchState !== "submitted";
  if (
    viewModel.batchState !== batchState
    || viewModel.availableActions.savePageDecision !== writesExpected
    || viewModel.availableActions.submitReviewBatch !== writesExpected
  ) return null;

  const draftIdentity = reviewDraftPageIdentity(createReviewDraftContext(data));
  return {
    decisions,
    batch,
    batchState,
    sessionIdentity: `${draftIdentity}:root:${encodeURIComponent(data.selectedProjectRoot)}`,
  };
}

function initialDrafts(
  viewModel: ContentReviewPageViewModel,
  decisions: ContentPageDecision[],
  restored: ContentReviewDraftUi["page_drafts"],
  batchState: ContentReviewBatchState,
): Record<string, ControllerDraft> {
  const savedBySlide = new Map(decisions.map((decision) => [decision.slide_id, decision]));
  const recoveredBySlide = batchState === "submitted"
    ? new Map<string, ContentReviewDraftUi["page_drafts"][number]>()
    : new Map(restored.map((draft) => [draft.slide_id, draft]));
  return Object.fromEntries(viewModel.slides.map((slide) => {
    const saved = savedBySlide.get(slide.slideId) ?? null;
    const recovered = recoveredBySlide.get(slide.slideId);
    return [slide.slideId, {
      decision: recovered?.decision ?? saved?.decision ?? "",
      comment: recovered?.comment ?? saved?.comment ?? "",
      saved,
      dirty: Boolean(recovered),
    } satisfies ControllerDraft];
  }));
}

function reconcileAuthoritativeDrafts(
  current: Record<string, ControllerDraft>,
  slides: readonly ContentReviewSlideViewModel[],
  decisions: ContentPageDecision[],
  batchState: ContentReviewBatchState,
): Record<string, ControllerDraft> {
  const savedBySlide = new Map(decisions.map((decision) => [decision.slide_id, decision]));
  return Object.fromEntries(slides.map((slide) => {
    const saved = savedBySlide.get(slide.slideId) ?? null;
    const draft = current[slide.slideId];
    if (draft?.dirty && batchState !== "submitted") {
      return [slide.slideId, { ...draft, saved } satisfies ControllerDraft];
    }
    return [slide.slideId, {
      decision: saved?.decision ?? "",
      comment: saved?.comment ?? "",
      saved,
      dirty: false,
    } satisfies ControllerDraft];
  }));
}

function contentLogicalOrigin(): number {
  const header = document.querySelector<HTMLElement>(".content-review-vm-header");
  if (!header || window.getComputedStyle(header).position !== "sticky") return 0;
  return header.getBoundingClientRect().bottom;
}

function scrollToContentLogicalPosition(
  slideId: string,
  offset: number,
  behavior: ScrollBehavior,
) {
  const target = document.getElementById(`content-vm-${slideId}`);
  if (!target) return;
  const origin = contentLogicalOrigin();
  window.scrollTo({
    behavior,
    left: window.scrollX,
    top: window.scrollY + target.getBoundingClientRect().top - origin + offset,
  });
}

interface SessionControllerProps extends ContentReviewViewModelControllerProps {
  validated: ValidatedControllerInput;
}

function ContentReviewViewModelSessionController({
  initialData,
  initialViewModel,
  bridge,
  validated,
}: SessionControllerProps) {
  const reviewDraftContext = useMemo(() => createReviewDraftContext(initialData), [initialData]);
  const defaultReviewDraftUi = useMemo<ContentReviewDraftUi>(() => ({
    view: "document",
    current_slide_id: null,
    page_drafts: [],
    logical_scroll: null,
  }), []);
  const reviewDraft = useReviewDraft({ context: reviewDraftContext, initialUi: defaultReviewDraftUi });
  const [revision, setRevision] = useState(initialData.snapshotRevision);
  const revisionRef = useRef(initialData.snapshotRevision);
  const [drafts, setDrafts] = useState(() => initialDrafts(
    initialViewModel,
    validated.decisions,
    reviewDraft.ui.page_drafts,
    validated.batchState,
  ));
  const [batchState, setBatchState] = useState(validated.batchState);
  const [savingSlideId, setSavingSlideId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [pageMessage, setPageMessage] = useState("");
  const mutationRef = useRef<null | { kind: "page"; slideId: string } | { kind: "batch" }>(null);
  const mountedRef = useRef(true);
  const generationRef = useRef(0);
  const restoredLogicalPositionRef = useRef(false);
  const logicalPositionRef = useRef(reviewDraft.ui.logical_scroll);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      generationRef.current += 1;
    };
  }, []);

  useEffect(() => {
    if (initialData.snapshotRevision <= revisionRef.current) return;
    const interrupted = mutationRef.current;
    generationRef.current += 1;
    mutationRef.current = null;
    setSavingSlideId(null);
    setSubmitting(false);
    revisionRef.current = initialData.snapshotRevision;
    setRevision(initialData.snapshotRevision);
    setDrafts((current) => reconcileAuthoritativeDrafts(
      current,
      initialViewModel.slides,
      validated.decisions,
      validated.batchState,
    ));
    setBatchState(validated.batchState);
    if (interrupted?.kind === "page") {
      setPageMessage("版本已变化；草稿仍保留，请刷新后重试。");
    } else if (interrupted?.kind === "batch") {
      setPageMessage("当前版本已变化；所有本地输入仍保留，请刷新后重试。");
    }
  }, [initialData.snapshotRevision, initialViewModel.slides, validated]);

  useEffect(() => {
    if (restoredLogicalPositionRef.current) return;
    restoredLogicalPositionRef.current = true;
    const logicalScroll = reviewDraft.ui.logical_scroll;
    const slideId = logicalScroll?.object_id ?? reviewDraft.ui.current_slide_id;
    if (!slideId) return;
    scrollToContentLogicalPosition(slideId, logicalScroll?.offset ?? 0, "auto");
  }, [reviewDraft.ui.current_slide_id, reviewDraft.ui.logical_scroll]);

  const recordLogicalPosition = (slideId: string, offset: number) => {
    const roundedOffset = Number.isFinite(offset) ? Math.max(0, Math.round(offset)) : 0;
    const previous = logicalPositionRef.current;
    if (previous?.object_id === slideId && previous.offset === roundedOffset) return;
    if (reviewDraft.updateDraft({
      type: "set-content-logical-position",
      slideId,
      offset: roundedOffset,
    })) {
      logicalPositionRef.current = { object_id: slideId, offset: roundedOffset };
    }
  };

  useEffect(() => {
    let frameId: number | null = null;
    const captureLogicalPosition = () => {
      frameId = null;
      const elements = Array.from(document.querySelectorAll<HTMLElement>("[data-content-review-vm-slide]"));
      if (!elements.length) return;
      const origin = contentLogicalOrigin();
      let selected = elements[0];
      let selectedRect: DOMRect | null = null;
      for (const element of elements) {
        const rect = element.getBoundingClientRect();
        if (selectedRect === null) selectedRect = rect;
        if (rect.top <= origin) {
          selected = element;
          selectedRect = rect;
        }
      }
      const slideId = selected.id.startsWith("content-vm-")
        ? selected.id.slice("content-vm-".length)
        : "";
      if (!slideId) return;
      recordLogicalPosition(slideId, Math.max(0, origin - (selectedRect?.top ?? origin)));
    };
    const handleScroll = () => {
      if (frameId !== null) return;
      frameId = window.requestAnimationFrame(captureLogicalPosition);
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", handleScroll);
      if (frameId !== null) window.cancelAnimationFrame(frameId);
    };
  }, [reviewDraft.updateDraft]);

  const patchDraft = (slideId: string, update: Partial<ControllerDraft>) => {
    setDrafts((current) => ({
      ...current,
      [slideId]: { ...current[slideId], ...update },
    }));
  };

  const handleDecisionChange = (slideId: string, decision: ContentDecisionChoice) => {
    if (mutationRef.current || batchState === "submitted") return;
    const current = drafts[slideId];
    if (!current) return;
    const comment = decision === "approved" ? "" : current.comment;
    patchDraft(slideId, { decision, comment, dirty: true });
    reviewDraft.updateDraft({
      type: "upsert-page-draft",
      draft: { slide_id: slideId, decision, comment },
    });
    setPageMessage("");
  };

  const handleCommentChange = (slideId: string, comment: string) => {
    if (mutationRef.current || batchState === "submitted") return;
    const current = drafts[slideId];
    if (!current) return;
    patchDraft(slideId, { comment, dirty: true });
    reviewDraft.updateDraft({
      type: "upsert-page-draft",
      draft: { slide_id: slideId, decision: current.decision, comment },
    });
    setPageMessage("");
  };

  const savePageDecision = async (slideId: string): Promise<boolean> => {
    if (mutationRef.current || batchState === "submitted") return false;
    const slide = initialData.review.slides.find((candidate) => candidate.slide_id === slideId);
    const draft = drafts[slideId];
    if (!slide || !draft?.dirty || !draft.decision) return false;
    const commandComment = draft.decision === "approved" ? "" : draft.comment.trim();
    if ((draft.decision !== "approved" && !commandComment) || [...commandComment].length > 1200) return false;
    const commandDecision = draft.decision;
    const commandRevision = revisionRef.current;
    const commandGeneration = generationRef.current;
    const commandIsCurrent = () => mountedRef.current && generationRef.current === commandGeneration;
    mutationRef.current = { kind: "page", slideId };
    setSavingSlideId(slideId);
    setPageMessage("正在保存…");
    try {
      const rawResult = await bridge.callTool("save_content_page_decision", {
        projectRoot: initialData.selectedProjectRoot,
        expectedRevision: commandRevision,
        reviewSessionId: initialData.review.review_session_id,
        sourceVersion: initialData.review.source_version,
        slideId,
        decision: commandDecision,
        comment: commandComment,
      });
      if (!commandIsCurrent()) return false;
      if (revisionRef.current !== commandRevision) {
        setPageMessage("版本已变化；草稿仍保留，请刷新后重试。");
        return false;
      }
      const result = clonePlainData(rawResult);
      if (!hasExactDataFields(result, pageSaveResultFields)) {
        setPageMessage("Runtime 返回无效结果；草稿仍保留，可直接重试。");
        return false;
      }
      const saved = validatedDecision(result.decision, initialData.review, slide);
      const savedRevision = nextRevision(result.snapshot, commandRevision);
      if (
        !isArtifactReference(result.decision_ref, "content-page-decision")
        || !saved
        || saved.decision !== commandDecision
        || saved.comment !== commandComment
        || savedRevision === null
      ) {
        setPageMessage("Runtime 返回无效结果；草稿仍保留，可直接重试。");
        return false;
      }
      revisionRef.current = savedRevision;
      setRevision(savedRevision);
      patchDraft(slideId, {
        decision: saved.decision,
        comment: saved.comment,
        saved,
        dirty: false,
      });
      reviewDraft.updateDraft({ type: "clear-page-draft", slideId });
      setPageMessage("");
      return true;
    } catch (error) {
      if (!commandIsCurrent()) return false;
      const code = (error as Error & { code?: string }).code;
      setPageMessage(isVersionConflictCode(code)
        ? "版本已变化；草稿仍保留，请刷新后重试。"
        : "保存失败；草稿仍保留，可直接重试。");
      return false;
    } finally {
      if (commandIsCurrent()) {
        mutationRef.current = null;
        setSavingSlideId(null);
      }
    }
  };

  const completed = initialViewModel.slides.filter((slide) => {
    const draft = drafts[slide.slideId];
    return Boolean(draft?.saved) && !draft?.dirty;
  }).length;
  const unsaved = initialViewModel.slides.filter((slide) => drafts[slide.slideId]?.dirty).length;
  const total = initialViewModel.slides.length;
  const allCompleted = total > 0
    && completed === total
    && unsaved === 0
    && batchState !== "submitted";

  const submitReviewBatch = async () => {
    if (!allCompleted || mutationRef.current) return;
    const commandRevision = revisionRef.current;
    const commandGeneration = generationRef.current;
    const commandIsCurrent = () => mountedRef.current && generationRef.current === commandGeneration;
    mutationRef.current = { kind: "batch" };
    setSubmitting(true);
    setPageMessage("正在冻结本轮审核…");
    try {
      const rawResult = await bridge.callTool("submit_content_review_batch", {
        projectRoot: initialData.selectedProjectRoot,
        expectedRevision: commandRevision,
        reviewSessionId: initialData.review.review_session_id,
        sourceVersion: initialData.review.source_version,
      });
      if (!commandIsCurrent()) return;
      if (revisionRef.current !== commandRevision) {
        setPageMessage("当前版本已变化；所有本地输入仍保留，请刷新后重试。");
        return;
      }
      const result = clonePlainData(rawResult);
      if (!hasExactDataFields(result, batchResultFields)) {
        setPageMessage("Runtime 返回无效结果；本轮审核仍可提交，请重试。");
        return;
      }
      const batch = validatedBatch(result.batch, initialData.review);
      const batchRevision = nextRevision(result.snapshot, commandRevision);
      if (
        !isArtifactReference(result.batch_ref, "content-review-batch")
        || !batch
        || batch.status !== "submitted"
        || batchRevision === null
      ) {
        setPageMessage("Runtime 返回无效结果；本轮审核仍可提交，请重试。");
        return;
      }
      revisionRef.current = batchRevision;
      setRevision(batchRevision);
      setBatchState("submitted");
      setPageMessage("已提交，等待整套修改方案");
      reviewDraft.updateDraft({ type: "clear-content-batch" });
    } catch (error) {
      if (!commandIsCurrent()) return;
      const code = (error as Error & { code?: string }).code;
      setPageMessage(isVersionConflictCode(code)
        ? "当前版本已变化；所有本地输入仍保留，请刷新后重试。"
        : "本轮审核尚未提交；所有输入仍保留，可直接重试。");
    } finally {
      if (commandIsCurrent()) {
        mutationRef.current = null;
        setSubmitting(false);
      }
    }
  };

  const controlledViewModel = useMemo<ContentReviewPageViewModel>(() => ({
    ...initialViewModel,
    revision,
    authoritativeRevision: revision,
    progress: {
      completed,
      total,
      remaining: total - completed,
      unsaved,
    },
    slides: initialViewModel.slides.map((slide) => {
      const draft = drafts[slide.slideId];
      return {
        ...slide,
        savedDecision: draft?.saved ?? null,
        localDraftState: {
          decision: draft?.decision ?? "",
          comment: draft?.comment ?? "",
          dirty: draft?.dirty ?? false,
        },
      };
    }),
    batchState,
    availableActions: {
      savePageDecision: initialViewModel.availableActions.savePageDecision && batchState !== "submitted",
      submitReviewBatch: initialViewModel.availableActions.submitReviewBatch && batchState !== "submitted",
    },
  }), [batchState, completed, drafts, initialViewModel, revision, total, unsaved]);

  return (
    <ContentReviewViewModelSurface
      viewModel={controlledViewModel}
      bridge={bridge}
      projectRoot={initialData.selectedProjectRoot}
      savingSlideId={savingSlideId}
      submitting={submitting}
      pageMessage={pageMessage}
      onDecisionChange={handleDecisionChange}
      onCommentChange={handleCommentChange}
      onSavePageDecision={savePageDecision}
      onSubmitReviewBatch={submitReviewBatch}
    />
  );
}

export function ContentReviewViewModelController({
  initialData,
  initialViewModel,
  bridge,
}: ContentReviewViewModelControllerProps) {
  const validated = validateControllerInput(initialData, initialViewModel);
  if (!validated) {
    return (
      <main className="content-review-vm-recovery" role="alert">
        审核页面与写入会话不一致，请刷新/重新打开后重试。
      </main>
    );
  }
  return (
    <ContentReviewViewModelSessionController
      key={validated.sessionIdentity}
      initialData={initialData}
      initialViewModel={initialViewModel}
      bridge={bridge}
      validated={validated}
    />
  );
}
