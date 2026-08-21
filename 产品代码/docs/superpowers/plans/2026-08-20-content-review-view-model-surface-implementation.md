# Content Review ViewModel Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建一个只消费 `ContentReviewPageViewModel` 的内容全稿审核生产候选组件，忠实呈现用户已验收的 08 前端结构，并以受控回调保留四类判断、页内意见、单页保存和全稿提交入口。

**Architecture:** 当前活动 `ContentFullDeckReviewPage` 继续承担旧投影、Runtime 校验、草稿恢复和写入，不在本切片中修改。新增 `ContentReviewViewModelSurface` 作为纯前端阅读与交互表面；它只接收 ViewModel、项目素材读取桥和受控动作，不读取 `ContentReviewProjection`，也不调用保存/提交 MCP。材料画面通过独立的延迟读取组件呈现，只消费 `visualId`、`assetRef`、`altText`。

**Tech Stack:** React 19、TypeScript 5.7、Vitest 3、Testing Library、现有 `PageDecisionControl` 与 `ProjectAssetImage`。

---

## Scope and file ownership

**Create:**

- `产品代码/widget/src/content-review/ContentReviewViewModelSurface.tsx`：只消费 ViewModel 的连续阅读与受控审核表面。
- `产品代码/widget/src/content-review/ContentReviewMaterialVisuals.tsx`：只呈现 ViewModel 允许的项目页面画面，延迟读取项目资产。
- `产品代码/widget/src/content-review/ContentReviewViewModelSurface.test.tsx`：冻结 DOM、禁止模块、动作回调、延迟素材读取和提交条件。
- `产品代码/widget/src/content-review/ContentReviewViewModelResponsive.test.tsx`：冻结最大宽度、宽屏双栏和窄屏回退合同。
- `产品代码/widget/src/styles/content-review-view-model.css`：生产候选表面的隔离样式。

**Modify:**

- `产品代码/widget/src/content-review/content-review-page-view-model.ts`：把只适用于 adapter 初始值的 `dirty: false` 字面量收窄错误修正为前端受控状态需要的 `dirty: boolean`；adapter 仍只输出 `false`。

**Do not modify:**

- `产品代码/widget/src/content-review/ContentFullDeckReviewPage.tsx`
- `产品代码/widget/src/content-review/ContentMaterialView.tsx`
- `产品代码/widget/src/ReviewSurfaceRouter.tsx`
- `产品代码/widget/src/review-surface-validation.ts`
- `产品代码/widget/src/types/content-review.ts`
- `产品代码/src/ai_ppt_studio/**`
- `产品代码/mcp/**`
- PPT 运行数据目录

## Resolved design decisions

- 既有前端优先合同、08 HTML 和用户验收已经完成 brainstorming 设计门；本计划不创建第二套设计或第二个 UI 验收门。
- 新组件命名为 `ContentReviewViewModelSurface`，明确它是活动路由接入前的生产候选表面；下一切片由控制器将真实草稿、冲突和写入状态投给它。
- `projectRoot` 与 `HostBridge` 是项目资产读取能力，不属于用户可见内容字段，可以作为独立基础设施 props；页面业务内容只来自 `ContentReviewPageViewModel`。
- 所有判断与输入均受控。组件不保存第二套事实，不自行修改 ViewModel；它通过 `onDecisionChange`、`onCommentChange`、`onSavePageDecision` 和 `onSubmitReviewBatch` 报告用户动作。
- `localDraftState.dirty` 是前端当前状态而不是后端字段，必须允许 `true | false`；纯 adapter 的初始投影继续固定为 `false`。
- `draftContent.blocks` 按 `paragraph | bullet` 原序渲染；连续 bullet 合并为同一个列表，不显示 identity。
- 材料画面不显示图注或元数据目录；替代文字直接使用 ViewModel 的 `altText`。
- 空材料页显示中性空状态，不恢复来源入口或证据缺口解释。
- Deck intro 只表达连续阅读方式和页数，不用第一页判断拼装整稿结论，也不把示例客户数据当正式合同。
- 当前路由继续渲染旧组件，因此本切片不会改变浏览器当前活动页；这是有意的版本隔离，不代表活动路由接入完成。

### Task 1: Freeze the accepted ViewModel DOM and action boundary

**Files:**

- Create: `产品代码/widget/src/content-review/ContentReviewViewModelSurface.test.tsx`
- Create: `产品代码/widget/src/content-review/ContentReviewViewModelResponsive.test.tsx`

- [ ] **Step 1: Write a complete ViewModel fixture**

Create a two-page `ContentReviewPageViewModel` fixture containing paragraph and bullet blocks, one material visual, four PageDecision choices, a non-approved local draft, progress, section navigation and stable project/session identity. Use a no-op `HostBridge` and explicit action spies.

- [ ] **Step 2: Write the failing accepted-DOM test**

Render `ContentReviewViewModelSurface` and assert:

```text
内容全稿审核
这一页的目标
希望客户形成的判断
页面实际文字
文字与图片材料一起审核
```

Both pages must appear in final order. Assert the actual title, paragraph, bullet and customer judgment are visible. Assert the DOM does not contain:

```text
完整可见文字
分析、假设与建议
完整演讲备注
证据与身份
查看来源证据
问题—方案映射
跨页关系
阅读质量
用途
处理方式
证据身份
```

- [ ] **Step 3: Write failing controlled-action tests**

Assert all four radio choices are present without hover, clicking `需要修改` calls `onDecisionChange("S01", "modify")`, changing the inline textarea calls `onCommentChange`, saving calls `onSavePageDecision`, and the full-deck submit button is disabled until progress is complete and unsaved is zero. The component must never call `bridge.callTool` for PageDecision or batch writes.

- [ ] **Step 4: Write failing lazy-material test**

Install a controlled `IntersectionObserver`, verify no project asset read occurs before intersection, trigger intersection for the first page and verify `read_ai_ppt_project_asset` receives only `projectRoot` and the ViewModel `assetRef`. Verify the resulting image uses the ViewModel `altText` and no material metadata is rendered.

- [ ] **Step 5: Write failing responsive source tests**

Read `content-review-view-model.css` and assert:

- the page uses `width: 100%` without a card-shell maximum width;
- the main page body uses a two-column text/visual grid on wide screens;
- the layout becomes one column at `860px` or below;
- the two purpose fields become one column below `380px`;
- `.page-decision-option` stays at least `42px` high and the four choices become `2×2` below `380px`.

- [ ] **Step 6: Run the two focused files and verify RED**

Run from `产品代码/`:

```bash
npm run test:widget -- widget/src/content-review/ContentReviewViewModelSurface.test.tsx widget/src/content-review/ContentReviewViewModelResponsive.test.tsx
```

Expected: FAIL because the component and CSS do not exist.

### Task 2: Implement the pure ViewModel reading surface

**Files:**

- Create: `产品代码/widget/src/content-review/ContentReviewViewModelSurface.tsx`
- Create: `产品代码/widget/src/content-review/ContentReviewMaterialVisuals.tsx`
- Create: `产品代码/widget/src/styles/content-review-view-model.css`
- Modify: `产品代码/widget/src/content-review/content-review-page-view-model.ts`
- Test: `产品代码/widget/src/content-review/ContentReviewViewModelSurface.test.tsx`
- Test: `产品代码/widget/src/content-review/ContentReviewViewModelResponsive.test.tsx`

- [ ] **Step 1: Implement lazy material rendering**

`ContentReviewMaterialVisuals` accepts only:

```ts
interface ContentReviewMaterialVisualsProps {
  bridge: HostBridge;
  projectRoot: string;
  slideId: string;
  visuals: readonly ContentReviewMaterialVisualViewModel[];
  readsDisabled?: boolean;
}
```

Use one `IntersectionObserver` per visual slot with a `320px 0px` root margin, reuse `ProjectAssetImage` after activation, and show a manual-read button only when the environment has no observer. Do not add `source_file_name`, `page_number`, `region_label`, `purpose`, `treatment`, `evidence_identity` or a generic metadata prop.

- [ ] **Step 2: Implement ordered draft block rendering**

Create a local `DraftContentBlocks` helper. Render paragraphs as `<p>` and flush each consecutive bullet run into one `<ul>` so the ViewModel order is preserved without guessing content type.

- [ ] **Step 3: Implement the controlled surface**

Use the following public boundary:

```ts
export interface ContentReviewViewModelSurfaceProps {
  viewModel: ContentReviewPageViewModel;
  bridge: HostBridge;
  projectRoot: string;
  savingSlideId?: string | null;
  submitting?: boolean;
  pageMessage?: string;
  readsDisabled?: boolean;
  onDecisionChange: (slideId: string, decision: ContentDecisionChoice) => void;
  onCommentChange: (slideId: string, comment: string) => void;
  onSavePageDecision: (slideId: string) => Promise<boolean>;
  onSubmitReviewBatch: () => void | Promise<void>;
}
```

Render compact sticky project/progress/chapter chrome, a short reading intro, positional chapters, every slide in final order, the two purpose fields, actual draft title/paragraphs/bullets, material visuals, reading question and the existing `PageDecisionControl`. Disable page or batch writes according to `availableActions`, `batchState`, current saving/submitting state and progress.

- [ ] **Step 4: Implement isolated approved-layout CSS**

Prefix page structure with `.content-review-vm-*`; reuse existing `.page-decision-*` control class names only. Match the accepted structural roles: maximum-width document, compact sticky header, small deck intro, continuous chapters, two-column page reading body, visible default decision controls, and narrow single-column/2×2 fallbacks. Do not create a product navigation, sidebar, dashboard, evidence drawer or large status hero.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run from `产品代码/`:

```bash
npm run test:widget -- widget/src/content-review/ContentReviewViewModelSurface.test.tsx widget/src/content-review/ContentReviewViewModelResponsive.test.tsx
```

Expected: both files pass with zero failures and no warnings.

- [ ] **Step 6: Run TypeScript**

Run from `产品代码/`:

```bash
npm run typecheck
```

Expected: exit 0 with no diagnostics.

### Task 3: Verify isolation and establish the second rollback point

**Files:**

- Verify the five new component/test/style files and this plan.

- [ ] **Step 1: Run complete Widget regression**

```bash
npm run test:widget
```

Expected: all existing and new Widget tests pass with zero failures.

- [ ] **Step 2: Prove the active route is untouched**

Run from the worktree root:

```bash
git diff --exit-code HEAD -- 产品代码/widget/src/ReviewSurfaceRouter.tsx 产品代码/widget/src/content-review/ContentFullDeckReviewPage.tsx 产品代码/widget/src/content-review/ContentMaterialView.tsx 产品代码/widget/src/review-surface-validation.ts 产品代码/widget/src/types/content-review.ts
```

Expected: exit 0 and no output.

- [ ] **Step 3: Verify diff hygiene and exact scope**

```bash
git diff --check
git status --short --branch
```

Explicitly stage only:

```text
产品代码/docs/superpowers/plans/2026-08-20-content-review-view-model-surface-implementation.md
产品代码/widget/src/content-review/ContentReviewViewModelSurface.tsx
产品代码/widget/src/content-review/ContentReviewMaterialVisuals.tsx
产品代码/widget/src/content-review/ContentReviewViewModelSurface.test.tsx
产品代码/widget/src/content-review/ContentReviewViewModelResponsive.test.tsx
产品代码/widget/src/content-review/content-review-page-view-model.ts
产品代码/widget/src/styles/content-review-view-model.css
```

Then run `git diff --cached --check` and `git diff --cached --name-status`. The unrelated ` D AGENTS.md` must remain unstaged.

- [ ] **Step 4: Commit the isolated frontend surface**

```bash
git commit -m "feat: add accepted content review view model surface"
```

Expected: one commit containing exactly the plan, five new implementation/test/style files and the one-line ViewModel draft-state type correction. This proves the accepted UI can be rendered from the frontend ViewModel; it does not prove activity-route, Runtime/MCP, real host, AI receipt or Gate acceptance.
