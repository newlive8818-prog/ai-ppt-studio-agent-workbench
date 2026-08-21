# Review Surface 原型保真账本

对应计划：`2026-08-17-review-surface-prototype-fidelity-and-acceptance.md`
产品基线：`v2.2`
来源记录：[2026-08-17-review-surface-source-selection.md](./2026-08-17-review-surface-source-selection.md)

本账本只登记 07/08 原型的结构、层级、交互位置和响应行为。原型中的示例客户、示例文案、旧
`sidebar` 命名、精确色值和样例状态不属于当前产品数据。React 只消费经过 `review-surface-validation.ts`
校验的正式投影；Runtime 的 `sourceVersion` 和 `revision` 是唯一业务版本身份。

## 1. 内容全稿审核（08）

| 原型区域 | 当前实现/语义锚点 | 当前数据来源 | 验证证据 |
|---|---|---|---|
| `.head` / `.head-main` | `.content-review-head` | ReviewSession + ReadingDeckBlueprint | `ContentFullDeckReviewPage.test.tsx` |
| `.progress` | `.content-review-progress` | `review.progress` | `ContentFullDeckReviewPage.test.tsx` |
| `.chapter-nav` | `.content-review-chapter-nav` | `review.section_flow` | `ContentFullDeckReviewPage.test.tsx` |
| `.deck-intro` | `.content-review-deck-intro` | 当前蓝图摘要与材料模式 | `ContentFullDeckReviewPage.test.tsx` |
| `.chapter` | `[data-content-chapter]` | 正式 section/chapter projection | `ContentFullDeckReviewPage.test.tsx` |
| `.page` / `.page-body` | `[data-content-slide]` + full readable body | 当前 slides、evidence、材料和 speaker notes | `ContentFullDeckReviewPage.test.tsx`, `ContentReviewLongDeck.test.tsx` |
| `.actions` | `PageDecisionControl` | 四类 `PageDecision` | `ContentFullDeckReviewPage.test.tsx`, `ContentReviewResponsive.test.tsx` |
| `.feedback-editor` | 页内非认可意见编辑器 | 本地草稿 + Runtime 单页保存 | `ContentFullDeckReviewPage.test.tsx` |
| `.more` | 窄页/长文档的显式展开动作 | 当前 slide 的完整内容 | `ContentFullDeckReviewPage.test.tsx` |
| `.review-summary` | `.content-review-summary` | 全页完成度与批次提交状态 | `ContentFullDeckReviewPage.test.tsx` |

保留的体验约束：完整连续阅读、正文与真实材料同屏、四选一判断、非认可意见必填、42 CSS px 最小触控高度、
窄宽 2×2、所有页面完成前不可提交、提交后不自动关闭。

## 2. 视觉专业审核（07）

| 原型区域 | 当前实现/语义锚点 | 当前数据来源 | 验证证据 |
|---|---|---|---|
| `.topbar` / `.project-identity` | `.visual-review-topbar` / 项目身份 | Visual ReviewSession | `VisualProfessionalReviewPage.test.tsx` |
| `.review-view-switch` | 两视图 segmented control | `review.view` | `VisualProfessionalReviewPage.test.tsx` |
| `.anchor-workbench` | `AnchorResultsView` | 三页 anchors + render assets | `VisualProfessionalReviewPage.test.tsx`, `VisualReviewResponsive.test.tsx` |
| `.anchor-toolbar` / `.slide-stage` | 锚点工具栏与幻灯片舞台 | 当前视觉 sourceVersion | `VisualProfessionalReviewPage.test.tsx` |
| `.anchor-feedback-composer` | `RegionFeedbackEditor` | pointer drag rectangle + local draft | `VisualProfessionalReviewPage.test.tsx` |
| `.feedback-panel` / `.status-timeline` | 记录面板与状态事实 | saved artifact + host/AI receipt facts | `VisualProfessionalReviewPage.test.tsx`, `tests.test_v22_review_session` |
| `.contract-document-head` | `VisualContractView` 合同页头 | visual contract artifact | `VisualProfessionalReviewPage.test.tsx` |
| `#anchor-evidence` | `[data-contract-logical-object="anchor-slide-evidence"]` | 三页锚点身份与证据 | `tests.test_v22_visual_review_service` |
| `.visual-contract-list` | `.visual-slide-contract` ordered list | 全部逐页 Visual Contract | `tests.test_v22_visual_review_service` |
| `.contract-outline` | `.visual-contract-outline` overlay drawer | 当前文档目录 | `VisualProfessionalReviewPage.test.tsx` |
| `.contract-mark-drawer` | `.visual-overlay-drawer` | field/text ReviewMark drafts | `VisualProfessionalReviewPage.test.tsx` |

保留的体验约束：三页锚点、矩形拖拽才形成正式意见、意见紧邻图片输入、批次提交、完整合同连续阅读、
目录/标记抽屉覆盖打开、锚点批次与合同标记状态隔离、无聊天记录和五空间导航。

## 3. 投影不变量

`review-surface-validation.ts` 在渲染前拒绝以下数据：

- visual professional projection 的 `anchors.length !== 3`、重复锚点身份或 render asset 不匹配；
- content full-deck projection 的重复 slide ID、非法 section order、slide 顺序与 `slide_ids` 不一致；
- visual contract 缺少 Deck Design System、Anchor Slide Evidence 或 ordered slide contracts；
- receipt 缺少 review session、artifact、sourceVersion、revision、receipt ref 绑定，或绑定到未来/旧 revision；
- host/AI receipt 状态声称成功但没有权威 receipt artifact；
- 当前 projection 的 `authoritative_revision` 与宿主连接 envelope 不一致。

这些约束由 Node Bridge、Python Runtime 和 Widget 三层分别验证；任一层失败都保持失败关闭，不从本地状态推断成功。

## 4. 测试文件归属说明

计划初稿点名的 `tests.test_v22_visual_review_projection` 在当前 v22 实现中没有独立文件；其职责已拆分为：

- `tests/test_v22_visual_review_contracts.py`：字段、矩形、作者和时间戳合同；
- `tests/test_v22_visual_review_service.py`：投影、lineage、sourceVersion/revision、回执和 Runtime 写入；
- `tests/test_v22_review_session.py`：单一 session、重开、宿主/AI 回执状态和冲突；
- `widget/src/ReviewSurfaceRouter.test.tsx` 与页面测试：路由和结构化表面。

本轮已验证上述现有测试，不新增同义测试文件。

## 5. 当前状态

Stage 1 的结构与投影校验已通过当前测试证据；浏览器截图和真实宿主/AI 回执仍按计划后续阶段验收，不能由本账本或本地测试替代。
