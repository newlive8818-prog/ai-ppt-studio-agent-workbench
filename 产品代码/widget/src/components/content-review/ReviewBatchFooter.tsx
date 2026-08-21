import { AlertTriangle, CheckCircle2, LoaderCircle, Send } from "lucide-react";

import type { ContentFullDeckProjection } from "../../types";

interface Props {
  projection: ContentFullDeckProjection;
  canSubmit: boolean;
  blockedReason: string;
  submitting: boolean;
  submitError: string;
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
  followUpState,
  onSubmit,
  onRetryFollowUp,
}: Props) {
  const counts = projection.review_progress.counts;
  const batchSubmitted = projection.current_batch.status !== "draft"
    || projection.phase !== "full-deck-review-ready";
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

      {batchSubmitted || followUpState !== "idle" ? (
        <div className={`review-batch-result ${followUpState}`}>
          {followUpState === "failed" ? <AlertTriangle size={20} /> : <CheckCircle2 size={20} />}
          <div>
            <strong>{followUpState === "failed" ? "审核批次已提交；Codex 后续消息尚未发送。" : "已提交，等待整套修改方案。"}</strong>
            <p>当前批次已冻结，不会直接改稿，也不会自动确认 G0。</p>
          </div>
          {followUpState === "failed" ? <button type="button" onClick={onRetryFollowUp}><Send size={15} />重试发送给 Codex</button> : null}
        </div>
      ) : (
        <div className="review-batch-action">
          <div>
            <strong>全部页面判断完成后，再一次性交给 Codex</strong>
            <p>{blockedReason || "将提交一个不可变审核批次，由总师先形成整套修改方案。"}</p>
          </div>
          <button type="button" disabled={!canSubmit || submitting} onClick={onSubmit}>
            {submitting ? <LoaderCircle size={17} /> : <Send size={17} />}
            完成本轮审核，交给 Codex 集中处理
          </button>
        </div>
      )}
      {submitError ? <p className="review-batch-error" role="alert">{submitError}</p> : null}
    </footer>
  );
}
