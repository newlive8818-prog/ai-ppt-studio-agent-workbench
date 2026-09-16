# Evidence-first presales content workflow

## Mission and material mode

Finish what the presentation says before deciding how it looks.

1. Save `MissionDraft` with `save_ai_ppt_mission_draft` and show the complete current task card.
2. Obtain `MissionConfirmation` through a verified user action or host-native confirmation. A complete draft is only `confirmable`; confirmation intent is not evidence.
3. Register only user-provided sources and preserve their identities, hashes, exclusions, conflicts, unknowns, and prohibited extrapolations.
4. Derive one current mode: `material-backed` when critical claims are sufficiently grounded, `mixed-evidence` when facts and explicit gaps coexist, or `proposal-led` when the user has confirmed no current customer material.

Across all modes, keep source fact, source-derived inference, `诊断假设`, `方案建议`, `待联合验证`, conflict, unknown, and gap distinguishable. Never invent customer facts, numbers, cases, capabilities, results, or commitments.

Evidence determines what the system may conclude. The chief deletes, downgrades, or rewrites unsupported intended conclusions; they may remain only as a labeled inference, hypothesis, proposal, validation item, gap, or prohibited extrapolation. Never select evidence after fixing a persuasive conclusion.

Use the internal identity vocabulary consistently: `来源事实`, `材料推断`, `用户已确认`, `诊断假设`, `方案建议`, `待联合验证`, `证据缺口`, and `禁止使用`. Missing material is not itself a hard-gate failure; fabrication, nonexistent citation, identity impersonation, unsupported capability/fit, or guaranteed outcome is.

## Presales chief and four current objects

Let the presales chief own the complete reasoning chain and write one current authority per object:

1. `PresalesEvidenceBook`: sources, supported facts, inferences, conflicts, unknowns, evidence gaps, exclusions, and mode.
2. `CustomerDecisionContext`: audience, decision stage, business issue, questions, constraints, desired action, and evidence-book reference.
3. `ProblemSolutionFitMap`: traceable current-state, problem, requirement, proposal, value hypothesis, and validation path.
4. `ReadingDeckBlueprint`: final page order, neutral title, page task, visible copy, speaker notes, evidence bindings, cross-page relations, identity labels, and media intent.

Write in that order and bind every object to exact current `artifact://<kind>/<sha256>` upstream heads. Use specialists only for a concrete uncertainty or a high-impact `RevisionProposal`; a specialist recommendation cannot write the blueprint or approve its own work.

Use neutral titles for factual objects, material scope, business matters, problem domains, solution components, work stages, validation matters, or next-step work. Do not put unsupported causality, superiority, necessity, uniqueness, or customer action decisions in titles; keep judgments inside the page and label their identity.

## Two hard gates and repair

Run `run_content_evidence_gate` and `run_content_presales_reading_gate` on the current `ReadingDeckBlueprint`. Both are binary and source-version-bound. A failure produces actionable requirements; use `repair_reading_deck_blueprint`, preserve repair history, publish a new source version, and rerun every invalidated gate. A score, fixture, or reviewer count cannot compensate for a failed check.

Hard-gate reviewers never edit the blueprint. If a result is called an independent Agent review, preserve the real independent instance identity, isolated context/hash, exact input source/hash, and output record; otherwise label it `isolated-review-task`.

## Full-deck review and G0

After both hard gates pass:

1. Open or resume one current `content-full-deck` ReviewSession.
2. Keep `ReadingDeckBlueprint` complete as the internal governance authority, but project only the accepted `ContentReviewPageViewModel`: page goal, desired customer judgment, actual page text, optional real material/page visuals, and the current page decision. Do not expose speaker notes, evidence identities or source-entry UI, analysis/proposal catalogs, mappings, cross-page relations, reading-quality fields, or the complete backend field catalog.
3. When a page has no real reviewable visual, omit the image region, its title, and any large empty state; expand “页面实际文字” to the full row. Zero images are valid in every material mode and do not imply insufficient evidence. Do not fill the gap with decorative, network, or AI-generated imagery.
4. Save exactly one `approved | modify | evidence | merge-or-delete` `PageDecision` per slide. Every non-approved decision requires a comment. `save_content_page_decision` is silent: it persists only that current decision/comment, sends no follow-up, changes no content, and confirms no Gate.
5. Only after every page is decided, submit one immutable `ContentReviewBatch`; only that complete Batch starts concentrated processing.
6. If all decisions are approved, open G0 review. If any requests change, the chief saves one whole-deck `ContentBatchRevisionPlan`; the user explicitly confirms it before one change set is created. Publish a new blueprint source version, rerun invalidated hard gates, and fully re-review every page with no inherited approvals.

Saving decisions, submitting a Batch, confirming a revision plan, or notifying the host never passes G0. Confirm G0 only for the current all-approved Batch through an explicit user judgment with a real host-verified reference. Begin visual work only after G0 passes.

## Pause conditions

Pause only for a critical source conflict, materially divergent diagnosis branches, a high-impact scope or commitment change, or inability to converge. An ordinary evidence gap does not pause complete content work; convert it into a hypothesis, option, validation question, material request suggestion, or joint-validation action.

## Legacy compatibility

`PresalesContentStrategy`, `ClaimEvidenceMap`, `DeckArgumentMap`, `SlideDraftSet`, framework confirmations, expansion authorizations, and legacy review objects are read-only migration inputs. New work must not recreate them as authority, a fixed multi-Agent pipeline, a separate evidence page, or another primary surface.
