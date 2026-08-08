# AI PPT Studio 契约优先重构设计

## 1. 文档状态

- 日期：2026-08-08
- 状态：已确认
- 决策来源：用户确认采用方案 A，并将 macOS PowerPoint、macOS WPS、Windows PowerPoint、Windows WPS 纳入一期强制验收。
- 权威上位合同：项目根目录四份唯一研发基线。
- UI 参考：`产品代码/prototypes/06-fullscreen-contract-review-exploration.html`。

## 2. 目标

在保留产品身份、插件入口和本地项目边界的前提下，淘汰与 v1.6 合同冲突的旧实现，重建一套契约优先、证据驱动的 Agent 原生工作台。最终系统必须完整贯通 Skill、MCP、Python Runtime、内容与视觉多智能体治理、严格路线 B、双形态 UI、G0–G4、反馈与经验、原生 PPTX 和四目标桌面软件实机验收。

完成不是“存在类库”或“单元测试通过”，而是一个真实售前项目能够从任务书、材料和内容治理运行到四目标实机通过的可编辑 PPTX，并由 Codex 聊天发送文件、记录 G4，且 Requirement Ledger 中没有未证明的一期要求。

## 3. 采用方案

采用方案 A：保留已批准的 Node / Python / React 技术边界，重写内部产品内核。

- Python Runtime 是项目状态、制品、治理、任务、Gate 和恢复的唯一业务执行者。
- Node MCP Server 是薄适配层，只做输入输出 Schema、Runtime 调用和 MCP App 资源发布。
- React Widget 与专业审阅页只消费权威投影，不自行推导 Gate 或兼容状态。
- Skill 只规定合法工作流、角色隔离、工具顺序、暂停条件和交付合同。
- 不采用渐进保留旧业务规则的兼容式重构，也不改成全 TypeScript 内核。

## 4. 总体架构

```text
Codex 聊天 / Native Widget / 专业审阅页
                    │
              Node MCP Adapter
                    │
          Python Application Runtime
                    │
   ┌────────────────┼─────────────────┐
项目内核          生产治理           投影与交付
revision/event     内容多智能体       WidgetProjection
artifact/hash      视觉多智能体       ReviewProjection
transaction        严格路线 B         ChatDeliveryReceipt
recovery           G0–G4             ReviewMarkSet
                    │
       /Users/defei/Documents/AI-PPT-Workspace
```

运行数据不得写入产品源码目录。并行 Web 产品空间保持隔离。

## 5. 模块边界

保留公开包名 `ai_ppt_studio`，内部按单一职责重建：

```text
ai_ppt_studio/
├── kernel/
│   ├── artifacts.py
│   ├── events.py
│   ├── revisions.py
│   ├── transactions.py
│   └── references.py
├── domains/
│   ├── mission/
│   ├── materials/
│   ├── content/
│   ├── visual/
│   ├── presentation/
│   ├── feedback/
│   └── experience/
├── application/
│   ├── commands/
│   ├── orchestration/
│   ├── gates/
│   ├── projections/
│   └── recovery/
└── adapters/
    ├── filesystem/
    └── platform_evidence/
```

每个模块公开稳定输入、输出和错误类型。领域模块只通过版本化正式制品协作，不共享可变内部状态。

## 6. 权威写入与制品引用

所有业务写入采用同一命令管线：

```text
Command + expectedRevision
  -> 权限与阶段校验
  -> Schema、引用、哈希和证据校验
  -> 领域规则与 Gate 计算
  -> 原子写入 Artifact + Event + ProjectState
  -> 生成 Widget / Review / Chat 投影
```

正式引用使用内容寻址身份：

```text
artifact://<ArtifactKind>/<sha256>
```

引用解析必须验证制品存在、种类、版本、哈希和适用项目。普通字符串、角色名或不存在的哈希不能成为放行证据。`GateEvaluator` 是唯一可计算通过结果的模块；UI、Skill、MCP、Agent 和测试夹具不得直接写入 `passed`。

## 7. 内容生产链路

```text
MissionBrief + Materials
  -> PresalesContentStrategy
  -> ClaimEvidenceMap
  -> DeckArgumentMap
  -> SlideDraftSet
  -> 五类隔离 ContentReviewRecord
  -> ContentRepairPlan / 定向修复与复审
  -> ContentAcceptanceRecord
  -> 专业审阅页
  -> ReviewMarkSet
  -> FeedbackGovernanceRecord
  -> ContentChangeSet 或聊天 G0
```

五类审查至少覆盖售前专业、决策者、证据、叙事和专业表达。缺失审查、版本不一致、关键证据缺失或任何适用硬条件失败时，不得生成通过的 `ContentAcceptanceRecord`。内部失败版本不能进入默认用户审阅或 G0。

## 8. 视觉与 PPTX 链路

```text
G0
  -> VisualBrief
  -> 隔离创意、内部质询与跨专业深化
  -> DeckDesignSystem + 全部 SlideVisualContract
  -> G1
  -> Presentations 原生锚点页
  -> 可选 Image 2 非语义资产
  -> 四目标实机导出与逐页检查
  -> G2
  -> 专业审阅与聊天 G3
  -> 整套原生 PPTX
  -> 每页四重硬门与整套节奏验收
  -> 四目标整套实机导出
  -> 聊天发送 PPTX 与 G4
```

正式路线固定为严格路线 B。Presentations 同时承担原生视觉设计和 PPTX 实现。Image 2 只能在原生首版结构、层级和业务关系冻结后生成无文字、无数字、无业务关系、无真实证据冒充的可替换非语义图层。

## 9. 四目标强制实机验收

G2 和 G4 同时要求：

1. macOS + Microsoft PowerPoint 桌面版；
2. macOS + WPS Office 演示桌面版；
3. Windows 11 + Microsoft PowerPoint 桌面版；
4. Windows 11 + WPS Office 演示桌面版。

四个平台必须引用同一个被验收 PPTX SHA-256。`TargetRenderEvidence` 至少包含：

- 目标操作系统、版本和目标标识；
- 应用名称和版本；
- 字体清单、缺失字体、替代策略及字宽/换行风险；
- PPTX SHA-256；
- 原生导出物、逐页图片或 PDF 的引用和哈希；
- 每页对象消失、错位、字体替代、溢出、裁切、遮挡、异常换行和设计意图掉级检查；
- 业务语义、视觉完成度、排版工程和目标渲染的二元结论；
- 检查执行者、时间、工具版本和不可变证据引用。

任一目标失败或缺失，G2/G4 均不得通过。PPTX 哈希变化会使四套证据全部过期。PPTX 未变化而单一目标环境变化时，可以只重做受影响目标，但必须形成新证据版本。

## 10. 双形态 UI

### 10.1 Native Widget

Widget 适配 360–480px，只显示项目、revision、五个认知空间、当前结论、最高风险、待判断、成果状态、一个主操作、审阅入口和制作/四目标证据状态。它不复制完整合同、联系表、大图质检、下载区或 Gate 确认。

### 10.2 专业审阅页

内容与视觉共用一份 `ProfessionalReviewApp`、同一 `ReviewProjection` 和同一保存接口：

- Codex 右侧审阅区从 760px 起正式支持；
- 独立页面覆盖 1000px、1440px 和更宽视口；
- 宿主低于 760px 时由 Review Surface Router 打开同一资源的独立页面；
- 1440px 可以使用宽正文和合同双列，1000px 与 760px 自动单列；
- 约 64px 单行 Header 在 760px 保留内容/视觉切换、目录、标记状态和保存；
- 目录默认折叠并覆盖打开；标记抽屉也覆盖打开，二者互斥；
- 全部冻结文字、备注、来源和合同连续展开，不依赖逐页 Tab；
- 右上角 `保存标记` 是唯一强操作；
- 不显示返回聊天、顶部版本历史、样张画廊、Gate 确认或 PPTX 下载。

选中文字标记保存 `fieldAnchor + exactText + prefix + suffix + sourceVersion`。业务状态不使用 `localStorage`。保存使用 `expectedRevision` 和幂等键；冲突或网络失败时保留草稿。

## 11. 失败与恢复

- Schema、引用、哈希或制品种类不匹配：拒绝写入，不增加 revision。
- Agent 任务失败：保留上一有效制品，从最近检查点重试。
- revision 冲突：返回最新状态、差异和冲突字段，不覆盖用户输入。
- 标记保存失败：草稿保留，成功前不显示已保存。
- 内容或视觉审查失败：只生成修复计划，不生成通过记录。
- 单一平台失败：保留其他平台证据，但 Gate 维持失败并只重跑失败目标。
- UI、宿主或聊天桥接失败：保留项目状态，使用同一资源独立页面或明确人工继续路径。
- 关闭并重开 Widget、审阅页或任务：从项目状态恢复，不依赖浏览器本地存储。

## 12. 旧实现清退与迁移

- 保留插件身份、安装入口和仍符合新合同的公开工具名称。
- 删除用户选择 G1/G2 方向、Image 2 整页先行、数字评分、UI 自行推断通过等旧能力。
- 每个新纵向切片贯通后删除对应旧生产代码、旧测试夹具和构建残留，不保留永久双实现。
- 提供一次性旧项目导入器，只迁移能够验证的任务、材料、事实和正式制品。
- 旧项目缺少真实审查或目标平台证据时保持未验证，不能伪造历史通过。
- 历史决策文档可保留并明确标记历史；四份唯一基线与本设计是当前有效合同。

## 13. 验收体系

建立 Requirement Ledger，为四份基线中的每项一期要求分配稳定 ID，并记录证明方式、自动测试、实机证据、真实项目证据和当前结论。

验收至少包含：

- Python 内核、领域合同和属性测试；
- 内容、视觉、反馈、经验纵向集成测试；
- MCP Schema、权限和 Gate 隔离契约测试；
- Skill 静态合同检查；
- Widget 360–480px 验收；
- 审阅页 760、1000、1440px 验收；
- 60+ 页连续文档、目录、标记、冲突恢复和性能验收；
- 四目标 G2/G4 真实桌面软件证据；
- 一个真实售前项目从 MissionBrief 到聊天发送 PPTX 和 G4 的端到端验收；
- 插件安装、重装、项目恢复、运行目录隔离和无远程业务依赖验证。

自动测试、旧 smoke JSON 或单次历史 PPTX 都不能替代当前四目标实机证据和真实项目验收。

## 14. 实施切片

1. 将四目标强制验收同步至四份基线，建立 Requirement Ledger。
2. 重建 revision、事务、事件、内容寻址制品和引用验证内核。
3. 贯通任务书、材料、内容多智能体、审阅、反馈治理和聊天 G0。
4. 贯通视觉多智能体、严格路线 B、锚点页、四目标 G2 和聊天 G3。
5. 贯通整套原生 PPTX、逐页四门、四目标 G4、聊天发送和恢复。
6. 贯通案例、反馈、角色化经验切片、晋级、回滚和稳定能力隔离。
7. 完成双形态 UI、60+ 页性能、revision 冲突、失败恢复和无障碍验收。
8. 完成插件安装、真实项目端到端、四平台证据和最终验收台账。

每个切片都必须采用 TDD，并同时落地 Runtime、MCP、Skill、投影/UI 和验收；不得再次以孤立类库或孤立测试代替产品链路。

## 15. 非目标

- 独立 Web SaaS、登录、云数据库、团队协作、计费和远程任务队列；
- 通用 PowerPoint 编辑器；
- AI 主动搜索互联网项目材料；
- 用户参与 G1/G2；
- 专业审阅页内的 Gate、下载或返回聊天入口；
- 以数字评分、平均或多数投票放行内容、审美或工程质量。
