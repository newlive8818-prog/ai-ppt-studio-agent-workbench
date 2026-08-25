import { AlertTriangle, CheckCircle2, LoaderCircle, Send } from "lucide-react";

import type { ContentFullDeckReviewProjection } from "../../types/content-review";

interface Props {
  projection: ContentFullDeckReviewProjection;
  canSubmit: boolean;
  blockedReason: string;
  submitting: boolean;
  submitError: string;
  batchReceipt: string;
  followUpState: "idle" | "sending" | "failed" | "sent";
  onSubmit: () => void;
  onRetryFollowUp: () => void;
}

export function ReviewBatchFooter({
  projection,
  canSubmit,
  blockedReason,
  submitting,
  submitError,
  batchReceipt,
  followUpState,
  onSubmit,
  onRetryFollowUp,
}: Props) {
  const counts = projection.review_progress.counts;
  const batchSubmitted = projection.review_session.status === "submitted" || Boolean(batchReceipt);
  return (
    <footer className="review-batch-footer" aria-label="整批内容审核">
      <div className="review-batch-progress">
        <div>
          <span>本轮审核</span>
          <strong>{projection.review_progress.completed} / {projection.review_progress.total} 页已完成</strong>
          <small>sourceVersion {projection.source_version}</small>
        </div>
        <dl>
          <div><dt>认可</dt><dd>{counts.approved}</dd></div>
          <div><dt>修改</dt><dd>{counts.modify}</dd></div>
          <div><dt>缺证</dt><dd>{counts.evidence}</dd></div>
          <div><dt>删并</dt><dd>{counts.merge_or_delete}</dd></div>
        </dl>
      </div>

      {batchSubmitted ? (
        <div className={`review-batch-result ${followUpState}`}>
          {followUpState === "failed" ? <AlertTriangle size={20} /> : <CheckCircle2 size={20} />}
          <div>
            <strong>{followUpState === "failed" ? "审核批次已持久化；Codex 后续消息尚未发送。" : "已提交，等待整套修改方案。"}</strong>
            <p>当前批次已冻结，不会直接改稿，也不会自动确认 G0。</p>
            {batchReceipt ? <code className="content-review-persistence-receipt">持久化回执 {batchReceipt}</code> : null}
          </div>
          {followUpState === "failed" ? <button type="button" onClick={onRetryFollowUp}><Send size={15} />重试发送给 Codex</button> : null}
        </div>
      ) : (
        <div className="review-batch-action">
          <div>
            <strong>全部页面判断完成后，再一次性交给 Codex</strong>
            <p>{blockedReason || "将提交一个不可变审核批次，由总师先在 Codex 对话中形成整套修改方案。"}</p>
          </div>
          <button type="button" disabled={!canSubmit || submitting} onClick={onSubmit}>
            {submitting ? <LoaderCircle size={17} /> : <Send size={17} />}
            完成本轮审核，交给 Codex 集中处理
          </button>
        </div>
      )}
      <dl className="content-review-receipt-status" aria-label="审核回执状态">
        <div><dt>宿主打开</dt><dd>{projection.review_session.host_open_status}</dd></div>
        <div><dt>Runtime 持久化</dt><dd>{projection.review_session.persistence_status}</dd></div>
        <div><dt>宿主通知</dt><dd>{projection.review_session.host_notification_status}</dd></div>
        <div><dt>AI 接收</dt><dd>{projection.review_session.ai_receipt_status}</dd></div>
      </dl>
      {submitError ? <p className="review-batch-error" role="alert">{submitError}</p> : null}
    </footer>
  );
}
