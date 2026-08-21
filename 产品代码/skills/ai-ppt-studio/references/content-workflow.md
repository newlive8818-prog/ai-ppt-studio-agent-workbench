# Evidence-first presales content workflow

## Preconditions

Formal content work requires the current trusted `MissionConfirmation` and current material identity. It does not require a separate framework confirmation or a full-deck expansion authorization.

Select one material mode:

- `material-backed`: relatively sufficient customer/project evidence;
- `mixed-evidence`: facts and material gaps coexist;
- `proposal-led`: no current customer material.

All three modes continue through complete content production, internal hard gates, sidebar review, and G0.

## Production authority

One `售前方案总师` owns the complete content line. On-demand specialists may answer bounded risk questions, but they are not a fixed production pipeline and do not divide final responsibility.

The chief may delete, downgrade, or rewrite an intended conclusion that lacks evidence. Unsupported content may remain only as `材料推断`, `诊断假设`, `方案建议`, or `待联合验证`. It cannot become customer fact, proven fit, result, or commitment.

## Required production order

1. Build `PresalesEvidenceBook`: facts, sources, conflicts, unknowns, gaps, exclusions, and forbidden extrapolations.
2. Build `CustomerDecisionContext`: audience, decision stage, current business matter, consensus, decision questions, constraints, and unresolved questions.
3. Build `ProblemSolutionFitMap`: situation, symptoms, causes/hypotheses, impacts, constraints, derived requirements, solution components, mappings, boundaries, alternatives, and validation.
4. Build the complete `ReadingDeckBlueprint` with neutral titles, all visible copy, identity labels, evidence, analysis/proposals, solution mappings, page relations, and speaker notes.
5. Run the `事实与证据硬门`.
6. Run the `售前阅读与客户立场硬门`.
7. The chief repairs failures and reruns every affected hard gate until both pass.
8. Publish the passing source to the existing full-deck sidebar review.

Evidence determines what the system may conclude. Never choose evidence after fixing a persuasive proposition.

## Identity vocabulary

Use the same identity throughout visible copy, notes, review, and G0:

- `来源事实`
- `材料推断`
- `用户已确认`
- `诊断假设`
- `方案建议`
- `待联合验证`
- `证据缺口`
- `禁止使用`

Material absence is not a hard-gate failure. Fabrication, nonexistent citations, identity impersonation, unsupported capability/fit, or guaranteed outcome is a failure.

## Neutral titles

Titles state factual objects, material scope, business matters, problem domains, solution components, work stages, validation matters, or next-step work.

Do not place unsupported causality, superiority, necessity, uniqueness, or customer action decisions in titles. Put judgments inside the page and label them as material observation, AI analysis, diagnostic hypothesis, proposal, or joint validation.

## Hard-gate truthfulness

Hard-gate reviewers do not edit the blueprint. They return `passed` or `failed` with structured repair requirements.

If a review is described as an independent Agent review, preserve a real independent instance ID, isolated context/hash, input source/hash, and output record. Without those records, label it `isolated-review-task`.

## Sidebar review and G0

Keep the approved full-deck review interaction:

- complete continuous deck at maximum sidebar width;
- full visible copy, real evidence, sources, notes, reading quality, and page relations;
- one `approved | modify | evidence | merge-or-delete` decision per page;
- comments required for every non-approved decision;
- `save_content_page_decision` is a silent page save: it persists only the current decision/comment, sends no follow-up, and never changes content or Gate state;
- all pages complete before `submit_content_review_batch` creates one immutable review batch and one concentrated Codex follow-up;
- the chief uses `save_content_batch_revision_plan` to produce one deck-level revision plan for the entire submitted batch;
- the user confirms that plan through `confirm_content_batch_revision_plan` before any content change;
- chief revises and reruns necessary gates;
- every new source version receives full re-review;
- final current source is confirmed at G0 in chat.

Saving a page, submitting a batch, confirming a revision plan, or confirming the mission never confirms G0.

Do not discuss or produce formal visual work before G0 passes.

## Pause conditions

Pause only for critical source conflict, materially different diagnosis branches, a high-impact scope/commitment change, or inability to converge. A missing material or ordinary evidence gap is not a pause condition; convert it into a hypothesis, option, validation question, material request suggestion, or joint validation action and continue.

## Legacy compatibility

`PresalesContentStrategy`, `ClaimEvidenceMap`, `DeckArgumentMap`, `SlideDraftSet`, framework confirmations, and expansion authorizations may be read from historical projects during migration. New projects must not use them as required authority or recreate the fixed multi-agent pipeline.
