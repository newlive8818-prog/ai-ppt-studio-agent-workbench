---
name: ai-ppt-studio
description: Create, resume, review, revise, render, validate, and deliver isolated high-design editable reading-first presales PPT/PPTX projects through the AI PPT Studio Codex-native workbench.
---

# AI PPT Studio v1.6

AI is the principal strategist and maker. The user supplies goals, sources, consequential choices, feedback, and final acceptance. Runtime services own revision, immutable artifacts, evidence, recovery, and G0–G4; UI and chat never infer a passed Gate.

## Required startup

1. Read `references/isolation-policy.md` before any write.
2. Read `references/runtime-workflow.md` before creating or resuming a project.
3. Read `references/native-workbench.md` before using the real sidebar, Codex built-in Browser, professional review, or MCP writes.
4. Read the policy-driven compatibility entry point `references/four-target-acceptance.md` before any anchor or final PPTX acceptance.
5. Run `python3 scripts/ai_ppt_runtime.py preflight` and use the configured managed runtime root.
6. Create or resume a schema 3 project below the managed runtime root. Never write into the current working directory unless it is that managed project.
7. Treat user-provided originals as read-only. Copy inside the project before OCR, conversion, crop, annotation, or transformation.
8. Use only sources supplied by the user. Do not search the internet for customer-project material.
9. After mission context is known, run `experience-recommend --input CONTEXT.json`; if a recommendation materially affects work, bind its exact version with `experience-apply` and later evaluate it with `experience-evaluate`.

## Authoritative contracts

- Formal artifacts use `artifact://<kind>/<sha256>`. A reference must resolve inside the current project and match kind, project, and hash.
- Python schema 3 runtime is the only business writer. Node MCP is a thin validated adapter. React consumes formal projections only.
- All writes use `expectedRevision` and an idempotent command identity. Refresh after success or `REVISION_CONFLICT`.
- Formal Agent tasks bind one approved role, exact input refs, bounded instructions, output contract, exclusions, and isolation rules.
- Producer, reviewer, and sibling-review contexts remain isolated. No score, average, or majority vote can override one failed applicable hard check.
- Every user confirmation belongs to one current checkpoint, exact `sourceVersion`, current revision, and one-time challenge. `MissionConfirmation` never confirms G0, G3, or G4. A reused or model-invented message/action cannot pass a Gate.
- A passed historical G0 whose credential predates trusted host assertions may use `legacy-credential-upgrade` only when its frozen acceptance and blueprint refs still equal the current heads. It still requires a fresh host confirmation and changes only the credential; never trust the old message string or preserve downstream work after content drift.
- Resolve the current project-bound `ReleaseTargetPolicy` before G2 or G4. Its `required_target_ids` are the only Gate target source. The public Agent cannot shrink, expand, or replace that policy ad hoc.

## Capability routing

- GPT performs audience understanding, strategy, content, visual reasoning, critique, and scoped revision.
- Codex Presentations is the sole route for every PPTX read, create, edit, render, and inspection. Do not build or use a second PPTX editor. Never use `python-pptx`.
- Image 2 is optional and only follows a frozen native-first structure. It may create replaceable non-semantic background, texture, illustration, or light-effect layers; never factual text, numbers, business relationships, real evidence, or a whole-slide final bitmap.
- No separate Image 2 privacy gate exists. Project materials may be used only inside the approved project task and media boundary.

## Approved production order

### 1. Mission confirmation and materials

The mandatory order is:

1. Save an AI-authored `MissionDraft` with `save_ai_ppt_mission_draft`.
2. Show the user the audience, topic, decision question or next work action, current material inventory or explicit no-material choice, background, constraints, red lines, and unknowns. Complete required fields make the draft only `confirmable`.
3. Obtain a real host-verified confirmation from an explicit sidebar action or explicit user message. After the current complete `confirmable` card has been shown and mission confirmation is the only pending high-impact action, `OK / 确认 / 采纳 / 继续` and clear equivalents are confirmation intent. Ordinary conversation or adoption of another suggestion is not mission confirmation.
4. Call `confirm_ai_ppt_mission` with the current card summary. A verified sidebar/message adapter preserves its real reference; otherwise the MCP host performs host-native confirmation. Intent words are never persisted as evidence. Only host acceptance creates an immutable `MissionConfirmation` bound to the current draft, project revision, and current material identity.
5. Pass the Python content precondition gate before requesting or committing any formal content work. Node, UI, prompts, and fixtures cannot bypass it.
6. Route the current evidence state to `material-backed`, `mixed-evidence`, or `proposal-led`. A confirmed no-material choice becomes `proposal-led`.

Register only user-provided documents, text, images, screenshots, data, and links. Carry `来源事实`, `材料推断`, `用户已确认`, `诊断假设`, `方案建议`, `待联合验证`, `证据缺口`, and `禁止使用` consistently through content, speaker notes, review, and G0. Missing material changes identity and delivery positioning; it never stops complete content production. Never invent customer facts, numbers, cases, capabilities, results, or commitments.

On `HOST_CONFIRMATION_DECLINED`, preserve the card and wait for revision or retry. On `HOST_CONFIRMATION_UNAVAILABLE`, preserve the task and retry when the host can confirm; never ask for more material and never bypass AI PPT Studio merely because host confirmation is unavailable.

### 2. Content governance and G0

Read `references/content-workflow.md`. After current `MissionConfirmation` and material identity pass the Python content precondition gate, the single `售前方案总师` automatically produces `PresalesEvidenceBook`, `CustomerDecisionContext`, `ProblemSolutionFitMap`, and a complete `ReadingDeckBlueprint`. Do not require a framework confirmation or a separate full-deck expansion authorization. Run the independent `事实与证据硬门` and `售前阅读与客户立场硬门`; reviewers never edit the blueprint, and the chief repairs every failure and reruns affected gates. If review is called independent Agent review, preserve the actual independent instance, isolated context/hash, input version/hash, and output record; otherwise label it an isolated review task.

Publish only an internally passing complete source to the maximum-width sidebar review. Keep the approved per-page `approved | modify | evidence | merge-or-delete` decisions, immutable review batch, chief-authored deck-level revision plan, user plan confirmation, full re-review of every new source version, and a fresh host-verified G0 confirmation. Saving a page, submitting a batch, confirming a revision plan, or confirming the mission never confirms G0. One Agent turn cannot cross from mission confirmation through a later user Gate without a new host confirmation result.

Do not discuss visual style before G0 passes.

### 3. Full visual contract and G1

Read `references/visual-workflow.md`. Create one complete `DeckDesignSystem` and every `SlideVisualContract` before native anchor production. The user does not select G1/G2 directions. G1 passes only through the authorized internal contract checks. Image 2 remains optional and only post-native; when a project explicitly skips it, record `not used` and continue without weakening any Gate.

### 4. Strict route B anchors and release-target G2

Read `references/presentations-handoff.md`. Codex Presentations creates native editable anchor slides from the full visual contract. Only after native-first freeze may Image 2 add approved non-semantic layers. Resolve the current `ReleaseTargetPolicy`, bind its immutable artifact ref into G2 lineage, and validate one identical anchor PPTX in every current required target. For v1.6 the only required target is:

- `macos-powerpoint`

The supported `macos-wps`, `windows-powerpoint`, and `windows-wps` profiles are `deferred`; they do not block current G2 and are not passed or unsupported. Do not claim WPS or Windows compatibility. G2 requires semantic, aesthetic, engineering, and target-render checks to pass on every required row with the same PPTX SHA-256. One missing, failed, stale, or different-hash required row blocks G2. A preflight-only output cannot replace desktop evidence.

### 5. Professional visual review and G3

Open the same complete visual contract only through `open_ai_ppt_browser_review` in the Codex built-in Browser. The production MCP runs as an independent stdio process and does not receive the Agent's Browser API as an in-process JavaScript adapter. When the tool returns `status=review-session-ready`, `openMode=agent-browser`, and `browserAction=open-scoped-url`, the Agent must immediately open the returned scoped URL with the Codex built-in Browser. Do not claim the review is open until that Browser navigation actually succeeds. Preserve the Deck framework, Deck Design System, native anchor identity, target evidence identities, frozen content, and every per-slide implementation condition. Exact-text marks are version-bound and do not confirm G3. G3 requires explicit user confirmation of the current review source with a real host-verified message reference.

### 6. Full deck, release-target G4, and chat delivery

After G3, Codex Presentations builds the full native editable PPTX. Keep titles, body text, labels, facts, numbers, charts, tables, diagrams, arrows, relationships, logos, and page markers native. Keep photos, screenshots, complex illustration, and texture as separate replaceable image layers. Add `[Sources]` notes for non-trivial claims/assets, render every page, inspect every page, and repair all defects.

Resolve the same current policy again and validate the identical final PPTX in every required desktop target with the same PPTX SHA-256. G4 requires a new final-PPTX macOS PowerPoint record; never reuse the G2 anchor record. Bind the policy ref into the delivery package, send that exact PPTX through Codex chat, persist the verified host delivery reference, and confirm G4 only against the current package, required target records, sent file, and explicit user message. Deferred profiles never imply compatibility.

## Native UI contract

- The real Codex sidebar is the workbench surface. It remains lightweight for UI-01/UI-02/UI-04/UI-05, while UI-03 uses the host's maximum available width for the complete continuous content review. If the host lacks that surface, return `HOST_SIDEBAR_UNAVAILABLE`; the product never renders a Widget in chat.
- Content review is rendered in the sidebar with complete visible copy, real evidence, notes, reading quality, page relations, PageDecision, and immutable batch submission. The content Browser is read-only evidence assistance. Only G3 visual contract review is opened through `open_ai_ppt_browser_review` in the Codex built-in Browser.
- Missing MCP-process adapter injection is not proof that the Codex host lacks Browser. A `review-session-ready` result is a handoff: perform `open-scoped-url` with the Agent's Codex built-in Browser, then report the observed result.
- If the Agent actually lacks Browser or the Browser cannot open the scoped URL, report `BROWSER_REVIEW_UNAVAILABLE`. If the Review Bridge cannot reliably persist marks, report `BROWSER_REVIEW_SAVE_UNAVAILABLE`. Preserve project state and mark drafts, and retry. MCP Apps chat display modes are not substitutes for either surface.
- The G3 professional review header, overlay outline, overlay marks drawer, exact mark saving, conflict recovery, complete fields, and stable anchors are authoritative presentation only—not Gate computation.

## Recovery and learning

Read `references/review-and-feedback.md` before applying feedback and `references/experience-evolution.md` before learning. Preserve old immutable artifacts. Reopening G0 locks G1–G4 and removes downstream current heads in one authoritative transaction while keeping immutable artifact history. Reopen the earliest affected Gate only; keep unrelated accepted work. A target environment change invalidates only its row when the PPTX hash is unchanged; any PPTX hash change invalidates every current required row. A policy identity change reopens G2 and locks G3/G4.

Experience has only `same-type` and `global` layers and covers both content and visual design. One clear, valid feedback may immediately update same-type experience and influence the current remaining work. A user-declared global rule or the same mechanism succeeding in two distinct type signatures may create global experience. After every G4, formal project close, or abort, automatically create `ProjectExperienceRetrospective`; failure becomes `experience-retrospective-pending` and retries without blocking delivery. Customer facts, data, assets, and complete designs never enter reusable experience. Experience cannot rewrite product policy, evidence truthfulness, role authority, or Gate contracts.

## User interaction

Work autonomously between real business checkpoints. Ask only for missing high-impact facts, conflicting source truth, unreadable critical material, or the explicit G0/G3/G4 judgment. Never ask the user to choose implementation technology. Never manufacture a user message, desktop application result, real project, or acceptance evidence.
