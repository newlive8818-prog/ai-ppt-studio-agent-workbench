# AI PPT Studio｜Presentations 主导生产与目标渲染治理设计

**日期：** 2026-08-06

**状态：** 已批准，待研发实施

**适用范围：** G1 视觉收敛之后的视觉合同深化、G2 锚点页、G3 后整套生产、G4 交付验收，以及 Image 2 非语义资产和目标软件兼容声明

**权威输入：** 项目根目录四份唯一研发基线；发生冲突时以更新后的产品需求基线为准

**验证输入：** [严格路线 B 与 PowerPoint 目标渲染验证记录](../../validation/2026-08-06-strict-route-b-powerpoint-target-render-validation.md)

## 1. 要解决的问题

旧机制把 Image 2 视为整页视觉构想来源，再要求 Presentations 翻译为可编辑 PPTX。真实实验暴露了三个风险：

1. Image 2 的构图、层级、色块、图标和图片关系没有稳定的结构化传递合同；
2. Presentations 在翻译整页位图时容易发生文字错乱、对象错位和视觉完成度下降；
3. 开发渲染通过不能证明 Microsoft PowerPoint 桌面版中的字体、换行、层叠和几何仍然成立。

本设计把正式生产改为严格路线 B：视觉合同规定专业意图、边界和质量结果，Presentations 在合同约束下直接完成原生视觉设计和 PPTX 实现；Image 2 只承担后置非语义资产，目标 PowerPoint 实机导出承担最终渲染真相。

## 2. 已确认决定

1. 一期正式项目固定使用 `strict-B`，不让用户选择 A/B/C。
2. 多智能体先形成完整 Visual Brief、Deck Design System 和全部 Slide Visual Contract。
3. Codex Presentations 同时承担原生视觉设计与 PPTX 工程实现，不是对 Image 2 整页图的机械还原器。
4. Presentations 可以在不改变 G0 语义、页面家族、视觉命题和硬规则的范围内决定具体布局、色块、图标、图片、背景和修饰。
5. 原生首版完成全页检查并冻结后，Image 2 才可生成背景、纹理、插画、光效等非语义资产。
6. Image 2 不得决定构图、信息层级、业务关系、事实内容或真实证据，也不得生成整页业务母版供 Presentations 复刻。
7. Presentations/开发渲染只作预检；G2 和 G4 的最终渲染证据来自 Microsoft PowerPoint 桌面版实机导出。
8. 默认验证当前生产平台；明确跨平台交付时追加目标平台复验。WPS 是独立兼容目标。
9. 业务语义、视觉完成度、排版工程、目标软件渲染四门任一失败即拒绝版本。
10. 新版本不因智能体数量、讨论轮次或合同长度增加而自动更好；上一有效版本始终保留。

## 3. 路线定义

| 路线 | 关系 | 正式身份 | 约束 |
|---|---|---|---|
| A | Image 2 先做整页视觉设计，Presentations 再还原 | 内部实验 | 与 B/C 输入、Context Pack、产物和审查隔离 |
| B | 视觉合同先形成，Presentations 直接原生设计与实现；Image 2 后置非语义资产 | 一期唯一正式路线 | `productionRoute=strict-B` |
| C | Image 2 完成整页结果，Presentations 完全复刻 | 内部实验 | 与 A/B 隔离，不进入正式项目 |

路线 A/C 的结果只能用于独立研究和后续产品决策，不能作为路线 B 当前项目的参考图、母版、Prompt 输入或验收基准。

## 4. 正式生产状态机

```text
G1 passed
  -> freeze VisualBrief + DeckDesignSystem + all SlideVisualContracts
  -> compile NativeVisualDesignBrief
  -> Presentations native-first design and build
  -> full-slide preflight and native-first freeze
  -> optional Image 2 non-semantic asset generation
  -> asset validation
  -> Presentations controlled asset integration
  -> development preflight render
  -> current-platform PowerPoint target export
  -> semantic / aesthetic / engineering / target-render gates
  -> failed: preserve last valid version -> targeted repair -> re-export
  -> G2 passed
  -> G3 user checkpoint
  -> full-deck Presentations production
  -> full-deck PowerPoint target export and four-gate review
  -> G4 user checkpoint
```

Image 2 不可用时，`optional Image 2` 节点可跳过；原生首版仍可继续进入 G2。Presentations 或目标 PowerPoint 证据缺失时不可跳过。

## 5. 中文角色责任

| 中文正式名称 | 本设计中的责任 | 禁止事项 |
|---|---|---|
| 视觉设计编排智能体 | 锁定 `strict-B`、编译上下文、管理依赖、版本和返工 | 不把 A/C 结果注入正式路线 |
| 视觉艺术指导智能体 | 形成视觉命题、构图语法、页面家族与节奏 | 不以一张样图替代完整合同 |
| 编辑设计智能体 | 规定长文阅读、标题正文、密度与留白结果 | 不删除冻结文字解决布局 |
| 信息设计智能体 | 规定层级、关系、比较、流程与数据表达结果 | 不让装饰图形承担业务关系 |
| 图像艺术指导智能体 | 规定真实图片和非语义资产的用途、裁切与真实性 | 不让生成资产冒充真实证据 |
| PPT 工程智能体 | 用 Presentations 完成原生视觉设计、实现、预检和资产整合 | 不复刻 Image 2 整页母版，不以工程便利降低设计目标 |
| 独立审美审查智能体 | 审查视觉完成度、构图、层级、节奏和设计感 | 不直接改稿或用数字平均放行 |
| 信息表达审查智能体 | 审查业务关系和信息表达准确性 | 不用“好看”补偿语义错误 |
| 编辑阅读审查智能体 | 审查阅读路径、密度、换行和跨页连续性 | 不通过删字掩盖排版失败 |
| PPT 工程审查智能体 | 审查原生对象、字体、层叠、裁切、目标 PowerPoint 证据和兼容声明 | 不用开发渲染冒充目标软件证据 |

## 6. 正式任务包

### 6.1 `NativeVisualDesignBrief`

必须包含：

- G0 冻结内容及逐页来源；
- Visual Brief、Deck Design System、Slide Visual Contract 版本；
- 页面家族、沟通目标、核心主张、信息层级和业务关系；
- Presentations 可自主实现范围与不可改变项；
- 原生对象、真实图片、受控位图和禁止位图的路由；
- 网格、安全区、字体、颜色、图像、图标、线段、背景、修饰和节奏要求；
- 目标 PowerPoint、生产平台、字体清单、替代策略和跨平台目标；
- 四重硬门、输出 Schema、保存位置和上一有效版本；
- 显式排除：Image 2 整页实验结果、其他路线产物、未治理反馈。

### 6.2 `ImageAssetPromptPack`

只有引用已冻结 `nativeFirstPptxRef` 和 `nativeFirstRenderRefs[]` 才可执行。必须明确：

- 目标页面与资产角色；
- 尺寸、主体、风格、裁切安全区和透明/替换要求；
- 禁止文字、数字、符号、箭头、业务关系、Logo、水印、系统截图、客户现场和真实证据冒充；
- 资产移除后页面语义与结构保持完整；
- Prompt、模型、质量、输出尺寸、哈希、生成时间、检查结果和使用页面。

### 6.3 `VisualRepairInstruction`

必须包含失败门、目标页面/对象、保持不变项、期望结果、上一有效版本、是否需要重新生成资产、重新导出的目标平台和原审查角色。

## 7. 正式产物合同

### 7.1 `NativeFirstBuild`

- productionRoute=`strict-B`；
- visualContractRef、nativeVisualDesignBriefRef；
- pptxRef、renderRefs[]、editabilityEvidenceRefs[]；
- fullSlideReviewRefs[]、frozenAt、sha256；
- 禁止包含对 A/C 整页图的依赖。

### 7.2 `ImageAssetPack`

- nativeFirstBuildRef；
- assets[]：fileRef、promptRef、model、dimensions、sha256、acceptedRole、targetSlides[]；
- semanticAbsenceChecks[]；
- rejectedAssets[] 与理由；
- assetIntegrationPlanRef。

### 7.3 `PresentationBuild`

- nativeFirstBuildRef、imageAssetPackRef、finalPptxRef；
- assetIntegrationChanges[]；
- preflightEnvironment、preflightRenderRefs[]、preflightCheckRefs[]；
- targetRenderEvidenceRef；
- repairHistoryRefs[]、lastValidBuildRef、revision。

### 7.4 `TargetRenderEvidence`

至少包含：

- targetApplication、operatingSystem、operatingSystemVersion、applicationVersion；
- sourcePptxRef、sha256Before、sha256After；
- fontInventoryRef、fontSubstitutionPlanRef、platformSpecificFontRisks[]；
- PDF、逐页 PNG 和导出时间；
- 每页业务语义、视觉完成度、排版工程、目标渲染四门结论；
- 失败页面、证据、返工指令和复验结果；
- compatibilityClaims[]，只允许写入已有同级实机证据的平台。

## 8. 四重硬门

### 8.1 业务语义门

- G0 冻结文字、数字、事实身份、来源、页面顺序和核心主张未改变；
- 业务关系、流程方向、架构层级、图表含义和真实证据未被生成资产或布局误导；
- 页面移除全部 Image 2 非语义资产后仍能完整表达业务语义。

### 8.2 视觉完成度门

- 视觉命题、页面家族、构图语法和整套节奏成立；
- 层级、对齐、留白、视觉锚点、图片和修饰共同服务核心主张；
- 未出现机械卡片墙、同构重复、无语义装饰、低对比或明显设计掉级。

### 8.3 排版工程门

- 原生对象/位图边界符合合同；
- 无溢出、裁切、遮挡、错误层叠、意外换行、断裂连接线或不可替换资产；
- 字体、行距、字重、安全区、对齐和备注完整；
- PPTX 文件、页数、尺寸、来源备注和压缩包结构有效。

### 8.4 目标软件渲染门

- 当前生产平台 Microsoft PowerPoint 桌面版实机导出成功；
- 导出前后 PPTX 哈希一致；
- 逐页图片中无对象消失、错位、字体静默替代、裁切、异常换行或视觉掉级；
- G2 覆盖 2–3 页锚点，G4 覆盖整套页面；
- 开发渲染只能作为对照，不能替代本门。

四门不计算总分，不用平均、权重、票数或优点补偿。任一适用项失败时整体 `failed`。

## 9. 平台与字体治理

1. 默认目标软件是 Microsoft PowerPoint 桌面版。
2. 当前在哪个平台生产，至少必须通过该平台 PowerPoint 实机验收。
3. 默认不要求同一项目同时验证 macOS 和 Windows。
4. 用户或交付合同明确要求跨平台时，增加目标平台同级导出、字体和逐页复验。
5. 使用 `PingFang SC` 等 macOS 专属字体时，必须记录 Windows 替代字体；默认候选可为微软雅黑，但不能未经实机验证直接声明等价。
6. 字体替代必须重点复核字宽、断行、文本框高度、图文对齐、页码和表格/图示几何。
7. WPS 是独立目标；PowerPoint 通过不等于 WPS 兼容。

## 10. 失败、返工和版本恢复

1. 每个 G2/G4 构建保存 `lastValidBuildRef`。
2. 失败时只修改命中失败门的页面、对象或合同字段，未受影响范围保持冻结。
3. 若视觉合同本身导致实现掉级，重开受影响 G1/G2 合同范围；若只是对象工程问题，不重写整套合同。
4. 非语义资产导致失败时优先移除或替换资产，不破坏原生结构。
5. 修复后必须重新完成原失败门和受影响的上下游检查；目标渲染失败必须重新实机导出。
6. 新版本只有四门全部通过且不存在相对上一有效版本的新退化时，才能替代 `lastValidBuildRef`。

## 11. UI 投影要求

- 正式项目显示 `Presentations 原生设计与制作`，不显示路线选择器；
- Image 2 只显示 `未使用 / 非语义资产生成中 / 已受控加入 / 资产失败但原生首版可用`；
- 开发渲染固定标记 `预检`，目标软件导出标记真实应用、平台和版本；
- G2/G4 并列显示四门 `通过 / 未通过`，任一失败时整体未通过；
- 显示已验证平台和未验证平台，WPS 不与 PowerPoint 合并展示；
- 用户可查看字体、哈希、导出物和失败页面，但不需要管理技术流水线。

## 12. 研发验收

1. 正式项目状态和 Context Pack 均固定 `productionRoute=strict-B`。
2. Presentations 任务不读取 A/C 整页实验产物。
3. 原生首版在 Image 2 之前存在、已全页检查并有独立哈希。
4. Image 2 任务没有原生首版引用时被拒绝；生成资产含语义内容时被拒绝。
5. Image 2 失败不破坏原生首版，也不阻断无需资产的页面继续审查。
6. G2 缺少当前生产平台 PowerPoint 实机证据时不能通过。
7. G4 缺少整套目标 PowerPoint 导出时不能进入交付。
8. 开发渲染无法伪装为 TargetRenderEvidence。
9. 四门任一失败时保留上一有效版本并形成定向返工任务。
10. 未实机验证的 Windows、macOS 或 WPS 不生成兼容声明。
11. 所有用户可见智能体名称为中文。

## 13. 待验证

- 严格路线 B 在 24–60 页完整售前方案和不同页面家族中的跨项目稳定性；
- 视觉合同详细度与 Presentations 自主设计空间之间的最佳边界；
- PowerPoint for Windows 实机导出的自动化、权限和恢复机制；
- macOS/Windows 字体替代后的字宽、换行和几何回归案例库；
- WPS 独立兼容验证的最低样本和工具链；
- 目标渲染自动返工轮次、耗时和成本阈值。

以上均保持 `待验证`，不得根据本次单一实验提前固化。
