# Agent Browser Review Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 AI PPT Studio 正式 stdio 入口未注入 Browser adapter 时无法建立专业审阅会话的问题，并由 Agent 使用 Codex In-app Browser 完成两段式打开与保存闭环。

**Architecture:** MCP Server 只负责验证权威投影并创建短时 loopback Review Bridge；它可以使用可选 adapter 直开，但生产默认返回 scoped URL 与明确的 Agent Browser 动作。Review Bridge 继续独占读取/保存安全合同，Python 继续作为业务真相源。

**Tech Stack:** Node.js ESM、MCP SDK、Node test、Python unittest、React/Vite、Codex In-app Browser、loopback HTTP Review Bridge。

---

### Task 1: 锁定 MCP 两段式交接合同

**Files:**
- Modify: `tests/mcp-server.test.mjs`
- Modify: `mcp/server.mjs`

- [ ] **Step 1: 写失败测试**：把“无 adapter 返回 BROWSER_REVIEW_UNAVAILABLE”改为“无 adapter 返回 `review-session-ready`、`opened=false`、`openMode=agent-browser`、`browserAction=open-scoped-url` 和 scoped URL”；增加 adapter 打开失败回退与 `canSave=false` 不阻断用例。
- [ ] **Step 2: 运行 `node --test tests/mcp-server.test.mjs`**，确认新用例因现有 adapter 前置检查而失败。
- [ ] **Step 3: 最小实现**：先校验 projection，再创建 session；可选 adapter 成功时返回直开，缺失/失败时返回 Agent 交接结果；只在 session 创建本身失败时返回准确 Bridge 错误。
- [ ] **Step 4: 重跑专项测试**，确认所有 MCP 合同通过。

### Task 2: 修复两段式会话生命周期

**Files:**
- Modify: `tests/review-bridge.test.mjs`
- Modify: `mcp/review-bridge.mjs`

- [ ] **Step 1: 写失败测试**：未首次 Bearer API 激活的会话跨过短 lease 后仍存活；硬 TTL 后停止；首次激活后短 lease 到期仍停止。
- [ ] **Step 2: 运行 `node --test tests/review-bridge.test.mjs`**，确认未激活宽限用例失败。
- [ ] **Step 3: 最小实现**：加入 `activated` 状态；首次授权 API 请求时激活并续租；激活前 sweep 只看硬 TTL，激活后同时看短 lease。
- [ ] **Step 4: 重跑 Review Bridge 专项测试**。

### Task 3: 更新生产探测与 Skill 行为

**Files:**
- Modify: `scripts/probe-mcp.mjs`
- Modify: `skills/ai-ppt-studio/SKILL.md`
- Modify: `skills/ai-ppt-studio/references/runtime-workflow.md`
- Modify: `skills/ai-ppt-studio/references/native-workbench.md`
- Modify: `skills/ai-ppt-studio/references/four-target-acceptance.md`
- Modify: `tests/test_skill_workflow.py`
- Modify: `tests/test_v16_support_scripts.py`

- [ ] **Step 1: 写失败断言**：Skill 必须包含 Agent 打开返回 scoped URL、不得把 session-ready 表述成 opened、MCP adapter 缺失不是宿主 Browser 缺失；probe 必须期待 `BROWSER_REVIEW_AVAILABLE` 和 `review-session-ready`。
- [ ] **Step 2: 运行相关 Python 测试和 `npm run probe:mcp`**，确认旧文案/旧探测失败。
- [ ] **Step 3: 更新 Skill 与 probe**：probe 先从 Python 读取权威 sourceVersion，再调用正式 stdio 工具建立 session；结果只证明 Bridge handoff，不伪造真实 Browser 证据。
- [ ] **Step 4: 重跑相关测试与 probe**。

### Task 4: 同步权威基线与验收语义

**Files:**
- Modify: `../00-唯一研发基线索引-v1.0.md`
- Modify: `../01-产品需求基线-v1.0.md`
- Modify: `../02-系统详细设计-v1.0.md`
- Modify: `../03-UI设计与交互规范-v1.0.md`
- Modify: `docs/validation/2026-08-11-v16-final-acceptance.md`

- [ ] **Step 1: 更新唯一合同**：明确 MCP 准备会话、Agent 调用 Codex In-app Browser、Review Bridge 保存；纠正 Browser adapter `canSave` 与错误语义。
- [ ] **Step 2: 保持证据状态诚实**：自动化通过只标为 Bridge handoff 已实现；真实 Browser 打开/保存必须有当前宿主实证才计入严格台账。
- [ ] **Step 3: 检查待确认/待验证状态没有被改写成已确认事实。

### Task 5: 完整回归、发布和真实验收

**Files:**
- Verify: repository and built plugin release

- [ ] **Step 1: 运行 `python3 -m unittest discover -s tests`。**
- [ ] **Step 2: 运行 `npm test`、`npm run probe:mcp`、`npm run accept:v16-ui`。**
- [ ] **Step 3: 运行发布构建和发布包验证，确认安装包内 Skill、MCP 与源码一致。**
- [ ] **Step 4: 安装新 build，使用 Codex In-app Browser 打开真实 scoped URL，读取投影并验证显式保存链路。**
- [ ] **Step 5: 从项目根检查四份基线相对链接、原型引用、目录边界和 `git diff --check`。**
- [ ] **Step 6: 只有全部可执行验收通过后更新实现状态；任何仍依赖外部宿主/真实项目/四目标桌面软件的项目继续保持未通过。**

