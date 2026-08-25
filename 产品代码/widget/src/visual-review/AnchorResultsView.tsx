import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent } from "react";

import type {
  AnchorFeedbackComposerState,
  AnchorFeedbackDraftState,
} from "../review-draft/reviewDraftStore";
import type { HostBridge } from "../types/host";
import type { ToolContractMap } from "../types/tool-contracts";
import type {
  AnchorFeedbackBatch,
  AnchorRegionFeedback,
} from "../types/visual-review";
import type { VisualReviewPageViewModel } from "./visual-review-page-view-model";
import { AnchorComparisonDialog } from "./AnchorComparisonDialog";
import {
  sameAnchorFeedbackBatchImmutableAuthority,
  validateAnchorFeedbackBatch,
  validateAnchorFeedbackToolResult,
} from "./anchor-feedback-validation";
import { RegionFeedbackEditor } from "./RegionFeedbackEditor";
import {
  isReviewWriteTimeout,
  withReviewWriteDeadline,
} from "./review-write-deadline";
import { VisualReceiptRecoveryControls } from "./VisualReceiptRecoveryControls";

interface Props {
  data: VisualReviewPageViewModel;
  bridge: HostBridge;
  revision: number;
  onRevision: (revision: number) => void;
  commandIdentity: string;
  drafts: AnchorFeedbackDraftState[];
  composer: AnchorFeedbackComposerState | null;
  onSliceChange: (
    drafts: AnchorFeedbackDraftState[],
    composer: AnchorFeedbackComposerState | null,
  ) => void;
  onClearSlice: () => void;
  currentSlideId: string;
  onCurrentSlideChange: (slideId: string) => void;
}

interface AnchorWriteRequest {
  commandIdentity: string;
  commandRevision: number;
  drafts: AnchorFeedbackDraftState[];
  feedback: AnchorRegionFeedback[];
  args: ToolContractMap["submit_visual_anchor_feedback_batch"]["input"];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function hostStatus(status: AnchorFeedbackBatch["host_notification_status"]) {
  return ({ "not-requested": "未请求", pending: "通知中", sent: "已送达", failed: "失败", unavailable: "不可用" })[status];
}

function aiStatus(status: AnchorFeedbackBatch["ai_receipt_status"]) {
  return ({ pending: "待回执", received: "已接收", rejected: "已拒绝", unverified: "未验证" })[status];
}

function capabilityStatus(status: "available" | "unavailable" | "unknown") {
  return ({ available: "可用", unavailable: "不可用", unknown: "待验证" })[status];
}

function isWritableRevision(value: unknown): value is number {
  return typeof value === "number"
    && Number.isSafeInteger(value)
    && value >= 0
    && value < Number.MAX_SAFE_INTEGER;
}

const invalidRevisionMessage = "当前 revision 无效，本地反馈已进入只读保护；请重新打开审核页后再提交。";

export function AnchorResultsView({
  data,
  bridge,
  revision,
  onRevision,
  commandIdentity,
  drafts,
  composer,
  onSliceChange,
  onClearSlice,
  currentSlideId,
  onCurrentSlideChange,
}: Props) {
  const anchors = data.review.anchors;
  const instanceId = useId();
  const projectedBatch = data.review.anchor_feedback_batch;
  const initialBatch = projectedBatch === null ? null : validateAnchorFeedbackBatch(projectedBatch, data);
  const invalidInitialBatch = projectedBatch !== null && initialBatch === null;
  const [batch, setBatch] = useState(initialBatch);
  const [savedArtifactRef, setSavedArtifactRef] = useState<string | null>(
    initialBatch ? data.review.anchor_feedback_batch_ref : null,
  );
  const [submitting, setSubmitting] = useState(false);
  const [retryPending, setRetryPending] = useState(false);
  const [recoveryRequired, setRecoveryRequired] = useState(invalidInitialBatch);
  const [comparisonOpen, setComparisonOpen] = useState(false);
  const [message, setMessage] = useState(invalidInitialBatch ? "权威视觉审核投影无效，请刷新/重新打开" : "");
  const mutationRef = useRef(false);
  const mountedRef = useRef(true);
  const generationRef = useRef(0);
  const retryRequestRef = useRef<AnchorWriteRequest | null>(null);
  const identityRef = useRef(commandIdentity);
  const revisionRef = useRef(revision);
  const highestObservedSnapshotRevisionRef = useRef(data.snapshotRevision);
  const authoritativeBatchRevisionRef = useRef(initialBatch?.revision ?? -1);
  const authoritativeBatchRef = useRef(initialBatch);
  const authoritativeBatchArtifactRef = useRef(initialBatch ? data.review.anchor_feedback_batch_ref : null);
  const anchorTabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const viewRef = useRef<HTMLElement | null>(null);
  identityRef.current = commandIdentity;
  revisionRef.current = revision;
  const activeSlide = currentSlideId;
  const setActiveSlide = (slideId: string) => {
    onCurrentSlideChange(slideId);
  };
  const active = anchors.find((item) => item.slide_id === activeSlide) || anchors[0];
  const feedbackRecords: AnchorFeedbackDraftState[] = batch
    ? batch.items.map((item) => ({
        feedback_id: item.feedback_id,
        anchor_slide_id: item.anchor_slide_id,
        normalized_region: item.normalized_region,
        comment: item.comment,
        created_at: item.created_at,
      }))
    : drafts;
  const closeComparison = useCallback(() => setComparisonOpen(false), []);
  const hasUncommittedFeedback = composer !== null;
  const revisionIsWritable = isWritableRevision(revision);
  const draftsLocked = Boolean(batch) || submitting || retryPending || recoveryRequired || !revisionIsWritable;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      generationRef.current += 1;
    };
  }, []);

  useEffect(() => {
    if (!mutationRef.current && !retryRequestRef.current) return;
    generationRef.current += 1;
    mutationRef.current = false;
    retryRequestRef.current = null;
    setSubmitting(false);
    setRetryPending(false);
    setMessage("当前视觉版本已变化；旧提交已失效，全部本地反馈仍保留，可重新提交。");
  }, [commandIdentity, revision]);

  useEffect(() => {
    if (data.snapshotRevision < highestObservedSnapshotRevisionRef.current) return;
    if (data.snapshotRevision > highestObservedSnapshotRevisionRef.current) {
      highestObservedSnapshotRevisionRef.current = data.snapshotRevision;
    }
    if (projectedBatch === null) return;
    if (!initialBatch) {
      setRecoveryRequired(true);
      setMessage("权威视觉审核投影无效，请刷新/重新打开");
      return;
    }
    if (initialBatch.revision < authoritativeBatchRevisionRef.current) return;
    if (
      initialBatch.revision === authoritativeBatchRevisionRef.current
      && authoritativeBatchRef.current
      && !sameAnchorFeedbackBatchImmutableAuthority(authoritativeBatchRef.current, initialBatch)
    ) return;
    if (
      initialBatch.revision === authoritativeBatchRevisionRef.current
      && authoritativeBatchArtifactRef.current
      && data.review.anchor_feedback_batch_ref !== authoritativeBatchArtifactRef.current
    ) return;
    if (
      initialBatch.revision === authoritativeBatchRevisionRef.current
      && authoritativeBatchRef.current
      && initialBatch.host_notification_status === authoritativeBatchRef.current.host_notification_status
      && initialBatch.ai_receipt_status === authoritativeBatchRef.current.ai_receipt_status
    ) return;
    authoritativeBatchRevisionRef.current = initialBatch.revision;
    authoritativeBatchRef.current = initialBatch;
    authoritativeBatchArtifactRef.current = data.review.anchor_feedback_batch_ref;
    setBatch(initialBatch);
    setSavedArtifactRef(data.review.anchor_feedback_batch_ref);
    setRecoveryRequired(false);
    setMessage("");
  }, [data.snapshotRevision, initialBatch, projectedBatch]);

  const handleAnchorTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>, currentIndex: number) => {
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % anchors.length;
    if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + anchors.length) % anchors.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = anchors.length - 1;
    if (nextIndex === null || nextIndex < 0) return;
    event.preventDefault();
    setActiveSlide(anchors[nextIndex].slide_id);
    anchorTabRefs.current[nextIndex]?.focus();
  };

  const updateSlice = useCallback((
    nextDrafts: AnchorFeedbackDraftState[],
    nextComposer: AnchorFeedbackComposerState | null,
  ) => {
    if (mutationRef.current || retryRequestRef.current || batch || recoveryRequired || !revisionIsWritable) return;
    onSliceChange(nextDrafts, nextComposer);
  }, [batch, onSliceChange, recoveryRequired, retryPending, revisionIsWritable]);

  const submit = async () => {
    if (!revisionIsWritable) {
      setMessage(invalidRevisionMessage);
      return;
    }
    if (!drafts.length || batch || recoveryRequired || hasUncommittedFeedback || mutationRef.current) return;
    const cachedRequest = retryRequestRef.current;
    if (
      cachedRequest
      && (
        cachedRequest.commandIdentity !== commandIdentity
        || cachedRequest.commandRevision !== revision
      )
    ) {
      retryRequestRef.current = null;
      setRetryPending(false);
      setMessage("当前视觉版本已变化；旧提交已失效，全部本地反馈仍保留，可重新提交。");
      return;
    }
    const request: AnchorWriteRequest = cachedRequest || (() => {
      const submittedDrafts = drafts.map((draft) => ({
        ...draft,
        normalized_region: { ...draft.normalized_region },
      }));
      const submittedFeedback: AnchorRegionFeedback[] = submittedDrafts.map((draft, index) => ({
        feedback_id: draft.feedback_id,
        anchor_slide_id: draft.anchor_slide_id,
        anchor_artifact_ref: data.review.anchor_slide_set_ref,
        normalized_region: draft.normalized_region,
        comment: draft.comment,
        order: index + 1,
        visual_source_version: data.review.source_version,
        revision,
        created_at: draft.created_at,
        created_by: "user",
      }));
      return {
        commandIdentity,
        commandRevision: revision,
        drafts: submittedDrafts,
        feedback: submittedFeedback,
        args: {
          projectRoot: data.selectedProjectRoot,
          expectedRevision: revision,
          reviewSessionId: data.review.review_session_id,
          sourceVersion: data.review.source_version,
          feedback: submittedFeedback,
        },
      };
    })();
    mutationRef.current = true;
    setSubmitting(true);
    setMessage("正在原子保存本轮反馈…");
    const commandRevision = request.commandRevision;
    const commandGeneration = ++generationRef.current;
    const submittedIdentity = request.commandIdentity;
    const commandIsCurrent = () => (
      mountedRef.current
      && generationRef.current === commandGeneration
      && identityRef.current === submittedIdentity
      && revisionRef.current === commandRevision
    );
    try {
      const result = await withReviewWriteDeadline((signal) => bridge.callTool(
        "submit_visual_anchor_feedback_batch",
        request.args,
        { signal },
      ));
      if (!commandIsCurrent()) return;
      const validated = validateAnchorFeedbackToolResult(result, data, request.feedback, commandRevision);
      if (!validated) {
        retryRequestRef.current = null;
        setRetryPending(false);
        setRecoveryRequired(true);
        setMessage("提交结果未闭合，请刷新/重新打开核对权威批次");
        return;
      }
      retryRequestRef.current = null;
      setRetryPending(false);
      authoritativeBatchRef.current = validated.batch;
      authoritativeBatchArtifactRef.current = validated.batchRef;
      setBatch(validated.batch);
      setSavedArtifactRef(validated.batchRef);
      highestObservedSnapshotRevisionRef.current = Math.max(
        highestObservedSnapshotRevisionRef.current,
        validated.revision,
      );
      authoritativeBatchRevisionRef.current = Math.max(
        authoritativeBatchRevisionRef.current,
        validated.batch.revision,
      );
      onRevision(validated.revision);
      onClearSlice();
      setMessage("反馈批次已保存");
    } catch (error) {
      if (!commandIsCurrent()) return;
      const code = isRecord(error) && typeof error.code === "string" ? error.code : "";
      if (isReviewWriteTimeout(error)) {
        retryRequestRef.current = request;
        setRetryPending(true);
        setMessage("保存请求超时；结果尚未确认，全部本地反馈仍保留。请使用相同内容重试。");
      } else if (code === "VISUAL_ANCHOR_FEEDBACK_RESULT_UNCLOSED") {
        retryRequestRef.current = null;
        setRetryPending(false);
        setRecoveryRequired(true);
        setMessage("提交结果未闭合，请刷新/重新打开核对权威批次");
      } else if (code === "REVISION_CONFLICT" || code === "REVIEW_SOURCE_STALE") {
        retryRequestRef.current = null;
        setRetryPending(false);
        setMessage("当前视觉版本已变化；全部本地反馈仍保留，请刷新后重试。");
      } else {
        setMessage("反馈尚未保存；全部本地反馈仍保留，可直接重试。");
      }
    } finally {
      if (commandIsCurrent()) {
        mutationRef.current = false;
        setSubmitting(false);
      }
    }
  };

  const installReceiptFact = (fact: "host" | "ai", nextRevision: number) => {
    const current = authoritativeBatchRef.current;
    if (!current || !savedArtifactRef) return;
    const next: AnchorFeedbackBatch = {
      ...current,
      ...(fact === "host"
        ? { host_notification_status: "sent" as const }
        : { ai_receipt_status: "received" as const }),
    };
    authoritativeBatchRef.current = next;
    highestObservedSnapshotRevisionRef.current = Math.max(highestObservedSnapshotRevisionRef.current, nextRevision);
    setBatch(next);
    onRevision(nextRevision);
  };

  return (
    <section ref={viewRef} className="anchor-results-view" aria-label="3 页锚点成果" tabIndex={-1}>
      <header className="visual-section-head">
        <div><h1>审核视觉锚点成果</h1><p>在真实渲染上拖动框选，可跨页积累多条意见后统一提交。</p></div>
      </header>
      <div className="anchor-review-layout">
        <div className="anchor-review-main anchor-workbench">
          <div className="anchor-tabs" role="tablist" aria-label="锚点页切换">
            {anchors.map((anchor, index) => (
              <button
                key={anchor.slide_id}
                data-anchor-tab={index + 1}
                ref={(node) => { anchorTabRefs.current[index] = node; }}
                id={`${instanceId}-anchor-slide-tab-${index}`}
                role="tab"
                aria-controls={`${instanceId}-anchor-slide-panel-${index}`}
                aria-selected={active?.slide_id === anchor.slide_id}
                tabIndex={active?.slide_id === anchor.slide_id ? 0 : -1}
                onKeyDown={(event) => handleAnchorTabKeyDown(event, index)}
                onClick={() => setActiveSlide(anchor.slide_id)}
              >
                {anchor.slide_id} 锚点页
              </button>
            ))}
          </div>
          {anchors.length ? anchors.map((anchor, index) => {
            const selected = active?.slide_id === anchor.slide_id;
            return (
              <div
                id={`${instanceId}-anchor-slide-panel-${index}`}
                role="tabpanel"
                aria-labelledby={`${instanceId}-anchor-slide-tab-${index}`}
                hidden={!selected}
                aria-hidden={!selected}
                data-anchor-logical-object={selected ? anchor.slide_id : undefined}
                key={anchor.slide_id}
              >
                {selected ? <RegionFeedbackEditor
                  bridge={bridge}
                  projectRoot={data.selectedProjectRoot}
                  slideId={anchor.slide_id}
                  assetRef={anchor.current_asset_ref}
                  drafts={drafts}
                  composer={composer}
                  disabled={draftsLocked}
                  onSliceChange={updateSlice}
                  toolbarActions={(
                    <div className="anchor-compare-control">
                      <button
                        className="anchor-compare-button"
                        type="button"
                        disabled={!anchor.previous_asset_ref}
                        onClick={() => setComparisonOpen(true)}
                      >与上一版对比</button>
                      {!anchor.previous_asset_ref ? <span>当前为首个可审核版本</span> : null}
                    </div>
                  )}
                /> : null}
              </div>
            );
          }) : <p className="visual-empty">当前视觉版本没有可审核的锚点成果。</p>}

        </div>
        <section className="anchor-batch-panel anchor-batch-inline feedback-panel" aria-label="本轮反馈批次">
            <header className="feedback-header"><h2>本轮反馈</h2><strong>{batch ? `${batch.items.length} 条已提交` : `${drafts.length} 条待提交`}</strong></header>
            {batch ? <p className="anchor-batch-id">{`反馈批次 ${batch.batch_id}`}</p> : null}
            {feedbackRecords.length ? (
              <ol className="anchor-draft-list feedback-batch-list feedback-scroll">
                {feedbackRecords.map((draft) => (
                  <li key={draft.feedback_id}>
                    <button type="button" onClick={() => setActiveSlide(draft.anchor_slide_id)}>{draft.anchor_slide_id}</button>
                    <p>{draft.comment}</p>
                    {!batch ? <button
                      type="button"
                      disabled={draftsLocked}
                      onClick={() => {
                        if (mutationRef.current || retryRequestRef.current || recoveryRequired || !revisionIsWritable) return;
                        onSliceChange(
                          drafts.filter((item) => item.feedback_id !== draft.feedback_id),
                          composer,
                        );
                      }}
                    >移除</button> : null}
                  </li>
                ))}
              </ol>
            ) : <p className="visual-empty">尚未加入反馈。先在任一锚点页拖动框选区域。</p>}
            <button className="visual-primary-action" type="button" disabled={!drafts.length || Boolean(batch) || submitting || recoveryRequired || hasUncommittedFeedback || !revisionIsWritable} onClick={submit}>
              {submitting ? "正在提交…" : batch ? "本轮反馈已冻结" : "提交本轮反馈"}
            </button>
            {hasUncommittedFeedback && !batch ? <p className="visual-operation-message">请先加入本轮反馈或放弃当前输入，再统一提交。</p> : null}
            {!revisionIsWritable ? <p className="visual-operation-message" role="alert">{invalidRevisionMessage}</p> : null}
            {message ? <p className="visual-operation-message" role="status">{message}</p> : null}
            {batch || recoveryRequired ? <section className="anchor-capability-facts" aria-label="宿主与回执能力">
              <h3>能力事实</h3>
              <p>宿主通知能力：{capabilityStatus(data.review.host_submission_capability)}</p>
              <p>AI 回执能力：{capabilityStatus(data.review.ai_receipt_capability)}</p>
            </section> : null}
            {batch || recoveryRequired ? <div className="visual-receipt-row" aria-label="反馈提交事实">
              <span>持久化：{recoveryRequired ? "无法确认，请刷新/重新打开" : batch ? "已保存" : "尚未提交"}</span>
              <span>宿主通知：{recoveryRequired ? "无法确认，请刷新/重新打开" : batch ? hostStatus(batch.host_notification_status) : "尚无批次回执"}</span>
              <span>AI 接收：{recoveryRequired ? "无法确认，请刷新/重新打开" : batch ? aiStatus(batch.ai_receipt_status) : "尚无批次回执"}</span>
              <strong>保存反馈不等于 G3 通过</strong>
            </div> : null}
            {batch ? <VisualReceiptRecoveryControls
              bridge={bridge}
              commandIdentity={commandIdentity}
              projectRoot={data.selectedProjectRoot}
              reviewSessionId={data.review.review_session_id}
              sourceVersion={data.review.source_version}
              revision={revision}
              savedArtifactRef={savedArtifactRef}
              hostStatus={batch.host_notification_status}
              aiStatus={batch.ai_receipt_status}
              hostCapability={data.review.host_submission_capability}
              aiCapability={data.review.ai_receipt_capability}
              onHostSent={(nextRevision) => installReceiptFact("host", nextRevision)}
              onAiReceived={(nextRevision) => installReceiptFact("ai", nextRevision)}
            /> : null}
          </section>
      </div>
      {comparisonOpen && active?.previous_asset_ref ? (
        <AnchorComparisonDialog
          bridge={bridge}
          projectRoot={data.selectedProjectRoot}
          slideId={active.slide_id}
          previousAssetRef={active.previous_asset_ref}
          currentAssetRef={active.current_asset_ref}
          onClose={closeComparison}
          fallbackFocusRef={viewRef}
        />
      ) : null}
    </section>
  );
}
