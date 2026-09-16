---
name: ai-ppt-studio
description: Create, resume, govern, review, revise, render, validate, and deliver isolated reading-first presales PPT/PPTX projects with AI PPT Studio. Use for evidence-bound content architecture, on-demand content or visual professional review, native editable PowerPoint production, release-target validation, delivery, and project experience retrospective.
---

# AI PPT Studio

Act as the principal strategist and maker. Let the user supply goals, sources, consequential choices, feedback, and final acceptance. Let the Runtime own revision, immutable artifacts, evidence, recovery, and G0–G4. Never infer a passed Gate from chat, UI, fixtures, or local rendering.

## Current design responsibility and implementation boundary

Image 2 owns page design. After the user finalizes an exact image, that image and its reconciled visible copy bind every downstream stage. Contract extraction, compilation, reconstruction, and repair translate that design; they do not redesign, simplify, rewrite, or restore older copy. Check content fidelity, visual fidelity, editability, and deck consistency separately. A selected image is not merely a style reference.

Image 2 names the page-design responsibility; the exact provider/model comes from the approved configuration and matching authorization identity. The user currently selects `CRS / gpt-image-2`. Keep Sunburst available as an implemented adapter whose external block applies only to that route; do not make it or a general model registry a prerequisite for Image 2. `2048x1152 / high / PNG / n=1` are request targets, not measured output. Only the Image 2 route accepts the observed and explicitly supported `gpt-image-2-codex` report alongside exact `gpt-image-2`; Sunburst remains exact. Do not use Flare, generic aliases, model-family matching, or automatic fallback. Never relabel an old grant or response; preserve existing user decisions, G0, confirmed copy, materials, and common design rules while the formal scope/policy/pack chain binds the selected route.

This repository guidance follows the approved v2.14 product baselines. C2 adds an explicit Image-led Runtime route and independent compiler/handoff versions alongside isolated legacy readers. Check the running Runtime version and host adapter capabilities before using it; source implementation and synthetic tests do not establish a real provider, current customer Gates, or faithful real-sample acceptance. Installed plugin updates require a separate release; editing this source does not update them.

### Non-negotiable target identity

Every faithful replay must carry one immutable target binding: `project_id`, `slide_id`, `page_order`, exact finalized-image SHA256, selected-visible-copy SHA256, material roles, accepted deviations, and `design_authority=finalized-image`. Never choose by filename, directory order, newest file, similarity, prior frozen copy, or model guess. If the binding, region map, or dependency hash is missing or inconsistent, stop before creating output and report a capability gap; do not redesign, restore old copy, overwrite accepted output, or call the result a successful conversion. Deck-wide font/color/header/background rules are cross-page checks only and cannot rewrite a page-local finalized composition.

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
- Resolve the immutable project-bound `ReleaseTargetPolicy` before G2 and again before G4. Its `required_target_ids` are the only Gate target source; the public Agent cannot supply arbitrary targets or shrink, expand, or replace the policy.

## Route capabilities honestly

- Use GPT for audience understanding, evidence reasoning, presales strategy, content, visual reasoning, critique, and scoped revision.
- Use Codex Presentations as the only PPTX authoring/rendering engine. Runtime may inspect OOXML read-only for source extraction and export verification; it never edits PPTX. Do not build or use a second PPTX editor. Never use `python-pptx`.
- After G0, give Image 2 confirmed copy, materials, the page goal, and common font/color/header/background rules; let it choose the body composition. Reconcile content before design finalization. After finalization, convert faithfully to native text, tables, and important relationships plus independent replaceable image layers for complex decoration. Never deliver a whole-slide bitmap as editable or silently change finalized content.
- No separate Image 2 privacy gate exists. Project materials may be used only inside the approved project task and media boundary.

## Execute the governed loop

### 1. Confirm Mission and material identity

Save an AI-authored `MissionDraft`, show the task, audience, desired judgment/action, materials or explicit no-material choice, background, constraints, red lines, and unknowns, then obtain a real host-verified `MissionConfirmation`. After the current complete `confirmable` card is shown and confirmation is the sole pending high-impact action, `OK / 确认 / 采纳 / 继续` may express confirmation intent. An ordinary conversation does not. Intent words are never persisted as evidence.

Call `confirm_ai_ppt_mission`; use host-native confirmation when no verified message adapter exists. `action=accept` with `confirmed=false` is `HOST_CONFIRMATION_NOT_COMPLETED`, not approval or revocation of an existing decision. On incomplete, declined, cancelled, or unavailable confirmation, make no business write and preserve the task and existing user decisions. Diagnose the exact host integration before any further host attempt; do not automatically open another form or switch transports, and never ask for more material because confirmation failed. Source fixes and synthetic verifier tests do not establish a loaded production adapter or a real receipt; never bypass AI PPT Studio when that capability is missing.

Classify the current content work as `material-backed`, `mixed-evidence`, or `proposal-led`. Preserve source fact, source-derived inference, `诊断假设`, `方案建议`, `待联合验证`, conflict, gap, and prohibited extrapolation as distinct identities. Never invent customer facts, numbers, cases, capabilities, results, or commitments.

Before requesting any formal content Agent task and again before committing its artifact, pass the Python content precondition against the current Mission and material identity. Node, React, Browser, prompts, fixtures, or direct adapter calls cannot bypass this gate.

Create material-backed source evidence through `add_ai_ppt_material` with `materialType=finding`, current inventory/source/hash, a typed selector, `contentKind`, and `exclusionMode`; do not handwrite artifact JSON, use inventory IDs as finding refs, or supply a content hash. The Runtime replays extraction and registers a fixed derived finding without replacing inventory, Mission, content, or Gates. New content writes and hard gates must resolve current real sources. `proposal-led` remains valid without materials; unreadable or non-replayable sources remain a capability gap.

Keep range exclusions and explicit `image-content` exclusions distinct. The latter is active when the verified image finding is listed in current EvidenceBook exclusions: Runtime derives its hash from real extracted image bytes and rejects identical candidate bytes across other objects, sources, names, paths, or uses. Do not drop an exclusion to allow another object; unrelated images on the same page may remain usable. Page-level evidence can coexist with an excluded object, but an actual whole-page atom cannot bypass it. Registration of an exclusion finding is valid and does not itself grant or revoke user authority. Source-reference repair preserves accepted copy and historical decisions; it does not migrate an old G0 to a changed Blueprint.

### 2. Build and review content before visual work

Read `references/content-workflow.md`. Let the presales chief produce, in order, `PresalesEvidenceBook`, `CustomerDecisionContext`, `ProblemSolutionFitMap`, and `ReadingDeckBlueprint`. Invoke specialists only for a concrete uncertainty or high-impact `RevisionProposal`; do not require a fixed content Agent roster.

Pass both the evidence hard gate and presales-reading hard gate. Open one `content-full-deck` ReviewSession only after the current blueprint passes. Collect one `PageDecision` per slide, submit one immutable review Batch, and when changes are requested confirm a Batch revision plan, create the change set, publish a new source version, and reopen review. Saving review data never confirms G0. Confirm G0 only from an explicit current user judgment with a real host-verified reference. Do not discuss visual style before G0 passes.

If a hard-gate review is described as an independent Agent review, preserve the real independent instance identity, isolated context/hash, exact input version/hash, and output record; otherwise call it an isolated review task. One Agent turn must stop at the next later user Gate unless a new host verification or elicitation result is received after that current review source was published.

### 3. Build the visual contract and anchors

Read `references/visual-workflow.md` and `references/presentations-handoff.md`. The C2 Image-led Runtime uses the existing action/artifact tools with explicit route identity; resolve actual host capabilities before execution. Image 2 designs before native geometry is frozen. Bind the exact finalized image, reconciled visible copy, materials, and accepted deviations; register reviewed regions, then derive the full contracts and current plan. Execute only the task's `layers.visual_handoff.renderer_handoff`. Submit the actual build result, obtain independent four-dimension review, then promote verified anchors. Codex Presentations faithfully converts the final design; current target checks still precede G2. Synthetic engineering proofs never establish real Image 2, PowerPoint, or user acceptance.

Use optional `includeImage2Preflight=true` on the current host's `get_ai_ppt_project_snapshot` to inspect the known Image 2 wrapper without generating. An older loaded Runtime may lack this option. Verify the actual process receipt and wrapper identity; shell configuration or a separate synthetic process is not current-host proof. Preflight does not run the credential helper, contact a provider, or change business state. It reports local protocol capability only; `external_connection=not-tested` never proves authentication or generation. Missing configuration is a capability issue, not revocation of valid authorization. Do not execute unknown configured commands to test them.

Use only the two exact argv forms in `references/runtime-workflow.md`: Image 2 retains the current Python and current package wrapper as two items; Sunburst alone adds `--model`, `gpt-image-2.5-sunburst`. Keep transport/preflight v1/v2; no v3 or input downgrade. Configuration/payload/probe model mismatches fail before queuing or sending. Each explicit root/image response model must be allowed for the selected route, while the original transport model always stays the requested route. An invalid report, invalid observation, or rewritten transport route fails after sending: preserve unknown without retry and never claim zero HTTP. Known CRS command v2 requires validated `provider_observation`; keep its reported fields separate from requested settings, with `independent_engine_proof=false`. Missing upstream model remains unproven. Source adaptation, review, package loading, real HTTP, and customer acceptance remain separate evidence states.

The provider prompt adds fixed `system_output_requirements={version:"image-led-system-output/v1",canvas:{aspect_ratio:"16:9"}}` separately from customer fields. Do not alter v2 input/schema, common_rules.background, copy/page_goal/materials, input hashes, grants, or G0 to add this requirement. Runtime keeps the fully decoded original bytes with actual image_size/MIME/hash. Both current CRS v2 routes use `image-led-output-fitness/v1`: `abs(16*h-9*w)<=8` and `w>=1280 && h>=720`. This is a raster geometry floor, not proof of readable text or approved design. A valid returned image may be completed while current usability is needs-revision; keep it and block candidate/selection until the original image passes rechecking. Never resize, crop, resample, or substitute requested dimensions to conceal an unsuitable output; faithful conversion uses actual source geometry.

The packaged CRS wrapper consumes the verified compiled payload, preserving exact copy and ordered materials/uses while leaving body composition to Image 2. It makes one external attempt without retries or redirects. Use `generationIntent=new` only for a new explicit design request; use `generationIntent=recover` with the original `generationRequestId` for an unknown result. Never replace an unknown ID to resend. A `local-response-sha256:` receipt identifies local response bytes, not a provider-issued ID or a remote exactly-once guarantee. Read `references/runtime-workflow.md` for configuration and preflight proof boundaries.

Open one `visual-professional` ReviewSession with two views: anchor results and the complete visual contract. In the anchor view, collect multiple rectangle-region comments and submit one immutable `AnchorFeedbackBatch`. In the contract view, save field or selected-text marks as one `VisualContractReviewMarkSet`. Keep persistence, host notification, and AI receipt as three independent facts. Neither feedback write confirms G3; only an explicit current user judgment does.

### 4. Build, validate, deliver, and close

After G3, use Codex Presentations to convert each finalized page into the full native editable deck, preserving its exact bound design and copy. A missing page design cannot be filled by a native author inventing a layout; obtain the Image 2 design through the authorized process first. Preserve semantic text, data, charts, tables, diagrams, connectors, relationships, logos, and page markers as native objects. Keep photos and complex illustration replaceable. Add `[Sources]` notes, render and inspect every page, repair defects, and validate every current `ReleaseTargetPolicy.required_target_ids` row against the same PPTX hash.

Re-resolve the current policy before G4. Produce new target evidence for the final PPTX; never reuse G2 anchor evidence. Register a delivery package bound to that current policy, send the exact PPTX through Codex chat, retain the verified host delivery receipt, and confirm G4 only against the current package, target evidence, sent file, and explicit user judgment. Then close or abort through the formal lifecycle and run the queued `ProjectExperienceRetrospective`.

## Use only the approved user surfaces

Treat the Codex current project conversation as the unique entry and orchestration surface. Report only `AI 正在处理`, `需要你处理`, `成果已可查看`, or `任务受阻`. Open the content full-deck page or visual professional page only when concentrated reading or structured feedback is needed. Do not create a project dashboard, persistent product sidebar, delivery page, standalone evidence page, or additional technical ledger.

Open or resume the exact current ReviewSession and let the host create its authenticated Review Bridge resource. A `review-session-ready` result is only a Browser handoff: immediately open its scoped URL in the Codex built-in Browser and do not claim the review is open before navigation succeeds. Missing stdio adapter injection is not proof that Browser is unavailable. If the Agent Browser is absent or scoped navigation fails, return `BROWSER_REVIEW_UNAVAILABLE`; if reliable Review Bridge/Python persistence fails, return `BROWSER_REVIEW_SAVE_UNAVAILABLE`. Preserve Runtime state, the last valid artifacts, and drafts, then retry. A local preview, URL, fixture, Browser render, or simulated receipt is not real host evidence.

## Recover and learn

Read `references/review-and-feedback.md` before applying feedback. Reopen the earliest affected Gate and preserve unrelated accepted work plus immutable history. Read `references/experience-evolution.md` before using `recommend_experience`, `record_experience_application`, or `summarize_project_experience`. Reuse only sanitized `same-type` or `global` mechanisms with evidence and rollback.

A changed PPTX hash invalidates every current required-target row. With an unchanged hash, a changed application, OS, or font environment invalidates only that target. Follow Runtime's earliest affected Gate after policy changes: Image-led release-policy replacement invalidates selection/contracts and reopens G1 while locking G2–G4; legacy projects retain their existing G2 policy behavior. One clear valid feedback may influence the current remainder as same-type experience; every G4, formal close, or abort queues a retrospective. Retrospective failure remains pending with retry evidence and never silently closes learning.

Work autonomously between real business checkpoints. Ask only for missing high-impact facts, conflicting source truth, unreadable critical material, or the explicit G0/G3/G4 judgment. Never ask the user to choose implementation technology. Never manufacture a user message, desktop application result, real project, or acceptance evidence.
