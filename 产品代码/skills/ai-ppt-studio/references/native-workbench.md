# Native workbench protocol

AI PPT Studio has exactly two UI surfaces: the lightweight workbench in the real Codex sidebar and professional review in the Codex built-in Browser. Chat is a text collaboration, confirmation, sample, and delivery channel; it never renders a Widget in chat. Both UI surfaces consume the schema 3 project truth and never derive a Gate.

## Operating loop

1. Use `create_ai_ppt_project` or `get_ai_ppt_project_snapshot`; retain `revision`.
2. Read the five spaces: 项目总览、材料工作台、内容蓝图、视觉设计、制作与交付.
3. Call `get_ai_ppt_sidebar_projection` only for a verified sidebar host. If it returns `HOST_SIDEBAR_UNAVAILABLE`, keep the acceptance item blocked and report the capability gap; do not attach a chat UI template.
4. Before formal content work, save `MissionDraft` and show the complete current task/materials/unknowns. When confirmation is the only pending high-impact action, `OK / 确认 / 采纳 / 继续` and clear equivalents are confirmation intent; ordinary conversation is not. Call `confirm_ai_ppt_mission` with the current card summary. Use a verified sidebar/message reference when available, otherwise require host-native confirmation. Intent words are never persisted as evidence; only host acceptance lets the Python content precondition gate establish `material-backed` or `proposal-only`.
5. Submit user input through the matching write with `expectedRevision`, then refresh.
6. Before AI work, use `request_ai_ppt_agent_action` with one formal role action and exact artifact inputs. Execute only that bounded task; return it with `commit_ai_ppt_artifact` and the task identity.
7. When content or visual review is formally available, call `open_ai_ppt_browser_review` and open the returned scoped URL only in the Codex built-in Browser.
8. Keep both review types in the 64px Header. Save or finish the current mark first; switching asks the authenticated Bridge for a new single-reviewType session whose target sourceVersion/revision comes from Python authority. Never reuse the current token across review types.
9. Save exact marks separately. Use `confirm_ai_ppt_gate` only for an explicit G0/G3/G4 user message with a real host-verified reference; use `record_internal_gate` only for authorized G1/G2 evidence.

## UI contract

- Real sidebar workbench: 360–480px, five-space navigation, conclusion, highest focus/risk, affected artifacts, formal counts/state, and at most one strongest action.
- Codex built-in Browser review: the same `ProfessionalReviewApp`, `ReviewProjection`, and save interface at 760/1000/1440px. Responsive width changes never create a third surface.
- Review header is one 64px line. Outline and marks drawers overlay the document and are mutually exclusive. Content remains continuous and complete.
- No review Gate button, PPTX download, return-chat button, contact sheet, or business state in local storage. Chat UI display modes cannot substitute for the real sidebar or Browser.

## Formal Agent actions

Content actions require a current `MissionConfirmation` and Python-approved identity first, then build strategy, claim evidence, argument map, slide draft, repair, five independent specialist reviews, and aggregate review. `proposal-only` actions must carry 诊断假设, 方案建议, and 待联合验证 through every formal content artifact and review. Visual actions design the Deck system and slide contracts, use Codex Presentations for native-first anchors/PPTX, optionally use Image 2 for post-native non-semantic assets, run aesthetic/engineering/target reviews, and coordinate delivery. Feedback/experience actions remain isolated from producer self-approval.

## Failure behavior

On `REVISION_CONFLICT` or `REVIEW_SOURCE_STALE`, refresh and preserve drafts. Failed tasks keep the last valid artifacts. `HOST_CONFIRMATION_DECLINED` or `HOST_CONFIRMATION_UNAVAILABLE` leaves the task and revision unchanged; retry without demanding additional material or suggesting a workflow bypass. Return `BROWSER_REVIEW_UNAVAILABLE` when Browser open is unavailable and `BROWSER_REVIEW_SAVE_UNAVAILABLE` when reliable save is unavailable; preserve sourceVersion and mark drafts. Host capability failure leaves project state unchanged. A changed PPTX hash invalidates all four desktop rows.
