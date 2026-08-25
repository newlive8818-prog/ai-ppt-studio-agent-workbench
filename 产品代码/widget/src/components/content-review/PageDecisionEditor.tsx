import { memo, useEffect, useMemo, useState } from "react";
import { Check, LoaderCircle, Pencil, Save } from "lucide-react";

import type {
  ContentDecisionSaveStatus,
  ContentDecisionState,
  ContentPageDecision,
} from "../../types/content-review";

export interface PageDecisionEditorMeta {
  dirty: boolean;
  completed: boolean;
  saveStatus: ContentDecisionSaveStatus;
  conflict: boolean;
}

interface Props {
  slideId: string;
  savedState: ContentDecisionState;
  onSave: (
    slideId: string,
    decision: ContentPageDecision,
    comment: string,
  ) => Promise<void>;
  onMetaChange: (slideId: string, meta: PageDecisionEditorMeta) => void;
}

const OPTIONS: Array<{ value: ContentPageDecision; label: string; hint: string }> = [
  { value: "approved", label: "认可本页", hint: "内容可保留" },
  { value: "modify", label: "需要修改", hint: "说明具体改法" },
  { value: "evidence", label: "证据不足", hint: "指明缺口与所需依据" },
  { value: "merge-or-delete", label: "考虑删页/合页", hint: "说明删除或合并建议" },
];

const LABEL_BY_VALUE = new Map(OPTIONS.map((option) => [option.value, option.label]));

function codePointLength(value: string) {
  return Array.from(value).length;
}

function PageDecisionEditorComponent({ slideId, savedState, onSave, onMetaChange }: Props) {
  const [baseline, setBaseline] = useState(() => ({
    selected: savedState.selected,
    comment: savedState.comment,
    completed: savedState.completed,
  }));
  const [selected, setSelected] = useState<ContentPageDecision | "">(savedState.selected);
  const [comment, setComment] = useState(savedState.comment);
  const [editing, setEditing] = useState(!savedState.saved || !savedState.completed);
  const [saveStatus, setSaveStatus] = useState<ContentDecisionSaveStatus>(savedState.saved ? "saved" : "idle");
  const [error, setError] = useState("");

  const dirty = selected !== baseline.selected || comment !== baseline.comment;
  const commentLength = useMemo(() => codePointLength(comment), [comment]);
  const completed = saveStatus === "saved" ? Boolean(selected) : baseline.completed && !dirty;

  useEffect(() => {
    if (saveStatus === "pending" || dirty) return;
    setBaseline({
      selected: savedState.selected,
      comment: savedState.comment,
      completed: savedState.completed,
    });
    setSelected(savedState.selected);
    setComment(savedState.comment);
    setSaveStatus(savedState.saved ? "saved" : "idle");
    if (savedState.saved && savedState.completed) setEditing(false);
  }, [dirty, saveStatus, savedState.comment, savedState.completed, savedState.saved, savedState.selected]);

  useEffect(() => {
    onMetaChange(slideId, {
      dirty,
      completed,
      saveStatus,
      conflict: saveStatus === "conflict",
    });
  }, [completed, dirty, onMetaChange, saveStatus, slideId]);

  function choose(value: ContentPageDecision) {
    if (savedState.frozen) return;
    setSelected(value);
    setComment((current) => value === "approved" ? "" : current);
    setEditing(true);
    setError("");
    setSaveStatus("idle");
  }

  async function save() {
    if (!selected || savedState.frozen || saveStatus === "pending") return;
    const normalized = comment.trim();
    if (selected !== "approved" && !normalized) {
      setError("请输入具体意见后再保存。");
      return;
    }
    if (commentLength > 1200) {
      setError("意见最多 1200 个字符。");
      return;
    }
    setSaveStatus("pending");
    setError("");
    try {
      const savedComment = selected === "approved" ? "" : normalized;
      await onSave(slideId, selected, savedComment);
      setComment(savedComment);
      setBaseline({ selected, comment: savedComment, completed: true });
      setSaveStatus("saved");
      setEditing(false);
    } catch (caught) {
      const code = (caught as Error & { code?: string }).code || "";
      const conflict = code === "REVISION_CONFLICT"
        || code === "CONTENT_REVIEW_CONFLICT"
        || code === "CONTENT_REVIEW_BATCH_STALE";
      setSaveStatus(conflict ? "conflict" : "failed");
      setError(
        conflict
          ? "内容版本已变化；你的选择和意见仍保留，请查看差异后重试。"
          : "本页判断尚未保存；选择和意见仍保留，可直接重试。",
      );
    }
  }

  const showSavedSummary = savedState.frozen || (!editing && completed && Boolean(selected));
  return (
    <section className={`page-decision-editor decision-question ${savedState.frozen ? "frozen" : ""}`} aria-label={`页面 ${slideId} 审核判断`}>
      <header>
        <div>
          <span>本页判断</span>
          <strong>{savedState.frozen ? "已随批次冻结" : "阅读完整内容后做一个判断"}</strong>
        </div>
        {saveStatus === "pending" ? <small><LoaderCircle size={14} />保存中</small> : null}
        {saveStatus === "saved" && !dirty ? <small className="saved"><Check size={14} />已保存</small> : null}
      </header>

      {showSavedSummary ? (
        <div className="decision-saved-summary saved-feedback">
          <div><Check size={17} /><strong>{selected ? LABEL_BY_VALUE.get(selected) : "已判断"}</strong></div>
          {comment ? <p>{comment}</p> : <p>本页已认可，没有额外意见。</p>}
          {!savedState.frozen ? (
            <button type="button" onClick={() => setEditing(true)}><Pencil size={14} />编辑意见</button>
          ) : null}
        </div>
      ) : (
        <>
          <fieldset className="page-decision-options actions" disabled={savedState.frozen || saveStatus === "pending"}>
            <legend className="sr-only">选择本页判断</legend>
            {OPTIONS.map((option) => (
              <label key={option.value} className={selected === option.value ? "selected" : ""}>
                <input
                  type="radio"
                  name={`decision-${slideId}`}
                  value={option.value}
                  aria-label={option.label}
                  checked={selected === option.value}
                  onChange={() => choose(option.value)}
                />
                <span>{option.label}</span>
                <small>{option.hint}</small>
              </label>
            ))}
          </fieldset>

          {selected && selected !== "approved" ? (
            <label className="decision-comment-field feedback-editor">
              <span>审核意见 <b>必填</b></span>
              <textarea
                aria-label="审核意见"
                rows={4}
                value={comment}
                disabled={savedState.frozen || saveStatus === "pending"}
                onChange={(event) => {
                  setComment(event.target.value);
                  setError("");
                  setSaveStatus("idle");
                }}
                placeholder={selected === "evidence"
                  ? "说明哪个判断缺什么证据，希望补充什么材料。"
                  : selected === "merge-or-delete"
                    ? "说明建议删除，还是与哪一页合并，以及需保留的内容。"
                    : "说明需要修改的文字、逻辑、材料或页面目标。"}
              />
              <small className={commentLength > 1200 ? "over" : ""}>{commentLength} / 1200</small>
            </label>
          ) : null}

          {error ? <p className="decision-editor-error" role="alert">{error}</p> : null}
          <button
            className="decision-save-button"
            type="button"
            disabled={!selected || savedState.frozen || saveStatus === "pending"}
            onClick={save}
          >
            {saveStatus === "pending" ? <LoaderCircle size={16} /> : <Save size={16} />}
            保存本页判断
          </button>
        </>
      )}
    </section>
  );
}

export const PageDecisionEditor = memo(PageDecisionEditorComponent);
