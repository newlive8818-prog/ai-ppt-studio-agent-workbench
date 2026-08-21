# Schema 3 Runtime workflow

## Startup and authority

1. Run `python3 scripts/ai_ppt_runtime.py preflight`.
2. Create with `create_ai_ppt_project`, or omit `projectRoot` to resume the latest schema 3 project.
3. Keep every project, artifact, review resource, render, PPTX, target export, and experience record below the configured managed Runtime root.
4. Call `get_ai_ppt_project_snapshot` after every write and retain `revision`.
5. Call `get_ai_ppt_project_status` for the user-facing state; do not derive status from Gate names or UI state.

The Runtime never falls back to an old state/projection. Legacy projects are available only through explicit one-way import; missing evidence remains unproven.

## Formal write groups

- Project and Mission: `add_ai_ppt_material`, `save_ai_ppt_mission_draft`, `confirm_ai_ppt_mission`, `set_ai_ppt_release_target_policy`.
- Formal work: `request_ai_ppt_agent_action`, `submit_ai_ppt_human_decision`, `commit_ai_ppt_artifact`.
- Content: build the four objects, run two hard gates, repair, save page decisions, submit or withdraw a Batch, confirm a revision plan, and create a change set.
- Review: `open_or_resume_review_session`, `record_review_host_open_receipt`, `record_review_host_notification_receipt`, and `record_review_ai_receipt`.
- Visual feedback: `submit_visual_anchor_feedback_batch` and `save_visual_contract_review_marks`.
- Gates and delivery: `record_internal_gate`, `confirm_ai_ppt_gate`, `record_chat_delivery`, `close_ai_ppt_project`, `abort_ai_ppt_project`, and `reopen_ai_ppt_scope`.
- Experience: `recommend_experience`, `record_experience_application`, and `summarize_project_experience`.

Every write uses `expectedRevision` and an idempotent command identity. Domain services recheck current heads and Gate preconditions. On `REVISION_CONFLICT` or `REVIEW_SOURCE_STALE`, refresh first and preserve user drafts.

The formal semantics are stricter than the tool names:

- `MissionConfirmation` is created only after the complete current task, material inventory or explicit no-material choice, background, constraints, red lines, and unknowns are shown and the host verifies the current confirmation action. Intent words are never evidence, and ordinary conversation or a stale card cannot confirm.
- `save_content_page_decision` silently persists one current-source `PageDecision` plus its required non-approved comment. It sends no follow-up, changes no content, and confirms no Gate. Only one complete immutable `ContentReviewBatch` starts concentrated processing.
- The chief saves one whole-deck revision plan; user confirmation is required before applying it. Every new source version receives full re-review with no inherited approvals.
- Visual ReviewMarks bind exact field/text anchors, prefix, suffix, comment, source version, and revision. A stale anchor conflicts; saving marks never confirms G3.
- `record_internal_gate` is restricted to authorized G1/G2 reviewers and exact current evidence heads. `confirm_ai_ppt_gate` accepts only G0/G3/G4, resolves the exact current source version, revision, evidence refs, and single-use challenge, and requires a verified current user action or fresh host-native confirmation. `MissionConfirmation` never confirms a Gate.
- `legacy-credential-upgrade` may replace only the credential of an already-passed historical G0 when its frozen acceptance and blueprint refs still equal current heads and its credential is strictly old-format. It requires a fresh host confirmation of the current challenge. Content drift requires normal G0 reopen and atomic downstream invalidation.

One Agent turn stops at the next later user Gate unless a new host verification or elicitation result arrives after the current review source is published. Never replay an older message or infer a Gate from task or Mission approval. `HOST_CONFIRMATION_DECLINED` and `HOST_CONFIRMATION_UNAVAILABLE` cause zero Gate business writes.

## Mission and content source replacement

Save `MissionDraft` → show the current complete card → recognize intent only in that card's sole-pending-action context → obtain verified or host-native confirmation → create `MissionConfirmation` → pass the Python content precondition → build the four content objects. `materials-provided` binds the current material inventory; `no-materials-confirmed` binds the current empty-material identity. `PresalesEvidenceBook` then classifies the work as `material-backed`, `mixed-evidence`, or `proposal-led`.

Formal content task creation and formal content artifact commit both recheck that Python precondition. Node, React, Browser, prompts, fixtures, and adapter calls cannot bypass it. Across all modes, preserve `来源事实`, `材料推断`, `用户已确认`, `诊断假设`, `方案建议`, `待联合验证`, `证据缺口`, and `禁止使用`. Missing evidence does not block complete content work; invented customer facts, numbers, cases, capabilities, results, or commitments always fail.

A new Mission, material inventory, or `ReadingDeckBlueprint.source_version` preserves immutable history but atomically removes stale current confirmation, review, visual, delivery, completion, and queued Agent heads as applicable. It reopens G0 and locks G1–G4. Old artifacts remain readable but cannot authorize new writes.

## Gate meaning

- G0: current two-hard-gate-passing `ReadingDeckBlueprint`, one complete all-approved content review Batch, and explicit user confirmation.
- G1: complete `DeckDesignSystem` plus all `SlideVisualContract` objects pass internal contract checks.
- G2: native anchors and all targets required by the current immutable `ReleaseTargetPolicy` pass semantic, aesthetic, engineering, and named-target-render checks against one PPTX hash. Deferred profiles are not Gate rows and do not imply compatibility.
- G3: current complete visual review source plus explicit user confirmation.
- G4: current full-deck build, QA, new final-PPTX evidence for every policy-required target, delivery package bound to the re-resolved current policy, verified sent-file receipt, and explicit final confirmation. G2 anchor evidence cannot be reused.

## Review and capability boundary

Create one current ReviewSession per review type and source identity. Internally retain the complete `ReadingDeckBlueprint`, but expose content pages only through the accepted `ContentReviewPageViewModel`; backend notes, evidence identities/source-entry UI, mappings, relations, reading-quality catalogs, and other internal fields do not become content-review modules. Let the host create its authenticated Review Bridge resource and open only that resource in the Codex built-in Browser at 760/1000/1440px. The Bridge resolves current project, source version, and revision from Python authority; the page cannot choose them.

Reliable persistence, host open, host notification, and AI receipt are independent. A `review-session-ready` response is only a handoff: immediately open its scoped URL with the Agent's Codex built-in Browser and do not claim success before actual navigation. Missing stdio adapter injection is not Browser unavailability. Report `BROWSER_REVIEW_UNAVAILABLE` only when the Agent Browser is absent or scoped navigation fails, and `BROWSER_REVIEW_SAVE_UNAVAILABLE` only when Review Bridge/Python persistence is unreliable. Preserve Runtime state, last valid artifacts, and drafts. A fixture, local preview, generated URL, loopback request, or Browser render cannot prove a real host action.
