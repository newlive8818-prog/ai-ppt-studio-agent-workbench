# 内容审核页前端优先合同重置设计

## 1. 文档状态

- 日期：2026-08-18
- 决策状态：`用户已确认方案 B`
- 验收修正：`用户在 08 原型复核中确认必须恢复四个前端标题及对应内容；本修正不恢复其他后台模块`
- 内容审核前端 UI 验收：`accepted；绑定提交 2607bed 与 08 HTML 哈希 18e680304a7218e86e0e553067123aa24f42b7d12da3e64fe3d94ca9989b7692`
- 活动生产路由接入：`pending；属于工程迁移，不形成第二个 UI 验收门`
- 验收记录：[内容审核前端 UI 验收口径澄清记录](../../validation/2026-08-19-content-review-frontend-ui-acceptance-clarification.md)
- 当前阶段：`只冻结前端合同；尚未授权本文件直接修改 Runtime、MCP 或持久化合同`
- 适用表面：内容全稿审核页
- 参考原型：`产品代码/prototypes/08-content-full-deck-review-v7-inline-feedback.html`
- 实现分支：`codex/review-surface-v22`
- 隔离 worktree：`/private/tmp/ai-ppt-v22-TmBomR`

本文取代 [内容全稿审核页空间保真还原设计](./2026-08-18-content-review-spatial-fidelity-design.md) 中“保留所有后台拆解字段为前端可见模块”的要求。后者关于紧凑页头、连续阅读、首屏空间、图文同屏、PageDecision 相对位置和验收证据分层的要求继续有效。

## 2. 用户最新决定

2026-08-18，用户明确决定：

1. 前端展示内容、功能和交互以用户确认的 UI 设计为需求源；
2. 后台已有字段不能自动成为前端模块；
3. 原型中没有、用户没有确认的“可能有用”功能不得自行增加；
4. 先冻结前端合同，再按照前端真实需要拆解后端字段；
5. 删除后台字段目录式展示，但保留用户真正要审核的实际成稿正文；
6. 采用方案 B：建立前端专用 ViewModel，旧投影先由 adapter 过渡，Runtime/MCP 收窄放在 UI 验收后的独立阶段。

同日原型复核中，用户进一步确认以下四项是原型本身的前端功能，不属于应删除的后台字段目录：

- “这一页的目标”及其内容；
- “希望客户形成的判断”及其内容；
- 实际成稿栏标题“页面实际文字”；
- 材料/画面栏标题“文字与图片材料一起审核”。

用户对 2026-08-18 首轮内容审核页 React 候选实现的结论是“不通过”。在按最新决定修正 08 HTML 后，用户于同日明确确认该页面“验收通过”，并于 2026-08-19 进一步澄清：该文件就是已经验收的内容审核页前端，不是仅供参考的原型。旧 React 候选未通过与前端已验收并不冲突；前者是活动路由未完成忠实接入的工程缺口，不能据此要求用户重新设计或验收同一前端。

## 3. 问题根因

首轮实现直接把 `ReadingDeckBlueprint` / `ContentReviewProjection` 的内部字段逐项映射成可见区块，形成了：

- “完整可见文字”；
- “分析、假设与建议”；
- “完整演讲备注”；
- “证据与身份”及来源证据按钮；
- “问题—方案映射”；
- “跨页关系”；
- “阅读质量”。

这些字段可以服务内容生产、硬门、审计和后端治理，但不因此获得前端展示权。根因不是折叠不足、间距不佳或视觉层级不够，而是前端合同被后台对象反向定义。

## 4. 已确认的前端可见合同

### 4.1 页面级内容

内容全稿审核页只呈现完成审核任务所必需的内容：

- 紧凑项目头、sourceVersion、revision 和审核进度；
- 单行章节定位；
- 紧凑 deck intro；
- 章节与页面按最终页序连续阅读；
- 页码、slideId 和中立标题；
- 阅读问题；
- “这一页的目标”及其实际内容；
- “希望客户形成的判断”及其实际内容；
- 实际成稿正文，直接以标题、段落和要点呈现；
- 真实材料本体或页面画面，与实际成稿正文同屏；
- 四类 `PageDecision`；
- 非 `approved` 的页内意见输入；
- 单页保存状态；
- 全稿完成后的集中批次提交。

“实际成稿正文”必须完整可读，不允许用摘要、截断或省略号替代；实际成稿栏显示用户确认的“页面实际文字”，材料/画面栏显示“文字与图片材料一起审核”。“页面实际文字”不等于“完整可见文字”后台字段卡；前者必须保留，后者继续禁止。实际成稿不显示内部 identity 标签。

### 4.2 明确禁止的前端模块

以下信息不得在内容全稿审核页中显示：

- “完整可见文字”字段标题或字段卡；
- “分析、假设与建议”；
- “完整演讲备注”；
- “证据与身份”；
- “查看来源证据”按钮或独立证据 Browser 入口；
- “问题—方案映射”；
- “跨页关系”；
- “阅读质量”；
- 来源文件、页码/区域、用途、处理方式和证据身份的目录式元数据；
- 面向研发或后台治理的状态解释、字段解释和工程摘要。

禁止项不能被转移到折叠区、抽屉、tooltip、hover、二级弹层或“高级信息”中变相保留。

### 4.3 不改变的审核业务语义

- `approved | modify | evidence | merge-or-delete` 四选一互斥；
- 非 `approved` 意见必填，最多 1200 Unicode code points；
- 单页保存不调用模型、不改稿、不确认 G0；
- 全部页面完成、无未保存输入且版本一致时才能提交；
- `ContentReviewBatch` 提交后不可原地修改；
- 新版必须全篇复审；
- 用户 UI 验收与 G0、宿主通知、AI 接收回执彼此独立。

## 5. 前端 ViewModel

### 5.1 目的

新增前端专用 `ContentReviewPageViewModel`，使 React 组件只依赖用户可见需求，不依赖内部内容治理对象的完整形状。

建议最小结构：

```text
ContentReviewPageViewModel
|- projectLabel
|- sourceVersion
|- revision
|- progress
|- sections[]
|- slides[]
|  |- slideId
|  |- order
|  |- sectionId
|  |- neutralTitle
|  |- pageGoal
|  |- customerJudgment
|  |- readingQuestion
|  |- draftContent
|  |  |- title
|  |  `- blocks[]: paragraph | bullet
|  |- materialVisuals[]
|  |  |- visualId
|  |  |- assetRef
|  |  `- altText
|  |- savedDecision
|  `- localDraftState
|- batchState
`- availableActions
```

这是前端投影视图，不是新的权威业务对象。它不保存第二套事实，不计算 Gate，不替代 Runtime。

### 5.2 过渡 adapter

当前阶段保留现有 `ContentReviewProjection` 输入和校验边界，在 Widget 内新增纯函数 adapter：

```text
ContentReviewProjection
        |
        v
toContentReviewPageViewModel()
        |
        v
ContentReviewPageViewModel
        |
        v
ContentFullDeckReviewPage
```

adapter 的规则：

- `page_task` 转为 `pageGoal`，显示在“这一页的目标”下；
- `customerJudgment` 是用户确认的必显语义；现有投影若缺少对应权威事实，adapter 必须报告投影字段缺口，不得用 neutralTitle、readingQuestion 或模型临时生成内容冒充；
- `visible_copy_blocks` 只作为过渡数据源转换为 `draftContent.blocks`；其 `identity` 不进入 ViewModel；
- `material_views` 只提取渲染页面画面所需的 `assetRef` 与 `altText`；来源、区域、用途、处理方式和证据身份不进入 ViewModel；
- `analysis_or_proposal_blocks`、`identity_labels`、`evidence_bindings`、`solution_mapping_refs`、`previous_relation`、`next_relation`、`speaker_notes` 和 `reading_quality` 明确忽略；
- adapter 不修改输入，不推断 Gate，不写入 Runtime；
- PageDecision、批次、sourceVersion 和 revision 继续使用现有权威标识。

“这一页的目标”“希望客户形成的判断”“页面实际文字”“文字与图片材料一起审核”是固定前端标题，不从后台字段名自动生成。

## 6. 后端字段反向拆解

后端收窄必须在前端 UI 通过用户验收后作为独立阶段进行：

1. 以前端 `ContentReviewPageViewModel` 的真实消费字段为依据；
2. 区分内部 `ReadingDeckBlueprint` 与外部内容审核页投影；
3. 内部字段可以继续服务生产、硬门、审计和视觉生产，但不能因为存在就暴露到前端；
4. Runtime/MCP 的内容审核投影最终只输出前端需要的数据与写入所需的稳定身份；
5. 删除或废弃字段必须有兼容策略、契约测试和独立可回退提交；
6. 不在本轮 UI 修复提交中混入 Runtime、MCP 或持久化迁移。

## 7. 原型同步规则

08 HTML 原型同步为当前前端合同：

- 保留连续阅读、实际成稿正文、页面画面、四类 PageDecision 和页内意见；
- 保留“这一页的目标”“希望客户形成的判断”两项内容与标题；
- 保留“页面实际文字”“文字与图片材料一起审核”两个栏标题；
- 删除完整逐字稿折叠区、阅读质量、相邻页面关系和材料元数据目录；
- 实际成稿正文改为无后台字段标签的主阅读内容；
- 原型内未被渲染的示例数据不构成后端合同；
- 旧 JPG 只记录 2026-08-15 的空间参考；其中上述四项已由用户再次确认，其他已删除模块不能依据旧截图恢复；当前 HTML 和 v2.4 基线优先。

## 8. 实施边界

### 8.1 当前合同冻结阶段

允许修改：

- 四份唯一基线；
- 本设计规格；
- 08 HTML 原型；
- 旧空间保真规格的取代声明。

不允许修改：

- React 页面实现；
- Runtime、MCP、Review Bridge；
- Python 领域合同或持久化；
- 视觉专业审核页；
- PPT 运行数据。

### 8.2 下一实施阶段

已验收前端进入正式工程接入阶段，用独立实现计划约束：

- 前端 ViewModel 与 adapter；
- 当前活动内容审核组件和 CSS 对已验收前端的忠实接入；
- 前端校验边界；
- DOM、交互、响应式和浏览器验收；
- 一个可独立 `git revert` 的实现提交。

## 9. 测试与验收合同

### 9.1 必须失败后再通过的测试

- 被禁止的八类模块标题和入口不得出现在 DOM；
- 实际成稿标题、段落和要点完整存在；
- 实际成稿正文与页面画面位于同一页面审核上下文；
- 页面任务、阅读问题、四类 PageDecision 和页内意见仍存在；
- 每页同时存在“这一页的目标”“希望客户形成的判断”“页面实际文字”“文字与图片材料一起审核”；
- 前两项具有实际内容，后两项分别标识成稿栏和材料/画面栏；
- 缺少 customerJudgment 权威事实时 adapter 明确失败，不从其他字段推断；
- adapter 输出没有后台字段目录；
- 60 页顺序、保存、批次、revision 冲突和草稿恢复回归不退化。

### 9.2 验收分层

- 单元测试：只证明 ViewModel、adapter 和交互行为；
- 浏览器几何与截图：只证明当前本地页面结构和空间；
- 已验收前端对照：决定活动路由是否出现偏差；偏差按缺陷处理，不重开第二个 UI 验收门；
- Runtime/MCP 验收：留在后续投影收窄阶段；
- 真实宿主与 AI 回执：继续保持 `待验证`。

`contentReviewFrontendUiAcceptance = accepted` 已绑定文件、提交和哈希；Runtime/MCP、真实宿主与 AI 回执继续使用独立状态。

## 10. 版本与回退

1. 本设计、四份基线、08 原型和取代声明组成“前端合同冻结”提交；
2. 活动 React 路由/ViewModel/adapter/test 组成后续“已验收内容审核前端正式接入”提交；
3. Runtime/MCP/持久化收窄组成再后续“内容审核投影迁移”提交；
4. 三个阶段不得混在同一提交；
5. 任一阶段失败使用 `git revert <commit>` 回退，不重写共享历史。

## 11. 阶段出口

本合同冻结阶段只有同时满足以下条件才完成：

1. 四份唯一基线统一表达前端合同优先；
2. 08 HTML 不再显示被用户否决的后台模块；
3. 旧空间保真规格已明确被本设计局部取代；
4. Markdown 相对链接可解析；
5. 07/08 被引用原型真实存在；
6. diff 中没有 React、Runtime、MCP、视觉审核页或 PPT 运行数据修改；
7. 形成一个可独立回退的 Git 提交；
8. 已验收前端保持不变，下一阶段只做活动路由接入和后端反向拆解准备。
