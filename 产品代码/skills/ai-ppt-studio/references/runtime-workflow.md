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

## Mission and content source replacement

Save `MissionDraft` → show the current complete card → obtain verified or host-native confirmation → create `MissionConfirmation` → build the four content objects. `materials-provided` binds the current material inventory; `no-materials-confirmed` binds the current empty-material identity. `PresalesEvidenceBook` then classifies the work as `material-backed`, `mixed-evidence`, or `proposal-led`.

A new Mission, material inventory, or `ReadingDeckBlueprint.source_version` preserves immutable history but atomically removes stale current confirmation, review, visual, delivery, completion, and queued Agent heads as applicable. It reopens G0 and locks G1–G4. Old artifacts remain readable but cannot authorize new writes.

## Gate meaning

- G0: current two-hard-gate-passing `ReadingDeckBlueprint`, one complete all-approved content review Batch, and explicit user confirmation.
- G1: complete `DeckDesignSystem` plus all `SlideVisualContract` objects pass internal contract checks.
- G2: native anchors and all targets required by current `ReleaseTargetPolicy` pass current evidence checks against one PPTX hash.
- G3: current complete visual review source plus explicit user confirmation.
- G4: current full-deck build, QA, required-target evidence, delivery package, verified sent-file receipt, and explicit final confirmation.

## Review and capability boundary

Create one current ReviewSession per review type and source identity. Let the host create its authenticated Review Bridge resource and open only that resource in the Codex built-in Browser at 760/1000/1440px. The Bridge resolves current project, source version, and revision from Python authority; the page cannot choose them.

Reliable persistence, host open, host notification, and AI receipt are independent. `BROWSER_REVIEW_UNAVAILABLE` or `BROWSER_REVIEW_SAVE_UNAVAILABLE` preserves Runtime state and drafts. A fixture, local preview, generated URL, loopback request, or Browser render cannot prove a real host action.
