# Visual Review ViewModel And Projection Narrowing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Route the accepted visual professional review frontend through a closed VisualReviewPageViewModel, narrow the authoritative visual review projection to real frontend consumption, and remove visible source/Gate technical ledger copy without changing accepted layout or interactions.

**Architecture:** Python Runtime remains authoritative and emits only reviewable contract fields plus stable write/recovery identities. A pure TypeScript adapter owns compatibility mapping and returns a closed surface ViewModel; the active Router passes only that ViewModel to React. Review sessions, source versions, revisions, artifact references, and receipt capabilities remain non-document command context.

**Tech Stack:** Python 3 unittest, TypeScript 5, React 19, Vitest, Node MCP/Review Bridge, Git.

---

## Scope and rollback boundary

This plan implements only Slice F2 and the related visible-ledger correction. It does not change the accepted two-view layout, anchor rectangle workflow, inline feedback batch, overlay directions, or mark interactions. It does not reopen content-review UI, claim a real host/Gate/PowerPoint acceptance, merge, push, install, or publish. The retired legacy G0 cleanup has a separate plan and commit.

### Task 1: Preserve and verify RED contract tests

**Files:**

- Test: widget/src/visual-review/visual-review-page-view-model.test.tsx
- Test: widget/src/visual-review/VisualProfessionalReviewPage.test.tsx
- Test: tests/test_v22_visual_review_service.py
- Test: tests/test_v22_source_shape.py

- [ ] **Step 1: Keep the adapter boundary assertions**

The adapter test must pass review_session, gate_status, slide governance fields, and future backend extras, then assert they are absent from output. It must assert this compatibility result:

    expect(viewModel.review.slide_visual_contracts[0]).toMatchObject({
      core_claim: "业务断点需要被看见",
      visible_copy: ["页面可见文案"],
      source_refs: ["source-1"],
      anchor_title: "经营协同仍有断点",
      validation_purpose: "说明当前问题",
    });

- [ ] **Step 2: Keep Runtime projection assertions**

    self.assertNotIn("gate_status", projection)
    self.assertEqual(
        set(projection["anchor_identity"]),
        {"slide_ids", "selection_reason", "native_first_frozen"},
    )
    self.assertNotIn("identity_labels", projection["slide_visual_contracts"][0])
    self.assertIn("visible_copy", projection["slide_visual_contracts"][0])
    self.assertIn("source_refs", projection["slide_visual_contracts"][0])

- [ ] **Step 3: Run RED**

    cd 产品代码
    npx vitest run --configLoader runner widget/src/visual-review/visual-review-page-view-model.test.tsx
    PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src       python3 -m unittest -v tests.test_v22_visual_review_service tests.test_v22_source_shape

Expected: missing adapter module, existing gate_status projection, and Router bypass failures only.

### Task 2: Add the closed TypeScript ViewModel adapter

**Files:**

- Create: widget/src/visual-review/visual-review-page-view-model.ts
- Modify: widget/src/types/visual-review.ts
- Test: widget/src/visual-review/visual-review-page-view-model.test.tsx

- [ ] **Step 1: Define the closed surface contract**

Export VisualReviewPageViewModel and this pure function:

    export function toVisualReviewPageViewModel(
      data: VisualReviewSurfaceData,
    ): VisualReviewPageViewModel;

The output retains the surface envelope and stable command/recovery identities, but its review body does not expose review_session or gate_status.

- [ ] **Step 2: Centralize compatibility mapping**

Use these exact precedence rules:

    visible_copy
      -> visible_copy
      -> visible_copy_blocks[].text
      -> frozen_copy

    source_refs
      -> source_refs
      -> evidence_bindings[].source_ref/source_refs

    anchor_title
      -> anchor_title
      -> neutral_title
      -> title

    validation_purpose
      -> validation_purpose
      -> anchor_validation_purpose
      -> page_task

Never map page_task to core_claim. Copy only approved design-system and slide-contract fields. Output anchor_identity with only slide_ids, selection_reason, and native_first_frozen.

- [ ] **Step 3: Run the adapter test GREEN**

    cd 产品代码
    npx vitest run --configLoader runner widget/src/visual-review/visual-review-page-view-model.test.tsx

Expected: one test file passes with zero failed tests.

### Task 3: Route and render only the ViewModel

**Files:**

- Modify: widget/src/ReviewSurfaceRouter.tsx
- Modify: widget/src/visual-review/VisualProfessionalReviewPage.tsx
- Modify: widget/src/visual-review/AnchorResultsView.tsx
- Modify: widget/src/visual-review/VisualContractView.tsx
- Modify: widget/src/visual-review/anchor-feedback-validation.ts
- Modify: widget/src/visual-review/visual-contract-mark-validation.ts
- Modify: widget/src/review-draft/reviewDraftStore.ts
- Test: tests/test_v22_source_shape.py
- Test: widget/src/visual-review/VisualProfessionalReviewPage.test.tsx

- [ ] **Step 1: Route only the adapter output**

The active route must call:

    initialViewModel={toVisualReviewPageViewModel(validated)}

- [ ] **Step 2: Type React and validation inputs as the closed ViewModel**

VisualProfessionalReviewPage accepts initialViewModel. A temporary initialData alias is allowed for direct tests only if both props are VisualReviewPageViewModel. Production Router uses only initialViewModel. No production visual React module imports VisualReviewSurfaceData.

- [ ] **Step 3: Convert direct test fixtures through the adapter**

Existing tests may pass:

    initialData={toVisualReviewPageViewModel(visualData())}

Keep their behavior, layout, command payload, and recovery assertions unchanged.

- [ ] **Step 4: Verify Router and visual tests**

    cd 产品代码
    PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src       python3 -m unittest -v tests.test_v22_source_shape
    npx vitest run --configLoader runner       widget/src/visual-review/visual-review-page-view-model.test.tsx       widget/src/visual-review/VisualProfessionalReviewPage.test.tsx

Expected: all selected tests pass.

### Task 4: Narrow Runtime and TypeScript projection validation

**Files:**

- Modify: src/ai_ppt_studio/application/visual_review_service.py
- Modify: widget/src/review-surface-validation.ts
- Modify: widget/src/types/visual-review.ts
- Modify only affected Router/Review Bridge fixtures
- Test: tests/test_v22_visual_review_service.py
- Test: affected Node and Widget validation tests

- [ ] **Step 1: Reuse authoritative projection helpers**

In VisualReviewService.project(), use _project_deck_design_system() and _project_slide_contract(). Project anchor_identity as exactly:

    {
      "slide_ids": ...,
      "selection_reason": ...,
      "native_first_frozen": ...,
    }

Remove gate_status from the external projection. Keep review_session, source/revision, artifact references, host_submission_capability, and ai_receipt_capability at the Projection/Bridge boundary for trusted writes and recovery.

- [ ] **Step 2: Close TypeScript validation**

Do not require or allow identity_labels, evidence_bindings, analysis_or_proposal_blocks, solution_mapping_refs, previous_relation, next_relation, reading_quality, material_mode, gate_status, or arbitrary extra backend fields. Validate only approved design-system fields, the three-field anchor identity, approved slide fields, anchors, saved feedback/marks, and stable command/recovery identities.

- [ ] **Step 3: Run focused verification**

    cd 产品代码
    PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src       python3 -m unittest -v tests.test_v22_visual_review_service
    npm run typecheck
    npm run test:node

Expected: all selected checks pass. Loopback sandbox failures are environment boundaries, not product failures.

### Task 5: Remove visible technical ledger copy without changing layout

**Files:**

- Modify: widget/src/visual-review/VisualProfessionalReviewPage.tsx
- Modify: widget/src/visual-review/VisualContractView.tsx
- Test: widget/src/visual-review/VisualProfessionalReviewPage.test.tsx

- [ ] **Step 1: Remove only forbidden visible text**

Delete visible G1, G2, and “视觉确认” from the header ledger. Delete source/G3 title-page items, per-page user-reviewable, and the generic “技术信息” module.

Keep project identity, tabs, single header, page count, production route, Deck Design System, Anchor Slide Evidence, all slide contracts, overlay drawers, mark interactions, save facts, host-notification facts, and AI-receipt facts. Hidden command/recovery context may retain sourceVersion, revision, and artifact references where recovery tests require them.

- [ ] **Step 2: Run visible-semantics tests**

    cd 产品代码
    npx vitest run --configLoader runner       widget/src/visual-review/VisualProfessionalReviewPage.test.tsx       -t 'keeps source and Gate identity|converges the contract first screen|keeps the accepted single 64px header'

Expected: selected tests pass and visible DOM has no source/G1/G2/G3/user-reviewable/技术信息 document ledger.

### Task 6: Synchronize the four authoritative baselines

**Files:**

- Modify: ../00-唯一研发基线索引-v1.0.md
- Modify: ../01-产品需求基线-v1.0.md
- Modify: ../02-系统详细设计-v1.0.md
- Modify: ../03-UI设计与交互规范-v1.0.md

- [ ] **Step 1: Update only point-in-time implementation status**

After fresh verification, change Slice F2 “尚未启动” statements to “已完成本地工程实现” and bind the independent commit. Preserve this boundary:

    该状态只证明本地 ViewModel、活动 Router、Runtime/Review Bridge/MCP 外部投影和自动化工程边界；
    不证明真实客户 ReviewSession、宿主打开/通知、AI 接收、G3、PowerPoint、发布或新的用户 UI 验收。

Do not change product requirements, accepted behavior, Gate rules, or prototype authority.

- [ ] **Step 2: Validate links, conflict markers, and whitespace**

    rg -n '^(<<<<<<<|=======|>>>>>>>)'       ../00-唯一研发基线索引-v1.0.md       ../01-产品需求基线-v1.0.md       ../02-系统详细设计-v1.0.md       ../03-UI设计与交互规范-v1.0.md .
    git diff --check

Expected: zero conflict markers and zero whitespace errors.

### Task 7: Full verification and independent commit

- [ ] **Step 1: Run full verification**

    cd 产品代码
    PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=src       python3 -m unittest discover -s tests
    npm run typecheck
    npm run test:node
    npm run test:widget -- --configLoader runner
    npm run build

Expected: zero failures. If Vite cannot write node_modules/.vite-temp, use the runner configuration or an authorized writable verification context and report that environment boundary separately.

- [ ] **Step 2: Verify Git integrity and prototype identity**

    git diff --check
    git status --short --branch
    rg -n '^(<<<<<<<|=======|>>>>>>>)'       ../00-唯一研发基线索引-v1.0.md       ../01-产品需求基线-v1.0.md       ../02-系统详细设计-v1.0.md       ../03-UI设计与交互规范-v1.0.md .
    shasum -a 256 prototypes/08-content-full-deck-review-v7-inline-feedback.html

Expected: only scoped files changed, no conflict markers, and accepted content-review HTML unchanged.

- [ ] **Step 3: Commit the rollback unit**

Stage only the four baselines, this plan, the F2 source files, and F2 tests, then run:

    git commit -m "fix: narrow visual review projection"

Expected: one local commit; no merge, push, install, or publish.
