# AI PPT Studio v1.6 侧边栏 / 浏览器与任务确认纠偏实施计划

> 状态：纠偏实现、本地回归、确定性发布与安装已完成；真实宿主和真实项目验收待新任务继续
> 日期：2026-08-12
> 对应设计：`../specs/2026-08-12-sidebar-browser-and-mission-confirmation-design.md`

## 目标

把当前“聊天内 Widget + 字段齐全自动确认”的实现纠正为已批准的唯一合同：真实 Codex 侧边栏轻量工作台、Codex 内置 Browser 专业审阅、聊天纯协作/确认/交付，以及由真实用户动作生成的独立 `MissionConfirmation`。没有材料时只允许以 `proposal-only` 身份继续。

本计划不恢复真实验收项目 G2，不修改 PPTX，不生成或登记任何侧边栏、Browser、Windows、WPS 或用户确认伪证据。真实项目 revision 51 的旧 MissionBrief、G0 和下游证据保留为历史，不原地改写。104/104 前只记录工作检查点，不创建 Git commit。

## 已确认根因

1. `domains/mission/contracts.py::validate_mission` 在三个最低字段齐全后直接写入 `status=confirmed`，没有独立确认对象。
2. `ContentService.register_content_stage` 与 `ProjectCommandService.request_agent_action` 没有权威前置门，调用方可绕过任务和材料确认直接开始正式内容生产。
3. `mcp/server.mjs` 注册 `render_ai_ppt_workbench` / `render_ai_ppt_review`，并附带 `ui.resourceUri`、`openai/outputTemplate`，因此宿主按 MCP Apps 合同把 UI 渲染在聊天消息中。
4. Widget 前端用 `requestDisplayMode("fullscreen")` 充当专业审阅入口；这只能改变聊天 MCP App 展示模式，不能形成 Codex Browser 路由。
5. Skill、探测脚本和预览脚本仍描述或调用旧 `MissionBrief`、inline/fullscreen render tools，导致运行说明与已批准基线冲突。

## 执行原则

- 每个行为变更先写失败测试，确认失败原因与本任务一致，再写最小实现。
- Python 权威服务承担任务确认、材料模式、proposal-only 身份、revision 和 sourceVersion 校验；Node、UI、Skill 和测试夹具不得绕过。
- 新对象使用新 slot/kind；旧 `mission` / `mission-brief` 只读兼容为历史，不自动升级为已确认。
- 普通 MCP 工具只返回文字与纯 `structuredContent`，不得附着聊天 UI template。
- 侧边栏入口能力未被真实宿主证明前，稳定返回 `HOST_SIDEBAR_UNAVAILABLE`，不得以 inline/fullscreen 降级。
- Browser Review Bridge 只绑定 `127.0.0.1` 随机端口，短时内存令牌、同源 Origin + Bearer、no-store、严格 CSP、lease/heartbeat；所有业务读写仍转发 Python。
- 现有工作树修改均视为用户资产；只编辑本计划列出的相关文件，不 reset、checkout、clean 或 worktree。

## Task 1：MissionDraft 合同与稳定错误

涉及文件：

- `src/ai_ppt_studio/domains/mission/contracts.py`
- `src/ai_ppt_studio/errors.py`
- `src/ai_ppt_studio/workbench_bridge.py`
- `tests/test_v16_inputs.py`
- `tests/test_cli.py`

步骤：

1. 把输入合同测试改为期望字段齐全后 `status=confirmable`，并覆盖不完整草稿、未知项和不可由 payload 强制写成 confirmed。
2. 新增 `MissionNotConfirmedError`、`MaterialModeUnconfirmedError`、`ProposalOnlyIdentityViolationError` 及稳定错误码映射。
3. 实现 `validate_mission_draft`；保留最窄的旧函数别名只用于调用迁移，不保留旧自动确认语义。
4. 运行聚焦测试并记录检查点，不提交。

## Task 2：独立不可变 MissionConfirmation

涉及文件：

- `src/ai_ppt_studio/domains/mission/contracts.py`
- `src/ai_ppt_studio/application/content_service.py`
- `src/ai_ppt_studio/application/project_service.py`
- `src/ai_ppt_studio/application/v16_bridge.py`
- `src/ai_ppt_studio/application/workspace_projection.py`
- `tests/test_v16_content_chain.py`
- `tests/test_v16_project_service.py`
- `tests/test_v16_bridge.py`
- `tests/test_v16_workspace_projection.py`

步骤：

1. 先写失败测试：保存草稿只产生 `mission-draft`；无确认时正式内容任务和内容 artifact 均被拒绝；确认必须绑定当前 draft、当前材料身份、material mode、用户动作/消息引用与 revision。
2. 新增 `save_mission_draft` 和 `confirm_mission` 服务命令。确认对象写入 `mission/confirmation`，不覆盖 draft；新 draft 或材料身份变化通过引用不一致自然使旧确认过期。
3. 新增 `MissionReadinessPolicy`，同时用于 Agent 内容任务创建和 ContentService 内容 stage/review/acceptance，阻止 Node、UI 或直接 bridge 绕过。
4. 快照与五空间投影增加 `missionDraftRef`、`missionConfirmationRef`、`materialMode`、`contentIdentityMode`；未确认时 overview 主体是任务确认卡。
5. 公共 bridge 增加 `save-mission-draft`、`confirm-mission`；旧 `kind=mission` 迁移为保存草稿，不再确认。
6. 测试辅助构造器必须显式执行一条确认命令，并使用醒目的合成测试引用；这些引用只验证合同，不登记为真实验收证据。

## Task 3：无材料 proposal-only 身份门

涉及文件：

- `src/ai_ppt_studio/domains/materials/contracts.py`
- `src/ai_ppt_studio/domains/content/contracts.py`
- `src/ai_ppt_studio/application/content_service.py`
- `src/ai_ppt_studio/context_compiler.py`
- `tests/test_v16_inputs.py`
- `tests/test_v16_content_chain.py`
- `tests/test_context_compiler_governance.py`
- 新增 `tests/test_v16_mission_readiness.py`
- 新增 `tests/test_v16_proposal_only.py`

步骤：

1. 写失败测试覆盖：无材料且未确认被拒绝；显式 `no-materials-confirmed` 后可启动；后来新增材料会使旧空材料确认失效。
2. 为 confirmation 建立不可变 `emptyMaterialIdentity`；readiness 输出 `material-backed|proposal-only`。
3. proposal-only 的 strategy、claim map、argument map 和 slide draft 必须携带身份标签；客户现状/痛点为 `diagnostic-hypothesis`，方案/范围/路径为 `solution-recommendation`，能力/结果为 `joint-validation-required`。
4. 拒绝缺少身份、把假设写成 supported fact、无来源数字/案例/客户事实或效果承诺，抛出 `PROPOSAL_ONLY_IDENTITY_VIOLATION`。
5. Context Pack 明确带入内容身份模式和三类语言规则；不得把规则降为提示词层软约束。

## Task 4：移除聊天 Widget 并建立诚实侧边栏边界

涉及文件：

- `mcp/server.mjs`
- `mcp/widget-resource.mjs`
- `tests/mcp-server.test.mjs`
- `tests/widget-bundle.test.mjs`
- `widget/src/App.tsx`
- `widget/src/main.tsx`
- `widget/src/types.ts`
- 相关 Widget 测试

步骤：

1. 先改 MCP schema 测试：工具列表不得包含两个 render tool；资源列表不得公开聊天 UI 资源；任何普通工具结果均无 `ui.resourceUri` 或 `openai/outputTemplate`。
2. 删除 `render_ai_ppt_workbench`、`render_ai_ppt_review` 的注册和聊天资源注册；普通数据工具不返回 Widget `_meta`。
3. 新增纯数据 `get_ai_ppt_sidebar_projection`。默认无真实 Host Sidebar Adapter 时返回稳定 `HOST_SIDEBAR_UNAVAILABLE`，同时可附诊断投影，但不渲染 UI。
4. 将前端入口拆为 sidebar shell 与 browser review app；任何生产入口不再请求 inline/fullscreen display mode。
5. 保留静态前端源码供真实侧边栏宿主和 Browser 使用，但组件截图或本地预览不得计作真实侧边栏通过。

## Task 5：Browser Review Bridge 与 Browser Surface Adapter

涉及文件：

- 新增 `mcp/review-bridge.mjs`
- 新增 `mcp/browser-surface-adapter.mjs`
- `mcp/server.mjs`
- `mcp/runtime-bridge/python-runtime.mjs`
- `widget/src/ProfessionalReviewApp.tsx`
- `widget/src/lib/mcp-app-client.ts`
- 新增 `tests/review-bridge.test.mjs`
- `tests/mcp-server.test.mjs`
- 相关 Browser review 前端测试

步骤：

1. 先写协议失败测试：仅监听 127.0.0.1 随机端口；错误 Host、跨源 Origin、无/错 Bearer、过期令牌、scope/sourceVersion 不符、路径穿越、非白名单方法全部拒绝。
2. 实现短时 session：令牌只在内存和 URL fragment；响应 no-store、CSP、no-referrer；日志不含令牌、投影或标记正文。
3. GET 投影与 POST 保存均转发 Python bridge；POST 额外强制同源 Origin、Bearer、expectedRevision、sourceVersion。
4. 实现 lease/heartbeat，页面关闭只减少提示性 lease；最后活跃 lease 到期或 session TTL 到期关闭 server。
5. 新增纯数据 `open_ai_ppt_browser_review`。没有可证明的 Codex Browser Adapter 时返回 `BROWSER_REVIEW_UNAVAILABLE`；只读可开但保存不可用时返回 `BROWSER_REVIEW_SAVE_UNAVAILABLE`，不得宣称闭环通过。
6. Browser 页面从 fragment 取 token 后立即 `history.replaceState` 清除地址，使用 Bearer 读取/保存；不提供 Gate、返回聊天、恢复版本或 PPTX 下载动作。
7. Header 保留内容/视觉双切换；当前会话只提交目标 reviewType，Bridge 从 Python 权威投影取得目标 sourceVersion/revision 后换发新的单类型会话。未保存标记阻断切换并保留草稿。

## Task 6：Skill、脚本、插件包与验收台账同步

涉及文件：

- `skills/ai-ppt-studio/SKILL.md`
- `skills/ai-ppt-studio/references/native-workbench.md`
- `skills/ai-ppt-studio/references/runtime-workflow.md`
- `skills/ai-ppt-studio/references/content-workflow.md`
- `scripts/probe-mcp.mjs`
- `scripts/create-review-preview.mjs`
- `scripts/create-widget-preview.mjs`
- `scripts/acceptance/prepare_real_project.py`
- `requirements/v1.6-acceptance-ledger.json`
- 相关 Skill、bundle、release 与 acceptance 测试

步骤：

1. 删除 MissionBrief 自动确认、render workbench/review、inline/fullscreen 等现行指令；历史说明必须清楚标为历史。
2. Skill 工作流改为：保存 MissionDraft → 展示任务/材料/未知项 → 获取真实用户确认引用 → confirm mission → 内容前置门 → proposal-only/material-backed。
3. 探测脚本只验证纯数据工具、侧边栏明确能力缺口和 Browser adapter/bridge 合同，不生成聊天 Widget 截图。
4. 真实项目准备脚本只保存 draft；没有真实用户证据不得替项目 confirm mission。
5. 台账把旧自动确认与聊天 Widget 证据标为历史/失效；新增验收项保持 open，直到真实能力证据完成。

## Task 7：验证与真实验收恢复边界

1. 运行 Python 聚焦测试、Node MCP/bridge 测试、Widget 单测和构建。
2. 运行项目全量测试与插件包验证；区分本次回归、既有脏树失败和真实宿主能力阻断。
3. 检查普通聊天工具结果无 UI template，side bar 缺失稳定报错，Browser bridge 安全用例全部通过。
4. 检查真实项目仍为 revision 51，未创建 MissionConfirmation、未恢复 G0/G2、未写 PPTX、未登记伪造凭据。
5. 重新计算 104 项台账。只有 104/104 且真实侧边栏、Browser 打开/保存和四目标软件证据均真实存在时，才进入提交决策；此前不 commit。

## 完成定义

- 任务字段齐全只能到 `confirmable`。
- 无当前 `MissionConfirmation` 或材料模式未确认，正式内容任务与直接 artifact 提交都在 Python 服务端失败。
- proposal-only 身份贯穿内容链，身份违规稳定失败。
- 聊天消息不再渲染工作台或专业审阅 Widget。
- 侧边栏能力缺失诚实阻断；Browser review 使用受限 loopback bridge，不回退聊天 UI。
- Skill、脚本、MCP、Python、前端和验收台账引用同一合同。
- 全量回归结果可复现；104/104 前无提交。
