# 视觉专业审核生产前端 UI 验收记录

## 1. 验收身份

- 验收日期：2026-08-19
- 用户明确结论：`OK 符合要求`
- 验收对象：当前生产 React 视觉专业审核前端，包括 `3 页锚点成果` 与 `完整视觉合同`
- 分支：`codex/review-surface-v22`
- 前端对象提交：`33ef088 feat: prepare visual review frontend candidate`
- 前端保真基础提交：`38f400f feat: restore visual contract document fidelity`
- 验收前基线提交：`3e84048 docs: sync v2.5 visual review baseline`
- 交互参考：`产品代码/prototypes/07-visual-anchor-chat-collaboration-prototype.html`
- 07 原型 SHA-256：`3b4e5a623fd0a2e9717d2015d1b3f03b5cd4baf9f9599cce2594df1abd911a4f`
- 验收证据类型：当前 Codex 任务中的用户明确消息

本记录保存用户对当前生产 React 前端的 UI 验收结论。它确认前端展示、布局、功能和交互符合本轮已确认范围，但不把本地预览、自动化检查或用户对前端的认可改写为 Runtime、Review Bridge、MCP、真实宿主或 Gate 已经通过。

## 2. 状态结论

```yaml
visualContractProductionUiAcceptance: accepted
runtimeReviewBridgeMcpAcceptance: not-in-scope
realHostEvidence: false
hostNotificationEvidence: false
aiReceiptEvidence: false
gateConfirmation: none
```

## 3. 用户接受的生产前端范围

### 3.1 3 页锚点成果

- 顶部直接切换 `3 页锚点成果 / 完整视觉合同`，不出现产品导航或聊天流；
- 不显示锚点项目徽标或常驻右侧辅助区；
- 空状态不显示反馈批次面板；
- 用户完成矩形框选并加入第一条真实反馈后，画布下方才出现紧凑内联批次；
- 保留矩形框选、多条反馈、跨页积累、编辑、移除和统一提交；
- 保存、宿主通知、AI 接收和 G3 继续作为相互隔离的事实。

### 3.2 完整视觉合同

- 桌面端使用单条约 64px 顶栏，双视图、目录、保存状态、标记数量和保存动作处于同一顶栏；
- 不显示第二条 sticky 操作栏或可见 G1/G2/revision 技术账本；
- 目录从左侧覆盖，标记抽屉从右侧覆盖，两者不长期压缩正文；
- Deck Design System 显示真实色板，并把字体、密度等对象转为可阅读文字；
- Anchor Slide Evidence 显示 `slide_id / 锚点内容标题 / 验证目的`；
- 逐页冻结内容显示 `核心主张 / 页面可见文案 / 讲解备注 / 来源引用`；
- `page_task` 不冒充 `core_claim`；
- 字段标记使用轻量评论入口，文字范围标记只在用户真实选择正文后上下文出现；
- 后端暂缺 `core_claim` 时，前端仍保留已经验收的 `S01 核心主张` 标记入口；后台现有键或字段缺口不决定前端功能是否存在。

## 4. 工程与 Browser 证据

验收对象在用户确认前完成了以下本地工程检查：

- `npm run test:widget`：12 个测试文件通过，`518 / 518` 测试通过；
- `npm run typecheck`：通过；
- `npm run build`：通过；
- `git diff --check`：通过。

应用内 Browser 人工检查覆盖：

- 桌面和 390 CSS px 窄宽下顶栏均为约 64px；
- 390 CSS px 下双视图按钮水平显示、无裁切且页面无横向溢出；
- 目录从左侧覆盖、标记抽屉从右侧覆盖；
- 缺少 `core_claim` 的兼容数据仍能打开核心主张标记输入；
- 检查期间控制台无 error 或 warning。

验收过程生成了两张临时截图，作为本次会话中的视觉核对工作文件，不作为持久化仓库制品：

- `/private/tmp/ai-ppt-v25-visual-contract-desktop.png`，SHA-256 `cc83ab73de68b9c0a2be9e121199d7e34617353c3a3c9de8ed56928d288c5f6e`；
- `/private/tmp/ai-ppt-v25-anchor-mobile-390.png`，SHA-256 `f684c7caf2cd7262edb5c30d14aa7fe0858baecc0a0a3b1c75b3b914743f9c31`。

Playwright 自动验收仍在当前 macOS sandbox 中被以下环境错误阻断：

```text
mach_port_rendezvous_mac.cc
Permission denied (1100)
```

该结果登记为 `CapabilityGap`。它不是源码断言失败，也不能写成 Playwright 自动 UI 验收通过。

## 5. 验收边界

本次通过只代表提交 `33ef088` 所对应生产前端的当前 UI 展示、布局、功能和交互得到用户接受，不代表：

- 真实 ReviewSession 已创建、打开、恢复或完成并发验证；
- AnchorFeedbackBatch 或 VisualContractReviewMarkSet 已通过正式 Review Bridge 写入 Python Runtime；
- Runtime、Review Bridge 或 MCP 投影已经按前端字段完成收窄；
- 真实宿主已打开页面或发送通知；
- AI 已收到反馈或返回接收回执；
- G1、G2、G3、G4 或任何产品 Gate 已确认；
- Playwright、真实宿主或长文档端到端验收已经通过。

保存、本地预览、Browser 人工检查和用户 UI 验收都不能推导上述事实。

## 6. 下一阶段准入与回退边界

本记录使系统详细设计中的 `Slice F2：视觉审核投影收窄` 达到启动准入条件，但 Slice F2 在本提交中尚未启动。下一阶段必须另建计划、独立提交和独立回退点，并按已经验收的前端真实消费关系反向拆解：

```text
VisualReviewPageViewModel
-> Review Bridge projection
-> MCP contract
-> Runtime projection
-> persistence / host notification / AI receipt
```

后台新增字段不得自动增加 UI；后台现有缺字段也不得删除、改名或降级已经验收的前端结构。若后端兼容需要与当前 UI 合同冲突，必须保留前端合同并把冲突登记为投影或能力缺口，不能用后端现状反向改写本次验收结论。
