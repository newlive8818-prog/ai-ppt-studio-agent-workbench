# Content Review Projection Narrowing Implementation Plan

> **For agentic workers:** Implement this plan with test-driven development and run the full verification gate before claiming completion.

**Goal:** 以用户已验收并已接入活动路由的 `ContentReviewPageViewModel` 真实消费字段为唯一需求源，收窄内容审核 Runtime/MCP 正式外部投影，同时保留内部 `ReadingDeckBlueprint` 的生产、硬门、审计和视觉生产字段。

**Architecture:** Python `ContentReviewProjectionService` 不再复制整张内部 slide，而是显式构造关闭形状的审核 slide，只输出稳定身份、页面任务/问题/中立标题、权威 `customerJudgment`、无 identity 的实际文字块和无来源元数据的材料画面引用。Review Bridge/MCP 继续原样传递这一窄投影，不建立第二套补字段逻辑。Widget 的正式 `ContentReviewProjection` 类型与关闭式 validator 使用同一窄形状；已从活动路由下线的旧完整字段页改用显式 `LegacyContentReviewProjection` 类型，仅保留迁移期源码和回归测试，不再定义正式活动合同。

**Tech Stack:** Python 3、ProjectKernel、Node MCP/Review Bridge、React 19、TypeScript 5.7、Vitest 3、Node test runner。

---

## Scope and ownership

**Modify:**

- `产品代码/src/ai_ppt_studio/application/content_review/projection_service.py`
- 内容审核投影、Review Bridge/MCP、UI seed 与预览相关 Python/Node 测试
- `产品代码/widget/src/types/content-review.ts`
- `产品代码/widget/src/review-surface-validation.ts`
- 正式 ViewModel/Router/Browser/Controller fixtures
- 旧 `ContentFullDeckReviewPage` 与材料组件的显式 legacy 类型引用及其测试
- `产品代码/scripts/run-v22-ui-acceptance.mjs`
- 四份唯一研发基线和前端优先设计规格中的实现状态
- 本计划文件

**Do not modify:**

- 已验收内容审核 ViewModel 表面的布局、文案、CSS 或交互
- `产品代码/widget/src/ReviewSurfaceRouter.tsx`
- 视觉审核生产代码、视觉投影或 Slice F2
- `ReadingDeckBlueprint` 领域合同及其内部治理字段
- PageDecision、ContentReviewBatch、revision plan 或 G0 业务语义
- `产品代码/prototypes/**`
- PPT 运行数据目录
- worktree 中用户原有的 `D AGENTS.md`

## Frozen external projection

`ContentReviewProjection.slides[]` 只允许：

```text
slide_id
order
section_id
page_task
reading_question
neutral_title
customerJudgment
visible_copy_blocks[]
  block_id
  text
material_views[]
  material_view_id
  asset_ref
```

Deck/会话级继续保留 `project_id`、`review_type`、`review_session_id`、`review_session`、`source_version`、`revision`、`authoritative_revision`、`reading_blueprint_ref`、`material_mode`、`section_flow`、`slides`、`decisions`、`progress`、`batch`、`revision_plan` 和 `content_acceptance_ref`，以支持写入、恢复、并发和审计绑定。

正式外部投影不得包含 `identity`、`identity_labels`、`evidence_bindings`、`analysis_or_proposal_blocks`、`solution_mapping_refs`、`previous_relation`、`next_relation`、`speaker_notes`、`reading_quality`，也不得包含材料 `source_ref`、文件名、页码/区域、用途、处理方式或证据身份元数据。

## Task 1: Freeze the narrow Python projection with RED tests

- [x] 将 Python 投影测试改为断言 slide、文字块和材料画面的精确关闭字段集合。
- [x] 断言内部 `ReadingDeckBlueprint` 仍包含治理字段，但投影递归不包含所有禁止字段。
- [x] 更新 UI seed 测试，只验证正式投影允许的材料身份和 asset ref，不从外部投影读取来源元数据。
- [x] 运行聚焦 Python 测试，确认当前 `copy.deepcopy(source_slide)` 因泄露后台字段而 RED。

## Task 2: Implement the minimum Runtime projection

- [x] 在 `ContentReviewProjectionService` 中显式构造每页和嵌套对象，不复制整张内部 slide。
- [x] `customer_decision_item.text -> customerJudgment`；不输出内部 identity/evidence refs。
- [x] `visible_copy_blocks` 只输出 `block_id/text`；`material_views` 只输出 `material_view_id/asset_ref`。
- [x] 保持内部蓝图、PageDecision、Batch、revision plan 和 G0 代码不变。
- [x] 运行聚焦 Python 测试转 GREEN。

## Task 3: Freeze and implement the formal Widget contract

- [x] 先把 Router/validator/ViewModel 测试 fixtures 改为窄形状，并增加“任一禁止后台字段都导致关闭式校验失败”的测试。
- [x] 将正式 `ContentReviewSlide`、`ContentMaterialView` 类型收窄到精确外部字段。
- [x] 将 `validateContentSlide` 改为关闭式窄字段校验，并验证文字块、材料画面嵌套形状。
- [x] 为已下线旧页面增加显式 `LegacyContentReview*` 类型；旧组件和旧测试只能引用 legacy 类型，不能回流到活动 Router、validator 或 ViewModel。
- [x] 更新 Browser client、Controller、长稿和正式 UI 验收 fixture，删除后台字段。
- [x] 运行聚焦 Widget 测试和 `npm run typecheck` 转 GREEN；页面 DOM 和交互不得变化。

## Task 4: Prove Review Bridge/MCP narrow pass-through

- [x] 更新 Node 内容投影 fixtures 为窄合同。
- [x] 断言 Review Bridge/MCP 返回的 slide 和嵌套对象仍是同一精确窄形状，不补字段、不重命名、不从其他字段推断。
- [x] 保持材料 asset allowlist 只读取 `material_views[].asset_ref`。
- [x] 不新增工具，不修改视觉 Review Bridge 行为。

## Task 5: Synchronize authoritative implementation status

- [x] 更新四份唯一研发基线：活动内容审核路由已在提交 `78866ec` 本地接入；内容投影收窄在本切片完成；真实客户 ReviewSession、宿主打开/通知、AI 回执、G0 和视觉 Slice F2 仍未由此证明。
- [x] 更新前端优先设计规格的阶段状态，不改变已验收 UI 合同。
- [x] 检查四份基线相对链接和被引用原型文件存在，且没有把待验证能力写成已确认。

## Task 6: Full verification and independent rollback point

- [x] 运行 `npm run typecheck`、`npm run test:widget`、`npm run test:python`、`npm run test:node` 和 `npm run build`。
- [x] 运行 `git diff --check`，核对视觉审核、原型和 PPT 运行数据零差异。
- [ ] 只显式暂存本切片文件；既有 `D AGENTS.md` 保持未暂存。
- [ ] 建立独立提交：`feat: narrow content review projection`。
- [ ] 提交后确认工作树只保留用户原有的 `D AGENTS.md`。

## Task 7: Reopen the accepted active content review page

- [ ] 使用当前提交正式构建和 `ReviewSurfaceRouter` 活动入口生成本地预览，不直接打开 08 原型或旧页面。
- [ ] 用内置 Browser 核对四个确认标题、实际文字/材料画面、四类 PageDecision、页内意见交互、无旧后台模块、无控制台错误和无横向溢出。
- [ ] 保持页面打开供用户复核，并明确它只证明本地活动路由；不冒充真实客户 ReviewSession、宿主/AI 回执或 G0。

## Completion evidence

- Python Runtime、MCP/Review Bridge、TypeScript 类型和关闭式 validator 的同一窄合同；
- 内部 `ReadingDeckBlueprint` 治理字段未删除的回归证据；
- 已验收前端 DOM/交互未改变的自动化和 Browser 证据；
- 全量测试、正式构建、独立提交哈希与 `git revert <hash>` 回退点；
- 真实宿主、AI 回执、Gate 与视觉投影收窄继续保持独立待办。
