import { useCallback, useMemo, useRef, useState } from "react";
import { ArrowDownToLine, ListTree } from "lucide-react";

import type { HostBridge } from "../../types";
import {
  contentReviewBatchId,
  nextIncompleteSlideId,
  type ContentFullDeckReviewProjection,
  type ContentPageDecision,
} from "../../types/content-review";
import type { ContentReviewClient } from "../../lib/content-review-client";
import { ContentReviewDirectory } from "./ContentReviewDirectory";
import { ContentSlideSection } from "./ContentSlideSection";
import type { PageDecisionEditorMeta } from "./PageDecisionEditor";
import { ReviewBatchFooter } from "./ReviewBatchFooter";

interface Props {
  projection: ContentFullDeckReviewProjection;
  projectRoot: string;
  bridge: HostBridge;
  client: ContentReviewClient;
  onProjectionChange: (projection: ContentFullDeckReviewProjection) => void;
}

function initialEditorMeta(projection: ContentFullDeckReviewProjection) {
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
}: Props) {
  const [directoryOpen, setDirectoryOpen] = useState(false);
  const [editorMetaBySlide, setEditorMetaBySlide] = useState(() => initialEditorMeta(projection));
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [followUpState, setFollowUpState] = useState<"idle" | "sending" | "failed" | "sent">("idle");
  const [followUpMessage, setFollowUpMessage] = useState("");
  const [batchReceipt, setBatchReceipt] = useState("");
  const submittedBatchRef = useRef("");
  const reviewSessionId = projection.review_session.review_session_id;
  const reviewBatchId = contentReviewBatchId(reviewSessionId);

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
    await client.saveDecision({
      projectRoot,
      expectedRevision: projection.revision,
      reviewSessionId,
      reviewBatchId,
      slideId,
      decision,
      comment,
    });
    const refreshed = await client.load(projectRoot, reviewSessionId);
    onProjectionChange(refreshed);
  }, [client, onProjectionChange, projectRoot, projection.revision, reviewBatchId, reviewSessionId]);

  const openEvidenceBrowser = useCallback(async (
    slideId: string,
    evidenceId: string,
    materialRef: string,
  ) => {
    return client.openEvidenceBrowser({
      projectRoot,
      reviewSessionId,
      sourceVersion: projection.source_version,
      slideId,
      evidenceId,
      materialRef,
    });
  }, [client, projectRoot, projection.source_version, reviewSessionId]);

  const allEditorMeta = projection.slides.map((slide) => editorMetaBySlide.get(slide.slide_id));
  const countMatches = projection.review_progress.total === projection.slides.length
    && editorMetaBySlide.size === projection.slides.length;
  const hasDirty = allEditorMeta.some((meta) => meta?.dirty);
  const hasPending = allEditorMeta.some((meta) => meta?.saveStatus === "pending");
  const hasFailure = allEditorMeta.some((meta) => meta?.saveStatus === "failed");
  const hasConflict = allEditorMeta.some((meta) => meta?.conflict);
  const allCompleted = allEditorMeta.every((meta) => meta?.completed);
  const sessionEditable = ["ready", "opened"].includes(projection.review_session.status);
  const canSubmit = countMatches
    && allCompleted
    && projection.review_progress.remaining === 0
    && !hasDirty
    && !hasPending
    && !hasFailure
    && !hasConflict
    && sessionEditable;

  let blockedReason = "";
  if (!countMatches) blockedReason = "页面数量与权威审核进度不一致，请刷新后再提交。";
  else if (hasConflict) blockedReason = "存在 sourceVersion 或 revision 冲突；草稿已保留，请处理冲突。";
  else if (hasPending) blockedReason = "仍有页面正在保存。";
  else if (hasFailure) blockedReason = "仍有保存失败的页面，意见未丢失，请重试。";
  else if (hasDirty) blockedReason = "仍有未保存的选择或意见。";
  else if (!allCompleted || projection.review_progress.remaining > 0) blockedReason = `仍有 ${Math.max(projection.review_progress.remaining, 0)} 页未完成判断。`;
  else if (!sessionEditable) blockedReason = "当前审核会话已冻结或失效，不能再次提交。";

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
        reviewSessionId,
        reviewBatchId,
      });
      submittedBatchRef.current = result.artifact_ref;
      setBatchReceipt(result.artifact_ref);
      setFollowUpMessage(result.follow_up_message);
      const refreshed = await client.load(projectRoot, reviewSessionId);
      onProjectionChange(refreshed);
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

  const nextIncomplete = nextIncompleteSlideId(projection);
  return (
    <article className="content-review-document" data-slide-count={projection.slides.length}>
      <header className="content-review-document-header content-review-header">
        <div className="content-review-title-row">
          <div>
            <p>CONTENT REVIEW</p>
            <h1>完整内容审核</h1>
            <span>按最终顺序连续阅读整套内容，并逐页作出判断</span>
          </div>
          <div className="content-review-header-actions">
            <button type="button" aria-label="目录定位" aria-expanded={directoryOpen} onClick={() => setDirectoryOpen(true)}><ListTree size={16} />目录</button>
            <button type="button" aria-label="定位下一页未判断" disabled={!nextIncomplete} onClick={() => navigateTo(nextIncomplete)}><ArrowDownToLine size={16} />下一页未判断</button>
          </div>
        </div>
        <div className="content-review-summary">
          <strong>{projection.review_progress.completed} / {projection.review_progress.total} 页已判断</strong>
          <span>{projection.review_progress.remaining} 页待处理</span>
          <span className="content-review-session-state">{projection.review_session.status}</span>
        </div>
        <div className="content-review-progress-track" aria-label="审核进度">
          <i style={{ width: `${projection.review_progress.total ? (projection.review_progress.completed / projection.review_progress.total) * 100 : 0}%` }} />
        </div>
      </header>

      <nav className="content-review-chapter-nav" aria-label="章节导航">
        <button type="button" onClick={() => navigateTo(projection.slides[0]?.slide_id || "")}>01 · 全稿内容</button>
        <span>{projection.slides.length} 页</span>
      </nav>

      <section className="content-review-deck-intro">
        <p>本次审核</p>
        <h2>先完整阅读页面目标、实际文字与材料，再在页内给出判断</h2>
        <span>没有图片的页面不强制提供图片；存在多条材料时按登记顺序连续展示。保存本页判断不等于 G0 通过。</span>
      </section>

      <ContentReviewDirectory open={directoryOpen} slides={projection.slides} onClose={() => setDirectoryOpen(false)} onNavigate={navigateTo} />

      <main className="content-review-slide-list">
        <section className="content-review-chapter" data-content-chapter="full-deck">
          <header className="content-review-chapter-heading"><span>01</span><div><p>完整内容</p><h2>按最终顺序逐页阅读与判断</h2></div></header>
          {projection.slides.map((slide) => (
            <ContentSlideSection
              key={slide.slide_id}
              slide={slide}
              bridge={bridge}
              projectRoot={projectRoot}
              onSaveDecision={saveDecision}
              onEditorMetaChange={updateEditorMeta}
              onOpenEvidenceBrowser={openEvidenceBrowser}
            />
          ))}
        </section>
      </main>

      <ReviewBatchFooter
        projection={projection}
        canSubmit={canSubmit}
        blockedReason={blockedReason}
        submitting={submitting}
        submitError={submitError}
        batchReceipt={batchReceipt}
        followUpState={followUpState}
        onSubmit={submitBatch}
        onRetryFollowUp={() => sendFollowUp(followUpMessage)}
      />
    </article>
  );
}
