# UI-03 内容审核侧边栏 v2.1 验证记录

## 1. 记录身份

- 日期：2026-08-14
- 验证对象：最大宽度、连续全稿、图文结合的 UI-03 内容审核侧边栏
- 对应基线：产品需求 v2.1、系统详细设计 v2.1、UI 设计与交互规范 v2.1
- 自动化提交：`6aa744e`，后续截图可读性修正：`16606bc`
- 结论：确定性合同、组件、MCP、响应式和本地 Chromium 预览通过；真实 Codex 最大宽度侧边栏、真实宿主回写、真实 Agent 批次接收、真实 Browser handoff 与 PowerPoint/WPS 均未由本记录证明。

本记录不改变严格 acceptance ledger，不把 fixture、自动化或本地预览写成真实项目、真实宿主或真实桌面验收。

## 2. 证据分层

| 层级 | 本次证据 | 能证明 | 不能证明 |
|---|---|---|---|
| Deterministic fixture | `deterministic-contract-fixture-not-real-project-proof` | 稳定场景、字段、页面数量、判断状态和错误分支可重复 | 真实客户事实、真实项目质量、真实用户接受 |
| Automated test proof | Vitest、Node unittest、Python unittest、TypeScript、MCP probe、UI acceptance | 代码合同、DOM、状态、交互、并发/冲突、工具 schema 和错误边界 | Codex 宿主实际渲染和真实 Agent 是否收到消息 |
| Local browser preview | bundled Playwright + 本机构建产物 | 当前构建在指定宽度下的布局、视觉、无溢出、交互和 console 状态 | 真实 Codex 侧边栏容器、宿主权限、真实 Browser/PowerPoint |
| Genuine Codex host evidence | 本次没有 | 无 | 最大宽度宿主、真实保存、真实 follow-up、AI 接收回执 |
| Genuine Browser/PowerPoint evidence | 本次没有 | 无 | scoped Browser handoff、真实 PowerPoint/WPS 渲染、G3/G4 |

确定性预览中的材料图像用于验证“正文与材料同屏、图片近视口加载和证据元数据布局”，不是客户材料真实性证明；fixture 中的来源、案例和 PPTX 哈希也不进入真实 Gate。

## 3. Deterministic fixture

`scripts/seed-v16-ui-project.py` 公开以下稳定场景身份：

1. `content-producing`
2. `content-hard-gate-review`
3. `content-hard-gate-failed`
4. `content-hard-gate-repaired`
5. `ready-10`
6. `mixed-decisions-24`
7. `long-review-60`
8. `save-failure`
9. `source-conflict`
10. `submitted-frozen`
11. `plan-proposed`
12. `new-version-zero-decisions`

所有场景统一标记：

```text
deterministic-contract-fixture-not-real-project-proof
```

`scripts/create-widget-preview.mjs` 使用正式 `ContentReviewDocument`、`ContentSlideSection`、`PageDecisionEditor` 和 `ReviewBatchFooter` 生成静态预览；预览桥只为确定性验收提供投影、保存结果、固定失败/冲突和提交计数。它不进入生产宿主，不写权威项目，不形成 Gate 事实。

生成的 UI-03 预览包括：

- `content-review-producing.html`
- `content-review-hard-gate.html`
- `content-review-hard-gate-failed.html`
- `content-review-hard-gate-repaired.html`
- `content-review-ready-10.html`
- `content-review-mixed-24.html`
- `content-review-ready-24.html`
- `content-review-long-60.html`
- `content-review-save-failure.html`
- `content-review-source-conflict.html`
- `content-review-submitted-frozen.html`
- `content-review-plan-proposed.html`
- `content-review-new-version-zero.html`

## 4. Automated test proof

### 4.1 聚焦合同

```text
PYTHONPATH=src python3 -m unittest tests.test_v16_ui_seed tests.test_v16_support_scripts
Ran 4 tests
OK
```

覆盖 seed 身份、场景清单、UI-03 预览入口、正式侧边栏选择器、24 页批次状态、10/60 页场景和历史 ProfessionalReviewApp 不再作为内容主验收表面。

### 4.2 Widget

```text
npm run test:widget
Test Files 16 passed (16)
Tests 63 passed (63)
```

其中直接覆盖：完整正文与证据、四类 PageDecision、非认可意见必填、失败/冲突保留草稿、静默单页保存、不可变批次、一次 follow-up、10/24/60 页连续 DOM、最大宽度、900px 单/双栏断点、内容证据 Browser 只读和 visual G3 回归。

### 4.3 Node 与 Review Bridge

```text
npm run test:node
tests 38
pass 38
fail 0
```

普通沙箱首次运行时 9 个 Review Bridge 用例因 `listen EPERM 127.0.0.1` 失败；保持代码和命令不变、仅允许本机 loopback 后，38/38 通过。该结果证明 Review Bridge 合同，不证明真实 Codex Browser 已打开。

### 4.4 Python Runtime

```text
PYTHONPATH=src python3 -m unittest discover -s tests
Ran 314 tests
OK
```

覆盖内容审核批次、修改方案、G0 lineage、revision、幂等、冻结、撤回、下游清理、只读证据会话和既有 Gate/交付回归。

### 4.5 构建、类型与 MCP

```text
npm run build                              # exit 0
npx tsc -p widget/tsconfig.json --noEmit   # exit 0
npm run probe:mcp                          # ok=true, tool_count=25
git diff --check                           # exit 0
```

MCP probe 现在自行创建隔离 schema 3 seed，不再读取可能漂移或损坏的默认用户项目。它确认内容审核工具、visual-only `open_ai_ppt_browser_review`、只读 `open_content_evidence_browser`、`HOST_SIDEBAR_UNAVAILABLE` 和 `BROWSER_REVIEW_UNAVAILABLE` 的能力边界。

## 5. Local browser preview

运行：

```text
npm run accept:v16-ui
```

最新结果文件：

```text
output/playwright/v16-ui/v16-ui-acceptance.json
```

结果：`ok=true`。UI-03 共 16 组浏览器检查，另保留 9 组工作台/visual G3 截图与 visual 120 页长文档回归。UI-03 检查包括：

| 场景 | 结果 |
|---|---|
| 480 / 900 / 1200 / 1440 | 无横向溢出；正文容器使用全部宽度；480 单栏，900+ 正文/证据双栏 |
| ready-10 | 10 个唯一页面 anchor；完整文字、图片/材料、来源/用途/处理、映射、逐字稿、阅读质量和前后关系存在 |
| 目录 | 覆盖打开，不改变正文几何 |
| 截断 | 正文和逐字稿没有 ellipsis 或 line-clamp；图片为近视口加载 |
| content-producing / hard-gate | 内部通过前不泄露逐页内容 |
| mixed-decisions-24 | 23/24 时批次按钮禁用 |
| ready-24 | 24/24 时按钮启用；提交一次；follow-up 恰好一次 |
| save-failure | 判断与完整意见保留；提交继续阻断 |
| source-conflict | 判断与完整意见保留；显示版本冲突；提交继续阻断 |
| submitted-frozen | 24 页判断全部冻结 |
| plan-proposed | 冻结批次保持，等待整套方案 |
| new-version-zero-decisions | 新 sourceVersion 的 24 页全部从 0 开始，不继承认可 |
| long-review-60 | 60 个唯一 anchor 和最后一页完整逐字稿存在，无横向溢出 |
| visual G3 | 760 / 1000 / 1440、100% / 200% 回归通过；120 页完整视觉合同回归通过 |
| console | 上述场景没有相关 error |

Playwright 截图使用当前 viewport，不把 `content-visibility: auto` 的离屏占位区域误当成完整视觉截图；全篇完整性由 DOM anchor、最后一页文本、无截断和长文档断言证明。

应用内 Browser 直接打开本地 `file://` 构建产物时，被 Codex Browser URL 安全策略拒绝。没有绕过该策略；因此本节的浏览器证据身份仍是 bundled Playwright 本地预览，不是 Codex Browser 证据。

## 6. Genuine Codex host evidence

以下保持 `待验证`：

- 真实 Codex 侧边栏是否向 UI-03 提供宿主最大宽度；
- 真实宿主投影是否能在 10/24/60 页保持相同阅读性能；
- 真实 `save_content_page_decision` 回写、revision 刷新和失败恢复；
- 真实 `submit_content_review_batch` 后是否只触发一个宿主 follow-up；
- 售前方案总师是否实际收到完整冻结批次并返回整套修改方案；
- 新 sourceVersion 在真实宿主是否从零 PageDecision 开始；
- 真实宿主保存、通知和 AI 接收回执的身份。

在取得上述证据前，不得把 `HOST_SIDEBAR_UNAVAILABLE` 改成 passed，也不得将 deterministic fixture 或 local preview 写入正式 Gate。

## 7. Genuine Browser/PowerPoint evidence

以下保持 `待验证`：

- 真实 Codex Browser 的 scoped visual handoff；
- 真实 content-evidence Browser 从 UI-03 打开并保持未保存判断；
- 真实 Browser 保存/通知/AI 回执；
- macOS PowerPoint 当前 PPTX 的真实渲染与 G2/G4 证据；
- macOS WPS、Windows PowerPoint、Windows WPS；三者当前为 deferred，不能写成通过、失败或兼容。

本次没有修改 acceptance ledger，也没有生成任何 PowerPoint/WPS 通过声明。

## 8. 当前验收结论

UI-03 的确定性实现和本地构建满足本轮自动化验收：它是最大宽度、连续全稿、图文结合的完整阅读表面；支持逐页四选一、非认可意见、失败恢复、整批冻结、集中处理和新版全篇复审；内容 Browser 只做证据，visual G3 Browser 回归保留。

严格产品验收仍未完成，因为真实 Codex 宿主、真实 Agent 接收回执、真实 Browser handoff 和真实 PowerPoint 证据尚未取得。这些缺口属于能力/环境证据边界，不由本地测试替代。
