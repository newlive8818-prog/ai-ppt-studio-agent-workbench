import { useCallback, useMemo, useRef, useState } from "react";
import { ArrowDownToLine, ListTree } from "lucide-react";

import type {
  ContentFullDeckProjection,
  ContentPageDecision,
  HostBridge,
  ProjectSnapshot,
} from "../../types";
import type { ContentReviewClient } from "../../lib/content-review-client";
import { ContentReviewDirectory } from "./ContentReviewDirectory";
import { ContentSlideSection } from "./ContentSlideSection";
import type { PageDecisionEditorMeta } from "./PageDecisionEditor";
import { ReviewBatchFooter } from "./ReviewBatchFooter";

interface Props {
  projection: ContentFullDeckProjection;
  projectRoot: string;
  bridge: HostBridge;
  client: ContentReviewClient;
  onProjectionChange: (projection: ContentFullDeckProjection) => void;
  onSnapshotChange: (snapshot: ProjectSnapshot) => void;
}

function initialEditorMeta(projection: ContentFullDeckProjection) {
  const result = new Map<string, PageDecisionEditorMeta>();
  for (const slide of projection.slides) {
    result.set(slide.slide_id, {
      dirty: false,
      completed: slide.decision_state.completed,
      saveStatus: slide.decision_state.saved ? "saved" : "idle",
      conflict: false,
    });
  }
  return result;
}

export function ContentReviewDocument({
  projection,
  projectRoot,
  bridge,
  client,
  onProjectionChange,
  onSnapshotChange,
}: Props) {
  const [directoryOpen, setDirectoryOpen] = useState(false);
  const [editorMetaBySlide, setEditorMetaBySlide] = useState(() => initialEditorMeta(projection));
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [followUpState, setFollowUpState] = useState<"idle" | "sending" | "failed" | "sent">("idle");
  const [followUpMessage, setFollowUpMessage] = useState("");
  const submittedBatchRef = useRef("");

  const slidesById = useMemo(
    () => new Map(projection.slides.map((slide) => [slide.slide_id, slide])),
    [projection.slides],
  );

  const updateEditorMeta = useCallback((slideId: string, meta: PageDecisionEditorMeta) => {
    setEditorMetaBySlide((current) => {
      const previous = current.get(slideId);
      if (previous
        && previous.dirty === meta.dirty
        && previous.completed === meta.completed
        && previous.saveStatus === meta.saveStatus
        && previous.conflict === meta.conflict) return current;
      const next = new Map(current);
      next.set(slideId, meta);
      return next;
    });
  }, []);

  const saveDecision = useCallback(async (
    slideId: string,
    decision: ContentPageDecision,
    comment: string,
  ) => {
    const result = await client.saveDecision({
      projectRoot,
      expectedRevision: projection.revision,
      sourceVersion: projection.source_version,
      reviewBatchId: projection.decision_set.review_batch_id,
      slideId,
      decision,
      comment,
    });
    onSnapshotChange(result.snapshot);
    const refreshed = await client.load(projectRoot);
    if (!client.isReviewReady(refreshed)) {
      const error = new Error("内容审核投影已转为不可审核状态") as Error & { code?: string };
      error.code = "CONTENT_REVIEW_CONFLICT";
      throw error;
    }
    onProjectionChange(refreshed);
  }, [client, onProjectionChange, onSnapshotChange, projectRoot, projection.decision_set.review_batch_id, projection.revision, projection.source_version]);

  const openEvidenceBrowser = useCallback(async (
    slideId: string,
    evidenceId: string,
    materialRef: string,
  ) => {
    await client.openEvidenceBrowser({
      projectRoot,
      sourceVersion: projection.source_version,
      slideId,
      evidenceId,
      materialRef,
    });
  }, [client, projectRoot, projection.source_version]);

  const allEditorMeta = projection.slides.map((slide) => editorMetaBySlide.get(slide.slide_id));
  const countMatches = projection.review_progress.total === projection.slides.length
    && editorMetaBySlide.size === projection.slides.length;
  const hasDirty = allEditorMeta.some((meta) => meta?.dirty);
  const hasPending = allEditorMeta.some((meta) => meta?.saveStatus === "pending");
  const hasFailure = allEditorMeta.some((meta) => meta?.saveStatus === "failed");
  const hasConflict = allEditorMeta.some((meta) => meta?.conflict);
  const allCompleted = allEditorMeta.every((meta) => meta?.completed);
  const currentBatchDraft = projection.current_batch.status === "draft"
    && projection.phase === "full-deck-review-ready";
  const canSubmit = countMatches
    && allCompleted
    && projection.review_progress.remaining === 0
    && !hasDirty
    && !hasPending
    && !hasFailure
    && !hasConflict
    && currentBatchDraft;

  let blockedReason = "";
  if (!countMatches) blockedReason = "页面数量与权威审核进度不一致，请刷新后再提交。";
  else if (hasConflict) blockedReason = "存在 sourceVersion 或 revision 冲突；草稿已保留，请处理冲突。";
  else if (hasPending) blockedReason = "仍有页面正在保存。";
  else if (hasFailure) blockedReason = "仍有保存失败的页面，意见未丢失，请重试。";
  else if (hasDirty) blockedReason = "仍有未保存的选择或意见。";
  else if (!allCompleted || projection.review_progress.remaining > 0) blockedReason = `仍有 ${Math.max(projection.review_progress.remaining, 0)} 页未完成判断。`;

  const navigateTo = useCallback((slideId: string) => {
    if (!slidesById.has(slideId)) return;
    setDirectoryOpen(false);
    const element = document.getElementById(`content-slide-${slideId}`);
    element?.scrollIntoView({ behavior: "smooth", block: "start" });
    element?.focus({ preventScroll: true });
  }, [slidesById]);

  async function sendFollowUp(message: string) {
    if (!message) {
      setFollowUpState("sent");
      return;
    }
    setFollowUpState("sending");
    try {
      await bridge.sendFollowUp(message);
      setFollowUpState("sent");
    } catch (_error) {
      setFollowUpState("failed");
    }
  }

  async function submitBatch() {
    if (!canSubmit || submitting || submittedBatchRef.current) return;
    setSubmitting(true);
    setSubmitError("");
    try {
      const result = await client.submitBatch({
        projectRoot,
        expectedRevision: projection.revision,
        sourceVersion: projection.source_version,
        reviewBatchId: projection.decision_set.review_batch_id,
      });
      submittedBatchRef.current = result.artifact_ref;
      onSnapshotChange(result.snapshot);
      const refreshed = await client.load(projectRoot);
      if (!client.isReviewReady(refreshed)) throw new Error("提交后无法刷新完整审核投影");
      onProjectionChange(refreshed);
      setFollowUpMessage(result.follow_up_message);
      await sendFollowUp(result.follow_up_message);
    } catch (caught) {
      if (submittedBatchRef.current) {
        setFollowUpState("failed");
      } else {
        const code = (caught as Error & { code?: string }).code || "";
        setSubmitError(code.includes("CONFLICT") || code.includes("STALE")
          ? "当前内容版本已变化；所有未保存意见仍保留，请查看差异后重试。"
          : "审核批次未提交；已保存的逐页判断未变，可重试。");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <article className="content-review-document" data-slide-count={projection.slides.length}>
      <header className="content-review-document-header">
        <div className="content-review-title-row">
          <div>
            <p>阅读优先·完整全稿</p>
            <h1>完整内容审核</h1>
            <span>{projection.mission_summary.topic}</span>
          </div>
          <div className="content-review-header-actions">
            <button type="button" aria-label="目录定位" aria-expanded={directoryOpen} onClick={() => setDirectoryOpen(true)}><ListTree size={16} />目录</button>
            <button type="button" aria-label="定位下一页未判断" disabled={!projection.review_progress.next_incomplete_slide_id} onClick={() => navigateTo(projection.review_progress.next_incomplete_slide_id)}><ArrowDownToLine size={16} />下一页未判断</button>
          </div>
        </div>
        <div className="content-review-mission">
          <div><span>汇报对象</span><strong>{projection.mission_summary.primary_audience}</strong></div>
          <div><span>本稿要支持的决策事项</span><strong>{projection.mission_summary.decision_question_or_next_action}</strong></div>
          <div><span>内容模式</span><strong>{projection.material_mode}</strong></div>
        </div>
        <div className="content-review-summary">
          <strong>{projection.review_progress.completed} / {projection.review_progress.total} 页已判断</strong>
          <span>{projection.review_progress.remaining} 页待处理</span>
          <code>revision {projection.revision}</code>
        </div>
      </header>

      <ContentReviewDirectory open={directoryOpen} chapters={projection.chapters} slides={projection.slides} onClose={() => setDirectoryOpen(false)} onNavigate={navigateTo} />

      <main className="content-review-slide-list">
        {projection.slides.map((slide) => (
          <ContentSlideSection
            key={slide.slide_id}
            slide={slide}
            projectRoot={projectRoot}
            bridge={bridge}
            onSaveDecision={saveDecision}
            onEditorMetaChange={updateEditorMeta}
            onOpenEvidenceBrowser={openEvidenceBrowser}
          />
        ))}
      </main>

      <ReviewBatchFooter
        projection={projection}
        canSubmit={canSubmit}
        blockedReason={blockedReason}
        submitting={submitting}
        submitError={submitError}
        followUpState={followUpState}
        onSubmit={submitBatch}
        onRetryFollowUp={() => sendFollowUp(followUpMessage)}
      />
    </article>
  );
}
