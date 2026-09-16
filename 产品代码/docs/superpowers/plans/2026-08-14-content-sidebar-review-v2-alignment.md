# Content Sidebar Review v2.0 Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` with TDD. This plan replaces Tasks 11–17 of `2026-08-14-content-blueprint-sidebar-review-implementation.md`; Tasks 1–10 remain implementation history, but framework confirmation and full-deck expansion authorization are historical compatibility only.

**Goal:** Finish the maximum-width, continuous full-deck content-review sidebar against the approved v2.0 contract: review only an internally accepted `ReadingDeckBlueprint`, save one decision per page, submit one immutable batch for concentrated Codex processing, confirm the whole-deck plan in chat, re-review every new version, and preserve G3 visual Browser behavior.

**Architecture:** Python remains the authoritative writer for page decisions, batches, plans, source lineage, and G0. Node MCP exposes only current review operations and action-scoped host confirmations for batch submission/withdrawal and plan confirmation. React consumes one full-deck projection, owns only unsaved local drafts, renders complete text and evidence, and never infers Gate truth.

**Tech Stack:** Python dataclasses and schema-3 project kernel, Node.js ESM MCP with Zod, React 19 + TypeScript + Vite, Vitest/Testing Library, Node test runner, Python `unittest`.

---

### Task 11: Align the review projection and MCP surface to v2.0

**Files:**
- Modify: `src/ai_ppt_studio/application/content_review_service.py`
- Modify: `src/ai_ppt_studio/application/workspace_projection.py`
- Modify: `tests/test_v16_content_sidebar_projection.py`
- Modify: `tests/test_v16_workspace_projection.py`
- Modify: `mcp/server.mjs`
- Modify: `mcp/host-confirmation-assertion.mjs`
- Modify: `tests/mcp-server.test.mjs`
- Modify: `scripts/probe-mcp.mjs`

- [ ] Add failing Python tests proving a current reviewable blueprint projects directly as `content-user-reviewable`/`full-deck-review-ready`, that no framework/expansion head is required, that `neutral_title` and `reading_question` are preserved, and that an unavailable/unaccepted blueprint produces progress state without slide leakage.
- [ ] Run the focused Python tests and verify failures are caused by the legacy phase gates or field shape.
- [ ] Implement the smallest projection compatibility layer: prefer `content/reading-blueprint` plus both passed hard-gate records when present; accept the existing current content blueprint/acceptance during migration; never require framework confirmation or expansion authorization for the current projection.
- [ ] Add failing MCP tests for the exact 25-tool public surface. The eight current review tools are `get_content_sidebar_review_projection`, `save_content_page_decision`, `submit_content_review_batch`, `withdraw_content_review_batch`, `save_content_batch_revision_plan`, `confirm_content_batch_revision_plan`, `create_content_batch_change_set`, and `open_content_evidence_browser`. Assert the three legacy framework/expansion tools are absent.
- [ ] Run `node --test tests/mcp-server.test.mjs` and verify the tool-list assertions fail before implementation.
- [ ] Remove the three obsolete public tools while retaining batch submission, withdrawal, and plan-confirmation scope signing. Keep page save and plan save silent; batch submission is the only review write returning `follow_up_message`.
- [ ] Update `scripts/probe-mcp.mjs` to require the exact 25 tools and validate page-decision/withdrawal schemas without synthesizing confirmations.
- [ ] Run focused Node/Python tests, then full Python tests, `node --check`, `git diff --check`, and commit `feat: align content review runtime surface`.

### Task 12: Add the typed content-review client and route UI-03

**Files:**
- Create: `widget/src/lib/content-review-client.ts`
- Modify: `widget/src/types.ts`
- Modify: `widget/src/App.tsx`
- Modify: `widget/src/components/CompactWorkspace.tsx`
- Modify: `widget/src/test-fixtures.ts`
- Modify: `widget/src/CompactWorkspace.v16.test.tsx`
- Modify: `widget/src/PhaseB.test.tsx`
- Modify: `widget/src/ReviewSurfaceRouter.test.tsx`

- [ ] Write failing routing tests: blueprint space loads `get_content_sidebar_review_projection`; production/hard-gate progress does not expose slide content or framework/authorization buttons; review-ready renders the content document; visual space still opens G3 Browser.
- [ ] Run the focused Vitest files and verify the new route/client expectations fail.
- [ ] Define required TypeScript types for source version, revision, material mode, chapters, every complete slide field, decision state, review progress, batch, previous round, and stable errors. Do not make complete copy/evidence/notes optional merely to hide invalid data.
- [ ] Implement `load`, `saveDecision`, `submitBatch`, `withdrawBatch`, and plan-status reads. Each successful write replaces the authoritative snapshot and refetches the projection; no projection/page-save call sends a follow-up.
- [ ] Route UI-03 to progress state or the full-deck document. Remove content-mode professional Browser as the primary action; keep visual Browser unchanged.
- [ ] Run the focused Widget tests and commit `feat: route current content review into sidebar`.

### Task 13: Render the complete maximum-width deck and page decisions

**Files:**
- Create: `widget/src/components/content-review/ContentReviewProgress.tsx`
- Create: `widget/src/components/content-review/ContentReviewDocument.tsx`
- Create: `widget/src/components/content-review/ContentReviewDirectory.tsx`
- Create: `widget/src/components/content-review/ContentSlideSection.tsx`
- Create: `widget/src/components/content-review/PageDecisionEditor.tsx`
- Create: `widget/src/components/content-review/ReviewBatchFooter.tsx`
- Create: `widget/src/content-review/ContentReviewDocument.test.tsx`
- Create: `widget/src/content-review/PageDecisionEditor.test.tsx`
- Create: `widget/src/content-review/ContentReviewLongDeck.test.tsx`
- Create: `widget/src/content-review/ContentReviewResponsive.test.tsx`
- Create: `widget/src/__fixtures__/content-sidebar-review.json`
- Modify: `widget/src/components/ProjectAssetImage.tsx`
- Modify: `widget/src/styles.css`

- [ ] Write failing complete-reading tests using unique strings for neutral title, page task, reading question, full visible copy, identity, material/source/location/use/treatment, evidence gap, analysis/proposal, mapping, notes, reading quality, and previous/next relations. Assert one continuous document, no tabs/carousel, no desired customer judgment, and no ellipsis/clamp contract.
- [ ] Write failing editor tests for four mutually exclusive decisions; approved optional comment; three required inline comments; whitespace/1201-code-point rejection; save error and revision/source conflict draft retention; saved-comment editing; and merge/delete wording.
- [ ] Implement the continuous document, overlay/compact directory, next-incomplete navigation, and stable anchors without a permanent directory column.
- [ ] Implement each slide as full copy plus real evidence/gap, then notes/quality/relations and the inline editor. Use `ProjectAssetImage` only for real asset refs; never substitute generic illustrations.
- [ ] Implement silent page saves and a batch footer disabled by incomplete pages, dirty editors, pending/failed saves, count mismatch, or revision/source conflict. On successful submission freeze controls and send the returned follow-up exactly once; retrying a failed follow-up must not resubmit the batch.
- [ ] Add maximum-width CSS with `width:100%`, `min-width:0`, no centered max-width, wide copy/evidence grid, below-900 single column, complete wrapping, visible focus, and no horizontal overflow. Add near-viewport lazy asset loading with an accessibility-safe fallback.
- [ ] Test 10/24/60 pages and 480/900/1200/1440 containers, run `npm run build`, and commit `feat: build full-deck sidebar review UI`.

### Task 14: Add read-only content evidence Browser and protect G3

**Files:**
- Modify: `mcp/review-bridge.mjs`
- Modify: `mcp/server.mjs`
- Modify: `tests/review-bridge.test.mjs`
- Modify: `tests/mcp-server.test.mjs`
- Modify: `widget/src/lib/content-review-client.ts`
- Modify: `widget/src/components/content-review/ContentSlideSection.tsx`
- Create: `widget/src/content-review/ContentEvidenceBrowser.test.tsx`
- Modify: `widget/src/ProfessionalReviewApp.test.tsx`
- Modify: `widget/src/ProfessionalReviewApp.e2e.test.tsx`
- Modify: `widget/src/ProfessionalReviewLongDocument.test.tsx`

- [ ] Write failing tests for an exact `content-evidence` session scoped to project/source/slide/material with no page-decision or ReviewMark save capability.
- [ ] Implement `open_content_evidence_browser` validation and a short-lived read-only session allowing original, crop, source/slide comparison, and adjacent-slide comparison only.
- [ ] Add `放大查看原材料` only for actual evidence assets. Opening/closing the Browser must not mutate decision or draft state.
- [ ] Remove new content-mode entry into ProfessionalReviewApp while retaining historical content fixtures read-only and preserving every visual/G3 review behavior.
- [ ] Run Node Browser tests and all visual Browser Vitest regressions; where loopback listen is sandbox-blocked, rerun the same tests with narrowly escalated permissions instead of changing code. Commit `feat: add read-only content evidence Browser`.

### Task 15: Align Skill and workflow documentation

**Files:**
- Modify: `skills/ai-ppt-studio/SKILL.md`
- Modify: `skills/ai-ppt-studio/references/content-workflow.md`
- Modify: `skills/ai-ppt-studio/references/native-workbench.md`
- Modify: `skills/ai-ppt-studio/references/review-and-feedback.md`
- Modify: `skills/ai-ppt-studio/references/runtime-workflow.md`
- Modify: `tests/test_skill_workflow.py`

- [ ] Write failing text-contract tests requiring automatic full-content production after Mission, two internal hard gates, neutral titles, full sidebar review, silent page saves, one submitted batch, a whole-deck plan, full new-version re-review, current-source G0, evidence-only content Browser, and preserved G3 Browser. Assert current instructions do not require framework/expansion authorization or desired customer judgment.
- [ ] Update only current workflow text; label old operations as historical compatibility where they must remain documented.
- [ ] Run Skill tests and link checks, then commit `docs: align content review workflow with v2 baseline`.

### Task 16: Extend deterministic previews and automated acceptance

**Files:**
- Modify: `scripts/seed-v16-ui-project.py`
- Modify: `scripts/create-widget-preview.mjs`
- Modify: `scripts/run-v16-ui-acceptance.mjs`
- Modify: `scripts/probe-mcp.mjs`
- Modify: `tests/test_v16_ui_seed.py`
- Modify: `tests/test_v16_support_scripts.py`
- Create: `docs/validation/2026-08-14-content-sidebar-review-acceptance.md`

- [ ] Write failing seed/support tests for content-production progress, hard-gate progress/failure, 10-page ready, 24-page mixed decisions, 60-page long review, save failure, source conflict, submitted batch, proposed plan, and new-version zero-decision states. Mark every fixture `deterministic-contract-fixture-not-real-project-proof`.
- [ ] Build previews at 480/900/1200/1440 and capture complete content/evidence/notes, three inline editors, 23/24 blocked, 24/24 ready, submitted/frozen, v2 zero-inherited decisions, 60 pages, and G3 visual Browser.
- [ ] Assert no overflow, full available width, wide/stacked columns, all pages, untruncated copy, lazy images, dirty-editor submission blocking, no old dual-authorization UI, and exactly one follow-up after submit.
- [ ] Run build, Node, Widget, UI acceptance, MCP probe, and Python suites. Record automated/deterministic evidence separately from missing real-host proof; do not change the acceptance ledger from preview-only evidence.
- [ ] Commit automation and the honest validation record separately.

### Task 17: Full regression, review, and non-destructive integration

**Files:**
- Verify all files changed by Tasks 1–16 and the latest four root baselines.
- Modify only files whose failing regression demonstrates a defect.

- [ ] Run `npm run quality`, full Python `unittest`, acceptance-ledger regeneration, `compileall`, and `git diff --check`.
- [ ] Map every current UI-03 v2.0 acceptance rule to an automated test and identify the rows still awaiting genuine host/Browser/PowerPoint evidence.
- [ ] Scan current UI/MCP/Skill paths for framework confirmation, expansion authorization, desired customer judgment, conclusion-first title, content Browser primary review, and fixed content multi-agent claims. Allow only explicit historical compatibility.
- [ ] Verify every public operation/type/error has one producer, consumer, and test; check revision/source race handling, frozen immutability, no inherited decisions, G0 lineage, full text/evidence, page-save silence, maximum width, and G3 regression.
- [ ] Load `superpowers:requesting-code-review` and perform a full-diff review without dispatching per-task implementers. Fix accepted findings test-first and rerun the full suite.
- [ ] Integrate into the dirty primary worktree by applying only the isolated commit series on top of the user's current files. Resolve overlapping Gate/release/UI changes in favor of the complete primary implementation and v2.0 baselines; never overwrite, reset, or drop the user's modifications or protective stashes.
- [ ] Verify the integrated primary worktree, record exact remaining real-host evidence gaps, and only then mark the goal complete.

## Completion criteria

- New UI-03 has no framework-confirmation or full-deck-authorization prerequisite or control.
- A reviewable accepted deck renders every page once, continuously, with neutral titles, complete text, identities, evidence/gaps, source/use/treatment, mapping, notes, quality, and relations.
- All four decisions persist; non-approved comments are required; failed saves retain drafts; page saves are silent.
- The whole batch is frozen and submitted only when complete; Codex processes it once and returns a whole-deck plan; every new version starts a full re-review.
- G0 remains separate and current-source bound.
- Content Browser is evidence-only; visual G3 Browser remains unchanged.
- 480/900/1200/1440 and 10/24/60-page checks pass without truncation or horizontal overflow.
- Automated, deterministic, and real-host evidence are not conflated.
- No unrelated primary-worktree changes or stashes are lost.
