import { useEffect, useMemo, useRef, useState } from "react";

import type { HostBridge } from "../types/host";
import type {
  ContentDecisionChoice,
  ContentPageDecision,
  LegacyContentReviewSlide,
  LegacyContentReviewSurfaceData,
} from "../types/content-review";
import { ContentMaterialView } from "./ContentMaterialView";
import { contentDecisionChoices, PageDecisionControl } from "./PageDecisionControl";
import {
  clonePlainData,
  createReviewDraftContext,
  hasExactDataFields,
  reviewDraftPageIdentity,
  type ContentReviewDraftUi,
} from "../review-draft/reviewDraftStore";
import { useReviewDraft } from "../review-draft/useReviewDraft";
import { isArtifactReference } from "../lib/artifact-reference";
import { isIsoInstant } from "../lib/iso-instant";
import "../styles/content-review.css";
import "../styles/evidence.css";

interface Props {
  initialData: LegacyContentReviewSurfaceData;
  bridge: HostBridge;
}

interface Draft {
  decision: ContentDecisionChoice | "";
  comment: string;
  saved?: ContentPageDecision;
  dirty: boolean;
  saving: boolean;
  message: string;
}

interface ContentReviewChapter {
  sectionId: string;
  title: string;
  task: string;
  slides: LegacyContentReviewSlide[];
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

const batchFields = [
  "batch_id", "project_id", "review_session_id", "source_version", "reading_blueprint_ref",
  "slide_ids", "decision_refs", "counts", "status", "immutable_after_submit", "submitted_at",
  "withdrawn_at", "supersedes_ref",
] as const;

const pageDecisionFields = [
  "page_decision_id", "project_id", "review_session_id", "source_version", "reading_blueprint_ref",
  "slide_id", "slide_order", "slide_title_snapshot", "decision", "comment", "status", "saved_at",
  "supersedes_decision_ref",
] as const;
const pageSaveResultFields = ["decision_ref", "decision", "snapshot"] as const;
const batchResultFields = ["batch_ref", "batch", "snapshot"] as const;
const snapshotFields = ["revision"] as const;

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

function contentLogicalOrigin(): number {
  const header = document.querySelector<HTMLElement>(".content-review-header");
  if (!header || window.getComputedStyle(header).position !== "sticky") return 0;
  return header.getBoundingClientRect().bottom;
}

function scrollToContentLogicalPosition(
  slideId: string,
  offset: number,
  behavior: ScrollBehavior,
) {
  const target = document.getElementById(`content-${slideId}`);
  if (!target) return;
  const origin = contentLogicalOrigin();
  window.scrollTo({
    behavior,
    left: window.scrollX,
    top: window.scrollY + target.getBoundingClientRect().top - origin + offset,
  });
}

function validatedDecision(
  value: unknown,
  review: LegacyContentReviewSurfaceData["review"],
  slide: LegacyContentReviewSlide,
): ContentPageDecision | null {
  const cloned = clonePlainData(value);
  if (!hasExactDataFields(cloned, pageDecisionFields)) return null;
  const decision = cloned.decision;
  if (!contentDecisionChoices.some(({ value: choice }) => choice === decision)) return null;
  const validatedChoice = decision as ContentDecisionChoice;
  if (typeof cloned.comment !== "string") return null;
  const comment = cloned.comment.trim();
  if (
    (validatedChoice === "approved" ? cloned.comment !== "" : !comment || cloned.comment !== comment)
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
    decision: validatedChoice,
    comment,
    status: "completed",
    saved_at: cloned.saved_at,
    supersedes_decision_ref: cloned.supersedes_decision_ref,
  };
}

function validatedBatch(
  value: unknown,
  review: LegacyContentReviewSurfaceData["review"],
): ValidatedContentReviewBatch | null {
  const cloned = clonePlainData(value);
  if (!hasExactDataFields(cloned, batchFields)) return null;
  const batch = cloned;
  const status = batch.status;
  if (status !== "submitted" && status !== "withdrawn") return null;
  const nonEmptyFields = [
    "batch_id", "project_id", "review_session_id", "source_version", "reading_blueprint_ref", "submitted_at",
  ];
  if (nonEmptyFields.some((field) => typeof batch[field] !== "string" || !(batch[field] as string).trim())) return null;
  if (!isIsoInstant(batch.submitted_at)) return null;
  if (!isArtifactReference(batch.reading_blueprint_ref, "reading-deck-blueprint")) return null;
  if (
    batch.project_id !== review.project_id
    || batch.review_session_id !== review.review_session_id
    || batch.source_version !== review.source_version
    || batch.reading_blueprint_ref !== review.reading_blueprint_ref
    || batch.immutable_after_submit !== true
  ) return null;
  if (!Array.isArray(batch.slide_ids) || !Array.isArray(batch.decision_refs)) return null;
  if (
    batch.slide_ids.length !== review.slides.length
    || batch.decision_refs.length !== review.slides.length
    || batch.slide_ids.some((slideId, index) => slideId !== review.slides[index]?.slide_id)
    || batch.decision_refs.some((reference) => !isArtifactReference(reference, "content-page-decision"))
    || new Set(batch.decision_refs).size !== batch.decision_refs.length
  ) return null;
  const choices = contentDecisionChoices.map(({ value: choice }) => choice);
  if (!hasExactDataFields(batch.counts, choices)) return null;
  const counts = batch.counts;
  if (
    choices.some((choice) => !Number.isInteger(counts[choice]) || (counts[choice] as number) < 0)
    || choices.reduce((total, choice) => total + (counts[choice] as number), 0) !== review.slides.length
  ) return null;
  if (typeof batch.withdrawn_at !== "string" || typeof batch.supersedes_ref !== "string") return null;
  if (batch.supersedes_ref && !isArtifactReference(batch.supersedes_ref, "content-review-batch")) return null;
  if (status === "submitted" && batch.withdrawn_at) return null;
  if (status === "withdrawn" && (!isIsoInstant(batch.withdrawn_at) || !batch.supersedes_ref)) return null;
  return {
    batch_id: batch.batch_id as string,
    project_id: batch.project_id as string,
    review_session_id: batch.review_session_id as string,
    source_version: batch.source_version as string,
    reading_blueprint_ref: batch.reading_blueprint_ref as string,
    slide_ids: [...batch.slide_ids] as string[],
    decision_refs: [...batch.decision_refs] as string[],
    counts: {
      approved: counts.approved as number,
      modify: counts.modify as number,
      evidence: counts.evidence as number,
      "merge-or-delete": counts["merge-or-delete"] as number,
    },
    status,
    immutable_after_submit: true,
    submitted_at: batch.submitted_at,
    withdrawn_at: batch.withdrawn_at,
    supersedes_ref: batch.supersedes_ref,
  };
}

function validatedInitialDecisions(
  review: LegacyContentReviewSurfaceData["review"],
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

function contentReviewChapters(
  sectionFlow: string[],
  slides: LegacyContentReviewSlide[],
): ContentReviewChapter[] {
  const chapters: ContentReviewChapter[] = [];
  for (const slide of slides) {
    const current = chapters.at(-1);
    if (current?.sectionId === slide.section_id) {
      current.slides.push(slide);
      continue;
    }
    chapters.push({
      sectionId: slide.section_id,
      title: sectionFlow[chapters.length] ?? slide.section_id,
      task: slide.page_task,
      slides: [slide],
    });
  }
  return chapters;
}

function initialDrafts(
  data: LegacyContentReviewSurfaceData,
  validatedDecisions: ContentPageDecision[],
  restoredDrafts: ContentReviewDraftUi["page_drafts"],
): Record<string, Draft> {
  const decisions = new Map(validatedDecisions.map((item) => [item.slide_id, item]));
  const recovered = new Map(restoredDrafts.map((item) => [item.slide_id, item]));
  return Object.fromEntries(data.review.slides.map((slide) => {
    const saved = decisions.get(slide.slide_id);
    const restored = recovered.get(slide.slide_id);
    return [slide.slide_id, {
      decision: restored?.decision ?? saved?.decision ?? "",
      comment: restored?.comment ?? saved?.comment ?? "",
      saved,
      dirty: Boolean(restored),
      saving: false,
      message: restored ? "已恢复，尚未保存" : saved ? "已保存" : "尚未判断",
    } satisfies Draft];
  }));
}

function reconcileAuthoritativeDrafts(
  current: Record<string, Draft>,
  slides: LegacyContentReviewSlide[],
  decisions: ContentPageDecision[],
): Record<string, Draft> {
  const authoritative = new Map(decisions.map((decision) => [decision.slide_id, decision]));
  return Object.fromEntries(slides.map((slide) => {
    const saved = authoritative.get(slide.slide_id);
    const draft = current[slide.slide_id];
    if (draft?.dirty) {
      return [slide.slide_id, { ...draft, saved } satisfies Draft];
    }
    return [slide.slide_id, {
      decision: saved?.decision ?? "",
      comment: saved?.comment ?? "",
      saved,
      dirty: false,
      saving: false,
      message: saved ? "已保存" : "尚未判断",
    } satisfies Draft];
  }));
}

export function ContentFullDeckReviewPage({ initialData, bridge }: Props) {
  const initialDecisions = validatedInitialDecisions(initialData.review);
  const initialBatch = initialData.review.batch === null
    ? null
    : validatedBatch(initialData.review.batch, initialData.review);
  const projectionInvalid = initialDecisions === null
    || (initialData.review.batch !== null && initialBatch === null);
  const reviewDraftContext = useMemo(
    () => createReviewDraftContext(initialData),
    [initialData],
  );
  const defaultReviewDraftUi = useMemo<ContentReviewDraftUi>(() => ({
    view: "document",
    current_slide_id: null,
    page_drafts: [],
    logical_scroll: null,
  }), [initialData]);
  const reviewDraft = useReviewDraft({
    context: reviewDraftContext,
    initialUi: defaultReviewDraftUi,
  });
  const contentIdentity = reviewDraftPageIdentity(reviewDraftContext);
  const [revision, setRevision] = useState(initialData.snapshotRevision);
  const revisionRef = useRef(initialData.snapshotRevision);
  const revisionIdentityRef = useRef(contentIdentity);
  const logicalPositionRef = useRef(reviewDraft.ui.logical_scroll);
  const mutationRef = useRef<null | { kind: "page"; slideId: string } | { kind: "batch" }>(null);
  const [drafts, setDrafts] = useState(() => initialDrafts(
    initialData,
    initialDecisions || [],
    reviewDraft.ui.page_drafts,
  ));
  const [batch, setBatch] = useState(initialBatch);
  const [submitting, setSubmitting] = useState(false);
  const [activeSaveSlideId, setActiveSaveSlideId] = useState<string | null>(null);
  const [pageMessage, setPageMessage] = useState("");
  const [evidenceSlide, setEvidenceSlide] = useState<LegacyContentReviewSlide | null>(null);
  const mountedRef = useRef(true);
  const generationRef = useRef(0);
  const restoredLogicalPositionRef = useRef(false);
  const evidenceTriggerRef = useRef<HTMLButtonElement | null>(null);
  const evidenceCloseRef = useRef<HTMLButtonElement | null>(null);
  const evidenceDialogRef = useRef<HTMLElement | null>(null);
  const evidenceWasOpenRef = useRef(false);
  const slides = initialData.review.slides;
  const chapters = useMemo(
    () => contentReviewChapters(initialData.review.section_flow, slides),
    [initialData.review.section_flow, slides],
  );
  const completed = slides.filter((slide) => drafts[slide.slide_id]?.saved && !drafts[slide.slide_id]?.dirty).length;
  const unsaved = slides.filter((slide) => drafts[slide.slide_id]?.dirty).length;
  const submittedBatch = batch?.status === "submitted";
  const withdrawnBatch = batch?.status === "withdrawn";
  const allCompleted = completed === slides.length && unsaved === 0 && !submittedBatch;
  const counts = useMemo(() => contentDecisionChoices.map(({ value, label }) => ({
    value,
    label,
    count: slides.filter((slide) => drafts[slide.slide_id]?.saved?.decision === value).length,
  })), [drafts, slides]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      generationRef.current += 1;
    };
  }, []);

  useEffect(() => {
    if (revisionIdentityRef.current !== contentIdentity) {
      revisionIdentityRef.current = contentIdentity;
      revisionRef.current = initialData.snapshotRevision;
      setRevision(initialData.snapshotRevision);
      return;
    }
    if (projectionInvalid || initialData.snapshotRevision <= revisionRef.current) return;
    revisionRef.current = initialData.snapshotRevision;
    setRevision((current) => Math.max(current, initialData.snapshotRevision));
    setDrafts((current) => reconcileAuthoritativeDrafts(
      current,
      initialData.review.slides,
      initialDecisions,
    ));
    setBatch(initialBatch);
  }, [
    contentIdentity,
    initialData.review.batch,
    initialData.review.decisions,
    initialData.review.slides,
    initialData.snapshotRevision,
    projectionInvalid,
  ]);

  useEffect(() => {
    if (restoredLogicalPositionRef.current) return;
    restoredLogicalPositionRef.current = true;
    const logicalScroll = reviewDraft.ui.logical_scroll;
    const slideId = logicalScroll?.object_id ?? reviewDraft.ui.current_slide_id;
    if (!slideId) return;
    scrollToContentLogicalPosition(slideId, logicalScroll?.offset ?? 0, "auto");
  }, [reviewDraft.ui.current_slide_id, reviewDraft.ui.logical_scroll]);

  useEffect(() => {
    if (evidenceSlide) {
      evidenceWasOpenRef.current = true;
      evidenceCloseRef.current?.focus();
      return;
    }
    if (evidenceWasOpenRef.current) {
      evidenceWasOpenRef.current = false;
      evidenceTriggerRef.current?.focus();
    }
  }, [evidenceSlide]);

  const closeEvidence = () => setEvidenceSlide(null);

  const handleEvidenceKeyDown = (event: React.KeyboardEvent<HTMLElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeEvidence();
      return;
    }
    if (event.key !== "Tab") return;
    const dialog = evidenceDialogRef.current;
    if (!dialog) return;
    const focusable = Array.from(dialog.querySelectorAll<HTMLElement>(
      "button:not(:disabled), [href], input:not(:disabled), textarea:not(:disabled), select:not(:disabled), [tabindex]:not([tabindex='-1'])",
    ));
    if (!focusable.length) {
      event.preventDefault();
      dialog.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (focusable.length === 1 || (!event.shiftKey && document.activeElement === last)) {
      event.preventDefault();
      first.focus();
    } else if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    }
  };

  const patchDraft = (slideId: string, update: Partial<Draft>) => {
    setDrafts((current) => ({
      ...current,
      [slideId]: { ...current[slideId], ...update },
    }));
  };

  const saveDecision = async (slide: LegacyContentReviewSlide): Promise<boolean> => {
    if (projectionInvalid || mutationRef.current || submittedBatch) return false;
    const draft = drafts[slide.slide_id];
    if (!draft.decision || (draft.decision !== "approved" && !draft.comment.trim())) return false;
    const commandGeneration = generationRef.current;
    const commandIdentity = contentIdentity;
    const commandRevision = revisionRef.current;
    const commandIsCurrent = () => (
      mountedRef.current
      && generationRef.current === commandGeneration
      && revisionIdentityRef.current === commandIdentity
    );
    mutationRef.current = { kind: "page", slideId: slide.slide_id };
    setActiveSaveSlideId(slide.slide_id);
    patchDraft(slide.slide_id, { saving: true, message: "正在保存…" });
    try {
      const rawResult = await bridge.callTool("save_content_page_decision", {
        projectRoot: initialData.selectedProjectRoot,
        expectedRevision: commandRevision,
        reviewSessionId: initialData.review.review_session_id,
        sourceVersion: initialData.review.source_version,
        slideId: slide.slide_id,
        decision: draft.decision,
        comment: draft.decision === "approved" ? "" : draft.comment.trim(),
      });
      if (!commandIsCurrent()) return false;
      if (revisionRef.current !== commandRevision) {
        patchDraft(slide.slide_id, {
          saving: false,
          message: "版本已变化；草稿仍保留，请刷新后重试。",
        });
        return false;
      }
      const result = clonePlainData(rawResult);
      if (!hasExactDataFields(result, pageSaveResultFields)) {
        patchDraft(slide.slide_id, {
          saving: false,
          message: "Runtime 返回无效结果；草稿仍保留，可直接重试。",
        });
        return false;
      }
      const commandDecision = draft.decision;
      const commandComment = draft.decision === "approved" ? "" : draft.comment.trim();
      const saved = validatedDecision(result.decision, initialData.review, slide);
      const savedRevision = nextRevision(result.snapshot, commandRevision);
      if (
        !isArtifactReference(result.decision_ref, "content-page-decision")
        || !saved
        || saved.decision !== commandDecision
        || saved.comment !== commandComment
        || savedRevision === null
      ) {
        patchDraft(slide.slide_id, {
          saving: false,
          message: "Runtime 返回无效结果；草稿仍保留，可直接重试。",
        });
        return false;
      }
      revisionRef.current = savedRevision;
      setRevision(savedRevision);
      patchDraft(slide.slide_id, {
        saved,
        decision: saved.decision,
        comment: saved.comment,
        dirty: false,
        saving: false,
        message: "已保存",
      });
      reviewDraft.updateDraft({ type: "clear-page-draft", slideId: slide.slide_id });
      return true;
    } catch (error) {
      if (!commandIsCurrent()) return false;
      const code = (error as Error & { code?: string }).code;
      patchDraft(slide.slide_id, {
        saving: false,
        message: code === "REVISION_CONFLICT" || code === "REVIEW_SOURCE_STALE"
          ? "版本已变化；草稿仍保留，请刷新后重试。"
          : "保存失败；草稿仍保留，可直接重试。",
      });
      return false;
    } finally {
      if (commandIsCurrent()) {
        mutationRef.current = null;
        setActiveSaveSlideId(null);
      }
    }
  };

  const nextIncompleteSlide = slides.find((slide) => {
    const draft = drafts[slide.slide_id];
    return !draft?.saved || draft.dirty;
  });

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
      const elements = Array.from(document.querySelectorAll<HTMLElement>("[data-content-slide]"));
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
      const slideId = selected.id.startsWith("content-")
        ? selected.id.slice("content-".length)
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

  const locateNextIncomplete = () => {
    if (!nextIncompleteSlide) return;
    recordLogicalPosition(nextIncompleteSlide.slide_id, 0);
    scrollToContentLogicalPosition(nextIncompleteSlide.slide_id, 0, "smooth");
    setPageMessage(`已定位到第 ${nextIncompleteSlide.order} 页未保存判断。`);
  };

  const submitBatch = async () => {
    if (projectionInvalid || !allCompleted || mutationRef.current || submittedBatch) return;
    const commandGeneration = generationRef.current;
    const commandIdentity = contentIdentity;
    const commandRevision = revisionRef.current;
    const commandIsCurrent = () => (
      mountedRef.current
      && generationRef.current === commandGeneration
      && revisionIdentityRef.current === commandIdentity
    );
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
      const submitted = validatedBatch(result.batch, initialData.review);
      const submittedRevision = nextRevision(result.snapshot, commandRevision);
      if (
        !isArtifactReference(result.batch_ref, "content-review-batch")
        || !submitted
        || submitted.status !== "submitted"
        || submittedRevision === null
      ) {
        setPageMessage("Runtime 返回无效结果；本轮审核仍可提交，请重试。");
        return;
      }
      revisionRef.current = submittedRevision;
      setRevision(submittedRevision);
      setBatch(submitted);
      setPageMessage("已提交，等待整套修改方案");
      reviewDraft.updateDraft({ type: "clear-content-batch" });
    } catch (error) {
      if (!commandIsCurrent()) return;
      const code = (error as Error & { code?: string }).code;
      setPageMessage(code === "REVISION_CONFLICT" || code === "REVIEW_SOURCE_STALE"
        ? "当前版本已变化；所有本地输入仍保留，请刷新后重试。"
        : "本轮审核尚未提交；所有输入仍保留，可直接重试。");
    } finally {
      if (commandIsCurrent()) {
        mutationRef.current = null;
        setSubmitting(false);
      }
    }
  };

  return (
    <>
    <main className="content-review-page" inert={evidenceSlide ? true : undefined}>
      <header className="content-review-head content-review-header" data-content-review-header>
        <div>
          <p className="content-review-kicker">内容全稿审核</p>
          <h1>完整售前阅读稿</h1>
          <p>{initialData.review.material_mode} · {initialData.review.source_version} · revision {revision}</p>
        </div>
        <div className="content-review-progress" aria-label="审核进度">
          <strong>{completed}/{slides.length}</strong>
          <span>已完成 · {slides.length - completed} 未完成 · {unsaved} 未保存</span>
          <div className="content-review-counts">
            {counts.map((item) => <span key={item.value}>{item.label} {item.count}</span>)}
          </div>
        </div>
        <div className="content-review-header-actions">
          <button
            className="content-review-locate"
            type="button"
            disabled={!nextIncompleteSlide}
            onClick={locateNextIncomplete}
          >{nextIncompleteSlide ? "定位下一页未判断" : "全部页面已完成判断"}</button>
          <button
            className="content-review-submit"
            type="button"
            disabled={projectionInvalid || !allCompleted || submitting || Boolean(activeSaveSlideId)}
            onClick={submitBatch}
          >
            {submitting ? "正在提交…" : "完成本轮审核，交给 Codex 集中处理"}
          </button>
        </div>
        <div
          className="content-review-progress-track"
          data-content-review-progress-track
          role="progressbar"
          aria-label="全稿审核完成进度"
          aria-valuemin={0}
          aria-valuemax={slides.length}
          aria-valuenow={completed}
        >
          <span style={{ width: `${slides.length ? (completed / slides.length) * 100 : 0}%` }} />
        </div>
      </header>

      {projectionInvalid ? (
        <p className="content-review-page-message" role="alert">权威审核投影无效，请刷新/重新打开；当前内容仅供只读查看。</p>
      ) : null}
      {withdrawnBatch ? <p className="content-review-page-message">上一批次已撤回</p> : null}
      {pageMessage ? <p className="content-review-page-message" role="status">{pageMessage}</p> : null}
      <nav
        className="content-review-chapter-nav content-review-outline"
        data-content-review-chapter-nav
        aria-label="章节导航"
      >
        {chapters.map((chapter, chapterIndex) => (
          <div className="content-review-chapter-nav-item" key={chapter.sectionId}>
            <a
              className="content-review-chapter-link"
              href={`#content-chapter-${chapterIndex + 1}`}
              onClick={(event) => {
                event.preventDefault();
                const firstSlide = chapter.slides[0];
                recordLogicalPosition(firstSlide.slide_id, 0);
                scrollToContentLogicalPosition(firstSlide.slide_id, 0, "smooth");
              }}
            >第 {chapterIndex + 1} 章 · {chapter.title}</a>
            <span className="content-review-chapter-pages" aria-label={`${chapter.title} 页面定位`}>
              {chapter.slides.map((slide) => (
                <a
                  key={slide.slide_id}
                  href={`#content-${slide.slide_id}`}
                  onClick={(event) => {
                    event.preventDefault();
                    recordLogicalPosition(slide.slide_id, 0);
                    scrollToContentLogicalPosition(slide.slide_id, 0, "smooth");
                  }}
                >{slide.order}</a>
              ))}
            </span>
          </div>
        ))}
      </nav>

      <section
        className="content-review-deck-intro"
        data-content-review-deck-intro
        aria-labelledby="content-review-deck-intro-title"
      >
        <p className="content-review-kicker">本稿阅读导语</p>
        <h2 id="content-review-deck-intro-title">按最终页序连续阅读完整稿</h2>
        <p><strong>{initialData.review.material_mode}</strong> · {chapters.length} 个章节 · {slides.length} 页 · {initialData.review.source_version}</p>
        <p>从第一章连续读到最后一页；正文、材料、证据身份、演讲备注和跨页关系保持在当前审核上下文中。</p>
      </section>

      <section className="content-review-document" aria-label="完整内容全稿">
        {chapters.map((chapter, chapterIndex) => (
          <section
            className="content-review-chapter"
            id={`content-chapter-${chapterIndex + 1}`}
            key={chapter.sectionId}
            data-content-chapter
            data-section-id={chapter.sectionId}
            aria-labelledby={`content-chapter-${chapterIndex + 1}-title`}
          >
            <header className="content-review-chapter-heading">
              <p>第 {chapterIndex + 1} 章</p>
              <h2 id={`content-chapter-${chapterIndex + 1}-title`}>{chapter.title}</h2>
              <p><strong>本章阅读任务：</strong>{chapter.task}</p>
              <p>第 {chapter.slides[0].order}–{chapter.slides.at(-1)?.order} 页 · {chapter.slides.length} 页</p>
            </header>
            <div className="content-review-chapter-slides">
              {chapter.slides.map((slide, slideIndex) => {
                const draft = drafts[slide.slide_id];
                return (
            <article className="content-review-slide" id={`content-${slide.slide_id}`} key={slide.slide_id} data-content-slide>
              <header className="content-slide-heading">
                <div><span>第 {slide.order} 页 · {slide.slide_id}</span><span>{slide.section_id}</span></div>
                <h2>{slide.neutral_title}</h2>
                <p><strong>页面任务：</strong>{slide.page_task}</p>
                <p><strong>阅读问题：</strong>{slide.reading_question}</p>
              </header>

              <div
                className="content-slide-reading-grid"
                data-content-review-first-reading-grid={chapterIndex === 0 && slideIndex === 0 ? "true" : undefined}
              >
                <div className="content-slide-main">
                  <section aria-label={`${slide.slide_id} 完整正文`}>
                    <h3>完整可见文字</h3>
                    {slide.visible_copy_blocks.map((block) => (
                      <p key={block.block_id}><span className="identity-label">{block.identity}</span>{block.text}</p>
                    ))}
                  </section>
                  <section aria-label={`${slide.slide_id} 分析与建议`}>
                    <h3>分析、假设与建议</h3>
                    {slide.analysis_or_proposal_blocks.length
                      ? slide.analysis_or_proposal_blocks.map((block) => (
                        <p key={block.block_id}><span className="identity-label">{block.identity}</span>{block.text}</p>
                      ))
                      : <p>本页没有额外分析或方案块。</p>}
                  </section>
                  <details className="content-slide-notes">
                    <summary>完整演讲备注</summary>
                    <p>{slide.speaker_notes}</p>
                  </details>
                  <section className="content-slide-evidence" aria-label={`${slide.slide_id} 证据与关系`}>
                    <h3>证据与身份</h3>
                    <p>{slide.identity_labels.join(" · ")}</p>
                    {slide.evidence_bindings.length ? (
                      <button type="button" onClick={(event) => {
                        evidenceTriggerRef.current = event.currentTarget;
                        setEvidenceSlide(slide);
                      }}>查看 {slide.slide_id} 来源证据</button>
                    ) : <p>当前为明确证据缺口或 proposal-led 内容，没有项目材料引用。</p>}
                    <h3>问题—方案映射</h3><p>{slide.solution_mapping_refs.join(" · ")}</p>
                    <h3>跨页关系</h3>
                    <p><span>{slide.previous_relation}</span><span> → </span><span>{slide.next_relation}</span></p>
                    <h3>阅读质量</h3><p>{slide.reading_quality.information_density} · {slide.reading_quality.review_note}</p>
                  </section>
                </div>
                <ContentMaterialView
                  bridge={bridge}
                  projectRoot={initialData.selectedProjectRoot}
                  slide={slide}
                  readsDisabled={projectionInvalid}
                />
              </div>

              <PageDecisionControl
                slideId={slide.slide_id}
                decision={draft.decision}
                comment={draft.comment}
                saved={draft.saved}
                dirty={draft.dirty}
                saving={draft.saving}
                message={draft.message}
                disabled={projectionInvalid || submittedBatch || submitting || activeSaveSlideId === slide.slide_id}
                saveDisabled={projectionInvalid || Boolean(activeSaveSlideId)}
                onDecisionChange={(decision) => {
                  const comment = decision === "approved" ? "" : draft.comment;
                  patchDraft(slide.slide_id, {
                    decision,
                    comment,
                    dirty: true,
                    message: "尚未保存",
                  });
                  reviewDraft.updateDraft({
                    type: "upsert-page-draft",
                    draft: { slide_id: slide.slide_id, decision, comment },
                  });
                }}
                onCommentChange={(comment) => {
                  patchDraft(slide.slide_id, {
                    comment,
                    dirty: true,
                    message: "尚未保存",
                  });
                  reviewDraft.updateDraft({
                    type: "upsert-page-draft",
                    draft: { slide_id: slide.slide_id, decision: draft.decision, comment },
                  });
                }}
                onSave={() => saveDecision(slide)}
              />
            </article>
                );
              })}
            </div>
          </section>
        ))}
      </section>

      <section className="content-review-summary" aria-labelledby="content-review-summary-title">
        <p className="content-review-kicker">本轮审核汇总</p>
        <h2 id="content-review-summary-title">{completed}/{slides.length} 页已完成</h2>
        <p>仍有 {slides.length - completed} 页未完成，{unsaved} 项本地输入尚未保存。</p>
        <p>{submittedBatch
          ? "本轮审核已冻结并提交，等待 Codex 形成整套修改方案。"
          : allCompleted
            ? "全部页面已完成，可使用页头主操作提交本轮审核。"
            : "继续完成逐页判断；系统会保留已保存判断和当前本地草稿。"}</p>
      </section>

    </main>

      {evidenceSlide ? (
        <div className="evidence-backdrop" role="presentation">
          <aside
            className="evidence-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="content-evidence-dialog-title"
            ref={evidenceDialogRef}
            tabIndex={-1}
            onKeyDown={handleEvidenceKeyDown}
          >
            <header>
              <h2 id="content-evidence-dialog-title">{evidenceSlide.slide_id} 来源证据</h2>
              <button type="button" ref={evidenceCloseRef} onClick={closeEvidence}>关闭证据</button>
            </header>
            {evidenceSlide.evidence_bindings.map((binding, index) => (
              <dl key={index}>
                {Object.entries(binding).map(([key, value]) => (
                  <div key={key}><dt>{key}</dt><dd>{Array.isArray(value) ? value.join(" · ") : String(value)}</dd></div>
                ))}
              </dl>
            ))}
            <p>只读辅助层：关闭后保留当前页、滚动位置和未保存草稿。</p>
          </aside>
        </div>
      ) : null}
    </>
  );
}
