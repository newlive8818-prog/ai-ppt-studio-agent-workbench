# AI PPT Studio 侧边栏 / 浏览器双形态与任务卡确认纠偏设计

**状态：** 已获用户批准；2026-08-13 补充批准宿主原生确认路径与确认意图词，待实现与重新验收
**日期：** 2026-08-12
**适用版本：** AI PPT Studio v1.6 最终验收纠偏
**上位基线：** `00-唯一研发基线索引-v1.0.md`、`01-产品需求基线-v1.0.md`、`02-系统详细设计-v1.0.md`、`03-UI设计与交互规范-v1.0.md`

**当前验收约束：** 用户已明确本次纠偏与真实项目恢复不使用 Image 2；严格路线 B 继续由 Codex Presentations 完成原生设计与实现，可选非语义资产阶段记录为未使用。

## 1. 问题与根因

真实试用暴露了两项 P0 偏差：

1. 轻量工作台通过带 UI 模板的 MCP render tool 在聊天消息中以内联卡片显示。实现把 MCP Apps 的 `inline` 展示模式误解为产品要求的“侧边栏”；实际效果挤占聊天阅读流，也没有形成持久工作台入口。
2. `MissionBrief` 只要 `topic`、`primary_audience` 和 `desired_judgment_or_action` 非空，运行时便自动写成 `confirmed`。AI 推断值因此被错误等同于用户确认，任务卡、材料状态和客户背景尚未核准时内容生产已经开始。

上述偏差同时属于实现错误和验收缺口。旧的聊天内 Widget 截图、自动确认 MissionBrief，以及建立在该任务事实之上的内容、视觉和 G2 证据，不得继续证明当前需求通过。

## 2. 已确认产品决定

### 2.1 双形态

产品只有两个 UI 工作形态：

- **Codex 侧边栏工作台**：唯一的轻量日常工作台，承载五个认知空间的结论、风险、待判断、成果状态和审阅入口。
- **Codex 内置浏览器专业审阅**：承载完整内容蓝图和视觉合同的连续阅读、精确标记与显式保存。

Codex 聊天是协作与交付通道，不是第三个 UI 工作形态。聊天只承载目标沟通、最高影响问题、任务卡或 Gate 的明确表达、专业解释、视觉样张和最终 PPTX。

### 2.2 禁止聊天 Widget

- 面向模型的普通数据工具不得附带 `_meta.ui.resourceUri`、`openai/outputTemplate` 或其他会让宿主在聊天消息中渲染 UI 的模板元数据。
- 轻量工作台不得通过 `render_ai_ppt_workbench` 一类聊天 render tool 启动。
- 专业审阅不得通过聊天内联卡片承载，也不得把 `fullscreen` 当成浏览器独立页面。
- 当前宿主没有真实侧边栏入口时，返回明确的 `HOST_SIDEBAR_UNAVAILABLE` 能力缺口；聊天继续可返回文字状态，但不得渲染替代 Widget，也不得把该状态记为侧边栏验收通过。

### 2.3 官方能力边界

2026-08-12 核对的 [官方 OpenAI 插件 UI 文档](https://developers.openai.com/plugins/build/chatgpt-ui)说明：MCP 自定义 UI 与对话一起渲染，公开展示形态为 inline、fullscreen 和 picture-in-picture，未提供插件强制指定持久 sidebar 的声明。[官方 Browser 文档](https://learn.chatgpt.com/docs/browser)说明 Codex/ChatGPT 桌面端内置 Browser 可打开网站和本地 Web 应用。两份文档都没有证明当前 AI PPT Studio 插件已经取得真实持久侧边栏入口，因此该宿主能力保持 `待验证`。

因此实现必须分开处理：

- 侧边栏工作台依赖 Codex 宿主实际提供的持久应用区域或后续正式 API；不得以 MCP `inline` 模拟。
- 专业审阅由 Browser Surface Adapter 打开当前项目的浏览器审阅资源。
- 如果宿主只支持浏览器、不支持侧边栏，浏览器审阅可以继续研发和验证，但侧边栏相关验收保持阻断。

浏览器审阅不建设独立 Web 产品，但为了在 Codex 内置 Browser 审阅页中完成权威读取与显式保存，允许插件按需启动一个受限的 loopback Review Bridge：只绑定 `127.0.0.1` 的随机端口，使用短时、单项目、单 reviewType、单 sourceVersion 的内存令牌，禁止目录浏览、外部网络访问和跨项目读取。令牌放在 URL fragment 中；页面首次加载后立即从地址栏移除 fragment，只在页面内存保存，并通过 Bearer header 换取投影和提交 `expectedRevision` 标记写入。服务端不得记录原始 fragment、Authorization、投影正文或用户标记内容。响应必须设置 `Cache-Control: no-store`、严格 `Content-Security-Policy`、`Referrer-Policy: no-referrer`；Host 必须是当前 loopback 会话，任何存在的 Origin 必须与该会话同源，状态写入还必须同时具备匹配 Origin 与正确 Bearer；任意文件路径、跨作用域请求和非白名单方法均拒绝。会话采用短时 lease/heartbeat；页面关闭信号只作提示，最后一个活跃 lease 结束或令牌到期后服务必须停止。它不是独立 Web 产品、共享服务或第二套业务后端，所有业务写入仍调用 Python 权威运行时。

内容审阅与视觉合同切换保持上述单类型隔离：页面只发送目标 `reviewType`，不得提交目标 projectRoot、sourceVersion 或 revision；当前 Bridge 完成同源 Origin 与 Bearer 校验后，从 Python 权威投影取得目标 sourceVersion/revision，签发新的短时单 `reviewType` 会话并导航。存在未保存标记或未完成标记编辑时必须阻断切换并保留草稿；目标投影不可用或换发失败时保留当前页面和项目状态。

原“生产插件不启动本地 Web Server”规则更新为：禁止常驻、公开监听或承载第二业务后端的 Web Server；本节定义的按需、短时、仅 loopback 的 Review Bridge 是唯一生产例外。若浏览器打开/保存稳定性或上述隔离检查未通过，保持 `BROWSER_REVIEW_UNAVAILABLE` / `BROWSER_REVIEW_SAVE_UNAVAILABLE`，不得降低安全边界或改用聊天 Widget。

## 3. 任务卡与材料确认合同

### 3.1 MissionDraft

AI 可以依据用户对话生成或修订 `MissionDraft`，但不得自行确认。任务卡至少展示：

- 汇报对象；
- 汇报主题；
- 期望促成的判断或行动；
- 当前材料清单；
- 关键背景、限制和禁区；
- 材料状态：`已有材料` 或 `当前明确无材料`；
- 仍未知且会影响内容准确性的事项。

字段齐全只会让状态从 `draft` 进入 `confirmable`，不会进入 `confirmed`。

### 3.2 MissionConfirmation

只有以下任一真实用户动作可生成不可变 `MissionConfirmation`：

- 用户在侧边栏任务卡执行显式确认；
- 用户在聊天中明确确认当前任务卡，Codex 保存宿主实际返回、可追溯且不可由 AI 自造的真实消息引用；不预设未经验证的 URI 格式。
- 当宿主不能提供可验证的聊天消息引用时，聊天中的确认意图触发一次 MCP/Codex 宿主原生确认；只有宿主返回 `accept` 后，才可把该次宿主交互形成的不可伪造确认身份写入 `MissionConfirmation`。`decline`、`cancel`、不支持该能力、超时或异常均不得写入确认。

聊天确认意图词包括 `OK`、`确认`、`采纳`、`继续` 及语义等价的明确肯定表达，但必须同时满足：

1. 当前完整任务卡已经在本次任务上下文中向用户展示；
2. 任务卡状态为当前 revision 的 `confirmable`；
3. 当前唯一最高影响待处理动作是“确认任务”；
4. 确认意图只能触发宿主原生确认，不能由模型直接生成凭据。

因此，普通讨论中的“继续”、对其他建议的“采纳”、未展示当前任务卡时的“OK”，均不得自动改变项目状态。宿主原生确认必须再次展示任务主题、汇报对象、期望判断/行动、材料模式及 proposal-only 身份提示，避免一个短词被错误绑定到其他对象。

确认凭据必须绑定：

- 当前 `mission_draft_ref`；
- 当前材料清单引用或空清单身份；
- `material_mode`；
- 用户动作 / 消息引用；
- 项目 revision；
- 确认时间。

AI 生成字段、默认值、页面打开、页面关闭、保存草稿、用户沉默或仅识别到确认意图词均不得生成确认凭据。

### 3.3 内容生产前置门

创建任何正式内容生产任务前必须同时满足：

1. `MissionDraft` 已达到 `confirmable`；
2. 存在绑定当前任务版本的 `MissionConfirmation`；
3. 当前材料状态满足以下二选一：
   - 至少一份用户提供且已登记的材料；
   - 用户明确确认 `material_mode=no-materials-confirmed`。

校验必须位于 Python 权威业务服务中；侧边栏、聊天 Prompt、Node MCP 和测试夹具均无权绕过。

## 4. 无材料的“方案建议模式”

用户已经确认：没有材料时可以继续，但只能作为方案建议。

当 `material_mode=no-materials-confirmed` 时，内容上下文进入 `proposal-only`：

- 客户现状、痛点、流程问题和组织判断统一标为 `诊断假设`；
- 架构、建设范围、实施路径和行动建议统一标为 `方案建议`；
- 未经来源支持的能力适配、业务结果和客户结论统一标为 `待联合验证`；
- 不得生成虚构数字、客户案例、客户引语、现状事实、能力承诺或效果承诺；
- 每页可见文案、讲解稿、主张—证据地图和专业审阅投影必须保留上述身份；
- G0 前明确提示“当前内容不代表客户已确认事实”。

后续补入真实材料时，系统保留旧版本，重新打开受影响的内容范围，把可证实内容转为来源事实，并重新执行相应内容审查；不得静默把原诊断假设改写成事实。

## 5. 状态与数据流

```text
用户目标 / AI 理解
        ↓
MissionDraft: draft
        ↓ 补齐最高影响缺口
MissionDraft: confirmable
        ↓ 用户显式确认
MissionConfirmation + material_mode
        ↓ 服务端前置门
material-backed ───────────────→ 来源事实驱动内容链
no-materials-confirmed ────────→ proposal-only 内容链
        ↓
五类内容独立审查 → G0 用户确认 → 后续视觉与交付
```

任何任务卡版本变化都会使旧 `MissionConfirmation` 过期，并重开 G0 及受影响下游状态。仅补充不改变任务目标的材料时，按材料影响范围重开内容；改变受众、主题或期望行动时，从任务确认和完整内容链重新开始。

## 6. UI 行为

### 6.1 侧边栏首次状态

项目未确认任务时，侧边栏项目总览主区域显示任务卡而不是交付认知地图。卡片完整显示任务字段、材料状态和身份提示，同一时刻只突出一个最高影响缺口。

主操作按状态变化：

- 字段不完整：`补充当前关键信息`；
- 字段完整未确认：`确认任务并开始内容策划`；
- 用户确认无材料：按钮附近显示“将以方案建议模式继续”；
- 已确认：切换为常规五空间认知投影。

### 6.2 浏览器专业审阅

- `打开内容审阅` / `打开视觉合同` 只打开 Codex 内置浏览器中的当前项目资源。
- 浏览器资源与侧边栏读取同一 revision 和 sourceVersion。
- Header 始终显示内容审阅/视觉合同双切换并标明当前状态；切换通过服务端换发新的独立作用域会话，不复用当前令牌越权读取另一审阅类型。
- 标记保存必须通过显式 `保存标记` 经受限 loopback Review Bridge 回写权威项目；若当前 Browser Surface Adapter 无可靠打开或写回能力，页面可用于只读研发验证，但保存与 G0/G3 的完整验收保持阻断。
- 浏览器关闭、重开和刷新不改变 Gate，也不得丢失已经持久化的标记。

## 7. 错误与恢复

新增或收紧以下错误：

- `MISSION_NOT_CONFIRMED`：任务卡未获得真实用户确认；阻止正式内容任务。
- `HOST_CONFIRMATION_UNAVAILABLE`：既无可验证聊天消息引用，宿主也不支持原生确认；保留当前 confirmable 任务卡并允许重试，不要求用户补材料，也不得建议绕开 AI PPT Studio。
- `HOST_CONFIRMATION_DECLINED`：用户在宿主原生确认中拒绝或取消；项目不变，继续等待任务卡修改或再次确认。
- `MATERIAL_MODE_UNCONFIRMED`：既无已登记材料，也无用户“当前无材料”确认；阻止正式内容任务。
- `PROPOSAL_ONLY_IDENTITY_VIOLATION`：无材料模式出现无来源事实、数字、案例或承诺；内容审查失败并定向返工。
- `HOST_SIDEBAR_UNAVAILABLE`：宿主没有真实持久侧边栏能力；保留项目状态，禁止聊天 Widget 替代，并阻断侧边栏验收。
- `BROWSER_REVIEW_UNAVAILABLE`：内置浏览器资源无法打开；保留审阅源和标记草稿，提供重试，不回退为聊天卡片。
- `BROWSER_REVIEW_SAVE_UNAVAILABLE`：浏览器可以阅读但不能可靠保存标记；禁止宣称完整审阅闭环通过。

## 8. 验收合同

必须新增真实路径证据：

1. 调用普通项目工具后聊天中不存在 AI PPT Studio iframe / Widget 卡片。
2. 工作台只出现在真实 Codex 侧边栏区域；关闭和重开后读取同一项目 revision。
3. 从侧边栏打开内容或视觉审阅时，Codex 内置浏览器出现同一项目资源，而不是聊天 `inline/fullscreen` UI。
4. AI 填齐任务字段后仍为 `confirmable`；没有真实用户确认引用时，正式内容任务被服务端拒绝。
5. 用户确认“当前无材料”后可以启动 proposal-only 内容链。
6. proposal-only 内容中的诊断假设、方案建议、待联合验证身份完整，虚构数字、案例、客户事实或承诺会使审查失败。
7. 用户后续补充材料时保留旧版本，按影响范围重开并重新审查。
8. Review Bridge 只监听 `127.0.0.1` 随机端口；令牌过期、项目/reviewType/sourceVersion 不匹配、Host 非当前 loopback、Origin 不同源、目录遍历、非白名单方法和缺失/错误 Bearer 均被拒绝，状态写入必须同时通过同源 Origin 与 Bearer 校验，日志不含令牌、正文和标记内容。
9. 页面关闭信号不得成为唯一生命周期依据；最后一个活跃 lease 结束或令牌到期后 Review Bridge 停止。其生命周期内不存在第二套业务状态，所有保存都经过 Python 的 sourceVersion、expectedRevision 和锚点校验。
10. 在已经展示当前 confirmable 任务卡且“确认任务”为唯一待处理动作时，`OK / 确认 / 采纳 / 继续` 均触发同一份宿主原生确认；宿主 `accept` 后创建当前 revision 的 MissionConfirmation，`decline/cancel` 时 revision 与项目状态不变。
11. 相同词语出现在普通讨论、其他建议反馈或没有当前任务卡的上下文时，不触发任务确认；确认意图词本身不得作为 `userActionRef` 或 `userMessageRef` 写入。

浏览器截图、组件测试或 MCP schema 测试不能代替真实侧边栏证据；聊天内 Widget 截图明确属于失败证据。

## 9. 对当前验收项目的影响

当前 `v16-真实售前验收-经营一体化方案` 的 MissionBrief 没有独立真实任务卡确认凭据，且当前已生成内容建立在旧自动确认合同上。因此：

- revision 51 与历史制品保留，不删除、不伪造；
- G0 及其后受任务事实影响的内容、视觉、锚点和 G2 证据不得继续作为最终验收依据；
- 实现新合同后，从任务卡确认处创建新版本并按正式恢复机制重跑；
- 104 项台账中所有依赖真实宿主、任务确认、内容、视觉和真实项目链路的证明重新取得；
- 在 104/104 前不提交。

## 10. 不采用的方案

- **继续使用聊天 inline Widget**：违反侧边栏唯一入口，拒绝。
- **把 inline/fullscreen 攵称侧边栏/浏览器**：只改命名不改宿主行为，拒绝。
- **两个形态都改成普通浏览器页面**：失去 Codex 侧边栏的日常认知入口，拒绝。
- **无材料时完全禁止继续**：与用户最新决定冲突，拒绝。
- **无材料时生成未标注的通用行业内容**：会把推断伪装成客户事实，拒绝。
- **把 `OK / 确认 / 采纳 / 继续` 字符串直接当作确认凭据**：模型可构造且缺少对象绑定，拒绝；这些词只触发宿主原生确认。
- **继续依赖启动时永远为空的 `confirmationVerifier`**：真实安装必然形成确认死锁，拒绝；运行时必须使用宿主声明的原生确认能力，或使用宿主实际提供的可验证消息/侧边栏动作适配器。
