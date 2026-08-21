---
name: ai-ppt-studio
description: Create, resume, govern, review, revise, render, validate, and deliver isolated reading-first presales PPT/PPTX projects with AI PPT Studio v2.2. Use for evidence-bound content architecture, on-demand content or visual professional review, native editable PowerPoint production, release-target validation, delivery, and project experience retrospective.
---

# AI PPT Studio v2.2

Act as the principal strategist and maker. Let the user supply goals, sources, consequential choices, feedback, and final acceptance. Let the Runtime own revision, immutable artifacts, evidence, recovery, and G0–G4. Never infer a passed Gate from chat, UI, fixtures, or local rendering.

## Start safely

1. Read `references/isolation-policy.md` before any write and `references/runtime-workflow.md` before project operations.
2. Read `references/native-workbench.md` before reporting status or opening a professional review.
3. Read the stage reference needed now: `content-workflow.md`, `visual-workflow.md`, `presentations-handoff.md`, `review-and-feedback.md`, `release-target-policy.md`, or `experience-evolution.md`.
4. Run `python3 scripts/ai_ppt_runtime.py preflight` and use the configured managed runtime root.
5. Create or resume one schema 3 project below that root. Never write into the current working directory unless it is that managed project. Treat every user original as read-only; copy it into the project before transformation.
6. Use only user-supplied customer material. Do not search the internet for customer-project facts.

## Preserve authority

- Use `artifact://<kind>/<sha256>` references that resolve in the current project and match the required kind and current head.
- Treat Python schema 3 as the only business writer, Node MCP as a validated adapter, and React as a projection consumer.
- Send `expectedRevision` and one idempotent command identity with every write. Refresh after success, `REVISION_CONFLICT`, or `REVIEW_SOURCE_STALE`.
- Formal Agent tasks bind one approved role, exact input refs, bounded instructions, output contract, exclusions, and isolation rules.
- Keep producer and reviewer contexts isolated. Applicable hard checks are binary; scores or votes cannot compensate for a failure.
- Bind every user confirmation to one current checkpoint, exact `sourceVersion`, current revision, and single-use challenge. `MissionConfirmation` never confirms G0, G3, or G4; an old, reused, replayed, or model-invented message/action cannot pass a Gate.
- Permit `legacy-credential-upgrade` only for an already-passed historical G0 whose frozen acceptance and blueprint refs still equal current heads and whose credential is strictly old-format. Require a fresh host confirmation of the current challenge, replace only the credential, and use the normal G0 reopen path after any content drift.
- Resolve the immutable project-bound `ReleaseTargetPolicy` before G2 and again before G4. Its `required_target_ids` are the only Gate target source; the public Agent cannot supply arbitrary targets or shrink, expand, or replace the policy.

## Route capabilities honestly

- Use GPT for audience understanding, evidence reasoning, presales strategy, content, visual reasoning, critique, and scoped revision.
- Use Codex Presentations for every PPTX read, create, edit, render, and inspection. Do not build or use a second PPTX editor. Never use `python-pptx`.
- Use Image 2 only after native-first structure is frozen, and only for replaceable non-semantic backgrounds, textures, illustrations, or light effects. Never rasterize factual text, numbers, evidence, or business relationships.
- No separate Image 2 privacy gate exists. Project materials may be used only inside the approved project task and media boundary.

## Execute the governed loop

### 1. Confirm Mission and material identity

Save an AI-authored `MissionDraft`, show the task, audience, desired judgment/action, materials or explicit no-material choice, background, constraints, red lines, and unknowns, then obtain a real host-verified `MissionConfirmation`. After the current complete `confirmable` card is shown and confirmation is the sole pending high-impact action, `OK / 确认 / 采纳 / 继续` may express confirmation intent. An ordinary conversation does not. Intent words are never persisted as evidence.

Call `confirm_ai_ppt_mission`; use host-native confirmation when no verified message adapter exists. On `HOST_CONFIRMATION_DECLINED` or `HOST_CONFIRMATION_UNAVAILABLE`, make no business write, preserve the task, and retry; never ask for more material, and never bypass AI PPT Studio merely because host confirmation is unavailable.

Classify the current content work as `material-backed`, `mixed-evidence`, or `proposal-led`. Preserve source fact, source-derived inference, `诊断假设`, `方案建议`, `待联合验证`, conflict, gap, and prohibited extrapolation as distinct identities. Never invent customer facts, numbers, cases, capabilities, results, or commitments.

Before requesting any formal content Agent task and again before committing its artifact, pass the Python content precondition against the current Mission and material identity. Node, React, Browser, prompts, fixtures, or direct adapter calls cannot bypass this gate.

### 2. Build and review content before visual work

Read `references/content-workflow.md`. Let the presales chief produce, in order, `PresalesEvidenceBook`, `CustomerDecisionContext`, `ProblemSolutionFitMap`, and `ReadingDeckBlueprint`. Invoke specialists only for a concrete uncertainty or high-impact `RevisionProposal`; do not require a fixed content Agent roster.

Pass both the evidence hard gate and presales-reading hard gate. Open one `content-full-deck` ReviewSession only after the current blueprint passes. Collect one `PageDecision` per slide, submit one immutable review Batch, and when changes are requested confirm a Batch revision plan, create the change set, publish a new source version, and reopen review. Saving review data never confirms G0. Confirm G0 only from an explicit current user judgment with a real host-verified reference. Do not discuss visual style before G0 passes.

If a hard-gate review is described as an independent Agent review, preserve the real independent instance identity, isolated context/hash, exact input version/hash, and output record; otherwise call it an isolated review task. One Agent turn must stop at the next later user Gate unless a new host verification or elicitation result is received after that current review source was published.

### 3. Build the visual contract and anchors

Read `references/visual-workflow.md`. Create the complete `DeckDesignSystem` and every `SlideVisualContract`; pass internal G1 checks. Use Codex Presentations for native editable anchors, then validate every target required by the current immutable `ReleaseTargetPolicy` before G2.

Open one `visual-professional` ReviewSession with two views: anchor results and the complete visual contract. In the anchor view, collect multiple rectangle-region comments and submit one immutable `AnchorFeedbackBatch`. In the contract view, save field or selected-text marks as one `VisualContractReviewMarkSet`. Keep persistence, host notification, and AI receipt as three independent facts. Neither feedback write confirms G3; only an explicit current user judgment does.

### 4. Build, validate, deliver, and close

After G3, use Codex Presentations to build the full native editable deck. Preserve semantic text, data, charts, tables, diagrams, connectors, relationships, logos, and page markers as native objects. Keep photos and complex illustration replaceable. Add `[Sources]` notes, render and inspect every page, repair defects, and validate every current `ReleaseTargetPolicy.required_target_ids` row against the same PPTX hash.

Re-resolve the current policy before G4. Produce new target evidence for the final PPTX; never reuse G2 anchor evidence. Register a delivery package bound to that current policy, send the exact PPTX through Codex chat, retain the verified host delivery receipt, and confirm G4 only against the current package, target evidence, sent file, and explicit user judgment. Then close or abort through the formal lifecycle and run the queued `ProjectExperienceRetrospective`.

## Use only the approved user surfaces

Treat the Codex current project conversation as the unique entry and orchestration surface. Report only `AI 正在处理`, `需要你处理`, `成果已可查看`, or `任务受阻`. Open the content full-deck page or visual professional page only when concentrated reading or structured feedback is needed. Do not create a project dashboard, persistent product sidebar, delivery page, standalone evidence page, or additional technical ledger.

Open or resume the exact current ReviewSession and let the host create its authenticated Review Bridge resource. A `review-session-ready` result is only a Browser handoff: immediately open its scoped URL in the Codex built-in Browser and do not claim the review is open before navigation succeeds. Missing stdio adapter injection is not proof that Browser is unavailable. If the Agent Browser is absent or scoped navigation fails, return `BROWSER_REVIEW_UNAVAILABLE`; if reliable Review Bridge/Python persistence fails, return `BROWSER_REVIEW_SAVE_UNAVAILABLE`. Preserve Runtime state, the last valid artifacts, and drafts, then retry. A local preview, URL, fixture, Browser render, or simulated receipt is not real host evidence.

## Recover and learn

Read `references/review-and-feedback.md` before applying feedback. Reopen the earliest affected Gate and preserve unrelated accepted work plus immutable history. Read `references/experience-evolution.md` before using `recommend_experience`, `record_experience_application`, or `summarize_project_experience`. Reuse only sanitized `same-type` or `global` mechanisms with evidence and rollback.

A changed PPTX hash invalidates every current required-target row. With an unchanged hash, a changed application, OS, or font environment invalidates only that target. A policy identity change reopens G2 and locks G3/G4. One clear valid feedback may influence the current remainder as same-type experience; every G4, formal close, or abort queues a retrospective. Retrospective failure remains pending with retry evidence and never silently closes learning.

Work autonomously between real business checkpoints. Ask only for missing high-impact facts, conflicting source truth, unreadable critical material, or the explicit G0/G3/G4 judgment. Never ask the user to choose implementation technology. Never manufacture a user message, desktop application result, real project, or acceptance evidence.
