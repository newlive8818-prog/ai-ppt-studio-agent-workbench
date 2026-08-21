# Review Surface Prototype Fidelity and Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将内容全稿审核页和视觉专业审核页迁移到唯一运行入口，并按已确认的 07/08 原型还原页面结构、阅读节奏、反馈位置和状态表达，同时建立可证明的视觉、Runtime、宿主和 AI 回执验收链路。

**Architecture:** 先冻结源码与设计权威，再把当前 v22 Runtime 投影接入唯一 Review Surface 路由；React 只消费正式投影，原型负责页面结构和交互位置，四份基线负责业务、状态和系统合同。内容审核、视觉锚点、完整视觉合同、宿主通知/AI 回执分别完成并验收，最后用截图证据、自动化测试和真实宿主证据汇总，不把逻辑测试或本地预览当作真实能力验收。

**Tech Stack:** React 19、TypeScript、Vitest、Testing Library、Node.js MCP/Review Bridge、Python schema-3 Runtime、Playwright、Markdown 基线、JSON 结构化验收证据。

---

## Scope and authority

- 当前项目根目录：`/Users/defei/Documents/我的空间/workspace/memory/产品研究/PPT大师/PPT-codex-app`。
- 实现候选 worktree：`/private/tmp/ai-ppt-v22-TmBomR`，分支 `codex/v22-unified-runtime`。
- 主目录当前仍有旧 `ProfessionalReviewApp`、`ContentReviewPanel` 和迁移期侧边栏实现；执行前必须决定 v22 是否成为唯一实现基线。
- [07-visual-anchor-chat-collaboration-prototype.html](../../../prototypes/07-visual-anchor-chat-collaboration-prototype.html) 负责视觉专业审核页的结构、视觉层级、交互位置和阅读方式。
- [08-content-full-deck-review-v7-inline-feedback.html](../../../prototypes/08-content-full-deck-review-v7-inline-feedback.html) 负责内容全稿审核页的结构、章节节奏、图文同屏和判断控件位置。
- 原型中的示例客户、示例文字、旧“侧边栏”命名和旧入口身份不复制到正式产品；用户最新明确决定优先于历史文档。
- 不恢复五空间、常驻产品导航、聊天式审核侧栏、独立项目仪表盘或重复 Gate 页面。

## Stage gates

| 阶段 | 目标 | 必须通过的出口条件 | 未通过处理 |
|---|---|---|---|
| 0 | 源码与权威冻结 | 唯一 worktree、唯一入口、原型边界写入计划和验证记录 | 停止 UI 开发，先解决分支/脏工作树冲突 |
| 1 | 差异账本与投影准备 | 07/08 结构节点、交互动作、状态字段全部有映射 | 不允许凭感觉改 CSS |
| 2 | 内容审核页 | 08 结构与 PageDecision 全部通过 | 只修内容页，不进入视觉页 |
| 3 | 视觉锚点页 | 07 顶栏、矩形反馈、批次记录和窄宽布局通过 | 不进入完整合同页 |
| 4 | 完整视觉合同页 | 合同文档头、Anchor Evidence、全部逐页合同和抽屉通过 | 不进入真实回执联调 |
| 5 | 回执与数据合同 | 保存、宿主通知、AI 接收可分离并能证明 | 只能显示待验证，禁止声称已接收 |
| 6 | 自动化与真实验收 | 截图、逻辑、长文档、真实宿主证据齐全 | 标记 CapabilityGap，不得发布为已完成 |
| 7 | 合并与交付 | 回归通过、差异清零、变更可回滚 | 保留独立分支，不合并 |

---

### Task 0: Freeze the source baseline and authority

**Files:**

- Read/possibly modify after explicit confirmation: `00-唯一研发基线索引-v1.0.md`
- Read/possibly modify after explicit confirmation: `01-产品需求基线-v1.0.md`
- Read/possibly modify after explicit confirmation: `02-系统详细设计-v1.0.md`
- Read/possibly modify after explicit confirmation: `03-UI设计与交互规范-v1.0.md`
- Create: `产品代码/docs/validation/2026-08-17-review-surface-source-selection.md`

- [ ] **Step 1: Record both worktrees without mutation**

Run from the project root:

```bash
git worktree list --porcelain
git -C /private/tmp/ai-ppt-v22-TmBomR status --short --branch
git status --short --branch
```

Expected: the source-selection record names the main directory and the v22 worktree, records their branches and HEADs, and states that neither dirty worktree may be overwritten.

- [ ] **Step 2: Build the migration matrix**

The record must map each active responsibility to exactly one owner:

| Responsibility | Selected owner |
|---|---|
| React review entry | one router only |
| Content projection | v22 content projection or explicitly migrated equivalent |
| Visual projection | v22 visual projection or explicitly migrated equivalent |
| Runtime writes | schema-3 authoritative Runtime |
| Browser/Review Bridge | one MCP adapter path |
| Old sidebar | compatibility-only, never active UI |

- [ ] **Step 3: Register the latest prototype rule**

The authority record must state: 07/08 structure, hierarchy, interaction location, and responsive behavior are implementation requirements; their sample data and obsolete sidebar wording are not product data requirements.

- [ ] **Step 4: Verify the authority record**

Run:

```bash
git diff --check -- 00-唯一研发基线索引-v1.0.md 01-产品需求基线-v1.0.md 02-系统详细设计-v1.0.md 03-UI设计与交互规范-v1.0.md 产品代码/docs/validation/2026-08-17-review-surface-source-selection.md
```

**Stage 0 acceptance:** one selected implementation worktree, one active review entry, no destructive cleanup, explicit prototype authority, and a clean source-selection record. Any unresolved duplicate route blocks the next stage.

---

### Task 1: Create the prototype fidelity ledger and fixture contract

**Files:**

- Create: `产品代码/docs/validation/2026-08-17-review-surface-prototype-fidelity-ledger.md`
- Modify: `产品代码/widget/src/types/content-review.ts` only if the projection is missing chapter/deck-intro fields
- Modify: `产品代码/widget/src/types/visual-review.ts` only if the projection is missing anchor-evidence or receipt fields
- Modify: `产品代码/widget/src/review-surface-validation.ts`
- Test: `产品代码/widget/src/review-surface-validation.test.ts` or the existing validation test file

- [ ] **Step 1: Inventory the 08 required nodes**

The ledger must contain mappings for `.head`, `.head-main`, `.progress`, `.chapter-nav`, `.deck-intro`, `.chapter`, `.page`, `.page-body`, `.actions`, `.feedback-editor`, `.more`, and `.review-summary`.

- [ ] **Step 2: Inventory the 07 required nodes**

The ledger must contain mappings for `.topbar`, `.project-identity`, `.review-view-switch`, `.anchor-workbench`, `.anchor-toolbar`, `.slide-stage`, `.anchor-feedback-composer`, `.feedback-panel`, `.status-timeline`, `.contract-document-head`, `#anchor-evidence`, `.visual-contract-list`, `.contract-outline`, and `.contract-mark-drawer`.

- [ ] **Step 3: Define projection invariants before UI work**

The validation contract must reject:

```text
visual-professional projection with anchors.length !== 3
content-full-deck projection with duplicate slide IDs or invalid section order
visual contract projection without ordered slide contracts
receipt facts without artifact/sourceVersion/revision identity
```

- [ ] **Step 4: Add failing validation tests**

Tests must cover two anchors, four anchors, duplicate anchor IDs, invalid section order, missing Anchor Evidence data, and an AI receipt tied to a different source version. Run:

```bash
npm run test:widget -- review-surface-validation
```

Expected before implementation: the new invalid fixtures fail validation.

**Stage 1 acceptance:** every required prototype region has a current component/projection owner, every deliberate deviation is recorded with a reason, and invalid page counts/lineage are rejected before rendering.

---

### Task 2: Migrate the single active review route

**Files:**

- Modify: `产品代码/widget/src/main.tsx`
- Modify or create: `产品代码/widget/src/ReviewSurfaceRouter.tsx`
- Modify: `产品代码/widget/src/ProfessionalReviewApp.tsx` only to remove it from the active route after parity tests
- Modify: `产品代码/widget/src/components/content-review/ContentReviewPanel.tsx` only to keep a compatibility adapter, not an active sidebar surface
- Test: `产品代码/widget/src/MainSurfaceRouter.test.tsx`
- Test: `产品代码/widget/src/ReviewSurfaceRouter.test.tsx`

- [ ] **Step 1: Add route-selection tests**

Tests must prove:

- content review renders `ContentFullDeckReviewPage`;
- visual review renders `VisualProfessionalReviewPage`;
- evidence review renders only the read-only evidence layer;
- the old `content-sidebar-progress` surface is not selected for a current v2.2 ReviewSession;
- no five-space navigation, product dashboard, or chat transcript is rendered.

- [ ] **Step 2: Switch the active entry only after tests fail for the old route**

Keep old components importable for compatibility until route tests prove they are unreachable from a current projection. Do not delete them in the same change as route switching.

- [ ] **Step 3: Verify active surface ownership**

Run:

```bash
rg -n "ProfessionalReviewApp|content-sidebar-progress|五空间导航|项目仪表盘|聊天记录" 产品代码/widget/src
npm run test:widget -- MainSurfaceRouter ReviewSurfaceRouter
```

Expected: compatibility references are either isolated behind a legacy adapter or explicitly covered by migration tests; no current route renders them.

**Stage 2 acceptance:** a current ReviewSession has one active review route, both review pages open from the approved entry, and legacy sidebar code cannot become the current surface through normal projection data.

---

### Task 3: Rebuild the 08 content full-deck review surface

**Files:**

- Modify: `产品代码/widget/src/content-review/ContentFullDeckReviewPage.tsx`
- Modify: `产品代码/widget/src/content-review/ContentMaterialView.tsx`
- Keep/modify: `产品代码/widget/src/content-review/PageDecisionControl.tsx`
- Modify: `产品代码/widget/src/styles/content-review.css`
- Modify: `产品代码/widget/src/types/content-review.ts` if chapter metadata is missing
- Modify: v22 Runtime content projection files under `产品代码/src/ai_ppt_studio/application/content_review/` and `产品代码/src/ai_ppt_studio/domains/content/` only when the UI cannot receive authoritative chapter data
- Test: `产品代码/widget/src/content-review/ContentFullDeckReviewPage.test.tsx`
- Test: `产品代码/widget/src/content-review/ContentReviewResponsive.test.tsx`
- Test: `产品代码/widget/src/content-review/ContentReviewLongDeck.test.tsx`

- [ ] **Step 1: Add failing DOM-structure tests**

The rendered page must contain:

```text
.content-review-head
.content-review-progress
.content-review-chapter-nav
.content-review-deck-intro
[data-content-chapter] for every section
[data-content-slide] in final order
.content-review-summary
```

The test must also assert that the full visible copy, evidence identity, speaker notes, material source, and cross-page relationship remain in the DOM without ellipsis or hover-only content.

- [ ] **Step 2: Implement chapter projection and rendering**

Render chapters from authoritative projection data. Do not infer chapter boundaries from title text in React. Each chapter must render its number, title, task, pages, and an explicit expand action when compact pages are used.

- [ ] **Step 3: Restore the 08 page rhythm**

Implement the prototype ordering:

```text
project header → progress → chapter navigation → deck intro → chapters → full-review summary
```

Use the prototype as the structural reference but use current project data and current neutral-title/content contracts.

- [ ] **Step 4: Preserve PageDecision behavior**

Keep four mutually exclusive choices, 42 CSS px minimum target height, 2×2 layout below 380 CSS px, non-approved required comments, local draft preservation, and single-page save semantics.

- [ ] **Step 5: Verify material loading behavior**

Ensure the current page and the material required to judge it are not replaced by a permanent placeholder. Lazy loading may remain for distant pages only if the current page has a deterministic load or retry path.

- [ ] **Step 6: Run focused tests**

```bash
npm run test:widget -- ContentFullDeckReviewPage ContentReviewResponsive ContentReviewLongDeck
```

**Stage 3 acceptance:** at 360, 760, 1000, and 1440 CSS px the page follows the 08 structure; all pages remain in final order; full copy/material/evidence are readable; PageDecision and local feedback work; incomplete pages cannot submit; no old sidebar identity appears.

---

### Task 4: Rebuild the 07 visual anchor review surface

**Files:**

- Modify: `产品代码/widget/src/visual-review/VisualProfessionalReviewPage.tsx`
- Modify: `产品代码/widget/src/visual-review/AnchorResultsView.tsx`
- Modify: `产品代码/widget/src/visual-review/RegionFeedbackEditor.tsx`
- Modify: `产品代码/widget/src/styles/visual-review.css`
- Test: `产品代码/widget/src/visual-review/VisualProfessionalReviewPage.test.tsx`
- Test: `产品代码/widget/src/visual-review/VisualReviewResponsive.test.tsx`

- [ ] **Step 1: Add failing topbar and layout assertions**

Tests must assert:

- white topbar with project identity, AI mark, segmented two-view switch, and compact status;
- exactly three anchor tabs;
- main anchor workbench and right feedback record area;
- no chat bubbles, chat transcript, product navigation, or five-space controls.

- [ ] **Step 2: Restore rectangle-only feedback flow**

The formal path must remain:

```text
开始标注 → pointer drag → numbered rectangle → composer directly below image → 加入本轮反馈
```

A click without a positive rectangle must not create a formal feedback item.

- [ ] **Step 3: Remove unconfirmed visible presets**

Remove the visible `整页/上半区/下半区/左侧/右侧` preset group from the default UI. Keep only pointer-drag selection unless a later product decision adds a tested use case.

- [ ] **Step 4: Reorganize the right panel as a record**

The right panel must contain only:

- current feedback records;
- batch identity and submission state;
- persistence state;
- host notification state;
- AI receipt state;
- retry/recovery actions when justified.

Do not render a conversational message stream.

- [ ] **Step 5: Run focused tests**

```bash
npm run test:widget -- VisualProfessionalReviewPage VisualReviewResponsive
```

**Stage 4 acceptance:** 07’s topbar, workbench, bottom composer, record panel, rectangle feedback, multi-item submission, comparison dialog, and 360/760/1000/1440 layouts match the ledger; all three anchors load real assets; no single-point formal feedback or chat-style side panel remains.

---

### Task 5: Rebuild the 07 full visual contract document

**Files:**

- Modify: `产品代码/widget/src/visual-review/VisualContractView.tsx`
- Modify: `产品代码/widget/src/styles/visual-review.css`
- Modify: `产品代码/widget/src/review-surface-validation.ts`
- Test: `产品代码/widget/src/visual-review/VisualProfessionalReviewPage.test.tsx`
- Test: `产品代码/tests/test_v22_visual_lineage.py`
- Test: `产品代码/tests/test_v22_visual_review_projection.py`

- [ ] **Step 1: Add failing structure assertions**

The contract view must expose stable semantic anchors for:

```text
.visual-contract-title-page
[data-contract-logical-object="deck-design-system"]
[data-contract-logical-object="anchor-slide-evidence"]
.visual-slide-contract
.visual-contract-outline
.visual-overlay-drawer
```

- [ ] **Step 2: Restore document order**

Render:

```text
Visual Contract · User Review → 完整视觉合同 → Deck Design System → Anchor Slide Evidence → 全部 Slide Visual Contract
```

The contract must remain one continuous reading document. Technical artifact IDs stay in a collapsed technical section and must not replace user-readable contract fields.

- [ ] **Step 3: Preserve review marks**

Keep field marks, selected-text marks, multi-mark draft collection, edit/remove before save, unified save, source/revision conflict handling, and overlay drawers. Contract marks must never enter the anchor feedback batch.

- [ ] **Step 4: Run focused tests**

```bash
npm run test:widget -- VisualProfessionalReviewPage
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest tests.test_v22_visual_lineage tests.test_v22_visual_review_projection -v
```

**Stage 5 acceptance:** the complete contract contains system, anchor evidence, and every slide contract in order; directory and marks drawers cover the document instead of permanently narrowing it; fields and selected text are markable; no three-page summary replaces the full contract.

---

### Task 6: Close the host notification and AI receipt contract

**Files:**

- Modify: `产品代码/src/ai_ppt_studio/application/visual_review_service.py`
- Modify: `产品代码/src/ai_ppt_studio/application/review_session_service.py`
- Modify: `产品代码/src/ai_ppt_studio/domains/review/contracts.py`
- Modify: `产品代码/src/ai_ppt_studio/domains/visual/review_contracts.py`
- Modify: `产品代码/mcp/review-bridge.mjs`
- Modify: `产品代码/mcp/tools/review-tools.mjs`
- Modify: `产品代码/widget/src/visual-review/VisualReceiptRecoveryControls.tsx`
- Test: `产品代码/tests/test_v22_review_session.py`
- Test: `产品代码/tests/test_v22_visual_review_service.py`
- Test: `产品代码/tests/review-bridge.test.mjs`
- Test: `产品代码/widget/src/visual-review/VisualProfessionalReviewPage.test.tsx`

- [ ] **Step 1: Define receipt identity**

Every receipt must bind:

```text
review_session_id
feedback or mark artifact ref
source_version
revision
receipt ref
created_at
```

- [ ] **Step 2: Implement explicit state transitions**

The projection must distinguish:

```text
saved → host notification pending/sent/failed/unavailable
saved → AI receipt pending/received/rejected/unverified
```

A successful save cannot set host or AI state to success. A missing host callback must remain unavailable or unverified.

- [ ] **Step 3: Test failure and recovery**

Cover unavailable host, notification failure, timeout, retry, duplicate command replay, stale source version, revision conflict, and reopened review session.

- [ ] **Step 4: Verify capability reporting**

Remove unconditional projection claims that obscure real capability. `unknown` is valid only when the host genuinely cannot report capability and must include a user-readable reason.

**Stage 6 acceptance:** the UI and Runtime independently prove persistence, host notification, and AI receipt; no timer or local state produces a false success; failures preserve drafts and retries are idempotent.

---

### Task 7: Fix acceptance automation and evidence boundaries

**Files:**

- Modify: `产品代码/scripts/run-v22-ui-acceptance.mjs`
- Modify: `产品代码/scripts/v22-ui-acceptance-evidence.mjs`
- Create: `产品代码/tests/v22-prototype-fidelity.test.mjs`
- Create: `产品代码/docs/validation/2026-08-17-review-surface-acceptance.md`

- [ ] **Step 1: Make selectors semantic and scoped**

Replace stale selectors such as `.visual-contract-title-page code` with selectors emitted by the actual React contract. Scope text/readability checks to the current `.visual-slide-contract` instead of querying the whole page inside every loop.

- [ ] **Step 2: Add structural acceptance**

The browser runner must fail when any of these is missing:

```text
08 deck intro, chapter nav, chapter nodes, review summary
07 segmented topbar, anchor workbench, feedback composer, status record
contract title page, Anchor Slide Evidence, all slide contracts, overlay drawers
```

- [ ] **Step 3: Add responsive geometry assertions**

Run content and visual checks at 360, 760, 1000, and 1440 CSS px. Assert no horizontal overflow, no clipped text, no hidden primary action, 08 PageDecision 2×2 below 380 px, and 07 assistant below the workbench on narrow screens.

- [ ] **Step 4: Add screenshot evidence**

Capture first viewport and interaction-state screenshots for:

- content page before/after non-approved feedback;
- anchor page before/after rectangle feedback;
- complete contract with Anchor Evidence;
- directory drawer;
- mark drawer;
- saved/unverified receipt state.

Screenshots are evidence for visual comparison only; they do not prove real host or AI capability.

- [ ] **Step 5: Run deterministic checks**

```bash
git diff --check
npm run typecheck
npm run test:node
npm run test:widget
npm run build
npm run accept:v22-ui
```

If Playwright cannot launch because of the current macOS sandbox, record the exact `CapabilityGap` and do not mark browser acceptance passed.

**Stage 7 acceptance:** stale selectors are removed, empty selector sets fail loudly, all prototype regions have automated structure checks, screenshots exist for all required states, and the evidence report distinguishes deterministic browser evidence from real-host evidence.

---

### Task 8: Full regression, real host verification, and merge gate

**Files:**

- Modify only as required by verified failures: implementation files from Tasks 2–7
- Create/update: `产品代码/docs/validation/2026-08-17-review-surface-acceptance.md`
- Do not modify: PPT runtime project data unless using the approved schema-3 Runtime command path

- [ ] **Step 1: Run full software regression**

```bash
npm run quality
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest discover -s tests -v
```

Expected: all current tests pass, no old active route is selected, and no new warning/error is introduced.

- [ ] **Step 2: Verify real Browser/Review Bridge behavior**

Using the actual approved host path, verify:

- review page opens for the current ReviewSession;
- closing and reopening restores scroll, active view, and drafts;
- anchor batch save is idempotent;
- contract mark save is independent;
- host notification status comes from a real send receipt;
- AI receipt status comes from a real receipt;
- stale source/revision is rejected without losing local drafts.

- [ ] **Step 3: Verify product boundary**

Confirm in the real surface:

- Codex conversation remains the only discussion channel;
- review pages contain no chat transcript;
- no five-space navigation or permanent sidebar is present;
- review pages do not provide G3/G0 buttons, PPTX download, or duplicate delivery pages.

- [ ] **Step 4: Write the final acceptance record**

The record must separate:

```text
automated logic evidence
deterministic browser/screenshot evidence
real Browser/Review Bridge evidence
unverified capability gaps
```

- [ ] **Step 5: Merge only after the gate is green**

Before merge:

```bash
git diff --check
git status --short
git log -1 --oneline
```

The merge request must list retained legacy adapters, deleted active surfaces, source/revision behavior, and rollback commit. No unrelated dirty worktree changes may be included.

**Stage 8 acceptance:** all software tests pass, visual evidence matches the 07/08 ledger, real host/review receipts are evidenced or explicitly marked as CapabilityGap, and the merged route is reversible without restoring five spaces or chat-style review.

---

## Final acceptance checklist

- [ ] One source worktree and one active review route are documented.
- [ ] 07 and 08 prototype structure is represented in the fidelity ledger.
- [ ] Content review restores deck intro, chapter navigation, chapters, full pages, inline feedback, and final summary.
- [ ] Visual anchor review restores white topbar, segmented views, rectangle feedback, bottom composer, record-style side panel, and batch submission.
- [ ] Complete visual contract restores contract head, Deck Design System, Anchor Slide Evidence, all slide contracts, directory drawer, and mark drawer.
- [ ] Exactly three anchors are enforced at Runtime, projection, UI, and acceptance levels.
- [ ] Save, host notification, and AI receipt are separate facts with artifact/revision identity.
- [ ] No five-space navigation, permanent sidebar, chat transcript, or duplicate Gate/delivery page is active.
- [ ] `npm run quality`, Python regression, deterministic browser checks, and real host checks are separately recorded.
- [ ] Any unavailable browser/host capability is recorded as `CapabilityGap`, never as a passed acceptance.

## Plan self-review

- **Spec coverage:** content structure, visual anchor interaction, complete contract reading, state separation, receipt evidence, source selection, responsive behavior, long-document performance, and acceptance evidence each have a dedicated task and stage gate.
- **No placeholders:** every stage names files, commands, expected evidence, and failure handling; unresolved host behavior is an explicit capability gap rather than an implementation placeholder.
- **Type consistency:** all UI tasks consume `ContentFullDeckReviewPage`, `VisualProfessionalReviewPage`, `AnchorResultsView`, and `VisualContractView`; Runtime tasks bind the same ReviewSession, artifact, sourceVersion, and revision identity.
