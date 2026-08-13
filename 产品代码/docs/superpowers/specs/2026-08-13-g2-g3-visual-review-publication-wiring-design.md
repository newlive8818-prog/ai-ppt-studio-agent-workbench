# AI PPT Studio G2→G3 视觉审阅发布接线设计

## 1. 文档状态

- 日期：2026-08-13
- 状态：设计已获用户确认，等待书面规格复核
- 适用版本：AI PPT Studio v1.6
- 真实恢复项目：`/Users/defei/Documents/AI-PPT-Workspace/projects/v16-final-real-acceptance-proposal-only`
- 恢复起点：revision 59；G0、G1、G2 已通过，G3/G4 锁定
- 发布目标策略：仅 `macos-powerpoint` 为必需目标；`macos-wps`、`windows-powerpoint`、`windows-wps` 延期

## 2. 背景与根因

真实项目已通过新的宿主原生 G0 凭据升级，并以当前 `ReleaseTargetPolicy` 和七项精确证据通过 G2。G2 成功事务只负责冻结内部视觉 lineage 和写入 `G2=passed`，这是正确行为。

按现有权威领域设计，G2 之后还必须执行独立的 `VisualService.publish_visual_review()`：它从当前 G2 lineage、内容蓝图、Deck Design System、VisualContractSet、AnchorSet、内部审查、当前发布策略和全部必需目标证据生成不可变 `visual-contract`，再把 G3 从 `locked` 变为 `user-reviewable`。只有这个发布事务完成后，Codex Browser 才能打开视觉专业审阅，用户才能确认 G3。

当前 Python 服务已经实现并测试该事务，但公共 v1.6 bridge 和 MCP 工具表没有暴露对应操作。Agent 因而无法通过正式产品路径完成发布。与此同时，快照的 `current_gate` 采用“查找第一个既非 locked 又非 passed 的 Gate，否则回退 G4”的算法；在 `G2=passed / G3=locked / G4=locked` 的合法发布前过渡态中，它错误返回 G4。

因此存在两个相关但边界清晰的缺陷：

1. 视觉审阅发布能力未接入公共 bridge/MCP；
2. `current_gate` 不能表达 G2 后、G3 发布前的过渡态。

## 3. 方案比较

### 3.1 方案 A：公开独立发布操作（采用）

新增一个薄 bridge 操作和一个公开 MCP 工具，唯一调用现有 `VisualService.publish_visual_review()`。运行时自行解析权威 heads、生成视觉合同并推进 G3。同步修正快照阶段投影。

优点：保留“G2 内部通过”和“G3 用户审阅发布”两个事务边界；可从当前 revision 59 原地恢复；Agent 无法自组装 Gate lineage；符合现有服务和测试结构。

### 3.2 方案 B：将发布隐式并入 `record_internal_gate(G2)`

这样可减少一次调用，但会把内部质量门与用户审阅发布混为一个事务，破坏既有领域边界，也无法自然恢复已经停在 revision 59 的真实项目，因此不采用。

### 3.3 方案 C：复用 `commit_ai_ppt_artifact(visual-contract)`

该工具现有 `visual-contract` vocabulary 用于登记 Deck Design System、VisualContractSet、VisualReviewRecord 或 ImageAssetPack 等生产 artifact。让 Agent传入最终用户审阅合同，会把本应由权威运行时冻结的 G2 lineage 重新交给调用方拼装，可能遗漏或替换 policy/evidence identities，因此不采用。

## 4. 正式公共合同

### 4.1 Python bridge

新增操作：

```text
publish-visual-review
```

请求字段只有：

```json
{
  "operation": "publish-visual-review",
  "project_root": "/absolute/managed/project",
  "expected_revision": 59
}
```

bridge 必须：

1. 解析 schema 3 项目；
2. 生成 revision-safe command identity；
3. 调用 `VisualService.publish_visual_review(command_id, expected_revision)`；
4. 返回新的权威 snapshot，以及新 `visual/contract` artifact ref；
5. 不接受视觉合同 payload、sourceVersion、目标数组、证据 refs 或 Gate 状态参数。

所有 lineage、策略和证据均由现有 Python 服务从当前项目 heads 解析。`REVISION_CONFLICT`、G2 未通过、G0 凭据失效、G2 lineage 缺失/漂移、策略陈旧或证据不匹配时，事务必须零写入失败。

### 4.2 MCP 工具

新增公开工具：

```text
publish_ai_ppt_visual_review
```

输入 Schema：

```ts
{
  projectRoot?: string;
  expectedRevision: number;
}
```

成功返回：

- 新 revision；
- `visualContractRef`；
- 权威 snapshot；
- 明确文案“视觉合同已发布，可进入 G3 专业审阅”。

工具是 revision-safe、非破坏性业务写入，不附带 MCP UI template，不直接打开 Browser，也不接受任意 artifact payload。

### 4.3 Gate 与 artifact 结果

在当前真实项目 revision 59 上成功执行时，预期一次事务进入 revision 60：

```text
G0 = passed
G1 = passed
G2 = passed
G3 = user-reviewable
G4 = locked
```

并新增：

```text
visual/contract = artifact://visual-contract/<sha256>
event_type = visual.review-published
```

视觉合同必须绑定：

- 当前 content blueprint；
- 当前 visual brief 与 convergence；
- 当前 Deck Design System 与 VisualContractSet；
- 当前 AnchorSet；
- 当前 G2 reviewed lineage；
- 当前 `ReleaseTargetPolicy`；
- 当前 required target IDs；
- 当前 deferred target IDs；
- G1/G2 内部审查 refs；
- 仅当前必需目标的 G2 target evidence refs 与可读 identities。

当前 v1.6 只能把 `macos-powerpoint` 纳入必需证据。三项延期 profile 只作为延期身份显示，不得产生或继承通过结论。

## 5. current_gate 投影

`current_gate` 是阶段投影，不是 Gate 写入权限。它必须覆盖全部合法状态组合，并以最早尚未完成的阶段为准。

当前修复的关键规则：

```text
G2=passed, G3=locked, visual/contract missing
=> current_gate=G3
```

发布成功后：

```text
G3=user-reviewable
=> current_gate=G3
```

只有 `G3=passed` 且 G4 尚未通过时才可投影 `current_gate=G4`。不得用默认 G4 掩盖全 locked、非法组合或待发布过渡态。

本次只修正阶段选择，不直接修改任何 Gate 状态，不允许投影逻辑替代 GateEvaluator。

## 6. Browser 与 G3 后续流程

公共发布成功后，Agent 必须按以下顺序继续：

1. 刷新 snapshot，确认 G3=`user-reviewable` 并取得当前 `visual/contract` ref；
2. 调用 `open_ai_ppt_browser_review(reviewType=visual, sourceVersion=<visual-contract-ref>)`；
3. 若返回 `review-session-ready`，立即使用 Codex 内置 Browser 打开 scoped URL；
4. 实际读取完整视觉合同并检查当前发布目标区只把 macOS Microsoft PowerPoint 作为 required；
5. 检查三项延期目标显示 `延期 · 当前版本不验收`，没有 WPS/Windows/跨平台通过声明；
6. 验证页面读取和必要的显式保存链路；测试标记必须清理，不能污染真实业务审阅；
7. 只有 Browser 验证成功后，才请求用户针对当前 sourceVersion 做宿主原生 G3 确认；
8. 用户确认 G3 前不得构建完整 12 页 PPTX。

## 7. 错误与恢复

- 发布前 revision 冲突：刷新 snapshot，不重放旧 revision 请求；
- G2 未通过：返回 Gate blocker，不生成视觉合同；
- G2 lineage 或 policy 漂移：停止并诊断，不拼装替代证据；
- 同一 command identity 重试：遵守 kernel 幂等语义，不产生第二份有效事务；
- Browser 会话建立失败：保持 G3 user-reviewable，报告准确的 Review Bridge 能力缺口；
- Browser 导航失败：保持项目状态，报告 `BROWSER_REVIEW_UNAVAILABLE`，不回退聊天 Widget；
- 保存失败：保留未保存草稿并报告 `BROWSER_REVIEW_SAVE_UNAVAILABLE`；
- 用户拒绝或取消 G3：项目不进入 G4，不构建完整成稿。

## 8. 测试设计

实现必须按 RED→GREEN 完成以下最小覆盖：

### 8.1 Python bridge

- `publish-visual-review` 在 prepared G2 项目上生成 `visual/contract`；
- revision 增长一次；
- G3 变为 `user-reviewable`，G4 保持 `locked`；
- 返回 artifact ref 与 snapshot 一致；
- G2 未通过、revision 冲突和 lineage 漂移均零写入失败。

### 8.2 快照投影

- `G2=passed / G3=locked / G4=locked` 投影 `current_gate=G3`；
- 发布后 G3 user-reviewable 仍投影 G3；
- G3 passed/G4 open 投影 G4；
- 不改变原始 `gates` 字典。

### 8.3 MCP

- 工具列表新增 `publish_ai_ppt_visual_review`；
- Schema 只暴露 projectRoot/expectedRevision；
- 请求精确路由为 `publish-visual-review`；
- 成功返回 revision、visualContractRef 和 snapshot；
- bridge 错误保持结构化错误，不误报 Browser 已打开；
- `open_ai_ppt_browser_review` 的既有两段式交接测试继续通过。

### 8.4 回归与发布

- Python 全套测试；
- Node MCP/Review Bridge 全套测试；
- Widget/UI 接受测试；
- Skill validator、release verifier、`git diff --check`；
- 发布安装后独立 MCP probe 显示新工具，工具总数从 18 增至 19；
- 新进程真实读取 revision 59 后，才允许对真实项目执行发布事务。

## 9. 非目标

本次不做以下工作：

- 不把 G2 与发布事务合并；
- 不让 Agent自行构造最终视觉合同；
- 不修改 G2 已通过的七项证据；
- 不生成 WPS 或 Windows 证据；
- 不声明 WPS、Windows 或跨平台兼容；
- 不在 G3 前创建完整 12 页 PPTX；
- 不绕过 Codex Browser、宿主原生 G3 确认或 Codex Presentations；
- 不把本次接线修复或 G2 通过夸大为最终 104/104；
- 不清理、重置或覆盖当前脏工作树中的其他用户改动。

## 10. 完成标准

只有同时满足以下条件，本专项接线修复才可声明完成：

1. 测试先失败并证明缺失行为；
2. 最小实现使新增测试和既有回归全部通过；
3. 新插件实际安装且新 stdio 进程加载 19-tool schema；
4. 真实项目通过公开 MCP 从 revision 59 进入 revision 60；
5. G3 为 `user-reviewable`，G4 仍锁定；
6. 真实 Codex Browser 成功打开并读取当前视觉合同；
7. 读取/保存链路与延期目标文案均经过现场核验；
8. 完整 12 页仍未在用户 G3 确认前构建；
9. 严格 104 项台账只按真实 proof mapping 更新，不因本专项成功自动置满。
