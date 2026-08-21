# Content Review Customer Judgment Projection Implementation Plan

> **For agentic workers:** Implement this plan with test-driven development and run the full verification gate before claiming completion.

**Goal:** 让正式 `ContentReviewProjection.slides[]` 提供用户已验收前端必需的、权威且非空的 `customerJudgment`，并由 Python Runtime、Review Bridge/MCP、Widget 正式类型和严格投影校验器共同执行同一合同。

**Architecture:** `ReadingDeckBlueprint.slides[]` 新增中性的内部治理对象 `customer_decision_item`，记录本页帮助客户形成判断的文本、内容身份与证据引用；它不是旧的观点先行结论字段。Runtime 在内容审核投影边界显式把 `customer_decision_item.text` 投影为 camelCase `customerJudgment`，Bridge/MCP 原样传递，Widget 严格校验后由 ViewModel adapter 直接消费。缺失或不合法时所有边界失败关闭，不从标题、页面任务、阅读问题或临时模型文字推断。

**Tech Stack:** Python 3、现有 v2.2 内容领域合同与 ProjectKernel、Node MCP/Review Bridge、React 19、TypeScript 5.7、Vitest 3、Node test runner。

---

## Scope and file ownership

**Modify:**

- `产品代码/src/ai_ppt_studio/domains/content/contracts.py`
- `产品代码/src/ai_ppt_studio/application/content_review/projection_service.py`
- 对应 Python、MCP/Bridge 与 Widget 合同测试和 fixtures
- `产品代码/widget/src/types/content-review.ts`
- `产品代码/widget/src/review-surface-validation.ts`
- `产品代码/widget/src/content-review/content-review-page-view-model.ts`

**Do not modify:**

- `产品代码/widget/src/ReviewSurfaceRouter.tsx`
- `产品代码/widget/src/content-review/ContentFullDeckReviewPage.tsx`
- `产品代码/widget/src/content-review/ContentReviewViewModelSurface.tsx`
- `产品代码/widget/src/content-review/ContentReviewViewModelController.tsx`
- 视觉审核生产代码
- PPT 运行数据目录

## Resolved decisions

- 已验收的 08 内容审核前端和现有 ViewModel 表面是固定输入，本切片不重新设计 UI。
- 内部权威字段固定为 `customer_decision_item: { text, identity, evidence_refs }`；它描述客户判断的审核上下文，不是 `desiredCustomerJudgment`、`customer_judgment`、`coreClaim` 或必须接受的结论。
- `text` 必须是首尾规范化的非空字符串；`identity` 必须属于当前内容身份集合。
- `来源事实` 与 `用户已确认` 身份必须有证据引用；`proposal-led` 页面不得把该对象标为客户事实，也不得引用项目证据。
- 判断文本不得包含无证强迫性结论表达；沿用当前对“必须、唯一、最佳、保证”等表达的硬拒绝边界。
- 正式外部投影只新增 `customerJudgment`，不把内部 `identity`、`evidence_refs` 或新的后台字段卡带入前端。
- Widget 类型和严格校验器要求 `customerJudgment` 是 own enumerable、非空且首尾规范化的字符串；缺失、额外旧字段或以其他字段代替都拒绝。
- ViewModel adapter 删除临时的属性描述符兼容读取，直接消费正式字段，且仍不提供任何兜底。
- Bridge/MCP 不建立第二套 schema，也不伪造文本；通过合同测试证明字段由 Python 投影原样到达客户端。
- 旧项目若保存的是缺少 `customer_decision_item` 的旧蓝图，必须重新生成并发布新的内容版本；不得静默迁移或推断。
- 本切片不切换活动 `ReviewSurfaceRouter`，因此完成后不能声称浏览器当前页面已经使用新 Controller。

### Task 1: Freeze the Python authority and projection contract with failing tests

- [x] 在 ReadingDeckBlueprint fixtures 中加入合法 `customer_decision_item`。
- [x] 覆盖缺失/额外字段、空或未规范化文本、非法 identity、无证事实身份、proposal-led 事实冒充与强迫性表达。
- [x] 投影测试要求 `slides[].customerJudgment` 精确等于内部权威文本，并继续拒绝所有旧观点先行字段。
- [x] 运行聚焦 Python 测试，确认因正式合同和投影尚未实现而 RED。

### Task 2: Implement the minimum Python contract and explicit projection

- [x] 用关闭形状验证并规范化 `customer_decision_item`。
- [x] 在现有内容身份、证据和 material mode 边界下执行事实与 proposal-led 约束。
- [x] Runtime 显式构造每页投影并添加 `customerJudgment`，不输出内部治理对象。
- [x] 聚焦 Python 测试转 GREEN。

### Task 3: Freeze and implement the Widget contract

- [x] 正式 `ContentReviewSlide` 类型要求 `customerJudgment: string`。
- [x] 严格投影校验器要求字段存在、非空、首尾规范化，并继续拒绝未知字段和继承/访问器属性。
- [x] ViewModel adapter 直接读取正式字段；删除测试中的 `Object.defineProperty` 临时注入。
- [x] 更新 Router、Browser client、Controller、已验收表面与长稿测试 fixtures；不得把字段渲染成额外后台模块。
- [x] 先证明新合同测试在实现前失败，再使聚焦 Widget 测试和 TypeScript 转 GREEN。

### Task 4: Prove Review Bridge/MCP pass-through

- [x] 更新 Node/Review Bridge fixtures，在正式内容投影中加入 `customerJudgment`。
- [x] 断言 `get_content_review_projection` 返回权威字段且未伪造、重命名或丢弃。
- [x] 不新增 MCP 工具，不改变 PageDecision、批次或活动路由。

### Task 5: Verify isolation and establish rollback point

- [x] 运行 `npm run typecheck`、`npm run test:widget`、`npm run test:node`、`npm run test:python`，并运行 `npm run build`。
- [x] 用 `git diff --exit-code` 证明 Router、已验收页面/表面/Controller、视觉审核生产代码和 PPT 运行数据零差异。
- [x] 运行 `git diff --check`，只显式暂存本切片文件；既有 `D AGENTS.md` 必须保持未暂存。
- [x] 建立独立提交：`feat: formalize content review customer judgment projection`。

本提交只证明正式 Python Runtime 投影、Bridge/MCP 传递、Widget 类型与严格校验器已具备权威 `customerJudgment`，以及 adapter 不再依赖临时测试属性；它不证明活动路由、真实 ReviewSession、宿主打开/通知、AI 回执或 G0 已完成。
