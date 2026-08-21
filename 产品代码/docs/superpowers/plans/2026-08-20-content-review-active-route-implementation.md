# Content Review Active Route Implementation Plan

> **For agentic workers:** Implement this plan with test-driven development and run the full verification gate before claiming completion.

**Goal:** 将活动 `content-full-deck` 审核路由切换到用户已验收的前端 ViewModel 链，同时保持视觉审核、Runtime、MCP、Review Bridge 和旧实现文件不变。

**Architecture:** `ReviewSurfaceRouter` 继续先执行关闭式 `ReviewSurfaceData` 校验和现有审核身份 key 计算；仅在内容分支中，将当前权威 `ContentReviewProjection` 通过 `toContentReviewPageViewModel()` 转为前端专用 ViewModel，再交给 `ContentReviewViewModelController` 连接草稿、PageDecision 和批次写入。adapter 或 Controller 校验失败时显示现有受控恢复状态，不回退到旧 `ContentFullDeckReviewPage`。视觉分支仍直接渲染 `VisualProfessionalReviewPage`。

**Tech Stack:** React 19、TypeScript 5.7、Vitest 3、Testing Library、现有 Review Bridge/HostBridge。

---

## Scope and ownership

**Modify:**

- `产品代码/widget/src/ReviewSurfaceRouter.tsx`
- `产品代码/widget/src/ReviewSurfaceRouter.test.tsx`
- 本计划文件

**Do not modify:**

- `产品代码/widget/src/content-review/ContentFullDeckReviewPage.tsx`；本切片只从活动路由下线，暂不删除
- `产品代码/widget/src/content-review/ContentReviewViewModelController.tsx`
- `产品代码/widget/src/content-review/ContentReviewViewModelSurface.tsx`
- `产品代码/widget/src/content-review/content-review-page-view-model.ts`
- `产品代码/widget/src/visual-review/**`
- `产品代码/src/**`
- `产品代码/mcp/**`
- `产品代码/prototypes/**`
- 四份唯一研发基线和 PPT 运行数据

## Frozen decisions

- 活动内容审核页必须使用 `ReviewSurfaceRouter -> toContentReviewPageViewModel() -> ContentReviewViewModelController -> ContentReviewViewModelSurface`。
- 页面必须显示“这一页的目标”“希望客户形成的判断”“页面实际文字”“文字与图片材料一起审核”及对应实际内容。
- 活动 DOM 不得包含“完整可见文字”“分析、假设与建议”“完整演讲备注”“证据与身份”“查看来源证据”“问题—方案映射”“跨页关系”“阅读质量”等旧后台目录模块。
- 四类 PageDecision、非认可页内意见、单页保存、集中批次提交、revision、草稿和长稿恢复仍由现有 Controller 负责。
- 不重新设计已验收前端，不根据旧后端字段增加 UI，不修改视觉审核路由。
- 本地 fixture 和 Browser 预览只证明活动路由及本机构建；不证明真实客户 ReviewSession、宿主通知、AI 回执、G0 或产品 Gate。

### Task 1: Freeze the active route with a failing test

- [ ] 更新 Router 内容 fixture，使其包含一页完整 ViewModel 必需数据、实际文字、页面画面和 `customerJudgment`。
- [ ] 断言活动内容路由出现四个确认标题、实际内容、四类 PageDecision、单页保存和批次动作。
- [ ] 断言存在 `[data-content-review-vm-slide]`，不存在旧 `[data-content-slide]` 及所有被禁止模块。
- [ ] 保持视觉双视图、关闭式投影校验、同身份 revision 保留 root 和跨身份重挂载测试。
- [ ] 运行 `npm run test:widget -- widget/src/ReviewSurfaceRouter.test.tsx`，确认因为 Router 仍渲染旧页而 RED，而非 fixture 或类型错误。

### Task 2: Make the minimum production route change

- [ ] 将旧内容页 import 替换为 ViewModel adapter 与 Controller import。
- [ ] 内容分支保持原 `pageKey`，传入 `initialData={validated}`、`initialViewModel={toContentReviewPageViewModel(validated.review)}` 与原 `bridge`。
- [ ] 不修改视觉分支，不添加旧页 fallback。
- [ ] 运行聚焦 Router 测试和 `npm run typecheck`，确认 GREEN。

### Task 3: Verify isolation and create a rollback point

- [ ] 运行完整 `npm run test:widget`、`npm run test:python`、`npm run test:node` 和 `npm run build`。
- [ ] 运行 `git diff --check`，并证明所有禁止修改路径相对 `HEAD` 零差异。
- [ ] 只显式暂存本计划、Router 和 Router 测试；既有 `D AGENTS.md` 保持未暂存。
- [ ] 建立独立提交：`feat: activate accepted content review surface`。
- [ ] 提交后再次确认工作树只保留既有、无关的 `D AGENTS.md`。

### Task 4: Open the built active route for user verification

- [ ] 使用当前提交的正式构建和通过 `ReviewSurfaceRouter` 的本地验收入口，不直接打开 08 原型，也不复用旧内容页。
- [ ] fixture 必须携带正式 `customerJudgment`，并明确标注为本地活动路由验收数据。
- [ ] 用内置 Browser 检查 URL、DOM、控制台、截图与至少一次非提交交互；验证选择“需要修改”后页内意见输入出现。
- [ ] 保持该页面打开供用户复验，并准确说明它是本地活动路由验收预览，不冒充真实客户 ReviewSession。

## Completion evidence

- 活动内容路由代码和聚焦/全量测试证据；
- 视觉分支与禁止修改路径零差异证据；
- 独立提交哈希和可用的 `git revert <hash>` 回退点；
- 当前构建页面的 Browser URL、无错误控制台和截图/交互证据；
- 明确保留真实宿主打开、Runtime/MCP 收窄和 AI 回执的独立待验证状态。
