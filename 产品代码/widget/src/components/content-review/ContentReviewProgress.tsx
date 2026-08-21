import { CheckCircle2, FileStack, ShieldCheck } from "lucide-react";

import type { ContentProgressProjection } from "../../types";

interface Props {
  projection: ContentProgressProjection;
}

export function ContentReviewProgress({ projection }: Props) {
  const checking = projection.phase === "content-hard-gate-review";
  return (
    <article className="content-review-progress" aria-live="polite">
      <div className="content-progress-mark" aria-hidden="true">
        {checking ? <ShieldCheck /> : <FileStack />}
      </div>
      <div className="content-progress-copy">
        <p className="content-progress-stage">{checking ? "内部硬门" : "完整内容生产"}</p>
        <h2>{checking ? "内容正在内部检查" : "正在生成完整内容"}</h2>
        <p>
          {checking
            ? "事实与证据、售前阅读与客户立场正在独立检查。失败稿不会进入逐页审核。"
            : "售前方案总师正在形成可独立阅读的完整逐页内容。"}
        </p>
        <dl>
          <div><dt>汇报主题</dt><dd>{projection.mission_summary.topic || "正在确认"}</dd></div>
          <div><dt>汇报对象</dt><dd>{projection.mission_summary.primary_audience || "正在确认"}</dd></div>
          <div><dt>决策事项</dt><dd>{projection.mission_summary.decision_question_or_next_action || "正在确认"}</dd></div>
        </dl>
        <p className="content-progress-boundary"><CheckCircle2 size={15} />内部通过后，这里会一次展示完整全稿；当前不提前泄露逐页内容。</p>
      </div>
    </article>
  );
}
