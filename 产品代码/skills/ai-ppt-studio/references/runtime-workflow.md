# Schema 3 runtime workflow

## Startup and project selection

1. Run `python3 scripts/ai_ppt_runtime.py preflight`.
2. Create a managed project with `create_ai_ppt_project`, or omit `projectRoot` to resume the latest schema 3 project.
3. Keep every project, artifact, render, PPTX, target export, and experience record below the configured managed runtime root.
4. Use `get_ai_ppt_project_snapshot` after every write and retain the returned revision.

The runtime never falls back to a v1.x state/projection. An old project is available only through the explicit one-way importer; missing review or desktop evidence remains unproven.

## Formal writes

- `add_ai_ppt_material` records only user-provided text, URLs, or copied bytes.
- `save_ai_ppt_mission_draft` writes the AI-authored `MissionDraft`. Required fields can make it `confirmable`, never confirmed.
- `confirm_ai_ppt_mission` creates an immutable `MissionConfirmation` only after the task, current materials or explicit no-material choice, background, constraints, red lines, and unknowns have been shown. A verified sidebar/message adapter may supply a real reference; otherwise the MCP server requests host-native confirmation and writes only after host `accept` plus explicit confirmation. The Skill does not assume any reference URI format.
- `request_ai_ppt_agent_action` creates one immutable role-bound task over exact `artifact://<kind>/<sha256>` inputs.
- `commit_ai_ppt_artifact` validates and commits the formal output; a task result cannot bypass its domain contract.
- `save_review_marks` writes exact text, prefix, suffix, field anchor, comment, and source version; it never confirms a Gate.
- `record_internal_gate` is restricted to authorized G1/G2 reviewers and exact current evidence heads.
- `confirm_ai_ppt_gate` accepts only G0/G3/G4 with a real host-verified user message reference.
- `record_chat_delivery` binds the current delivery package and exact sent PPTX.
- `reopen_ai_ppt_scope` preserves immutable history and locks invalid downstream evidence.

Every write uses `expectedRevision`. On `REVISION_CONFLICT` or `REVIEW_SOURCE_STALE`, refresh first and preserve unsaved user drafts.

## Mission and content precondition

The order is strict: save `MissionDraft` → show task, materials, and unknowns → recognize confirmation intent only in the current card context → call `confirm_ai_ppt_mission` → obtain a verified reference or host-native confirmation → pass the Python content precondition gate → continue as `material-backed` or `proposal-only`.

- After the current complete `confirmable` card is shown and confirmation is its only pending high-impact action, `OK / 确认 / 采纳 / 继续` and clear equivalents may trigger the tool. The words themselves are never persisted as evidence.
- The same words in ordinary conversation, unrelated feedback, or against a stale/non-current card do not confirm the mission.
- `HOST_CONFIRMATION_DECLINED` and `HOST_CONFIRMATION_UNAVAILABLE` make no business write. Preserve the card and retry; never ask for more material and never bypass AI PPT Studio because of a host capability failure.

- `materials-provided` must bind the current material inventory and becomes `material-backed`.
- `no-materials-confirmed` must bind the current empty-material identity and becomes `proposal-only`.
- Any material or mission identity change makes the old `MissionConfirmation` stale.
- Formal content task creation and content artifact commits both re-check the Python gate. Node, sidebar, Browser, prompts, and fixtures cannot bypass it.
- `proposal-only` preserves 诊断假设, 方案建议, and 待联合验证 across all formal content and rejects invented customer facts, numbers, cases, capabilities, results, or commitments.

## Gate meaning

- G0: current internally accepted content blueprint plus explicit user confirmation.
- G1: complete Deck Design System and all slide visual contracts pass internal contract review.
- G2: strict route B native anchors plus four same-hash desktop targets pass semantic, aesthetic, engineering, and target-render checks.
- G3: current complete visual contract plus explicit user confirmation.
- G4: current full-deck build, QA, four same-hash target records, delivery package, sent chat receipt, and explicit final user confirmation.

## UI resources

`get_ai_ppt_sidebar_projection` is a pure-data projection for the real Codex sidebar at 360–480px. When no verified sidebar host exists, it returns `HOST_SIDEBAR_UNAVAILABLE`; it never renders a Widget in chat.

`open_ai_ppt_browser_review` opens content/visual professional review only in the Codex built-in Browser using the same resource and save contract at 760/1000/1440px. Return `BROWSER_REVIEW_UNAVAILABLE` when open is unavailable or `BROWSER_REVIEW_SAVE_UNAVAILABLE` when reliable mark saving is unavailable. Preserve state and drafts and retry; no chat UI display mode is a substitute.

Content/visual switching requires a newly issued single-reviewType session. The page submits only the target reviewType through its authenticated same-origin Bridge; the server resolves the current target sourceVersion/revision from Python. Never reuse the current token for the other type and never let the page choose a target project, sourceVersion, or revision. Unsaved marks or an unfinished mark editor block switching and remain on the current page.
