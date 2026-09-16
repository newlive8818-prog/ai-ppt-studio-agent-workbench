# 07/08 审核原型忠实度整改 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不恢复五空间、常驻侧边栏或聊天 Widget 的前提下，使内容全稿审核页和视觉专业审核页忠实实现 08/07 原型中已确认且仍有效的审核合同。

**Architecture:** 先修闭合领域合同与 Review Projection，使页面拿到真实材料和恰好三页可读锚点；再通过小型 React 组件和版本化 Browser 草稿存储实现连续审核、响应式布局与恢复；最后用真实项目内图片、360/760/1000/1440 四视口和参考截图差异账本替换当前只检查 DOM 存在的弱验收。现有 PageDecision、不可变批次、矩形区域反馈、合同 ReviewMark、覆盖式抽屉及真实回执边界继续复用。

**Tech Stack:** Python 3 标准库领域/应用服务、Node.js Review Bridge、React 19、TypeScript 5、Vitest/Testing Library、Node test、Playwright、CSS。

---

## 权威边界

- 视觉参考：`prototypes/07-visual-anchor-chat-collaboration-prototype.html`。
- 内容参考：`prototypes/08-content-full-deck-review-v7-inline-feedback.html`。
- 产品合同：项目根目录四份 v1.0 基线。
- 不恢复 08 中已废止的“侧边栏”“希望客户形成的判断”“代表页代替全稿”。
- 不恢复五空间、一级导航、项目仪表盘、聊天流、审核页 G0/G3 按钮或制作交付页。
- 07 的精确客户、颜色、字体、阴影不是跨项目数据合同；双视图、三页锚点、宽屏辅助区、矩形反馈、上一版对比、完整合同和覆盖式抽屉是实现合同。

## 文件职责

- `src/ai_ppt_studio/domains/content/contracts.py`：闭合 ReadingDeckBlueprint 的材料展示引用。
- `src/ai_ppt_studio/application/content_review/projection_service.py`：把当前页材料展示资源解析成只读 Projection。
- `src/ai_ppt_studio/domains/visual/contracts.py`：恰好三页锚点及当前/上一版渲染资源闭合合同。
- `src/ai_ppt_studio/application/visual_review_service.py`：验证并输出完整 VisualReviewProjection。
- `src/ai_ppt_studio/domains/review/contracts.py`：版本约束的恢复状态引用。
- `mcp/review-bridge.mjs`：只 allowlist 当前 Projection 中的内容/视觉图片，不开放任意文件。
- `widget/src/review-draft/*`：版本化、按 ReviewSession 隔离的 Browser 草稿和滚动恢复。
- `widget/src/content-review/*`：08 风格连续内容/材料同屏、PageDecision 与页内意见。
- `widget/src/visual-review/*`：07 风格双视图、宽屏辅助区、对比和完整合同。
- `scripts/seed-v16-ui-project.py`：三页锚点、真实项目内 PNG、未完成内容审核的代表性 fixture。
- `scripts/run-v22-ui-acceptance.mjs`：四视口、几何、资源、恢复和交互验收。

### Task 1: 内容材料展示闭合合同

**Files:**
- Modify: `src/ai_ppt_studio/domains/content/contracts.py`
- Modify: `src/ai_ppt_studio/application/content_review/projection_service.py`
- Modify: `widget/src/types/content-review.ts`
- Test: `tests/test_v22_content_contracts.py`
- Test: `tests/test_v22_content_review_projection.py`

- [ ] **Step 1: 写失败测试：material-backed/mixed-evidence 每页必须提供 material_views**

测试输入使用闭合结构：

```python
"material_views": [{
    "material_view_id": "S01-M01",
    "source_ref": source_ref,
    "asset_ref": "review-assets/content/S01-M01.png",
    "source_file_name": "客户现状材料.pptx",
    "page_number": 3,
    "region_label": "整页",
    "purpose": "证明当前流程断点",
    "treatment": "原页只读呈现",
    "evidence_identity": "来源事实",
}]
```

断言 `validate_reading_deck_blueprint()` 保留全部字段，缺失或额外字段失败，proposal-led 允许空数组。

- [ ] **Step 2: 运行 RED**

Run: `python3 -m unittest tests.test_v22_content_contracts -v`

Expected: FAIL，原因是 `material_views` 目前不在 ReadingDeckBlueprint slide 的闭合字段中。

- [ ] **Step 3: 最小实现材料展示合同并加入 Projection**

新增闭合字段 `material_views`，验证项目内 POSIX 相对 `asset_ref`，禁止 `..`、绝对路径、URL scheme 和空路径；Projection 只复制已验证字段，不读任意文件。

- [ ] **Step 4: 运行 GREEN**

Run: `python3 -m unittest tests.test_v22_content_contracts tests.test_v22_content_review_projection -v`

Expected: PASS。

### Task 2: Review Bridge 同时支持内容与视觉受控图片

**Files:**
- Modify: `mcp/review-bridge.mjs`
- Modify: `widget/src/lib/browser-review-client.ts`
- Test: `tests/review-bridge.test.mjs`
- Test: `widget/src/BrowserReviewClient.test.tsx`

- [ ] **Step 1: 写失败测试：Projection 只允许自身声明的 material_views 与 anchors 图片**

内容 Projection 提供 `review.slides[].material_views[].asset_ref`，视觉 Projection 提供 `review.anchors[].asset_ref/current_asset_ref/previous_asset_ref`。分别读取成功；未声明、跨项目和路径穿越资源失败。

- [ ] **Step 2: 运行 RED**

Run outside sandbox: `node --test tests/review-bridge.test.mjs`

Expected: FAIL，当前 allowlist 只收集 `review.anchors[].asset_ref`。

- [ ] **Step 3: 实现纯函数 collectProjectionAssetRefs**

函数只遍历上述闭合位置，过滤空值并返回 `Set<string>`；`/api/asset` 继续使用既有 project-root 受控 reader，不新增任意 URL 或 file:// 路由。

- [ ] **Step 4: 运行 GREEN**

Run outside sandbox: `node --test tests/review-bridge.test.mjs`

Expected: PASS。

### Task 3: 恰好三页锚点与正式渲染资源

**Files:**
- Modify: `src/ai_ppt_studio/domains/visual/contracts.py`
- Modify: `src/ai_ppt_studio/application/gate_evaluator.py`
- Modify: `src/ai_ppt_studio/application/visual_review_service.py`
- Modify: `src/ai_ppt_studio/application/visual_service.py`
- Modify: `widget/src/types/visual-review.ts`
- Test: `tests/test_v16_visual_contracts.py`
- Test: `tests/test_v16_visual_gates.py`
- Test: `tests/test_v22_visual_review_service.py`

- [ ] **Step 1: 写失败测试：两页、四页、缺当前渲染资源均拒绝**

正式 AnchorSlideSet 使用：

```python
"render_assets": [{
    "slide_id": "S01",
    "current_asset_ref": "review-assets/anchors/S01-current.png",
    "previous_asset_ref": "review-assets/anchors/S01-previous.png",
}]
```

`previous_asset_ref` 可空表示无上一有效版本，`current_asset_ref` 必填；三个 slide_id 与三条资源一一对应且顺序一致。

- [ ] **Step 2: 运行 RED**

Run: `python3 -m unittest tests.test_v16_visual_contracts tests.test_v16_visual_gates tests.test_v22_visual_review_service -v`

Expected: FAIL，当前合同和 G2 接受 2–3 页，且 render_assets 未验证。

- [ ] **Step 3: 最小实现三页与资源验证**

将 AnchorSlideSet 和 G2 改为 `len(slide_ids) == 3`；Projection 输出 `current_asset_ref`、`previous_asset_ref` 和锚点身份理由；project() 对当前视觉合同页数、顺序、Deck Design System、三页锚点和资源做闭合验证。

- [ ] **Step 4: 运行 GREEN**

Run: `python3 -m unittest tests.test_v16_visual_contracts tests.test_v16_visual_gates tests.test_v22_visual_review_service -v`

Expected: PASS。

### Task 4: 08 内容审核结构与 PageDecision

**Files:**
- Create: `widget/src/content-review/ContentMaterialView.tsx`
- Create: `widget/src/content-review/PageDecisionControl.tsx`
- Modify: `widget/src/content-review/ContentFullDeckReviewPage.tsx`
- Modify: `widget/src/styles/content-review.css`
- Test: `widget/src/content-review/ContentFullDeckReviewPage.test.tsx`
- Test: `widget/src/content-review/ContentReviewResponsive.test.tsx`

- [ ] **Step 1: 写失败组件测试**

断言每页同一 `.content-slide-reading-grid` 内同时出现完整正文和真实 `<img>`；四个判断是可识别的 radio-button labels；保存后显示完整意见和“编辑意见”；存在“定位下一页未判断”。

- [ ] **Step 2: 运行 RED**

Run: `npx vitest run widget/src/content-review/ContentFullDeckReviewPage.test.tsx widget/src/content-review/ContentReviewResponsive.test.tsx`

Expected: FAIL，当前没有材料画面、大按钮、定位动作和保存后折叠状态。

- [ ] **Step 3: 实现 08 有效结构**

宽屏每页为 `minmax(340px,.9fr) minmax(500px,1.1fr)`；窄屏单栏。PageDecision 默认 42px、有边框/背景/圆形图形；选中态使用边框、背景、字重、图形四重信号；360px 为 2×2 且标签不换行。非 approved 页内展开意见；保存后显示完整意见与编辑按钮。

- [ ] **Step 4: 运行 GREEN 与类型检查**

Run: `npx vitest run widget/src/content-review && npm run typecheck`

Expected: PASS。

### Task 5: 07 视觉锚点宽屏辅助区与上一版对比

**Files:**
- Create: `widget/src/visual-review/AnchorComparisonDialog.tsx`
- Modify: `widget/src/visual-review/AnchorResultsView.tsx`
- Modify: `widget/src/visual-review/RegionFeedbackEditor.tsx`
- Modify: `widget/src/styles/visual-review.css`
- Test: `widget/src/visual-review/VisualProfessionalReviewPage.test.tsx`
- Test: `widget/src/visual-review/VisualReviewResponsive.test.tsx`

- [ ] **Step 1: 写失败测试**

断言三页锚点、当前真实图片、上一版对比入口、宽屏 `.anchor-review-layout` 两列、输入紧邻幻灯片、右侧只含反馈/批次/回执；360px 下辅助区位于主内容之后。

- [ ] **Step 2: 运行 RED**

Run: `npx vitest run widget/src/visual-review`

Expected: FAIL，当前没有对比入口和宽屏两列。

- [ ] **Step 3: 实现 07 有效结构并复用既有反馈机制**

不修改 RegionFeedback/Batch payload；只调整组合结构和资源字段。对比弹窗并排显示 previous/current，同一缩放与宽高；无 previous 时按钮禁用并显示“当前为首个可审核版本”。

- [ ] **Step 4: 运行 GREEN**

Run: `npx vitest run widget/src/visual-review && npm run typecheck`

Expected: PASS。

### Task 6: 完整视觉合同首屏收敛

**Files:**
- Modify: `widget/src/visual-review/VisualContractView.tsx`
- Modify: `widget/src/styles/visual-review.css`
- Test: `widget/src/visual-review/VisualProfessionalReviewPage.test.tsx`

- [ ] **Step 1: 写失败测试**

首屏只允许一次“完整视觉合同”，显示项目、视觉版本、revision、G1/G2/G3、合同页数和未保存标记数；完整 artifact URI 不作为可见主标题。Deck Design System、锚点身份/理由/证据、全部逐页合同仍连续存在。

- [ ] **Step 2: 运行 RED**

Run: `npx vitest run widget/src/visual-review/VisualProfessionalReviewPage.test.tsx`

Expected: FAIL，当前重复标题并直接显示超长 artifact URI。

- [ ] **Step 3: 最小调整标题层级和技术信息**

保留覆盖式目录/标记抽屉与顶部统一保存；将技术引用放入折叠的“技术信息”，不新增常驻侧栏。

- [ ] **Step 4: 运行 GREEN**

Run: `npx vitest run widget/src/visual-review/VisualProfessionalReviewPage.test.tsx`

Expected: PASS。

### Task 7: ReviewSession 恢复状态

**Files:**
- Create: `widget/src/review-draft/reviewDraftStore.ts`
- Create: `widget/src/review-draft/useReviewDraft.ts`
- Modify: `widget/src/content-review/ContentFullDeckReviewPage.tsx`
- Modify: `widget/src/visual-review/VisualProfessionalReviewPage.tsx`
- Modify: `widget/src/visual-review/AnchorResultsView.tsx`
- Modify: `widget/src/visual-review/VisualContractView.tsx`
- Test: `widget/src/review-draft/reviewDraftStore.test.ts`
- Test: `widget/src/content-review/ContentFullDeckReviewPage.test.tsx`
- Test: `widget/src/visual-review/VisualProfessionalReviewPage.test.tsx`

- [ ] **Step 1: 写失败测试：同一 session 恢复、不同 revision 隔离**

存储键固定为 `ai-ppt-review-draft:v1:<projectId>:<reviewType>:<reviewSessionId>:<sourceVersion>:<sourceRevision>`；只保存 UI 草稿、当前对象和滚动位置，不伪造 persistence/host/AI/Gate 事实。

- [ ] **Step 2: 运行 RED**

Run: `npx vitest run widget/src/review-draft widget/src/content-review widget/src/visual-review`

Expected: FAIL，当前没有版本化草稿 store。

- [ ] **Step 3: 实现版本化 sessionStorage 存储**

使用版本化 schema、边界验证和 try/catch；读取一次后缓存，输入更新节流；提交成功清除对应已提交草稿，但保留视图和滚动位置；新 sourceVersion/revision 使用新键，不自动迁移旧反馈。

- [ ] **Step 4: 运行 GREEN**

Run: `npx vitest run widget/src && npm run typecheck`

Expected: PASS。

### Task 8: 真实 fixture 与原型忠实度验收

**Files:**
- Modify: `scripts/seed-v16-ui-project.py`
- Modify: `scripts/run-v22-ui-acceptance.mjs`
- Modify: `scripts/create-review-preview.mjs`
- Test: `tests/test_v16_ui_seed.py`
- Test: `tests/review-bridge.test.mjs`

- [ ] **Step 1: 写失败测试与验收断言**

Fixture 必须有三页锚点 PNG、每个内容页的材料 PNG、至少一页未判断、一页 modify 草稿态、无已提交批次。UI acceptance 增加 360px，并断言图片真实加载、PageDecision 42px、360px 2×2、宽屏锚点两列、对比按钮、完整合同全部页、无 placeholder。

- [ ] **Step 2: 运行 RED**

Run: `python3 -m unittest tests.test_v16_ui_seed -v && npm run accept:v22-ui`

Expected: FAIL，当前 fixture 只有两页锚点且资源为空，验收不检查原型几何。

- [ ] **Step 3: 生成项目内确定性 SVG/PNG fixture 并重写验收**

资源只写临时验收项目，不写源码仓库；截图输出继续标记为 local-development-preview，不能声明真实宿主、AI、Presentations 或 PowerPoint 通过。

- [ ] **Step 4: 全量验证**

Run:

```bash
npm run typecheck
npm run build
npm run test:widget
npm run test:node
npm run test:python
npm run accept:v22-ui
```

Expected: 所有命令 exit 0；回环 Node 测试和 UI acceptance 在需要时按权限边界于沙箱外执行。

### Task 9: Browser 与参考截图终验

**Files:**
- No production-file changes unless a mismatch is reproduced by a failing test.

- [ ] **Step 1: 使用内置 Browser 打开内容和视觉审核页**

检查页面 URL、标题、DOM、console、首屏、核心交互。

- [ ] **Step 2: 四视口参考差异账本**

对比 07/08 与当前渲染的：结构、文案、控件、字体层级、颜色、间距、资源、响应式、滚动和交互。任何可修复偏差先写失败测试再修。

- [ ] **Step 3: 最终证据边界**

仅在真实凭据存在时报告宿主通知或 AI 已接收；本地截图只报告开发验收，不把它升级为 Browser/宿主/PowerPoint/用户正式验收。

## 计划自检

- 覆盖内容材料、四类 PageDecision、三页锚点、对比、完整视觉合同、两类反馈隔离、草稿/滚动恢复、响应式和真实验收。
- 不恢复任何已废止页面、五空间、常驻侧边栏、desired judgment 或 Gate 按钮。
- 所有生产行为先有可观察失败测试；不使用仅 mock 成功的 `asset://` 测试假象。
- 每个任务都给出明确文件、失败条件、最小实现和验证命令，没有悬空步骤。
- 当前 worktree 已承载大量用户所有的未提交研发改动，因此计划不自动创建混合提交；完成全量验证后再由分支收尾流程决定是否做路径限定提交。
