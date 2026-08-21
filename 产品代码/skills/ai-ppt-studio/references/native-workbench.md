# Codex-native conversation and review protocol

AI PPT Studio has one entry: the Codex current project conversation. Use it for discussion, status, Mission confirmation, Gate judgments, and delivery. Open structured pages only when concentrated reading or feedback is needed:

- `content-full-deck`: the complete content review;
- `visual-professional`: anchor results plus the complete visual contract;

All surfaces consume schema 3 authority and never derive a Gate.

## Operating loop

1. Use `create_ai_ppt_project` or `get_ai_ppt_project_snapshot`; retain `revision`.
2. Report only `AI 正在处理`, `需要你处理`, `成果已可查看`, or `任务受阻`, based on `get_ai_ppt_project_status`.
3. Before content work, save `MissionDraft`, show the current complete task, material inventory or explicit no-material choice, background, constraints, red lines, and unknowns, and call `confirm_ai_ppt_mission` only when the current complete `confirmable` card is visible and confirmation is the sole pending high-impact action. `OK / 确认 / 采纳 / 继续` can be confirmation intent only in that context; ordinary conversation or adopting another suggestion is not confirmation, and the words are never evidence.
4. Send every write with `expectedRevision`, then refresh the snapshot.
5. Use `request_ai_ppt_agent_action` only for a bounded current role task and return its result with `commit_ai_ppt_artifact` plus the exact task identity.
6. Open or resume the exact `content-full-deck` or `visual-professional` ReviewSession. Let the host create its authenticated, source-bound Review Bridge resource and open only that resource in the Codex built-in Browser.
7. Keep content and visual ReviewSessions independent. Do not reuse a token, source version, revision, draft, or receipt across review types.
8. Use `confirm_ai_ppt_gate` only for explicit G0/G3/G4 judgments bound to the exact current source version, revision, and single-use challenge with real host-verified references. `MissionConfirmation` never confirms a later Gate. Use `record_internal_gate` only for authorized G1/G2 evidence.
9. Stop an Agent turn at the next later user Gate unless a new host verification or elicitation result is received after the current review source was published. Never replay an older message or infer a Gate from task or Mission approval.

Use Codex Presentations for PPTX production and inspection. Use Image 2 only for approved post-native, non-semantic, replaceable layers.

## Review contract

- Render review pages at 760/1000/1440px without a product navigation shell.
- Keep the full review readable in source order. Overlay drawers must not change document geometry or discard scroll position.
- Content review owns the accepted page-level ViewModel, `PageDecision`, Batch submission, and revision plan. It does not expose a standalone evidence page or the full internal blueprint field catalog.
- Visual review owns rectangle-region `AnchorFeedbackBatch` and field/text `VisualContractReviewMarkSet` as separate writes.
- Keep persistence, host open, host notification, and AI receipt independently visible. A saved state cannot imply notification or AI receipt.
- Do not add Gate buttons, PPTX download, duplicate chat, or business state in local storage.

## Failure behavior

On `REVISION_CONFLICT` or `REVIEW_SOURCE_STALE`, refresh and preserve drafts. `HOST_CONFIRMATION_DECLINED` or `HOST_CONFIRMATION_UNAVAILABLE` makes no business write. A `review-session-ready` response is only a handoff: immediately perform its `open-scoped-url` action with the Agent's Codex built-in Browser and do not claim the page is open before navigation succeeds. Missing stdio adapter injection is not Browser unavailability. Return `BROWSER_REVIEW_UNAVAILABLE` only if the Agent Browser is absent or actual scoped navigation fails, and `BROWSER_REVIEW_SAVE_UNAVAILABLE` only if Review Bridge/Python persistence is unreliable. Keep the task, revision, last valid artifacts, Runtime state, and drafts intact. A local preview, loopback request, generated URL, or simulated receipt is not real host evidence.
