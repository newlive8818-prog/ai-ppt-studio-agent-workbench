# Content Review ViewModel Controller Implementation Plan

> **For agentic workers:** Implement this plan with test-driven development and run the full verification gate before claiming completion.

**Goal:** 建立 `ContentReviewViewModelController`，把用户已验收的内容审核 ViewModel 表面接到权威 PageDecision、本地草稿、revision、批次提交和长稿滚动恢复，同时保持活动路由与 Runtime/MCP 不变。

**Architecture:** `ContentReviewSurfaceData` 只提供写入身份、权威已保存结果、revision 与草稿 lineage；`ContentReviewPageViewModel` 只提供用户可见内容。Controller 在渲染前严格校验两者属于同一个项目、会话、来源版本、蓝图、revision 与逐页顺序，失败时关闭写入且不拼接两套状态。校验通过后，按审核身份 key 挂载独立会话控制器，复用 `useReviewDraft`，并只向 `ContentReviewViewModelSurface` 传递新的受控 ViewModel。

**Tech Stack:** React 19、TypeScript 5.7、Vitest 3、Testing Library、现有 `useReviewDraft`、`PageDecisionControl` 与 `HostBridge`。

---

## Scope and file ownership

**Create:**

- `产品代码/widget/src/content-review/ContentReviewViewModelController.tsx`
- `产品代码/widget/src/content-review/ContentReviewViewModelController.test.tsx`
- 本计划文件

**Do not modify:**

- `产品代码/widget/src/ReviewSurfaceRouter.tsx`
- `产品代码/widget/src/content-review/ContentFullDeckReviewPage.tsx`
- `产品代码/widget/src/content-review/ContentMaterialView.tsx`
- `产品代码/widget/src/review-surface-validation.ts`
- `产品代码/widget/src/types/content-review.ts`
- `产品代码/src/ai_ppt_studio/**`
- `产品代码/mcp/**`

## Resolved decisions

- 已验收 08 前端、ViewModel adapter 和纯表面是本切片的固定输入，不重新设计页面。
- Controller 的输入固定为 `initialData`、`initialViewModel`、`bridge`；后端字段不能反向增加前端内容。
- 初始身份必须逐项一致：project、review session、source version、reading blueprint、projection revision、authoritative revision、页面总数、最终页序、slide id/order/section/title、章节顺序和 batch state。
- 初始 PageDecision 与 batch 必须通过关闭形状、引用、时间、顺序、状态和 lineage 校验；无效时显示恢复错误，不渲染候选表面，不发写入。
- 当前运行 revision 从 `snapshotRevision` 开始；同身份更高 snapshot 到达时只更新权威状态并保留本地 dirty 草稿，所有旧异步结果不得覆盖新 revision。
- 同一审核身份的本地草稿优先于权威已保存值，但必须显示 `dirty: true`，不能计入 completed。
- 单页保存成功后只清除该页草稿并使用 Runtime 返回的完整已保存 PageDecision；失败、冲突或畸形返回保留输入。
- 批次只有在所有页面均有干净的已保存判断时可提交；成功后冻结页面写入，失败时保留全部输入。
- 长稿滚动只使用新表面的 `.content-review-vm-header`、`#content-vm-${slideId}` 和 `[data-content-review-vm-slide]`。
- 本切片不切换活动路由，因此不声称浏览器活动内容审核页已接入 Controller。

### Task 1: Freeze Controller behavior with failing tests

- [ ] 写完整 `ContentReviewSurfaceData`、权威 PageDecision、batch、ViewModel、草稿和 HostBridge fixtures。
- [ ] 覆盖身份不一致失败关闭、权威初始化、本地草稿恢复、精确保存命令、成功 revision/progress 更新、冲突与畸形返回保留草稿。
- [ ] 覆盖全稿提交条件、成功冻结、失败保留、同身份 revision 增长和跨身份重挂载时的旧异步结果隔离。
- [ ] 覆盖新表面的逻辑滚动恢复/记录、60 页最终顺序，以及后台治理字段不进入渲染。
- [ ] 运行聚焦测试，确认因 Controller 模块不存在而 RED。

### Task 2: Implement the minimum Controller

- [ ] 实现关闭形状的 PageDecision、batch、snapshot 和双输入身份校验。
- [ ] 用审核身份 key 隔离会话级组件；初始化权威状态并合并同身份本地草稿。
- [ ] 实现 decision/comment 受控更新、草稿持久化、单页保存、revision 增长和严格返回校验。
- [ ] 实现全稿完成条件、批次提交、成功冻结和失败保留。
- [ ] 实现 mount/identity/revision generation 隔离与新表面逻辑滚动恢复/记录。
- [ ] 聚焦测试转 GREEN，并运行 TypeScript。

### Task 3: Verify isolation and establish rollback point

- [ ] 运行完整 `npm run test:widget`。
- [ ] 用 `git diff --exit-code` 证明 Router、旧活动页、Runtime/MCP、投影校验器和旧投影类型零差异。
- [ ] 运行 `git diff --check`，只显式暂存本计划、Controller 和测试；无关 `D AGENTS.md` 必须保持未暂存。
- [ ] 建立独立提交：`feat: connect content review view model controller`。

本提交只证明新 ViewModel 候选表面具备前端控制器和写入合同；它不证明活动路由、正式 customerJudgment 投影、Runtime/MCP 收窄、真实 Browser/Host 或产品 Gate 已完成。
