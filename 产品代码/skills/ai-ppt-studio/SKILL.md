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
4. Read `references/four-target-acceptance.md` before any anchor or final PPTX acceptance.
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

## Capability routing

- GPT performs audience understanding, strategy, content, visual reasoning, critique, and scoped revision.
- Codex Presentations is the sole route for every PPTX read, create, edit, render, and inspection. Do not build or use a second PPTX editor. Never use `python-pptx`.
- Image 2 is optional and only follows a frozen native-first structure. It may create replaceable non-semantic background, texture, illustration, or light-effect layers; never factual text, numbers, business relationships, real evidence, or a whole-slide final bitmap.
- No separate Image 2 privacy gate exists. Project materials may be used only inside the approved project task and media boundary.

## Approved production order

### 1. Mission confirmation and materials

The mandatory order is:

1. Save an AI-authored `MissionDraft` with `save_ai_ppt_mission_draft`.
2. Show the user the audience, topic, desired judgment/action, current material inventory or explicit no-material choice, background, constraints, red lines, and unknowns. Complete required fields make the draft only `confirmable`.
3. Obtain a real host-verified confirmation from an explicit sidebar action or explicit user message. After the current complete `confirmable` card has been shown and mission confirmation is the only pending high-impact action, `OK / 确认 / 采纳 / 继续` and clear equivalents are confirmation intent. Ordinary conversation or adoption of another suggestion is not mission confirmation.
4. Call `confirm_ai_ppt_mission` with the current card summary. A verified sidebar/message adapter preserves its real reference; otherwise the MCP host performs host-native confirmation. Intent words are never persisted as evidence. Only host acceptance creates an immutable `MissionConfirmation` bound to the current draft, project revision, and current material identity.
5. Pass the Python content precondition gate before requesting or committing any formal content work. Node, UI, prompts, and fixtures cannot bypass it.
6. Route `materials-provided` to `material-backed`, or route `no-materials-confirmed` to `proposal-only`.

Register only user-provided documents, text, images, screenshots, data, and links. In `proposal-only`, carry the identities `诊断假设`, `方案建议`, and `待联合验证` through strategy, claims, narrative, slide copy, speaker notes, review, and G0. Never invent customer facts, numbers, cases, capabilities, results, or commitments.

On `HOST_CONFIRMATION_DECLINED`, preserve the card and wait for revision or retry. On `HOST_CONFIRMATION_UNAVAILABLE`, preserve the task and retry when the host can confirm; never ask for more material and never bypass AI PPT Studio merely because host confirmation is unavailable.

### 2. Content governance and G0

Read `references/content-workflow.md`. Only after current `MissionConfirmation` and material identity pass the Python content precondition gate, produce, in order, `PresalesContentStrategy`, `ClaimEvidenceMap`, `DeckArgumentMap`, and a complete `SlideDraftSet` with every page's visible copy, speaker notes, source refs, material refs, and required identity. Run five isolated content reviews and aggregate them into one passing acceptance record or a repair plan. Publish only an internally passing content blueprint to Browser professional review. Saving marks never confirms G0; G0 requires an explicit user confirmation with a real host-verified message reference.

Do not discuss visual style before G0 passes.

### 3. Full visual contract and G1

Read `references/visual-workflow.md`. Create one complete `DeckDesignSystem` and every `SlideVisualContract` before native anchor production. The user does not select G1/G2 directions. G1 passes only through the authorized internal contract checks. Image 2 remains optional and only post-native; when a project explicitly skips it, record `not used` and continue without weakening any Gate.

### 4. Strict route B anchors and four-target G2

Read `references/presentations-handoff.md`. Codex Presentations creates native editable anchor slides from the full visual contract. Only after native-first freeze may Image 2 add approved non-semantic layers. Validate one identical anchor PPTX in:

- `macos-powerpoint`
- `macos-wps`
- `windows-powerpoint`
- `windows-wps`

G2 requires semantic, aesthetic, engineering, and target-render checks to pass on all four rows with the same PPTX SHA-256. One missing, failed, stale, or different-hash row blocks G2.

### 5. Professional visual review and G3

Open the same complete visual contract only through `open_ai_ppt_browser_review` in the Codex built-in Browser. Preserve the Deck framework, Deck Design System, native anchor identity, target evidence identities, frozen content, and every per-slide implementation condition. Exact-text marks are version-bound and do not confirm G3. G3 requires explicit user confirmation of the current review source with a real host-verified message reference.

### 6. Full deck, four-target G4, and chat delivery

After G3, Codex Presentations builds the full native editable PPTX. Keep titles, body text, labels, facts, numbers, charts, tables, diagrams, arrows, relationships, logos, and page markers native. Keep photos, screenshots, complex illustration, and texture as separate replaceable image layers. Add `[Sources]` notes for non-trivial claims/assets, render every page, inspect every page, and repair all defects.

Validate the identical final PPTX in the same four desktop targets with the same PPTX SHA-256. Register the delivery package, send that exact PPTX through Codex chat, persist the verified host delivery reference, and confirm G4 only against the current package, four target records, sent file, and explicit user message.

## Native UI contract

- The real Codex sidebar is the only lightweight workbench surface. `get_ai_ppt_sidebar_projection` returns pure data for its 360–480px five-space projection. If the host lacks that surface, return `HOST_SIDEBAR_UNAVAILABLE`; the product never renders a Widget in chat.
- Content and visual review share one responsive document and save contract at 760/1000/1440px, opened only through `open_ai_ppt_browser_review` in the Codex built-in Browser.
- The review Header always keeps both content/visual controls. Switching never reuses the current single-reviewType token across scopes: save current marks first, then let the authenticated Review Bridge resolve the authoritative target source/revision and issue a new short-lived scoped session.
- If Browser open or reliable save is unavailable, return `BROWSER_REVIEW_UNAVAILABLE` or `BROWSER_REVIEW_SAVE_UNAVAILABLE`, preserve project state and mark drafts, and retry. MCP Apps chat display modes are not substitutes for either surface.
- The professional review header, overlay outline, overlay marks drawer, exact mark saving, conflict recovery, complete fields, and stable anchors are authoritative presentation only—not Gate computation.

## Recovery and learning

Read `references/review-and-feedback.md` before applying feedback and `references/experience-evolution.md` before promoting learning. Preserve old immutable artifacts. Reopen the earliest affected Gate only; keep unrelated accepted work. A target environment change invalidates only its row when the PPTX hash is unchanged; any PPTX hash change invalidates all four rows. A single user reaction or test fixture never mutates the stable Skill core.

## User interaction

Work autonomously between real business checkpoints. Ask only for missing high-impact facts, conflicting source truth, unreadable critical material, or the explicit G0/G3/G4 judgment. Never ask the user to choose implementation technology. Never manufacture a user message, desktop application result, real project, or acceptance evidence.
