import { useState } from "react";

import type { ContentDecisionChoice, ContentPageDecision } from "../types/content-review";

export const contentDecisionChoices: ReadonlyArray<{ value: ContentDecisionChoice; label: string }> = [
  { value: "approved", label: "认可本页" },
  { value: "modify", label: "需要修改" },
  { value: "evidence", label: "证据不足" },
  { value: "merge-or-delete", label: "考虑删页/合页" },
];

interface Props {
  slideId: string;
  decision: ContentDecisionChoice | "";
  comment: string;
  saved?: ContentPageDecision;
  dirty: boolean;
  saving: boolean;
  message: string;
  disabled: boolean;
  saveDisabled: boolean;
  onDecisionChange: (decision: ContentDecisionChoice) => void;
  onCommentChange: (comment: string) => void;
  onSave: () => Promise<boolean>;
}

export function PageDecisionControl({
  slideId,
  decision,
  comment,
  saved,
  dirty,
  saving,
  message,
  disabled,
  saveDisabled,
  onDecisionChange,
  onCommentChange,
  onSave,
}: Props) {
  const [editingSavedComment, setEditingSavedComment] = useState(false);
  const needsComment = Boolean(decision && decision !== "approved");
  const showSavedComment = needsComment && Boolean(saved) && !dirty && !editingSavedComment;
  const controlsDisabled = disabled || saving;
  const commentCounterId = `decision-comment-count-${slideId}`;

  const save = async () => {
    if (await onSave()) setEditingSavedComment(false);
  };

  return (
    <fieldset className="page-decision-editor">
      <legend>本页审核判断 · {slideId}</legend>
      <div className="page-decision-options">
        {contentDecisionChoices.map((choice) => {
          const selected = decision === choice.value;
          return (
            <label
              className={`page-decision-option page-decision-option--${choice.value}${selected ? " is-selected" : ""}`}
              key={choice.value}
            >
              <input
                type="radio"
                name={`decision-${slideId}`}
                value={choice.value}
                checked={selected}
                disabled={controlsDisabled}
                onChange={() => {
                  setEditingSavedComment(choice.value !== "approved");
                  onDecisionChange(choice.value);
                }}
              />
              <span>{choice.label}</span>
            </label>
          );
        })}
      </div>

      {needsComment && !showSavedComment ? (
        <label className="page-decision-comment">
          <span>{slideId} 审核意见</span>
          <textarea
            aria-label={`${slideId} 审核意见`}
            aria-describedby={commentCounterId}
            value={comment}
            disabled={controlsDisabled}
            onChange={(event) => onCommentChange([...event.target.value].slice(0, 1200).join(""))}
          />
          <small id={commentCounterId}>{[...comment].length}/1200</small>
        </label>
      ) : null}

      {showSavedComment ? (
        <div className="page-decision-saved-comment">
          <p>{saved?.comment}</p>
          <button type="button" disabled={controlsDisabled} onClick={() => setEditingSavedComment(true)}>编辑意见</button>
        </div>
      ) : null}

      <div className="page-decision-actions">
        <button
          type="button"
          disabled={disabled || saveDisabled || saving || !dirty || !decision || (decision !== "approved" && !comment.trim())}
          onClick={save}
        >保存本页判断</button>
        <span role="status">{message}</span>
      </div>
    </fieldset>
  );
}
