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
- `save_content_page_decision` silently writes one current-source PageDecision and comment; it sends no follow-up, changes no content, and confirms no Gate.
- `submit_content_review_batch` freezes one complete immutable review batch and is the only content-review write that starts concentrated Codex processing.
- `save_content_batch_revision_plan` stores the chief's whole-deck plan without applying it; `confirm_content_batch_revision_plan` requires a current host confirmation before content change.
- `open_content_evidence_browser` creates only a short-lived read-only evidence session bound to one source/slide/evidence/material/asset identity.
- `save_review_marks` writes exact text, prefix, suffix, field anchor, comment, and source version only for G3 visual review; it never confirms a Gate.
- `record_internal_gate` is restricted to authorized G1/G2 reviewers and exact current evidence heads.
- `confirm_ai_ppt_gate` accepts only G0/G3/G4. It first resolves the exact current `sourceVersion`, revision, evidence refs, and challenge, then requires a verified user message/action or a fresh host-native confirmation. One confirmation belongs to one current checkpoint and is consumed once; `MissionConfirmation` never confirms G0, G3, or G4.
- For a passed historical G0 created before trusted host assertions, `legacy-credential-upgrade` is available only when the old confirmation's acceptance and blueprint refs exactly equal current heads and the credential is strictly old-format. The host must confirm the current challenge again. Success replaces only `gate/G0/confirmation` and preserves current visual lineage; it never upgrades an old message string by itself. Any content drift requires normal G0 reopen and downstream invalidation.
- `record_chat_delivery` binds the current delivery package and exact sent PPTX.
- `reopen_ai_ppt_scope` preserves immutable history. Reopening G0 atomically locks G1–G4, invalidates the downstream active Agent task, and removes downstream current heads without deleting their artifact objects.

Every write uses `expectedRevision`. On `REVISION_CONFLICT` or `REVIEW_SOURCE_STALE`, refresh first and preserve unsaved user drafts.

One Agent turn cannot cross from mission confirmation through the next user Gate unless a new host verification/elicitation result is obtained after the current review source was published. `HOST_CONFIRMATION_DECLINED` and `HOST_CONFIRMATION_UNAVAILABLE` cause zero Gate business writes.

## Mission and content precondition

The order is strict: save `MissionDraft` → show task, materials, and unknowns → recognize confirmation intent only in the current card context → call `confirm_ai_ppt_mission` → obtain a verified reference or host-native confirmation → pass the Python content precondition gate → continue as `material-backed`, `mixed-evidence`, or `proposal-led`.

- After the current complete `confirmable` card is shown and confirmation is its only pending high-impact action, `OK / 确认 / 采纳 / 继续` and clear equivalents may trigger the tool. The words themselves are never persisted as evidence.
- The same words in ordinary conversation, unrelated feedback, or against a stale/non-current card do not confirm the mission.
- `HOST_CONFIRMATION_DECLINED` and `HOST_CONFIRMATION_UNAVAILABLE` make no business write. Preserve the card and retry; never ask for more material and never bypass AI PPT Studio because of a host capability failure.

- A relatively sufficient current material inventory becomes `material-backed`.
- A current inventory with material evidence and material gaps becomes `mixed-evidence`.
- `no-materials-confirmed` binds the current empty-material identity and becomes `proposal-led`.
- Any material or mission identity change makes the old `MissionConfirmation` stale.
- Formal content task creation and content artifact commits both re-check the Python gate. Node, sidebar, Browser, prompts, and fixtures cannot bypass it.
- All modes preserve 来源事实, 材料推断, 用户已确认, 诊断假设, 方案建议, 待联合验证, 证据缺口, and 禁止使用 consistently. Missing evidence never blocks complete content work; invented customer facts, numbers, cases, capabilities, results, or commitments always fail.
- After the mission precondition, new projects do not require a content-framework confirmation or a full-deck expansion authorization. Historical projects may retain those immutable artifacts, but they are not new-work prerequisites.

## Gate meaning

- G0: current internally accepted content blueprint plus explicit user confirmation.
- G1: complete Deck Design System and all slide visual contracts pass internal contract review.
- G2: strict route B native anchors plus every target required by the current `ReleaseTargetPolicy` pass semantic, aesthetic, engineering, and target-render checks on one PPTX SHA-256.
- G3: current complete visual contract plus explicit user confirmation.
- G4: current full-deck build, QA, new final-PPTX records for every policy-required target, policy-bound delivery package, sent chat receipt, and explicit final user confirmation.

## UI resources

`get_ai_ppt_sidebar_projection` is a pure-data projection for the real Codex sidebar. UI-01/UI-02/UI-04/UI-05 remain compact; UI-03 may use the host's maximum available width for the complete continuous content review. When no verified sidebar host exists, it returns `HOST_SIDEBAR_UNAVAILABLE`; it never renders a Widget in chat.

Content review is published to the maximum-width sidebar only after `ReadingDeckBlueprint` passes both content hard gates. It preserves neutral titles, complete visible copy, evidence, notes, reading quality, page relations, PageDecision, and immutable batch state. `open_content_evidence_browser` is read-only evidence assistance for one exact material scope and cannot save PageDecision or ReviewMark.

`open_ai_ppt_browser_review` prepares the G3 visual professional review. A directly connected adapter may return `status=opened`. The production stdio path normally returns `status=review-session-ready`, `openMode=agent-browser`, `browserAction=open-scoped-url`, and a short-lived scoped URL; the Agent must immediately open that URL with the Codex built-in Browser and must not claim success before navigation succeeds. Missing in-process adapter injection is not a host Browser failure. Report `BROWSER_REVIEW_UNAVAILABLE` only when the Agent Browser is absent or actual navigation fails, and `BROWSER_REVIEW_SAVE_UNAVAILABLE` only when the Review Bridge cannot reliably persist marks. Preserve state and drafts and retry; no chat UI display mode is a substitute.
