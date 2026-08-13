# AI PPT Studio v1.6 macOS PowerPoint 发布目标策略设计

## 1. 文档状态

- 日期：2026-08-13
- 状态：已确认，待用户审阅书面规格
- 决策来源：用户明确要求“取消 WPS 和 Windows 的验证，先保证 MAC 和 office”，并进一步确认其含义为当前 v1.6 发布范围仅强制 `macos-powerpoint`，WPS 和 Windows 延期但保留未来扩展能力。
- 产品解释：这里的 “Office” 特指 macOS 桌面版 Microsoft PowerPoint，不包含 Word、Excel、WPS，也不构成对其他 Microsoft 365 应用的兼容声明。
- 权威上位合同：项目根目录四份唯一研发基线；本设计获批实施后，必须同步更新四份基线，以用户最新决定取代 2026-08-08 的四目标强制规则。
- 运行数据边界：真实 PPT 项目继续位于 `/Users/defei/Documents/AI-PPT-Workspace`，不得写入产品源码或并行 Web 产品空间。

## 2. 背景与冲突

现有 v1.6 合同将以下四个目标固定为 G2 和 G4 的共同硬门：

1. `macos-powerpoint`；
2. `macos-wps`；
3. `windows-powerpoint`；
4. `windows-wps`。

该固定矩阵已经写入产品需求、系统设计、UI 规范、Skill、Python Gate evaluator、视觉和交付服务、上下文编译器、投影、Widget 类型与测试、目标证据验证器和 104 项验收台账。当前真实项目已经取得一条正式、非模拟、可证明的 macOS PowerPoint G2 证据，但其余三条缺失，因此旧合同会继续阻止 G2。

用户最新决定改变了发布范围，而不是声明缺失目标已经通过。系统必须同时避免两种错误：

- 不得继续用旧四目标合同阻止当前 v1.6 发布；
- 不得把 WPS 或 Windows 标成通过，也不得从 macOS PowerPoint 结果外推兼容性。

## 3. 方案比较与采用决定

### 方案 A：直接把固定四目标常量改成一个目标

优点是改动最小，现有 G2 很快可以放行。缺点是把“系统认识哪些目标”和“当前版本要求哪些目标”混为一谈；历史 WPS/Windows artifact 可能变成不可解析数据，未来恢复目标还要再次改写领域模型，UI 也无法准确表达延期状态。

### 方案 B：保留支持 profile，新增版本化发布目标策略（采用）

领域层继续识别四种目标 profile，但 Gate 只要求当前项目绑定策略中的 `required_target_ids`。当前 v1.6 策略只要求 `macos-powerpoint`，其余三项作为 `deferred_target_ids` 明确展示。策略本身是项目内不可变 artifact，并被 G2/G4 Gate 事件引用。

该方案能让当前真实项目在不重写历史 artifact 的情况下采用新范围，也为将来恢复 WPS/Windows 提供明确的策略升级和 Gate 失效路径。

### 方案 C：完全删除 WPS 和 Windows profile

优点是产品表面最简单。缺点是与用户“延期、保留未来能力”的确认相反，也会破坏历史证据的可解析性，因此不采用。

## 4. 产品范围

### 4.1 当前 v1.6 强制发布目标

当前发布策略的唯一强制目标为：

```text
macos-powerpoint = macOS + Microsoft PowerPoint 桌面版
```

G2 的锚点 PPTX 和 G4 的最终 PPTX 都必须在该目标中取得真实桌面证据。开发预检、Codex Presentations 本地渲染、fixture、浏览器渲染和历史文件均不能替代该证据。

### 4.2 延期目标

以下目标保留为系统可识别 profile，但不进入当前 v1.6 G2/G4 必需矩阵：

- `macos-wps`；
- `windows-powerpoint`；
- `windows-wps`。

它们的产品状态统一为 `deferred`，含义是“当前版本不要求、未形成兼容声明”。`deferred` 不等于 `passed`、`failed`、`missing` 或 `not-supported`。

### 4.3 非目标

本次变更不执行以下工作：

- 不证明或否定 WPS/Windows 兼容性；
- 不删除历史四目标 artifact、测试记录或设计文档；
- 不增加用户在每个 PPT 项目中随意选择验收平台的 UI；
- 不降低业务语义、视觉完成度、排版工程、字体、可编辑性、逐页检查或聊天交付要求；
- 不把本次范围变更自动解释为整个产品最终 `104/104` 已通过；
- 不覆盖并行独立 Web 产品线。

## 5. 核心领域合同

### 5.1 支持目标与必需目标分离

目标领域拆分为两个概念：

```text
SUPPORTED_TARGET_IDS
  = macos-powerpoint
  + macos-wps
  + windows-powerpoint
  + windows-wps

ReleaseTargetPolicy.required_target_ids
  = 当前项目、当前发布策略真正阻断 Gate 的目标
```

`TargetRenderEvidence` 使用 `SUPPORTED_TARGET_IDS` 校验 profile、操作系统和应用身份，因此历史四目标证据继续可解析。`TargetEvidenceMatrix` 不再读取全局固定四目标常量，而是显式接收当前策略的 `required_target_ids`。

### 5.2 ReleaseTargetPolicy

新增不可变正式 artifact：

```json
{
  "policy_id": "v1.6-macos-powerpoint",
  "policy_version": "1.0",
  "status": "active",
  "required_target_ids": ["macos-powerpoint"],
  "deferred_target_ids": [
    "macos-wps",
    "windows-powerpoint",
    "windows-wps"
  ],
  "compatibility_claim_scope": ["macos-powerpoint"],
  "effective_at": "2026-08-13T00:00:00+08:00",
  "decision_source": "explicit-user-confirmation",
  "rationale": "v1.6 当前先保证 macOS Microsoft PowerPoint；WPS 和 Windows 延期。"
}
```

校验规则：

1. `required_target_ids` 非空、无重复，且都是受支持 profile；
2. `deferred_target_ids` 无重复，且都是受支持 profile；
3. 必需与延期集合互斥，并完整覆盖当前已支持 profile；
4. `compatibility_claim_scope` 必须与 `required_target_ids` 完全一致；
5. 当前正式策略必须是 `active`，并包含带时区的生效时间；
6. 策略只决定目标软件矩阵，不得关闭语义、审美、工程、字体、可编辑性和逐页检查。

项目通过 `release/target-policy` artifact head 绑定当前策略。Gate evaluator、任务上下文、交付报告和 UI 投影只能从该 head 读取当前要求，不得分别维护隐式目标列表。

### 5.3 旧项目兼容与策略绑定

已有 schema 3 项目可能没有 `release/target-policy`。迁移必须使用一次 revision-safe、可审计的运行时命令绑定当前默认策略，不得直接编辑状态 JSON。该命令产生新 artifact、事件和 revision，保留所有旧 artifact。

当前真实项目 `v16-final-real-acceptance-proposal-only` 在迁移时：

- 保留现有 G0、G1、视觉合同、锚点、审美/工程审查和 macOS PowerPoint 证据；
- 新增并绑定 `v1.6-macos-powerpoint` 策略；
- 不生成 WPS/Windows 通过记录；
- 因当前 G2 仍为 `open`，无需重开 Gate；
- 使用现有正式 `macos-powerpoint` 证据重新计算 G2。

对于已经通过 G2 或进入 G3/G4 的其他旧项目，策略变化属于质量门合同变化。运行时必须重开最早受影响的 G2，并锁定 G3/G4，直到新策略下的证据重新通过。若未来策略扩大目标集合，同样从 G2 重验；若只更换某个目标的软件版本且 PPTX 哈希不变，只使对应目标行过期。

## 6. G2 与 G4 计算

### 6.1 G2

G2 继续要求：

1. G1 已通过且 G2 为 `open`；
2. 当前 Deck Design System、完整 VisualContractSet 和 2–3 页冻结锚点一致；
3. 独立审美审查通过；
4. 独立 PPT 工程审查通过；
5. 当前 `ReleaseTargetPolicy` 有效；
6. `required_target_ids` 中每个目标恰有一条当前 G2 正式证据；
7. 所有必需证据通过、引用同一锚点 PPTX SHA-256，并按锚点最终顺序覆盖全部页面；
8. Gate 事件的 acceptance refs 与当前设计、锚点、两类审查、目标策略和全部必需目标 evidence heads 完全一致。

在当前策略下，第 6 项只要求 `macos-powerpoint`。延期目标既不加入缺失 blocker，也不加入 G2 通过证据集合。

### 6.2 G4

G4 继续要求：

1. G3 已确认；
2. 最终原生可编辑 PPTX、逐页四门、字体与平台报告、交付包均为当前版本；
3. 当前策略中的每个必需目标都有同一最终 PPTX SHA-256 的正式证据；
4. 该精确 PPTX 已通过 Codex 聊天发送并有真实宿主回执；
5. 用户对当前交付包明确确认 G4。

字体与平台报告中的 `targets` 必须等于当前 `required_target_ids`，并另外保存 `deferred_targets`，不能继续要求固定四目标，也不能把延期行写成通过。

### 6.3 哈希和证据失效

- PPTX SHA-256 变化：当前策略下所有必需目标证据失效；
- 当前必需目标的操作系统、PowerPoint 版本或字体环境变化：仅该目标证据失效；
- 策略扩大：新增必需目标缺失并阻断 G2/G4；
- 策略缩小：被移出的目标转为延期，不作为通过证据；已有历史 artifact 保留；
- 策略本身变化：Gate 事件必须绑定新策略，旧 Gate 证据集合不能自动沿用。

## 7. 应用服务与数据流

正式数据流为：

```text
用户批准发布范围
  -> 运行时登记 ReleaseTargetPolicy
  -> 项目 head 绑定 release/target-policy
  -> ContextCompiler 编译当前必需/延期目标
  -> Presentations 构建锚点或最终 PPTX
  -> 必需目标真实桌面取证
  -> TargetRenderEvidence 独立校验
  -> TargetEvidenceMatrix(required_target_ids)
  -> GateEvaluator 计算 G2/G4
  -> Workspace / Review / Delivery 投影准确显示范围和结果
```

MCP 仍是薄适配层，不自行计算 Gate。当前发布策略由产品版本和权威运行时管理，不新增普通用户可见的“跳过平台”按钮。将来若恢复目标，应通过正式产品变更和策略升级，而不是让 Agent 在验收过程中临时删减 blocker。

## 8. UI 与文案合同

### 8.1 目标证据显示

UI 从“固定四目标矩阵”改为“当前发布目标与延期目标”：

- 标题使用 `当前发布目标证据`，不再使用 `四目标桌面实机证据`；
- 强制区只显示当前策略的 required rows；
- 延期区显示 WPS/Windows profile 和 `延期 · 当前版本不验收`；
- 延期行不得显示绿色通过、缺失 blocker 或兼容结论；
- 兼容声明明确写为 `已验证：macOS Microsoft PowerPoint <version>`；
- 不出现“支持 Windows/WPS”或“跨平台通过”的概括文案。

### 8.2 工作台与专业审阅

- 侧边栏制作与交付投影显示当前策略、必需目标进度、最高 blocker 和聊天发送状态；
- 专业视觉审阅保留目标证据 artifact identity，但只把 required rows 计入 Gate；
- 锚点区明确区分 Codex Presentations 预检与 macOS PowerPoint 正式桌面证据；
- UI 类型仍允许全部受支持 target IDs，以便读取历史 artifact；
- fixture 和测试数据必须覆盖 required、deferred、failed、stale 和 policy-change 状态。

## 9. Skill 与 Agent 工作流

AI PPT Studio Skill 将 `four-target-acceptance.md` 重构为发布目标策略指引，或采用不带固定数量含义的新文件名并保留旧文件为历史跳转。当前工作流必须明确：

1. 在锚点或最终 PPTX 验收前读取当前 `ReleaseTargetPolicy`；
2. 只对 `required_target_ids` 请求正式桌面证据；
3. 当前 v1.6 只验证 `macos-powerpoint`；
4. WPS/Windows 是延期项，不能标成通过、失败或兼容；
5. 不得用 Presentations 预检替代真实 PowerPoint；
6. G2/G4 仍要求当前必需目标证据与同一个精确 PPTX 哈希一致；
7. Agent 不得在没有新产品决定和策略 artifact 的情况下自行缩小目标集合。

## 10. 验收台账语义

Requirement Ledger 继续保留 104 个稳定 requirement ID，避免通过删除要求制造分母下降。受本次决定影响的 requirement 文本和 proof contract 按新基线更新：

- 原“四目标固定强制”改为“当前发布策略中的全部必需目标强制”；
- 新增或明确证明 required/deferred 投影、策略绑定和兼容声明边界；
- WPS/Windows 延期本身不能以 `passed desktop evidence` 计分；
- 相关 requirement 只有在代码、测试、正式策略 artifact 和 UI/Skill 边界证据齐全时才可通过；
- 既有严格结论 `37/104` 在完成稳定 ID 逐项映射前保持不变；
- 最终仍可达到 `104/104`，但含义是新批准基线的全部 104 项均有证据，不是四个平台都通过。

旧验收报告保留历史数值和当时口径，在顶部追加范围变更说明与新策略引用，不回写历史事实为“当时已通过”。

## 11. 错误与阻断语义

新增或调整以下错误：

- `RELEASE_TARGET_POLICY_MISSING`：项目没有当前策略；阻止 G2/G4，并要求通过运行时绑定策略；
- `RELEASE_TARGET_POLICY_INVALID`：必需/延期集合不合法；拒绝写入且 revision 不增长；
- `TARGET_RENDER_EVIDENCE_MISSING`：当前策略中的某个必需目标缺少证据；只列实际必需目标；
- `TARGET_RENDER_EVIDENCE_FAILED`：必需目标证据失败；保留失败原因与定向修复；
- `TARGET_RENDER_HASH_MISMATCH`：必需目标证据与当前 PPTX 哈希不一致；
- `TARGET_POLICY_STALE`：Gate、字体报告或交付包绑定旧策略；阻止放行；
- `DEFERRED_TARGET_NOT_PROOF`：延期目标 artifact 可以保存为历史/实验记录，但不能加入当前 Gate acceptance refs 或兼容声明。

任何错误都不得让 UI 或 Agent回退到“用预检代替桌面证据”。

## 12. 测试设计

### 12.1 领域与 Gate

自动测试必须证明：

1. 四个 profile 仍可分别解析合法 `TargetRenderEvidence`；
2. 当前策略只要求 `macos-powerpoint`，单条真实结构证据可形成完整矩阵；
3. 缺少或失败的 `macos-powerpoint` 仍阻止 G2/G4；
4. 缺少 WPS/Windows 不阻止当前策略；
5. WPS/Windows artifact 不能冒充当前必需证据，也不能扩大兼容声明；
6. 混合 PPTX 哈希、重复必需目标、错误应用身份、缺页或模拟证据仍被拒绝；
7. 策略扩大为四目标后，原单目标 Gate 证据立即不足；
8. 旧四目标 artifact 在新代码下仍可解析；
9. 现有项目通过 revision-safe 策略绑定迁移，不改写旧 artifact；
10. 策略变化对已通过项目重开 G2 并锁定下游 Gate。

### 12.2 应用与投影

自动测试必须证明：

1. VisualService、DeliveryService、GateEvaluator 和 ContextCompiler 使用同一策略来源；
2. G2 acceptance refs 精确包含策略、设计、锚点、两类审查和 `macos-powerpoint` evidence；
3. G4 字体/平台报告、交付包和聊天回执绑定相同策略与 PPTX；
4. 工作台和专业审阅显示一个 required row 与三个 deferred rows；
5. UI 不再出现“四目标已通过”“跨平台通过”等越界文案；
6. MCP 和运行时在 revision 冲突、旧策略和证据过期时返回明确错误。

### 12.3 真实验收

当前真实项目必须证明：

1. 策略 artifact 已权威回写并可解析；
2. 已登记的 `macos-powerpoint` G2 evidence 仍绑定锚点 PPTX SHA-256 `1aa97f42c41adc0cf9f6eb4f989d88586598f8cf9cc0d9c7c510459e54e07de3`；
3. G2 只在独立审美、独立工程和当前策略必需证据精确齐全时通过；
4. G3 在 G2 后才开放，完整 12 页 PPTX 在 G3 用户确认前仍不得构建；
5. G4 对最终 PPTX 重新取得 macOS PowerPoint 正式桌面证据，不能复用 G2 锚点证据；
6. WPS/Windows 在投影中为延期且不产生兼容声明。

## 13. 实施范围与顺序

实施按以下顺序进行：

1. 同步四份唯一研发基线和本设计的已批准状态；
2. 先以测试定义 `ReleaseTargetPolicy`、支持 profile 与必需目标矩阵；
3. 修改领域合同、Gate evaluator、视觉/交付服务、上下文编译和投影；
4. 增加旧项目 revision-safe 策略绑定迁移；
5. 更新 MCP/支持脚本、Skill 和目标验收参考；
6. 更新 Widget/专业审阅类型、组件、fixture 和文案；
7. 更新 104 项 ledger proof contract 和严格验收说明，但不提前提高通过数；
8. 跑 Python、Node、Widget、Skill 和 ledger 回归；
9. 安装新插件版本并从真实 Codex 宿主复验；
10. 对当前真实项目绑定策略，使用既有正式 macOS PowerPoint G2 证据推进 Gate；
11. 只在 G2 通过后发布视觉审阅并请求用户 G3。

## 14. 完成条件

本变更只有在以下条件全部满足时才完成：

- 四份唯一研发基线不再把 WPS/Windows 写成当前 v1.6 强制目标；
- 运行时只有一个权威 `ReleaseTargetPolicy` 来源，UI、Skill 和 Gate 不维护冲突列表；
- 当前策略只要求 `macos-powerpoint`，其余 profile 明确延期；
- 历史四目标 artifact 仍可解析，当前项目历史不被改写；
- 自动测试与真实项目都证明 macOS PowerPoint 缺失/失败仍阻断，WPS/Windows 缺失不再阻断；
- 已有 G2 macOS PowerPoint 证据被权威解析并参与新 Gate，而不是重新伪造；
- G4 仍要求最终 PPTX 的全新 macOS PowerPoint 桌面证据、聊天发送回执和用户明确确认；
- 严格台账按稳定 ID 和新 proof contract 重算，不通过删项或延期项制造虚假 `104/104`；
- 未宣称 WPS、Windows、跨平台或整个产品最终验收通过。
