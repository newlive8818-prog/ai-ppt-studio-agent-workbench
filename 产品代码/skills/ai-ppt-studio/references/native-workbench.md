# Native workbench protocol

AI PPT Studio has two governed UI surfaces: the real Codex sidebar workbench and the Codex built-in Browser. The sidebar remains lightweight outside UI-03, while UI-03 uses the host's maximum available width for complete content review. The Browser provides read-only content evidence and G3 visual professional review. Chat is a text collaboration, confirmation, sample, and delivery channel; it never renders a Widget in chat. Both UI surfaces consume schema 3 project truth and never derive a Gate.

## Operating loop

1. Use `create_ai_ppt_project` or `get_ai_ppt_project_snapshot`; retain `revision`.
2. Read the five spaces: 项目总览、材料工作台、内容蓝图、视觉设计、制作与交付.
3. Call `get_ai_ppt_sidebar_projection` only for a verified sidebar host. If it returns `HOST_SIDEBAR_UNAVAILABLE`, keep the acceptance item blocked and report the capability gap; do not attach a chat UI template.
4. Before formal content work, save `MissionDraft` and show the complete current task/materials/unknowns. When confirmation is the only pending high-impact action, `OK / 确认 / 采纳 / 继续` and clear equivalents are confirmation intent; ordinary conversation is not. Call `confirm_ai_ppt_mission` with the current card summary. Use a verified sidebar/message reference when available, otherwise require host-native confirmation. Intent words are never persisted as evidence; only host acceptance lets the Python content precondition gate establish `material-backed`, `mixed-evidence`, or `proposal-led`.
5. Submit user input through the matching write with `expectedRevision`, then refresh.
6. Before AI work, use `request_ai_ppt_agent_action` with one formal role action and exact artifact inputs. Execute only that bounded task; return it with `commit_ai_ppt_artifact` and the task identity.
7. Load the complete UI-03 source with `get_content_sidebar_review_projection`. Use `save_content_page_decision` as a silent page save; after every page is decided, call `submit_content_review_batch` once and let Codex process the immutable review batch as a whole.
8. Use `open_content_evidence_browser` only from a real material asset. The short-lived `content-evidence` session is read-only evidence assistance bound to one source version, slide, evidence item, material, and server-confirmed asset. It never saves PageDecision or ReviewMark and never displays the full-deck directory.
9. For G3 visual review, call `open_ai_ppt_browser_review`. If it returns `review-session-ready` with `browserAction=open-scoped-url`, immediately use the Agent's Codex built-in Browser to open the returned scoped URL. Do not claim it is open until navigation succeeds. The stdio MCP process not having an injected Browser adapter is not evidence that the Codex host lacks Browser.
10. Save G3 exact marks separately. Use `confirm_ai_ppt_gate` only for G0/G3/G4 after the current `sourceVersion` and challenge are resolved. One confirmation belongs to one current checkpoint; `MissionConfirmation` never confirms G0, G3, or G4. Without a verified message/action, require fresh host-native confirmation. Use `record_internal_gate` only for authorized G1/G2 evidence.

## UI contract

- Real sidebar workbench: compact five-space navigation for UI-01/UI-02/UI-04/UI-05; maximum-width sidebar review for UI-03 with complete continuous pages, real material, notes, quality, relations, PageDecision, and immutable batch state.
- Read-only content evidence Browser: one bound material/page comparison plus adjacent-page summaries; no full-deck directory, review-type switch, PageDecision, ReviewMark, or save action.
- G3 visual Browser: `ProfessionalReviewApp` and `ReviewProjection` at 760/1000/1440px; one 64px header, overlay outline, overlay marks drawer, and `save_review_marks` only for visual review.
- No review Gate button, PPTX download, return-chat button, contact sheet, or business state in local storage. Chat UI display modes cannot substitute for the real sidebar or Browser.

## Formal Agent actions

Content actions require a current `MissionConfirmation` and Python-approved identity. The single `售前方案总师` automatically builds `PresalesEvidenceBook`, `CustomerDecisionContext`, `ProblemSolutionFitMap`, and the complete `ReadingDeckBlueprint`; the independent `事实与证据硬门` and `售前阅读与客户立场硬门` return only pass/fail plus repair requirements. On-demand specialists are bounded risk support, not a fixed production pipeline. Visual actions design the Deck system and slide contracts, use Codex Presentations for native-first anchors/PPTX, optionally use Image 2 for post-native non-semantic assets, run aesthetic/engineering/target reviews, and coordinate delivery. Feedback/experience actions remain isolated from producer self-approval.

One Agent turn must stop at the next user Gate unless a new host verification/elicitation result is received after that current review source was published. Never replay an earlier message or infer confirmation from task approval.

## Failure behavior

On `REVISION_CONFLICT` or `REVIEW_SOURCE_STALE`, refresh and preserve drafts. Failed tasks keep the last valid artifacts. `HOST_CONFIRMATION_DECLINED` or `HOST_CONFIRMATION_UNAVAILABLE` leaves the task and revision unchanged; retry without demanding additional material or suggesting a workflow bypass. Report `BROWSER_REVIEW_UNAVAILABLE` only after the Agent's Browser capability is absent or its scoped navigation fails; missing stdio adapter injection is not this error. Report `BROWSER_REVIEW_SAVE_UNAVAILABLE` only when the Review Bridge / Python persistence path is unavailable. Preserve sourceVersion and mark drafts. Host capability failure leaves project state unchanged. A changed PPTX hash invalidates every row required by the current `ReleaseTargetPolicy`; deferred profiles remain non-Gate rows.
