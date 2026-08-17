# Evidence-first presales content workflow

## Mission and material mode

Finish what the presentation says before deciding how it looks.

1. Save `MissionDraft` with `save_ai_ppt_mission_draft` and show the complete current task card.
2. Obtain `MissionConfirmation` through a verified user action or host-native confirmation. A complete draft is only `confirmable`; confirmation intent is not evidence.
3. Register only user-provided sources and preserve their identities, hashes, exclusions, conflicts, unknowns, and prohibited extrapolations.
4. Derive one current mode: `material-backed` when critical claims are sufficiently grounded, `mixed-evidence` when facts and explicit gaps coexist, or `proposal-led` when the user has confirmed no current customer material.

Across all modes, keep source fact, source-derived inference, `诊断假设`, `方案建议`, `待联合验证`, conflict, unknown, and gap distinguishable. Never invent customer facts, numbers, cases, capabilities, results, or commitments.

## Presales chief and four current objects

Let the presales chief own the complete reasoning chain and write one current authority per object:

1. `PresalesEvidenceBook`: sources, supported facts, inferences, conflicts, unknowns, evidence gaps, exclusions, and mode.
2. `CustomerDecisionContext`: audience, decision stage, business issue, questions, constraints, desired action, and evidence-book reference.
3. `ProblemSolutionFitMap`: traceable current-state, problem, requirement, proposal, value hypothesis, and validation path.
4. `ReadingDeckBlueprint`: final page order, neutral title, page task, visible copy, speaker notes, evidence bindings, cross-page relations, identity labels, and media intent.

Write in that order and bind every object to exact current `artifact://<kind>/<sha256>` upstream heads. Use specialists only for a concrete uncertainty or a high-impact `RevisionProposal`; a specialist recommendation cannot write the blueprint or approve its own work.

## Two hard gates and repair

Run `run_content_evidence_gate` and `run_content_presales_reading_gate` on the current `ReadingDeckBlueprint`. Both are binary and source-version-bound. A failure produces actionable requirements; use `repair_reading_deck_blueprint`, preserve repair history, publish a new source version, and rerun every invalidated gate. A score, fixture, or reviewer count cannot compensate for a failed check.

## Full-deck review and G0

After both hard gates pass:

1. Open or resume one current `content-full-deck` ReviewSession.
2. Project every page without summarizing away visible copy, notes, evidence bindings, identities, or cross-page relations.
3. Let users open each source through the read-only evidence layer. It belongs to the parent review, writes no `PageDecision`, and creates no second evidence judgment.
4. Save one current `PageDecision` per slide, then submit one immutable `ContentReviewBatch`.
5. If all decisions are approved, open G0 review. If any request change, save and explicitly confirm one `ContentBatchRevisionPlan`, create one change set, publish the new blueprint source version, and reopen review.

Saving decisions, submitting a Batch, opening evidence, or notifying the host never passes G0. Confirm G0 only for the current all-approved Batch through an explicit user judgment with a real host-verified reference. Begin visual work only after G0 passes.
