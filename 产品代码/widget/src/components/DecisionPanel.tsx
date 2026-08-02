import { ArrowRight, MessageSquareText } from "lucide-react";

import type { ProjectSnapshot } from "../types";

interface Props {
  decision: ProjectSnapshot["current_decision"];
  selected: string;
  feedback: string;
  submitting: boolean;
  onSelected: (value: string) => void;
  onFeedback: (value: string) => void;
  onSubmit: () => void;
}

export function DecisionPanel({ decision, selected, feedback, submitting, onSelected, onFeedback, onSubmit }: Props) {
  return (
    <section className="decision-panel" aria-labelledby="decision-title">
      <div className="section-kicker"><MessageSquareText size={16} />需要你的判断</div>
      <h2 id="decision-title">{decision.question}</h2>
      {decision.why_now && <p className="decision-why">为什么现在：{decision.why_now}</p>}
      <fieldset>
        <legend className="sr-only">请选择一个判断</legend>
        {(decision.options || []).map((option) => (
          <label key={option} className={selected === option ? "decision-option selected" : "decision-option"}>
            <input type="radio" name="decision" value={option} checked={selected === option} onChange={() => onSelected(option)} />
            <span>{option}</span>
            {option === decision.recommended_choice && <small>AI 推荐</small>}
          </label>
        ))}
      </fieldset>
      <label className="feedback-field">
        <span>补充意见（可选）</span>
        <textarea value={feedback} onChange={(event) => onFeedback(event.target.value)} placeholder="复杂修改会在保存后交给 Codex 继续理解" rows={2} />
      </label>
      <button className="primary-button" type="button" disabled={!selected || submitting} onClick={onSubmit}>
        {submitting ? "正在保存…" : "提交当前判断"}<ArrowRight size={17} />
      </button>
      <p className="reversible-note">可撤销 · 保存后生成新 revision · 不覆盖历史决定</p>
    </section>
  );
}
